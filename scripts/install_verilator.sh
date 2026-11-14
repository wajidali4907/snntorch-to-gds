#!/usr/bin/env bash
# Build Verilator from source into ./tools/verilator (no sudo needed).
set -euo pipefail
VER=${VERILATOR_VERSION:-v5.030}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="$ROOT/tools/verilator"
SRC="$ROOT/tools/src/verilator"
if [ -x "$PREFIX/bin/verilator" ]; then echo "verilator already at $PREFIX"; exit 0; fi
mkdir -p "$ROOT/tools/src"
[ -d "$SRC" ] || git clone --depth 1 --branch "$VER" https://github.com/verilator/verilator "$SRC"
cd "$SRC"
autoconf
./configure --prefix="$PREFIX"
make -j"$(nproc)"
make install
"$PREFIX/bin/verilator" --version
