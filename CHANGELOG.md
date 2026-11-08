## Integração IDE — GP Bridge 0.2 (mantém GP 0.8.52)

- A Bridge passa a oferecer `/api/compile-project` e `/api/run-project`, recebendo o arquivo principal e os módulos enviados pelo GP Programinha.
- A API confina os imports ao conjunto de arquivos recebido: rejeita caminhos absolutos, backslashes, traversal para fora da raiz e módulos ausentes, inclusive em imports aninhados.
- Endpoints de arquivo único rejeitam fontes com imports e direcionam o cliente para os endpoints de projeto.
- Limites de projeto: 128 arquivos, 4 MiB por arquivo, 16 MiB totais; timeout de compilação de 30 s e execução de 10 s com limite de 1.000.000 de instruções.
- O processo do compilador recebe apenas ambiente mínimo (PATH, PYTHONPATH e flags de UTF-8), sem herdar credenciais ou variáveis arbitrárias do processo servidor.
- A CORS local inclui Vite em `localhost:5173`/`127.0.0.1:5173`, além das portas de preview 4173/4174; o serviço continua restrito a loopback.
- Fixtures binárias GGPC v2 passaram a ser versionadas como Base64 com hash e tamanho verificados antes da materialização, evitando depender de bytes gerados por zlib de cada sistema.
- Testes HTTP reais cobrem health, execução modular (retorno 42), rejeição de imports externos e preflight CORS.
- GitHub Actions (Linux x64, Python 3.12): `make validate` aprovado no commit `1c65079a90b20acf331bfcb4e12c29f3fb578612`; 263 testes, corpus diferencial 6/6 em todas as seis comparações, fuzz determinístico 64 (38 rejeições, 26 aceitos/executados, zero divergências), hashes e `git diff --check` aprovados.
- Esta integração não altera a versão do compilador: GP continua em 0.8.52. A validação registrada é no runner Linux; a verificação final no Termux/Android depende do dispositivo local.
## Integração GP Programinha — GP Bridge 0.1

- Criado gp_ide_server.py, serviço HTTP local que conecta o editor separado à CLI oficial da linguagem sem duplicar o compilador.
- Endpoints iniciais: GET /api/health, POST /api/compile e POST /api/run usando a VM Python de referência.
- Serviço limitado a loopback, com CORS allowlist, host allowlist, fonte máxima de 1 MiB, nome de arquivo sem caminhos, workspace temporário por chamada e timeouts.
- Não existem endpoints genéricos de shell, leitura de arquivos, rede ou administração.
- Contrato documentado em docs/GP_BRIDGE.md; testes reais de compilação e execução em tests/test_ide_bridge.py.
- make bridge inicia o serviço; make check verifica sua sintaxe e make validate inclui os testes de integração.
- Validação integrada final: 245 testes aprovados (238 da linguagem + 7 do Bridge), corpus diferencial 6/6, fuzz 64 sem divergências, hashes e git diff --check aprovados.
- A primeira comunicação HTTP foi validada no Termux: health 200, compile 200, run 200 e rejeição de path traversal.
- O aplicativo permanece no repositório independente Gp-ai-programacao.

## 0.8.52 — junção eficiente de texto e serialização GP-IR em lote

- Adicionada a primitiva `unir_textos(lista texto) -> texto` ao interpretador bootstrap, VM Python e VM C nativa.
- `unir_textos` valida os itens em runtime, preserva UTF-8, aceita lista vazia e limita o texto resultante a 64 MiB.
- Os serializadores canônicos de código principal e funções do frontend GP agora acumulam fragmentos em listas tipadas e juntam cada bloco uma única vez, evitando concatenação cumulativa repetida.
- Adicionados testes para texto Unicode, lista vazia, rejeição de itens não textuais e execução Python/C; o frontend auto-hospedado passa a usar a mesma primitiva no serializador.
- `make validate`: 238 testes; corpus diferencial 6/6; fuzz 64 (37 rejeições, 27 execuções aceitas, zero divergências); hashes dos fixtures e `git diff --check` aprovados.
- `make bootstrap-proof` otimizado: `BOOTSTRAP_PROOF_OK`; N+1 e N+2 idênticos, SHA-256 `6ced6b6e03f7d9978eb13d3919591bd3ec8fefd8046f7d73600b78ea4055ab72`, 23.141 bytes cada. N: `3dcf7be34ef2c90255f9026d33d5022fb00b570062e9d5c31520967dbbd978b6`, 23.118 bytes.
- Heap pico: 66.584.931 B em N→N+1 e 66.777.876 B em N+1→N+2, abaixo do teto de 268.435.456 B; RSS pico 96.002.048 B e 96.264.192 B.
- Evidências sincronizadas em `artifacts/bootstrap/proof/`: `proof.json`, dois bytecodes N+1/N+2, relatórios de memória e `native-stages.stderr.log`. A prova confirma reprodutibilidade binária, não autohospedagem integral: o estágio N ainda é construído pelo bootstrap Python.

## 0.8.51 — leitura segura e limitada de módulos locais

