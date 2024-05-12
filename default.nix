{
  pkgs ? let
    rust_overlay = import (builtins.fetchTarball "https://github.com/oxalica/rust-overlay/archive/master.tar.gz");
  in
    import <nixpkgs> {
      overlays = [rust_overlay];
    },
}: {
  stable = pkgs.callPackage ./stable {};
}
