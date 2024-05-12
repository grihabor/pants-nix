# pants-nix

Nix packages for [pants build system](https://www.pantsbuild.org/).

## Classic nix

Add channel:

```bash
nix-channel --add https://github.com/grihabor/pants-nix/archive/main.tar.gz pants-nix
nix-channel --update
```

Then build the package:

```bash
nix-build '<pants-nix>' -A '"release_2.20.0"'
```

Or install via `nix-env`:

```bash
```

## Nix flakes

Adhoc shell:

```bash
nix shell 'github:grihabor/pants-nix#"release_2.20.0"' --command pants --version
```

Using in a flake:

```nix
  inputs = {
    ...
    pants-nix = {
      url = "github:grihabor/pants-nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };
```

## Development

```bash
nix-build -A '"release_2.20.0"'

nix build '.#"release_2.20.0"'

nix shell '.#"release_2.20.0"' --command pants --version
```
