# ENGINEERING_STATUS — Gabriel Programming

Atualizado em: 2026-11-08
Ambiente: Android / Termux / ARM64
Repositório: `$HOME/gabriel-luna-gp`
Branch de evolução no GitHub: `feature/gp-bridge-v0.2`

## Integração GP Programinha — estado atual

- O repositório da linguagem mantém o compilador GP 0.8.52 e agora disponibiliza a GP Bridge 0.2 como camada HTTP local.
- Endpoints de projeto: `POST /api/compile-project` e `POST /api/run-project`; os endpoints individuais rejeitam imports.
- Cada projeto é validado antes da escrita no workspace temporário: até 128 arquivos, 4 MiB por fonte e 16 MiB de fontes somadas.
- Imports absolutos, caminhos externos, backslashes e módulos ausentes são rejeitados; a validação percorre o grafo de imports alcançável, inclusive aninhado.
- Serviço limitado a `127.0.0.1`, com verificação Host/CORS, allowlist de origem local e ambiente mínimo para o processo compilador.
- Projeto de integração: https://github.com/gabriellunadev-cell/Linguagem-GP-/pull/1
- IDE separada: https://github.com/gabriellunadev-cell/Gp-ai-programacao/pull/1

### Validação mais recente — GitHub Actions

- Runner: Ubuntu Linux x64, Python 3.12; resultado não deve ser confundido com validação local Termux/Android.
- `make validate`: sucesso no commit `895303f0552697fc1e7ff801de0952dea1399cf2` (08/11/2026).
- 264 testes aprovados em 26,087 s.
- Corpus diferencial: 6/6 casos em cada uma das seis dimensões (`frontend_supported`, `direct_legacy_exact`, `frontend_bootstrap_exact`, `native_runner_exact`, `native_encoder_exact`, `python_c_semantic`).
- Fuzz determinístico: 64 iterações, 38 rejeições, 26 aceitas/executadas, zero divergências.
- Testes HTTP reais: health 200; execução de projeto modular 200 com saída `HTTP: 42`; import externo 400; arquivo único com import 400; preflight CORS Vite 204.
- SHA-256 do corpus GP-IR e `git diff --check` aprovados.

### Testes específicos da Bridge

- 20 testes unitários de payload, limites, caminhos relativos, import aninhado, bloqueio de traversal e execução real.
- 6 testes de HTTP real contra servidor loopback: health, compile-project, run-project, rejeições de imports e preflight CORS de `http://localhost:5173`.
- O processo filho do compilador recebe ambiente mínimo em vez de herdar todas as variáveis do servidor.
## Estado confirmado

- Encoder GGPC v2 nativo em C implementado e integrado ao CLI auto-hospedado quando a VM C é selecionada.
- Entrada GP-IR v1 validada, campos de funções normalizados para serialização canônica, envelope GGPC v2 produzido com zlib/CRC32 e gravação atômica.
- O caminho de compilação self-hosted usa `validate_canonical_ir` para validação; não chama mais o encoder Python apenas para validar.
- Encoder Python permanece como referência de compatibilidade e oráculo diferencial; adaptador e hidratação Python continuam presentes.
- Encoder C e encoder Python produziram bytes idênticos nos seis casos do corpus.

## Snapshot histórico de validação local no Android ARM64

Os números abaixo documentam um ciclo local anterior e não substituem a validação GitHub Actions mais recente registrada acima.

### make validate
- Exit code 0.
- 194 testes aprovados.
- Corpus diferencial: 6/6 casos.
- Fuzz determinístico: 64 iterações; 37 rejeições; 27 execuções aceitas; zero divergências.
- Hashes dos fixtures aprovados.
- `git diff --check` aprovado.

### make bootstrap-proof
- Exit code 0; duração observada: 590,18 s.
- Estágios nativos executados na VM C: N → N+1 e N+1 → N+2.
- N: `4925c7dcb756a3b3c4f5eed396ce5a92198f0a6930b0952e84990e0d94ed0e54`.
- N+1: `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`.
- N+2: `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`.
- N+1 == N+2: verdadeiro; ambos com 23.037 bytes.
- Prova registrada em `artifacts/bootstrap/proof/proof.json`; relatórios em `memory_n_to_n1.json` e `memory_n1_to_n2.json`.

## Memória observada no bootstrap

Limite: 268.435.456 bytes (256 MiB).

| Métrica | N → N+1 | N+1 → N+2 |
|---|---:|---:|
| Heap total pico | 59.533.173 B (56,78 MiB) | 60.000.755 B (57,22 MiB) |
| Heap total vivo | 43.179.550 B | 43.646.739 B |
| RSS atual | 70.115.328 B | 70.512.640 B |
| RSS de pico | 71.974.912 B (68,64 MiB) | 72.372.224 B (69,00 MiB) |

Os picos de cada grupo de alocação são máximos independentes e não devem ser somados. O total global rastreado é a métrica de controle do teto.

## Arquivos alterados no ciclo observado

