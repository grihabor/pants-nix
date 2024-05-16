#!/usr/bin/env nix-shell
#! nix-shell -i python3.12 --pure
#! nix-shell -p python312 python312Packages.requests

import argparse
import shlex
import string
import sys
from pathlib import Path

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    args = parser.parse_args()

    template_string = Path("template.nix").read_text()
    result = string.Template(template_string).safe_substitute(
        version=args.version,
        args=shlex.join(sys.argv),
        hash="",
        rust_version="",
    )
    print(result)


if __name__ == "__main__":
    main()
