{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-23.11";
    rust-overlay.url = "github:oxalica/rust-overlay";
  };

  outputs = {
    self,
    nixpkgs,
    rust-overlay,
  }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs {
      inherit system;
      overlays = [rust-overlay.overlays.default];
    };
    pants-bin = pkgs.callPackage ./. {};
  in {
    packages.${system} = with pants-bin; {
      inherit "release_2.20.0" "release_2.20.1";
    };
    devShells.${system}.default = pkgs.mkShell {
      packages = [pants-bin."release_2.20.0"];
    };
  };
}
