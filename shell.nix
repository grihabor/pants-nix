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
    pants-bin = pkgs.callPackage ./. {};
  in [
    pants-bin."release_2.20.1"
    (pkgs.python3.withPackages (ps: [ps.pex]))
  ];
}
