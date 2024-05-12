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
    nixpkgs = nixpkgs.legacyPackages.x86_64-linux;
    pkgs = import nixpkgs {
      overlays = [(import rust-overlay)];
    };
  in {
    packages.x86_64-linux.default = pkgs.callPackage ./. {};
  };
}
