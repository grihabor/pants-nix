{
  pkgs ? let
    rust_overlay = import (builtins.fetchTarball "https://github.com/oxalica/rust-overlay/archive/master.tar.gz");
  in
    import <nixpkgs> {
      overlays = [rust_overlay];
    },
}:
pkgs.mkShell {
  nativeBuildInputs = let
    pants = pkgs.callPackage ./pants.nix {};
  in [
    pkgs.python39
    pants
    pkgs.which
    pkgs.xxd
  ];
}
