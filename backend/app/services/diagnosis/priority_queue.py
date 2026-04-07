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
        self._cancelled_count = 0  # 跟踪已取消任务数量

    async def put(self, priority: int, task_id: str, data: Any) -> bool:
        """
        插入任务，返回是否成功
        队列满时：
        - 新任务优先级 >= 队列最低优先级：丢弃新任务，返回 False
        - 新任务优先级 < 队列最低优先级：取消队列中最低优先级任务，插入新任务
        """
        async with self._lock:
            # 只在已取消任务过多时才清理（避免每次都重建）
            if self._cancelled_count > self._maxsize:
                self._compact()

            active_size = len(self._queue) - self._cancelled_count

            if active_size >= self._maxsize:
                # 队列已满，检查是否需要替换
                # 找到未取消的最低优先级任务
                lowest_priority_task = None
                lowest_priority = -1
                for task in self._queue:
                    if not task._cancelled and task.priority > lowest_priority:
                        lowest_priority = task.priority
                        lowest_priority_task = task

                if lowest_priority_task is None:
                    # 所有任务都已取消，清理后重试
                    self._compact()
                elif priority >= lowest_priority:
                    # 新任务优先级更低，丢弃
                    return False
                else:
                    # 取消最低优先级任务
                    lowest_priority_task._cancelled = True
                    self._cancelled_count += 1

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
                    self._cancelled_count -= 1

                if self._queue:
                    task = heapq.heappop(self._queue)
                    if not task._cancelled:
                        return task
                    else:
                        # 已取消，继续循环
                        self._cancelled_count -= 1
                        continue
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
                    self._cancelled_count += 1
                    return True
            return False

    async def qsize(self) -> int:
        """
        返回队列大小（不包括已取消的任务）
        注意：此方法现在是异步的，需要加锁保护
        """
        async with self._lock:
            return len(self._queue) - self._cancelled_count

    def _compact(self):
        """
        清理已取消的任务（内部方法，调用者需持有锁）
        """
        self._queue = [t for t in self._queue if not t._cancelled]
        heapq.heapify(self._queue)
        self._cancelled_count = 0
