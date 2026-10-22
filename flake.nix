{
  description = "collusion-env: Colosseum Jira collusion environment (Python 3.11 + uv; llama.cpp server)";

  # Pinned by flake.lock (commit it). The pinned revision's CUDA build of llama.cpp is already in
  # this machine's Nix store, so the `server` shell does not compile it again.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config = {
          allowUnfree = true;            # CUDA is unfree
          cudaCapabilities = [ "7.5" ];  # RTX 2060 (Turing). Change for another GPU (e.g. "8.6", "8.9").
        };
      };
      llama-cpp-cuda = pkgs.llama-cpp.override { cudaSupport = true; };
      python-env = {
        # uv must use this Python, never download its own (it would not run on NixOS).
        UV_PYTHON = "${pkgs.python311}/bin/python3.11";
        UV_PYTHON_DOWNLOADS = "never";
        # Prebuilt wheels (numpy, scipy, matplotlib) need these libraries. The Makefile sets
        # LD_LIBRARY_PATH to this value for Python commands only.
        ENV_PY_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib pkgs.zlib ];
      };
      base = [ pkgs.python311 pkgs.uv pkgs.git pkgs.gnumake pkgs.curl ];
    in
    {
      devShells.${system} = {
        # Everyday shell: Python, uv, make. Light: no CUDA.
        default = pkgs.mkShell {
          packages = base;
          env = python-env;
          shellHook = ''
            echo "collusion-env shell: $(python3.11 --version), $(uv --version). Run 'make' to list commands."
          '';
        };
        # Shell with the local model server (llama.cpp built with CUDA). `make local-server` enters it
        # by itself when llama-server is not on the PATH.
        server = pkgs.mkShell {
          packages = base ++ [ llama-cpp-cuda ];
          env = python-env;
          shellHook = ''
            echo "collusion-env server shell: $(llama-server --version 2>&1 | head -n 1)"
          '';
        };
      };
    };
}
