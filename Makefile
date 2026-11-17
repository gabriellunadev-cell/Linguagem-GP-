PYTHON ?= python3
CLANG ?= $(shell command -v clang || command -v gcc || command -v cc)
FUZZ_ITERATIONS ?= 64
FUZZ_SEED ?= 0x47505632
FUZZ_TIMEOUT ?= 2
FUZZ_REPORT ?= build/fuzz-reports/latest.json

.PHONY: test check validate bootstrap-runner bootstrap-proof run compile native native-vm native-vm-run fuzz-bytecode differential-corpus bridge bytecode-fixtures compile-selfhosted-native compile-selfhosted-native-project cross-native wasi-native targets

test: bytecode-fixtures
	$(PYTHON) -m unittest discover -s tests -v

bytecode-fixtures:
	$(PYTHON) ferramentas/materializar_fixtures_bytecode.py

check:
	$(PYTHON) -m py_compile gp.py gp_compile.py gp_vm.py gp_native.py gp_ide_server.py gpcompiler/*.py tests/*.py ferramentas/*.py scripts/*.py
	sh -n scripts/gpc-native scripts/gpc-native-project scripts/build-native-cross.sh scripts/build-wasi.sh
	$(CLANG) -std=c11 -Wall -Wextra -Wpedantic -fsyntax-only gpvm_native.c
	@if command -v aarch64-linux-gnu-gcc >/dev/null 2>&1; then aarch64-linux-gnu-gcc -std=c11 -Wall -Wextra -Wpedantic -fsyntax-only gpvm_native.c; else echo "SKIP Linux AArch64 syntax: cross compiler unavailable"; fi
	@if command -v x86_64-w64-mingw32-gcc >/dev/null 2>&1; then x86_64-w64-mingw32-gcc -std=c11 -Wall -Wextra -Wpedantic -fsyntax-only gpvm_native.c; else echo "SKIP Windows x64 syntax: cross compiler unavailable"; fi

bootstrap-runner:
	$(PYTHON) ferramentas/gerar_bootstrap_runner.py

# Strict proof consumes the existing seed; it must never rebuild it with Python.
bootstrap-proof: native-vm
	$(PYTHON) ferramentas/provar_bootstrap_gp.py --native-vm build/gpvm-native

validate:
	$(MAKE) check
	$(MAKE) bootstrap-runner
	$(MAKE) differential-corpus
	$(MAKE) test
	$(MAKE) fuzz-bytecode
	cd tests/fixtures/gp_ir_direct && sha256sum -c SHA256SUMS
	$(MAKE) targets
	@if command -v aarch64-linux-gnu-gcc >/dev/null 2>&1 && command -v x86_64-w64-mingw32-gcc >/dev/null 2>&1 && command -v qemu-aarch64 >/dev/null 2>&1; then $(MAKE) cross-native; else echo "SKIP cross-native runtime proof: cross toolchains/QEMU unavailable"; fi
	git diff --check

run:
	$(PYTHON) gp.py exemplos/recursos_02.gp

compile:
	$(PYTHON) gp_compile.py exemplos/bytecode_basico.gp --run

native:
	$(PYTHON) gp_native.py exemplos/native_basico.gp -o build/gp-native-demo --run

native-vm:
	mkdir -p build
	$(CLANG) -std=c11 -O2 -Wall -Wextra gpvm_native.c -lz -lm -o build/gpvm-native

native-vm-run: native-vm
	@test -n "$(BYTECODE)" || (echo "Uso: make native-vm-run BYTECODE=arquivo.gbc"; exit 2)
	./build/gpvm-native "$(BYTECODE)"

fuzz-bytecode: native-vm
	$(PYTHON) ferramentas/fuzz_bytecode.py --native-vm build/gpvm-native --iterations $(FUZZ_ITERATIONS) --seed $(FUZZ_SEED) --timeout $(FUZZ_TIMEOUT) --report $(FUZZ_REPORT)


differential-corpus: native-vm
	$(PYTHON) ferramentas/gerar_corpus_ir.py --native-vm build/gpvm-native


# Compila um unico arquivo com frontend GP, VM C e encoder C sem iniciar Python.
compile-selfhosted-native: native-vm
	@test -n "$(GP_SOURCE)" || (echo "Uso: make compile-selfhosted-native GP_SOURCE=arquivo.gp [GP_OUTPUT=saida.gbc]"; exit 2)
	@if [ -n "$(GP_OUTPUT)" ]; then scripts/gpc-native "$(GP_SOURCE)" "$(GP_OUTPUT)"; else scripts/gpc-native "$(GP_SOURCE)"; fi

# Compila e executa projeto com imports; Python e host de filesystem/orquestracao.
compile-selfhosted-native-project: native-vm
	@test -n "$(GP_SOURCE)" || (echo "Uso: make compile-selfhosted-native-project GP_SOURCE=arquivo.gp [GP_OUTPUT=saida.gbc]"; exit 2)
	@if [ -n "$(GP_OUTPUT)" ]; then scripts/gpc-native-project "$(GP_SOURCE)" "$(GP_OUTPUT)"; else scripts/gpc-native-project "$(GP_SOURCE)"; fi

# Compila Linux ARM64 + Windows x64 e executa a VM ARM64 via QEMU.
cross-native:
	./scripts/build-native-cross.sh

# Compila e executa a VM WASI. Requer GP_WASI_ZLIB_PREFIX e Wasmtime Python.
wasi-native:
	scripts/build-wasi.sh
	scripts/gpc-native-project exemplos/modulos/aplicacao.gp build/wasi-smoke.gbc
	$${GP_WASMTIME_PYTHON:-$(PYTHON)} scripts/run-gp-wasi.py build/gpvm-native-wasi.wasm build/wasi-smoke.gbc --workspace .

# Detecta toolchains e evidências; alvos ausentes são reportados como não verificados.
targets:
	$(PYTHON) ferramentas/verificar_alvos.py

# Inicia a API local consumida pelo GP Programinha.
bridge:
	$(PYTHON) gp_ide_server.py
