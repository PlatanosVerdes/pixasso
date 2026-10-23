import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from . import discover, fit
from .config import Config
from .tv import ArtTV, TVUnavailable

log = logging.getLogger(__name__)

COMMANDS = [
    ("help", "How it works"),
    ("tv", "Choose the TV"),
    ("list", "Pictures on the TV"),
    ("crop", "Crop the next photo"),
    ("rotate", "Cycle the pictures: <minutes> or off"),
    ("exit", "Leave art mode"),
]
HELP = (
    "Send me a photo (better as a file, it keeps the quality) and I hang it on the TV.\n\n"
    "/{p}tv - find the TVs on the network and choose one\n"
    "/{p}list - the pictures on the TV, to show or delete\n"
    "/{p}crop - crop the next photo without asking\n"
    "/{p}rotate <minutes> - cycle through them, /{p}rotate off stops it\n"
    "/{p}exit - leave art mode and go back to the TV home"
)
TV_DOWN = "The TV is not answering. Is it on, in art mode, and chosen with /tv?"


def build(cfg: Config) -> Application:
    tv = ArtTV(cfg.data_dir, cfg.tv_host, cfg.tv_timeout)
    allowed = filters.Chat(chat_id=list(cfg.allowed_chats))

    async def on_start(app: Application) -> None:
        if not cfg.push:
            # On a shared bot switchboard publishes the menu; on its own bot pixasso does.
            await app.bot.set_my_commands(COMMANDS)
        try:
            await tv.pair()
        except TVUnavailable as e:
            log.warning("TV pairing skipped: %s", e)

    builder = Application.builder().token(cfg.telegram_token).post_init(on_start)
    if cfg.push:
        # No updater: switchboard reads the bot and posts each update here.
        builder = builder.updater(None)
    app = builder.build()
    app.bot_data["tv"] = tv
    app.bot_data["allowed"] = cfg.allowed_chats
    app.bot_data["prefix"] = p = cfg.prefix
    app.bot_data["subnet"] = cfg.scan_subnet

    app.add_handler(CommandHandler([p + "help", p + "start"], help_cmd, filters=allowed))
    app.add_handler(CommandHandler(p + "tv", tv_cmd, filters=allowed))
    app.add_handler(CommandHandler(p + "list", list_cmd, filters=allowed))
    app.add_handler(CommandHandler(p + "crop", crop_cmd, filters=allowed))
    app.add_handler(CommandHandler(p + "rotate", rotate_cmd, filters=allowed))
    app.add_handler(CommandHandler(p + "exit", exit_cmd, filters=allowed))
    app.add_handler(MessageHandler(allowed & (filters.PHOTO | filters.Document.IMAGE), picture))
    app.add_handler(CallbackQueryHandler(button, pattern=f"^{p}(show|delete|tv|fit):"))
    app.add_error_handler(on_error)
    return app


def tv_of(ctx: ContextTypes.DEFAULT_TYPE) -> ArtTV:
    return ctx.application.bot_data["tv"]


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP.format(p=ctx.application.bot_data["prefix"]))


async def crop_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.chat_data["crop_next"] = True
    await update.effective_message.reply_text("The next photo will be cropped to fill the screen.")


async def picture(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    media = msg.document or msg.photo[-1]
    data = bytes(await (await media.get_file()).download_as_bytearray())
    if ctx.chat_data.pop("crop_next", False) or await asyncio.to_thread(fit.fits_screen, data):
        await hang(msg, ctx, data, crop=True)
        return
    # Only the latest photo waits for an answer: one per chat keeps the memory bounded.
    ctx.chat_data["pending"] = data
    p = ctx.application.bot_data["prefix"]
    await msg.reply_text("This photo is not 16:9. How should it go on the TV?", reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("✂️ Crop to fill", callback_data=f"{p}fit:crop"),
        InlineKeyboardButton("🖼 Whole", callback_data=f"{p}fit:whole"),
    ]]))