- `gpvm_native.c`, `gp_compile.py`
- `ferramentas/gerar_corpus_ir.py`, `ferramentas/provar_bootstrap_gp.py`
- `tests/test_compiler.py`, `tests/test_selfhosted_ir.py`
- fixtures/manifests em `tests/fixtures/gp_ir_direct/`
- `artifacts/bootstrap/manifest.json` e `artifacts/bootstrap/proof/*`
- `CHANGELOG.md`, `docs/ROADMAP.md`

O estado Git foi observado na branch `master`, com alterações locais não commitadas. Nenhum commit, push, tag ou release foi criado. Dois diretórios antigos `linguagem/.gp_selfhosted_native_runner_*` foram encontrados; não foram removidos porque sua descartabilidade não foi confirmada.

## Limites importantes

- O bootstrap N → N+1 → N+2 demonstra reprodutibilidade do frontend bootstrap no escopo atual, não autocompilação integral do toolchain.
- O artefato inicial ainda é construído pelo bootstrap Python.
- A hidratação/materialização de GP-IR para objetos runtime continua no host Python.
- Encoder Python e adaptador continuam como referência/fallback; não remover sem cobertura ampliada.
- GP permanece experimental. Não declarar versão 1.0, produção ou independência integral.

## Próxima sequência

1. Auditar limites de entrada/saída do encoder C, parsing JSON, UTF-8, valores inteiros, memória e falhas de alocação.
2. Testar entradas adversariais, reordenação de propriedades, Unicode, arrays e schemas.
3. Verificar gravação atômica, limpeza de temporários e comportamento em falha de escrita.
4. Ampliar testes diferenciais e o corpus além dos seis casos atuais.
5. Separar a hidratação de GP-IR da camada CLI e mover a materialização de funções, parâmetros e schemas gradualmente para GP, mantendo o oráculo Python até equivalência comprovada.

## Política de mudanças

Nenhum commit, push, tag ou release foi criado. Nenhuma infraestrutura GPTV foi alterada.


## Revisão de segurança do encoder — 2026-11-07

- Corrigida a criação do arquivo temporário em `write_binary_atomic`: `mkstemp` usa criação exclusiva e modo 0600 em vez de caminho previsível `.tmp.<pid>` com `fopen("wb")`.
- Escrita usa `write` em loop, retenta `EINTR`, executa `fsync`, verifica `close` e publica com `rename`; temporário criado é removido se a publicação falhar.
- `clang -std=c11 -O2 -Wall -Wextra -Wpedantic gpvm_native.c -lz -lm` aprovado.
- Cinco testes focados do encoder aprovados, incluindo saída 0600 e remoção de temporário em falha de rename.
- A validação integral após essa alteração ainda está pendente.
## Revisão adicional de parsing JSON — 2026-11-07

- A função `json_string` foi otimizada de `malloc(n * 4 + 1)` para `malloc(n + 1)`: cada escape JSON consome pelo menos tantos bytes de entrada quanto os bytes UTF-8 emitidos, e texto UTF-8 bruto mantém o mesmo comprimento.
- Validado pelo encoder nativo com GP-IR contendo Unicode escapado, comparando o programa decodificado com a referência.
- Testes novos confirmam rejeição de chave duplicada aninhada e entrada contendo byte `0xFF` inválido.
- Os três testes focados passaram; a suíte integral desta revisão está pendente.
## Limites de entrada do encoder — 2026-11-07

- Novo teste cria arquivo esparso com 64 MiB + 1 byte e confirma rejeição antecipada; nenhum GGPC é produzido.
- Novo teste fornece JSON truncado e confirma rejeição sem publicar saída.
- Os dois testes direcionados passaram em 2,601 s; validação integral posterior está pendente.
## Validação integral final — 2026-11-07

- `make validate`: exit code 0; log persistido em `build/validate-0.8.43.log`; código de saída em `build/validate-0.8.43.exit`.
- `make check`: py_compile Python e `clang -std=c11 -Wall -Wextra -Wpedantic -fsyntax-only gpvm_native.c` aprovados.
- Corpus diferencial: `CORPUS_OK cases=6`; os seis casos passaram em frontend supported, direct/legacy, frontend/bootstrap, runner nativo, encoder nativo e semântica Python/C.
- Suíte: 201 testes aprovados em 44,629 s.
- Fuzz: 64 iterações; seed 0x47505632; 37 rejeições; 27 execuções aceitas; zero divergências.
- SHA-256 de todos os artefatos em `tests/fixtures/gp_ir_direct/SHA256SUMS`: aprovados.
- `git diff --check`: aprovado.
- Os números anteriores de 194/196 testes foram substituídos por esta validação final de 201 testes.
## GP 0.8.44 — caminho nativo sem materialização JSON Python — 2026-11-07

