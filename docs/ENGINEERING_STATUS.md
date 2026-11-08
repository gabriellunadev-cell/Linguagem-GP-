# GP — Estado de engenharia e continuidade

Atualizado em: 2026-11-07 (America/Sao_Paulo)
Repositório: /data/data/com.termux/files/home/gabriel-luna-gp
Ambiente primário: Android ARM64 / Termux; Python 3.13.13; Clang disponível.
VPS cadastrada: offline durante a auditoria; nenhuma alteração remota.

## Ciclo 0.8.37 — indexação textual e contabilidade de memória (Android ARM64 / Termux)

- VM C: cache de caracteres ASCII por instância; leituras repetidas reutilizam o mesmo objeto gerenciado em vez de alocar uma nova string por acesso.
- VM C: strings ASCII usam indexação direta por byte; strings não ASCII continuam respeitando pontos de código UTF-8. A busca Unicode usa uma única travessia.
- O cache é marcado como raiz pelo GC e permanece válido durante coletas. Teste de regressão cobre 5.000 indexações e exige menos de 100 objetos gerenciados alocados.
- O contador do heap agora inclui sizeof(GPAllocHeader) em malloc, free e realloc, além do payload. O limite continua em 256 MiB; não foi aumentado.
- O relatório da VM expõe o total de objetos gerenciados alocados e mantém a expressão de compatibilidade "limite 256 MiB".
- make check, compilação nativa e git diff --check: aprovados.
- Regressões nativas focadas: 4/4 (cache ASCII, indexação UTF-8, coleta de lixo/raízes vivas e diagnóstico de memória).
- make validate: exit 0; 186 testes aprovados em 69,139 s; corpus CORPUS_OK 6/6 nas comparações; fuzz 64 casos, 37 rejeições, 27 aceitos/executados e zero divergências; 38/38 SHA-256 dos fixtures; git diff --check aprovado. Log: build/gp-next-cycle/validate-0837-memory-index.log; exit: 0.
- Artefato bootstrap íntegro: 23.014 bytes, SHA-256 4925c7dcb756a3b3c4f5eed396ce5a92198f0a6930b0952e84990e0d94ed0e54.
- A prova de autocompilação N → N+1 → N+2 não foi repetida neste ciclo. O pico global de heap do frontend ainda precisa ser medido e reduzido; não há comprovação de N+1/N+2 nem liberação da GP 1.0.
- VPS permaneceu offline/intocada; nenhum deploy ou publicação remota foi realizado.

## Ciclo 0.8.36 — entrada explícita do host, runner nativo e bootstrap reutilizável

- Criada a chamada reservada entrada_fonte(), sem argumentos, com retorno texto e sem acesso do programa GP a caminhos ou arquivos.
- GPVirtualMachine.run_bytes aceita host_source por execução, valida UTF-8 estrito e limita o conteúdo a 16 MiB; a entrada é descartada ao final de cada execução.
- As CLIs Python e C aceitam --source-input arquivo.txt. A VM C valida UTF-8, rejeita NUL e recusa entradas acima de 16 MiB.
- O runner auto-hospedado recebe a fonte-alvo como dado do host, não como literal interpolado no código temporário.
- Os analisadores semânticos bootstrap e GP reconhecem entrada_fonte() e rejeitam argumentos.
- Corrigido o parser auto-hospedado para aceitar chamadas de função como comandos independentes (CHAMADA_COMANDO), emitindo POP para descartar o retorno.
- Corrigidos terminadores opcionais após blocos se/enquanto/para e compatibilidade de lista vazia tipada em atribuições e construtores nomeados.
- Corrigido o montador do runner: _strip_gp_top_level_self_tests preserva quebras de linha reais; o runner final contém 2.823 linhas.
- Adicionada a opção experimental --runner-vm native. O frontend GP completo pode ser executado pela VM C.
- Corpus diferencial: 6/6 fontes aceitas; 6/6 encoder direto/legado byte-idênticos; 6/6 frontend/bootstrap idênticos; 6/6 runners Python/C produziram GP-IR idêntico; 6/6 execuções Python/C semanticamente equivalentes.
- Artefato persistente artifacts/bootstrap/gp_frontend_runner.gbc: 23.014 bytes, GGPC v2 / GP-IR v1, manifesto com hashes das nove entradas. SHA-256: 4925c7dcb756a3b3c4f5eed396ce5a92198f0a6930b0952e84990e0d94ed0e54.
- O loader verifica manifesto, hash do artefato e hashes das fontes; testes comprovam reutilização sem recompilar o runner Python quando as entradas não mudam.
- make validate: exit 0; 185 testes aprovados em 54,759 s; make check aprovado; corpus 6/6 nas comparações; fuzz 64 casos (37 rejeitados, 27 aceitos/executados, zero divergências); 38/38 artefatos SHA-256; git diff --check aprovado. Log: build/gp-next-cycle/validate-final.log.
- Prova N -> N+1 -> N+2: tentada com limite de 100 milhões. A VM C atingiu o teto padrão de heap de 256 MiB durante a análise do próprio frontend e falhou com 'opcode sem nome'; pico informado de 256 MiB. Não emitiu STAGE_N1. O aumento experimental do limite foi revertido após introduzir regressões na VM C. Nenhum N+1/N+2 foi comprovado. A autohospedagem integral permanece pendente.
- VPS permaneceu offline/intocada; nenhum commit, release ou publicação foi criado.

