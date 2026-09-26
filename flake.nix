{
  description = "Algorithmic trading harness: daily-bar backtesting, strategy comparison, Alpaca execution";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        lib = pkgs.lib;
        python = pkgs.python312;
      in
      {
        # Nix pins the toolchain (Python, uv, ruff, just); uv pins the Python
        # dependency graph via uv.lock. `nix develop` (or direnv) drops you into
        # a shell with a synced .venv on any Linux or macOS machine.
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.uv
            pkgs.ruff
            pkgs.just
            pkgs.jq
          ];

          env =
            {
              UV_PYTHON = "${python}/bin/python3";
              UV_PYTHON_DOWNLOADS = "never";
              UV_PROJECT_ENVIRONMENT = ".venv";
            }
            // lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
              # manylinux wheels (numpy, pyarrow, ...) expect these on NixOS.
              LD_LIBRARY_PATH = lib.makeLibraryPath [
                pkgs.stdenv.cc.cc.lib
                pkgs.zlib
              ];
            };

          shellHook = ''
            uv sync --frozen --quiet
            source .venv/bin/activate
            echo "trader devshell: $(python --version), uv $(uv --version | cut -d' ' -f2). Run 'just' for tasks."
          '';
        };

        formatter = pkgs.nixfmt-rfc-style;
      }
    );
}
