let
  makePants = {
    version,
    hash,
    rustVersion,
    cargoLock,
  }: (
    {
      fetchFromGitHub,
      python3,
      stdenv,
      protobuf,
      rust-bin,
      makeRustPlatform,
    }: let
      python = python3;
      cargo = rust-bin.stable.${rustVersion}.default;
      rustc = rust-bin.stable.${rustVersion}.default;
      rustPlatform = makeRustPlatform {
        inherit cargo rustc;
      };
      src = fetchFromGitHub {
        inherit hash;
        owner = "pantsbuild";
        repo = "pants";
        rev = "release_${version}";
      };
      pants-engine = stdenv.mkDerivation rec {
        inherit src version;
        pname = "pants-engine";
        cargoDeps = rustPlatform.importCargoLock cargoLock;

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

          buildInputs = [
            setuptools
          ];

          # curl -L -O https://raw.githubusercontent.com/pantsbuild/pants/release_2.20.0/3rdparty/python/requirements.txt
          propagatedBuildInputs = [
            ansicolors
            chevron
            fasteners
            freezegun
            ijson
            node-semver
            packaging
            pex
            psutil
            pytest
            python-lsp-jsonrpc
            pyyaml
            requests
            setproctitle
            setuptools
            toml
            types-freezegun
            types-pyyaml
            types-requests
            types-setuptools
            types-toml
            typing-extensions
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
            recursive-include src/python/pants *.lock *.java *.scala *.lockfile.txt
            EOF

            find src/python -type d -exec bash -c "if [ -n \"$ls {}/*.py\" ]; then touch {}/__init__.py; fi" \;
          '';

          prePatch = ''
            patch -p1 --batch -u -i ${./patch-process-manager.txt}
            patch -p1 --batch -u -i ${./patch-jar-tool.txt}
            patch -p1 --batch -u -i ${./patch-coursier-fetch.txt}
            patch -p1 --batch -u -i ${./patch-process.txt}
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
              --run "if [ -f .pants.bootstrap ]; then . .pants.bootstrap; fi"
          '';
        }
  );
in {
  inherit makePants;
}
