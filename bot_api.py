from __future__ import annotations

from typing import Any

import aiohttp


class TelegramAPIError(RuntimeError):
    pass


class BotAPI:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

    async def request(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        await self.start()
        assert self.session is not None
        async with self.session.post(f"{self.base_url}/{method}", json=payload or {}) as resp:
            data = await resp.json(content_type=None)
            if not data.get("ok"):
                raise TelegramAPIError(f"Telegram API error {method}: {data}")
            return data["result"]

    async def set_webhook(self, url: str, secret_token: str) -> dict[str, Any]:
        return await self.request(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret_token,
                "drop_pending_updates": False,
                "allowed_updates": [
                    "message",
                    "callback_query",
                    "business_connection",
                    "business_message",
                    "edited_business_message",
                    "deleted_business_messages",
                ],
            },
        )

    async def delete_webhook(self) -> dict[str, Any]:
        return await self.request("deleteWebhook", {"drop_pending_updates": False})

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        disable_web_page_preview: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.request("sendMessage", payload)

    async def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.request("editMessageText", payload)

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None, show_alert: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            payload["text"] = text[:200]
        return await self.request("answerCallbackQuery", payload)

    async def send_cached_media(self, chat_id: int, kind: str, file_id: str, caption: str | None = None) -> dict[str, Any]:
        method_map = {
            "photo": "sendPhoto",
            "video": "sendVideo",
            "animation": "sendAnimation",
            "document": "sendDocument",
            "audio": "sendAudio",
            "voice": "sendVoice",
            "video_note": "sendVideoNote",
            "sticker": "sendSticker",
        }
        method = method_map.get(kind)
        if not method:
            raise TelegramAPIError(f"Unsupported cached media kind: {kind}")
        field = "photo" if kind == "photo" else kind
        payload: dict[str, Any] = {"chat_id": chat_id, field: file_id, "parse_mode": "HTML"}
        if caption and kind not in {"video_note", "sticker"}:
            payload["caption"] = caption[:1024]
        return await self.request(method, payload)
