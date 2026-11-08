# AST da Gabriel Programming

## Representação atual

A implementação inicial da AST está em linguagem/parser_gp.gp e usa uma arena tipada:

    estrutura NoAST_GP {
        texto categoria;
        texto valor;
        lista numero filhos;
        numero linha;
        numero coluna;
    }
    lista NoAST_GP arvore_ast_gp = []

Cada nó é armazenado uma única vez no array arvore_ast_gp. Seus filhos são referências por índice para outros nós da mesma arena. O nó raiz tem categoria PROGRAMA.

Essa forma evita ponteiros e listas genéricas aninhadas, mantém os nós em armazenamento tipado e permite referências compartilhadas no futuro. O índice de um nó é a posição retornada após sua inserção na arena.

## Categorias implementadas

| Categoria | Valor | Filhos |
|---|---|---|
| PROGRAMA | vazio | comandos do programa |
| BLOCO | vazio | comandos do bloco |
| DECLARACAO | tipo e nome (tipo\|nome) | expressão inicial |
| ATRIBUICAO | = | identificador e expressão |
| MOSTRAR | vazio | argumentos |
| SE | vazio ou senao | condição, bloco então e, opcionalmente, bloco senão |
| ENQUANTO | vazio | condição e bloco |
| PARA | vazio | inicialização, condição, incremento e bloco |
| FUNCAO | nome e tipo de retorno | parâmetros seguidos pelo bloco |
| PARAMETRO | tipo e nome (tipo\|nome) | nenhum |
| RETORNAR | vazio | expressão opcional |
| ESTRUTURA | nome da estrutura | campos declarados |
| CAMPO_DECLARADO | tipo e nome (tipo\|nome) | nenhum |
| QUEBRAR | vazio | nenhum |
| CONTINUAR | vazio | nenhum |
| VAZIO | cláusula omitida do para | nenhum |
| LITERAL | tipo e lexema | nenhum |
| IDENTIFICADOR | nome | nenhum |
| UNARIO | operador | operando |
| BINARIO | operador | esquerda e direita |
| AGRUPAMENTO | () | expressão agrupada |
| CHAMADA | nome da função | argumentos |
| ARRAY | vazio | elementos |
| INDICE | [] | base e índice |
| CAMPO | nome do campo | estrutura-base |

## API interna

- validar_sintaxe_gp(fonte) tokeniza, analisa e cria a AST; retorna logico.
- obter_no_ast_gp(indice) retorna a estrutura do nó.
- resumo_no_ast_gp(indice) retorna categoria e valor.
- quantidade_filhos_ast_gp(indice) informa a quantidade de filhos.
- obter_filho_ast_gp(indice, posicao) retorna o índice de um filho.
- linha_no_ast_gp(indice) e coluna_no_ast_gp(indice) consultam a posição do cursor quando o nó foi criado.
- raiz_ast_gp contém o índice raiz quando a análise tem sucesso.

## Limitações conhecidas

A gramática auto-hospedada ainda é parcial. O parser reconhece blocos, se/senao, enquanto, para, funções com parâmetros e retornar, mas ainda não cobre tipos compostos em todos os contextos, inicialização de campos, métodos ou validação contextual de quebrar/continuar dentro de laços. A análise semântica e a geração de IR/bytecode continuam no pipeline bootstrap; a AST GP ainda não foi integrada como front-end substituto.

Linha e coluna representam, nesta versão, a posição do cursor no momento da criação do nó; ainda não são spans exatos de início/fim do lexema. Os diagnósticos do parser são mensagens textuais básicas, não objetos estruturados. O parser mantém contexto de laços e funções para rejeitar quebrar/continuar fora de laços e retornar fora de funções; ao entrar numa função, o contexto de laço externo é isolado. Próximo passo: spans precisos, recuperação/diagnósticos estruturados e testes de gramática negativa mais amplos.
