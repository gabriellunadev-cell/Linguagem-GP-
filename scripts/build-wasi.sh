#!/bin/sh
# Build GP Native VM for WASI preview1. zlib must be built for wasm32-wasi.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CC=${GP_WASI_CC:-clang-18}
SYSROOT=${GP_WASI_SYSROOT:-/usr}
ZLIB=${GP_WASI_ZLIB_PREFIX:-}
[ -n "$ZLIB" ] || { echo "Defina GP_WASI_ZLIB_PREFIX para o prefixo zlib wasm32-wasi" >&2; exit 2; }
[ -f "$SYSROOT/include/wasm32-wasi/unistd.h" ] || { echo "WASI libc não encontrado em $SYSROOT" >&2; exit 2; }
[ -f "$ZLIB/include/zlib.h" ] && [ -f "$ZLIB/lib/libz.a" ] || { echo "zlib WASI não encontrado em $ZLIB" >&2; exit 2; }
command -v "$CC" >/dev/null 2>&1 || { echo "Clang WASI ausente: $CC" >&2; exit 2; }
mkdir -p "$ROOT/build"
cd "$ROOT"
"$CC" --target=wasm32-wasi --sysroot="$SYSROOT" \
    -std=c11 -O2 -Wall -Wextra -Wpedantic \
    -I"$ZLIB/include" gpvm_native.c "$ZLIB/lib/libz.a" -lm \
    -Wl,--initial-memory=33554432 -Wl,--max-memory=536870912 \
    -o build/gpvm-native-wasi.wasm
file build/gpvm-native-wasi.wasm
