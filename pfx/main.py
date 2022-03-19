"""
pfx

Layer programs/versions to build a personal prefix
"""
# pylint: disable=unused-argument
import argparse
from os import environ
from pathlib import Path
from typing import Optional


def current_prefix() -> Path:
    "Get the current prefix path"
    pfx_prefix = environ.get("PFX_PREFIX")
    if pfx_prefix:
        return Path(pfx_prefix)

    return Path.home() / ".prefix"


def current_opt() -> Path:
    "Get the current program opt path"
    pfx_opt = environ.get("PFX_OPT")
    if pfx_opt:
        return Path(pfx_opt)

    return Path.home() / ".opt"


def mount() -> None:
    """
    Remount the prefix by collecting programs/versions from the "opt" folder
    and overlaying them into the "prefix" folder.
    """


def use(program: str, version: Optional[str]) -> None:
    """
    Remount the prefix with a specific program/version, but do not update the
    permanent settings.
    """


def install(program: str, version: str) -> None:
    """
    Remount the prefix such that new files/folders placed into it will be
    installed to the provided program/version.
    """


def uninstall(program: str) -> None:
    """
    Disable a program from participating in the prefix, and remount the prefix
    with that program removed.
    """


def set_(program: str, version: str) -> None:
    """
    Change the default version of a program in the prefix and remount it.
    """


def unset(program: str) -> None:
    """
    Remove a program version override previously provided as a prefix default.
    """


def main() -> None:
    "Main pfx entry point"
    parser = argparse.ArgumentParser(
        description="Manage a personal system prefix by layering program installations"
    )

    parser.parse_args()


if __name__ == "__main__":
    main()