- `gpcompiler/modules.py`: a leitura de cada módulo agora abre o arquivo em modo binário e limita os bytes realmente lidos a 4 MiB, sem depender apenas de metadados de tamanho do arquivo.
- O limite total de 16 MiB por grafo contabiliza os bytes efetivamente lidos nos módulos; os limites de profundidade (32) e quantidade (128) permanecem ativos.
- Caminhos inválidos, arquivos ausentes, UTF-8 inválido e falhas de leitura são convertidos em diagnósticos GP. Ciclos de links simbólicos (ELOOP), inclusive em imports aninhados, recebem diagnóstico explícito de caminho inválido. Pipes nomeados e outros arquivos especiais são rejeitados como não regulares, sem bloquear a compilação.
- Os dois compiladores — referência Python e backend auto-hospedado — compartilham as regras de leitura e limites.
- 18 testes de módulos cobrem paridade, imports aninhados, ciclos, aliases duplicados, profundidade, limites reais por arquivo/grafo, links simbólicos cíclicos (inclusive aninhados) e rejeição de FIFO; suíte integral aprovada.
- `make validate`: exit 0; 231 testes em 48,620 s; corpus diferencial 6/6 nas seis dimensões; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes e `git diff --check` aprovados.
- `make bootstrap-proof`: exit 0; `BOOTSTRAP_PROOF_OK`; N+1 e N+2 idênticos, SHA-256 `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes cada.
- Bootstrap N: SHA-256 `4925c7dcb756a3b3c4f5eed396ce5a92198f0a6930b0952e84990e0d94ed0e54`, 23.014 bytes. Heap pico 55.347.618 B em N→N+1 e 55.540.904 B em N+1→N+2; RSS pico 68.431.872 B e 68.505.600 B; heap abaixo do teto de 268.435.456 B.
- Evidências finais: `build/validate-0.8.51-final.log`, `build/validate-0.8.51-final.exit`, `build/bootstrap-proof-0.8.51-final.log`, `build/bootstrap-proof-0.8.51-final.exit` e `artifacts/bootstrap/proof/proof.json`.
- Limite honesto: o artefato N ainda é gerado por `Python bootstrap compile_source`. A prova confirma N→N+1→N+2 com execução nativa e reprodutibilidade binária, mas não independência total do host Python.

## 0.8.44 — GP-IR JSON bruto direto no encoder C

- O caminho CLI self-hosted com encoder nativo agora preserva a linha JSON canônica produzida pelo frontend GP e a entrega diretamente ao encoder C.
- O caminho nativo deixa de executar `json.loads`, `validate_canonical_ir` e `json.dumps` sobre o GP-IR; o parser/validador C passa a ser a fronteira de validação desse fluxo.
- Mantida a API `compile_source_selfhosted_document` que retorna dict validado e a API de compatibilidade que retorna `IRProgram`; o caminho Python de referência permanece.
- Criada `encode_canonical_ir_native_json` e cobertura que intercepta `validate_canonical_ir` para demonstrar que o caminho JSON bruto não hidrata um dict Python; bytes resultantes permanecem idênticos aos da referência.
- Alinhado o validador C ao contrato canônico: cada instrução precisa ter exatamente as propriedades `op` e `args`; propriedades extras são rejeitadas.
- Corrigido o padrão do CLI: `--runner-vm native` seleciona automaticamente `build/gpvm-native` como runner e encoder, mesmo sem `--native-vm` explícito.
- Teste de CLI comprova seleção automática do C e funcionamento de `--dump-ir`.
- `make validate`: exit 0; 203 testes aprovados em 54,715 s; corpus 6/6 em todas as comparações; fuzz 64 (37 rejeições, 27 execuções aceitas, zero divergências); hashes e `git diff --check` aprovados.
- A eliminação da ida e volta JSON no CLI nativo reduz dependência de materialização Python, mas a orquestração do host, o bootstrap inicial e APIs de compatibilidade continuam em Python.

- make bootstrap-proof: exit 0; BOOTSTRAP_PROOF_OK; N+1 == N+2: 20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399; ambos com 23.037 bytes.
- Memória N → N+1: heap pico 55222251 B (52.66 MiB), RSS pico 68231168 B (65.07 MiB).
- Memória N+1 → N+2: heap pico 55415537 B (52.85 MiB), RSS pico 68435968 B (65.27 MiB). Limite de heap rastreado: 256 MiB.
- Prova armazenada em artifacts/bootstrap/proof/proof.json e nos relatórios memory_n_to_n1.json / memory_n1_to_n2.json; log: build/bootstrap-proof-0.8.44.log.
## 0.8.43 — limites explícitos do encoder GP-IR

- Adicionada regressão com arquivo GP-IR esparso de 64 MiB + 1 byte, confirmando rejeição pelo tamanho antes da leitura/alocação do payload.
- Adicionada regressão para JSON truncado/malformado, garantindo que nenhum arquivo GGPC seja publicado.
- Os dois testes direcionados passaram no Android/Termux.
- make validate: exit 0; make check, corpus 6/6 (frontend_supported, direct_legacy_exact, frontend_bootstrap_exact, native_runner_exact, native_encoder_exact e python_c_semantic), 201 testes, fuzz 64 casos (37 rejeições, 27 aceitos, zero divergências), hashes dos 38 arquivos do corpus e git diff --check aprovados.
- Relatório desta execução: build/validate-0.8.43.log; código de saída: build/validate-0.8.43.exit (0).
## 0.8.42 — menor memória JSON e entrada adversarial do encoder

- O decodificador de strings JSON agora reserva n+1 bytes, pois a expansão de escapes JSON para UTF-8 nunca supera o comprimento bruto da string escapada; antes reservava até 4n+1.
- Adicionada regressão de GP-IR com Unicode escapado (incluindo caracteres multibyte) e comparação semântica com o encoder de referência.
- Adicionada regressão para chave duplicada aninhada em instrução e para entrada JSON com byte UTF-8 inválido.
- Os três testes focados passaram no Termux/Android ARM64.
- A alteração deve ser validada pela suíte integral nesta revisão; nenhum resultado de ciclos anteriores é atribuído a ela.
## 0.8.41 — publicação segura do encoder nativo

- O gravador atômico deixou de usar nome temporário previsível baseado no PID e fopen("wb").
- Temporários agora são criados de forma exclusiva por mkstemp, com permissão inicial 0600, evitando seguir ou truncar temporário preexistente.
- Escrita em loop trata chamadas parciais e EINTR; fsync ocorre antes do fechamento e rename publica somente após a gravação completa.
- Falhas ao escrever, sincronizar, fechar ou publicar removem o temporário criado pela operação.
- Dois testes novos validam a permissão restrita da saída e a limpeza do temporário quando rename falha; os cinco testes focados do encoder passaram.
- Compilação C com -Wall -Wextra -Wpedantic aprovada no Termux/Android ARM64.
- A validação integral será executada após esta alteração; não atribuir os resultados de 194 testes anteriores à revisão atual sem repetir a suíte.
## 0.8.40 — encoder GGPC nativo e paridade de bootstrap

- Implementado em C o caminho --encode-ir: valida GP-IR v1, normaliza os campos para serialização canônica, produz GGPC v2 com zlib/CRC32 e grava a saída atomicamente.
- Integrado o encoder C ao CLI self-hosted quando a VM C é selecionada; a validação do documento não chama mais o encoder Python apenas como etapa intermediária.
- Mantidos encoder Python e adaptador como referência de compatibilidade e oráculo diferencial.
- Corpus diferencial: 6/6 casos com igualdade byte a byte entre encoder C e encoder Python.
- Testes cobrem paridade, rejeição de GP-IR inválido sem publicar saída e seleção do encoder nativo pelo CLI.
- make validate: 194 testes; corpus 6/6; fuzz 64 iterações (37 rejeições, 27 aceitas, zero divergências); hashes dos fixtures e git diff --check aprovados.
- make bootstrap-proof: N → N+1 → N+2 aprovado na VM C; N+1 e N+2 têm SHA-256 idêntico: 20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399.
- Relatórios de memória dos dois estágios persistidos em artifacts/bootstrap/proof/; pico de heap rastreado de 56,78 MiB e 57,22 MiB, abaixo do teto de 256 MiB.
- A prova cobre o frontend bootstrap e não demonstra autossuficiência integral do toolchain; bootstrap e hidratação Python permanecem.
# Changelog

## 0.8.39 — memória por grupos e telemetria do bootstrap

- Separadas as alocações rastreadas em buffers nativos, objetos gerenciados pelo GC e pilhas de operandos, com contadores de bytes vivos e picos por grupo.
- Mantido o teto global de 256 MiB; a soma dos grupos vivos é verificada por teste de regressão.
- A prova N → N+1 → N+2 agora salva relatórios de memória independentes para as execuções N → N+1 e N+1 → N+2, além dos hashes dos artefatos.
- Os picos de cada grupo são máximos independentes e não devem ser somados; o total global continua sendo a métrica autoritativa do limite.
- O relatório também mede o RSS atual via procfs e o pico de RSS via getrusage, separando memória residente do heap rastreado pela VM.
- O timeout de cada estágio nativo do bootstrap agora é configurável; a ferramenta usa 600 s por estágio, invalida provas antigas antes de iniciar e publica o JSON final atomicamente.
- Validação final no Termux/ARM64: 191 testes aprovados; corpus diferencial 6/6; fuzz determinístico 64/64 sem divergências (37 rejeições e 27 execuções aceitas).
- Bootstrap nativo N → N+1 → N+2 aprovado; N+1 e N+2 geraram SHA-256 idêntico: 20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399.
- Picos medidos: heap 56,78 MiB e RSS 68,31 MiB em N → N+1; heap 57,22 MiB e RSS 67,76 MiB em N+1 → N+2.

## 0.8.38 — indexação linear da VM e bootstrap reproduzível

- A VM C pré-indexa os tokens das instruções de cada bloco uma vez e executa por acesso direto; blocos pequenos usam buffer local para evitar alocação adicional.
- A validação do schema percorre instruções linearmente e confere limites/avanço dos tokens antes de acessar o índice.
- Comparação Android ARM64/Termux com a VM anterior, 2 aquecimentos e 9 repetições, usando tempo de CPU do processo: loop de 12.000 iterações 1,88x mais rápido; bloco com 320 declarações 1,45x mais rápido. Relatório: `build/gp-next-cycle/indexing-benchmark.json`.
- Corrigida validação de `MAKE_TYPED_ARRAY` que usava o nome do tipo depois de liberar o buffer; incluído teste que injeta tipo incompatível no bytecode.
- Tornada segura a expansão de ambientes sob falta de memória: cada `realloc` confirmado atualiza imediatamente o ponteiro e a definição de variável só é confirmada após todas as cópias.
- `make validate`: 189/189 testes, corpus diferencial 6/6, fuzz 64 casos sem divergências, hashes dos fixtures e `git diff --check` aprovados.
- Prova de bootstrap nativo N → N+1 → N+2 concluída; N+1 e N+2 têm SHA-256 idêntico (`20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`).
- A GP continua experimental: a prova de bootstrap do frontend não elimina a dependência do bootstrap/adaptador Python em todas as etapas do toolchain e não declara a versão 1.0.

## 0.8.37 — Otimização da indexação textual e orçamento de memória

- A VM C mantém cache por instância para caracteres ASCII usados por indexação; leituras repetidas reutilizam o mesmo objeto gerenciado.
- Strings ASCII usam indexação direta por byte. Textos não ASCII continuam indexados por pontos de código UTF-8, preservando acentos e emojis.
- A indexação UTF-8 deixou de calcular o comprimento completo antes de localizar o caractere, fazendo uma única travessia para textos Unicode.
- O orçamento de 256 MiB agora contabiliza também o cabeçalho do alocador interno; o relatório informa objetos gerenciados alocados.
- Regressão com 5.000 indexações ASCII comprova reutilização limitada de objetos; testes Unicode, GC e memória preservados.
- make validate: exit 0; 186/186 testes em 69,139 s; corpus diferencial 6/6; fuzz 64 casos (37 rejeitados, 27 aceitos/executados, zero divergências); 38/38 hashes dos fixtures; git diff --check aprovado.
- A prova N -> N+1 -> N+2 não foi concluída neste ciclo. A autocompilação integral continua pendente; não declarar GP 1.0.

## 0.8.36 — Entrada explícita do host e runner nativo

- Criada entrada_fonte() e canal de texto explícito do host nas VMs Python e C, com limite de 16 MiB e validação UTF-8.
- Removida a interpolação da fonte-alvo como código dentro do runner auto-hospedado.
- Runner do frontend GP executável pela VM C via --runner-vm native.
- Parser auto-hospedado aceita chamadas como comandos independentes e terminadores opcionais de blocos; a semântica aceita lista vazia compatível em atribuições e construtores nomeados.
- Montagem do runner corrigida para preservar quebras de linha reais.
- Artefato bootstrap reutilizável: GGPC v2, 23.014 bytes, manifesto/hash ligado a nove fontes.
- make validate: 185/185 testes, corpus 6/6 nas quatro comparações, fuzz 64 casos sem divergências, 38 hashes e git diff --check aprovados.
- A prova N -> N+1 -> N+2 foi tentada até 100 milhões de instruções, mas a VM C atingiu o teto padrão de heap de 256 MiB durante a autocompilação e não emitiu N+1. A expansão experimental do limite foi revertida após falhar nos testes da VM. A autohospedagem integral não está comprovada.
## 0.8.35 — Paridade do lowering condicional

- O parser bootstrap agora representa explicitamente a ausência de senao como None, distinguindo-a de senao {} vazio.
- Lowerer Python, análise semântica, backend C e interpretador bootstrap foram alinhados a essa distinção; condicionais sem ramo alternativo não geram salto final redundante.
- Novo teste compara estruturalmente o GP-IR do frontend GP e do bootstrap em três formas de condicional, incluindo função, execução do bytecode e interpretação bootstrap.
- Corpus regenerado: 6/6 fontes aceitas pelo frontend GP, encoder direto/legado idêntico em 6/6 casos, frontend/bootstrap byte-idênticos em 6/6 e equivalência semântica Python/C em 6/6.
- Validação Android ARM64: 164 testes aprovados em 221,169 s; make check aprovado; fuzz de 64 casos (37 rejeições, 27 execuções, zero divergências); 38 hashes do corpus aprovados.
- Adicionado e executado com sucesso o alvo sequencial make validate: check, corpus diferencial, 164 testes, fuzz de 64 casos, SHA-256 e git diff --check passaram em 230,50 s.
- O adaptador Python e o bootstrap permanecem como compatibilidade/oráculo. A autohospedagem integral ainda não está concluída.

## 0.8.34 — Inicializadores nomeados e incremento de para

- O parser GP reconhece construtores nomeados, como Pessoa{nome: "Ana", idade: 37}, criando nós AST específicos para cada campo.
- A análise semântica rejeita campos desconhecidos, duplicados, ausentes e valores com tipos incompatíveis; a geração de GP-IR organiza os valores pela ordem do schema declarado.
- A cláusula de incremento de para distingue chamadas de função de atribuições e preserva as formas existentes de incremento.
- O corpus diferencial contém seis fontes aceitas diretamente pelo frontend GP; os seis bytecodes diretos são idênticos aos do encoder legado e as seis saídas coincidem entre as VMs Python e C.
- Na validação 0.8.34, ainda havia diferença estrutural entre o lowering GP e o bootstrap em control_flow_nested.gp; corrigida e coberta por regressão no ciclo 0.8.35.
- O bootstrap Python e o adaptador legado continuam preservados; GP não é declarado integralmente auto-hospedado.

## 0.8.33 — Encoder direto do GP-IR canônico

- Adicionado validate_canonical_ir, validador de GP-IR JSON v1 que não materializa dataclasses de runtime.
- Adicionado encode_canonical_ir(document), que gera GGPC v2 diretamente do envelope canônico sem criar IRProgram/IRFunction.
- Preservada a API pública encode(IRProgram); o encoder direto normaliza a ordenação dos campos e demonstra equivalência byte a byte com o encoder antigo.
- compile_source_selfhosted_document retorna o envelope canônico; o CLI --self-hosted codifica esse documento diretamente. A API compile_source_selfhosted segue compatível e retorna IRProgram.
- Adicionado corpus diferencial persistente com seis casos, bytecodes direto/legado/bootstrap, execução Python/C, manifesto e SHA-256; 6/6 encoder direto/legado byte-idênticos e 6/6 execuções Python/C coincidentes.
- Registradas limitações: quatro fontes aceitas pelo frontend auto-hospedado; dois fixtures usam GP-IR extraído de bytecodes dourados por sintaxe nomeada ainda não suportada; o lowering de controle aninhado difere em bytes do bootstrap embora a saída seja igual.
- make differential-corpus reproduz o corpus. Encoder antigo e adaptador não foram removidos.
- Validação final Android ARM64: 159 testes aprovados em 358,475 s; make check, fuzz de 64 casos (37 rejeições, 27 execuções, zero divergências), git diff --check e 38 hashes do corpus aprovados.

## 0.8.32 — Serializador GP-IR canônico nativo

- Frontend GP agora emite diretamente o envelope canônico GP-IR v1 com `main`, `functions`, parâmetros, retorno e schemas em `BUILD_STRUCT`.
- Criado serializador GP para instruções e schemas; o runner emite em paralelo o formato legado de registros e o novo objeto canônico.
- `compile_source_selfhosted` compara diferencialmente ambos os documentos e só retorna o novo IR quando a equivalência é exata.
- Criado decoder tipado do envelope canônico; a reconstrução das seções e metadados passa a ser responsabilidade do frontend GP. O adaptador de registros permanece apenas como referência de comparação/fallback.
- A serialização nativa ainda é uma etapa intermediária: o host decodifica o JSON canônico para os objetos de runtime e o encoder Python continua emitindo bytecode.
- Validação Android ARM64: 154 testes aprovados; `make check` aprovado; fuzz diferencial de 64 casos sem divergências.

## 0.8.31 — Formalização inicial do GP-IR

- Definido GP-IR v1 como versão de formato independente da versão do contêiner binário e da versão da linguagem.
- Adicionado validador central `validate_ir` e validação nas fronteiras do lowering, adaptador auto-hospedado e encoder.
- Adicionado `program.ir_version` ao IR serializado; leitores Python/C aceitam ausência em artefatos v2 históricos como GP-IR v1 e rejeitam versões explícitas desconhecidas.
- Mantido o adaptador Python como bootstrap; materialização integral em GP permanece trabalho aberto.
- Criada `docs/GP_IR_SPEC.md` (rascunho 0.1); `make check`, 152 testes e fuzz diferencial de 64 casos aprovados em Android ARM64, sem divergências.

## 0.8.30 — Limites de recursos e política de extensões v2
- Harness diferencial agora limita o processo C a 512 MiB de segmento de dados (RLIMIT_DATA), 3 s de CPU (RLIMIT_CPU) e timeout de parede configurável.
- RLIMIT_AS foi testado e descartado no Android: bloqueia o mapeamento CFI do linker Bionic antes da execução da VM. RLIMIT_DATA preserva esses mapeamentos e passou no Termux.
- Relatórios JSON são persistidos em build/fuzz-reports/latest.json; entradas que causarem divergência são salvas individualmente para reprodução.
- Makefile permite configurar FUZZ_REPORT.
- Política v2 formalizada: leitores ignoram propriedades desconhecidas no objeto raiz; produtores SHOULD usar prefixo x-; extensões não redefinem campos normativos. Mudanças incompatíveis exigem nova versão do contêiner.
- Regressão do harness: 64 casos, 37 rejeitados, 27 aceitos/executados, zero divergências com os limites ativos.
- Especificação BYTECODE_V2_SPEC.md atualizada para rascunho 0.7; ainda não congelada.

## 0.8.29 — Harness diferencial limitado para bytecode
- Criado ferramentas/fuzz_bytecode.py, um harness reproduzível que muta fixtures válidas e compara decoder/VM Python com a VM C.
- Limites explícitos: 1–512 iterações, timeout nativo de 0,1–5 s, fixtures até 2 MiB e VM Python com 1 milhão de passos.
- O harness suporta mutações inválidas de bytes/cabeçalho e mutações válidas de reordenação JSON, whitespace e campo de extensão.
- Lote verificado: seed 0x47505632, 64 iterações, 37 rejeições, 27 execuções aceitas e zero divergências.
- Makefile ganhou o alvo make fuzz-bytecode e make check passou a incluir ferramentas/*.py.
- Política observada: ambos os loaders atualmente toleram propriedades extras no envelope JSON raiz; ainda não é garantia normativa.
- Especificação v2 atualizada para rascunho 0.6. O formato continua experimental.

## 0.8.28 — Fuzz smoke determinístico de loaders
- Adicionado teste diferencial de 48 mutações de bit sobre as seis fixtures v2, com PRNG seed fixo 0x47505632 e oito casos por binário.
- Decoder Python e VM C ARM64 rejeitaram todos os 48 artefatos mutados; a bateria de 66 mutações estruturais também continuou verde.
- Corpus positiva mantém cobertura de 32/32 opcodes e seis binários SHA-256 verificados.
- Especificação BYTECODE_V2_SPEC.md atualizada para rascunho 0.5, documentando o fuzz smoke e seus limites.
- Validação integral: 139 testes aprovados em 107,417 s; make check, compilação otimizada ARM64 e verificação da corpus aprovados.

Próxima etapa: fuzzing guiado por cobertura ou harness com limites explícitos, ampliação de casos de fronteira e ensaios em outra arquitetura antes de congelar v2.

## 0.8.27 — Cobertura positiva completa dos opcodes v2
- Corpus dourada ampliada para seis binários; nova fixture opcode_catalog.gbc exercita os 32/32 opcodes reconhecidos pelo decoder.
- Teste diferencial confirma SHA-256, versão, stdout idêntico e código de saída nas VMs Python e C ARM64; a própria suíte falha se um opcode permitido deixar de aparecer na corpus.
- Matriz determinística ampliada para 66 mutações inválidas (11 por seed em seis fixtures), todas rejeitadas igualmente pelos dois loaders.
- Especificação BYTECODE_V2_SPEC.md revisada para rascunho 0.4; o formato permanece experimental e não congelado.
- Validação integral no Termux/Android ARM64: 138 testes aprovados em 104,681 s; make check, build otimizado C e hashes das fixtures aprovados.

Próxima etapa: fuzzing aleatório/guiado por cobertura limitado, policy de extensões/versões e testes de conformidade para arquiteturas além de ARM64 antes do congelamento v2.

## 0.8.26 — Mutação diferencial de bytecode v2
- Adicionada uma matriz determinística de 55 corrupções aplicadas aos cinco binários dourados (11 mutações por seed).
- Python e VM C ARM64 rejeitam os mesmos casos: cabeçalho curto, zlib truncado/residual, assinatura/versão/tamanho/CRC inválidos, deflate corrompido, chave JSON duplicada, opcode desconhecido e args com forma inválida.
- Teste diferencial exige a mesma decisão de aceitação/rejeição dos loaders; não compara textos de erro que podem ser específicos de cada runtime.
- Especificação v2 revisada para rascunho 0.3 com a matriz de mutação e o limite de cobertura (não substitui fuzzing).
- Validação integral: 138 testes aprovados em 107,175 s; make check, compilação otimizada ARM64 e git diff --check aprovados.

Próxima etapa: ampliar fixtures positivas para cada opcode e acrescentar fuzzing determinístico/aleatório limitado; decidir política de extensões antes de congelar a especificação v2.

## 0.8.25 — Fixtures binárias douradas e paridade entre VMs
- Criada a corpus imutável tests/fixtures/bytecode_v2 com cinco fontes GP e cinco arquivos .gbc de referência: aritmética, controle de fluxo aninhado, função recursiva, estruturas/campos e texto Unicode.
- SHA-256 e tamanhos dos cinco binários registrados em SHA256SUMS; as fixtures são entradas de teste e não são recompiladas no teste de conformidade.
- Novo teste diferencial executa exatamente os mesmos bytes na VM Python e na VM C ARM64, verifica a integridade dos hashes e compara stdout e código de saída.
- Especificação preliminar BYTECODE_V2_SPEC.md revisada para rascunho 0.2 com a corpus e suas saídas esperadas.
- Validação integral no Termux/Android ARM64: **137 testes aprovados** em 107,352 s, incluindo a nova corpus. make check e build otimizado da VM C aprovados.

**Próxima etapa:** fuzzing diferencial dos loaders e execução, ampliar a corpus para todos os opcodes, decidir política de extensões e congelar a especificação somente após as evidências adicionais.

## 0.8.24 — Hardening de loaders e contêiner bytecode v2
- Backpatch bootstrap agora valida índice, opcode e destino antes de modificar uma instrução; regressões cobrem destino final e loops aninhados com quebrar/continuar em funções.
- Loaders Python/C agora validam tipos e aridade de todos os opcodes conhecidos, constantes escalares finitas, DECLARE, BUILD_STRUCT, schemas, parâmetros, retornos e versões de linguagem.
- Cabeçalho binário exige versão externa/interna coerente; decoder Python exige raiz objeto, versão estritamente inteira e mantém leitura compatível do JSON experimental v1.
- Limites Python/C alinhados: payload descomprimido de 64 MiB, arquivo comprimido de 128 MiB, 2 milhões de tokens e profundidade JSON 512.
- Ambos os loaders rejeitam chaves JSON duplicadas, escapes inválidos, caracteres de controle não escapados, NUL, surrogates isolados e constantes JSON não padrão.
- Loader C usa inflate com validação do stream completo; bytes residuais após zlib são rejeitados, alinhando o comportamento com o decoder Python.
- Especificação preliminar BYTECODE_V2_SPEC.md criada como rascunho 0.1; formato permanece experimental e não congelado.
- Validação integral no Termux/Android ARM64: 136 testes aprovados; make check e compilação otimizada da VM C aprovados.

**Próxima etapa:** gerar fixtures binárias de referência, acrescentar testes diferenciais/fuzzing cross-runtime, decidir a política de extensões e congelar formalmente a especificação antes de declarar bytecode estável.

## 0.8.23 — Auditoria de fluxo de controle e validação de bytecode
- Backpatcher do compilador bootstrap agora valida índice, tipo de instrução e destino antes de substituir o operando; destinos de saída no limite len(code) continuam válidos.
- Contrato de execução confirmado: as VMs incrementam o IP antes da instrução e aplicam saltos como índices absolutos dentro do bloco; len(code) representa saída.
- Loader C deixou de converter operandos de salto/contagem por strtod sem validação lexical; booleanos, frações e notação exponencial são rejeitados onde o contrato exige inteiro JSON.
- Decoder Python valida destinos, contagens de arrays/saída e argumentos de chamadas como inteiros JSON reais, não booleanos ou floats.
- Decoder Python rejeita raiz JSON não objeto, versão booleana/não inteira e divergência entre versão do cabeçalho binário e versão interna. A leitura compatível do bytecode JSON experimental v1 foi preservada.
- Regressões cobrem backpatch inválido, laços aninhados, quebrar/continuar, saltos dentro de funções, destinos booleanos/decimais, raiz JSON malformada e versões divergentes.
- Validação integral no Termux/Android ARM64: 120 testes aprovados em 114,507 s. make check, compilação da VM C com warnings e verificações Python aprovados.

Próxima etapa: completar a validação estrutural por opcode (tipos de todos os operandos, schemas, parâmetros e constantes), escrever a especificação formal do formato GP bytecode v2 e expandir testes de compatibilidade adversarial. A versão continua experimental, não está declarada estável.

## 0.8.22 — Emissão direta de IR tipado pelo frontend GP
- Todos os pontos de lowering do frontend GP agora criam registros `InstrucaoIR_GP` diretamente, incluindo constantes, operações, saltos, declarações, chamadas e instruções de retorno/saída.
- Metadados de funções (`FUNCTION/PARAM/CODE_BEGIN/CODE_END`) e esquemas de estruturas (`STRUCT/STRUCT_FIELD`) também são construídos como registros tipados, sem serialização intermediária em linhas `OPCODE|campo`.
- Removidos o emissor textual `emitir_ir_gp`, a ponte `registro_ir_de_texto_gp` e o helper de extração de sufixos usado exclusivamente por essa conversão.
- O serializador JSON continua emitindo o contrato estruturado consumido pelo adaptador Python; o leitor de IR textual legado permanece isolado para compatibilidade.
- Parser validado na VM Python e na VM nativa ARM64; testes de listas de estruturas, passagem por funções, recursão e constantes escapadas aprovados.

**Próxima etapa:** mover para GP a materialização de `IRProgram/IRFunction` atualmente feita pelo adaptador Python e avançar na compilação reproduzível sem depender do bootstrap Python.

## 0.8.21 — IR interno representado por registros GP tipados
- Introduzida a estrutura `InstrucaoIR_GP`, com campos separados para opcode, operandos textuais, valores numéricos e valores lógicos.
- Instruções do programa, metadados de funções e metadados de estruturas passam a ser armazenados em listas tipadas de `InstrucaoIR_GP`, sem manter linhas de IR como representação interna principal.
- A validação de registros, a resolução de rótulos e a serialização JSON agora leem os campos tipados; destinos de salto deixam de ser reescritos por concatenação textual.
- O JSON emitido mantém o contrato consumido pelo adaptador Python, incluindo números, booleanos, nulo e literais de texto.
- Diagnósticos e autotestes do frontend passaram a exibir registros como arrays JSON. Os testes extensos do parser receberam orçamento específico de 5 milhões de passos, sem alterar o limite padrão das VMs.
- Validação integral no Android ARM64: **111 testes aprovados**; compilação sintática do código C e verificações Python aprovadas.

**Limite conhecido:** os pontos de lowering ainda montam algumas instruções como texto delimitado por `|` e usam `registro_ir_de_texto_gp` como ponte transitória para criar os registros tipados. A próxima etapa é emitir `InstrucaoIR_GP` diretamente nesses pontos e remover essa conversão; depois, transferir gradualmente a materialização de `IRProgram/IRFunction` do adaptador Python para GP.

## 0.8.20 — Validação do contrato de IR no frontend GP
- O frontend GP valida os registros finais do envelope antes de declarar a geração de IR como concluída.
- A validação confere opcode permitido, quantidade de campos por instrução, presença de metadados, tipos de constantes e campos inteiros decimais não negativos.
- Cabeçalho ausente/duplicado, opcode desconhecido, contagem/destino malformado e constantes lógicas/nulas/textuais inválidas são rejeitados na origem.
- O adaptador Python continua validando o protocolo de forma independente, mantendo defesa em profundidade antes de construir IRProgram/IRFunction.
- Autotestes do frontend cobrem opcode desconhecido, operando numérico inválido, constante lógica inválida e cabeçalho duplicado.
- Validação integral: 111 testes passaram; exemplos com estruturas/listas, laços e constantes tipadas executaram pelo frontend auto-hospedado; VM C ARM64 recompilada.

**Limite:** os registros internos de IR ainda são linhas delimitadas por `|` e a validação GP ainda não substitui a construção tipada de IRProgram no adaptador Python. A próxima etapa é substituir progressivamente essas linhas por registros GP com campos tipados.

## 0.8.19 — Construção direta do IR estruturado
- O adaptador estruturado percorre arrays JSON diretamente e constrói IRInstruction/IRFunction sem recompor registros delimitados por pipe.
- A validação tipada exige inteiros JSON reais para contagens e destinos; booleanos e números em formato textual são rejeitados nesses campos.
- O leitor legado textual converte seus tokens em sua própria fronteira de compatibilidade e compartilha o construtor tipado, sem ser usado pelo caminho --self-hosted.
- Cabeçalho de protocolo valida a versão como inteiro estrito; regressões cobrem booleano no cabeçalho, número textual e compatibilidade do envelope antigo.

**Limite:** o IR tipado ainda é materializado pelo adaptador Python. A próxima redução de dependência exige representar instruções e operandos tipados na própria GP e mover para ela as validações de protocolo.

## 0.8.18 — Operandos tipados no protocolo de IR
- O serializador GP agora emite números e contagens do IR como inteiros JSON, constantes decimais como números JSON, valores lógicos como booleanos e nulo como null; textos são strings JSON efetivas.
- O adaptador estruturado valida os tipos de acordo com o opcode e sua posição: contagens e destinos exigem inteiros não negativos, constantes respeitam o tipo declarado e números não finitos são rejeitados.
- A conversão continua centralizando as verificações existentes de opcode, operandos, esquemas de estruturas, funções e alvos de salto.
- Teste de execução na VM C ARM64 cobre constante decimal, booleano e texto com separador e quebra de linha.

**Limite:** identificadores, tipos, nomes de função e outros metadados continuam sendo strings, conforme o contrato. O adaptador Python ainda converte os registros para IRProgram; a migração da validação e do IR tipado para GP continua pendente.

## 0.8.17 — Transporte estruturado de IR
- O frontend GP agora serializa os registros de IR como um único documento JSON composto por arrays de campos, com escape de aspas, barras invertidas, tabulações e quebras de linha.
- O driver deixou de interpretar a representação textual de listas do Python com literal_eval; agora decodifica JSON e valida listas, campos e tipos de registro antes da adaptação.
- Novo adaptador structured_ir_to_program reutiliza as validações rigorosas de opcode, operandos, esquemas, funções e destinos de salto; o leitor textual anterior permanece disponível para compatibilidade e testes legados.
- Regressões cobrem protocolo estruturado, registros malformados, campos não textuais e payloads de texto com pipes e escapes.

**Limite:** o protocolo estruturado ainda transporta campos como strings e o adaptador Python ainda faz a conversão para IRProgram tipado. Próximo passo: emitir operandos tipados no protocolo GP e mover a validação/normalização para código GP, reduzindo outra camada Python.

## 0.8.16 — Módulos locais no backend auto-hospedado
- O modo --self-hosted agora expande imports locais de módulos com alias antes de executar o frontend escrito em GP.
- Declarações de funções importadas e chamadas internas recebem namespace privado; chamadas alias.funcao(...) são reescritas para o identificador de namespace correspondente.
- Cabeçalho opcional programa é removido na preparação para o parser GP, mantendo o restante do fonte sob análise do frontend auto-hospedado.
- Resolução relativa ao arquivo principal, rejeição de arquivo ausente, alias duplicado, declaração não suportada e importação que não ocupa linha própria.
- Testes de integração validam módulo local, chamadas entre funções do módulo e falhas de resolução/alias.

**Limites:** módulos seguem restritos a funções e não aceitam imports aninhados, estruturas exportadas, dependências externas ou import em linha compartilhada. O carregamento e a reescrita de namespace ainda são uma etapa Python de preparação; lexer, parser, semântica e IR da fonte expandida continuam executados pelo frontend GP. A compilação integral sem bootstrap Python permanece pendente.

## 0.8.15 — Validação dos elementos de listas em campos
- Corrigida a análise semântica de campos lista<T>: o formato genérico não é mais aceito sem validar T como primitivo ou estrutura declarada/forward declarada.
- Regressão rejeita lista<Fantasma> em campo de estrutura.
- Testes de integração combinam listas de estruturas com indexação, leitura/alteração de campos, enquanto, continuar e quebrar nas VMs Python e C ARM64.
- O runner do frontend auto-hospedado recebe orçamento independente de 5 milhões de instruções para executar os próprios testes e transformações do compilador; o limite do programa GP gerado permanece inalterado.
- Exemplo executável em exemplos/autohospedado_listas_em_lacos.gp.

## 0.8.14 — Listas tipadas em funções e estruturas
- Parser GP aceita parâmetros e retornos na forma lista Tipo e registra o tipo canônico lista<T> nas assinaturas.
- Análise semântica valida a identidade do tipo de elemento para argumentos, retornos, declarações, listas de estruturas e campos lista<T>.
- VM Python reconhece lista<T>, verifica seus elementos e preserva o alias da lista tipada recebida por parâmetro.
- VM C ARM64 valida lista<T> recursivamente e associa o tipo de elemento ao parâmetro, preservando a mutação compartilhada e a validação de adicionar/SET_INDEX.
- Frontend auto-hospedado suporta listas de estruturas, acesso a campos através de indexação, campos de estruturas que armazenam listas e funções que recebem/devolvem lista<T>.
- O runner agora transporta a listagem textual do IR em um registro agregado, evitando percorrer o vetor de instruções por indexação dinâmica na própria GP durante a saída do runner.
- Testes cobrem parâmetros/retornos lista<numero>, parâmetros/retornos lista<estrutura>, campos lista<estrutura>, rejeição de argumentos e retornos com tipo incompatível nas VMs Python/C.

**Limites:** listas de listas, listas de estruturas com aninhamento recursivo por referência, imports locais de módulos no backend auto-hospedado já são expandidos para módulos de funções; bibliotecas padrão expandidas ainda exigem lowering próprio.

## 0.8.13 — Estruturas no backend auto-hospedado
- O frontend GP emite metadados de esquema STRUCT/STRUCT_FIELD antes do código executável.
- Construtores posicionais são baixados para BUILD_STRUCT; o adaptador associa o nome e a quantidade ao esquema validado de campos.
- Leitura e atribuição de campos geram GET_FIELD/SET_FIELD, incluindo acesso encadeado.
- Estruturas podem ser declaradas aninhadas e passadas como parâmetros de funções; VM Python e VM C ARM64 executam os mesmos bytecodes.
- Testes rejeitam metadados incompletos, construtores sem esquema e validam construtores, mutação, argumentos de função e estruturas aninhadas.

**Limites:** arrays de estruturas, campos lista<T>, parâmetros lista<T> e convenções de módulos no backend auto-hospedado ainda exigem lowering específico.

## 0.8.12 — Controle de laços no backend auto-hospedado
- quebrar gera salto para o fim do laço ativo mais interno.
- continuar em enquanto retorna à condição; em para, salta para a atualização antes de reavaliar a condição.
- Pilha de destinos usa slots por profundidade com limite explícito de 128 laços aninhados, evitando reutilização de alvos obsoletos entre laços sequenciais.
- Testes cobrem enquanto, para, laços aninhados, laços de tipos diferentes em sequência, funções com seus próprios laços e o bytecode resultante na VM C ARM64.

**Limites:** o runtime atual ainda não cria escopos lexicais de bloco no bytecode; variáveis declaradas dentro de blocos repetidos devem ser declaradas antes do laço e atualizadas dentro dele. Estruturas/campos e parâmetros lista<T> ainda não estão conectados ao backend auto-hospedado.

## 0.8.11 — Arrays tipados e indexação no backend auto-hospedado
- Gerador GP agora baixa literais ARRAY para BUILD_ARRAY, indexação para GET_INDEX e atribuição por índice para SET_INDEX.
- Declarações lista<T> emitem MAKE_TYPED_ARRAY e DECLARE com tipo de elemento, alinhados ao ABI do Lowerer existente.
- Chamadas de tamanho/adicionar/remover usam CALL para os builtins existentes da VM; atribuições que atualizam listas tipadas mantêm a validação de elemento.
- Testes cobrem arrays preenchidos/vazios, mutação por índice, builtins de coleção, texto indexado e execução do bytecode gerado na VM C ARM64.
- VM C agora clona o contêiner em MAKE_TYPED_ARRAY, alinhando-se à cópia feita por GPTypedArray no Python e evitando que declarar o resultado de adicionar altere indevidamente a lista fonte.
- Regressões nas VMs Python e C garantem a independência da cópia tipada após remover; exemplo reproduzível em exemplos/autohospedado_arrays.gp.

**Limites:** construtores e valores de estruturas, atribuição/acesso a campos, quebrar/continuar e parâmetros de função do tipo lista ainda precisam de lowering/convenções específicas no frontend GP.

## 0.8.10 — Ponte do IR auto-hospedado para bytecode v2
- Novo adaptador estrito transforma o envelope textual GP-IR|1 em IRProgram/IRFunction tipados, preservando parâmetros, retornos, chamadas e alvos de salto.
- O CLI oferece --self-hosted: o frontend escrito em GP analisa a fonte alvo, gera seu IR, e o adaptador entrega a representação ao serializador binário v2.
- Funções recursivas com condicionais são compiladas e executadas em bytecode; teste de integração valida o mesmo arquivo na VM Python e na VM C nativa.
- Constantes de texto JSON (incluindo separadores e escapes), números, valores lógicos e nulos são convertidos; o adaptador rejeita metadados, operandos e saltos inválidos.
- Subconjunto atual: declarações escalares, expressões suportadas, mostrar, se/senao, enquanto, para e funções/chamadas/retornos.

**Limites:** o runner do frontend ainda é compilado pelo bootstrap Python e executado pela VM de referência Python; a conversão do envelope textual para IRProgram também é Python. Construtores/estruturas, campos e quebrar/continuar ainda não entram no backend auto-hospedado; arrays tipados e indexação foram adicionados em 0.8.11. Isso é auto-hospedagem parcial, não compilação integral do compilador por ele mesmo.

## 0.8.9 — Funções no IR auto-hospedado
- Declarações de função são extraídas do fluxo principal e emitidas em seções próprias FUNCTION/PARAM/CODE_BEGIN/CODE_END.
- Parâmetros preservam tipo e nome; cabeçalho registra nome, tipo de retorno e quantidade de parâmetros.
- Chamadas em expressões geram CALL com nome e quantidade de argumentos; retornar gera expressão/valor nulo seguido de RETURN.
- Cada corpo de função recebe sua própria resolução de rótulos, separada dos endereços do programa principal.
- Testes cobrem soma de dois parâmetros e função fatorial recursiva com se/senao, chamada recursiva e saltos locais nas VMs Python e C.

**Limites:** nesta etapa as seções ainda eram apenas um envelope textual; a ponte para IRFunction e bytecode v2 foi adicionada em 0.8.10. Chamadas qualificadas por módulo, construtores de estruturas, arrays e atribuições por índice/campo ainda não estão no lowering auto-hospedado.

## 0.8.8 — Resolução de rótulos do IR
- Adicionada resolução em duas passagens para LABEL, JUMP e JUMP_IF_FALSE.
- Rótulos simbólicos são removidos da listagem final e saltos passam a conter endereços absolutos contados sem metadados.
- Validação rejeita rótulos duplicados, destinos inexistentes e rótulos vazios.
- Corrigida conversão de números para texto: o quociente decimal agora é calculado por subtração inteira, evitando índices fracionários em endereços acima de 9.
- Testes verificam destinos numéricos maiores que um dígito e falhas de referência nas VMs Python e C nativa.

**Limites:** o resultado ainda é uma listagem textual com cabeçalho próprio, não o IR serializável consumido pelo compilador; assinatura e operandos das instruções ainda precisam ser normalizados antes de alimentar o bytecode.

## 0.8.7 — Controle de fluxo no IR auto-hospedado
- Gerador em GP agora baixa nós SE/SENAO, ENQUANTO e PARA para IR textual.
- Saltos condicionais e incondicionais usam rótulos simbólicos LABEL/JUMP_IF_FALSE/JUMP, permitindo resolução posterior sem mutação de instruções já emitidas.
- Laços PARA tratam inicialização, condição e atualização, inclusive cláusulas vazias; inicialização declarativa é suportada.
- Testes verificam o fluxo emitido pelas VMs Python e C nativa.

**Limites:** rótulos já são resolvidos em endereços numéricos; quebrar/continuar, funções, chamadas, arrays e estruturas ainda não foram baixados pelo gerador auto-hospedado.

## 0.8.6 — Primeiro gerador de IR auto-hospedado
- Adicionado gerador de IR textual em GP, com cabeçalho GP-IR versão 1.
- Lowering inicial de literais, identificadores, agrupamentos, operadores unários/binários, declarações, atribuições simples e mostrar.
- Emissão de instruções de pilha determinísticas: CONST, LOAD, NOT, NEG, operações aritméticas/comparativas/lógicas, DECLARE, STORE e PRINT.
- Testes validam a listagem IR nas VMs Python e C nativa.
- make check, make test (58 testes), make native-vm e git diff --check concluídos com sucesso.

**Limites:** IR textual ainda não é bytecode binário; chamadas, funções, controle de fluxo, arrays, estruturas, atribuições indexadas/campos e integração com serializador ainda não foram implementados no gerador auto-hospedado.

## 0.8.5 — Verificação de retorno em todos os caminhos
- Analisador de fluxo identifica retorno direto, blocos sequenciais e ramos completos de se/senao.
- Funções com tipo de retorno não vazio são rejeitadas quando algum caminho pode terminar sem retornar.
- Laços não são considerados garantia de retorno, pois podem executar zero vezes.
- Testes Python e C nativa cobrem retorno em todos os ramos, ramo ausente e retorno apenas dentro de laço.
- make check, make test (58 testes), make native-vm e git diff --check concluídos com sucesso.

**Limites:** análise de fluxo ainda não detecta código inalcançável, nem prova invariantes de laços; o front-end auto-hospedado ainda não gera IR/bytecode.

## 0.8.4 — Análise semântica de estruturas e campos
- Registro prévio de estruturas/campos permite resolver referências a tipos definidos mais adiante no arquivo.
- Variáveis, parâmetros e retornos de funções aceitam tipos definidos pelo usuário e rejeitam tipos desconhecidos.
- Construtores posicionais validam quantidade de campos e tipo de cada valor.
- Acesso e atribuição a campos verificam existência e compatibilidade de tipos, inclusive em estruturas aninhadas.
- Duplicidade de estruturas/campos e tipos de campos desconhecidos são rejeitados.
- Testes Python e C nativa cobrem estruturas simples/aninhadas, parâmetros e retornos tipados, construtores e diagnósticos.
- make check, make test (58 testes), make native-vm e git diff --check concluídos com sucesso.

**Limites:** construtores usam ordem de declaração dos campos; listas como campos e ciclos entre estruturas por valor ainda não são suportados/validados; análise de retorno em todos os caminhos e integração com geração de IR seguem pendentes.

## 0.8.3 — Análise semântica de listas tipadas
- Parser auto-hospedado aceita declarações de listas tipadas com lista numero/texto/logico.
- Analisador valida homogeneidade de literais, tipo de índice e compatibilidade na atribuição por posição.
- Operações tamanho, adicionar e remover verificam assinatura, coleção e tipo do elemento.
- Testes Python e C nativa cobrem listas válidas, tipos heterogêneos, inserção incompatível, índice inválido e atribuição por posição.
- make check, make test (58 testes), make native-vm e git diff --check concluídos com sucesso.

**Limites:** a semântica auto-hospedada de estruturas, arrays de estruturas, parâmetros de função do tipo lista e análise completa de fluxo de retorno ainda está pendente.

## 0.8.2 — Análise semântica inicial de laços
- Analisador GP valida condições lógicas em enquanto e para.
- Escopo dedicado ao inicializador de para e validação da expressão de incremento.
- Contexto semântico impede quebrar/continuar fora de laços.
- Contexto de laços é isolado ao entrar em funções, evitando herança indevida do laço chamador.
- Testes nas VMs Python e C nativa cobrem laços válidos, controle aninhado e condições não lógicas.
- make check, make test (58 testes), make native-vm e git diff --check concluídos com sucesso.

**Limites:** arrays e estruturas ainda não têm cobertura semântica auto-hospedada completa; a análise de retornos ainda não prova retorno em todos os caminhos.

## 0.8.1 — Assinaturas e chamadas de função na análise semântica GP
- Análise em duas passagens registra assinaturas antes de analisar os corpos e comandos globais.
- Chamadas podem ocorrer antes da definição da função, sem perder suporte à recursão.
- Parâmetros são introduzidos no escopo da função e passam pela detecção de nomes duplicados.
- Chamadas verificam quantidade e tipo dos argumentos; retornos verificam compatibilidade com o tipo declarado.
- Corrigidos acessos fora dos limites em varreduras de texto: GP não avalia && com curto-circuito.
- Testes Python e C nativa cobrem múltiplos parâmetros, chamada antecipada, argumentos e retornos incompatíveis.
- make check, make test (58 testes), make native-vm e git diff --check concluídos com sucesso.

**Limites:** análise semântica auto-hospedada ainda não cobre estruturas, arrays, laços e análise de retorno em todos os caminhos; ainda não substitui o compilador bootstrap.

## 0.8.0 — Primeira análise semântica sobre AST GP
- Analisador semântico em GP integrado à AST produzida pelo parser auto-hospedado.
- Verifica declarações primitivas, tipos de literais/expressões, nomes, atribuições, condições e blocos.
- Escopos de blocos permitem sombreamento e rejeitam declarações duplicadas no mesmo escopo.
- Testes de aceitação/rejeição executados nas VMs Python e C nativa ARM64.
- Limitações: funções, parâmetros, estruturas, arrays e laços ainda não têm cobertura semântica completa.

## 0.7.9 — Tabela de símbolos auto-hospedada inicial
- Novo módulo semântico em GP com registros de símbolos e escopos hierárquicos.
- Cadeia de escopos pai/filho, rejeição de duplicatas locais e resolução de nomes com sombreamento.
- API para resetar, criar escopos, declarar/buscar símbolos e consultar tipos.
- Testes executados nas VMs Python e C nativa ARM64.

## 0.7.8 — Validação contextual de comandos
- Parser GP mantém profundidade de laços e funções durante a análise.
- quebrar e continuar são rejeitados fora de laços; retornar é rejeitado fora de funções.
- O contexto de laço externo não vaza para o corpo de uma função declarada dentro dele.
- Testes de integração Python/C cobrem os casos válidos e inválidos.
- make check, make test (56 testes), make native-vm e git diff --check concluídos com sucesso.

## 0.7.7 — Estruturas e controle de laços no parser GP
- Parser auto-hospedado agora representa declarações de estrutura e campos tipados na AST.
- Adicionados nós explícitos para quebrar e continuar, inclusive em blocos condicionais aninhados dentro de laços.
- Testes de integração verificam a construção da AST nas VMs Python e C nativa.
- make check, make test (56 testes), make native-vm e git diff --check concluídos com sucesso.

## 0.7.6 — Blocos e comandos estruturados no parser GP
- Parser auto-hospedado agora constrói nós BLOCO e SE para blocos e condicionais se/senao.
- Adicionado suporte sintático a enquanto e para, com inicialização, condição, incremento e cláusulas omitidas representadas por VAZIO.
- Adicionada representação de funções, parâmetros e retornar na AST.
- Comandos podem ser analisados recursivamente dentro de blocos, incluindo estruturas de controle aninhadas.
- Testes de integração validam as novas construções na VM Python e na VM C nativa.
- make check, make test (56 testes), make native-vm e git diff --check concluídos com sucesso.

## 0.7.5 — Metadados de posição nos nós AST
- NoAST_GP agora registra linha e coluna do cursor no momento da criação.
- Cursor do parser acompanha quebras de linha e colunas durante o consumo dos lexemas.
- API para consultar linha e coluna de um nó.
- Testes de integração mantidos nas VMs Python e C.

## 0.7.4 — AST hierárquica em GP
- AST passa a usar arena lista NoAST_GP, com nós tipados e referências de filhos por índice.
- Construção hierárquica de programa, declarações, atribuições, saída, literais, identificadores, operadores unários/binários, agrupamentos, chamadas, arrays, campos e índices.
- Parser valida precedência aritmética e lógica, argumentos e delimitadores; inclui rejeição de expressão inválida.
- Acesso aos campos dos nós usa variáveis locais tipadas, preservando a análise estática atual.
- Cobertura de integração nas VMs Python e C nativa.

## 0.7.3 — Primeiro parser escrito em GP
- Criado parser recursivo descendente em GP para declarações primitivas, mostrar(...), chamadas e expressões com precedência.
- Parser valida expressões e rejeita sintaxe inválida com diagnóstico inicial.
- Lexer convertido em módulo reutilizável; demonstração movida para exemplos/lexer_demo.gp.
- Testes de integração Python e VM C nativa: 56 testes aprovados.

## 0.7.2 — Validação da classificação lexical
- Corrigida a distinção entre delimitadores e operadores no classificador escrito em GP.
- Classificador agora reconhece somente operadores definidos pela linguagem e rejeita lexemas inválidos.
- Validação de identificadores e números decimais, incluindo rejeição de formas numéricas malformadas.
- Testes executados nas VMs Python e C nativa.
- make check, make test (54 testes) e make native-vm concluídos com sucesso.

## 0.7.1 — Classificação tipada no lexer auto-hospedado
- Adicionada classificação de lexemas em GP: palavra-chave, identificador, número, texto, operador e delimitador.
- `lexer_tipos_gp` retorna registros `TIPO:lexema`, mantendo `lexer_gp` compatível com a saída anterior.
- Execução validada na VM Python e na VM C nativa ARM64.
- Testes de regressão verificam as categorias geradas nas duas VMs.

**Limites:** tokens ainda não carregam linha/coluna; erros lexicais estruturados e parser em GP continuam pendentes.

## 0.5.2 — Coletor de lixo inicial da VM nativa
- Heap gerenciado para textos, arrays e estruturas da VM C.
- Coleta mark-and-sweep automática em limites seguros entre instruções.
- Rastreamento de raízes em globais, ambientes locais e pilhas de execução aninhadas.
- Marcação recursiva de valores contidos em arrays e estruturas; objetos inacessíveis e ciclos não alcançáveis podem ser recuperados.
- Métricas de ciclos, objetos liberados e bytes recuperados; opção `--gc-threshold BYTES` para testes e ajuste.
- Teste de estresse valida recuperação de arrays/textos temporários e preservação de array, estrutura e texto ainda alcançáveis em função.
- `make check` e `make test`: 54 testes aprovados na suíte completa.

**Limites:** coleta cobre os objetos de valor do runtime C (texto, array e estrutura); metadados, parser JSON e buffers auxiliares continuam no alocador rastreado geral. A gramática atual ainda limita certos grafos de objetos que podem ser construídos diretamente em GP.

## 0.5.1 — Robustez, UTF-8 e lexer GP
- Testes nativos de contagem e indexação Unicode (emoji e caracteres acentuados).
- Testes de medição do pico de memória da VM C.
- Loader Python rejeita payload comprimido cujo tamanho descomprimido exceda o declarado.
- Diagnósticos semânticos incluem caminho do arquivo, linha e coluna.
- Lexer GP ampliado com números decimais, strings com escapes e operadores compostos (==, !=, <=, >=, ->, &&, ||).
- Lexer validado nas VMs Python e C.
- Suíte de regressão ampliada para 53 testes aprovados.
- Benchmark Android ARM64: mediana de 0,2385 s na VM Python e 0,0912 s no processo nativo; aproximadamente 2,61x nesta carga. Inclui inicialização e carga do bytecode.

**Limitações conhecidas:** o coletor mark-and-sweep inicial cobre objetos de valor no runtime C, mas o gerenciamento de buffers auxiliares permanece separado; spans semânticos ainda não cobrem todas as transformações; o lexer GP não é ainda parser nem compilador auto-hospedado.

## 0.5.0 — Consolidação experimental Android/ARM64
- VM C nativa com loader de bytecode v2.
- Validação UTF-8, medição de memória e limpeza no encerramento.
- Diagnósticos com linha/coluna e primeiro lexer GP executável.

## 0.4.1 — Prévia de compilação nativa ARM64
- Backend experimental GP → C → Clang.
- Lançador bin/gpn para gerar e executar ELF64 AArch64 no Termux.
- Teste de integração que compila e executa o binário nativo.

## 0.4.0 — Estruturas, módulos e bytecode binário experimental
- Análise semântica de estruturas, construtores, campos e tipos compostos.
- Instruções de IR/VM para criar, ler e alterar campos de estruturas.
- Importação local de módulos de funções com alias e namespace.
- Contêiner binário v2 com compressão zlib, tamanho e CRC32.
- Compatibilidade de leitura com bytecode JSON v1.

## 0.3.0 — Primeiro pipeline de compilação e VM de referência
- AST formal, análise semântica inicial e IR explícita.
- Bytecode versionado e VM de pilha com chamadas e recursividade.
- Arrays tipados, indexação, mutação e funções de coleção.

## 0.2.0 — GP Core estruturado
- Funções, parâmetros tipados, retorno e recursividade.
- Escopos, laços, arrays, estruturas e módulos no bootstrap.

## 0.1.0 — Bootstrap
- Lexer, parser, tipos básicos, expressões, saída e condicionais.
## 0.8.45 — paridade estrita do schema GP-IR entre Python e C

- O decoder Python agora rejeita propriedades extras em instruções, definições de função e no objeto program do GP-IR; a política de extensões desconhecidas continua válida somente para o objeto raiz do envelope GGPC v2.
- O validador de GP-IR canônico exige exatamente format, ir_version, version, main e functions; cada função exige exatamente parameters, return_type e code; cada instrução exige exatamente op e args.
- O loader C foi alinhado: objetos program aceitam somente o conjunto normativo completo com ir_version ou a forma histórica sem esse campo; função tem exatamente três propriedades e instrução exatamente duas.
- Corrigida a validação C para não confundir uma quinta propriedade desconhecida com ir_version ausente.
- Preservada a compatibilidade de bytecodes v2 históricos sem program.ir_version; testes verificam aceitação em Python e VM C.
- Regressões diferenciais comprovam decisões iguais Python/C para propriedades extras em instruções, funções e program; encoder direto rejeita campos extras no root GP-IR e nas funções.
- `make validate`: exit 0; 207 testes aprovados em 76,734 s; corpus 6/6 em todas as comparações; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes dos 38 artefatos e `git diff --check` aprovados.
- `make bootstrap-proof`: exit 0; `BOOTSTRAP_PROOF_OK`; N+1 e N+2 reproduzidos com SHA-256 idêntico `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399` (23.037 bytes).
- Pico de heap rastreado: 55.222.251 B em N → N+1 e 55.415.537 B em N+1 → N+2, ambos abaixo do limite de 256 MiB. RSS de pico: 68.321.280 B e 68.448.256 B.
- Relatórios persistidos em `artifacts/bootstrap/proof/proof.json` e nos arquivos de memória dos dois estágios; logs em `build/validate-0.8.45-rerun.log` e `build/bootstrap-proof-0.8.45.log`.


## 0.8.46 — encoder nativo com entrada GP-IR por stdin

- O executável nativo aceita `--encode-ir - saida.gbc`, lendo o GP-IR JSON diretamente de stdin com limite de 64 MiB, validação UTF-8 e rejeição de NUL.
- O adaptador Python transmite os bytes serializados diretamente ao processo nativo; o arquivo temporário de entrada JSON foi eliminado. O arquivo de saída continua isolado em diretório temporário e é publicado pelo mecanismo atômico já existente no encoder.
- A interface histórica `--encode-ir arquivo.gp-ir.json saida.gbc` permanece disponível.
- Testes novos cobrem a equivalência byte a byte com a referência Python e rejeição de stdin vazio, UTF-8 inválido e NUL sem publicar saída.
- Testes direcionados cobrem stdin vazio, UTF-8 inválido, NUL e payload acima de 64 MiB; execução com `-W error::ResourceWarning` passou sem avisos de recursos.
- `make validate`: exit 0; 210 testes em 56,193 s; corpus diferencial 6/6; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes das fixtures e `git diff --check` aprovados.
- `make bootstrap-proof`: `BOOTSTRAP_PROOF_OK`; N+1 e N+2 reproduzidos com SHA-256 idêntico `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399` (23.037 bytes cada), métricas de heap/RSS abaixo do limite de 256 MiB.
- Relatórios: `build/validate-0.8.46-final.log`, `build/validate-0.8.46-final.exit`, `build/bootstrap-proof-0.8.46.log`, `artifacts/bootstrap/proof/` e `build/fuzz-reports/latest.json`.

## 0.8.47 — transporte direto da fonte para a VM nativa

- A VM C aceita `--source-input -` e lê a fonte GP diretamente de stdin, com limite de 16 MiB, tratamento de EINTR, validação UTF-8 e rejeição de NUL.
- O frontend self-hosted no caminho nativo transmite a fonte pelo pipe do processo; o arquivo temporário `source-input.txt` foi eliminado. O bytecode temporário do runner continua isolado e a opção `--source-input arquivo.txt` permanece compatível.
- Testes cobrem fonte Unicode e multilinha, fonte vazia, UTF-8 inválido, NUL, excesso de 16 MiB e compatibilidade com arquivo.
- Compilação C com `-Wall -Wextra -Wpedantic`, `py_compile` e integração do frontend self-hosted com VM nativa aprovadas.
- `make validate`: exit 0; 213 testes em 51,732 s; corpus diferencial 6/6; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes de fixtures e `git diff --check` aprovados.
- Log: `build/validate-0.8.47.log`; exit: `build/validate-0.8.47.exit`; fuzz: `build/fuzz-reports/latest.json`.

## 0.8.48 — execução do programa final pela VM C nativa

- O CLI `gpc` ganhou `--run-vm python|native`, separando a VM do frontend (`--runner-vm`) da VM que executa o bytecode do usuário.
- `--run-vm native` executa o GGPC produzido usando a VM C, respeitando `--run-max-steps` e `--run-timeout-seconds`; o caminho nativo não faz fallback silencioso para Python.
- `--native-vm` pode apontar a VM C tanto para o runner quanto para a execução final. O modo Python continua como padrão.
- `make validate`: exit 0; 216 testes em 46,202 s; corpus 6/6; fuzz 64 (37 rejeições, 27 execuções aceitas, zero divergências); hashes e `git diff --check` aprovados.
- `make bootstrap-proof`: exit 0; `BOOTSTRAP_PROOF_OK`; N+1 e N+2 byte a byte idênticos, SHA-256 `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes cada.

