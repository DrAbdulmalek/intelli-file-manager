# -*- coding: utf-8 -*-
"""
الفئة الأساسية للوكلاء (Agents)
===================================

توفر الفئة الأساسية المجردة التي يجب أن ترثها جميع وكلاء
الذكاء الاصطناعي في التطبيق. تحتوي على البنية المشتركة
لإدارة المهام والتسجيل ودورة الحياة.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# ─── إعداد التسجيل ──────────────────────────────────────────────
logger = logging.getLogger(__name__)


# ─── أنواع البيانات المساعدة ───────────────────────────────────
class TaskStatus(str, Enum):
    """حالات المهمة"""

    PENDING = "pending"        # في الانتظار
    RUNNING = "running"        # قيد التنفيذ
    COMPLETED = "completed"    # مكتملة
    FAILED = "failed"          # فاشلة
    CANCELLED = "cancelled"    # ملغاة


@dataclass
class Task:
    """
    تمثيل مهمة واحدة في قائمة الانتظار.

    المعاملات
    ---------
    task_id : str
        معرّف فريد للمهمة
    data : dict
        بيانات المهمة
    priority : int
        الأولوية (كلما كان الرقم أصغر، زادت الأولوية)
    callback : callable, اختياري
        دالة تُستدعى عند اكتمال المهمة
    """

    task_id: str
    data: Dict[str, Any]
    priority: int = 0
    callback: Optional[Callable[[Dict[str, Any]], None]] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    @property
    def duration(self) -> Optional[float]:
        """مدة تنفيذ المهمة بالثواني"""
        if self.started_at is None:
            return None
        end: float = self.completed_at or time.time()
        return end - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        """تحويل المهمة إلى قاموس"""
        return {
            "task_id": self.task_id,
            "data": self.data,
            "priority": self.priority,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
        }


@dataclass(order=True)
class PrioritizedTask:
    """مهمة ذات أولوية لقائمة الانتظار"""

    priority: int
    task: Task = field(compare=False)


# ─── الفئة الأساسية المجردة ────────────────────────────────────
class BaseAgent(ABC):
    """
    الفئة الأساسية المجردة لجميع وكلاء الذكاء الاصطناعي.

    توفر هذه الفئة البنية المشتركة التي يجب أن ترثها كل
    فئات الوكلاء، بما في ذلك:
    - إدارة قائمة انتظار المهام
    - التسجيل المُهيأ
    - إدارة دورة الحياة
    - التنفيذ المتزامن (thread-safe)

    يجب على كل وكيل فرعي تنفيذ الطريقة المجردة
    ``execute(task)`` التي تحتوي على المنطق الأساسي.
    """

    # ─── عداد المهام المشترك ──────────────────────────────────
    _task_counter: int = 0
    _counter_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        agent_name: Optional[str] = None,
        max_queue_size: int = 1000,
        auto_start: bool = False,
    ) -> None:
        """
        تهيئة الوكيل الأساسي.

        المعاملات
        ---------
        agent_name : str, اختياري
            اسم الوكيل (يُستخدم في التسجيل). إذا لم يُحدد،
            يُستخدم اسم الفئة.
        max_queue_size : int
            الحد الأقصى لحجم قائمة انتظار المهام
        auto_start : bool
            هل يبدأ التنفيذ التلقائي للمهام مباشرة
        """
        # ─── المعلومات الأساسية ───────────────────────────────
        self._agent_name: str = agent_name or self.__class__.__name__

        # ─── إعداد التسجيل المخصص ─────────────────────────────
        self._logger: logging.Logger = logging.getLogger(
            f"{__name__}.{self._agent_name}"
        )

        # ─── قائمة انتظار المهام ─────────────────────────────
        self._max_queue_size: int = max_queue_size
        self._task_queue: deque[PrioritizedTask] = deque()
        self._task_history: Dict[str, Task] = {}
        self._queue_lock: threading.Lock = threading.Lock()

        # ─── حالة التشغيل ─────────────────────────────────────
        self._is_running: bool = False
        self._is_processing: bool = False
        self._stop_event: threading.Event = threading.Event()

        # ─── إحصائيات ─────────────────────────────────────────
        self._total_tasks: int = 0
        self._successful_tasks: int = 0
        self._failed_tasks: int = 0

        # ─── قفل التشغيل ─────────────────────────────────────
        self._processing_lock: threading.Lock = threading.Lock()

        self._logger.info(
            "تم تهيئة الوكيل: %s | الحد الأقصى للطابور: %d",
            self._agent_name,
            max_queue_size,
        )

        if auto_start:
            self.start()

    # ─── الخصائص المجردة والملموسة ─────────────────────────────
    @property
    @abstractmethod
    def name(self) -> str:
        """
        اسم الوكيل.

        يجب أن يُعيد سلسلة نصية فريدة تصف الوكيل.
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """
        وصف مختصر لعمل الوكيل.

        يجب أن يوضح ما يفعله الوكيل بشكل موجز.
        """
        ...

    @property
    def is_running(self) -> bool:
        """هل الوكيل يعمل؟"""
        return self._is_running

    @property
    def queue_size(self) -> int:
        """عدد المهام في قائمة الانتظار"""
        with self._queue_lock:
            return len(self._task_queue)

    @property
    def stats(self) -> Dict[str, Any]:
        """إحصائيات الوكيل"""
        return {
            "agent_name": self._agent_name,
            "is_running": self._is_running,
            "total_tasks": self._total_tasks,
            "successful_tasks": self._successful_tasks,
            "failed_tasks": self._failed_tasks,
            "queue_size": self.queue_size,
            "success_rate": (
                (self._successful_tasks / self._total_tasks * 100)
                if self._total_tasks > 0
                else 0.0
            ),
        }

    # ─── الطريقة المجردة الأساسية ──────────────────────────────
    @abstractmethod
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        تنفيذ مهمة واحدة.

        هذه هي الطريقة الأساسية التي يجب أن تنفذها كل فئة
        فرعية. تحتوي على المنطق الخاص بالوكيل لمعالجة المهمة.

        المعاملات
        ---------
        task : dict
            بيانات المهمة المراد تنفيذها

        العائد
        -------
        dict
            نتيجة التنفيذ

        الاستثناءات
        -----------
        Exception
            أي خطأ يحدث أثناء التنفيذ
        """
        ...

    # ─── إدارة قائمة الانتظار ─────────────────────────────────
    @classmethod
    def _generate_task_id(cls) -> str:
        """إنشاء معرّف فريد للمهمة"""
        with cls._counter_lock:
            cls._task_counter += 1
            return f"task_{cls._task_counter:06d}_{int(time.time() * 1000)}"

    def enqueue(
        self,
        task_data: Dict[str, Any],
        priority: int = 0,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """
        إضافة مهمة جديدة إلى قائمة الانتظار.

        المعاملات
        ---------
        task_data : dict
            بيانات المهمة
        priority : int
            الأولوية (0 = الأعلى، أرقام أكبر = أقل أولوية)
        callback : callable, اختياري
            دالة تُستدعى عند اكتمال المهمة

        العائد
        -------
        str
            معرّف المهمة المُنشأة
        """
        with self._queue_lock:
            if len(self._task_queue) >= self._max_queue_size:
                raise RuntimeError(
                    f"قائمة الانتظار ممتلئة ({self._max_queue_size} مهمة)"
                )

            task_id: str = self._generate_task_id()
            task: Task = Task(
                task_id=task_id,
                data=task_data,
                priority=priority,
                callback=callback,
            )

            prioritized: PrioritizedTask = PrioritizedTask(
                priority=priority,
                task=task,
            )

            self._task_queue.append(prioritized)
            self._task_history[task_id] = task

            # ترتيب الطابور حسب الأولوية
            sorted_queue: deque[PrioritizedTask] = deque(
                sorted(self._task_queue, key=lambda pt: pt.priority)
            )
            self._task_queue.clear()
            self._task_queue.extend(sorted_queue)

        self._logger.debug(
            "تمت إضافة المهمة '%s' إلى الطابور | الأولوية: %d | الطول: %d",
            task_id,
            priority,
            self.queue_size,
        )

        return task_id

    def process_next(self) -> Optional[Dict[str, Any]]:
        """
        معالجة المهمة التالية في قائمة الانتظار.

        العائد
        -------
        dict أو None
            نتيجة المهمة، أو None إذا كانت القائمة فارغة
        """
        with self._queue_lock:
            if not self._task_queue:
                return None

            prioritized: PrioritizedTask = self._task_queue.popleft()
            task: Task = prioritized.task

        # ─── تنفيذ المهمة ─────────────────────────────────────
        return self._run_task(task)

    def process_all(self) -> List[Dict[str, Any]]:
        """
        معالجة جميع المهام في قائمة الانتظار.

        العائد
        -------
        list[dict]
            قائمة نتائج جميع المهام
        """
        results: List[Dict[str, Any]] = []

        while self.queue_size > 0 and not self._stop_event.is_set():
            result = self.process_next()
            if result is not None:
                results.append(result)

        self._logger.info(
            "اكتملت معالجة جميع المهام | النتائج: %d",
            len(results),
        )
        return results

    def clear_queue(self) -> int:
        """
        مسح قائمة الانتظار وإلغاء جميع المهام المعلقة.

        العائد
        -------
        int
            عدد المهام الملغاة
        """
        with self._queue_lock:
            cancelled_count: int = len(self._task_queue)

            for prioritized in self._task_queue:
                task = prioritized.task
                task.status = TaskStatus.CANCELLED
                self._logger.debug("تم إلغاء المهمة: %s", task.task_id)

            self._task_queue.clear()

        self._logger.info("تم مسح قائمة الانتظار | مهام ملغاة: %d", cancelled_count)
        return cancelled_count

    # ─── التنفيذ الداخلي ────────────────────────────────────────
    def _run_task(self, task: Task) -> Dict[str, Any]:
        """
        تشغيل مهمة واحدة مع إدارة الحالة والتسجيل.

        المعاملات
        ---------
        task : Task
            كائن المهمة

        العائد
        -------
        dict
            نتيجة التنفيذ
        """
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        self._total_tasks += 1
        self._logger.info(
            "بدء تنفيذ المهمة: %s | الأولوية: %d",
            task.task_id,
            task.priority,
        )

        try:
            result: Dict[str, Any] = self.execute(task.data)

            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            self._successful_tasks += 1

            self._logger.info(
                "اكتملت المهمة: %s | المدة: %.2f ثانية",
                task.task_id,
                task.duration or 0.0,
            )

            # ─── استدعاء الدالة المستدعاة ─────────────────────
            if task.callback is not None:
                try:
                    task.callback(result)
                except Exception as cb_exc:
                    self._logger.warning(
                        "خطأ في دالة الاستدعاء للمهمة %s: %s",
                        task.task_id,
                        cb_exc,
                    )

            return result

        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.completed_at = time.time()
            self._failed_tasks += 1

            self._logger.error(
                "فشلت المهمة: %s | الخطأ: %s | المدة: %.2f ثانية",
                task.task_id,
                exc,
                task.duration or 0.0,
            )

            return {
                "success": False,
                "error": str(exc),
                "task_id": task.task_id,
            }

    # ─── التحكم بدورة الحياة ────────────────────────────────────
    def start(self) -> None:
        """بدء تشغيل الوكيل"""
        if self._is_running:
            self._logger.warning("الوكيل '%s' يعمل بالفعل", self._agent_name)
            return

        self._is_running = True
        self._stop_event.clear()
        self._logger.info("تم بدء تشغيل الوكيل: %s", self._agent_name)

    def stop(self, wait_for_completion: bool = False) -> None:
        """
        إيقاف تشغيل الوكيل.

        المعاملات
        ---------
        wait_for_completion : bool
            هل ينتظر اكتمال المهمة الحالية قبل الإيقاف
        """
        if not self._is_running:
            return

        self._logger.info(
            "جاري إيقاف الوكيل: %s | الانتظار: %s",
            self._agent_name,
            wait_for_completion,
        )

        self._stop_event.set()
        self._is_running = False

        if wait_for_completion:
            # انتظار انتهاء المعالجة الحالية
            for _ in range(50):  # أقصى 5 ثوانٍ
                if not self._is_processing:
                    break
                time.sleep(0.1)

        self._logger.info("تم إيقاف الوكيل: %s", self._agent_name)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        الحصول على حالة مهمة محددة.

        المعاملات
        ---------
        task_id : str
            معرّف المهمة

        العائد
        -------
        dict أو None
            حالة المهمة، أو None إذا لم تُوجد
        """
        task: Optional[Task] = self._task_history.get(task_id)
        if task is None:
            return None
        return task.to_dict()

    def get_history(
        self,
        status_filter: Optional[TaskStatus] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        الحصول على سجل المهام.

        المعاملات
        ---------
        status_filter : TaskStatus, اختياري
            فلتر حسب الحالة
        limit : int
            الحد الأقصى للنتائج

        العائد
        -------
        list[dict]
            قائمة المهام المطلوبة
        """
        tasks: List[Task] = list(self._task_history.values())

        if status_filter is not None:
            tasks = [t for t in tasks if t.status == status_filter]

        # ترتيب حسب وقت الإنشاء (الأحدث أولاً)
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return [t.to_dict() for t in tasks[:limit]]

    # ─── التمثيل النصي ──────────────────────────────────────────
    def __repr__(self) -> str:
        """تمثيل نصي للوكيل"""
        return (
            f"{self.__class__.__name__}("
            f"name='{self._agent_name}', "
            f"running={self._is_running}, "
            f"queue={self.queue_size})"
        )

    def __str__(self) -> str:
        """وصف نصي موجز"""
        return self._agent_name

    def __enter__(self) -> "BaseAgent":
        """دعم بروتوكول context manager"""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Any | None,
        exc_val: Any | None,
        exc_tb: Any | None,
    ) -> None:
        """إغلاق تلقائي عند الخروج من السياق"""
        self.stop(wait_for_completion=True)
