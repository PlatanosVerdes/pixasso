import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from . import fit
from .config import Config
from .tv import ArtTV, TVUnavailable

log = logging.getLogger(__name__)

# The services bot is shared, so every command and button carries this prefix.
PREFIX = "tv_"
COMMANDS = [
    ("help", "TV art: how it works"),
    ("list", "TV art: pictures on the TV"),
    ("crop", "TV art: crop the next photo"),
    ("rotate", "TV art: /tv_rotate <minutes> or off"),
    ("exit", "TV art: leave art mode"),
]
HELP = (
    "Send me a photo (better as a file, it keeps the quality) and I hang it on the TV.\n\n"
    "/tv_list - the pictures on the TV, to show or delete\n"
    "/tv_crop - crop the next photo instead of the blurred fill\n"
    "/tv_rotate <minutes> - cycle through them, /tv_rotate off stops it\n"
    "/tv_exit - leave art mode and go back to the TV home"
)
TV_DOWN = "The TV is not answering. Is it on, or in art mode?"


def build(cfg: Config) -> Application:
    tv = ArtTV(cfg.tv_host, cfg.tv_token_file, cfg.tv_timeout)
    allowed = filters.Chat(chat_id=list(cfg.allowed_chats))

    async def on_start(app: Application) -> None:
        try:
            await tv.pair()
        except TVUnavailable as e:
            log.warning("TV pairing skipped: %s", e)

    # No updater: switchboard reads the bot and posts each update here.
    app = Application.builder().token(cfg.telegram_token).updater(None).post_init(on_start).build()
    app.bot_data["tv"] = tv
    app.bot_data["allowed"] = cfg.allowed_chats

    app.add_handler(CommandHandler(PREFIX + "help", help_cmd, filters=allowed))
    app.add_handler(CommandHandler(PREFIX + "list", list_cmd, filters=allowed))
    app.add_handler(CommandHandler(PREFIX + "crop", crop_cmd, filters=allowed))
    app.add_handler(CommandHandler(PREFIX + "rotate", rotate_cmd, filters=allowed))
    app.add_handler(CommandHandler(PREFIX + "exit", exit_cmd, filters=allowed))
    app.add_handler(MessageHandler(allowed & (filters.PHOTO | filters.Document.IMAGE), picture))
    app.add_handler(CallbackQueryHandler(button, pattern=f"^{PREFIX}"))
    app.add_error_handler(on_error)
    return app


def tv_of(ctx: ContextTypes.DEFAULT_TYPE) -> ArtTV:
    return ctx.application.bot_data["tv"]


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP)


async def crop_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.chat_data["crop_next"] = True
    await update.effective_message.reply_text("The next photo will be cropped to fill the screen.")


async def picture(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    media = msg.document or msg.photo[-1]
    data = bytes(await (await media.get_file()).download_as_bytearray())
    force_crop = ctx.chat_data.pop("crop_next", False)
    jpeg = await asyncio.to_thread(fit.fit, data, force_crop)
    status = await msg.reply_text("Hanging it...")
    try:
        content_id = await tv_of(ctx).upload(jpeg)
        await tv_of(ctx).show(content_id)
    except TVUnavailable:
        await status.edit_text(TV_DOWN)
        return
    await status.edit_text("On the TV.")


async def list_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    try:
        pictures = await tv_of(ctx).pictures()
    except TVUnavailable:
        await msg.reply_text(TV_DOWN)
        return
    if not pictures:
        await msg.reply_text("No pictures on the TV yet. Send me one.")
        return
    for p in pictures:
        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton("Show", callback_data=f"{PREFIX}show:{p.content_id}"),
            InlineKeyboardButton("Delete", callback_data=f"{PREFIX}delete:{p.content_id}"),
        ]])
        try:
            thumb = await tv_of(ctx).thumbnail(p.content_id)
            await msg.reply_photo(thumb, caption=p.content_id, reply_markup=buttons)
        except TVUnavailable:
            await msg.reply_text(p.content_id, reply_markup=buttons)


async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_chat.id not in ctx.application.bot_data["allowed"]:
        await query.answer()
        return
    action, content_id = query.data.removeprefix(PREFIX).split(":", 1)
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


async def rotate_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    arg = ctx.args[0] if ctx.args else ""
    if arg == "off":
        minutes = 0
    elif arg.isdigit() and int(arg) > 0:
        minutes = int(arg)
    else:
        await msg.reply_text("Usage: /tv_rotate <minutes> or /tv_rotate off")
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
