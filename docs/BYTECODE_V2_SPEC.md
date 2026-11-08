# GP Bytecode v2 — Especificação preliminar

**Estado:** rascunho 0.7 — derivado da implementação e dos testes atuais em 2026-11-06.
**Não é uma especificação congelada nem uma declaração de estabilidade do bytecode.**

Este documento descreve o formato efetivamente implementado pelos encoders/loaders Python e C no repositório. Em caso de divergência, os testes de conformidade e o código atualmente validado determinam o comportamento até a aprovação de uma especificação normativa.

## 1. Visão geral

A versão binária v2 é um contêiner comprimido que transporta um documento JSON UTF-8. O JSON contém um programa GP-IR, com um bloco principal e um mapa de funções. Cada instrução possui um opcode e uma lista de operandos.

A VM Python é a referência de compatibilidade. A VM C nativa ARM64 implementa o mesmo formato binário v2 e valida o envelope antes de executar o programa.

O encoder atual produz sempre o contêiner binário v2. O decoder Python preserva leitura de um formato JSON experimental legado v1. A VM C não carrega esse JSON legado diretamente.

## 2. Contêiner binário

O cabeçalho possui exatamente 14 bytes, em big-endian:

| Offset | Tamanho | Tipo | Significado |
|---:|---:|---|---|
| 0 | 4 | bytes | Assinatura ASCII GGPC |
| 4 | 2 | uint16 | Versão externa do contêiner; atualmente 2 |
| 6 | 4 | uint32 | Tamanho do payload JSON descomprimido |
| 10 | 4 | uint32 | CRC32 do payload JSON descomprimido |

Após o cabeçalho há exatamente um stream zlib com o documento JSON UTF-8. O encoder usa nível de compressão 9. Os loaders exigem que o stream termine corretamente, produza exatamente o tamanho declarado e não deixe bytes comprimidos residuais.

O CRC32 é calculado sobre os bytes JSON descomprimidos. O tamanho descomprimido deve ser maior que zero e não exceder 64 MiB.

### 2.1 Limites atuais de segurança

| Limite | Valor implementado |
|---|---:|
| Payload descomprimido | 64 MiB |
| Arquivo binário comprimido | 128 MiB |
| Tokens JSON | 2.000.000 |
| Profundidade JSON | 512 |
| Instruções por bloco no decoder Python | 2.000.000 |

A VM C limita o número total de tokens JSON a 2.000.000; por isso, o número efetivo de instruções em cada bloco também fica limitado pelo orçamento global de tokens. Limites de heap, pilha de chamadas e passos de execução pertencem ao runtime e não são definidos pelo cabeçalho do bytecode.

## 3. Envelope JSON

O payload é um objeto JSON UTF-8. A estrutura de alto nível atual é:

~~~json
{
  "magic": "GABRIEL-GP-BYTECODE",
  "bytecode_version": 2,
  "language_version": "0.4",
  "program": {
    "format": "GP-IR",
    "ir_version": 1,
    "version": "0.4",
    "main": [
      {"op": "CONST", "args": [42]},
      {"op": "PRINT", "args": [1]}
    ],
    "functions": {}
  }
}
~~~

Regras do envelope:

- magic deve ser exatamente GABRIEL-GP-BYTECODE.
- bytecode_version deve ser um inteiro JSON, não booleano ou float; no contêiner binário atual deve ser 2.
- A versão externa uint16 do cabeçalho deve coincidir com bytecode_version.
- language_version deve ser uma string não vazia e coincidir exatamente com program.version.
- program.format deve ser GP-IR.
- program.ir_version identifica o formato GP-IR independentemente do contêiner e da linguagem; o valor atual é o inteiro JSON 1. Em bytecodes v2 históricos sem esse campo, os leitores interpretam GP-IR v1. Novos produtores devem emitir o campo explicitamente.
- program.main deve ser um array de instruções.
- program.functions deve ser um objeto que mapeia nomes de função para suas definições.
- Chaves duplicadas em qualquer objeto JSON são rejeitadas.
- Strings devem usar escapes JSON válidos e UTF-8 válido. O runtime atual rejeita NUL e surrogates Unicode isolados; pares surrogate válidos são aceitos.
- NaN, Infinity e -Infinity não são valores JSON aceitos.
- JSON truncado, dados extras após o documento ou bytes extras após o stream zlib são rejeitados.
- Propriedades desconhecidas no objeto raiz do envelope MUST ser ignoradas pelos leitores v2; elas não alteram a semântica do programa. Produtores SHOULD prefixar propriedades de extensão com x- para evitar colisões com campos normativos futuros. Leitores não precisam preservar nem retransmitir extensões desconhecidas. Campos normativos conhecidos mantêm validação estrita; esta regra não autoriza propriedades extras dentro de instruções, operandos ou schemas. O objeto `program` aceita somente `format`, `version`, `main`, `functions` e, quando presente, `ir_version`; a ausência de `ir_version` é aceita apenas para bytecodes v2 históricos. Cada definição de função aceita exatamente `parameters`, `return_type` e `code`. Cada instrução aceita exatamente `op` e `args`. Campos extras nessas estruturas são rejeitados igualmente pelos decoders Python e C.

## 4. Bloco de código e instruções

Cada bloco de código é um array ordenado. Cada instrução é um objeto com:

- op: string que identifica um opcode conhecido;
- args: array cuja aridade e tipos são definidos pelo opcode.

OpCodes desconhecidos, aridade incorreta e operandos com tipos inválidos são rejeitados antes da execução.

### 4.1 Tabela de opcodes

| Opcode | Operandos em args | Validação atual |
|---|---|---|
| CONST | [valor] | string, boolean, null ou número JSON finito |
| LOAD | [nome] | string não vazia |
| STORE | [nome] | string não vazia |
| DECLARE | [nome, tipo, tipo_elemento] | nome/tipo não vazios; tipo_elemento é string para lista e null para tipo simples |
| POP | [] | nenhum operando |
| BUILD_ARRAY | [quantidade] | inteiro JSON não negativo; não maior que o tamanho do bloco |
| MAKE_TYPED_ARRAY | [tipo_elemento] | string não vazia |
| BUILD_STRUCT | [nome, schema] | nome não vazio; schema validado conforme 4.2 |
| GET_FIELD | [nome_campo] | string não vazia |
| SET_FIELD | [nome_campo] | string não vazia |
| GET_INDEX | [] | nenhum operando |
| SET_INDEX | [] | nenhum operando |
| NEG | [] | nenhum operando |
| NOT | [] | nenhum operando |
| ADD | [] | nenhum operando |
| SUB | [] | nenhum operando |
| MUL | [] | nenhum operando |
| DIV | [] | nenhum operando |
| MOD | [] | nenhum operando |
| EQ | [] | nenhum operando |
| NE | [] | nenhum operando |
| GT | [] | nenhum operando |
| LT | [] | nenhum operando |
| GE | [] | nenhum operando |
| LE | [] | nenhum operando |
| AND | [] | nenhum operando |
| OR | [] | nenhum operando |
| PRINT | [quantidade] | inteiro JSON não negativo; não maior que o tamanho do bloco |
| JUMP | [destino] | inteiro JSON absoluto no intervalo de 0 até o tamanho do bloco |
| JUMP_IF_FALSE | [destino] | inteiro JSON absoluto no intervalo de 0 até o tamanho do bloco |
| CALL | [nome_funcao, quantidade] | nome não vazio e quantidade inteira não negativa, limitada pelo tamanho do bloco |
| RETURN | [] | nenhum operando |

Booleanos não são inteiros para destinos ou contagens, mesmo que a linguagem hospedeira Python trate bool como subclasse de int. Floats que representem números inteiros, notação exponencial e strings numéricas também são rejeitados nesses operandos.

### 4.2 Schema de estrutura

O segundo operando de BUILD_STRUCT é um array ordenado de campos. Cada campo é um par:

~~~json
[
  ["nome", "texto"],
  ["idade", "numero"]
]
~~~

O nome e o tipo de cada campo devem ser strings não vazias. Nomes de campo duplicados são rejeitados. A ordem do schema é preservada, pois corresponde à ordem posicional usada para construir o valor.

### 4.3 Funções

program.functions é um objeto. A chave é o nome da função; o valor contém:

~~~json
{
  "parameters": [
    ["numero", "a"],
    ["numero", "b"]
  ],
  "return_type": "numero",
  "code": [
    {"op": "LOAD", "args": ["a"]},
    {"op": "LOAD", "args": ["b"]},
    {"op": "ADD", "args": []},
    {"op": "RETURN", "args": []}
  ]
}
~~~

