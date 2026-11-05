"""Shared rules for the in-process caches of files read from disk.

Both the montage cache (``components.qc_viewer``) and the NIfTI cache
(``managers.niivue_viewer_manager``) use ``st.cache_resource`` and follow the
same rules:

1. **Limits** are ``MONTAGE_CACHE_MAX_ENTRIES`` / ``NIIVUE_CACHE_MAX_ENTRIES``
   in ``constants.py``.
2. **Keys** include each file's :func:`file_signature` (resolved path, mtime,
   size). A file regenerated while the app runs gets a new key and is reloaded
   on the next rerun; the stale entry ages out under ``max_entries``.
3. **Values** are immutable. ``cache_resource`` hands the same object to every
   session and rerun, so cached values go through :func:`freeze` (or are
   already immutable, like tuples of ``bytes``). Mutating one raises
   ``TypeError`` instead of silently changing it for other sessions.
"""

from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Optional, Tuple, Union

FileSignature = Tuple[str, Optional[int], Optional[int]]


def file_signature(path: Union[str, Path]) -> FileSignature:
    """Return ``(resolved path, mtime_ns, size)`` for use in a cache key.

    A missing or unreadable file gets ``None`` for mtime and size, so the key
    changes once the file appears.
    """
    path = Path(path)
    try:
        stat = path.stat()
    except OSError:
        return str(path.resolve()), None, None
    return str(path.resolve()), stat.st_mtime_ns, stat.st_size


def files_signature(paths: Iterable[Union[str, Path]]) -> Tuple[FileSignature, ...]:
    """:func:`file_signature` for each path, in order."""
    return tuple(file_signature(p) for p in paths)


def freeze(value: Any) -> Any:
    """Return a read-only copy of ``value``, converting containers recursively.

    Dicts become ``MappingProxyType`` and lists/tuples become tuples. Other
    values are returned unchanged, so leaves should already be immutable
    (str, bytes, numbers, None).
    """
    if isinstance(value, dict):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    return value
