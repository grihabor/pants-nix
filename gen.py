#!/usr/bin/env nix-shell
#! nix-shell -i python3.12 --pure
#! nix-shell -p python312 python312Packages.requests

import argparse
import logging
import shlex
import shutil
import string
import sys
import tomllib
from io import BytesIO
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def download_file(*, url: str, output_path: str):
    logger.info("downloading: %s", url)
    r = requests.get(url)
    Path(output_path).write_text(r.text)


def download_toml(*, url: str):
    logger.info("downloading toml: %s", url)
    r = requests.get(url)
    r.raise_for_status()
    result = tomllib.load(BytesIO(r.content))
    logger.info("got toml: %s", result)
    return result


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    args = parser.parse_args()

    version = args.version
    tag = f"release_{args.version}"

    tag_dir = Path("tags") / tag
    tag_dir.mkdir(exist_ok=True)
    cargo_lock_url = f"https://raw.githubusercontent.com/pantsbuild/pants/{tag}/src/rust/engine/Cargo.lock"
    download_file(url=cargo_lock_url, output_path=tag_dir / "Cargo.lock")

    rust_toolchain_url = f"https://raw.githubusercontent.com/pantsbuild/pants/{tag}/src/rust/engine/rust-toolchain"
    rust_version = download_toml(url=rust_toolchain_url)["toolchain"]["channel"]

    template_string = Path("template.nix").read_text()
    result = string.Template(template_string).safe_substitute(
        version=args.version,
        args=shlex.join(sys.argv),
        hash="",
        rust_version=rust_version,
    )
    (tag_dir / "default.nix").write_text(result)


if __name__ == "__main__":
    main()
