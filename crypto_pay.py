from __future__ import annotations

from decimal import Decimal
from typing import Any

import aiohttp


class CryptoPayError(RuntimeError):
    pass


class CryptoPayClient:
    def __init__(self, token: str | None, api_url: str):
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

    async def request(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.token:
            raise CryptoPayError("CRYPTO_PAY_TOKEN is not configured")
        await self.start()
        assert self.session is not None
        headers = {"Crypto-Pay-API-Token": self.token}
        async with self.session.post(f"{self.api_url}/{method}", json=payload or {}, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if not data.get("ok"):
                raise CryptoPayError(f"CryptoPay API error {method}: {data}")
            return data["result"]

    async def create_invoice(self, amount_usd: Decimal | float | str, description: str, payload: str) -> dict[str, Any]:
        return await self.request(
            "createInvoice",
            {
                "currency_type": "fiat",
                "fiat": "USD",
                "amount": str(amount_usd),
                "accepted_assets": "USDT,TON,BTC,ETH,LTC,BNB,TRX,USDC",
                "description": description[:1024],
                "payload": payload,
                "expires_in": 3600,
            },
        )

    async def get_invoice(self, invoice_id: str) -> dict[str, Any] | None:
        result = await self.request("getInvoices", {"invoice_ids": str(invoice_id)})
        items = result.get("items") or []
        return items[0] if items else None
