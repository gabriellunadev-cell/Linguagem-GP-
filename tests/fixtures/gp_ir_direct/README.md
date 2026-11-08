# Corpus diferencial GP-IR direto

Gerado em Android ARM64 / Termux no ciclo GP 0.8.33.

Reprodução: make differential-corpus
Verificação: sha256sum -c tests/fixtures/gp_ir_direct/SHA256SUMS

Cada fixture contém fonte .gp, envelope .gp-ir.json, bytecodes .legacy.gbc e .direct.gbc, mais .bootstrap.gbc. Quando há bytecode dourado histórico, ele também é copiado como .golden.gbc.

manifest.json distingue igualdade byte a byte entre encoder direto e encoder legado; igualdade de bytes entre frontend GP e bootstrap Python; igualdade das saídas nas VMs Python/C; origem do GP-IR, incluindo fallback explicitamente marcado para os fixtures cuja sintaxe ainda não é suportada pelo parser GP.

O manifesto não afirma igualdade de IR quando somente a saída foi comparada.