- `gp_compile.py`: introduzido `_raw_json_output` no executor self-hosted e `encode_canonical_ir_native_json`; o CLI nativo passa a encaminhar o JSON bruto do frontend ao encoder C sem `json.loads`, `validate_canonical_ir` ou `json.dumps` no caminho normal.
- APIs existentes preservadas: `compile_source_selfhosted_document` continua retornando dict validado e `compile_source_selfhosted` continua retornando `IRProgram` para compatibilidade.
- `gpvm_native.c`: valida que cada instrução GP-IR contém exatamente `op` e `args`, rejeitando propriedades extras como o validador Python canônico.
- CLI: `--runner-vm native` usa automaticamente `build/gpvm-native` tanto para o runner quanto para encoder, mesmo sem `--native-vm`; testado também com `--dump-ir`.
- Regressões adicionais cobrem bypass de hidratação, equivalência byte a byte e rejeição de propriedade extra em instrução.
- `make validate`: exit 0; 203 testes em 54,715 s; corpus 6/6 nas seis dimensões; fuzz 64 (37 rejeições, 27 aceitos/executados, 0 divergências); hashes e `git diff --check` aprovados.
- Relatório persistido: `build/validate-0.8.44.log`; código de saída `build/validate-0.8.44.exit` = 0.
- A prova N → N+1 → N+2 foi repetida após esta revisão da VM/host e terminou com sucesso; os hashes N+1/N+2 e as métricas completas estão registrados na seção abaixo.

## Reprova do bootstrap após a rota JSON bruta — 2026-11-07

- make bootstrap-proof: exit code 0; saída BOOTSTRAP_PROOF_OK.
- N: 4925c7dcb756a3b3c4f5eed396ce5a92198f0a6930b0952e84990e0d94ed0e54.
- N+1 e N+2: 20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399; igualdade confirmada; 23.037 bytes por artefato.
- N → N+1: heap total pico 55222251 B (52.66 MiB); heap vivo 38982472 B; RSS atual 66363392 B; RSS pico 68231168 B (65.07 MiB).
- N+1 → N+2: heap total pico 55415537 B (52.85 MiB); heap vivo 39175413 B; RSS atual 66584576 B; RSS pico 68435968 B (65.27 MiB).
- Teto de heap rastreado: 268.435.456 B (256 MiB); ambos os estágios ficaram dentro do limite.
- Relatório consolidado em artifacts/bootstrap/proof/proof.json, relatórios separados em memory_n_to_n1.json e memory_n1_to_n2.json; log em build/bootstrap-proof-0.8.44.log.
- Dois diretórios antigos de runner em linguagem/.gp_selfhosted_native_runner_* continuam no workspace; não foram removidos porque já existiam antes desta execução e não foram demonstrados como descartáveis.


## GP 0.8.45 — contrato de schema estrito entre Python/C — 2026-11-07

- gpcompiler/ir.py: validate_canonical_ir exige exatamente cinco campos no envelope GP-IR v1.
- gpcompiler/bytecode.py: decoder exige a forma normativa de program, função e instrução; program.ir_version continua opcional somente para compatibilidade histórica v2, sem aceitar uma propriedade desconhecida em seu lugar.
- gpvm_native.c: loader C exige 4 campos no program histórico sem ir_version ou 5 campos com ir_version explícito; os campos obrigatórios são conferidos; cada função tem exatamente 3 campos e cada instrução exatamente 2.
- Propriedades desconhecidas continuam permitidas somente no objeto raiz do envelope GGPC v2, conforme BYTECODE_V2_SPEC; não são permitidas dentro de program, função, instrução ou schema.
- Quatro testes focados passaram: rejeição diferencial Python/C de propriedades extras, aceitação histórica sem ir_version em Python/C, rejeição de propriedades extras no root do encoder e em função.
- Compilação nativa com -Wall -Wextra -Wpedantic e py_compile aprovadas.
- `make validate`: exit 0; 207 testes em 76,734 s; corpus 6/6 em todas as comparações; fuzz 64 (37 rejeições, 27 execuções aceitas, zero divergências); hashes e `git diff --check` aprovados. Log: `build/validate-0.8.45-rerun.log`.
- `make bootstrap-proof`: exit 0; `BOOTSTRAP_PROOF_OK`; N+1 e N+2 têm SHA-256 idêntico `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes cada. Log: `build/bootstrap-proof-0.8.45.log`.
- Memória N → N+1: heap pico 55.222.251 B, heap vivo 38.982.472 B, RSS atual 66.465.792 B, RSS pico 68.321.280 B. N+1 → N+2: heap pico 55.415.537 B, heap vivo 39.175.413 B, RSS atual 66.592.768 B, RSS pico 68.448.256 B. Teto de heap: 268.435.456 B (256 MiB).
- Provas persistidas em `artifacts/bootstrap/proof/proof.json`, `memory_n_to_n1.json` e `memory_n1_to_n2.json`.


## GP 0.8.46 — encoder nativo com entrada GP-IR por stdin — 2026-11-07

- `gpvm_native.c`: `read_json_stdin` lê em blocos com crescimento limitado a 64 MiB, trata EINTR, detecta excesso de limite, rejeita entrada vazia, NUL e UTF-8 inválido. `read_json_file("-")` encaminha a leitura para stdin; caminho de arquivo tradicional permanece intacto.
- `gp_compile.py`: `_encode_gp_ir_native_json` envia os bytes serializados via `subprocess.run(input=...)`. Não materializa mais `input.gp-ir.json`; o diretório temporário contém apenas o bytecode de saída.
- `tests/test_compiler.py`: regressões verificam stdin válido com saída idêntica byte a byte à referência Python, e rejeição de stdin vazio, inválido em UTF-8 ou com NUL, sempre sem arquivo de saída.
- Testes direcionados: 4 aprovados, incluindo a rota nativa bruta sem hidratação de IR Python.
- Compilação C com `-Wall -Wextra -Wpedantic` e `py_compile` aprovadas.
- Testes direcionados de stdin passaram sob `-W error::ResourceWarning`: entrada válida, stdin vazio, UTF-8 inválido, NUL e payload acima de 64 MiB; nenhum aviso de recurso ou bytecode parcial.
- `make validate`: exit code 0; 210 testes em 56,193 s; corpus diferencial 6/6 em todas as dimensões; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes de fixtures e `git diff --check` aprovados.
- Log final: `build/validate-0.8.46-final.log`; código de saída `build/validate-0.8.46-final.exit` = 0; relatório de fuzz: `build/fuzz-reports/latest.json`.
- `make bootstrap-proof`: exit code 0; `BOOTSTRAP_PROOF_OK`; N+1 e N+2 têm SHA-256 idêntico `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes cada.
- Métricas bootstrap registradas: N → N+1 heap pico 55.222.251 B, heap vivo 38.982.472 B, RSS pico 68.399.104 B; N+1 → N+2 heap pico 55.415.537 B, heap vivo 39.175.413 B, RSS pico 68.435.968 B. Ambos abaixo do teto de heap de 256 MiB.
- Relatórios: `artifacts/bootstrap/proof/proof.json`, `memory_n_to_n1.json` e `memory_n1_to_n2.json`; log `build/bootstrap-proof-0.8.46.log`.

