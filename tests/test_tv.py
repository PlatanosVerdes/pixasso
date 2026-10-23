import asyncio
from pathlib import Path

import pytest
from websocket import WebSocketTimeoutException

from pixasso.tv import ArtTV, TVUnavailable


def test_library_errors_become_tv_unavailable(tmp_path: Path):
    tv = ArtTV(tmp_path, "192.0.2.1", timeout=1)

    def boom():
        raise WebSocketTimeoutException("Connection timed out")

    with pytest.raises(TVUnavailable):
        asyncio.run(tv._run(boom))


def test_no_tv_chosen(tmp_path: Path):
    with pytest.raises(TVUnavailable):
        asyncio.run(ArtTV(tmp_path, "", timeout=1)._run(lambda: None))
