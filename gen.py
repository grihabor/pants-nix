#!/usr/bin/env nix-shell
#! nix-shell -i python3.12 --pure
#! nix-shell -p python312 git nix python312Packages.requests

from __future__ import annotations

import argparse
import logging
import os
import re
import shlex
import string
import subprocess as sp
import sys
from dataclasses import dataclass
from functools import total_ordering
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NamedTuple

import requests
import tomllib

logger = logging.getLogger(__name__)


def download_file(*, url: str, output_path: str):
    logger.info("downloading: %s", url)
    r = requests.get(url)
    r.raise_for_status()
    Path(output_path).write_text(r.text)


def download_toml(*, url: str):
    logger.info("downloading toml: %s", url)
    r = requests.get(url)
    r.raise_for_status()
    result = tomllib.load(BytesIO(r.content))
    logger.info("got toml: %s", result)
    return result


def _run(command: str) -> bytes:
    return sp.check_output(shlex.split(command))


@dataclass(frozen=True)
class Repo:
    path: Path
    url: str

    @classmethod
    def default(cls) -> Repo:
        return Repo(
            url="https://github.com/pantsbuild/pants.git",
            path=Path(os.environ["HOME"]) / ".cache" / "pants-nix" / "pants",
        )

    def fetch(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            _run(f"git clone {self.url} {self.path}")

        _run(f"git -C {self.path} fetch origin")

    def read_file(self, path: str, tag: str) -> str:
        _run(f"git -C {self.path} checkout {tag}")
        return (self.path / path).read_text()

    def tag_hash(self, tag: str) -> str:
        with TemporaryDirectory() as d:
            archive = Path(d) / "archive.tar.gz"
            _run(f"git -C {self.path} archive -o {archive} {tag}")
            path = Path(d) / f"{tag}.tar.gz"
            path.mkdir()
            _run(f"tar -xf {archive} -C {path}")
            _run(f"find {path} -maxdepth 1")
            result = _run(f"nix-hash --type sha256 --base32 --sri {path}")

        return result.decode(encoding="utf-8").strip()

    def list_versions(self) -> list[Version]:
        _run(f"git -C {self.path} checkout origin/main")
        lines = _run(f"git -C {self.path} tag --list release_*").decode("utf-8").splitlines()
        versions = [Version.from_tag(line.strip()) for line in lines]
        versions.sort()
        return versions


class Version(NamedTuple):
    major: int
    minor: int
    micro: int
    other: str

    @classmethod
    def from_tag(cls, tag: str) -> Version:
        regex = r"^release_([0-9]+).([0-9]+).([0-9]+)(.*)$"
        match = re.match(regex, tag)
        assert match, tag
        return Version(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            micro=int(match.group(3)),
            other=str(match.group(4)),
        )

    def __format__(self, __format_spec: str) -> str:
        return f"{self.major}.{self.minor}.{self.micro}{self.other}"


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    tag_command = subparsers.add_parser("tag")
    tag_command.add_argument("version")
    tag_command.set_defaults(entrypoint=generate_single_tag)

    all_command = subparsers.add_parser("all")
    all_command.add_argument("--force", action=argparse.BooleanOptionalAction)
    all_command.set_defaults(entrypoint=generate_many_tags)

    args = parser.parse_args()
    args.entrypoint(args)


def generate_many_tags(args: Any):
    repo = Repo.default()
    repo.fetch()

    versions = [f"{version}" for version in repo.list_versions() if version.major >= 2 and version.minor >= 19]

    print("Going to generate these versions:", versions)
    if input("Continue? [y/n] ").lower() not in ("y", "yes"):
        return

    for version in versions:
        _generate_tag(repo, version, force=args.force)

    _generate_list_of_packages()


def generate_single_tag(args: Any):
    repo = Repo.default()
    repo.fetch()
    version = args.version
    _generate_tag(repo, version)
    _generate_list_of_packages()


def _generate_tag(repo: Repo, version: str, force: bool = False):
    tag = f"release_{version}"

    tag_dir = Path("tags") / tag
    if not force and tag_dir.exists():
        logger.info(f"dir {tag_dir} exists, skipping")
        return

    tag_dir.mkdir(exist_ok=True)

    cargo_lock = repo.read_file(path="src/rust/engine/Cargo.lock", tag=tag)
    (tag_dir / "Cargo.lock").write_text(cargo_lock)

    rust_toolchain = repo.read_file(path="src/rust/engine/rust-toolchain", tag=tag)
    rust_version = tomllib.loads(rust_toolchain)["toolchain"]["channel"]

    template_string = Path("template.nix").read_text()
    result = string.Template(template_string).safe_substitute(
        version=version,
        args=f"{sys.argv[0]} tag {version}",
        hash=repo.tag_hash(tag),
        rust_version=rust_version,
        cargo_lock_url=f"https://raw.githubusercontent.com/pantsbuild/pants/{tag}/src/rust/engine/Cargo.lock",
        rust_toolchain_url=f"https://raw.githubusercontent.com/pantsbuild/pants/{tag}/src/rust/engine/rust-toolchain",
    )
    (tag_dir / "default.nix").write_text(result)


def _generate_list_of_packages():
    tags_dir = Path("tags")
    dirs = next(os.walk(tags_dir))[1]
    versions = [Version.from_tag(d) for d in dirs]
    versions.sort()

    path = Path("tags") / "default.nix"
    with open(path, "w") as f:
        f.write("{pkgs}: {\n")
        for v in versions:
            tag = f"release_{v}"
            f.write(f'  "{tag}" = pkgs.callPackage ./{tag} {{}};\n')
        f.write("}\n")


if __name__ == "__main__":
    main()
