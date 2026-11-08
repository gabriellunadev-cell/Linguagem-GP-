# Especificação inicial da linguagem GP

Versão de referência: Core 0.4.

A sintaxe evolui mediante testes de compatibilidade. A implementação do parser no bootstrap é a referência prática atual.

## Tokens e comentários

- Identificadores aceitam letras, números e sublinhado; letras portuguesas são aceitas.
- Textos usam aspas duplas e escapes JSON comuns.
- Números inteiros e decimais usam ponto.
- Comentários de linha começam com `//`.
- Ponto e vírgula é opcional na maioria das instruções.
- Campos de estrutura exigem ponto e vírgula.
- O cabeçalho de `para` usa ponto e vírgula como separador obrigatório.

## Tipos

- `numero`: inteiros e decimais; booleanos não são números.
- `texto`: sequência de caracteres.
- `logico`: verdadeiro ou falso.
- `lista TIPO`: lista homogênea, por exemplo `lista numero itens = [1, 2]`.
- Estruturas nomeadas: tipos definidos com `estrutura Nome { ... }`.

## Gramática simplificada

    programa = [ "programa" STRING ], { instrucao } ;
    instrucao = declaracao | funcao | estrutura | importar
              | condicional | enquanto | para | retorno
              | mostrar | atribuicao | expressao ;
    tipo = "numero" | "texto" | "logico" | IDENT
         | "lista", ( "numero" | "texto" | "logico" | IDENT ) ;
    declaracao = tipo, IDENT, "=", expressao, [ ";" ] ;
    funcao = "funcao", IDENT, "(", [ parametros ], ")",
             [ "->", tipo ], bloco ;
    parametros = parametro, { ",", parametro } ;
    parametro = tipo, IDENT ;
    estrutura = "estrutura", IDENT, "{", { tipo, IDENT, ";" }, "}" ;
    importar = "usar", STRING, "como", IDENT, [ ";" ] ;
    condicional = "se", "(", expressao, ")", bloco,
                  [ "senao", bloco ] ;
    enquanto = "enquanto", "(", expressao, ")", bloco ;
    para = "para", "(", [ declaracao_ou_atribuicao ], ";",
           [ expressao ], ";", [ atribuicao_ou_expressao ], ")", bloco ;
    retorno = "retornar", [ expressao ], [ ";" ] ;
    mostrar = "mostrar", "(", [ expressao, { ",", expressao } ], ")",
              [ ";" ] ;
    bloco = "{", { instrucao }, "}" ;

## Expressões

O parser Pratt aceita valores literais, nomes, arrays, chamadas, indexação, acesso a campo, construtores de estrutura e operadores unários/binários.

Exemplo:

    estrutura Pessoa {
        texto nome;
        numero idade;
    }

    Pessoa p = Pessoa{nome: "Ada", idade: 37}
    p.idade = 38
    mostrar(p.nome, p.idade)

## Precedência

Da menor para a maior:

| Operadores | Significado |
|---|---|
| `||` | OU lógico |
| `&&` | E lógico |
| `== !=` | igualdade e diferença |
| `> < >= <=` | comparação |
| `+ -` | soma e subtração |
| `* / %` | multiplicação, divisão e módulo |
| `! -` unários | negação lógica e sinal |

## Módulos

Um módulo local é carregado com:

    usar "matematica.gp" como math
    mostrar(math.somar(2, 3))

No Core 0.4, o módulo deve ser um arquivo local e exportar funções. O caminho é relativo ao arquivo principal. Imports aninhados, pacotes externos e estruturas exportadas não estão implementados.

## Biblioteca padrão inicial

- `tamanho(valor)`: comprimento de texto ou lista.
- `adicionar(lista, valor)`: adiciona respeitando o tipo do array tipado.
- `remover(lista, indice)`: remove e retorna o elemento.

## Escopos e fluxo

Blocos condicionais e laços criam escopos locais. Atribuições procuram a declaração mais próxima nos escopos externos. Funções possuem frames próprios. A VM limita a quantidade total de instruções para interromper loops que não terminam.
