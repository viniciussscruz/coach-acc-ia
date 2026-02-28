from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import TextIO


class _StreamTee:
    def __init__(self, original: TextIO, file_handle: TextIO) -> None:
        self._original = original
        self._file = file_handle

    def write(self, data: str) -> int:
        self._original.write(data)
        try:
            self._file.write(data)
        except ValueError:
            # The log file can already be closed during interpreter shutdown.
            pass
        return len(data)

    def flush(self) -> None:
        try:
            self._original.flush()
        except Exception:
            pass
        try:
            self._file.flush()
        except ValueError:
            pass

    def isatty(self) -> bool:
        return bool(getattr(self._original, "isatty", lambda: False)())

    @property
    def encoding(self) -> str | None:
        return getattr(self._original, "encoding", None)


def configure_runtime_log(log_file: Path) -> Path:
    log_path = log_file.expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("a", encoding="utf-8", buffering=1)
    handle.write(
        f"\n========== AIDC session started {dt.datetime.now().isoformat(timespec='seconds')} ==========\n"
    )

    if not isinstance(sys.stdout, _StreamTee):
        sys.stdout = _StreamTee(sys.stdout, handle)  # type: ignore[assignment]
    if not isinstance(sys.stderr, _StreamTee):
        sys.stderr = _StreamTee(sys.stderr, handle)  # type: ignore[assignment]

    return log_path

