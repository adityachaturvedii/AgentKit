"""Strict private atomic writes adapted from OpenHarness ``utils/fs.py``."""

import contextlib
import os
from pathlib import Path
import tempfile


def atomic_private_write(path, data, *, mode=0o600):
    if type(mode) is not int or mode & ~0o777 or mode & 0o077:
        raise ValueError("atomic private file mode must not grant group/other access")
    target = Path(path)
    if target.exists() and target.is_symlink():
        raise ValueError("atomic write target cannot be a symlink")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = data.encode("utf-8") if isinstance(data, str) else data
    if not isinstance(payload, bytes):
        raise TypeError("atomic write data must be bytes or text")
    descriptor, temporary_name = tempfile.mkstemp(prefix="." + target.name + ".",
                                                  suffix=".tmp", dir=str(target.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise
