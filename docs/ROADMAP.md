# Roadmap técnico — Gabriel Programming

## GP Core 0.1 — Bootstrap
Lexer/parser, variáveis, expressões, saída e condicionais.
**Status:** concluído.

## GP Core 0.2 — Linguagem estruturada
Funções, escopos, laços, arrays, estruturas, módulos e biblioteca inicial no interpretador.
**Status:** concluído no bootstrap.

## GP Core 0.3 — Front-end, IR, bytecode e VM de referência
AST, análise semântica inicial, IR, bytecode versionado, VM, arrays tipados, chamadas, recursividade e CLI.
**Status:** protótipo funcional.

## GP Core 0.4 — Consolidação do compilador
Estruturas e campos tipados; módulos locais de funções com namespace; IR e VM para estruturas; contêiner binário v2 comprimido; checksum e compatibilidade JSON v1.
**Status:** implementado no protótipo Android.

## GP Core 0.5 — Runtime nativo Android/ARM64
- VM C nativa executa bytecode v2 no Android ARM64.
- Loader nativo valida JSON UTF-8, checksum, formato IR, opcodes e operandos.
- Limite de heap monitorado de 256 MiB e medição do pico de uso.
- Heap gerenciado para strings, arrays e estruturas com coleta mark-and-sweep em pontos seguros entre instruções.
- Rastreamento de raízes na pilha de operandos, ambientes locais/globais e chamadas aninhadas; marcação recursiva protege referências encadeadas e ciclos.
- Limpeza explícita dos ambientes de função e dos objetos restantes ao encerrar.
- Contagem e indexação de strings por pontos de código UTF-8.
- VM Python mantida como referência de conformidade.
**Status:** VM nativa experimental funcional com coletor mark-and-sweep inicial validado por teste de estresse. Cobertura de objetos gerenciados e raízes continua evoluindo; runtime ainda não é produção.

## GP Core 0.6 — Diagnósticos e ferramentas
- Tokens e nós AST carregam linha/coluna.
- Diagnósticos léxicos, sintáticos e semânticos básicos incluem posição; erros semânticos incluem caminho do arquivo quando disponível.
- Loader Python limita tamanho de payload, valida checksum, opcodes, operandos e alvos de salto; teste contra payload comprimido maior que o tamanho declarado.
- Backpatcher bootstrap valida índice, opcode de salto e destino inteiro no intervalo permitido; destino igual ao tamanho do bloco representa saída válida.
- Contrato de IP confirmado nas VMs Python/C: incremento antes da instrução e destinos absolutos por bloco; laços aninhados, quebrar/continuar e saltos em funções cobertos por regressões.
- Loaders Python/C rejeitam booleanos, frações e expoentes em operandos que exigem inteiros; decoder Python valida raiz JSON objeto, versão inteira e consistência entre versão externa e interna do bytecode binário.
- Compatibilidade JSON experimental v1 preservada no decoder Python; o binário v2 permanece experimental até especificação formal e validação completa por opcode.
- Benchmark reproduzível compara VM Python e processo da VM C, incluindo inicialização e carga.
- Próximos itens: spans completos em todas as transformações, depurador, formatador e manifesto de projeto.
**Status:** primeira etapa implementada; cobertura total de spans ainda pendente.

## GP Core 0.7 — Auto-hospedagem gradual
- Lexer escrito em GP retorna lexemas, ignora espaços/comentários, reconhece identificadores, números inteiros/decimais, strings com escapes e operadores compostos.
- Classificador escrito em GP categoriza lexemas como palavra-chave, identificador, número, texto, operador, delimitador ou inválido.
- Classificação valida operadores conhecidos, identificadores e números decimais; pontuação delimitadora não é confundida com operador.
- Parser recursivo descendente escrito em GP trata expressões com precedência, agrupamentos, chamadas, arrays, indexação e acesso a campos.
- Gramática de comandos do parser GP inclui declarações primitivas e listas tipadas, atribuição a identificadores e posições de listas, mostrar(...), blocos, se/senao, enquanto, para, declaração de funções, parâmetros, retornar, estruturas com campos e comandos quebrar/continuar.
- Laços para aceitam cláusulas omitidas, registradas como nós VAZIO; funções guardam parâmetros e corpo em uma AST hierárquica.
- AST hierárquica em arena de estruturas tipadas: cada NoAST_GP contém categoria, valor, índices de filhos e posição do cursor de criação (linha/coluna).
- Nós implementados: PROGRAMA, BLOCO, DECLARACAO, ATRIBUICAO, MOSTRAR, SE, ENQUANTO, PARA, FUNCAO, PARAMETRO, RETORNAR, ESTRUTURA, CAMPO_DECLARADO, QUEBRAR, CONTINUAR, VAZIO, LITERAL, IDENTIFICADOR, UNARIO, BINARIO, AGRUPAMENTO, CHAMADA, ARRAY, INDICE e CAMPO.
- Lexer e parser executam nas VMs Python e C; testes verificam precedência, chamadas, arrays, operadores lógicos, campos, índices, comandos aninhados, condicionais, laços, funções, parâmetros, retorno e rejeição de sintaxe inválida.
- Analisador semântico inicial integrado à AST auto-hospedada: declarações primitivas, expressões aritméticas/lógicas, resolução de identificadores, atribuições, condições e escopos de blocos.
- Tabela de símbolos hierárquica rejeita duplicatas no mesmo escopo e permite sombreamento em blocos internos.
- Assinaturas de funções são registradas em primeira passagem, permitindo chamadas antes da definição e recursão.
- Parâmetros são declarados no escopo da função; chamadas verificam quantidade e tipos dos argumentos; retornos verificam compatibilidade com o tipo declarado.
- Análise semântica de enquanto e para verifica condições lógicas, escopo de inicialização e incrementos; quebrar/continuar dependem do contexto de laço.
- Declarações de listas tipadas, arrays homogêneos, indexação, atribuição por índice e operações tamanho/adicionar/remover recebem verificação semântica.
- Estruturas registram campos e tipos; construtores posicionais validam quantidade e tipos dos valores.
- Acesso e atribuição a campos verificam a estrutura-base e o tipo do campo, inclusive em estruturas aninhadas.
- Tipos definidos pelo usuário podem ser usados em variáveis, parâmetros e retornos; tipos e campos desconhecidos ou duplicados são rejeitados.
- Funções com retorno não vazio precisam retornar em todos os caminhos; blocos sequenciais e ramos completos de se/senao são analisados. Laços não contam como retorno garantido.
- Gerador de IR escrito em GP converte literais, variáveis, operações unárias/binárias, declarações, atribuições simples, saída e controle de fluxo (se/senao, enquanto e para); a representação interna dessas instruções usa a estrutura tipada InstrucaoIR_GP.
- Saltos usam rótulos simbólicos durante o lowering (LABEL/JUMP/JUMP_IF_FALSE); uma segunda passagem resolve os destinos em endereços numéricos absolutos e remove metadados LABEL.
- O resolver rejeita rótulos vazios/duplicados e destinos inexistentes; endereços de múltiplos dígitos são testados nas VMs Python e C.
- A inicialização, condição e atualização de para são emitidas, incluindo cláusulas vazias.
- Funções e chamadas são baixadas em seções independentes de registros InstrucaoIR_GP: FUNCTION/PARAM/CODE_BEGIN/CODE_END; parâmetros preservam tipo/nome, CALL registra nome/quantidade e RETURN gera o valor de retorno.
- Cada função resolve seus próprios rótulos em um espaço de endereços independente do programa principal; testes cobrem fatorial recursivo com fluxo condicional.
- Instruções do programa, metadados de funções e metadados de estruturas são armazenados em listas GP tipadas de InstrucaoIR_GP; campos de opcode, texto, número e lógico são mantidos separados.
- Validação de registros, resolução de rótulos e serialização JSON do frontend GP operam sobre os campos tipados, mantendo o contrato JSON consumido pelo adaptador e o bytecode binário v2.
- Todos os pontos de lowering emitem InstrucaoIR_GP diretamente; a ponte de conversão de linhas internas e o emissor textual foram removidos. O formato textual legado continua disponível somente no adaptador de compatibilidade, fora do caminho principal do frontend GP.
- Adaptador Python estrito constrói IRProgram/IRFunction diretamente dos registros JSON tipados emitidos pelo frontend GP e integra a saída ao serializador de bytecode binário v2; leitor textual legado preservado para compatibilidade.
- Frontend GP valida o contrato do envelope antes de emitir JSON: opcodes, aridade, campos obrigatórios, inteiros de contagem/destino e payloads tipados; o adaptador Python mantém validação independente em profundidade.
- CLI gpc --self-hosted executa o lexer, parser, analisador semântico e gerador de IR escritos em GP para a fonte alvo; teste cobre função fatorial recursiva, escapes de texto e execução do bytecode resultante na VM C ARM64.
- O modo auto-hospedado ainda usa o bootstrap Python para compilar o runner do frontend e a VM Python de referência para executá-lo; o adaptador Python constrói IRProgram/IRFunction diretamente a partir dos registros JSON tipados. Não é autocompilação integral.
- Subconjunto conectado: expressões escalares, arrays tipados, literais de lista, indexação/leitura e atribuição por índice, builtins tamanho/adicionar/remover, declarações, saída, controle de fluxo e funções/calls/returns.
- Declarações lista<T> são convertidas para MAKE_TYPED_ARRAY + DECLARE; literais em BUILD_ARRAY, leitura em GET_INDEX e escrita em SET_INDEX. Bytecode de listas é validado nas VMs Python e C ARM64.
- quebrar e continuar conectados para enquanto, para e laços aninhados; os destinos são indexados pela profundidade e limitados a 128 níveis. continuar em para direciona ao bloco de atualização.
- Estruturas ligadas ao backend: esquema STRUCT/STRUCT_FIELD, construtores posicionais, GET_FIELD/SET_FIELD, campos encadeados, estruturas aninhadas e parâmetros de função de tipo estrutura.
- Listas tipadas em parâmetros e retornos de funções; validação de tipo elemento; listas de estruturas, indexação seguida de acesso a campo e campos lista<estrutura> nas VMs Python/C.
- A análise semântica confirma que o elemento de todo campo lista<T> é primitivo ou estrutura declarada/forward declarada; tipos inexistentes são rejeitados. Integração de lista<estrutura> com laços validada nas duas VMs.
- O runner de compilação auto-hospedada usa orçamento de 5 milhões de instruções para o frontend e seus autotestes; o limite do bytecode executado pela aplicação segue separado.
- Módulos locais de funções com alias foram conectados ao backend auto-hospedado por expansão de fonte antes do frontend GP; imports aninhados e exportação de estruturas continuam pendentes. Listas de listas e recursos avançados da biblioteca padrão ainda exigem lowering específico.
- Diagnósticos iniciais para identificadores/funções não declarados, nomes duplicados, condições inválidas e incompatibilidade de tipos.
- Testes semânticos de funções, fluxo de retorno, laços, listas, estruturas e geração de IR executam nas VMs Python e C nativa ARM64.
- Transporte do IR migrado do texto/lista Python para arrays de campos em JSON emitidos pelo próprio GP; números, destinos/contagens, booleanos, nulo e textos passam por campos JSON tipados. O adaptador constrói diretamente o IR sem remontar linhas, mantém compatibilidade com o leitor textual legado e rejeita operandos numéricos em string.
- Próximos itens: mover a materialização IRProgram/IRFunction para GP, incluindo construção de funções, parâmetros e schemas sem o adaptador Python; depois avançar em imports aninhados/exportação de estruturas e eliminar gradualmente a dependência do bootstrap Python até obter compilação reproduzível pelo próprio GP.
- Meta posterior: compilar o compilador GP com ele mesmo e comparar builds reproduzíveis.
**Status:** lexer, parser, análise semântica e gerador GP já alimentam um backend experimental de bytecode v2 para um subconjunto da linguagem. A representação e emissão interna do IR são tipadas em GP; a materialização do IRProgram/IRFunction pelo próprio GP e a redução do bootstrap Python continuam pendentes. O runner e o adaptador ainda dependem de Python; a autocompilação integral continua pendente.

## GP Bytecode v2 — Estado de conformidade
- Backpatch bootstrap valida índice, instrução e destino absoluto; destinos no fim do bloco representam saída válida.
- Loaders Python/C validam tipos e aridade dos opcodes, operandos inteiros estritos, schemas, parâmetros e tipos de retorno.
- Contêiner binário exige cabeçalho coerente, CRC32, stream zlib completo e exato; JSON exige UTF-8, chaves únicas, escapes válidos, sem NUL/surrogates isolados ou constantes não padrão.
- Limites atuais alinhados: 64 MiB descomprimido, 128 MiB comprimido, 2 milhões de tokens e profundidade JSON 512.
- docs/BYTECODE_V2_SPEC.md descreve a implementação como rascunho 0.1; política de extensões, fixtures douradas e estabilidade continuam pendentes.
**Status:** validado por 136 testes no Termux/Android ARM64; formato ainda experimental, sem congelamento normativo.

- Corpus dourada v2 com seis arquivos binários de referência; teste diferencial executa os mesmos bytes nas VMs Python/C ARM64, verifica SHA-256 e compara saída.
- Cobertura positiva de 32/32 opcodes na fixture de catálogo; matriz determinística de 66 mutações sobre as seis fixtures; loaders Python/C concordam na rejeição de todos os casos.
- Fuzz smoke determinístico de 48 flips de bit com seed 0x47505632; loaders Python/C rejeitam todos os casos.
- Harness ferramentas/fuzz_bytecode.py e alvo make fuzz-bytecode; lote de 64 casos com 37 rejeições, 27 execuções válidas e zero divergências. Limites de recurso no processo C, relatório persistente e regra normativa para extensões desconhecidas no envelope v2.
- Rascunho BYTECODE_V2_SPEC.md 0.2 documenta envelope, opcodes, limites e fixtures; ainda não é especificação congelada.
**Próximos itens:** fuzzing diferencial, ampliação das fixtures para todos os opcodes e política de extensões/versionamento.

## GP 1.0 — Estabilidade
Especificação congelada, compatibilidade semântica, suíte de conformidade, documentação, builds reproduzíveis e distribuição.
**Status:** futuro.

