"""
pfx

Layer programs/versions to build a personal prefix
"""
import json
import logging
import os
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set

import click

LOGGER = logging.getLogger("pfx")


def _assure_path(path: Path) -> Path:
    if not path.exists():
        os.mkdir(path)

    return path


def pfx_path_home() -> Path:
    "Get the pfx home directory"
    pfx_dir = environ.get("PFX_DIR")
    if pfx_dir:
        return Path(pfx_dir)

    return _assure_path(Path.home() / ".pfx")


def pfx_path_lower(pfx_home: Path) -> Path:
    "Get a dummy lower directory"
    return _assure_path(pfx_home / ".lower")


def pfx_path_work(pfx_home: Path) -> Path:
    "Get a temporary working directory"
    return _assure_path(pfx_home / ".work")


def pfx_path_prefix(pfx_home: Path) -> Path:
    "Get the installation prefix"
    return _assure_path(pfx_home / ".prefix")


@dataclass
class Program:
    "Abstract representation of an install program"
    name: str
    version: str
    path: Path

    @classmethod
    def from_path(cls, program_path: Path) -> "Program":
        "Build a program entry given a known filesystem path"
        name, version = program_path.name.split("|")
        return Program(name, version, program_path)

    @classmethod
    def from_name_version(cls, pfx_home: Path, name: str, version: str) -> "Program":
        "Build a program entry given the name/version"
        return Program(name, version, pfx_home / f"{name}|{version}")

    @classmethod
    def all_programs(cls, pfx_home: Path) -> Iterable["Program"]:
        "Find all program entries in a provided prefix"
        all_dirs: List[str] = []
        for _, all_dirs, _ in os.walk(pfx_home):
            break

        for program_dir in sorted(pfx_home / d for d in all_dirs):
            if program_dir.name.startswith("."):
                continue

            name, version = program_dir.name.split("|")
            yield Program(name, version, program_dir)


@dataclass
class PfxConfig:
    "Python API wrapper for dealing with persistent configuration"
    overrides: Dict[str, str]
    excluded: Set[str]


@contextmanager
def pfx_config(pfx_home: Path) -> Iterator[PfxConfig]:
    "Load and save the pfx configuration from a home directory"
    cfg_path = pfx_home / ".config.json"

    if cfg_path.exists():
        with open(cfg_path, "r") as handle:
            cfg_json = json.load(handle)

        cfg = PfxConfig(
            cfg_json.get("overrides", {}),
            set(cfg_json.get("excluded", [])),
        )
    else:
        cfg = PfxConfig({}, set())

    yield cfg

    with open(cfg_path, "w") as handle:
        json.dump(
            {
                "overrides": cfg.overrides,
                "excluded": list(cfg.excluded),
            },
            handle,
        )


def remount(pfx_home: Path, config: PfxConfig, upper: Optional[Program] = None) -> None:
    "Remount the prefix given a config and optional upper directory"
    lower: Dict[str, Program] = {}

    for program in Program.all_programs(pfx_home):
        if upper and upper.name == program.name:
            continue
        if program.name in lower:
            continue
        if program.name in config.excluded:
            continue
        if (
            program.name in config.overrides
            and program.version != config.overrides[program.name]
        ):
            continue

        lower[program.name] = program

    pfx_prefix = pfx_path_prefix(pfx_home)
    subprocess.run(["fusermount", "-u", pfx_prefix], check=False)

    mount_command = ["fuse-overlayfs"]

    # fuse-overlayfs must always have a lower directory
    lower_dirs = [str(pfx_path_lower(pfx_home))]
    lower_dirs += [str(p.path) for p in lower.values()]
    lower_arg = ":".join(lower_dirs)

    mount_command += ["-o", f"lowerdir={lower_arg}"]

    if upper:
        mount_command += [
            "-o",
            f"upperdir={upper.path}",
            "-o",
            f"workdir={pfx_path_work(pfx_home)}",
        ]

    mount_command += [str(pfx_prefix)]

    subprocess.run(mount_command, check=True)


@click.group()
def cli() -> None:
    """
    Layer programs to build a personal prefix.
    """


@cli.command()
def mount() -> None:
    """
    Remount the prefix by collecting programs/versions from the "opt" folder
    and overlaying them into the "prefix" folder.
    """

    pfx_home = pfx_path_home()
    with pfx_config(pfx_home) as config:
        remount(pfx_home, config)


@cli.command()
def prefix() -> None:
    """
    Print the current prefix path.
    """

    print(pfx_path_prefix(pfx_path_home()))


@cli.command("list")
@click.argument("program", required=False)
# pylint: disable=unused-argument
def list_(program: Optional[str] = None) -> None:
    """
    When no program is provided, list all programs and versions available.
    If a program is provided, list all versions of that program.
    """


@cli.command()
@click.argument("program")
@click.argument("version")
def install(program: str, version: str) -> None:
    """
    Remount the prefix with a program/version as the "upper" directory.
    """
    pfx_home = pfx_path_home()

    with pfx_config(pfx_home) as config:
        intended = Program.from_name_version(pfx_home, program, version)
        if not intended.path.exists():
            os.mkdir(intended.path)

        remount(pfx_home, config, intended)


@cli.command()
@click.argument("program")
def uninstall(program: str) -> None:
    """
    Disable a program and remount the prefix with it removed.
    """
    pfx_home = pfx_path_home()

    # Check that the program exists
    found = False
    for existing in Program.all_programs(pfx_home):
        if existing.name == program:
            found = True
            break

    if not found:
        raise RuntimeError(f"Unable to find program; name={program}")

    with pfx_config(pfx_home) as config:
        if program in config.overrides:
            config.overrides.pop(program)

        config.excluded.add(program)


@cli.command(name="set")
@click.argument("program")
@click.argument("version")
def set_(program: str, version: str) -> None:
    """
    Change the default version of a program and remount the prefix.
    """
    pfx_home = pfx_path_home()

    # Check that the program exists
    found = False
    for existing in Program.all_programs(pfx_home):
        if existing.name == program and existing.version == version:
            found = True
            break

    if not found:
        raise RuntimeError(f"Unable to find program; name={program}, version={version}")

    with pfx_config(pfx_home) as config:
        config.excluded.discard(program)
        config.overrides[program] = version
        remount(pfx_home, config)


@cli.command()
@click.argument("program")
def unset(program: str) -> None:
    """
    Remove a program version override and remount the prefix.
    """
    pfx_home = pfx_path_home()

    with pfx_config(pfx_home) as config:
        del config.overrides[program]
        remount(pfx_home, config)


if __name__ == "__main__":
    cli()
