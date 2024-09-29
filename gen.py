#!/usr/bin/env nix-shell
#! nix-shell -i python3.12 --pure
#! nix-shell -p python312 git nix python312Packages.requests nix-prefetch-git

from __future__ import annotations

import argparse
import logging
import json
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
from typing import Any, Generator, NamedTuple

import requests
import tomllib

logger = logging.getLogger(__name__)

git_url_re = re.compile(r"^git\+(?P<url>https://[^/]+/[^/]+/[^/.?]+(.git)?)(?P<rev1>\?rev=[^#]+|)(?P<rev2>#.*|)$")

output_hash_overrides = json.loads(Path("output_hash_overrides.json").read_text("utf-8"))


def _run(command: str) -> bytes:
    return sp.check_output(shlex.split(command))


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    tag_command = subparsers.add_parser("tag")
    tag_command.add_argument("version")
    tag_command.add_argument("--force", action=argparse.BooleanOptionalAction)
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
    _generate_tag(repo, version, force=args.force)
    _generate_list_of_packages()


def _nix_prefetch_git(url: str, rev: str) -> str:
    return _run(f"nix-prefetch-git {url} --rev {rev} --quiet").decode("utf-8")


def _prefetch_output_hashes(cargo_lock: str) -> str:
    output_hashes = set()
    for package in tomllib.loads(cargo_lock)["package"]:
        source = package.get("source", "")
        if not source.startswith("git+"):
            continue

        pname = f"{package["name"]}-{package["version"]}"
        hash_ = output_hash_overrides.get(pname)
        if hash_ is None:
            m = git_url_re.match(source)
            if not m:
                logger.warning(
                    "git package %s has invalid source %s, skipping prefetch",
                    pname,
                    source,
                )
                continue
            url, rev1, rev2 = m.group("url", "rev1", "rev2")
            rev = rev1[5:] if rev1 else rev2[1:] if rev2 else "HEAD"
            hash_ = json.loads(_nix_prefetch_git(url, rev)).get("hash")
        output_hashes.add(f'"{pname}" = "{hash_}";')

    if output_hashes:
        return f"""
    outputHashes = {{
      {"\n      ".join(output_hashes)}
    }};"""
    return ""


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

    output_hashes = list(_prefetch_output_hashes(cargo_lock))

    template_string = Path("template.nix").read_text("utf-8")
    result = string.Template(template_string).safe_substitute(
        version=version,
        args=f"{sys.argv[0]} tag {version}",
        hash=repo.tag_hash(tag),
        rust_version=rust_version,
        cargo_lock_url=f"https://raw.githubusercontent.com/pantsbuild/pants/{tag}/src/rust/engine/Cargo.lock",
        rust_toolchain_url=f"https://raw.githubusercontent.com/pantsbuild/pants/{tag}/src/rust/engine/rust-toolchain",
        output_hashes=_prefetch_output_hashes(cargo_lock),
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


if __name__ == "__main__":
    main()