## Próxima tarefa exata — GP 0.8.37: prova de bootstrap reproduzível

1. Otimizar o frontend auto-hospedado para analisar e gerar o próprio código dentro do orçamento do Android ARM64.
2. Fazer o artefato N produzir N+1, executando o runner armazenado na VM C sem recompilar o runner por chamada.
3. Fazer N+1 produzir N+2 na VM C e exigir igualdade byte a byte de GP-IR/GGPC e hashes.
4. Persistir relatório com hashes N, N+1 e N+2, versões e orçamento utilizado.
5. Manter o bootstrap Python como fallback/oráculo até a prova em dois estágios passar. Não declarar GP 1.0 antes disso.
## Ciclo 0.8.35 — paridade do lowering condicional (Android ARM64 / Termux)

- Corrigida a representação do ramo senao ausente no AST bootstrap: agora é distinto de um bloco senao {} explicitamente vazio.
- Lowerer, análise semântica e backend C tratam o ramo ausente sem inventar bloco alternativo; o interpretador bootstrap trata None como ramo sem instruções.
- Adicionado teste de regressão que compara o GP-IR completo do frontend GP com o bootstrap para condicionais sem senao, com senao {} e com ramo alternativo preenchido, inclusive em função.
- make check: aprovado (Python byte-compilation e Clang -fsyntax-only).
- python3 -m unittest discover -s tests -v: 164 testes aprovados em 221,169 s, exit code 0; log em build/gp-next-cycle/full-suite-final.log.
- make differential-corpus: 6/6 fontes aceitas diretamente pelo frontend GP, 6/6 bytecodes diretos idênticos ao encoder legado, 6/6 bytecodes frontend/bootstrap estruturalmente idênticos e 6/6 resultados semânticos coincidentes entre VMs Python/C; manifesto atualizado.
- make fuzz-bytecode: 64 iterações, seed 0x47505632, 37 rejeições, 27 entradas aceitas/executadas, zero divergências; relatório em build/fuzz-reports/latest.json.
- tests/fixtures/gp_ir_direct/SHA256SUMS: 38/38 artefatos verificados.
- git diff --check: aprovado após as alterações de código e documentação.
- Nenhum commit, release ou publicação criado. VPS permaneceu intocada.

## Ciclo 0.8.34 — parser de construtores nomeados e incremento de para



- linguagem/parser_gp.gp: parse_primaria_gp cria CHAMADA_NOMEADA e CAMPO_ARGUMENTO para Tipo{campo: expressão}.
- A análise semântica valida existência, unicidade, completude e tipo de cada campo; o IR é emitido na ordem canônica do schema, mesmo quando a fonte fornece outra ordem.
- parse_para_gp reconhece uma chamada de função na posição de incremento sem tratá-la como atribuição.
- Testes cobrem estruturas aninhadas, ordem de campos, campos ausentes/desconhecidos/duplicados, tipos incorretos e chamada no incremento.
- Corpus diferencial: 6/6 fontes aceitas diretamente pelo frontend GP, 6/6 bytecodes diretos idênticos ao encoder legado e 6/6 resultados semânticos Python/C coincidentes (confirmação estrutural completa no ciclo 0.8.35).
- Na validação original 0.8.34, control_flow_nested.gp ainda apresentava diferenças estruturais. Essa divergência foi corrigida e coberta por teste de regressão no ciclo 0.8.35.
- O caminho CLI direto ainda depende do bootstrap Python para executar o runner e do encoder Python para o bytecode; a API de compatibilidade e o oráculo legado permanecem.
- Backup incremental pré-ajuste do para: gp-backups/20261107-020920-gp-0834-pre-for-increment.