## Diretriz de engenharia
O Android é a máquina primária de desenvolvimento e execução. A VPS é infraestrutura opcional e complementar. Não declarar runtime nativo completo, autossuficiência ou produção antes da implementação e validação correspondentes.


## GP 0.8.31 — GP-IR

- [x] Formalizar GP-IR v1 e separar seu versionamento do contêiner GGPC v2 e da linguagem 0.4.
- [x] Implementar validação central do IR em Python nas fronteiras de compilação/codificação.
- [x] Emitir GP-IR canônico em GP e codificar o documento diretamente no caminho CLI sem materializar `IRProgram`/`IRFunction`.
- [x] Demonstrar paridade estrutural frontend/bootstrap no corpus de seis fontes; ampliar a matriz para o contrato completo permanece pendente.
- [x] Persistir corpus diferencial de seis fontes com manifesto e SHA-256; cobertura cross-architecture permanece pendente.


## GP 0.8.33 — encoder direto de GP-IR

- [x] Validar envelope GP-IR v1 em sua forma JSON sem criar IRProgram/IRFunction.
- [x] Criar encode_canonical_ir(document) usando o contêiner GGPC v2 existente.
- [x] Preservar encode(IRProgram) como API de compatibilidade.
- [x] Redirecionar o CLI --self-hosted para o encoder direto.
- [x] Provar igualdade exata de bytes entre encoder direto e legado em seis casos do corpus.
- [x] Executar bytecodes direto e bootstrap nas VMs Python e C com saídas coincidentes em seis casos.
- [x] Persistir manifestos e SHA-256 para reprodução.
- [x] Ampliar a sintaxe do parser GP para inicializadores de estruturas com campos nomeados usados pelos fixtures do corpus.
- [x] Corrigir a divergência estrutural do lowering em control_flow_nested.gp e provar equivalência de IR, além da igualdade de saída.
- [ ] Retirar emissão paralela/adaptador legado somente após cobertura completa e conformance ampliada.

## GP 0.8.35 — paridade estrutural de condicionais

- [x] Distinguir no AST bootstrap a ausência de senao de um bloco alternativo explicitamente vazio.
- [x] Alinhar lowering, análise semântica, backend C e interpretador à representação explícita.
- [x] Comparar estruturalmente frontend GP e bootstrap para condicionais sem ramo, ramo vazio e ramo preenchido.
- [x] Validar suíte completa, corpus de seis fontes e fuzz diferencial ARM64.
- [ ] Reduzir a materialização e as validações duplicadas do adaptador Python sem perder a fronteira de segurança do host.

## GP 0.8.32 — serializador canônico nativo

- [x] Serializar no frontend GP o objeto GP-IR v1 canônico (`main`, `functions`, parâmetros, retorno e schemas).
- [x] Manter emissão paralela do envelope legado e comparar os dois resultados antes de aceitar o canônico.
- [x] Hidratar e validar o envelope canônico no host, sem reconstruir seções a partir de registros GP.
- [ ] Eliminar a emissão paralela e o adaptador de registros após conformidade completa e corpus diferencial persistente.
- [ ] Fazer o encoder/CLI consumir GP-IR canônico sem depender da materialização por Python; depois mover a hidratação/runtime conforme a arquitetura.


## GP 0.8.36 — entrada explícita e runner reutilizável

- [x] Definir entrada textual fornecida pelo host, sem caminhos ou leitura arbitrária de arquivos pelo programa GP.
- [x] Implementar o mesmo contrato nas VMs Python e C, com limite, UTF-8 e erro para ausência de entrada.
- [x] Remover interpolação do código-fonte-alvo dentro do runner temporário.
- [x] Aceitar chamadas de função como comandos isolados e ponto e vírgula opcional após blocos de controle.
- [x] Alinhar semântica de listas vazias tipadas em declarações, atribuições e construtores nomeados.
- [x] Executar o runner do frontend GP pelas VMs Python e C e comparar GP-IR em 6/6 casos do corpus.
- [x] Gerar artefato GGPC v2 reutilizável, manifesto e hashes vinculados às fontes geradoras.
- [x] Verificar que chamadas subsequentes reutilizam o artefato em vez de recompilá-lo.
- [x] Validar 185 testes, corpus 6/6, fuzz 64 casos sem divergências e 38 hashes.
- [x] Provar bootstrap nativo N -> N+1 -> N+2 com igualdade SHA-256 de N+1 e N+2; prova registrada em `artifacts/bootstrap/proof/proof.json`.


## GP 0.8.37 — redução de alocações e bootstrap reproduzível

