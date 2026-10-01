"""Locate immutable AgentKit resources in a checkout or installed wheel."""

from pathlib import Path


_PACKAGE = Path(__file__).resolve().parent
_CHECKOUT = _PACKAGE.parent
_INSTALLED = _PACKAGE / "_resources"


def _is_resource_root(path):
    return ((path / "catalog.json").is_file() and
            all((path / name).is_dir() for name in ("skills", "domains", "contracts")))


def resource_root():
    """Return the filesystem root for bundled, read-only toolkit resources."""
    if _is_resource_root(_CHECKOUT):
        return _CHECKOUT
    if _is_resource_root(_INSTALLED):
        return _INSTALLED
    raise RuntimeError("AgentKit packaged resources are missing or incomplete")


def resource_path(*parts):
    """Return a path below the active immutable resource root."""
    return resource_root().joinpath(*parts)
