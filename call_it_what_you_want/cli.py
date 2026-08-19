"""
Command line access to the records, for getting what an application
discovered back into the package.

The loop it's built for: your application calls `record` as it runs and
warns about anything new, `ciwyw new` shows you what piled up, and
`ciwyw show --output` writes the file to commit.
"""

import asyncio
import sys
from pathlib import Path

from .classification import KIND as CLASSIFICATIONS
from .classification import (
    default_classifications,
    local_classifications_csv,
    merged_classifications_csv,
)
from .data import NCAA, default_teams, local_csv, merged_csv
from .local import clear_local, local_path


class _Classifications:
    """
    Read and stage what division and conference teams played in.
    """

    def show(self, namespace: str = NCAA, output: str | None = None) -> None:
        """
        Print the bundled classifications with the local additions
        appended -- what the file in the package should look like once
        they're committed.

            ciwyw classifications show --output \
call_it_what_you_want/data/ncaa_classifications.csv
        """
        text = merged_classifications_csv(namespace)
        if output is None:
            sys.stdout.write(text)
            return
        Path(output).write_text(text, encoding="utf-8")
        print(f"Wrote {len(text.splitlines()) - 1} rows to {output}.", file=sys.stderr)

    def new(self, namespace: str = NCAA) -> None:
        """
        Print only the classifications recorded locally.
        """
        text = local_classifications_csv(namespace)
        if not text:
            print(
                f"No classifications recorded locally for {namespace!r} "
                f"({local_path(namespace, CLASSIFICATIONS)}).",
                file=sys.stderr,
            )
            return
        sys.stdout.write(text)

    def where(self, namespace: str = NCAA) -> None:
        """
        Print the path local classifications are written to.
        """
        path = local_path(namespace, CLASSIFICATIONS)
        rows = len(local_classifications_csv(namespace).splitlines())
        print(path)
        print(
            f"{rows - 1} local rows." if rows else "No local classifications yet.",
            file=sys.stderr,
        )

    def count(self, namespace: str = NCAA) -> None:
        """
        Print how many classification observations are on file.
        """
        bundled = len(default_classifications(namespace, include_local=False))
        total = len(default_classifications(namespace))
        print(
            f"{total} observations ({bundled} bundled, "
            f"{total - bundled} added locally)."
        )

    def clear(self, namespace: str = NCAA, yes: bool = False) -> None:
        """
        Delete the local classifications, once they've been committed.
        """
        path = local_path(namespace, CLASSIFICATIONS)
        rows = len(local_classifications_csv(namespace).splitlines())
        if not rows:
            print(f"No classifications recorded locally for {namespace!r} ({path}).")
            return
        if not yes:
            raise SystemExit(
                f"{path} holds {rows - 1} rows that aren't in the package. "
                "Save them with `ciwyw classifications new` first, then pass --yes."
            )
        clear_local(namespace, CLASSIFICATIONS)
        print(f"Deleted {path}.")

    def fetch(
        self,
        league: str,
        start: int,
        end: int | None = None,
        namespace: str = NCAA,
    ) -> None:
        """
        Look up divisions and conferences on ESPN and stage what's new.

        One season, or a range:

            ciwyw classifications fetch ncaafb 2023
            ciwyw classifications fetch ncaafb 2002 2024

        Years are done one at a time on purpose -- a season is already a
        few dozen parallel requests, and a quarter century of them at once
        is how you get rate limited.
        """
        from .espn import leagues, record_tiers

        if league not in leagues():
            raise SystemExit(
                f"No ESPN groups known for {league!r}. "
                f"Available: {', '.join(sorted(leagues()))}."
            )
        total = 0
        for year in range(start, (end or start) + 1):
            staged = asyncio.run(record_tiers(year, league, namespace=namespace))
            total += staged
            print(f"{year}: {staged} new", file=sys.stderr)
        print(
            f"Staged {total} observations in {local_path(namespace, CLASSIFICATIONS)}.",
            file=sys.stderr,
        )


class Records:
    """
    Read and stage team name records.
    """

    def __init__(self) -> None:
        self.classifications = _Classifications()

    def sync(self, *args, **kwargs) -> None:
        """
        Pull a league's names from ESPN and stage what's new.

            ciwyw sync ncaafb --check

        Imported here rather than at module scope: it needs the `sync`
        extra, and the rest of these commands work without it.
        """
        from .sync import main as sync_main

        sync_main(*args, **kwargs)

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