## 0.8.49 — publicação atômica do bytecode pelo CLI

- O compilador publica agora o GGPC em arquivo temporário exclusivo no mesmo diretório, sincroniza os dados e usa `os.replace` para substituir o destino atomicamente; depois sincroniza o diretório.
- Uma falha antes da substituição preserva integralmente o artefato anterior e remove o temporário.
- Entradas vazias são rejeitadas antes de publicar.
- Testes cobrem substituição completa, falha simulada de replace com preservação do arquivo anterior e ausência de temporários órfãos.
- `make validate`: exit 0; 219 testes em 49,356 s; corpus diferencial 6/6; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes de fixtures e `git diff --check` aprovados.
- Evidências: `build/validate-0.8.49.log`, `build/validate-0.8.49.exit` = 0 e `build/fuzz-reports/latest.json`. Prova de bootstrap concluída: exit 0, BOOTSTRAP_PROOF_OK; N+1 e N+2 têm SHA-256 idêntico 20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399 (23.037 bytes cada).

## 0.8.50 — módulos locais aninhados e limites do grafo

- O carregador dos backends de referência e auto-hospedado agora expande módulos locais recursivamente, com namespaces hierárquicos e chamadas internas resolvidas.
- Importações cíclicas, aliases duplicados, profundidade acima de 32, mais de 128 módulos, módulos acima de 4 MiB e grafos acima de 16 MiB são rejeitados.
- A paridade entre backends foi verificada em um grafo aninhado: ambos produziram a mesma saída.
- O pipeline completo frontend GP + encoder C + VM C executou programa com módulos aninhados e retornou o resultado esperado.
- Testes cobrem expansão aninhada, ciclos, aliases duplicados, limites de profundidade e compatibilidade com módulos simples.
- `make validate`: exit 0; 226 testes em 51,667 s; corpus diferencial 6/6; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes de fixtures e `git diff --check` aprovados.
- `make bootstrap-proof`: exit 0; `BOOTSTRAP_PROOF_OK`; N+1 e N+2 idênticos, SHA-256 `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`, 23.037 bytes cada.
- Heap pico: 55.347.618 B em N → N+1 e 55.540.904 B em N+1 → N+2; ambos abaixo do limite de 256 MiB.
- Evidências: `build/validate-0.8.50-final.log`, `build/validate-0.8.50-final.exit` = 0, `build/bootstrap-proof-0.8.50.log`, `build/bootstrap-proof-0.8.50.exit` = 0 e `artifacts/bootstrap/proof/`.