## Validação final do ciclo 0.8.34 — Android ARM64 / Termux

- make check: aprovado após as alterações do ciclo.
- make test, fuzz de 64 mutações, SHA-256 do corpus e git diff --check: resultados registrados em build/gp-0.8.34-validation/recovery-final2.log.
- make differential-corpus: 6/6 fontes aceitas pelo frontend, 6/6 bytes diretos/legados idênticos e 6/6 resultados Python/C coincidentes.
- Nenhum commit, release ou publicação foi criado.


## Ciclo 0.8.33 — encoder direto GP-IR → GGPC

- gpcompiler.ir.validate_canonical_ir(document) valida o GP-IR v1 em listas/dicionários JSON, sem dataclasses.
- gpcompiler.bytecode.encode_canonical_ir(document) cria GGPC v2 direto do JSON; não instancia IRProgram nem IRFunction.
- A API encode(IRProgram) foi preservada. A ordem do envelope é normalizada para compatibilidade binária.
- compile_source_selfhosted_document entrega o envelope canônico. gp_compile.py --self-hosted usa essa função e o encoder direto. compile_source_selfhosted permanece como API de compatibilidade que retorna IRProgram.
- O CLI de produção valida somente o envelope canônico e não hidrata registros legados. A comparação byte a byte com encode() é executada pelo corpus e pela suíte diferencial, fora do caminho de produção.
- Corpus persistente: tests/fixtures/gp_ir_direct/; ferramenta: ferramentas/gerar_corpus_ir.py; alvo: make differential-corpus.
- Corpus: 6 casos, 6/6 bytes diretos iguais ao encoder legado, 6/6 execuções coincidentes entre VM Python e VM C. Artefatos e manifesto possuem SHA-256.
- Quatro fontes foram compiladas pelo frontend GP. opcode_catalog.gp e structs_and_fields.gp ainda usam inicializadores de campos nomeados não aceitos pelo parser GP; seus GP-IR foi obtido dos bytecodes dourados existentes e marcado no manifesto.
- control_flow_nested.gp: frontend GP e bootstrap produzem IR/bytecodes com diferentes quantidades de instruções/alvos, mas a saída observada foi igual (48 3 11 8). Isso não prova lowering idêntico.
- O adaptador Python continua como oracle/fallback e na API de compatibilidade. O caminho do CLI auto-hospedado não materializa o envelope canônico em objetos IR. Não declarar autohospedagem integral nem independência completa de Python.
- Backup pré-alterações: $HOME/gp-backups/20261107-011658-gp-ir-033; SHA-256 em SHA256SUMS.

## Validação final do ciclo 0.8.33 — Android ARM64 / Termux

- make check: aprovado; py_compile de fontes/testes/ferramentas e Clang -fsyntax-only aprovados.
- python3 -m unittest discover -s tests -v: 159 testes aprovados em 358,475 s, exit code 0; log em build/gp-0.8.33-validation/tests-rerun.log.
- make fuzz-bytecode com 64 iterações, seed 0x47505632 e timeout 2 s: 6 fixtures, 37 rejeições, 27 aceitas/executadas, zero divergências; relatório build/fuzz-reports/latest.json.
- make differential-corpus: 6/6 encoder direto/legado byte-idênticos; 6/6 execuções coincidentes Python/C; 4 fontes compiladas pelo frontend GP e 2 casos obtidos de bytecodes dourados por sintaxe ainda não suportada.
- sha256sum -c tests/fixtures/gp_ir_direct/SHA256SUMS: todos os 38 artefatos aprovados.
- git diff --check: aprovado.
- CLI --self-hosted: bytecode de 230 bytes gerado e executado em Python/C; saída igual: 11 24 5.
- Exit codes finais: CHECK=0, TEST_SUITE=0, FUZZ=0, DIFF=0, CORPUS_SHA=0.

