#!/usr/bin/env nix-shell
#! nix-shell -i python3.12 --pure
#! nix-shell -p python312 git python312Packages.requests

from __future__ import annotations

import argparse
import logging
import os
import shlex
import shutil
import string
import subprocess as sp
import sys
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import requests

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
            sp.check_call(shlex.split(f"git clone {self.url} {self.path}"))

        sp.check_call(shlex.split(f"git -C {self.path} fetch origin"))

    def read_file(self, path: str, tag: str) -> str:
        sp.check_call(shlex.split(f"git -C {self.path} checkout {tag}"))
        return (self.path / path).read_text()


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    args = parser.parse_args()

    repo = Repo.default()
    repo.fetch()

    version = args.version
    tag = f"release_{version}"

    tag_dir = Path("tags") / tag
    tag_dir.mkdir(exist_ok=True)

    cargo_lock = repo.read_file(path="src/rust/engine/Cargo.lock", tag=tag)
    (tag_dir / "Cargo.lock").write_text(cargo_lock)

    rust_toolchain = repo.read_file(path="src/rust/engine/rust-toolchain", tag=tag)
    rust_version = tomllib.loads(rust_toolchain)["toolchain"]["channel"]

    template_string = Path("template.nix").read_text()
    result = string.Template(template_string).safe_substitute(
        version=args.version,
        args=shlex.join(sys.argv),
        hash="",
        rust_version=rust_version,
        cargo_lock_url=f"https://raw.githubusercontent.com/pantsbuild/pants/{tag}/src/rust/engine/Cargo.lock",
        rust_toolchain_url=f"https://raw.githubusercontent.com/pantsbuild/pants/{tag}/src/rust/engine/rust-toolchain",
    )
    (tag_dir / "default.nix").write_text(result)


if __name__ == "__main__":
    main()