## GP 0.8.47 — transporte direto da fonte para a VM nativa

- `gpvm_native.c`: implementado `load_host_source_stdin`, com crescimento geométrico limitado a 16 MiB, tratamento de EINTR, leitura de byte extra para detectar excesso, validação UTF-8 e rejeição de NUL. `load_host_source` encaminha `-` para stdin e mantém o caminho de arquivo.
- `gp_compile.py`: frontend self-hosted nativo envia a fonte via `subprocess.run(input=source, text=True, encoding="utf-8")`; eliminado `source-input.txt`. O bytecode do runner continua em diretório temporário.
- Testes novos: stdin com Unicode/multilinha e vazio; rejeição de UTF-8 inválido, NUL e fonte acima de 16 MiB. Teste existente confirma a compatibilidade do arquivo.
- `py_compile` aprovado; compilação C com `clang -std=c11 -O2 -Wall -Wextra -Wpedantic` aprovada.
- Teste de integração `test_self_hosted_frontend_runner_matches_on_native_vm`: aprovado.
- `make validate`: exit 0; 213 testes em 51,732 s; corpus diferencial 6/6; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes das fixtures e `git diff --check` aprovados.
- Evidências: `build/validate-0.8.47.log`, `build/validate-0.8.47.exit` = 0 e `build/fuzz-reports/latest.json`.
- Limite honesto: Python ainda orquestra o frontend e a execução; esta mudança remove somente a materialização da fonte-alvo em arquivo. Não declarar autonomia completa nem independência de Python.

## GP 0.8.49 — publicação atômica do bytecode pelo CLI

- `gp_compile.py`: adicionada `write_bytecode_atomic`. Valida bytes não vazios, cria temporário exclusivo no mesmo diretório do destino, grava e sincroniza o arquivo, fecha, substitui com `os.replace` e sincroniza o diretório.
- Se a criação, gravação ou substituição falhar antes do replace, o destino anterior permanece intacto e o temporário é removido. Arquivos temporários recebem permissões restritivas por `mkstemp`.
- O CLI principal passou a usar a função atômica em vez de `Path.write_bytes`; encoder C já utilizava `mkstemp` + fsync + rename.
- Testes focados: publicação e substituição completas; falha simulada de `os.replace` preserva bytes antigos e remove temporário; bytes vazios são rejeitados. Os três passaram sob `-W error::ResourceWarning`.
- `python -m py_compile gp_compile.py tests/test_compiler.py` aprovado.
- `make validate`: exit 0; 219 testes em 49,356 s; corpus diferencial 6/6; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes das fixtures e `git diff --check` aprovados.
- Evidências: `build/validate-0.8.49.log`, `build/validate-0.8.49.exit` = 0 e `build/fuzz-reports/latest.json`.
- `make bootstrap-proof`: exit 0; `BOOTSTRAP_PROOF_OK`; N+1 e N+2 idênticos, SHA-256 `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes cada.
- Limite: o rename atômico garante que leitores vejam o arquivo antigo ou o novo completo; se o fsync do diretório falhar depois do replace, o novo arquivo já pode estar visível, mas a durabilidade do nome não é confirmada. Não afirmar rollback após a etapa de replace.

- `make bootstrap-proof`: exit 0; `BOOTSTRAP_PROOF_OK`; N+1 e N+2 idênticos, SHA-256 `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes cada.
- Métricas N → N+1: heap pico 55.347.618 B, heap vivo 39.107.839 B, RSS atual 66.387.968 B, RSS pico 68.251.648 B. N+1 → N+2: heap pico 55.540.904 B, heap vivo 39.300.780 B, RSS atual 66.519.040 B, RSS pico 68.378.624 B. Teto de heap 268.435.456 B (256 MiB), ambos dentro do limite.
- Relatórios: `build/bootstrap-proof-0.8.49.log`, `build/bootstrap-proof-0.8.49.exit` = 0, `artifacts/bootstrap/proof/proof.json`, `memory_n_to_n1.json`, `memory_n1_to_n2.json`.

