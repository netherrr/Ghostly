from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from bot_api import BotAPI
from config import load_settings
from crypto_pay import CryptoPayClient
from db import Database
from handlers import BotHandlers

settings = load_settings()
db = Database(settings)
bot = BotAPI(settings.bot_token)
crypto = CryptoPayClient(settings.crypto_pay_token, settings.crypto_pay_api_url)
handlers = BotHandlers(settings, db, bot, crypto)
cleanup_task: asyncio.Task | None = None
broadcast_task: asyncio.Task | None = None


async def periodic_cleanup() -> None:
    while True:
        try:
            await asyncio.sleep(60 * 60 * 6)
            deleted = await db.cleanup_old_messages()
            print(f"Cleanup old messages: {deleted}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print("Periodic cleanup error:", repr(exc))


async def broadcast_scheduler() -> None:
    # Tick every 30s and post to any chat whose interval has elapsed. Timing and
    # last-message ids live in the DB, so the schedule survives restarts.
    while True:
        try:
            await asyncio.sleep(30)
            sent = await handlers.run_due_broadcasts()
            if sent:
                print(f"Broadcast tick: posted to {sent} chat(s)")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print("Broadcast scheduler error:", repr(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cleanup_task, broadcast_task
    await db.connect()
    await bot.start()
    await crypto.start()
    if settings.webhook_url:
        await bot.set_webhook(settings.webhook_url, settings.webhook_secret)
        print(f"Telegram webhook configured: {settings.webhook_url}")
    else:
        print("WEBHOOK_BASE_URL is not set. Set it on Railway for Telegram webhooks.")
    cleanup_task = asyncio.create_task(periodic_cleanup())
    broadcast_task = asyncio.create_task(broadcast_scheduler())
    try:
        yield
    finally:
        if cleanup_task:
            cleanup_task.cancel()
        if broadcast_task:
            broadcast_task.cancel()
        await bot.close()
        await crypto.close()
        await db.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": settings.app_name}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return f"""
<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{settings.app_name}</title>
<style>
  body {{ margin:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#0b1020; color:#eef2ff; }}
  .wrap {{ max-width: 820px; margin: 0 auto; padding: 48px 20px; }}
  .card {{ background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.14); border-radius:24px; padding:28px; box-shadow:0 20px 80px rgba(0,0,0,.35); }}
  h1 {{ font-size:42px; margin:0 0 12px; }}
  p {{ line-height:1.65; color:#cbd5e1; }}
  .badge {{ display:inline-block; padding:8px 12px; background:#172554; border:1px solid #38bdf8; border-radius:999px; margin-bottom:20px; color:#bae6fd; }}
  .grid {{ display:grid; gap:14px; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); margin-top:24px; }}
  .item {{ background:rgba(255,255,255,.06); padding:16px; border-radius:18px; }}
  code {{ color:#93c5fd; }}
</style>
</head>
<body>
  <main class="wrap">
    <div class="card">
      <div class="badge">🕵️ Telegram Business Spy Bot</div>
      <h1>{settings.app_name}</h1>
      <p>Бот працює через офіційне Telegram Business-підключення: не просить коди входу, паролі або session string. Зберігає видалені/відредаговані повідомлення та зникаючі медіа (кружки, голосові, фото, відео).</p>
      <div class="grid">
        <div class="item"><b>👁 Deleted messages</b><br/>Зберігає та показує видалені повідомлення в особистих та групових чатах.</div>
        <div class="item"><b>🔥 Disappearing media</b><br/>Зберігає зникаючі кружки, голосові, фото та відео одразу при отриманні.</div>
        <div class="item"><b>🔎 Keyword monitoring</b><br/>Моніторинг чатів за вибраними словами та фразами.</div>
        <div class="item"><b>👑 Admin panel</b><br/>Тарифи, ціни, заявки й методи оплати керуються кнопками без коду.</div>
      </div>
      <p>Health endpoint: <code>/health</code></p>
    </div>
  </main>
</body>
</html>
    """


@app.post(settings.webhook_path)
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)) -> JSONResponse:
    if x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram secret token")
    update = await request.json()
    await handlers.handle_update(update)
    return JSONResponse({"ok": True})


@app.post("/cryptopay/webhook")
async def cryptopay_webhook(request: Request) -> JSONResponse:
    # Optional endpoint. CryptoBot invoices are already checked by button.
    # You can configure this in CryptoBot later and harden verification if needed.
    payload = await request.json()
    update_type = payload.get("update_type")
    invoice = (payload.get("payload") or {}) if isinstance(payload.get("payload"), dict) else {}
    if update_type == "invoice_paid" and invoice.get("invoice_id"):
        async with db._pool().acquire() as con:
            payment_id = await con.fetchval(
                "SELECT id FROM payments WHERE provider='cryptobot' AND external_id=$1 AND status <> 'paid'",
                str(invoice.get("invoice_id")),
            )
        if payment_id:
            paid = await db.mark_payment_paid(int(payment_id), raw=invoice)
            if paid and paid.get("user_id"):
                lang = await handlers.user_lang(int(paid["user_id"]))
                from i18n import tr
                from keyboards import main_menu
                from handlers import dt
                await bot.send_message(int(paid["user_id"]), tr(lang, "crypto_paid", date=dt(paid.get("paid_until"))), main_menu(lang, False))
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=False)