- [x] Reutilizar caracteres ASCII indexados pela VM C com cache por instância e raízes seguras para o coletor.
- [x] Preservar indexação por pontos de código UTF-8 e reduzir a busca Unicode a uma única travessia.
- [x] Incluir cabeçalhos do alocador no orçamento padrão de 256 MiB, sem elevar o limite.
- [x] Cobrir 5.000 indexações ASCII, indexação Unicode, raízes do GC e relatório de memória com regressões.
- [x] Validar 186 testes, corpus 6/6, fuzz 64 casos sem divergências e 38 hashes.
- [ ] Medir e reduzir o pico total do frontend GP até executar dentro do orçamento real de 256 MiB.
- [x] Gerar N+1 com o artefato bootstrap N executado na VM C, sem `compile_source()` no caminho de compilação alvo.
- [x] Fazer N+1 produzir N+2 na VM C e comparar GP-IR/bytecode/hashes.
- [x] Gerar N+2 a partir de N+1 e comprovar hashes e saída reproduzíveis.

## GP 0.8.39 — telemetria de memória por grupo

- [x] Classificar todas as alocações rastreadas entre buffers nativos, objetos gerenciados pelo GC e pilhas de operandos.
- [x] Expor bytes vivos e picos independentes por grupo, além do total global, sem elevar o limite de 256 MiB.
- [x] Verificar por teste que os grupos vivos particionam exatamente o heap rastreado e que o pico total respeita o teto.
- [x] Registrar relatórios dos dois estágios nativos N → N+1 e N+1 → N+2 junto à prova de bootstrap.
- [x] Medir RSS residente atual via procfs e pico via getrusage, separadamente do heap rastreado.
- [x] Tornar o timeout do bootstrap nativo configurável e impedir que um proof.json antigo seja confundido com o resultado da execução atual.
- [ ] Reduzir a dependência do bootstrap Python e materializar GP-IR/encoder integralmente em GP.

**Status:** pools de alocação, limites do heap e RSS residente atual/pico estão instrumentados e validados; a autossuficiência integral do toolchain e o encoder GGPC em GP continuam pendentes.
- [x] make validate: 191 testes; corpus diferencial 6/6; fuzz 64 iterações sem divergências.
- [x] make bootstrap-proof: N → N+1 → N+2 aprovado, com SHA-256 idêntico entre N+1 e N+2 e relatórios de heap/RSS dos dois estágios.
- [x] make check e git diff --check aprovados.

## GP 0.8.38 — indexação linear da VM e bootstrap reproduzível

- [x] Pré-indexar instruções uma única vez por bloco; usar buffer local para blocos pequenos e alocação controlada para blocos grandes.
- [x] Validar a estrutura do bloco em uma passagem linear e preservar destinos absolutos de saltos.
- [x] Cobrir bloco grande com 320 declarações e laço com teste de regressão.
- [x] Corrigir validação de tipo em `MAKE_TYPED_ARRAY` e cobrir bytecode adulterado.
- [x] Tornar a expansão dos ambientes segura sob falha intermediária de alocação, com teste de OOM.
- [x] Medir a VM anterior e a indexada em Android ARM64: 1,88x no loop de 12.000 iterações e 1,45x no bloco com 320 declarações (medianas de tempo de CPU, 2 aquecimentos e 9 repetições).
- [x] `make validate`: 189 testes, corpus 6/6 e fuzz diferencial sem divergências.
- [x] Provar bootstrap N → N+1 → N+2 com SHA-256 idêntico para N+1 e N+2.
- [ ] Medir separadamente o pico contabilizado do heap gerenciado, alocador e pilhas durante a autocompilação; manter o limite de 256 MiB.
- [ ] Reduzir a dependência do bootstrap Python e materializar GP-IR/encoder integralmente em GP.

**Status:** índice linear e segurança de memória validados; bootstrap nativo reproduzível demonstrado para o frontend e corpus atual. A autossuficiência integral do toolchain e a estabilidade 1.0 permanecem pendentes.


## GP 0.8.40 — encoder GGPC nativo

- [x] Implementar encoder GGPC v2 em C consumindo GP-IR v1 validado.
- [x] Integrar o encoder C ao CLI self-hosted no caminho da VM nativa.
- [x] Preservar encoder Python como oráculo e provar igualdade byte a byte em 6/6 casos do corpus.
- [x] Rejeitar GP-IR inválido sem publicar arquivo de saída.
- [x] Executar 194 testes, corpus diferencial 6/6 e fuzz 64 casos sem divergências.
- [x] Provar bootstrap N → N+1 → N+2, com hashes N+1/N+2 idênticos.
- [ ] Ampliar testes de segurança do encoder para limites, JSON adversarial, UTF-8, falhas de alocação e falhas de escrita.
- [ ] Reduzir a hidratação Python e mover a materialização de funções, parâmetros e schemas para GP.

Status: encoder binário C nativo e paridade byte a byte validados no corpus atual. O bootstrap e a hidratação de IR ainda têm dependências Python; GP não é integralmente auto-hospedada.

