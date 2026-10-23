import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    telegram_token: str
    allowed_chats: frozenset[int]
    tv_host: str
    tv_token_file: Path
    tv_timeout: float
    port: int


def load() -> Config:
    data_dir = Path(os.environ.get("PIXASSO_DATA_DIR", "/data"))
    chats = os.environ.get("PIXASSO_ALLOWED_CHATS", "")
    return Config(
        telegram_token=os.environ["PIXASSO_TELEGRAM_TOKEN"],
        allowed_chats=frozenset(int(c) for c in chats.split(",") if c.strip()),
        tv_host=os.environ["PIXASSO_TV_HOST"],
        tv_token_file=data_dir / "tv-token.txt",
        tv_timeout=float(os.environ.get("PIXASSO_TV_TIMEOUT", "30")),
        port=int(os.environ.get("PIXASSO_PORT", "8080")),
    )