- Nome da função deve ser uma string não vazia.
- parameters é obrigatório e é um array de pares [tipo, nome].
- Tipo e nome de cada parâmetro devem ser strings não vazias.
- Nomes de parâmetros duplicados são rejeitados.
- return_type é obrigatório e deve ser null ou uma string não vazia.
- code é obrigatório e segue a mesma tabela de opcodes.
- Cada função possui seu próprio bloco de endereços de salto.

## 5. Endereçamento de saltos

Os destinos são índices absolutos dentro do bloco de código ao qual a instrução pertence. O ponteiro de instrução é avançado antes da execução da instrução; ao executar JUMP ou JUMP_IF_FALSE, o IP recebe o destino absoluto.

O destino pode variar de zero até len(code), inclusive. Um destino igual a len(code) representa a saída do bloco. Saltos não são relativos ao IP atual.

O compilador bootstrap usa backpatching. O patch só pode substituir o operando de JUMP/JUMP_IF_FALSE; o índice da instrução e o destino precisam ser inteiros válidos. O frontend auto-hospedado resolve rótulos simbólicos em uma segunda passagem antes de emitir o IR estruturado.

## 6. Validação e integridade

Os loaders Python e C validam, antes de executar:

1. Assinatura, versão externa, tamanho declarado e CRC32.
2. Stream zlib completo, sem truncamento ou dados residuais.
3. JSON UTF-8 válido, raiz objeto, sem chaves duplicadas e com limites de tokens/profundidade.
4. Envelope, versões e formato GP-IR.
5. Nomes, aridade e tipos dos operandos para os opcodes conhecidos.
6. Schemas de estruturas, parâmetros e tipos de retorno.
7. Inteiros de destinos e contagens sem aceitar bool/float.
8. Tipos escalares finitos nas constantes.

A VM C rejeita escapes JSON inválidos, caracteres de controle não escapados, NUL e surrogates isolados ao materializar strings. A implementação Python aplica as mesmas restrições no decoder.

## 7. Compatibilidade

- O encoder atual escreve somente o contêiner binário v2.
- O decoder Python ainda aceita o envelope JSON experimental legado v1, para leitura de arquivos antigos.
- A VM C nativa exige o contêiner binário com versão externa 2; não lê o JSON legado v1.
- A versão externa do contêiner e bytecode_version precisam coincidir.
- A versão de linguagem do envelope e program.version precisam coincidir.
- program.ir_version é independente de bytecode_version e language_version. Uma mudança incompatível no formato GP-IR exige incremento de ir_version; uma mudança incompatível no contêiner exige incremento de bytecode_version.
- Não há neste rascunho garantia de compatibilidade futura entre versões v2; isso requer política formal de evolução e fixtures de conformidade.

## 8. Corpus dourada de conformidade

A pasta tests/fixtures/bytecode_v2 contém seis artefatos binários produzidos pelo encoder atual e mantidos como entradas imutáveis de teste. Cada arquivo possui sua fonte GP correspondente e uma entrada SHA-256 em SHA256SUMS.

| Fixture | Cobertura | Saída esperada |
|---|---|---|
| arithmetic.gbc | expressões e operações aritméticas | 11 24 5 |
| control_flow_nested.gbc | laços aninhados, se/senao, quebrar/continuar e chamada de função | 48 3 11 8 |
| recursive_function.gbc | recursão e retornos | 120 |
| structs_and_fields.gbc | schema, construção nomeada e alteração de campo | Ana 38 |
| unicode_text.gbc | texto UTF-8 e contagem de caracteres | Olá, GP 7 |
| opcode_catalog.gbc | catálogo positivo de todos os 32 opcodes reconhecidos | 11 5 24 2; 9 3 0 GP GP 9 5 |

O teste test_native_vm_matches_python_on_v2_golden_fixture_corpus:
1. lê os bytes .gbc sem recompilar as fontes;
2. verifica SHA-256 e versão binária;
3. executa exatamente os mesmos bytes na VM Python e na VM C;
4. compara código de saída e stdout com o resultado esperado.

A corpus comprova equivalência para esses casos, não cobertura exaustiva de todos os opcodes ou arquiteturas.

## 9. Testes diferenciais determinísticos

Além das seis fixtures válidas, a suíte mantém uma matriz determinística de mutações sobre cada binário de referência. São 11 mutações por seed, totalizando 66 entradas inválidas:

