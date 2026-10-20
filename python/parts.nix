{ inputs, ... }:
let
  # Load workspace from uv.lock
  workspace = inputs.uv2nix.lib.workspace.loadWorkspace {
    workspaceRoot = ../.;
  };

  mkPythonSet = { pkgs, lib, self', members }:
    let
      inherit (pkgs.stdenv.hostPlatform) isLinux isDarwin isx86_64;
      inherit (pkgs.config) cudaSupport;
      inherit (pkgs) cudaPackages;
      python = pkgs.python313;

      cuda_cccl_compat = pkgs.runCommand "cuda-cccl-compat" { } ''
        mkdir -p $out/include
        ln -s ${cudaPackages.cuda_cccl}/include $out/include/cccl
      '';
      cudaLibs = with cudaPackages; [
        cuda_crt
        cuda_cudart
        cuda_cccl
        cuda_cupti
        cuda_nvrtc
        cuda_nvtx
        cudnn
        libcufile
        libcublas
        libcufft
        libcurand
        libcusolver
        libcusparse
        libcusparse_lt
        libnvjitlink
        libnvshmem
        nccl
      ];
      cudaRoot = pkgs.symlinkJoin {
        name = "cuda-merged-exo";
        paths = builtins.concatMap (p: [ (lib.getBin p) (lib.getLib p) (lib.getDev p) ]) (cudaLibs ++ [ cudaPackages.cuda_nvcc cuda_cccl_compat ]);
      };
      exoOverlay = final: prev: {
        # Replace workspace exo_rs with Nix-built wheel.
        # Preserve passthru so mkVirtualEnv can resolve dependency groups.
        # Copy .pyi stub + py.typed marker so basedpyright can find the types.
        exo-rs = pkgs.stdenv.mkDerivation {
          pname = "exo-rs";
          version = "0.1.0";
          src = self'.packages.exo-rs;
          # Install from pre-built wheel
          nativeBuildInputs = [ final.pyprojectWheelHook ];
          dontStrip = true;
          passthru = prev.exo-rs.passthru or { };

          postInstall = ''
            local siteDir=$out/${final.python.sitePackages}/exo_rs
            cp ${inputs.self}/rust/exo_rs/exo_rs.pyi $siteDir/
            touch $siteDir/py.typed
          '';
        };
      };
      buildSystemsOverlay = final: prev:
        lib.optionalAttrs isLinux {
          torch = prev.torch.overrideAttrs (old: {
            nativeBuildInputs = old.nativeBuildInputs ++ lib.optionals cudaSupport [ pkgs.autoAddDriverRunpath ];
            buildInputs = old.buildInputs ++ [ pkgs.zlib ] ++ lib.optionals cudaSupport cudaLibs;
            autoPatchelfIgnoreMissingDeps = lib.optionals cudaSupport [ "libcuda.so.1" ];
          });
          torchaudio = prev.torchaudio.overrideAttrs (old: {
            nativeBuildInputs = old.nativeBuildInputs ++ lib.optionals cudaSupport [ pkgs.autoAddDriverRunpath ];
            buildInputs = old.buildInputs ++ [ final.torch ] ++ lib.optionals cudaSupport [ cudaPackages.cuda_cudart ];
            preFixup = (old.preFixup or "") + ''
              addAutoPatchelfSearchPath "${final.torch}/${final.python.sitePackages}/torch/lib"
            '';
          });
          torchvision = prev.torchvision.overrideAttrs (old: {
            nativeBuildInputs = old.nativeBuildInputs ++ lib.optionals cudaSupport [ pkgs.autoAddDriverRunpath ];
            buildInputs = old.buildInputs ++ [ final.torch ] ++ lib.optionals cudaSupport cudaLibs;
            preFixup = (old.preFixup or "") + ''
              addAutoPatchelfSearchPath "${final.torch}/${final.python.sitePackages}/torch/lib"
            '';
          });
        } // lib.optionalAttrs cudaSupport {
          nvidia-cufile = prev.nvidia-cufile.overrideAttrs (old: {
            nativeBuildInputs = old.nativeBuildInputs ++ [ pkgs.autoAddDriverRunpath ];
            buildInputs = old.buildInputs ++ [ pkgs.rdma-core ];
          });
          nvidia-cusolver = prev.nvidia-cusolver.overrideAttrs (old: {
            nativeBuildInputs = old.nativeBuildInputs ++ [ pkgs.autoAddDriverRunpath ];
            buildInputs = old.buildInputs ++ cudaLibs;
          });
          nvidia-nvshmem-cu13 = prev.nvidia-nvshmem-cu13.overrideAttrs (old: {
            nativeBuildInputs = old.nativeBuildInputs ++ [ pkgs.autoAddDriverRunpath ];
            buildInputs = old.buildInputs ++ [ pkgs.rdma-core pkgs.pmix pkgs.libfabric pkgs.ucx pkgs.openmpi ];
          });
          nvidia-cusparse = prev.nvidia-cusparse.overrideAttrs (old: {
            nativeBuildInputs = old.nativeBuildInputs ++ [ pkgs.autoAddDriverRunpath ];
            buildInputs = old.buildInputs ++ cudaLibs;
          });
          torch-c-dlpack-ext = prev.torch-c-dlpack-ext.overrideAttrs (old: {
            buildInputs = old.buildInputs ++ cudaLibs;
            autoPatchelfIgnoreMissingDeps = [ "libcuda.so.1" ];
            preFixup = "addAutoPatchelfSearchPath '${final.torch}'";
          });

        } // lib.optionalAttrs (cudaSupport && isx86_64) {
          numba = prev.numba.overrideAttrs (old: {
            buildInputs = (old.buildInputs or [ ]) ++ [ pkgs.tbb ];
          });
        };
      pyprojectOverlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
        dependencies = members;
      };
      editableOverlay = workspace.mkEditablePyprojectOverlay {
        # Use environment variable pointing to editable root directory
        root = "$REPO_ROOT";
        members = [ "exo" "exo-bench" ];
      };
      pythonSet = (pkgs.callPackage inputs.pyproject-nix.build.packages {
        inherit python;
      }).overrideScope (
        lib.composeManyExtensions [
          inputs.pyproject-build-systems.overlays.default
          pyprojectOverlay
          exoOverlay
          buildSystemsOverlay
        ]
      );
      venv = name: pythonSet.mkVirtualEnv "${name}-venv" members;
      mkApp =
        let
          libPath = lib.makeLibraryPath (
            [ pkgs.stdenv.cc.cc.lib ] ++ lib.optionals cudaSupport [ cudaRoot ]
          );
        in
        text: name: pkgs.writeShellApplication {
          inherit name;
          text = ''
            LD_LIBRARY_PATH="${libPath}''${LD_LIBRARY_PATH:+:}''${LD_LIBRARY_PATH:-}" exec \
              ${lib.optionalString cudaSupport "nixglhost "} ${text}
          '';
          runtimeEnv = {
            EXO_DASHBOARD_DIR = self'.packages.dashboard;
            EXO_RESOURCES_DIR = inputs.self + /resources;
          };
          runtimeInputs = [
            (venv name)
          ] ++ lib.optionals cudaSupport [ pkgs.nix-gl-host ]
          ++ lib.optionals isDarwin [ pkgs.macmon ];
          passthru = {
            venv = venv name;
            evenv = ((pythonSet.overrideScope editableOverlay).mkVirtualEnv "${name}-evenv" (members // { exo = (members.exo or [ ]) ++ [ "dev" ]; exo-rs = [ ]; })).overrideAttrs (_: {
              venvSkip = [ "lib/python${python.pythonVersion}/site-packages/build_backend.py" ];
            });
          } // lib.optionalAttrs cudaSupport {
            inherit cudaRoot;
          };
        };

    in
    {
      inherit venv;
      mkPythonScript = path: mkApp ''python ${path} "$@"'';
      exo = mkApp ''exo "$@"'' "exo";
    };