## GP 0.8.41 — publicação segura do encoder

- [x] Substituir temporário previsível por criação exclusiva com mkstemp.
- [x] Criar arquivo temporário com permissão restrita 0600.
- [x] Tratar escritas parciais e EINTR; sincronizar dados antes da publicação.
- [x] Remover temporário quando a gravação, o fechamento ou o rename falhar.
- [x] Testar saída bem-sucedida, permissões e limpeza após falha de publicação.
- [ ] Completar matriz de entradas adversariais: JSON malformado, chaves duplicadas, UTF-8 inválido, limites e falhas de alocação.
- [ ] Executar make validate após a revisão de segurança.

Status: fluxo de publicação protegido e testes focados aprovados. A validação integral do ciclo está pendente.

## GP 0.8.42 — redução de memória e entradas adversariais JSON

- [x] Reduzir a alocação temporária de strings JSON de até 4n+1 para n+1 bytes, mantendo a decodificação UTF-8 escapada.
- [x] Cobrir Unicode escapado e equivalência semântica entre encoder nativo e referência.
- [x] Cobrir rejeição de chaves JSON duplicadas em objetos aninhados.
- [x] Cobrir rejeição de bytes UTF-8 inválidos na entrada do encoder.
- [ ] Executar make validate após a revisão.

Status: três regressões focadas aprovadas; validação integral pendente.

## GP 0.8.43 — limites de entrada do encoder

- [x] Rejeitar arquivo GP-IR maior que 64 MiB antes de alocar o payload.
- [x] Rejeitar JSON malformado sem publicar bytecode.
- [x] Cobrir os dois casos com testes nativos no Android ARM64.
- [x] Executar make validate com o corpus e os 201 testes.

- [x] make validate: 201 testes; corpus diferencial 6/6; fuzz 64 iterações sem divergências; hashes e git diff --check aprovados.

Status: limites de entrada e parsing adversarial validados no Termux/Android ARM64. O encoder continua experimental e a materialização Python ainda está pendente.

## GP 0.8.44 — JSON bruto direto ao encoder C

- [x] Preservar o GP-IR JSON bruto do frontend sem `json.loads` no CLI nativo.
- [x] Encaminhar o texto diretamente ao encoder C sem `validate_canonical_ir` nem `json.dumps` no fluxo nativo.
- [x] Manter as APIs Python de documento e compatibilidade `IRProgram` inalteradas.
- [x] Tornar a validação C estrita quanto às chaves exatas `op`/`args` de cada instrução.
- [x] Corrigir seleção automática de `build/gpvm-native` para runner e encoder quando `--runner-vm native` não recebe caminho explícito.
- [x] Validar CLI com `--dump-ir`, caminho nativo, API de compatibilidade e comparação byte a byte.
- [x] `make validate`: 203 testes; corpus 6/6; fuzz 64 casos sem divergências; hashes e diff check aprovados.
- [x] Provar novamente bootstrap N → N+1 → N+2 após a revisão da VM C e do host CLI.
- [ ] Continuar a migração do bootstrap e da materialização de GP-IR para GP; preservar o adaptador Python até conformidade completa.

Status: o caminho de compilação CLI com encoder nativo não materializa o GP-IR em dict Python. O host ainda orquestra a VM e grava o JSON bruto para o encoder; autonomia integral do toolchain não foi alcançada.

- [x] Bootstrap N → N+1 → N+2 revalidado: N+1 e N+2 têm hashes idênticos; relatórios de heap/RSS dos dois estágios persistidos.

## GP 0.8.45 — paridade de schema GP-IR Python/C

- [x] Exigir conjunto exato de propriedades no envelope GP-IR canônico e nas definições de função.
- [x] Exigir exatamente op/args em toda instrução no decoder Python e validador nativo C.
- [x] Alinhar o decoder Python do GGPC v2 para rejeitar campos extras no objeto program e em funções.
- [x] Preservar extensões desconhecidas somente no objeto raiz do envelope GGPC v2.
- [x] Preservar bytecodes históricos sem program.ir_version em Python e C.
- [x] Testar diferencialmente Python/C as rejeições de campos extras e a compatibilidade histórica.
- [x] Executar `make validate`: 207 testes; corpus 6/6; fuzz 64 casos sem divergências; hashes e diff check aprovados.
- [x] Executar `make bootstrap-proof`: N → N+1 → N+2 com hashes idênticos de N+1/N+2 e relatórios de memória dos dois estágios.

Status: contrato de schema estrito alinhado entre Python e C, com compatibilidade histórica preservada e provas integrais aprovadas no Android ARM64.


## GP 0.8.46 — transporte direto do GP-IR pelo stdin

