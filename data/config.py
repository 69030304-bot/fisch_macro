"""
data/config.py - Robust, atomic JSON configuration management.

Designed by Member 69030343 (นายธีระนิตย์ บุญทวี — Backend & Database Developer).
Provides atomic writes, graceful fallback to defaults, and corruption recovery.
"""
from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict, Optional


class ConfigManager:
    """Manages application configuration files with atomic file writing and schema defaults."""

    def __init__(self, file_path: str, defaults: Optional[Dict[str, Any]] = None):
        self.file_path = os.path.abspath(file_path)
        self.defaults = dict(defaults or {})
        self._data: Dict[str, Any] = dict(self.defaults)
        self.load()

    @property
    def data(self) -> Dict[str, Any]:
        """Return a copy of the active configuration dictionary."""
        return dict(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value by key."""
        return self._data.get(key, default if default is not None else self.defaults.get(key))

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value in memory."""
        self._data[key] = value

    def update(self, new_values: Dict[str, Any]) -> None:
        """Batch update configuration in memory."""
        self._data.update(new_values)

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from disk.
        If file does not exist, defaults are used.
        If file is corrupted, backs up corrupted file and falls back to defaults.
        """
        config = dict(self.defaults)
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        loaded = json.loads(content)
                        if isinstance(loaded, dict):
                            config.update(loaded)
            except Exception as exc:
                # File is corrupted, create backup for safety and use defaults
                backup_path = f"{self.file_path}.corrupted"
                try:
                    shutil.copy2(self.file_path, backup_path)
                except Exception:
                    pass
        self._data = config
        return dict(self._data)

    def save(self, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Atomically write configuration to disk.
        Writes to a temporary file first, flushes and fsyncs, then renames to target.
        """
        if data is not None:
            self._data.update(data)

        dir_path = os.path.dirname(self.file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

        tmp_path = f"{self.file_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.file_path)
            return True
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise
