{
  fetchFromGitHub,
  python310,
  stdenv,
  protobuf,
  rust-bin,
  makeRustPlatform,
  rustVersion ? "1.75.0",
}: let
  python = python310;
  cargo = rust-bin.stable.${rustVersion}.default;
  rustc = rust-bin.stable.${rustVersion}.default;
  rustPlatform = makeRustPlatform {
    inherit cargo rustc;
  };
  version = "2.20.0";
  src = fetchFromGitHub {
    owner = "pantsbuild";
    repo = "pants";
    rev = "release_${version}";
    hash = "sha256-tzpeYxzDfHbDkGAOCXjQfaLf6834c34zJS3DwahSMwI=";
  };
  pants-engine = stdenv.mkDerivation rec {
    inherit src version;
    pname = "pants-engine";

    cargoDeps = rustPlatform.importCargoLock {
      # curl -L -o Cargo.lock https://raw.githubusercontent.com/pantsbuild/pants/release_2.20.0/src/rust/engine/Cargo.lock
      lockFile = ./Cargo.lock;
      outputHashes = {
        "console-0.15.7" = "sha256-EsUtBySVj2aoGOPBteDKCY7PCehJoqEJXpjOyQlpCf4=";
        "deepsize-0.2.0" = "sha256-E73xdzYfpJASps3yz6sjL48Kimy44F2LvxndWzgV3dU=";
        "globset-0.4.10" = "sha256-1ucpIHxISBqjvKBAea7o2wSddWiIQr6tBiInk4kg0P0=";
        "indicatif-0.17.7" = "sha256-GxQM+y5zL1KW5HmN9UcuS3xNNiZC8neMCyGIoOMleLs=";
        "lmdb-rkv-0.14.0" = "sha256-yj0+3wRQkAyp5EYOe2WQeUt1D/3cXZK0XrH6qcxhaWw=";
        "notify-5.0.0-pre.15" = "sha256-LG6e3dSIqQcHbNA/uYSVJwn/vgcAH0noHK4x3QQdqVI=";
        "prodash-16.0.0" = "sha256-Dkn4BmsF1SnSDAoqW5QkjdzGHEq41y7S20Q/DkRCpVQ=";
      };
    };

    sourceRoot = "${src.name}/src/rust/engine";

    nativeBuildInputs = [
      python
      protobuf
      rustPlatform.cargoSetupHook
    ];

    buildPhase = ''
      export CARGO_BUILD_RUSTC=${rustc}/bin/rustc

      # https://github.com/pantsbuild/pants/blob/release_2.20.0/src/rust/engine/.cargo/config#L4
      export RUSTFLAGS="--cfg tokio_unstable"

      # https://github.com/pantsbuild/pants/blob/release_2.20.0/src/rust/engine/BUILD#L32
      ${cargo}/bin/cargo build \
        --features=extension-module \
        --release \
        -p engine \
        -p client
    '';

    installPhase = ''

      mkdir -p $out/lib/
      cp target/release/libengine.so $out/lib/native_engine.so

      mkdir -p $out/bin/
      cp target/release/pants $out/bin/native_client
    '';
  };
in
  with python.pkgs;
    buildPythonApplication {
      inherit version src;
      pname = "pants";
      pyproject = true;

      build-system = [
        setuptools
      ];

      # curl -L -O https://raw.githubusercontent.com/pantsbuild/pants/release_2.20.0/3rdparty/python/requirements.txt
      dependencies = [
        ansicolors
        packaging
        pex
        psutil
        python-lsp-jsonrpc
        pyyaml
        setproctitle
        setuptools
        toml
        typing-extensions
        fasteners
        pytest
      ];

      # https://github.com/pantsbuild/pants/blob/release_2.20.0/src/python/pants/BUILD#L27-L39
      configurePhase = ''
        cat > setup.py << EOF
        from setuptools import setup, Extension

        setup(
            ext_modules=[Extension(name="dummy_twAH5rHkMN", sources=[])],
        )
        EOF

        cat > pyproject.toml << EOF
        [build-system]
        requires = ["setuptools"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "pants"
        version = "$version"
        requires-python = "==3.10.*"
        dependencies = [
          "packaging",
        ]

        [tool.setuptools]
        include-package-data = true

        [tool.setuptools.packages.find]
        where = ["src/python"]
        include = ["pants", "pants.*"]
        namespaces = false

        [project.scripts]
        pants = "pants.bin.pants_loader:main"

        EOF

        echo ${version} > src/python/pants/_version/VERSION

        cat > MANIFEST.in << EOF
        include src/python/pants/_version/VERSION
        include src/python/pants/engine/internals/native_engine.so
        include src/python/pants/bin/native_client
        recursive-include src/python/pants *.lock *.java *.scala
        EOF

        find src/python -type d -exec touch {}/__init__.py \;
      '';

      prePatch = ''
        patch -p1 --batch -u -i ${./patch.txt}
      '';

      preBuild = ''

        # https://github.com/pantsbuild/pants/blob/release_2.20.0/src/python/pants/engine/internals/BUILD#L28
        cp ${pants-engine}/lib/native_engine.so src/python/pants/engine/internals/

        # https://github.com/pantsbuild/pants/blob/release_2.20.0/build-support/bin/rust/bootstrap_code.sh#L34
        cp ${pants-engine}/bin/native_client src/python/pants/bin/
      '';

      postInstall = ''
        wrapProgram "$out/bin/pants" \
          --set NO_SCIE_WARNING 1 \
          --run ". .pants.bootstrap"
      '';
    }