- [x] Adicionar leitura nativa limitada a 64 MiB a partir de stdin, com tratamento de EINTR.
- [x] Rejeitar stdin vazio, UTF-8 inválido e bytes NUL antes de processar o JSON.
- [x] Alterar o adaptador Python para enviar bytes diretamente com subprocess.run(input=...), removendo o arquivo temporário de entrada.
- [x] Preservar a interface de encoder baseada em caminho de arquivo para compatibilidade.
- [x] Testar equivalência byte a byte entre a entrada stdin e o encoder Python, além de entradas inválidas.
- [x] Executar `make validate`: 210 testes; corpus 6/6; fuzz 64 casos sem divergências; hashes e diff check aprovados.
- [x] Executar e registrar a prova de bootstrap N → N+1 → N+2 após a mudança no transporte.
- [x] Testar entrada stdin acima de 64 MiB sob `-W error::ResourceWarning`, sem vazamentos de pipes.

Status: o caminho nativo não precisa mais gravar o GP-IR JSON bruto em um arquivo intermediário. A saída ainda é recebida em arquivo temporário e o encoder nativo preserva a publicação atômica. A autonomia completa do toolchain continua pendente.

## GP 0.8.47 — transporte direto da fonte para a VM nativa

- [x] Adicionar `--source-input -` com leitura limitada a 16 MiB, tratamento de EINTR, validação UTF-8 e rejeição de NUL.
- [x] Transmitir a fonte GP pelo stdin no frontend self-hosted executado pela VM C, removendo o arquivo temporário `source-input.txt`.
- [x] Preservar `--source-input arquivo.txt` para compatibilidade.
- [x] Cobrir fonte Unicode/multilinha, fonte vazia, bytes inválidos, NUL e payload acima do limite.
- [x] Compilar VM C com `-Wall -Wextra -Wpedantic` e executar integração do frontend nativo.
- [x] `make validate`: 213 testes; corpus 6/6; fuzz 64 sem divergências; hashes e `git diff --check` aprovados.

Status: a fonte do usuário não é mais gravada em arquivo temporário no caminho do runner nativo. O bytecode do runner ainda usa arquivo temporário; a orquestração de compilação continua em Python e a autonomia integral do toolchain permanece como objetivo futuro.

## GP 0.8.48 — execução do programa final pela VM C nativa

- [x] Adicionar `--run-vm python|native`, independente de `--runner-vm`.
- [x] Executar o bytecode final na VM C quando `--run-vm native`, sem fallback silencioso para Python.
- [x] Suportar `--native-vm` compartilhado para runner/runtime e selecionar `build/gpvm-native` como padrão no modo nativo.
- [x] Expor limite de instruções e timeout da execução final, com validação de faixa antes de compilar.
- [x] Preservar a VM Python como padrão e testar a compatibilidade.
- [x] Testar execução nativa, saída correta, limite de instruções e limites inválidos de configuração.
- [x] `make validate`: 216 testes em 46,202 s; corpus 6/6; fuzz 64 (37 rejeições, 27 execuções aceitas, zero divergências); hashes e `git diff --check` aprovados.
- [x] `make bootstrap-proof`: N → N+1 → N+2 concluído; N+1 e N+2 com SHA-256 idêntico `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`.

Status: o CLI pode agora executar frontend, encoder e programa final na VM C nativa. A geração inicial do runner, a expansão de módulos e a orquestração continuam parcialmente dependentes de Python. Critérios de estabilização para 1.0.0 estão em `docs/RELEASE_CRITERIA_1.0.0.md`.

## GP 0.8.49 — publicação atômica do bytecode pelo CLI

- [x] Validar bytes não vazios antes da publicação.
- [x] Criar temporário exclusivo no diretório de destino, com permissões restritivas do mkstemp.
- [x] Gravar integralmente, executar flush/fsync, fechar e substituir com os.replace.
- [x] Sincronizar o diretório após publicação para persistir a entrada do nome.
- [x] Em falha de escrita/substituição antes do replace, manter o artefato anterior e limpar o temporário.
- [x] Testar publicação, substituição e falha simulada sem perda do artefato anterior.
- [x] `make validate`: 219 testes; corpus 6/6; fuzz 64 sem divergências; hashes e diff check aprovados.
- [x] Reexecutar prova de bootstrap N → N+1 → N+2 após a mudança do host de compilação; `BOOTSTRAP_PROOF_OK`, N+1 = N+2 SHA-256 `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`.

Status: o encoder C já possuía publicação atômica própria; agora o caminho CLI Python que publica o artefato final também não trunca o destino existente. Validação completa e prova de bootstrap concluídas com sucesso. A construção inicial do runner ainda usa bootstrap Python.

## GP 0.8.50 — módulos locais aninhados e limites do grafo

