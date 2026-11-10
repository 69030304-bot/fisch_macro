"""
core/events.py - Thread-safe Publish/Subscribe Event Bus.

Decouples core automation, UI presentation, and monitoring layers.
"""
import threading
from typing import Any, Callable, Dict, List, Optional


class EventBus:
    """Thread-safe publish/subscribe event dispatcher."""

    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        """Subscribe a callable to a named topic."""
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            if handler not in self._subscribers[topic]:
                self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[Any], None]) -> bool:
        """Unsubscribe a callable from a named topic."""
        with self._lock:
            if topic in self._subscribers and handler in self._subscribers[topic]:
                self._subscribers[topic].remove(handler)
                if not self._subscribers[topic]:
                    del self._subscribers[topic]
                return True
            return False

    def publish(self, topic: str, data: Any = None) -> None:
        """Publish an event to all subscribers of topic outside lock to prevent deadlocks."""
        handlers_to_call = []
        with self._lock:
            if topic in self._subscribers:
                handlers_to_call = list(self._subscribers[topic])

        for handler in handlers_to_call:
            try:
                handler(data)
            except Exception:
                pass

    def clear(self) -> None:
        """Clear all topic subscribers."""
        with self._lock:
            self._subscribers.clear()


# Default global event bus instance
default_bus = EventBus()
