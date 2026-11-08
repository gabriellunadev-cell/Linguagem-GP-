PYTHON ?= python3
CLANG ?= clang
FUZZ_ITERATIONS ?= 64
FUZZ_SEED ?= 0x47505632
FUZZ_TIMEOUT ?= 2
FUZZ_REPORT ?= build/fuzz-reports/latest.json

.PHONY: test check validate bootstrap-runner bootstrap-proof run compile native native-vm native-vm-run fuzz-bytecode differential-corpus bridge bytecode-fixtures

test: bytecode-fixtures
	$(PYTHON) -m unittest discover -s tests -v

bytecode-fixtures:
	$(PYTHON) ferramentas/materializar_fixtures_bytecode.py

check:
	$(PYTHON) -m py_compile gp.py gp_compile.py gp_vm.py gp_native.py gp_ide_server.py gpcompiler/*.py tests/*.py ferramentas/*.py
	$(CLANG) -std=c11 -Wall -Wextra -Wpedantic -fsyntax-only gpvm_native.c

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


# Inicia a API local consumida pelo GP Programinha.
bridge:
	$(PYTHON) gp_ide_server.py
