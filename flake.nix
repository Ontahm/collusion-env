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

      # Security (SECURITY.md). uv >= 0.13.4 is required by the eMudhra/emSign CA advisory (Oct 2026);
      # nixpkgs' stable channel has an older uv, so the shell uses Astral's official static binary,
      # pinned by the SHA-256 Astral publishes with the release.
      uv-bin = pkgs.stdenvNoCC.mkDerivation rec {
        pname = "uv";
        version = "0.13.5";
        src = pkgs.fetchurl {
          url = "https://github.com/astral-sh/uv/releases/download/${version}/uv-x86_64-unknown-linux-musl.tar.gz";
          hash = "sha256-V++dnMsB+xvZmN+ZWw3SIbUvfXhB++qT8tRGO/Yft6k=";
        };
        sourceRoot = "uv-x86_64-unknown-linux-musl";
        dontFixup = true;                  # a static binary: nothing to patch
        installPhase = "install -Dm755 -t $out/bin uv uvx";
      };
      # The pinned certificate bundle without the eMudhra/emSign roots (all four: a superset of every
      # certifi decision so far; none of the services this project uses depends on them). Used by
      # curl, git and OpenSSL in the shells through the variables below.
      cacert-safe = pkgs.cacert.override {
        blacklist = [ "emSign Root CA - G1" "emSign ECC Root CA - G3" "emSign Root CA - C1" "emSign ECC Root CA - C3" ];
      };
      cert-bundle = "${cacert-safe}/etc/ssl/certs/ca-bundle.crt";
      cert-env = {
        NIX_SSL_CERT_FILE = cert-bundle;
        CURL_CA_BUNDLE = cert-bundle;
      };
      # `nix develop` drops SSL_CERT_FILE from a shell's environment (Nix sets it for builds), so it
      # is exported when the shell starts instead.
      cert-hook = ''
        export SSL_CERT_FILE="${cert-bundle}" NIX_SSL_CERT_FILE="${cert-bundle}" CURL_CA_BUNDLE="${cert-bundle}"
      '';
      python-env = cert-env // {
        # uv must use this Python, never download its own (it would not run on NixOS).
        UV_PYTHON = "${pkgs.python311}/bin/python3.11";
        UV_PYTHON_DOWNLOADS = "never";
        # Prebuilt wheels (numpy, scipy, matplotlib) need these libraries. The Makefile sets
        # LD_LIBRARY_PATH to this value for Python commands only.
        ENV_PY_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib pkgs.zlib ];
      };
      base = [ pkgs.python311 uv-bin pkgs.git pkgs.gnumake pkgs.curl ];
    in
    {
      devShells.${system} = {
        # Everyday shell: Python, uv, make. Light: no CUDA.
        default = pkgs.mkShell {
          packages = base;
          env = python-env;
          shellHook = cert-hook + ''
            echo "collusion-env shell: $(python3.11 --version), $(uv --version). Run 'make' to list commands."
            echo "certificates: $SSL_CERT_FILE (emSign roots distrusted, SECURITY.md)"
          '';
        };
        # Shell with the local model server (llama.cpp built with CUDA). `make local-server` enters it
        # by itself when llama-server is not on the PATH.
        server = pkgs.mkShell {
          packages = base ++ [ llama-cpp-cuda ];
          env = python-env;
          shellHook = cert-hook + ''
            echo "collusion-env server shell: $(llama-server --version 2>&1 | head -n 1)"
          '';
        };
      };
    };
}