## GP 0.8.50 — módulos locais aninhados e limites do grafo

- `gp_compile.py`: `_expand_modules_for_selfhosted` agora percorre recursivamente o grafo de módulos locais, preserva a ordem de dependências e constrói namespaces hierárquicos para módulos e chamadas internas.
- `gpcompiler/modules.py`: o compilador de referência recebeu a mesma expansão recursiva e a mesma política de limites, mantendo equivalência semântica.
- Segurança do grafo: rejeita ciclos, aliases duplicados, profundidade acima de 32, mais de 128 módulos, arquivo individual acima de 4 MiB e grafo acima de 16 MiB.
- Testes direcionados: 7 aprovados para paridade, ciclos, aliases duplicados, limite de profundidade e execução aninhada pela VM C. Teste isolado da string JSON escapada também passou após correção do fixture.
- `py_compile` e compilação C passaram; `git diff --check` passou.
- `make validate`: exit 0; 226 testes em 51,667 s; corpus diferencial 6/6 em todas as dimensões; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes de fixtures aprovados.
- Evidências da suíte: `build/validate-0.8.50-final.log`, `build/validate-0.8.50-final.exit` = 0 e `build/fuzz-reports/latest.json`.
- `make bootstrap-proof`: exit 0; `BOOTSTRAP_PROOF_OK`; N+1 e N+2 são byte a byte idênticos, SHA-256 `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes cada.
- Métricas N → N+1: heap pico 55.347.618 B, heap vivo 39.107.839 B, RSS pico 68.341.760 B. N+1 → N+2: heap pico 55.540.904 B, heap vivo 39.300.780 B, RSS pico 68.476.928 B. Ambos abaixo do teto de heap de 268.435.456 B (256 MiB).
- Relatórios de bootstrap: `build/bootstrap-proof-0.8.50.log`, `build/bootstrap-proof-0.8.50.exit` = 0, `artifacts/bootstrap/proof/proof.json`, `memory_n_to_n1.json` e `memory_n1_to_n2.json`.
- Limite honesto: o estágio N ainda declara `Python bootstrap compile_source`; a prova confirma N → N+1 → N+2 usando a VM C nos estágios do runner, mas não prova construção inicial independente do host Python.


## GP 0.8.51 — hardening do carregamento de módulos — 2026-11-08

- `gpcompiler/modules.py`: adicionados `resolve_module_path` e `read_module_source`; leitura em modo binário limitada a 4 MiB + 1 byte para detectar excesso, com contagem dos bytes efetivamente lidos e decodificação UTF-8 estrita.
- Ambos os compiladores passaram a aplicar a mesma política ao carregamento de módulos e ao limite acumulado de 16 MiB por grafo; os limites existentes de 32 níveis e 128 módulos permanecem.
- Erros de arquivo ausente, caminho inválido, UTF-8 inválido e falha de acesso são traduzidos para diagnósticos GP. `errno.ELOOP` recebe diagnóstico específico para ciclo de link simbólico.
- Testes de módulos: 18 regressões cobrem limites reais individual/acumulado, arquivos especiais, links simbólicos cíclicos na raiz e em imports aninhados, paridade, ciclos de importação, aliases e profundidade.

### Validação integral — 2026-11-08

- `make validate`: exit code 0; 231 testes em 48,620 s.
- `make check`: `py_compile` e análise sintática C com `-Wall -Wextra -Wpedantic` aprovadas.
- Corpus diferencial: 6/6 nas seis dimensões — frontend suportado, legado/direto, bootstrap, runner nativo, encoder nativo e semântica Python/C.
- Fuzz: 64 iterações; seed `0x47505632`; 37 rejeições; 27 aceitos e executados; zero divergências.
- SHA-256 das fixtures aprovados; `git diff --check` aprovado.
- Log final: `build/validate-0.8.51-final.log`; código: `build/validate-0.8.51-final.exit` = 0.

### Bootstrap nativo — 2026-11-08

- `make bootstrap-proof`: exit code 0; duração total observada 346,16 s; `BOOTSTRAP_PROOF_OK`.
- Estágio N: SHA-256 `4925c7dcb756a3b3c4f5eed396ce5a92198f0a6930b0952e84990e0d94ed0e54`, 23.014 bytes.
- N+1 e N+2: SHA-256 idêntico `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes por artefato.
- Heap pico: 55.347.618 B em N→N+1 e 55.540.904 B em N+1→N+2; teto 268.435.456 B (256 MiB). RSS pico: 68.431.872 B e 68.505.600 B, respectivamente.
- Relatório: `artifacts/bootstrap/proof/proof.json`; logs finais: `build/bootstrap-proof-0.8.51-final.log` e `build/bootstrap-proof-0.8.51-final.exit` = 0.
- Limite: o manifesto do builder N continua identificando `Python bootstrap compile_source`. A prova demonstra reprodutibilidade dos estágios nativos N→N+1→N+2, mas não prova construção inicial independente de Python.

