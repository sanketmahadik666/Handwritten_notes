import asyncio
import json
from typing import AsyncGenerator, Dict, Set

class JobEventBroadcaster:
    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        async with self._lock:
            q = asyncio.Queue(maxsize=100)
            if job_id not in self._subscribers:
                self._subscribers[job_id] = set()
            self._subscribers[job_id].add(q)
            return q

    async def unsubscribe(self, job_id: str, q: asyncio.Queue):
        async with self._lock:
            if job_id in self._subscribers:
                self._subscribers[job_id].discard(q)
                if not self._subscribers[job_id]:
                    del self._subscribers[job_id]

    async def publish(self, job_id: str, event_type: str, data: dict):
        async with self._lock:
            queues = list(self._subscribers.get(job_id, []))
        payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def sse_generator(self, job_id: str) -> AsyncGenerator[str, None]:
        queue = await self.subscribe(job_id)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            await self.unsubscribe(job_id, queue)

broadcaster = JobEventBroadcaster()
