import asyncio
import logging
from typing import Optional, Set
import httpx
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Setting
from command_processor import process_user_input

logger = logging.getLogger(__name__)

class TelegramBotRunner:
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_update_id = 0

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())
            logger.info("Telegram bot polling started.")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("Telegram bot polling stopped.")

    async def _poll_loop(self):
        """Long-polling loop for Telegram updates."""
        while self._running:
            token, allowed_chat_ids = self._get_bot_credentials()

            if not token:
                # No token configured yet, check again after delay
                await asyncio.sleep(5)
                continue

            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    url = f"https://api.telegram.org/bot{token}/getUpdates"
                    params = {
                        "offset": self._last_update_id + 1,
                        "timeout": 30
                    }
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("ok"):
                            updates = data.get("result", [])
                            for up in updates:
                                self._last_update_id = up.get("update_id", self._last_update_id)
                                await self._handle_update(up, token, allowed_chat_ids)
                    elif resp.status_code == 401:
                        logger.warning("Telegram Bot Token is invalid (401). Pausing for 30s...")
                        await asyncio.sleep(30)
                    else:
                        logger.warning(f"Telegram getUpdates returned {resp.status_code}")
                        await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
                await asyncio.sleep(5)

    def _get_bot_credentials(self) -> tuple[str, Set[str]]:
        """Reads current bot token and allowed chat IDs from DB."""
        db: Session = SessionLocal()
        try:
            token_row = db.query(Setting).filter(Setting.key == "telegram_bot_token").first()
            id1_row = db.query(Setting).filter(Setting.key == "telegram_chat_id_1").first()
            id2_row = db.query(Setting).filter(Setting.key == "telegram_chat_id_2").first()

            token = token_row.value.strip() if token_row and token_row.value else ""
            allowed = set()
            if id1_row and id1_row.value.strip():
                allowed.add(id1_row.value.strip())
            if id2_row and id2_row.value.strip():
                allowed.add(id2_row.value.strip())

            return token, allowed
        finally:
            db.close()

    async def _handle_update(self, update: dict, token: str, allowed_chat_ids: Set[str]):
        message = update.get("message")
        if not message:
            return

        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = message.get("text", "").strip()

        if not text:
            return

        # Check authorization
        # If no chat IDs are configured yet, inform the user what their chat ID is so they can add it!
        if not allowed_chat_ids:
            reply_msg = f"ברוך הבא! ה-Chat ID שלך הוא:\n`{chat_id}`\n\nהזן אותו בהגדרות האפליקציה כדי לאשר גישה."
            await self._send_reply(token, chat_id, reply_msg)
            return

        if chat_id not in allowed_chat_ids:
            reply_msg = f"גישה לא מורשית. ה-Chat ID שלך הוא: {chat_id}"
            await self._send_reply(token, chat_id, reply_msg)
            return

        # Handle /start
        if text.startswith("/start"):
            reply_msg = "הבוט עובד! שלח פריטים לרשימה 🛒"
            await self._send_reply(token, chat_id, reply_msg)
            return

        # Handle items / commands
        db: Session = SessionLocal()
        try:
            res = await process_user_input(text, db)
            from sync_notifier import sync_notifier
            sync_notifier.notify()
            reply_msg = res.get("message", "עודכן!")
            await self._send_reply(token, chat_id, reply_msg)
        except Exception as e:
            logger.error(f"Error handling Telegram message: {e}")
            await self._send_reply(token, chat_id, f"שגיאה בעיבוד הבקשה: {str(e)}")
        finally:
            db.close()

    async def _send_reply(self, token: str, chat_id: str, text: str):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown"
                }
                await client.post(url, json=payload)
        except Exception as e:
            logger.error(f"Failed to send Telegram reply to {chat_id}: {e}")

bot_runner = TelegramBotRunner()
