#!/usr/bin/env nix-shell
#! nix-shell -i python3.12 --pure
#! nix-shell -p python312 git nix python312Packages.requests python312Packages.aiofiles nix-prefetch-git

from .lib import main

if __name__ == "__main__":
    main()
