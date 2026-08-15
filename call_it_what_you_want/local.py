"""
Where records the application discovers get written.

The bundled CSVs live inside the installed package, which is the wrong
place to write to: it's read-only under most installs, and a reinstall
wipes whatever landed there. So new observations go to a separate file
per namespace in a local data directory, which is layered over the
bundled data on load. That file is a staging area -- the CLI prints it
back out so the rows can be committed to the package.

This module is deliberately just file plumbing: it knows where the file
is and how to read and append rows, not what a team is.
"""

import csv
import os
from pathlib import Path

ENV_VAR = "CIWYW_DATA_DIR"
_APP_DIR = "call-it-what-you-want"


def local_dir() -> Path:
    """
    The directory local records are written to.

    `$CIWYW_DATA_DIR` if it's set, otherwise
    `$XDG_DATA_HOME/call-it-what-you-want`, otherwise
    `~/.local/share/call-it-what-you-want`.

    Point the environment variable somewhere per-project to keep one
    application's discoveries out of another's.
    """
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / _APP_DIR


def local_path(namespace: str) -> Path:
    """
    The local file for `namespace`, whether or not it exists yet.
    """
    return local_dir() / f"{namespace}.csv"


def read_local(namespace: str) -> list[str]:
    """
    The lines of the local file, header included, or [] if there isn't one.
    """
    path = local_path(namespace)
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def append_local(namespace: str, columns: tuple[str, ...], row: dict[str, str]) -> Path:
    """
    Add one row to the local file, creating it (and its directory) with a
    header if this is the first one. Returns the file it was written to.
    """
    path = local_path(namespace)
    path.parent.mkdir(parents=True, exist_ok=True)
    empty = not path.is_file() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        if empty:
            writer.writeheader()
        writer.writerow(row)
    return path


def clear_local(namespace: str) -> bool:
    """
    Delete the local file for `namespace`. Returns whether there was one.

    For use once the rows have been committed to the package, so they
    aren't carried twice.
    """
    path = local_path(namespace)
    if not path.is_file():
        return False
    path.unlink()
    return True
