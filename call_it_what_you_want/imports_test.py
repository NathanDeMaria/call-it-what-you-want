"""The base install has no third-party dependencies. Keep it that way.

Translating a name is what a serving image needs, and it shouldn't have to
carry an HTTP stack or an AWS client to do it. That's only true as long as
nothing on the import path of `call_it_what_you_want` reaches for one, which
is easy to break by adding a top-level import to the wrong module.
"""

import subprocess
import sys

# What the `sync` extra brings in. None of it may be imported by the base
# package -- `candidates`, `espn` and `sync` are the modules allowed to.
_EXTRA_ONLY = ("aiohttp", "endgame", "endgame_aws", "aiobotocore", "fire")


def test_importing_the_package_pulls_in_nothing_third_party() -> None:
    checked = ", ".join(repr(m) for m in _EXTRA_ONLY)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "import call_it_what_you_want\n"
            f"leaked = [m for m in ({checked},) if m in sys.modules]\n"
            "print(','.join(leaked))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "", (
        f"importing call_it_what_you_want pulled in {result.stdout.strip()}, "
        "which is only in the `sync` extra. Move that import into the module "
        "that needs it, or behind TYPE_CHECKING if it's only a type hint."
    )