### Integridade do workspace

- Nenhum commit, push, tag ou release foi criado.
- Nenhuma infraestrutura GPTV foi acessada ou modificada.


## Auditoria adicional do encoder/VM nativa — 2026-11-08

- `clang --analyze -std=c11 -Wall -Wextra -Wpedantic gpvm_native.c`: concluído sem apontamentos de acesso fora de limites, use-after-free ou vazamento. O analisador emitiu três avisos da categoria `unix.Errno` relacionados à preservação de `errno` em caminhos de falha de alocação/`fclose` e à chamada `rewind`; devem ser revisados como qualidade de diagnóstico, não classificados como vulnerabilidade confirmada.
- Build isolado com UndefinedBehaviorSanitizer (`-fsanitize=undefined -fno-sanitize-recover=all`) aprovado; fuzz diferencial de 64 iterações, seed `0x47505632`: 37 rejeições, 27 aceitos/executados, zero divergências e zero diagnósticos UBSan.
- AddressSanitizer foi compilado, mas não pôde executar no Termux/Android ARM64: o runtime falhou ao reservar sua região de shadow memory de 8.589.938.688 bytes (`ReserveShadowMemoryRange`, `errno 12`). Os falsos resultados divergentes desse ensaio são limitação do runtime ASan no ambiente, não falhas funcionais da VM. ASan permanece não validado neste dispositivo.
- Os binários e relatórios auxiliares foram mantidos em `$HOME/.cache/gp-lab`, fora do repositório. Nenhum arquivo de código foi alterado nesta auditoria; nenhum commit, push, tag ou release foi criado.


## Auditoria de autossuficiência — 2026-11-08

- Confirmado: frontend GP (lexer/parser/análise/IR) executa na VM C nativa; encoder GGPC v2 e execução final também podem usar C.
- Confirmado: CLI/orquestração, expansão de módulos, geração inicial do estágio N e harnesses de engenharia ainda dependem de Python.
- Confirmado: builtins de runtime são limitados a entrada_fonte, tamanho, adicionar e remover; mostrar é tratado pelo pipeline de execução. Ainda falta biblioteca padrão de sistema e driver GP.
- Não declarar independência integral: o bootstrap N atual ainda chama Python bootstrap compile_source.
- Plano detalhado e critérios de prova: docs/SELF_HOSTING.md.
- Nenhum código do compilador foi alterado nesta auditoria; nenhum commit, tag ou release foi criado.

### Diagnóstico de custo do bootstrap — 2026-11-08

- A execução de prova sem regeneração Python foi iniciada a partir do seed N íntegro, mas não concluiu na janela operacional e foi interrompida de forma controlada.
- Fonte expandida do frontend: 136.757 caracteres / 2.823 linhas.
- VM Python: 10.000.000 instruções excedidas em 41,57 s ao compilar o frontend contra si mesmo.
- VM C: limite de 1.000.000 instruções atingido; pico de 14,57 MiB gerenciados, 184.097 objetos gerenciados alocados, zero ciclos de GC.
- VM C: limite de 10.000.000 não concluiu em 90 s. Não declarar prova N→N+1→N+2 aprovada nesta tentativa.
- Próximo gargalo a medir: alocação de strings/concatenação no lexer e buscas lineares na tabela de símbolos semânticos.


## Baseline de desempenho da VM C — 2026-11-08

- Medições executadas no tablet ARM64 com bytecodes preexistentes e VM C nativa; nenhum fonte do frontend foi modificado nesta etapa.
- Aritmética: 14 instruções, mediana 0,0442 s em cinco execuções, heap GP pico 36.443 B.
- Probe do parser: 878.748 instruções, mediana 1,1885 s em três execuções, heap GP pico 11.355.760 B e RSS pico entre 20.787.200 e 20.889.600 B.
- Frontend expandido: 136.757 caracteres / 2.823 linhas. Com limite de 1.000.000 passos, a VM C parou pelo limite em 2,9168 s após 184.097 objetos gerenciados alocados e heap contabilizado de 14,57 MiB. O RSS de pico observado foi 35.708.928 B.
- Execuções do frontend com teto de 3.000.000 passos/timeout 15 s e 10.000.000 passos/timeout 25 s não concluíram. Não há contagem final de instruções ou relatório de memória final para esses timeouts.
- Relatório completo e método: `docs/PERFORMANCE_BASELINE_2026-11-08.md`; métricas brutas em `build/perf-baseline/`.
- Meta de produto atualizada para GP 1.1, mantendo GP 1.0.0 como portão intermediário obrigatório de estabilidade e qualidade.
- A prova estrita N → N+1 → N+2 permanece pendente; esta etapa não alterou o frontend nem declarou autossuficiência.


