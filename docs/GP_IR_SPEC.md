# GP-IR — Especificação formal preliminar

**Estado:** rascunho 0.1 — GP 0.8.31. Ainda não congelada.

## 1. Identidade e versionamento

GP-IR é a representação intermediária tipada do compilador Gabriel Programming. Seu identificador é `GP-IR` e sua versão de formato atual é o inteiro `1` (`IR_VERSION = 1`). Essa versão descreve a estrutura dos registros, instruções, operandos, funções e regras de endereçamento.

Três versões são independentes:

| Campo | Exemplo | Governa |
|---|---|---|
| Versão do contêiner | `bytecode_version = 2` / cabeçalho GGPC `2` | transporte binário, compressão, checksum e envelope |
| Versão do formato IR | `program.ir_version = 1` e cabeçalho de transporte GP-IR `1` | estrutura e semântica da representação intermediária |
| Versão da linguagem | `language_version = "0.4"` e `program.version = "0.4"` | recursos e regras da linguagem-fonte |

Uma mudança incompatível no transporte binário exige nova versão de contêiner. Uma mudança incompatível na estrutura ou semântica do IR exige nova versão de GP-IR. Evolução da linguagem, sem mudança incompatível no IR, não incrementa automaticamente nenhum dos dois formatos.

O campo `program.ir_version` foi introduzido de forma aditiva. Leitores que recebem artefatos v2 históricos sem esse campo interpretam-nos como GP-IR v1. Novos produtores devem emitir o campo explicitamente.

## 2. Modelo

`IRProgram(language_version, instructions, functions, ir_version=1)` contém um bloco principal ordenado e um mapa de funções. Cada `IRInstruction` contém `opcode` e tupla ordenada `operands`. Cada `IRFunction` contém nome, parâmetros `(tipo, nome)`, tipo de retorno opcional e bloco de instruções.

## 3. Instruções

O conjunto v1 é: `CONST`, `LOAD`, `DECLARE`, `STORE`, `POP`, `BUILD_ARRAY`, `MAKE_TYPED_ARRAY`, `BUILD_STRUCT`, `GET_FIELD`, `SET_FIELD`, `GET_INDEX`, `SET_INDEX`, `NEG`, `NOT`, `ADD`, `SUB`, `MUL`, `DIV`, `MOD`, `EQ`, `NE`, `GT`, `LT`, `GE`, `LE`, `AND`, `OR`, `PRINT`, `JUMP`, `JUMP_IF_FALSE`, `CALL`, `RETURN`.

| Opcode | Operandos | Regra |
|---|---|---|
| CONST | `(valor)` | JSON escalar: null, boolean, número finito ou texto |
| LOAD / STORE / GET_FIELD / SET_FIELD / MAKE_TYPED_ARRAY | `(texto)` | texto não vazio |
| DECLARE | `(nome, tipo, tipo_elemento)` | tipo_elemento é texto apenas quando tipo=`lista`; caso contrário null |
| BUILD_ARRAY / PRINT | `(quantidade)` | inteiro não negativo |
| BUILD_STRUCT | `(nome, schema)` | schema é sequência ordenada de pares `(nome_campo, tipo)` sem duplicatas |
| JUMP / JUMP_IF_FALSE | `(destino)` | inteiro não negativo no intervalo `0..len(bloco)` |
| CALL | `(nome_funcao, quantidade)` | nome não vazio e quantidade inteira não negativa |
| POP, GET_INDEX, SET_INDEX, NEG, NOT, ADD, SUB, MUL, DIV, MOD, EQ, NE, GT, LT, GE, LE, AND, OR, RETURN | `()` | nenhum operando |

Booleanos não são inteiros válidos para contagens ou destinos. Opcode desconhecido, aridade incorreta, tipo inválido, constante não finita, schema ou parâmetro duplicado são erros de validação.

## 4. Blocos e funções

O mapa `functions` associa o nome não vazio à definição com o mesmo nome. Parâmetros são pares ordenados `(tipo, nome)`; tipo e nome não podem ser vazios e nomes não podem se repetir. `return_type` é null ou texto não vazio. O bloco principal e cada função têm endereços de salto próprios.

## 5. Saltos

Os destinos são índices absolutos locais ao bloco. `len(code)` significa saída do bloco. O compilador GP pode usar rótulos simbólicos durante a construção, mas deve resolvê-los antes de materializar GP-IR v1 executável. Não são permitidos destinos negativos, booleanos, fracionários ou além do fim do bloco.

