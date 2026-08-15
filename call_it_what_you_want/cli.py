"""
Command line access to the records, for getting what an application
discovered back into the package.

The loop it's built for: your application calls `record` as it runs and
warns about anything new, `ciwyw new` shows you what piled up, and
`ciwyw show --output` writes the file to commit.
"""

import sys
from pathlib import Path

from .data import NCAA, default_teams, local_csv, merged_csv
from .local import clear_local, local_path


class Records:
    """
    Read and stage team name records.
    """

    def show(self, namespace: str = NCAA, output: str | None = None) -> None:
        """
        Print the bundled CSV with the local additions appended -- what
        the file in the package should look like once they're committed.

        Pass --output to write it somewhere instead. Writing it straight
        over the package's own copy is the point:

            ciwyw show --output call_it_what_you_want/data/ncaa.csv
        """
        text = merged_csv(namespace)
        if output is None:
            sys.stdout.write(text)
            return
        Path(output).write_text(text, encoding="utf-8")
        print(f"Wrote {len(text.splitlines()) - 1} rows to {output}.", file=sys.stderr)

    def new(self, namespace: str = NCAA) -> None:
        """
        Print only the rows recorded locally -- the ones not in the
        package yet.
        """
        text = local_csv(namespace)
        if not text:
            print(
                f"Nothing recorded locally for {namespace!r} "
                f"({local_path(namespace)}).",
                file=sys.stderr,
            )
            return
        sys.stdout.write(text)

    def where(self, namespace: str = NCAA) -> None:
        """
        Print the path local records are written to, and how many are
        there.
        """
        path = local_path(namespace)
        rows = len(local_csv(namespace).splitlines())
        print(path)
        print(
            f"{rows - 1} local rows." if rows else "No local records yet.",
            file=sys.stderr,
        )

    def count(self, namespace: str = NCAA) -> None:
        """
        Print how many teams are in the registry, bundled and local.
        """
        bundled = len(default_teams(namespace, include_local=False))
        total = len(default_teams(namespace))
        print(f"{total} teams ({bundled} bundled, {total - bundled} added locally).")

    def clear(self, namespace: str = NCAA, yes: bool = False) -> None:
        """
        Delete the local records for `namespace`, once they've been
        committed to the package. Needs --yes, since they're the only
        copy until they're upstreamed.
        """
        path = local_path(namespace)
        rows = len(local_csv(namespace).splitlines())
        if not rows:
            print(f"Nothing recorded locally for {namespace!r} ({path}).")
            return
        if not yes:
            raise SystemExit(
                f"{path} holds {rows - 1} rows that aren't in the package. "
                "Save them with `ciwyw new` first, then pass --yes."
            )
        clear_local(namespace)
        print(f"Deleted {path}.")


def main() -> None:
    try:
        import fire
    except ImportError:
        raise SystemExit(
            "The command line tool needs fire: pip install 'call-it-what-you-want[cli]'"
        ) from None
    fire.Fire(Records)