## Migração e validação no tablet — 2026-11-08

- Projeto restaurado em `$HOME/gabriel-luna-gp`; os 24 checkpoints em `$HOME/gp-backups` foram restaurados. O arquivo original de migração permaneceu intacto em `$HOME/downloads/GP-MIGRACAO-CELULAR-20261108-114934.tar.gz` e seu SHA-256 foi confirmado como `4e47274e6b54a6336928f529579b4cb558550db7e301cb5f68b3f87028cfd4a0`.
- Ambiente tablet ARM64 preparado com Git 2.54.0, Python 3.13.13 e Clang 21.1.8.
- `python -m unittest discover -s tests -p 'test_*.py' -q`: 231 testes aprovados em 96,736 s.
- `make check`: compilação Python e análise sintática C com `-Wall -Wextra -Wpedantic` aprovadas.
- `make validate`: exit code 0 em 182,85 s; 231 testes, corpus diferencial 6/6, fuzz 64 iterações (37 rejeições, 27 aceitos/executados, zero divergências), hashes dos fixtures e `git diff --check` aprovados.
- `make bootstrap-proof`: `BOOTSTRAP_PROOF_OK`, exit code 0; duração observada de 859,58 s. N: `4925c7dcb756a3b3c4f5eed396ce5a92198f0a6930b0952e84990e0d94ed0e54`; N+1 e N+2: `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes em cada estágio. N+1 == N+2 confirmado.
- O estágio N ainda é identificado pelo manifesto como `Python bootstrap compile_source`; a prova não demonstra autohospedagem integral nem independência do host Python.
- O repositório preserva HEAD `2987a5d` (`master`) e 21 caminhos modificados/não rastreados antes de nova edição. `git fsck --full --no-reflogs` e `git diff --check` passaram. Nenhum commit, push, tag ou release foi criado nesta validação.
- Repositório remoto ainda não foi criado; nenhuma publicação foi feita.


### Retificação de evidência do bootstrap no tablet — 2026-11-08

- A saída apresentada pela sessão remota informou `STAGE_N2` e `BOOTSTRAP_PROOF_OK`, porém a inspeção posterior do workspace não encontrou `proof.json`, `gp_frontend_runner_n1.gbc`, `gp_frontend_runner_n2.gbc` nem `memory_n1_to_n2.json`.
- O único relatório de memória presente em `artifacts/bootstrap/proof/memory_n_to_n1.json` registra `status: error`; por isso, a sessão não é considerada evidência suficiente de uma prova persistida, apesar da saída exibida.
- A afirmação de bootstrap integral no tablet fica **pendente de reprodução** até que uma execução controlada produza os dois artefatos e `proof.json` com `status: passed`, hashes N+1/N+2 idênticos e relatórios de memória `status: ok`.
- Uma execução isolada N→N+1 foi iniciada com saída e relatório separados em `$HOME/.cache/gp-lab` para capturar o diagnóstico exato. Não alterar o código C durante esta execução.


### Preparação para publicação e integridade no tablet — 2026-11-08

- Varredura heurística dos arquivos de texto do projeto (excluindo `.git`, `build`, caches, bytecode e objetos compilados) encontrou zero ocorrências de chaves privadas PEM, tokens conhecidos `ghp_`/`github_pat_`, chaves AWS `AKIA` ou atribuições óbvias de segredo. Esta verificação reduz risco, mas não substitui revisão humana nem garante ausência absoluta de segredos.
- O arquivo de migração original permanece preservado; nenhuma credencial foi adicionada ao projeto.
- Nenhum commit ou push foi feito. A publicação privada no GitHub segue pendente da criação do repositório remoto e da autenticação Git no tablet.


## Bootstrap N → N+1 → N+2 confirmado no tablet — 2026-11-08

- Prova controlada concluída com `status: passed`; evidência persistida em `artifacts/bootstrap/proof/proof.json`.
- N: `4925c7dcb756a3b3c4f5eed396ce5a92198f0a6930b0952e84990e0d94ed0e54`.
- N+1 e N+2: `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`; ambos com 23.037 bytes. Comparação byte a byte aprovada.
- Relatórios de memória N→N+1 e N+1→N+2: `status: ok`, limite de heap 268.435.456 B.
- N→N+1: heap pico 55.347.618 B (52,78 MiB), heap vivo 39.107.839 B, RSS pico 86.532.096 B.
- N+1→N+2: heap pico 55.540.904 B (52,97 MiB), heap vivo 39.300.780 B, RSS pico 86.786.048 B.
- Cada estágio executou 72.070.594 instruções na VM nativa; relatório indica 2.420 ciclos de GC e aproximadamente 6,07 milhões de objetos gerenciados alocados por estágio. Esses números tornam a eficiência do frontend e a pressão de alocação prioridade explícita de otimização.
- Saída bruta do runtime persistida em `artifacts/bootstrap/proof/native-stages.stderr.log`.
- Manifesto identifica corretamente o construtor do estágio N como `Python bootstrap compile_source`; portanto, esta prova confirma reprodutibilidade N→N+1→N+2 usando a VM C, mas **não** autohospedagem integral independente de Python.
- Arquivos oficiais N+1/N+2, JSON de prova e relatórios de memória foram copiados para `artifacts/bootstrap/proof/`. `.gitignore` agora permite versionar os artefatos de prova nessa pasta.


## GP 0.8.52 — validação integral e bootstrap otimizado — 2026-11-08

- Ambiente: Termux / Android ARM64; Node 26.3.1; Python 3.13.13; compilador C Clang.
- `make validate`: exit code 0; 238 testes em 88,805 s; `make check` (py_compile e sintaxe C com `-Wall -Wextra -Wpedantic`) aprovado.
- Corpus diferencial: 6/6 em frontend suportado, legado/direto, bootstrap, runner nativo, encoder nativo e semântica Python/C.
- Fuzz determinístico: 64 iterações, seed `0x47505632`; 37 rejeições, 27 aceitos/executados, zero divergências.
- SHA-256 dos fixtures aprovados; `git diff --check` aprovado.
- Bootstrap otimizado: `BOOTSTRAP_PROOF_OK`; N = `3dcf7be34ef2c90255f9026d33d5022fb00b570062e9d5c31520967dbbd978b6` (23.118 bytes); N+1 = N+2 = `6ced6b6e03f7d9978eb13d3919591bd3ec8fefd8046f7d73600b78ea4055ab72` (23.141 bytes cada).
- Heap total pico: 66.584.931 B em N→N+1 e 66.777.876 B em N+1→N+2; ambos abaixo do teto de 268.435.456 B (256 MiB). RSS de pico: 96.002.048 B e 96.264.192 B.
- Métricas da VM durante cada estágio: 72.464.879 instruções; 1.053 ciclos de GC; aproximadamente 2.441,38 MiB recuperados; heap contabilizado 63,50 MiB e 63,68 MiB.
- Evidências atualizadas e sincronizadas em `artifacts/bootstrap/proof/`: bytecodes N+1/N+2, `proof.json`, relatórios de memória e log de estágios nativos. A inconsistência anterior era causada por prova nova armazenada no cache sem cópia para o diretório versionado; os arquivos agora correspondem aos hashes do log mais recente.
- Limite honesto: o estágio N ainda é produzido por `Python bootstrap compile_source`; N→N+1→N+2 é reprodutível na VM C, mas o toolchain não é totalmente autossuficiente nem independente de Python.
- Comparação de desempenho contra o baseline 0.8.51 permanece pendente. Não inferir ganho de velocidade apenas da redução de concatenações.
- Estado Git: alterações locais não commitadas; nenhum commit, push, tag ou release criado. Nenhuma infraestrutura GPTV foi alterada.

### Próximas prioridades técnicas

1. Medir o baseline 0.8.51 e comparar tempo por estágio, instruções, ciclos/objetos de GC, heap e RSS em condições equivalentes.
2. Auditar e ampliar a cobertura do encoder/decoder nativo e das fronteiras de entrada/saída.
3. Reduzir gradualmente a dependência do host Python: resolver módulos, materializar GP-IR e conduzir o driver de build no próprio GP, preservando o oráculo Python até equivalência comprovada.
4. Ampliar a biblioteca padrão com contratos estáveis, testes Python/C e documentação de cada função.
5. Fechar os critérios de `docs/RELEASE_CRITERIA_1.0.0.md` antes de qualquer declaração de estabilidade.


## GP Programinha — bridge local e integração — 2026-11-08

- Criado gp_ide_server.py como ponte HTTP para o editor visual mantido em repositório separado.
- A ponte usa a CLI oficial gp_compile.py; não replica parser, compilador, bytecode nem runtime.
- Segurança inicial: bind exclusivo em 127.0.0.1, host allowlist, CORS allowlist configurável, corpo limitado a 1 MiB, validação de nome .gp sem caminho, workspace temporário, invocação por lista de argumentos sem shell, timeout de compilação/execução e VM de referência com teto de passos.
- Endpoints implementados e verificados por HTTP real: /api/health, /api/compile e /api/run. Health, compilação e execução retornaram HTTP 200; path traversal foi rejeitado.
- tests/test_ide_bridge.py: 7 testes aprovados, incluindo compilação e execução reais. gp_ide_server.py e os testes passaram em py_compile.
- Revalidação integral após integrar o Bridge: make validate exit 0; 245 testes em 88,766 s (238 da linguagem + 7 do Bridge); corpus diferencial 6/6; fuzz determinístico 64 casos, 37 rejeições e 27 execuções aceitas, zero divergências; hashes dos fixtures e git diff --check aprovados.
- docs/GP_BRIDGE.md documenta operação e limites; biblioteca/README.md organiza o contrato da biblioteca padrão; Makefile e README passam a oferecer make bridge.
- O GP Programinha permanece em Gp-ai-programacao, como cliente da API. Não há compilador duplicado no app.
- Limites: a primeira ponte executa pela VM Python de referência, trabalha com uma fonte GP por chamada e não oferece persistência de projetos, terminal arbitrário, runtime nativo ou rede externa. Estas funções só devem ser adicionadas com contratos e controles separados.
