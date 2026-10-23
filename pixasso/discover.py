import asyncio
import ipaddress
from dataclasses import dataclass

import aiohttp


@dataclass(frozen=True)
class FoundTV:
    host: str
    name: str
    model: str


async def scan(subnet: str, timeout: float = 1.5) -> list[FoundTV]:
    """Samsung TVs answer GET :8001/api/v2/ on the LAN; unicast works from a bridged container, SSDP does not."""
    hosts = [str(ip) for ip in ipaddress.ip_network(subnet, strict=False).hosts()]
    limit = asyncio.Semaphore(64)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        async def probe(host: str) -> FoundTV | None:
            async with limit:
                try:
                    async with session.get(f"http://{host}:8001/api/v2/") as resp:
                        device = (await resp.json(content_type=None)).get("device", {})
                except (aiohttp.ClientError, TimeoutError, ValueError):
                    return None
            if device.get("type") != "Samsung SmartTV":
                return None
            return FoundTV(host, device.get("name", host), device.get("modelName", ""))

        found = await asyncio.gather(*(probe(h) for h in hosts))
    return [tv for tv in found if tv]