## Auditoria real

- Ciclo 0.8.32: serializador GP nativo em `linguagem/parser_gp.gp` produz envelope JSON canônico GP-IR v1.
- O frontend organiza `main`, `functions`, `parameters`, `return_type`, `code` e schemas de `BUILD_STRUCT`; o runner ainda emite o formato de registros anterior em paralelo para comparação diferencial.
- `compile_source_selfhosted` hidrata o documento canônico e compara sua representação com o adaptador de registros; divergências bloqueiam a compilação.
- O CLI auto-hospedado já codifica o JSON canônico diretamente; o bootstrap de ferramentas e o oráculo legado ainda usam Python. Não declarar remoção completa da dependência Python.

- Ciclo 0.8.31: versão base 0.8.30 confirmada pelo CHANGELOG; GP-IR v1 separado conceitualmente do contêiner GGPC v2 e da linguagem 0.4.
- `gpcompiler/ir.py` passou a definir `IR_VERSION=1` e `validate_ir`; lowering, adaptador auto-hospedado e encoder chamam o validador.
- `program.ir_version` agora é emitido no envelope serializado. Decoders Python/C aceitam ausência em bytecodes históricos como v1 e rejeitam valor explícito diferente de 1.
- Especificação inicial: `docs/GP_IR_SPEC.md` rascunho 0.1. A materialização continua no adaptador Python; não houve remoção do bootstrap.

- Repositório, bootstrap, frontend GP, IR, bytecode, VM Python, VM C, testes, documentação e dependências examinados antes das alterações.
- Arquitetura atual: bootstrap Python + lexer/parser/semântica/gerador parcial em GP + adaptador Python para materializar IRProgram/IRFunction + VM Python de referência + VM C ARM64 experimental.
- O frontend GP emite IR interno tipado diretamente; materialização do IR final ainda ocorre no adaptador Python. A linguagem não se recompila integralmente.
- IP é incrementado antes da instrução; destinos de salto são absolutos por bloco e len(code) representa saída.
- Git: branch master sem commits iniciais; arquivos ainda não rastreados. Nenhum commit criado.

## Alterações deste ciclo

