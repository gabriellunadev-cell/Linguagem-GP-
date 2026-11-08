# Biblioteca padrão inicial — Gabriel Programming

Este documento registra as primitivas de biblioteca padrão já implementadas e os contratos públicos que precisam permanecer consistentes entre o interpretador bootstrap, a VM Python e a VM C.

## `unir_textos(partes: lista texto) -> texto`

Concatena todos os itens da lista, sem inserir separador entre eles.

- Uma lista vazia produz `""`.
- Todos os itens precisam ser valores `texto`; qualquer outro tipo gera erro de runtime.
- A saída é limitada a 64 MiB em UTF-8 para manter o consumo previsível.
- A implementação Python e a implementação C aplicam o mesmo contrato e preservam os bytes UTF-8 dos itens válidos.
- Complexidade esperada: uma passagem para medir e outra para copiar os fragmentos, proporcional ao tamanho total da saída.

Exemplo:

```gp
lista texto partes = ["Olá", " ", "Gabriel", " 🚀"]
texto mensagem = unir_textos(partes)
mostrar(mensagem)
```

Para grandes blocos de texto, prefira acumular fragmentos em `lista texto` e chamar `unir_textos` uma vez, em vez de concatenar repetidamente a string acumulada dentro de um laço.

## Compatibilidade e limites

A primitiva está disponível no interpretador bootstrap, VM Python, VM C e no frontend auto-hospedado. O backend GP→C continua sendo experimental e não oferece suporte geral a listas; não declarar compatibilidade desse backend com `unir_textos` até que sua representação de coleções seja implementada.

Este documento é uma especificação inicial. Assinaturas, diagnósticos, limites de texto e comportamento Unicode devem permanecer cobertos por testes de conformidade.


## `tamanho(valor: texto | lista) -> numero`

Retorna a quantidade de caracteres Unicode de um texto ou a quantidade de elementos de uma lista.

- Para texto, conta pontos de código UTF-8, não bytes nem unidades UTF-16.
- Para lista, conta elementos; não percorre recursivamente listas ou estruturas internas.
- Outros tipos e quantidade incorreta de argumentos geram erro de runtime.

```gp
texto nome = "Gabriel 🚀"
lista numero valores = [10, 20, 30]
mostrar(tamanho(nome))
mostrar(tamanho(valores))
```

## `adicionar(alvo: lista, valor: qualquer) -> lista`

Adiciona um elemento ao final da lista e retorna a própria lista alterada.

- A operação modifica a lista recebida; não cria uma cópia independente.
- Em listas tipadas (`lista numero`, `lista texto`, etc.), o valor precisa respeitar o tipo declarado.
- Lista inválida ou quantidade incorreta de argumentos gera erro de runtime.

```gp
lista texto nomes = ["Ana"]
adicionar(nomes, "Bia")
mostrar(nomes)
```

## `remover(alvo: lista, indice: numero inteiro) -> valor`

Remove o elemento no índice indicado, desloca os elementos seguintes uma posição e retorna o elemento removido.

- Índices começam em zero.
- Índice negativo, fracionário ou fora dos limites gera erro de runtime.
- A lista original é modificada.

```gp
lista numero valores = [10, 20, 30]
numero removido = remover(valores, 1)
mostrar(removido)
mostrar(valores)
```

## Instruções e intrínsecos do host

- `mostrar(...)` é uma instrução da linguagem, não uma função da biblioteca. Aceita uma ou mais expressões e escreve os valores na saída padrão.
- `entrada_fonte()` é um intrínseco reservado ao frontend auto-hospedado: devolve a fonte GP explicitamente fornecida pelo host por stdin/arquivo. Não é uma API geral de leitura arbitrária de arquivos e falha quando o host não fornece a fonte.

## Matriz de disponibilidade atual

| Recurso | Interpretador bootstrap | VM Python | VM C nativa | Frontend auto-hospedado |
|---|---|---|---|---|
| `tamanho` | Sim | Sim | Sim | Sim |
| `adicionar` | Sim | Sim | Sim | Sim |
| `remover` | Sim | Sim | Sim | Sim |
| `unir_textos` | Sim | Sim | Sim | Sim |
| `entrada_fonte` | Não é API geral | Sim, com fonte do host | Sim, com fonte do host | Sim, para compilar a própria fonte |
| `mostrar` | Instrução | Opcode/runtime | Opcode/runtime | Instrução |

Esta é a biblioteca padrão inicial efetivamente implementada, não uma promessa de biblioteca completa. APIs de arquivos, rede, sistema operacional, datas, matemática ampliada, testes, concorrência e pacotes ainda não fazem parte do contrato estável 0.8.52. Cada novo módulo deve ser adicionado somente após especificação, paridade entre runtimes, limites de recursos e testes positivos/negativos.
