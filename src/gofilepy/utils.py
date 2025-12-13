"""Utility helpers for GofilePy."""

from __future__ import annotations

import io
from typing import BinaryIO, Callable


class ProgressFileReader(io.BufferedReader):
    """Buffered reader that reports read progress through a callback."""

    def __init__(self, file_obj: BinaryIO, callback: Callable[[int], None]):
        self._callback = callback
        super().__init__(file_obj)

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        chunk = super().read(size)
        if chunk:
            self._callback(len(chunk))
        return chunk
