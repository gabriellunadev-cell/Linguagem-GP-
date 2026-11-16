// Resolver puro de grafo de modulos. O host continua responsavel por abrir
// arquivos e validar caminhos; a travessia, ciclos, aliases e ordem pertencem a GP.
funcao modulo_lista_contem_gp(lista texto itens, texto alvo) -> logico {
    numero i = 0
    enquanto (i < tamanho(itens)) {
        se (itens[i] == alvo) { retornar verdadeiro }
        i = i + 1
    }
    retornar falso
}

funcao modulo_aliases_validos_gp(lista texto origens, lista texto aliases) -> logico {
    se (tamanho(origens) != tamanho(aliases) || tamanho(origens) > 128) { retornar falso }
    numero i = 0
    numero j = 0
    enquanto (i < tamanho(origens)) {
        j = 0
        enquanto (j < i) {
            se (origens[i] == origens[j] && aliases[i] == aliases[j]) { retornar falso }
            j = j + 1
        }
        i = i + 1
    }
    retornar verdadeiro
}

funcao visitar_modulo_gp(texto caminho, numero profundidade, lista texto origens, lista texto destinos, lista texto visitando, lista texto visitados, lista texto ordem) -> logico {
    se (profundidade > 32) { retornar falso }
    se (modulo_lista_contem_gp(visitando, caminho)) { retornar falso }
    se (modulo_lista_contem_gp(visitados, caminho)) { retornar verdadeiro }

    adicionar(visitando, caminho)
    numero i = 0
    enquanto (i < tamanho(origens)) {
        se (origens[i] == caminho) {
            se (!visitar_modulo_gp(destinos[i], profundidade + 1, origens, destinos, visitando, visitados, ordem)) {
                retornar falso
            }
        }
        i = i + 1
    }
    texto removido = remover(visitando, tamanho(visitando) - 1)
    adicionar(visitados, caminho)
    adicionar(ordem, caminho)
    retornar verdadeiro
}

funcao resolver_modulos_gp(lista texto origens, lista texto destinos, lista texto aliases, lista texto raizes) -> lista texto {
    lista texto ordem = []
    lista texto falha = []
    lista texto visitando = []
    lista texto visitados = []
    se (tamanho(origens) != tamanho(destinos) || !modulo_aliases_validos_gp(origens, aliases)) {
        retornar ordem
    }
    numero i = 0
    enquanto (i < tamanho(raizes)) {
        se (!visitar_modulo_gp(raizes[i], 1, origens, destinos, visitando, visitados, ordem)) {
            retornar falha
        }
        i = i + 1
    }
    retornar ordem
}
