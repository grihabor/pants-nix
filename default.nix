{pkgs ? import <nixpkgs> {}}: {
  stable = pkgs.callPackage ./stable {};
}