- Backpatcher bootstrap valida índice, opcode, tipo e destino.
- Loaders Python/C validam schemas e tipos por opcode, parâmetros/funções, versões, JSON, Unicode, limites de recurso, CRC32 e stream zlib exato.
- Loader C usa inflate e recusa bytes residuais; strings são validadas quanto a escapes, caracteres de controle, NUL e surrogates isolados.
- Corpus v2: seis fontes GP e seis binários de referência com SHA256SUMS.
- Fixture opcode_catalog.gp exercita 32/32 opcodes reconhecidos pelo decoder; a suíte exige cobertura positiva completa.
- Teste diferencial estrutural: 66 mutações inválidas (11 por fixture), rejeitadas por Python e C.
- Fuzz smoke determinístico: 48 flips de bit, seed fixo, oito por fixture; ambos os loaders rejeitam todos.
- Harness ferramentas/fuzz_bytecode.py compara loaders/VMs em mutações válidas e inválidas; processo C limitado por RLIMIT_DATA=512 MiB e RLIMIT_CPU=3 s, além de timeout de parede; 64 casos executados (37 rejeitados, 27 aceitos, zero divergências).
- Makefile inclui o alvo make fuzz-bytecode e py_compile de ferramentas/*.py.
- Especificação BYTECODE_V2_SPEC.md atualizada para rascunho 0.7; política normativa de extensões desconhecidas no envelope raiz definida; ainda não congelada.
- CHANGELOG, README e ROADMAP atualizados para 0.8.30.

## Evidências

- make test: 139 testes aprovados em 107,417 s (antes da inclusão do harness, que é executado separadamente).
- make check: aprovado após incluir ferramentas/*.py.
- make fuzz-bytecode com seed 0x47505632 e 64 iterações: 37 entradas rejeitadas, 27 aceitas/executadas, zero divergências; relatório JSON válido em build/fuzz-reports/latest.json.
- Clang ARM64: build otimizado -O2 -Wall -Wextra -Wpedantic aprovado.
- Corpus: 6/6 fixtures válidas; 32/32 opcodes cobertos; mesmos bytes executados nas duas VMs e SHA-256/saída coincidem.
- Mutações estruturais: 66/66 rejeitadas pelos dois loaders.
- Fuzz smoke: 48/48 flips de bit rejeitados pelos dois loaders.
- make test na versão 0.8.30: 139 testes aprovados em 106,857 s. Relatório JSON validado: build/fuzz-reports/latest.json. RLIMIT_DATA/RLIMIT_CPU ativos no processo C; RLIMIT_AS rejeitado por incompatibilidade com Bionic CFI.
- Backups anteriores incluem $HOME/gp-backups/20261106-post-seeded-fuzz/; backup final deste ciclo: $HOME/gp-backups/20261106-post-bounded-harness/.

## Quadro de progresso

| Área | Estado | Observação |
|---|---|---|
| Auditoria inicial | Validado | Estado real confirmado no Termux |
| Backpatch e fluxo de controle | Validado | Saltos absolutos, funções e laços aninhados |
| Validação estrutural por opcode | Validado | Casos de operandos e schemas cobertos |
| Integridade JSON/zlib/CRC | Validado | Chaves, escapes, Unicode e stream exato |
| Limites dos loaders | Validado | 64 MiB raw, 128 MiB comprimido, 2M tokens, depth 512 |
| Corpus binária v2 | Validado | 6 fixtures, 32/32 opcodes, duas VMs |
| Mutação estrutural diferencial | Validado | 66 corrupções rejeitadas pelos dois loaders |
| Fuzz smoke determinístico | Validado | 48 bit flips, seed fixo, sem divergências |
| Harness diferencial limitado | Validado | 64 iterações, 27 aceitas, 37 rejeitadas, zero divergências; RLIMIT_DATA/RLIMIT_CPU e relatório JSON |
| Fuzzing guiado por cobertura | Planejado | Harness mutacional limitado; ainda sem instrumentação de cobertura |
| Especificação BYTECODE_V2 | Em desenvolvimento | Rascunho 0.7; extensões raiz normatizadas; não congelado |
| IR materializado pela GP | Em desenvolvimento | Adaptador Python ainda constrói IRProgram/IRFunction |
| Autohospedagem integral | Planejado | Bootstrap Python ainda necessário |
| Runtime nativo de produção | Planejado | VM C experimental, sem certificação cross-platform |
| Biblioteca padrão completa | Planejado | Parcial |
| Gerenciador de pacotes | Planejado | Não implementado |
| Ferramentas profissionais completas | Em desenvolvimento | CLI/test runner iniciais; formatter/linter/debugger incompletos |
| GP 1.0 | Planejado | Critérios finais ainda não atendidos |

## Ciclo 0.8.31 — concluído com validação Android ARM64

- Novos testes dedicados em `tests/test_ir_validation.py` cobrem versionamento independente, validação de opcode/operandos, saltos, constantes, funções, schemas e serialização.
- `make check`: aprovado (py_compile e Clang `-fsyntax-only`).
- `make test`: **152 testes aprovados em 107,470 s** (139 anteriores + 13 novos).
- `make fuzz-bytecode FUZZ_ITERATIONS=64 FUZZ_SEED=0x47505632 FUZZ_TIMEOUT=2`: 64 casos, 37 rejeitados, 27 aceitos/executados, zero divergências; JSON validado.
- Clang compilou a VM nativa ARM64 otimizada; os testes de integração nativa passaram com o campo `ir_version` explícito; o teste C também rejeita GP-IR v2 desconhecido.
- `git diff --check`: aprovado. Nenhum commit, release ou publicação criado.
- Backup estrutural salvo em `$HOME/gp-backups/` com sufixo `gp-ir-031` (caminho registrado em `$HOME/gp-backups/LATEST-GP-IR-031`).

## Ciclo 0.8.32 — concluído com validação Android ARM64

- `make check`: aprovado (Python byte-compilation e Clang `-fsyntax-only`).
- `make test`: **154 testes aprovados em 126,854 s**; inclui os testes antigos e dois novos testes do envelope canônico.
- Os testes auto-hospedados exercitam a comparação diferencial entre serialização legada e canônica em fontes com funções, recursão, loops, arrays, schemas, estruturas aninhadas e listas tipadas.
- `make fuzz-bytecode FUZZ_ITERATIONS=64 FUZZ_SEED=0x47505632 FUZZ_TIMEOUT=2`: 64 casos, 37 rejeitados, 27 aceitos/executados, zero divergências; relatório JSON válido.
- VM C ARM64 recompilada e integrada à suíte; `git diff --check` aprovado.
- O adaptador de registros não foi removido: permanece como oráculo diferencial/fallback. Python ainda decodifica o objeto JSON canônico para `IRProgram`/`IRFunction` e executa o encoder; a organização semântica das seções já é emitida por GP.
- Backup salvo em `$HOME/gp-backups/` com sufixo `gp-ir-032`; caminho em `$HOME/gp-backups/LATEST-GP-IR-032`.
- Nenhum commit, release ou publicação criado.

## Próxima tarefa exata — GP 0.8.37: artefato bootstrap e recompilação em estágios

1. Separar a geração do bytecode runner da compilação de cada fonte-alvo e criar um artefato bootstrap GP-IR/GGPC versionado, com hashes da fonte do frontend, versão do formato e saída de referência.
2. Fazer o modo native reutilizar esse artefato validado, sem executar compile_source() para compilar o runner a cada chamada.
3. Executar o artefato runner pela VM C com entrada fornecida pelo host e comparar GP-IR com a execução Python de referência.
4. Provar bootstrap em dois estágios: artefato N gera artefato N+1; N+1 gera N+2; hashes/GP-IR devem coincidir nos dois caminhos.
5. Manter o bootstrap Python como fallback/oráculo até a prova de dois estágios e a matriz de conformidade passarem. Não declarar autohospedagem integral antes disso.

## Retomada

Confirmar caminho do repo, git status, backups e dispositivos antes de editar. Rodar make check e make test antes de alterações estruturais. Não criar commits, releases ou publicações sem autorização explícita.


## Estado no tablet — 2026-11-08 (validação e prova reprodutível)

- Projeto e 24 checkpoints restaurados do arquivo de migração; SHA-256 original confirmado. Ambiente ARM64 preparado com Git 2.54.0, Python 3.13.13 e Clang 21.1.8.
- `make validate`: exit 0; 231 testes aprovados, corpus diferencial 6/6, fuzz de 64 iterações (37 rejeições, 27 execuções aceitas, zero divergências), hashes dos fixtures e `git diff --check` aprovados.
- `make check`, compilação da VM C ARM64, execução da VM C e exemplos smoke aprovados.
- Bootstrap N→N+1→N+2: `status: passed`; N+1 e N+2 têm SHA-256 idêntico `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes, comparação byte a byte aprovada.
- Memória N→N+1: heap pico 55.347.618 B (52,78 MiB); N+1→N+2: 55.540.904 B (52,97 MiB); ambos `status: ok`, abaixo do teto de 256 MiB. RSS pico: 86.532.096 B e 86.786.048 B.
- Cada execução nativa registrou 72.070.594 instruções, 2.420 ciclos de GC e aproximadamente 6,07 milhões de objetos gerenciados alocados. O tempo no tablet foi de vários minutos por estágio, indicando que otimização do frontend, alocações e serialização deve preceder a liberação 1.0.
- Evidência completa: `artifacts/bootstrap/proof/proof.json`, `gp_frontend_runner_n1.gbc`, `gp_frontend_runner_n2.gbc`, relatórios de memória e `native-stages.stderr.log`.
- Limite arquitetural mantido: o estágio N é construído pelo `Python bootstrap compile_source`; a prova confirma reprodutibilidade dos estágios N→N+1→N+2 na VM C, não independência integral de Python.
- GitHub CLI 2.95.0 instalado no tablet. Login por dispositivo foi iniciado, mas ainda depende de autorização do usuário no navegador; nenhum commit, push ou repositório remoto foi criado nesta etapa.

### Próxima otimização escolhida

- Introduzir `unir_textos(lista texto)` como primitiva de biblioteca padrão com validação de tipo, limite de tamanho e implementação eficiente Python/C.
- Refatorar `serializar_codigo_principal_canonico_ir_gp` e `serializar_funcoes_canonicas_ir_gp` para coletar fragmentos em listas e juntá-los uma única vez, preservando exatamente o JSON canônico e o bytecode final.
- Cobrir Unicode, lista vazia, tipos inválidos, limite de tamanho e paridade Python/C; regenerar o artefato seed N com o bootstrap Python e repetir validação e prova nativa.
