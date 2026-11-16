#!/bin/sh
# Cross-build the GP C VM for Linux/AArch64 and Windows/x64, then execute
# the ARM64 binary under QEMU against a real GP project bytecode fixture.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
AARCH64_CC=${GP_AARCH64_CC:-aarch64-linux-gnu-gcc}
WINDOWS_CC=${GP_WINDOWS_CC:-x86_64-w64-mingw32-gcc}
QEMU_AARCH64=${GP_QEMU_AARCH64:-qemu-aarch64}
ARM64_SYSROOT=${GP_ARM64_SYSROOT:-/usr/aarch64-linux-gnu}
cd "$ROOT"
command -v "$AARCH64_CC" >/dev/null 2>&1 || { echo "Compilador Linux ARM64 ausente: $AARCH64_CC" >&2; exit 2; }
command -v "$WINDOWS_CC" >/dev/null 2>&1 || { echo "Compilador Windows x64 ausente: $WINDOWS_CC" >&2; exit 2; }
command -v "$QEMU_AARCH64" >/dev/null 2>&1 || { echo "QEMU AArch64 ausente: $QEMU_AARCH64" >&2; exit 2; }
mkdir -p build
"$AARCH64_CC" -std=c11 -O2 -Wall -Wextra -Wpedantic \
    gpvm_native.c -lz -lm -o build/gpvm-native-linux-arm64
"$WINDOWS_CC" -std=c11 -O2 -Wall -Wextra -Wpedantic \
    gpvm_native.c -lpsapi -Wl,-Bstatic -lz -Wl,-Bdynamic -lm \
    -o build/gpvm-native-windows.exe
file build/gpvm-native-linux-arm64 build/gpvm-native-windows.exe
# Compile the project using the production GP module-graph/frontend pipeline.
scripts/gpc-native-project exemplos/modulos/aplicacao.gp build/cross-target-module-smoke.gbc
"$QEMU_AARCH64" -L "$ARM64_SYSROOT" \
    build/gpvm-native-linux-arm64 build/cross-target-module-smoke.gbc \
    > build/cross-target-arm64-smoke.stdout \
    2> build/cross-target-arm64-smoke.stderr
grep -F "Resultado do módulo: 42" build/cross-target-arm64-smoke.stdout
WASI_PYTHON=${GP_WASMTIME_PYTHON:-python3}
if [ -n "${GP_WASI_ZLIB_PREFIX:-}" ] && command -v clang-18 >/dev/null 2>&1 && "$WASI_PYTHON" -c 'import wasmtime' >/dev/null 2>&1; then
    scripts/build-wasi.sh
    scripts/gpc-native-project exemplos/modulos/aplicacao.gp build/cross-target-wasi-smoke.gbc
    "$WASI_PYTHON" scripts/run-gp-wasi.py build/gpvm-native-wasi.wasm build/cross-target-wasi-smoke.gbc \
        --workspace "$ROOT" > build/cross-target-wasi-smoke.stdout
    grep -F "Resultado do módulo: 42" build/cross-target-wasi-smoke.stdout
    echo "GP_WASI_RUNTIME_OK"
else
    echo "SKIP WASI runtime: define GP_WASI_ZLIB_PREFIX e GP_WASMTIME_PYTHON e instala clang-18/wasmtime"
fi
echo "GP_CROSS_TARGETS_OK linux-aarch64-runtime-qemu windows-x64-cross-compiled"
