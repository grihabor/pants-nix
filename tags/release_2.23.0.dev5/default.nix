# The file is generated by:
#   python -m gen tag 2.23.0.dev5
let
  lib = import ../../common/lib.nix;

  version = "2.23.0.dev5";
  hash = "sha256-yQgdDB9lD6kSLsC24IrMyk4OmaIN++MLi8jGVzaJVZM=";

  # https://raw.githubusercontent.com/pantsbuild/pants/release_2.23.0.dev5/src/rust/engine/rust-toolchain
  rustVersion = "1.80.0";
  cargoLock = {
    # https://raw.githubusercontent.com/pantsbuild/pants/release_2.23.0.dev5/src/rust/engine/Cargo.lock
    lockFile = ./Cargo.lock;
    outputHashes = {
      "deepsize-0.2.0" = "sha256-E73xdzYfpJASps3yz6sjL48Kimy44F2LvxndWzgV3dU=";
      "deepsize_derive-0.1.2" = "sha256-E73xdzYfpJASps3yz6sjL48Kimy44F2LvxndWzgV3dU=";
      "globset-0.4.10" = "sha256-1ucpIHxISBqjvKBAea7o2wSddWiIQr6tBiInk4kg0P0=";
      "ignore-0.4.20" = "sha256-1ucpIHxISBqjvKBAea7o2wSddWiIQr6tBiInk4kg0P0=";
      "lmdb-rkv-0.14.0" = "sha256-yj0+3wRQkAyp5EYOe2WQeUt1D/3cXZK0XrH6qcxhaWw=";
      "lmdb-rkv-sys-0.11.0" = "sha256-c9lKJuE74Xp/sIwSFXFsl2EKffY3oC7Prnglt6p1Ah0=";
      "notify-5.0.0-pre.15" = "sha256-LG6e3dSIqQcHbNA/uYSVJwn/vgcAH0noHK4x3QQdqVI=";
      "prodash-16.0.0" = "sha256-Dkn4BmsF1SnSDAoqW5QkjdzGHEq41y7S20Q/DkRCpVQ=";
      "tree-sitter-dockerfile-0.2.0" = "sha256-UQSdcOWRH1QsFWVgxyx9/E7419Ue5zi79ngWNsWuQBc=";
    };
  };
in
  lib.makePants {
    inherit version hash rustVersion cargoLock;
  }
