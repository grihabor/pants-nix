from __future__ import annotations

import argparse
import asyncio
import json
import logging
import operator
import os
import re
import shlex
import shutil
import string
import subprocess as sp
import sys
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from functools import total_ordering
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, ClassVar, Generator, NamedTuple

import requests
import tomllib

logger = logging.getLogger(__name__)

git_url_re = re.compile(r"^git\+(?P<url>https://[^/]+/[^/]+/[^/.?]+(.git)?)(?P<rev1>\?rev=[^#]+|)(?P<rev2>#.*|)$")

output_hash_overrides = json.loads(Path("output_hash_overrides.json").read_text("utf-8"))


semaphore = asyncio.Semaphore(50)


async def _run(command: str) -> str:
    await semaphore.acquire()
    logger.info("running: %s", command)
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()
    finally:
        semaphore.release()

    if proc.returncode != 0:
        logger.error(f"{command!r} exited with {proc.returncode}, stderr:\n{stderr.decode()}")

    return stdout.decode()


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    tag_command = subparsers.add_parser("tag")
    tag_command.add_argument("version")
    tag_command.add_argument("--force", action=argparse.BooleanOptionalAction)
    tag_command.set_defaults(entrypoint=generate_single_tag)

    all_command = subparsers.add_parser("all")
    all_command.add_argument("--force", action=argparse.BooleanOptionalAction)
    all_command.add_argument("--start", type=Version.from_tag, required=True)
    all_command.set_defaults(entrypoint=generate_many_tags)

    args = parser.parse_args()
    asyncio.run(args.entrypoint(args))


async def generate_many_tags(args: Any):
    repo = Repo.default()
    await repo.fetch()

    all_versions = await repo.list_versions()
    versions = [f"{version}" for version in all_versions if version > args.start]

    print("Going to generate these versions:", versions)
    if input("Continue? [y/n] ").lower() not in ("y", "yes"):
        return

    async with asyncio.TaskGroup() as tg:
        for version in versions:
            tg.create_task(_generate_tag(repo, version, force=args.force))

    _generate_list_of_packages()


async def generate_single_tag(args: Any) -> None:
    repo = Repo.default()
    await repo.fetch()
    version = args.version
    await _generate_tag(repo, version, force=args.force)
    _generate_list_of_packages()


async def _nix_prefetch_git(url: str, rev: str) -> str:
    return await _run(f"nix-prefetch-git {url} --rev {rev} --quiet")


async def _prefetch_output_hashes(cargo_lock: str) -> list[tuple[str, str]]:
    futures = [_prefetch_package_hash(package) for package in tomllib.loads(cargo_lock)["package"]]
    return [result for f in asyncio.as_completed(futures) if (result := await f) is not None]


async def _prefetch_package_hash(package) -> tuple[str, str] | None:
    source = package.get("source", "")
    m = git_url_re.match(source)
    if m is None:
        return None

    pname = f"{package['name']}-{package['version']}"
    # I have no idea why, but lmdb-rkv-0.14.0 fails to build with the
    # prefetched hash. To address this we include a hard-coded, known-good
    # set of hash overrides. If we find pname in output_hash_overrides.json
    # we use the provided hash instead of prefetching.
    hash_ = output_hash_overrides.get(pname)
    if hash_ is None:
        url, rev1, rev2 = m.group("url", "rev1", "rev2")
        rev = rev1[5:] if rev1 else rev2[1:] if rev2 else "HEAD"
        raw = await _nix_prefetch_git(url, rev)
        hash_ = json.loads(raw).get("hash")
    return (pname, hash_)


