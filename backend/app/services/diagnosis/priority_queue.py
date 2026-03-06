import asyncio
import heapq
from typing import Any, Optional
from dataclasses import dataclass, field

@dataclass(order=True)
class PriorityTask:
    priority: int
    task_id: str = field(compare=False)
    data: Any = field(compare=False)
    _cancelled: bool = field(default=False, compare=False)

class CancellablePriorityQueue:
    """
    基于 heapq 的可取消优先级队列
    - 支持按优先级排序（数字越小优先级越高）
    - 支持任务取消（标记法，不立即移除）
    - 支持队列满时的替换策略
    """
    def __init__(self, maxsize: int = 50):
        self._queue: list[PriorityTask] = []
        self._maxsize = maxsize
        self._event = asyncio.Event()
        self._lock = asyncio.Lock()

    async def put(self, priority: int, task_id: str, data: Any) -> bool:
        """
        插入任务，返回是否成功
        队列满时：
        - 新任务优先级 >= 队列最低优先级：丢弃新任务，返回 False
        - 新任务优先级 < 队列最低优先级：取消队列中最低优先级任务，插入新任务
        """
        async with self._lock:
            # 移除已取消的任务
            self._queue = [t for t in self._queue if not t._cancelled]
            heapq.heapify(self._queue)

            if len(self._queue) >= self._maxsize:
                # 队列已满，检查是否需要替换
                # 此时 self._queue 中都是未取消的任务
                lowest_priority_task = max(self._queue, key=lambda t: t.priority)
                if priority >= lowest_priority_task.priority:
                    # 新任务优先级更低，丢弃
                    return False
                else:
                    # 取消最低优先级任务
                    lowest_priority_task._cancelled = True

            # 插入新任务
            task = PriorityTask(priority=priority, task_id=task_id, data=data)
            heapq.heappush(self._queue, task)
            self._event.set()
            return True

    async def get(self) -> Optional[PriorityTask]:
        """
        获取最高优先级任务（跳过已取消的任务）
        """
        while True:
            async with self._lock:
                # 移除已取消的任务
                while self._queue and self._queue[0]._cancelled:
                    heapq.heappop(self._queue)

                if self._queue:
                    task = heapq.heappop(self._queue)
                    if not task._cancelled:
                        return task
                else:
                    self._event.clear()

            # 等待新任务
            await self._event.wait()

    async def cancel(self, task_id: str) -> bool:
        """
        取消指定任务（标记法）
        """
        async with self._lock:
            for task in self._queue:
                if task.task_id == task_id and not task._cancelled:
                    task._cancelled = True
                    return True
            return False

    def qsize(self) -> int:
        """
        返回队列大小（不包括已取消的任务）
        """
        return sum(1 for t in self._queue if not t._cancelled)
