import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from samsungtvws import SamsungTVWS

MY_PHOTOS = "MY-C0002"
CLIENT_NAME = "pixasso"


@dataclass(frozen=True)
class Picture:
    content_id: str
    width: int
    height: int


class TVUnavailable(Exception):
    pass


class ArtTV:
    """Samsung art mode over the local websocket. Each call opens its own connection: the TV drops idle ones."""

    def __init__(self, data_dir: Path, default_host: str, timeout: float):
        self.data_dir = data_dir
        self.timeout = timeout
        self.state_file = data_dir / "state.json"
        self.host = self._load_host() or default_host

    def _load_host(self) -> str:
        try:
            return json.loads(self.state_file.read_text()).get("tv_host", "")
        except (OSError, ValueError):
            return ""

    def choose(self, host: str) -> None:
        self.host = host
        self.state_file.write_text(json.dumps({"tv_host": host}))

    def _tv(self) -> SamsungTVWS:
        # One token per TV: switching TVs must not ask "Allow" again on the one used before.
        return SamsungTVWS(host=self.host, port=8002, name=CLIENT_NAME,
                           token_file=str(self.data_dir / f"tv-token-{self.host}.txt"), timeout=self.timeout)

    async def _run(self, fn):
        # Outside art mode the TV accepts the connection and never answers, so every call needs a deadline.
        if not self.host:
            raise TVUnavailable("no TV chosen yet")
        try:
            return await asyncio.wait_for(asyncio.to_thread(fn), self.timeout + 5)
        except TVUnavailable:
            raise
        except Exception as e:
            # samsungtvws and websocket-client raise their own types for a TV that is off, asleep or not allowed yet.
            raise TVUnavailable(f"{type(e).__name__}: {e}") from e

    async def pair(self) -> None:
        # The art channel refuses a client that never paired on the remote channel.
        await self._run(lambda: self._tv().open())

    async def pictures(self) -> list[Picture]:
        items = await self._run(lambda: self._tv().art().available(MY_PHOTOS))
        return [Picture(i["content_id"], int(i.get("width", 0)), int(i.get("height", 0))) for i in items]

    async def upload(self, jpeg: bytes) -> str:
        return await self._run(lambda: self._tv().art().upload(jpeg, file_type="JPEG", matte="none"))

    async def show(self, content_id: str) -> None:
        await self._run(lambda: self._tv().art().select_image(content_id, show=True))

    async def delete(self, content_id: str) -> bool:
        return await self._run(lambda: self._tv().art().delete(content_id))

    async def thumbnail(self, content_id: str) -> bytes:
        return bytes(await self._run(lambda: self._tv().art().get_thumbnail(content_id)))

    async def rotate(self, minutes: int) -> None:
        # The TV rotates by itself, so it keeps going while the bot is down; 0 turns it off.
        await self._run(lambda: self._tv().art().set_slideshow_status(duration=minutes, type=True, category_id=MY_PHOTOS))

    async def leave_art_mode(self) -> None:
        def leave():
            tv = self._tv()
            tv.art().set_artmode(False)
            tv.send_key("KEY_HOME")
        await self._run(leave)