async def _generate_tag(repo: Repo, version: str, force: bool = False) -> None:
    tag = f"release_{version}"

    tag_dir = Path("tags") / tag
    if not force and tag_dir.exists():
        logger.info(f"dir {tag_dir} exists, skipping")
        return

    tag_dir.mkdir(exist_ok=True)

    cargo_lock = await repo.read_file(path="src/rust/engine/Cargo.lock", tag=tag)
    (tag_dir / "Cargo.lock").write_text(cargo_lock)

    rust_toolchain = await repo.read_file(path="src/rust/engine/rust-toolchain", tag=tag)
    rust_version = tomllib.loads(rust_toolchain)["toolchain"]["channel"]

    template_string = Path("template.nix").read_text("utf-8")
    output_hashes = await _prefetch_output_hashes(cargo_lock)
    output_hashes.sort(key=operator.itemgetter(0))
    print(output_hashes)
    result = string.Template(template_string).safe_substitute(
        version=version,
        args=f"{sys.argv[0]} tag {version}",
        hash=await repo.tag_hash(tag),
        rust_version=rust_version,
        cargo_lock_url=f"https://raw.githubusercontent.com/pantsbuild/pants/{tag}/src/rust/engine/Cargo.lock",
        rust_toolchain_url=f"https://raw.githubusercontent.com/pantsbuild/pants/{tag}/src/rust/engine/rust-toolchain",
        output_hashes="\n      ".join(f'"{pname}" = "{hash_}";' for pname, hash_ in output_hashes),
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

    async def fetch(self) -> None:
        if self.path.exists():
            result = await _run(f"git -C {self.path} rev-parse --is-bare-repository")
            if result.strip() == "false":
                logger.info(f"cloned repo is not bare, removing: {self.path}")
                shutil.rmtree(self.path)

        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            await _run(f"git clone --bare {self.url} {self.path}")

        await _run(f"git -C {self.path} fetch origin")

    async def read_file(self, path: str, tag: str) -> str:
        return await _run(f"git -C {self.path} show {tag}:{path}")

    async def tag_hash(self, tag: str) -> str:
        with TemporaryDirectory() as d:
            archive = Path(d) / "archive.tar.gz"
            await _run(f"git -C {self.path} archive -o {archive} {tag}")
            path = Path(d) / f"{tag}.tar.gz"
            path.mkdir()
            await _run(f"tar -xf {archive} -C {path}")
            await _run(f"find {path} -maxdepth 1")
            result = await _run(f"nix-hash --type sha256 --base32 --sri {path}")

        return result.strip()

    async def list_versions(self) -> list[Version]:
        lines = (await _run(f"git -C {self.path} tag --list release_*")).splitlines()
        versions = [
            Version.from_tag(stripped)
            for line in lines
            if not (stripped := line.strip()).startswith("release_1.") and not stripped.startswith("release_2.0.")
        ]
        versions.sort()
        return versions


def maybe_int(s: str | None) -> int | None:
    if s is None:
        return None
    return int(s)


INT32_MAX = 2**64 - 1


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    micro: int
    rc: int | None = None
    a: int | None = None
    dev: int | None = None

    regex: ClassVar[re.Pattern[str]] = re.compile(
        r"^release_(?P<major>[0-9]+).(?P<minor>[0-9]+).(?P<micro>[0-9]+)(rc(?P<rc>[0-9]+)|\.dev(?P<dev>[0-9]+)|a(?P<a>[0-9]+))?$"
    )

    @classmethod
    def from_tag(cls, tag: str) -> Version:
        match = cls.regex.match(tag)
        if not match:
            raise ValueError(f"Tag `{tag}` doesn't match the regex `{cls.regex}")
        return Version(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            micro=int(match.group("micro")),
            rc=maybe_int(match.group("rc")),
            a=maybe_int(match.group("a")),
            dev=maybe_int(match.group("dev")),
        )

    def __str__(self) -> str:
        return f"{self}"

    def __format__(self, __format_spec: str) -> str:
        extra = ""
        if self.rc:
            extra = f"rc{self.rc}"
        if self.a:
            extra = f"a{self.a}"
        if self.dev:
            extra = f".dev{self.dev}"
        return f"{self.major}.{self.minor}.{self.micro}{extra}"

    @property
    def is_stable(self) -> bool:
        return not self.other

    def _tuple(self) -> tuple[int, int, int, int, int, int]:
        main = (
            self.major,
            self.minor,
            self.micro,
        )
        extra = (
            self.rc if self.rc is not None else -1,
            self.a if self.a is not None else -1,
            self.dev if self.dev is not None else -1,
        )
        if extra == (-1, -1, -1):
            extra = (INT32_MAX, INT32_MAX, INT32_MAX)
        return main + extra

    def __lt__(self, other: Version) -> bool:
        return self._tuple() < other._tuple()

    def __le__(self, other: Version) -> bool:
        return self._tuple() <= other._tuple()

    def __gt__(self, other: Version) -> bool:
        return self._tuple() > other._tuple()

    def __ge__(self, other: Version) -> bool:
        return self._tuple() >= other._tuple()
