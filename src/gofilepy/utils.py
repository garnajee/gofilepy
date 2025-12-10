#!/usr/bin/env python3

import typing
import io

class ProgressFileReader(io.BufferedReader):
    """
    Wraps a file object to trigger a callback when data is read.
    This allows monitoring upload progress in httpx without loading the file into RAM.
    """
    def __init__(self, filename: str, callback: typing.Callable[[int], None]):
        self._f = open(filename, 'rb')
        self._callback = callback
        # Get file size for verification if needed, or just standard init
        super().__init__(self._f)

    def read(self, size: int = -1) -> bytes:
        # Read the chunk from disk
        chunk = self._f.read(size)
        # Update the progress bar with the length of the chunk read
        if chunk:
            self._callback(len(chunk))
        return chunk

    def close(self) -> None:
        if hasattr(self, '_f'):
            self._f.close()

