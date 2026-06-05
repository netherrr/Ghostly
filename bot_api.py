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

    async def request_multipart(self, method: str, form: aiohttp.FormData) -> dict[str, Any]:
        await self.start()
        assert self.session is not None
        async with self.session.post(f"{self.base_url}/{method}", data=form) as resp:
            data = await resp.json(content_type=None)
            if not data.get("ok"):
                raise TelegramAPIError(f"Telegram API error {method}: {data}")
            return data["result"]

    async def send_document_bytes(
        self,
        chat_id: int | str,
        filename: str,
        data: bytes,
        caption: str | None = None,
    ) -> dict[str, Any]:
        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        form.add_field("document", data, filename=filename, content_type="application/zip")
        if caption:
            form.add_field("caption", caption[:1024])
            form.add_field("parse_mode", "HTML")
        return await self.request_multipart("sendDocument", form)

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
                    "pre_checkout_query",
                    "business_connection",
                    "business_message",
                    "edited_business_message",
                    "deleted_business_messages",
                ],
            },
        )

    async def delete_webhook(self) -> dict[str, Any]:
        return await self.request("deleteWebhook", {"drop_pending_updates": False})

    async def send_stars_invoice(
        self,
        chat_id: int | str,
        title: str,
        description: str,
        payload: str,
        amount_stars: int,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a Telegram Stars invoice.

        For Telegram Stars, currency must be XTR and provider_token must be omitted.
        Amount is an integer number of Stars.
        """
        payload_data: dict[str, Any] = {
            "chat_id": chat_id,
            "title": title[:32],
            "description": description[:255],
            "payload": payload,
            "currency": "XTR",
            "prices": [{"label": title[:32], "amount": int(amount_stars)}],
        }
        if reply_markup:
            payload_data["reply_markup"] = reply_markup
        return await self.request("sendInvoice", payload_data)

    async def answer_pre_checkout_query(self, pre_checkout_query_id: str, ok: bool = True, error_message: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "pre_checkout_query_id": pre_checkout_query_id,
            "ok": bool(ok),
        }
        if error_message:
            payload["error_message"] = error_message[:200]
        return await self.request("answerPreCheckoutQuery", payload)

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        disable_web_page_preview: bool = True,
        entities: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if entities is not None:
            payload["entities"] = entities
        else:
            payload["parse_mode"] = "HTML"
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.request("sendMessage", payload)

    async def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        entities: list[dict[str, Any]] | None = None,
        disable_web_page_preview: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if entities is not None:
            payload["entities"] = entities
        else:
            payload["parse_mode"] = "HTML"
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.request("editMessageText", payload)

    async def edit_message_caption(
        self,
        chat_id: int | str,
        message_id: int,
        caption: str,
        reply_markup: dict[str, Any] | None = None,
        caption_entities: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": caption[:1024],
        }
        if caption_entities is not None:
            payload["caption_entities"] = caption_entities
        else:
            payload["parse_mode"] = "HTML"
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.request("editMessageCaption", payload)

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None, show_alert: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            payload["text"] = text[:200]
        return await self.request("answerCallbackQuery", payload)


    async def copy_message(
        self,
        chat_id: int | str,
        from_chat_id: int | str,
        message_id: int,
        caption: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
        }
        if caption is not None:
            payload["caption"] = caption[:1024]
            payload["parse_mode"] = "HTML"
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.request("copyMessage", payload)

    async def delete_message(self, chat_id: int | str, message_id: int) -> dict[str, Any]:
        return await self.request("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

    async def send_cached_media(
        self,
        chat_id: int | str,
        kind: str,
        file_id: str,
        caption: str | None = None,
        reply_markup: dict[str, Any] | None = None,
        caption_entities: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
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
        payload: dict[str, Any] = {"chat_id": chat_id, field: file_id}
        if caption and kind not in {"video_note", "sticker"}:
            payload["caption"] = caption[:1024]
            if caption_entities is not None:
                payload["caption_entities"] = caption_entities
            else:
                payload["parse_mode"] = "HTML"
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.request(method, payload)
