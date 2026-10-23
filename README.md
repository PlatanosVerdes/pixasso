# pixasso

A Telegram bot that hangs pictures on a TV. Send it a photo and it turns into a painting on a
Samsung TV's art mode; the bot also manages the whole art library.

## Target

- A Samsung TV with art mode, reachable on the local network. Its address comes from config.
- Art mode API over the local websocket on port 8002 (`samsungtvws`). The TV asks "Allow" once and
  hands out a token; the token is the only credential.
- The art mode terms must stay accepted on the TV, or the art API stops answering.

## Commands

| Command | What it does |
|---|---|
| photo (sent as a file) | Fit to 3840×2160, upload to My Photos and show it |
| `/list` | Thumbnails of the library, each with Show and Delete buttons |
| `/rotate <minutes>` | The TV's own slideshow over My Photos; `/rotate off` stops it |
| `/exit` | Leave art mode and go back to the TV home |

## Fitting pictures

- Landscape: centre crop to 16:9, scale to 3840×2160, no matte.
- Portrait: the whole picture centred over a blurred, enlarged copy of itself.
- `/crop` before a photo forces a crop instead of the blurred fill.

## Running it

- A small container on a home server on the same network as the TV.
- Telegram: its own bot by default, read by pixasso itself. It can also sit on a bot shared with
  other services behind [switchboard](https://github.com/PlatanosVerdes/switchboard):
  `PIXASSO_UPDATES=push` and a prefix such as `tv_`, so switchboard posts its updates to
  `POST /telegram/update` and reads its menu from `GET /telegram/commands`. Answers allowed chats only.
- Secrets (bot token, TV token) come from the environment, never from the repo.

## Config

| Variable | |
|---|---|
| `PIXASSO_TELEGRAM_TOKEN` | Bot token |
| `PIXASSO_ALLOWED_CHATS` | Comma-separated chat ids the bot answers |
| `PIXASSO_TV_HOST` | TV address |
| `PIXASSO_TV_TIMEOUT` | Seconds per TV call, default 30 |
| `PIXASSO_UPDATES` | `poll` (own bot, default) or `push` (behind switchboard) |
| `PIXASSO_PREFIX` | Command and button prefix on a shared bot, empty by default |
| `PIXASSO_PORT` | Where switchboard posts the updates in push mode, default 8080 |
| `PIXASSO_DATA_DIR` | Where the TV pairing token is kept, default `/data` |

The first start pairs with the TV: accept "Allow" on screen once.

## Status

Written, not deployed. Upload, select, delete and remote keys were proven against the art API by
hand; thumbnails and the TV slideshow are not yet tried on the real TV.
