import asyncio
import time
import logging
from typing import Set

logger = logging.getLogger("sync_notifier")

class SyncNotifier:
    def __init__(self):
        self.version: int = int(time.time())
        self._subscribers: Set[asyncio.Queue] = set()

    def notify(self):
        """Increment version and notify all active SSE listeners immediately."""
        self.version += 1
        current_version = self.version
        dead = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(current_version)
            except Exception:
                dead.append(q)
        for d in dead:
            self._subscribers.discard(d)
        logger.debug(f"SyncNotifier triggered version={current_version}, subscribers={len(self._subscribers)}")

    async def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.discard(q)

sync_notifier = SyncNotifier()