- cabeçalho curto;
- stream zlib truncado;
- bytes residuais após o stream zlib;
- assinatura alterada;
- versão externa alterada;
- tamanho declarado alterado;
- CRC alterado;
- dados comprimidos corrompidos;
- chave JSON duplicada;
- opcode desconhecido;
- forma de args inválida.

Cada mutação deve ser recusada tanto pelo decoder Python quanto pela VM C ARM64. O teste não exige textos de erro idênticos; exige a mesma decisão de aceitação/rejeição. Isso é uma matriz determinística de regressão, não substitui fuzzing aleatório ou guiado por cobertura.

## 10. Fuzz smoke determinístico

A suíte também aplica mutações de bit com PRNG determinístico:
- seed: 0x47505632;
- oito mutações por fixture;
- seis fixtures;
- 48 entradas binárias mutadas no total.

Cada caso altera um bit em posição e máscara selecionadas pelo seed. O decoder Python e a VM C devem rejeitar as 48 entradas. A bateria é pequena e limitada, destinada a regressão reproduzível; não representa fuzzing guiado por cobertura nem certifica ausência de bugs.

## 11. Política normativa de extensões e evolução v2

1. Leitores de contêiner v2 MUST ignorar propriedades desconhecidas no objeto JSON raiz, desde que o JSON e os campos normativos conhecidos sejam válidos.
2. Produtores SHOULD nomear extensões com prefixo x-; nomes sem esse prefixo continuam ignorados por compatibilidade, mas podem colidir com campos normativos introduzidos no futuro.
3. Extensões não podem redefinir magic, bytecode_version, language_version ou program, nem mudar o significado de opcodes existentes.
4. Uma alteração incompatível no cabeçalho, envelope obrigatório, schema de instrução ou semântica de opcode exige nova versão do contêiner (v3), não apenas nova language_version.
5. Uma evolução aditiva dentro de v2 deve preservar a interpretação de programas existentes; leitores podem ignorar extensões desconhecidas.
6. A VM C ARM64 e o decoder Python são ambos leitores v2 e devem manter a mesma política para propriedades desconhecidas no objeto raiz.\n\n## 12. Harness diferencial limitado

O script ferramentas/fuzz_bytecode.py executa mutações reproduzíveis sobre a corpus e persiste relatório JSON e entradas divergentes: 
- seed padrão 0x47505632;
- 64 iterações por padrão, configurável entre 1 e 512;
- timeout por execução nativa configurável entre 0,1 e 5 segundos;
- fixtures limitadas a 2 MiB;
- processo nativo limitado a 512 MiB de segmento de dados (RLIMIT_DATA), 3 s de CPU (RLIMIT_CPU) e timeout de parede configurável;
- execução da VM Python limitada a 1.000.000 passos;
- mutações inválidas de bytes/cabeçalho e mutações válidas que reserializam o JSON.

Para entradas aceitas pelo decoder Python, o harness compara sucesso/falha e stdout de execução nas duas VMs. Para entradas recusadas pelo Python, uma execução bem-sucedida da VM C é registrada como divergência. Os casos são determinísticos por seed e podem ser repetidos.

Comando reproduzível no Termux:

    make fuzz-bytecode FUZZ_ITERATIONS=64 FUZZ_SEED=0x47505632 FUZZ_TIMEOUT=2

Execução verificada em 2026-11-06: 64 iterações, 37 entradas rejeitadas, 27 entradas aceitas/executadas e zero divergências. O harness é smoke fuzzing limitado; ainda não é guiado por cobertura e limita o segmento de dados do processo nativo, mas não impõe um teto universal de memória virtual; RLIMIT_AS é incompatível com os mapeamentos CFI do linker Bionic no Android.

A política de extensões acima é normativa para o envelope raiz v2; propriedades desconhecidas são ignoradas e produtores devem preferir o prefixo x-.

## 13. Pontos ainda não congelados

1. Política formal para campos JSON desconhecidos e extensões futuras.
2. Esquema normativo de versão do IR separado da versão do contêiner.
3. Regras de migração e prazo de remoção do JSON legado v1.
4. Catálogo completo de semântica de cada opcode, incluindo efeitos na pilha e erros de runtime.
5. Fixtures binárias douradas, testes cruzados em mais arquiteturas e estratégia de fuzzing.
6. Congelamento de limites e requisitos de segurança para distribuição pública.

Até que esses pontos sejam decididos, o formato v2 permanece experimental. Este documento é um rascunho de implementação, não uma promessa de estabilidade GP 1.0.