- [x] Expandir recursivamente módulos locais no backend auto-hospedado.
- [x] Implementar namespaces hierárquicos e resolver chamadas internas em módulos aninhados.
- [x] Detectar ciclos de importação e rejeitar aliases duplicados em cada nível.
- [x] Aplicar limites de profundidade (32), quantidade (128), tamanho por módulo (4 MiB) e tamanho total do grafo (16 MiB).
- [x] Atualizar o compilador de referência para manter a mesma semântica de expansão.
- [x] Testar paridade de saída entre compilador de referência e frontend auto-hospedado.
- [x] Executar o pipeline completo com frontend GP, encoder C e runtime C usando módulos aninhados.
- [x] `make validate`: 226 testes em 51,667 s; corpus 6/6; fuzz 64 sem divergências; hashes e diff check aprovados.
- [x] `make bootstrap-proof`: N → N+1 → N+2 aprovado; N+1 = N+2 SHA-256 `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`.

Status: ambos os compiladores expandem o mesmo grafo aninhado e a VM C executa o programa produzido. O bootstrap N é ainda gerado pelo host Python; a prova confirma a reprodução dos estágios seguintes na VM C, não independência total de Python.


## GP 0.8.51 — leitura segura e limites reais dos módulos locais

- [x] Centralizar a resolução de caminhos e a leitura binária limitada dos módulos.
- [x] Aplicar o limite individual de 4 MiB aos bytes efetivamente lidos, sem confiar apenas em metadados de tamanho.
- [x] Contabilizar o limite total de 16 MiB do grafo pelos bytes efetivamente lidos.
- [x] Preservar os limites de profundidade (32) e quantidade (128), além da detecção de ciclos e aliases duplicados.
- [x] Converter loops de links simbólicos (ELOOP) em diagnóstico específico de caminho inválido.
- [x] Aplicar a mesma política ao compilador de referência e ao backend auto-hospedado.
- [x] Executar 18 testes de regressão de módulos, incluindo links aninhados e arquivos especiais, todos aprovados.
- [x] `make validate`: 231 testes em 48,620 s; corpus 6/6; fuzz 64 (37 rejeições, 27 aceitos/executados, zero divergências); hashes e `git diff --check` aprovados.
- [x] `make bootstrap-proof`: `BOOTSTRAP_PROOF_OK`; N+1 = N+2, SHA-256 `20a4be94cbdd9e2a2368b500490586cca1a2cd0db65ded69448f89dbe3bfd399`.

Status: limites de leitura aplicados aos bytes reais, rejeição não bloqueante de arquivos especiais e diagnósticos de links simbólicos aninhados validados no Termux/Android ARM64. A geração inicial do estágio N ainda usa `Python bootstrap compile_source`; a autohospedagem integral permanece pendente.

## Direção de release — GP 1.1

**Meta de produto:** GP 1.1.0.

A GP 1.0.0 permanece como marco intermediário obrigatório, não como encerramento do projeto. Antes dela, concluir os critérios de estabilidade, regressão, segurança, documentação, instalação reprodutível e bootstrap honesto definidos em `docs/RELEASE_CRITERIA_1.0.0.md`. A evolução até 1.1.0 deve priorizar autossuficiência real do toolchain, biblioteca padrão e driver de compilação em GP, experiência de desenvolvimento e distribuição multiplataforma. GP Fusion, segurança adaptativa e IA própria devem entrar em etapas compatíveis com a maturidade do núcleo, sem comprometer a estabilidade da linguagem.

A linha de base da VM C e do frontend auto-hospedado está em `docs/PERFORMANCE_BASELINE_2026-11-08.md`. Otimizações devem ser orientadas por medições por fase, manter paridade entre as VMs e não contornar limites de execução para mascarar regressões.


## GP 0.8.52 — junção eficiente de texto e serialização em lote

- [x] Implementar `unir_textos(lista texto) -> texto` no interpretador bootstrap, VM Python e VM C.
- [x] Preservar Unicode, aceitar lista vazia, rejeitar itens não textuais e limitar a saída a 64 MiB.
- [x] Atualizar a análise semântica do frontend auto-hospedado para exigir `lista texto`.
- [x] Refatorar os serializadores canônicos de código principal e funções para acumular fragmentos e juntar uma única vez.
- [x] Cobrir interpretador, VM Python, VM C e execução auto-hospedada.
- [x] `make validate`: 238 testes; corpus 6/6; fuzz 64 sem divergências; hashes e `git diff --check` aprovados.
- [x] Confirmar bootstrap otimizado N → N+1 → N+2, com `status: passed` e N+1 == N+2.
- [ ] Comparar tempo, instruções, GC, heap e RSS com o baseline 0.8.51 no mesmo tablet.
- [ ] Usar os resultados para priorizar novas otimizações do frontend e da VM nativa.

**Status:** otimização, suíte completa e bootstrap reproduzível aprovados no Termux/Android ARM64. A comparação quantitativa com o baseline anterior permanece pendente; não declarar melhoria global de desempenho antes dela.