## 6. Validação

Todo IR deve passar por `validate_ir` antes de ser codificado. Adaptadores também validam o resultado materializado. A validação inclui versão, raiz, blocos, opcodes, aridade, tipos, finitude numérica, parâmetros, schemas e destinos. O decoder de bytecode valida o `ir_version` declarado e aceita ausência somente como compatibilidade histórica, interpretando-a como versão 1.

## 7. Compatibilidade

O cabeçalho de registros emitido pelo frontend GP é `GP-IR` versão 1. O formato binário GGPC v2 é apenas o contêiner que transporta esse IR; os dois números não são intercambiáveis. O adaptador Python atual continua responsável pela conversão dos registros GP em objetos tipados; a substituição dessa etapa por materialização nativa GP ainda não foi concluída.


## 8. Envelope canônico produzido pelo frontend GP

A partir do ciclo 0.8.32, o frontend GP emite diretamente um objeto JSON GP-IR v1:

```json
{
  "format": "GP-IR",
  "ir_version": 1,
  "version": "0.4",
  "main": [{"op": "CONST", "args": [42]}],
  "functions": {
    "dobro": {
      "return_type": "numero",
      "parameters": [["numero", "valor"]],
      "code": [{"op": "LOAD", "args": ["valor"]}, {"op": "RETURN", "args": []}]
    }
  }
}
```

Cada instrução contém exatamente `op` e `args`. Schemas de estrutura são incorporados ao segundo operando de `BUILD_STRUCT` como lista ordenada de pares `[nome, tipo]`. `main` e `code` são blocos independentes; endereços de salto permanecem locais a cada bloco. `functions` é um objeto indexado pelo nome, e cada função declara `return_type`, `parameters` e `code`. O frontend GP é responsável por organizar essas seções e resolver rótulos antes da emissão.

O objeto GP-IR v1 contém exatamente `format`, `ir_version`, `version`, `main` e `functions`. Cada definição de função contém exatamente `return_type`, `parameters` e `code`. Campos adicionais nesses objetos, assim como nas instruções, são inválidos. Essa regra é aplicada pelo encoder direto e pelos decoders Python/C; não se confunde com a política de extensões do objeto externo GGPC v2.

No ciclo 0.8.32, o runner ainda emite também o envelope de registros anterior. O host compara as duas formas após hidratação tipada e rejeita qualquer divergência. Esse modo diferencial é transitório e serve como prova de conformidade antes da retirada do adaptador legado.


## 9. Codificação direta do envelope canônico (ciclo 0.8.33)

encode_canonical_ir(document) consome o objeto JSON GP-IR v1 já produzido pelo frontend GP. O caminho valida o documento com validate_canonical_ir e projeta os campos normativos para a ordem estável compatível com ir_to_dict. Não cria objetos IRProgram ou IRFunction.

A codificação usa o mesmo invólucro GGPC v2 da API anterior: JSON UTF-8 compacto, compressão zlib nível 9, CRC32 do payload descomprimido e cabeçalho >4sHII. Para documentos equivalentes, encode_canonical_ir(document) deve produzir bytes exatamente iguais a encode(IRProgram).

A API encode(IRProgram) permanece disponível como caminho de compatibilidade. compile_source_selfhosted_document retorna o documento JSON; compile_source_selfhosted preserva o contrato anterior e ainda retorna IRProgram. O CLI --self-hosted usa o documento canônico e encode_canonical_ir diretamente.

A conformidade reproduzível está em tests/fixtures/gp_ir_direct/, com fontes, envelopes GP-IR, bytecodes direto/legado/bootstrap, manifesto e SHA-256. Após o ciclo 0.8.35: 6/6 fontes são aceitas diretamente pelo frontend GP; os seis bytecodes diretos são idênticos aos do encoder legado; os seis bytecodes do frontend GP são estruturalmente idênticos aos do bootstrap; e as VMs Python e C coincidem em 6/6 execuções. Os 38 artefatos do manifesto passam na verificação SHA-256.

A divergência estrutural anteriormente observada em control_flow_nested.gp foi corrigida no bootstrap. Um teste adicional compara o GP-IR do frontend GP e do bootstrap para condicionais sem senao, com senao vazio e com ramo preenchido, inclusive dentro de função. O adaptador legado permanece ativo como oráculo/fallback; sua remoção ainda exige uma estratégia de conformidade mais ampla e a migração segura das responsabilidades do host.