async def hang(msg, ctx: ContextTypes.DEFAULT_TYPE, data: bytes, crop: bool) -> None:
    status = await msg.reply_text("Hanging it...")
    jpeg = await asyncio.to_thread(fit.fit, data, crop)
    tv = tv_of(ctx)
    try:
        content_id = await tv.upload(jpeg)
    except TVUnavailable as e:
        log.warning("photo not uploaded: %s", e)
        await status.edit_text(TV_DOWN)
        return
    try:
        await tv.show(content_id)
    except TVUnavailable as e:
        # Seen on a Q8F: the TV switches to the picture but never sends the confirmation.
        log.warning("no confirmation showing %s: %s", content_id, e)
    try:
        current = await tv.current()
    except TVUnavailable as e:
        log.warning("could not check the TV after %s: %s", content_id, e)
        await status.edit_text(f"Uploaded as {content_id}, but the TV did not say what it shows.")
        return
    if current == content_id:
        await status.edit_text("✓ On the TV.")
    else:
        await status.edit_text(f"Uploaded as {content_id}, but the TV still shows {current}. Try /list and Show.")


async def list_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    try:
        pictures = await tv_of(ctx).pictures()
    except TVUnavailable:
        await msg.reply_text(TV_DOWN)
        return
    prefix = ctx.application.bot_data["prefix"]
    if not pictures:
        await msg.reply_text("No pictures on the TV yet. Send me one.")
        return
    for p in pictures:
        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton("Show", callback_data=f"{prefix}show:{p.content_id}"),
            InlineKeyboardButton("Delete", callback_data=f"{prefix}delete:{p.content_id}"),
        ]])
        try:
            thumb = await tv_of(ctx).thumbnail(p.content_id)
            await msg.reply_photo(thumb, caption=p.content_id, reply_markup=buttons)
        except TVUnavailable as e:
            log.warning("no thumbnail for %s: %s", p.content_id, e)
            await msg.reply_text(p.content_id, reply_markup=buttons)


async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_chat.id not in ctx.application.bot_data["allowed"]:
        await query.answer()
        return
    action, content_id = query.data.removeprefix(ctx.application.bot_data["prefix"]).split(":", 1)
    if action == "fit":
        data = ctx.chat_data.pop("pending", None)
        await query.answer()
        await query.edit_message_reply_markup(None)
        if data is None:
            await query.message.reply_text("That photo is gone; send it again.")
            return
        await hang(query.message, ctx, data, crop=content_id == "crop")
        return
    if action == "tv":
        tv_of(ctx).choose(content_id)
        await query.answer(f"Pictures now go to {content_id}. Accept \"Allow\" on the TV if it asks.")
        await query.edit_message_reply_markup(None)
        try:
            await tv_of(ctx).pair()
        except TVUnavailable as e:
            log.warning("pairing with %s failed: %s", content_id, e)
        return
    try:
        if action == "show":
            await tv_of(ctx).show(content_id)
            await query.answer("On the TV.")
        elif action == "delete":
            await tv_of(ctx).delete(content_id)
            await query.answer("Deleted.")
            await query.message.delete()
    except TVUnavailable:
        await query.answer(TV_DOWN, show_alert=True)


async def tv_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    status = await msg.reply_text("Looking for TVs...")
    found = await discover.scan(ctx.application.bot_data["subnet"])
    if not found:
        await status.edit_text("No Samsung TV answered on the network. Is it on?")
        return
    current = tv_of(ctx).host
    p = ctx.application.bot_data["prefix"]
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(("✓ " if tv.host == current else "") + f"{tv.name} {tv.model} ({tv.host})",
                              callback_data=f"{p}tv:{tv.host}")]
        for tv in found
    ])
    await status.edit_text("Which TV gets the pictures?", reply_markup=buttons)


async def rotate_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    arg = ctx.args[0] if ctx.args else ""
    if arg == "off":
        minutes = 0
    elif arg.isdigit() and int(arg) > 0:
        minutes = int(arg)
    else:
        p = ctx.application.bot_data["prefix"]
        await msg.reply_text(f"Usage: /{p}rotate <minutes> or /{p}rotate off")
        return
    try:
        await tv_of(ctx).rotate(minutes)
    except TVUnavailable:
        await msg.reply_text(TV_DOWN)
        return
    await msg.reply_text(f"Rotating every {minutes} min." if minutes else "Rotation off.")


async def exit_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await tv_of(ctx).leave_art_mode()
    except TVUnavailable:
        await update.effective_message.reply_text(TV_DOWN)
        return
    await update.effective_message.reply_text("Back to the TV home.")


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Handler failed", exc_info=ctx.error)
