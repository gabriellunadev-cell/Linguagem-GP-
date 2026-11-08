// Tabela de simbolos GP: escopos hierarquicos e resolucao por cadeia de pais.
estrutura SimboloGP {
    texto nome;
    texto tipo;
    numero escopo;
}
lista SimboloGP simbolos_gp = []
lista numero pais_escopos_gp = []

funcao resetar_semantica_gp() -> logico {
    simbolos_gp = []
    pais_escopos_gp = []
    adicionar(pais_escopos_gp, -1)
    retornar verdadeiro
}

funcao criar_escopo_gp(numero escopo_pai) -> numero {
    adicionar(pais_escopos_gp, escopo_pai)
    retornar tamanho(pais_escopos_gp) - 1
}

funcao declarar_simbolo_gp(texto nome, texto tipo, numero escopo) -> logico {
    numero i = tamanho(simbolos_gp) - 1
    SimboloGP item = SimboloGP{nome: "", tipo: "", escopo: -1}
    enquanto (i >= 0) {
        item = simbolos_gp[i]
        se (item.escopo == escopo && item.nome == nome) {
            retornar falso
        }
        i = i - 1
    }
    SimboloGP novo = SimboloGP{nome: nome, tipo: tipo, escopo: escopo}
    adicionar(simbolos_gp, novo)
    retornar verdadeiro
}

funcao buscar_simbolo_gp(texto nome, numero escopo) -> numero {
    numero atual = escopo
    numero i = 0
    SimboloGP item = SimboloGP{nome: "", tipo: "", escopo: -1}
    enquanto (atual >= 0) {
        i = tamanho(simbolos_gp) - 1
        enquanto (i >= 0) {
            item = simbolos_gp[i]
            se (item.escopo == atual && item.nome == nome) {
                retornar i
            }
            i = i - 1
        }
        se (atual >= tamanho(pais_escopos_gp)) {
            retornar -1
        }
        atual = pais_escopos_gp[atual]
    }
    retornar -1
}

funcao tipo_simbolo_gp(texto nome, numero escopo) -> texto {
    numero indice = buscar_simbolo_gp(nome, escopo)
    se (indice < 0) { retornar "" }
    SimboloGP item = simbolos_gp[indice]
    retornar item.tipo
}

funcao quantidade_simbolos_gp() -> numero {
    retornar tamanho(simbolos_gp)
}

resetar_semantica_gp()

numero escopo_raiz = 0
numero escopo_funcao = criar_escopo_gp(escopo_raiz)
numero escopo_bloco = criar_escopo_gp(escopo_funcao)

mostrar("Declaracao global:", declarar_simbolo_gp("idade", "numero", escopo_raiz))
mostrar("Duplicata global rejeitada:", !declarar_simbolo_gp("idade", "texto", escopo_raiz))
mostrar("Sombreamento local permitido:", declarar_simbolo_gp("idade", "texto", escopo_funcao))
mostrar("Variavel local:", tipo_simbolo_gp("idade", escopo_funcao))
mostrar("Variavel no bloco:", declarar_simbolo_gp("ativo", "logico", escopo_bloco))
mostrar("Heranca de escopo:", tipo_simbolo_gp("idade", escopo_bloco))
mostrar("Tipo global:", tipo_simbolo_gp("idade", escopo_raiz))
mostrar("Desconhecido:", tipo_simbolo_gp("inexistente", escopo_raiz) == "")
mostrar("Total de simbolos:", quantidade_simbolos_gp())
