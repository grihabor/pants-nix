# pants-nix

Nix packages for [pants build system](https://www.pantsbuild.org/).

## Nuances

Official [pants launcher](https://github.com/pantsbuild/scie-pants) can read
`[GLOBAL].pants_version` from `pants.toml`, download the correct version of
pants and run it. On the contrary, this nix package only provides the specific
versions of pants, you need to use the correct version yourself.

Pants can download other tools via
[backends](https://www.pantsbuild.org/2.20/docs/using-pants/key-concepts/backends).
This installation is reproducable by design, but binary packages like `ruff`
probably won't work on nixos. To make them work we need some mechanism to tell
pants to use preinstalled package from nix store.

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
