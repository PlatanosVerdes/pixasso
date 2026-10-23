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
| `/list` | Thumbnails of the library |
| `/show` | Show the chosen picture |
| `/delete` | Delete the chosen picture |
| `/rotate <interval>` | Cycle through the library; `/rotate off` stops it |
| `/exit` | Leave art mode and go back to the TV home |

## Fitting pictures

- Landscape: centre crop to 16:9, scale to 3840×2160, no matte.
- Portrait: the whole picture centred over a blurred, enlarged copy of itself.
- `/crop` per photo to force a crop instead of the blurred fill.

## Running it

- A small container on a home server on the same network as the TV.
- Telegram: its own bot, so pixasso is the only poller. Answers allowed chats only.
- Secrets (bot token, TV token) come from the environment, never from the repo.

## Status

Planned. Upload, select, delete and remote keys were proven against the art API by hand.