in
{
  perSystem =
    { self', pkgs, unfreePkgs, lib, ... }:
    let
      inherit (pkgs.stdenv.hostPlatform) isLinux;
      inherit (mkPythonSet { inherit self' pkgs lib; members = { exo = [ "tinygrad" ]; }; }) exo;

      # Virtual environment with dev dependencies for testing
      testVenv = (mkPythonSet {
        inherit self' pkgs lib; members = {
        exo = [ "dev" "tinygrad" ]; # Include pytest, pytest-asyncio, pytest-env
      };
      }).venv "exo-test";

      mkBenchScript = (mkPythonSet {
        inherit self' pkgs lib; members = {
        exo = [ "tinygrad" ];
        exo-bench = [ ]; # Include pytest, pytest-asyncio, pytest-env
      };
      }).mkPythonScript;

      mkSimplePythonScript = name: path: pkgs.writeShellApplication {
        inherit name;
        runtimeInputs = [ pkgs.python313 ];
        text = ''exec python ${path} "$@"'';
      };
    in
    {
      packages = {
        inherit exo;
        # for running tests in ci
        exo-test-env = testVenv;
        exo-bench = mkBenchScript "exo-bench" (inputs.self + /bench/exo_bench.py);
        exo-eval = mkBenchScript "exo-eval" (inputs.self + /bench/exo_eval.py);
        exo-eval-tool-calls = mkBenchScript "exo-eval-tool-calls" (inputs.self + /bench/eval_tool_calls.py);
        # used by ./tests/run_exo_on.sh
        exo-get-all-models-on-cluster = mkSimplePythonScript "exo-get-all-models-on-cluster" (inputs.self + /tests/get_all_models_on_cluster.py);
      };

      checks = {
        lint = pkgs.runCommand "ruff-lint" { } ''
          export RUFF_CACHE_DIR="$TMPDIR/ruff-cache"
          ${pkgs.ruff}/bin/ruff check ${inputs.self}
          touch $out
        '';

        typecheck = pkgs.runCommand "typecheck" { nativeBuildInputs = [ testVenv ]; } ''
          cd ${inputs.self}
          basedpyright
          touch $out
        '';
      };
    };
}
