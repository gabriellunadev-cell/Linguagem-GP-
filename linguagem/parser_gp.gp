usar "lexer_gp.gp" como lexer

// AST GP baseada em arena: cada no guarda categoria, valor e indices dos filhos.
// Os indices permitem referencias hierarquicas sem ponteiros nem listas aninhadas.
estrutura NoAST_GP {
    texto categoria;
    texto valor;
    lista numero filhos;
    numero linha;
    numero coluna;
}
lista texto tokens_parser = []
lista NoAST_GP arvore_ast_gp = []
numero cursor_parser = 0
numero ultimo_no_ast_gp = -1
numero raiz_ast_gp = -1
numero linha_parser = 1
numero coluna_parser = 1
numero profundidade_laco_parser = 0
numero profundidade_funcao_parser = 0
logico erro_parser = falso
texto mensagem_parser = ""

funcao criar_no_ast_gp(texto categoria, texto valor, lista numero filhos) -> numero {
    NoAST_GP novo_no = NoAST_GP{categoria: categoria, valor: valor, filhos: filhos, linha: linha_parser, coluna: coluna_parser}
    adicionar(arvore_ast_gp, novo_no)
    ultimo_no_ast_gp = tamanho(arvore_ast_gp) - 1
    retornar ultimo_no_ast_gp
}
funcao obter_no_ast_gp(numero indice) -> NoAST_GP {
    retornar arvore_ast_gp[indice]
}
funcao resumo_no_ast_gp(numero indice) -> texto {
    NoAST_GP no_lido = arvore_ast_gp[indice]
    retornar no_lido.categoria + "|" + no_lido.valor
}
funcao linha_no_ast_gp(numero indice) -> numero {
    NoAST_GP no_lido = arvore_ast_gp[indice]
    retornar no_lido.linha
}
funcao coluna_no_ast_gp(numero indice) -> numero {
    NoAST_GP no_lido = arvore_ast_gp[indice]
    retornar no_lido.coluna
}
funcao quantidade_filhos_ast_gp(numero indice) -> numero {
    NoAST_GP no_lido = arvore_ast_gp[indice]
    retornar tamanho(no_lido.filhos)
}
funcao obter_filho_ast_gp(numero indice, numero posicao) -> numero {
    NoAST_GP no_lido = arvore_ast_gp[indice]
    retornar no_lido.filhos[posicao]
}
funcao atual_parser() -> texto {
    se (cursor_parser >= tamanho(tokens_parser)) { retornar "" }
    retornar tokens_parser[cursor_parser]
}
funcao atualizar_posicao_parser(texto lexema) -> logico {
    numero i = 0
    enquanto (i < tamanho(lexema)) {
        se (lexema[i] == "\n") {
            linha_parser = linha_parser + 1
            coluna_parser = 1
        } senao {
            coluna_parser = coluna_parser + 1
        }
        i = i + 1
    }
    retornar verdadeiro
}
funcao avancar_parser() -> logico {
    atualizar_posicao_parser(atual_parser())
    cursor_parser = cursor_parser + 1
    retornar verdadeiro
}
funcao consumir_parser(texto esperado) -> logico {
    se (atual_parser() == esperado) {
        avancar_parser()
        retornar verdadeiro
    }
    erro_parser = verdadeiro
    mensagem_parser = "Esperado '" + esperado + "', encontrado '" + atual_parser() + "'"
    retornar falso
}
funcao aceitar_parser(texto esperado) -> logico {
    se (atual_parser() == esperado) {
        avancar_parser()
        retornar verdadeiro
    }
    retornar falso
}

funcao parse_primaria_gp() -> logico {
    texto token = atual_parser()
    texto tipo = lexer.classificar_lexema_gp(token)
    texto nome = ""
    numero argumentos = 0
    numero base = -1
    lista numero filhos = []
    se (token == "(") {
        avancar_parser()
        se (!parse_expressao_gp()) { retornar falso }
        adicionar(filhos, ultimo_no_ast_gp)
        se (!consumir_parser(")")) { retornar falso }
        criar_no_ast_gp("AGRUPAMENTO", "()", filhos)
        retornar verdadeiro
    }
    se (token == "-" || token == "!") {
        avancar_parser()
        se (!parse_primaria_gp()) { retornar falso }
        adicionar(filhos, ultimo_no_ast_gp)
        criar_no_ast_gp("UNARIO", token, filhos)
        retornar verdadeiro
    }
    se (tipo == "NUMERO" || tipo == "TEXTO" || token == "verdadeiro" || token == "falso") {
        avancar_parser()
        criar_no_ast_gp("LITERAL", tipo + "|" + token, filhos)
        retornar verdadeiro
    }
    se (token == "[") {
        avancar_parser()
        se (atual_parser() != "]") {
            se (!parse_expressao_gp()) { retornar falso }
            adicionar(filhos, ultimo_no_ast_gp)
            enquanto (aceitar_parser(",")) {
                se (!parse_expressao_gp()) { retornar falso }
                adicionar(filhos, ultimo_no_ast_gp)
            }
        }
        se (!consumir_parser("]")) { retornar falso }
        criar_no_ast_gp("ARRAY", "", filhos)
        retornar verdadeiro
    }
    se (tipo == "IDENTIFICADOR") {
        nome = token
        avancar_parser()
        se (aceitar_parser("{")) {
            texto nome_argumento_nomeado = ""
            lista numero filhos_argumento_nomeado = []
            enquanto (atual_parser() != "}" && atual_parser() != "" && !erro_parser) {
                se (lexer.classificar_lexema_gp(atual_parser()) != "IDENTIFICADOR") {
                    erro_parser = verdadeiro
                    mensagem_parser = "Nome de campo esperado no construtor " + nome
                    retornar falso
                }
                nome_argumento_nomeado = atual_parser()
                avancar_parser()
                se (!consumir_parser(":")) { retornar falso }
                se (!parse_expressao_gp()) { retornar falso }
                filhos_argumento_nomeado = []
                adicionar(filhos_argumento_nomeado, ultimo_no_ast_gp)
                criar_no_ast_gp("CAMPO_ARGUMENTO", nome_argumento_nomeado, filhos_argumento_nomeado)
                adicionar(filhos, ultimo_no_ast_gp)
                se (!aceitar_parser(",")) { quebrar }
            }
            se (!consumir_parser("}")) { retornar falso }
            criar_no_ast_gp("CHAMADA_NOMEADA", nome, filhos)
        } senao {
            se (aceitar_parser("(")) {
                se (atual_parser() != ")") {
                    se (!parse_expressao_gp()) { retornar falso }
                    adicionar(filhos, ultimo_no_ast_gp)
                    argumentos = argumentos + 1
                    enquanto (aceitar_parser(",")) {
                        se (!parse_expressao_gp()) { retornar falso }
                        adicionar(filhos, ultimo_no_ast_gp)
                        argumentos = argumentos + 1
                    }
                }
                se (!consumir_parser(")")) { retornar falso }
                criar_no_ast_gp("CHAMADA", nome, filhos)
            } senao {
                criar_no_ast_gp("IDENTIFICADOR", nome, filhos)
            }
        }
        enquanto (atual_parser() == "[" || atual_parser() == ".") {
            base = ultimo_no_ast_gp
            filhos = []
            adicionar(filhos, base)
            se (aceitar_parser("[")) {
                se (!parse_expressao_gp()) { retornar falso }
                adicionar(filhos, ultimo_no_ast_gp)
                se (!consumir_parser("]")) { retornar falso }
                criar_no_ast_gp("INDICE", "[]", filhos)
            } senao {
                aceitar_parser(".")
                se (lexer.classificar_lexema_gp(atual_parser()) != "IDENTIFICADOR") {
                    erro_parser = verdadeiro
                    mensagem_parser = "Nome de campo esperado"
                    retornar falso
                }
                token = atual_parser()
                avancar_parser()
                criar_no_ast_gp("CAMPO", token, filhos)
            }
        }
        retornar verdadeiro
    }
    erro_parser = verdadeiro
    mensagem_parser = "Expressao invalida perto de '" + token + "'"
    retornar falso
}
funcao parse_multiplicacao_gp() -> logico {
    texto operador = ""
    numero esquerdo = -1
    lista numero filhos = []
    se (!parse_primaria_gp()) { retornar falso }
    enquanto (atual_parser() == "*" || atual_parser() == "/" || atual_parser() == "%") {
        operador = atual_parser()
        avancar_parser()
        esquerdo = ultimo_no_ast_gp
        se (!parse_primaria_gp()) { retornar falso }
        filhos = []
        adicionar(filhos, esquerdo)
        adicionar(filhos, ultimo_no_ast_gp)
        criar_no_ast_gp("BINARIO", operador, filhos)
    }
    retornar verdadeiro
}
funcao parse_adicao_gp() -> logico {
    texto operador = ""
    numero esquerdo = -1
    lista numero filhos = []
    se (!parse_multiplicacao_gp()) { retornar falso }
    enquanto (atual_parser() == "+" || atual_parser() == "-") {
        operador = atual_parser()
        avancar_parser()
        esquerdo = ultimo_no_ast_gp
        se (!parse_multiplicacao_gp()) { retornar falso }
        filhos = []
        adicionar(filhos, esquerdo)
        adicionar(filhos, ultimo_no_ast_gp)
        criar_no_ast_gp("BINARIO", operador, filhos)
    }
    retornar verdadeiro
}
funcao parse_comparacao_gp() -> logico {
    texto operador = ""
    numero esquerdo = -1
    lista numero filhos = []
    se (!parse_adicao_gp()) { retornar falso }
    enquanto (atual_parser() == "==" || atual_parser() == "!=" || atual_parser() == ">" || atual_parser() == "<" || atual_parser() == ">=" || atual_parser() == "<=") {
        operador = atual_parser()
        avancar_parser()
        esquerdo = ultimo_no_ast_gp
        se (!parse_adicao_gp()) { retornar falso }
        filhos = []
        adicionar(filhos, esquerdo)
        adicionar(filhos, ultimo_no_ast_gp)
        criar_no_ast_gp("BINARIO", operador, filhos)
    }
    retornar verdadeiro
}
funcao parse_e_gp() -> logico {
    numero esquerdo = -1
    lista numero filhos = []
    se (!parse_comparacao_gp()) { retornar falso }
    enquanto (atual_parser() == "&&") {
        aceitar_parser("&&")
        esquerdo = ultimo_no_ast_gp
        se (!parse_comparacao_gp()) { retornar falso }
        filhos = []
        adicionar(filhos, esquerdo)
        adicionar(filhos, ultimo_no_ast_gp)
        criar_no_ast_gp("BINARIO", "&&", filhos)
    }
    retornar verdadeiro
}
funcao parse_expressao_gp() -> logico {
    numero esquerdo = -1
    lista numero filhos = []
    se (!parse_e_gp()) { retornar falso }
    enquanto (atual_parser() == "||") {
        aceitar_parser("||")
        esquerdo = ultimo_no_ast_gp
        se (!parse_e_gp()) { retornar falso }
        filhos = []
        adicionar(filhos, esquerdo)
        adicionar(filhos, ultimo_no_ast_gp)
        criar_no_ast_gp("BINARIO", "||", filhos)
    }
    retornar verdadeiro
}
funcao parse_declaracao_gp() -> logico {
    texto tipo = atual_parser()
    texto nome = ""
    texto tipo_elemento = ""
    lista numero filhos = []
    se (tipo == "lista") {
        avancar_parser()
        tipo_elemento = atual_parser()
        se (tipo_elemento != "numero" && tipo_elemento != "texto" && tipo_elemento != "logico" && lexer.classificar_lexema_gp(tipo_elemento) != "IDENTIFICADOR") {
            erro_parser = verdadeiro
            mensagem_parser = "Tipo de elemento de lista invalido"
            retornar falso
        }
        avancar_parser()
        tipo = "lista<" + tipo_elemento + ">"
    } senao {
        se (tipo != "numero" && tipo != "texto" && tipo != "logico" && lexer.classificar_lexema_gp(tipo) != "IDENTIFICADOR") { retornar falso }
        avancar_parser()
    }
    se (lexer.classificar_lexema_gp(atual_parser()) != "IDENTIFICADOR") {
        erro_parser = verdadeiro
        mensagem_parser = "Nome de variavel esperado"
        retornar falso
    }
    nome = atual_parser()
    avancar_parser()
    se (!consumir_parser("=")) { retornar falso }
    se (!parse_expressao_gp()) { retornar falso }
    adicionar(filhos, ultimo_no_ast_gp)
    criar_no_ast_gp("DECLARACAO", tipo + "|" + nome, filhos)
    aceitar_parser(";")
    retornar verdadeiro
}
funcao parse_atribuicao_gp() -> logico {
    lista numero filhos = []
    se (!parse_primaria_gp()) { retornar falso }
    numero destino = ultimo_no_ast_gp
    se (!consumir_parser("=")) { retornar falso }
    se (!parse_expressao_gp()) { retornar falso }
    filhos = []
    adicionar(filhos, destino)
    adicionar(filhos, ultimo_no_ast_gp)
    criar_no_ast_gp("ATRIBUICAO", "=", filhos)
    aceitar_parser(";")
    retornar verdadeiro
}
funcao parse_mostrar_gp() -> logico {
    lista numero filhos = []
    se (!consumir_parser("mostrar")) { retornar falso }
    se (!consumir_parser("(")) { retornar falso }
    se (atual_parser() != ")") {
        se (!parse_expressao_gp()) { retornar falso }
        adicionar(filhos, ultimo_no_ast_gp)
        enquanto (aceitar_parser(",")) {
            se (!parse_expressao_gp()) { retornar falso }
            adicionar(filhos, ultimo_no_ast_gp)
        }
    }
    se (!consumir_parser(")")) { retornar falso }
    criar_no_ast_gp("MOSTRAR", "", filhos)
    aceitar_parser(";")
    retornar verdadeiro
}
funcao parse_bloco_gp() -> logico {
    lista numero filhos_bloco = []
    se (!consumir_parser("{")) { retornar falso }
    enquanto (atual_parser() != "}" && atual_parser() != "" && !erro_parser) {
        se (!parse_comando_gp()) { retornar falso }
        adicionar(filhos_bloco, ultimo_no_ast_gp)
    }
    se (!consumir_parser("}")) { retornar falso }
    criar_no_ast_gp("BLOCO", "", filhos_bloco)
    retornar verdadeiro
}
funcao parse_se_gp() -> logico {
    lista numero filhos_se = []
    se (!consumir_parser("se")) { retornar falso }
    se (!consumir_parser("(")) { retornar falso }
    se (!parse_expressao_gp()) { retornar falso }
    adicionar(filhos_se, ultimo_no_ast_gp)
    se (!consumir_parser(")")) { retornar falso }
    se (!parse_bloco_gp()) { retornar falso }
    adicionar(filhos_se, ultimo_no_ast_gp)
    se (aceitar_parser("senao")) {
        se (!parse_bloco_gp()) { retornar falso }
        adicionar(filhos_se, ultimo_no_ast_gp)
        criar_no_ast_gp("SE", "senao", filhos_se)
    } senao {
        criar_no_ast_gp("SE", "", filhos_se)
    }
    aceitar_parser(";")
    retornar verdadeiro
}
funcao parse_enquanto_gp() -> logico {
    lista numero filhos_enquanto = []
    se (!consumir_parser("enquanto")) { retornar falso }
    se (!consumir_parser("(")) { retornar falso }
    se (!parse_expressao_gp()) { retornar falso }
    adicionar(filhos_enquanto, ultimo_no_ast_gp)
    se (!consumir_parser(")")) { retornar falso }
    profundidade_laco_parser = profundidade_laco_parser + 1
    se (!parse_bloco_gp()) {
        profundidade_laco_parser = profundidade_laco_parser - 1
        retornar falso
    }
    profundidade_laco_parser = profundidade_laco_parser - 1
    adicionar(filhos_enquanto, ultimo_no_ast_gp)
    criar_no_ast_gp("ENQUANTO", "", filhos_enquanto)
    aceitar_parser(";")
    retornar verdadeiro
}
funcao parse_retorno_gp() -> logico {
    lista numero filhos_retorno = []
    se (!consumir_parser("retornar")) { retornar falso }
    se (profundidade_funcao_parser == 0) {
        erro_parser = verdadeiro
        mensagem_parser = "retornar fora de funcao"
        retornar falso
    }
    se (atual_parser() != ";" && atual_parser() != "}" && atual_parser() != "") {
        se (!parse_expressao_gp()) { retornar falso }
        adicionar(filhos_retorno, ultimo_no_ast_gp)
    }
    criar_no_ast_gp("RETORNAR", "", filhos_retorno)
    aceitar_parser(";")
    retornar verdadeiro
}
funcao parse_funcao_gp() -> logico {
    texto nome = ""
    texto retorno = "vazio"
    texto tipo_parametro = ""
    texto tipo_elemento_parametro = ""
    texto tipo_elemento_retorno_funcao = ""
    texto nome_parametro = ""
    lista numero filhos_funcao = []
    lista numero filhos_parametro = []
    numero laco_anterior_funcao = profundidade_laco_parser
    se (!consumir_parser("funcao")) { retornar falso }
    se (lexer.classificar_lexema_gp(atual_parser()) != "IDENTIFICADOR") {
        erro_parser = verdadeiro
        mensagem_parser = "Nome de funcao esperado"
        retornar falso
    }
    nome = atual_parser()
    avancar_parser()
    se (!consumir_parser("(")) { retornar falso }
    enquanto (atual_parser() != ")" && atual_parser() != "" && !erro_parser) {
        tipo_parametro = atual_parser()
        se (tipo_parametro == "lista") {
            avancar_parser()
            tipo_elemento_parametro = atual_parser()
            se (tipo_elemento_parametro != "numero" && tipo_elemento_parametro != "texto" && tipo_elemento_parametro != "logico" && lexer.classificar_lexema_gp(tipo_elemento_parametro) != "IDENTIFICADOR") {
                erro_parser = verdadeiro
                mensagem_parser = "Tipo de elemento da lista de parametro esperado"
                retornar falso
            }
            avancar_parser()
            tipo_parametro = "lista<" + tipo_elemento_parametro + ">"
        } senao {
            se (tipo_parametro != "numero" && tipo_parametro != "texto" && tipo_parametro != "logico" && lexer.classificar_lexema_gp(tipo_parametro) != "IDENTIFICADOR") {
                erro_parser = verdadeiro
                mensagem_parser = "Tipo de parametro esperado"
                retornar falso
            }
            avancar_parser()
        }
        se (lexer.classificar_lexema_gp(atual_parser()) != "IDENTIFICADOR") {
            erro_parser = verdadeiro
            mensagem_parser = "Nome de parametro esperado"
            retornar falso
        }
        nome_parametro = atual_parser()
        avancar_parser()
        filhos_parametro = []
        criar_no_ast_gp("PARAMETRO", tipo_parametro + "|" + nome_parametro, filhos_parametro)
        adicionar(filhos_funcao, ultimo_no_ast_gp)
        se (!aceitar_parser(",")) { quebrar }
    }
    se (!consumir_parser(")")) { retornar falso }
    se (aceitar_parser("->")) {
        retorno = atual_parser()
        se (retorno == "") {
            erro_parser = verdadeiro
            mensagem_parser = "Tipo de retorno esperado"
            retornar falso
        }
        se (retorno == "lista") {
            avancar_parser()
            tipo_elemento_retorno_funcao = atual_parser()
            se (tipo_elemento_retorno_funcao != "numero" && tipo_elemento_retorno_funcao != "texto" && tipo_elemento_retorno_funcao != "logico" && lexer.classificar_lexema_gp(tipo_elemento_retorno_funcao) != "IDENTIFICADOR") {
                erro_parser = verdadeiro
                mensagem_parser = "Tipo de elemento da lista de retorno esperado"
                retornar falso
            }
            avancar_parser()
            retorno = "lista<" + tipo_elemento_retorno_funcao + ">"
        } senao {
            avancar_parser()
        }
    }
    profundidade_funcao_parser = profundidade_funcao_parser + 1
    profundidade_laco_parser = 0
    se (!parse_bloco_gp()) {
        profundidade_funcao_parser = profundidade_funcao_parser - 1
        profundidade_laco_parser = laco_anterior_funcao
        retornar falso
    }
    profundidade_funcao_parser = profundidade_funcao_parser - 1
    profundidade_laco_parser = laco_anterior_funcao
    adicionar(filhos_funcao, ultimo_no_ast_gp)
    criar_no_ast_gp("FUNCAO", nome + " -> " + retorno, filhos_funcao)
    retornar verdadeiro
}
funcao parse_para_gp() -> logico {
    lista numero filhos_para = []
    lista numero filhos_vazios = []
    logico incremento_chamada_funcao = falso
    se (!consumir_parser("para")) { retornar falso }
    se (!consumir_parser("(")) { retornar falso }
    se (atual_parser() == ";") {
        criar_no_ast_gp("VAZIO", "inicializacao", filhos_vazios)
        adicionar(filhos_para, ultimo_no_ast_gp)
        avancar_parser()
    } senao {
        se (atual_parser() == "numero" || atual_parser() == "texto" || atual_parser() == "logico" || atual_parser() == "lista") {
            se (!parse_declaracao_gp()) { retornar falso }
        } senao {
            logico declaracao_tipo_usuario = falso
            se (lexer.classificar_lexema_gp(atual_parser()) == "IDENTIFICADOR" && cursor_parser + 1 < tamanho(tokens_parser)) {
                declaracao_tipo_usuario = lexer.classificar_lexema_gp(tokens_parser[cursor_parser + 1]) == "IDENTIFICADOR"
            }
            se (declaracao_tipo_usuario) {
                se (!parse_declaracao_gp()) { retornar falso }
            } senao {
                se (!parse_atribuicao_gp()) { retornar falso }
            }
        }
        adicionar(filhos_para, ultimo_no_ast_gp)
    }
    se (atual_parser() == ";") {
        criar_no_ast_gp("VAZIO", "condicao", filhos_vazios)
        adicionar(filhos_para, ultimo_no_ast_gp)
        avancar_parser()
    } senao {
        se (!parse_expressao_gp()) { retornar falso }
        adicionar(filhos_para, ultimo_no_ast_gp)
        se (!consumir_parser(";")) { retornar falso }
    }
    se (atual_parser() == ")") {
        criar_no_ast_gp("VAZIO", "incremento", filhos_vazios)
        adicionar(filhos_para, ultimo_no_ast_gp)
    } senao {
        incremento_chamada_funcao = falso
        se (lexer.classificar_lexema_gp(atual_parser()) == "IDENTIFICADOR" && cursor_parser + 1 < tamanho(tokens_parser)) {
            incremento_chamada_funcao = tokens_parser[cursor_parser + 1] == "("
        }
        se (incremento_chamada_funcao) {
            se (!parse_expressao_gp()) { retornar falso }
        } senao {
            se (lexer.classificar_lexema_gp(atual_parser()) == "IDENTIFICADOR") {
                se (!parse_atribuicao_gp()) { retornar falso }
            } senao {
                se (!parse_expressao_gp()) { retornar falso }
            }
        }
        adicionar(filhos_para, ultimo_no_ast_gp)
    }
    se (!consumir_parser(")")) { retornar falso }
    profundidade_laco_parser = profundidade_laco_parser + 1
    se (!parse_bloco_gp()) {
        profundidade_laco_parser = profundidade_laco_parser - 1
        retornar falso
    }
    profundidade_laco_parser = profundidade_laco_parser - 1
    adicionar(filhos_para, ultimo_no_ast_gp)
    criar_no_ast_gp("PARA", "", filhos_para)
    aceitar_parser(";")
    retornar verdadeiro
}
funcao parse_estrutura_gp() -> logico {
    texto nome = ""
    texto tipo_campo = ""
    texto elemento_campo_estrutura = ""
    texto nome_campo = ""
    lista numero filhos_estrutura = []
    lista numero filhos_campo = []
    se (!consumir_parser("estrutura")) { retornar falso }
    se (lexer.classificar_lexema_gp(atual_parser()) != "IDENTIFICADOR") {
        erro_parser = verdadeiro
        mensagem_parser = "Nome de estrutura esperado"
        retornar falso
    }
    nome = atual_parser()
    avancar_parser()
    se (!consumir_parser("{")) { retornar falso }
    enquanto (atual_parser() != "}" && atual_parser() != "" && !erro_parser) {
        tipo_campo = atual_parser()
        se (tipo_campo == "lista") {
            avancar_parser()
            elemento_campo_estrutura = atual_parser()
            se (elemento_campo_estrutura != "numero" && elemento_campo_estrutura != "texto" && elemento_campo_estrutura != "logico" && lexer.classificar_lexema_gp(elemento_campo_estrutura) != "IDENTIFICADOR") {
                erro_parser = verdadeiro
                mensagem_parser = "Tipo de elemento da lista de campo esperado"
                retornar falso
            }
            avancar_parser()
            tipo_campo = "lista<" + elemento_campo_estrutura + ">"
        } senao {
            se (tipo_campo != "numero" && tipo_campo != "texto" && tipo_campo != "logico" && lexer.classificar_lexema_gp(tipo_campo) != "IDENTIFICADOR") {
                erro_parser = verdadeiro
                mensagem_parser = "Tipo de campo esperado"
                retornar falso
            }
            avancar_parser()
        }
        se (lexer.classificar_lexema_gp(atual_parser()) != "IDENTIFICADOR") {
            erro_parser = verdadeiro
            mensagem_parser = "Nome de campo esperado"
            retornar falso
        }
        nome_campo = atual_parser()
        avancar_parser()
        filhos_campo = []
        criar_no_ast_gp("CAMPO_DECLARADO", tipo_campo + "|" + nome_campo, filhos_campo)
        adicionar(filhos_estrutura, ultimo_no_ast_gp)
        se (!consumir_parser(";")) { retornar falso }
    }
    se (!consumir_parser("}")) { retornar falso }
    criar_no_ast_gp("ESTRUTURA", nome, filhos_estrutura)
    retornar verdadeiro
}
funcao parse_controle_laco_gp() -> logico {
    texto palavra = atual_parser()
    lista numero filhos_controle = []
    se (palavra != "quebrar" && palavra != "continuar") { retornar falso }
    se (profundidade_laco_parser == 0) {
        erro_parser = verdadeiro
        mensagem_parser = palavra + " fora de laco"
        retornar falso
    }
    avancar_parser()
    se (palavra == "quebrar") {
        criar_no_ast_gp("QUEBRAR", "", filhos_controle)
    } senao {
        criar_no_ast_gp("CONTINUAR", "", filhos_controle)
    }
    aceitar_parser(";")
    retornar verdadeiro
}
funcao parse_comando_gp() -> logico {
    // Comando vazio (incluindo o ponto e virgula apos um bloco).
    se (atual_parser() == ";") {
        avancar_parser()
        lista numero filhos_vazios_comando = []
        criar_no_ast_gp("VAZIO", "", filhos_vazios_comando)
        retornar verdadeiro
    }
    se (atual_parser() == "numero" || atual_parser() == "texto" || atual_parser() == "logico" || atual_parser() == "lista") {
        retornar parse_declaracao_gp()
    }
    se (lexer.classificar_lexema_gp(atual_parser()) == "IDENTIFICADOR" && cursor_parser + 1 < tamanho(tokens_parser)) {
        se (lexer.classificar_lexema_gp(tokens_parser[cursor_parser + 1]) == "IDENTIFICADOR") {
            retornar parse_declaracao_gp()
        }
    }
    se (atual_parser() == "mostrar") {
        retornar parse_mostrar_gp()
    }
    se (atual_parser() == "se") {
        retornar parse_se_gp()
    }
    se (atual_parser() == "enquanto") {
        retornar parse_enquanto_gp()
    }
    se (atual_parser() == "para") {
        retornar parse_para_gp()
    }
    se (atual_parser() == "funcao") {
        retornar parse_funcao_gp()
    }
    se (atual_parser() == "estrutura") {
        retornar parse_estrutura_gp()
    }
    se (atual_parser() == "quebrar" || atual_parser() == "continuar") {
        retornar parse_controle_laco_gp()
    }
    // Uma chamada de funcao isolada e um comando: sua expressao e
    // descartada pelo gerador IR depois de executar os efeitos colaterais.
    se (lexer.classificar_lexema_gp(atual_parser()) == "IDENTIFICADOR" && cursor_parser + 1 < tamanho(tokens_parser)) {
        se (tokens_parser[cursor_parser + 1] == "(") {
            lista numero filhos_chamada_comando = []
            se (!parse_primaria_gp()) { retornar falso }
            adicionar(filhos_chamada_comando, ultimo_no_ast_gp)
            criar_no_ast_gp("CHAMADA_COMANDO", "", filhos_chamada_comando)
            aceitar_parser(";")
            retornar verdadeiro
        }
    }
    se (atual_parser() == "retornar") {
        retornar parse_retorno_gp()
    }
    se (atual_parser() == "{") {
        retornar parse_bloco_gp()
    }
    se (lexer.classificar_lexema_gp(atual_parser()) == "IDENTIFICADOR" && cursor_parser + 1 < tamanho(tokens_parser)) {
        se (tokens_parser[cursor_parser + 1] == "(") {
            lista numero filhos_chamada_comando = []
            se (!parse_expressao_gp()) { retornar falso }
            adicionar(filhos_chamada_comando, ultimo_no_ast_gp)
            criar_no_ast_gp("CHAMADA_COMANDO", "", filhos_chamada_comando)
            aceitar_parser(";")
            retornar verdadeiro
        }
        retornar parse_atribuicao_gp()
    }
    erro_parser = verdadeiro
    mensagem_parser = "Comando inesperado: '" + atual_parser() + "'"
    retornar falso
}
// Registros tipados do IR auto-hospedado. Os slots texto1..3 carregam
// nomes/tipos; numero1 carrega contagens/destinos/constantes numericas;
// logico1 carrega constantes logicas. O adaptador textual temporario fica
// restrito a entrada do gerador e sera removido na proxima etapa.
estrutura InstrucaoIR_GP {
    texto opcode;
    texto texto1;
    texto texto2;
    texto texto3;
    numero numero1;
    logico logico1;
}
lista InstrucaoIR_GP instrucoes_ir_gp = []
lista InstrucaoIR_GP secoes_funcoes_ir_gp = []
lista InstrucaoIR_GP secoes_estruturas_ir_gp = []
logico erro_ir_gp = falso
texto diagnostico_ir_gp = ""
numero contador_rotulo_ir_gp = 0
lista texto nomes_rotulos_ir_gp = []
lista numero enderecos_rotulos_ir_gp = []
// Pilhas paralelas de destinos para quebrar/continuar; o nivel ativo
// identifica o laco mais interno, inclusive em lacos aninhados.
lista texto rotulos_fim_laco_ir_gp = []
lista texto rotulos_continuar_laco_ir_gp = []
numero profundidade_lacos_ir_gp = 0

lista texto nomes_estruturas_semanticas_gp = []
lista texto chaves_campos_estruturas_semanticas_gp = []
lista texto tipos_campos_estruturas_semanticas_gp = []

funcao obter_rotulo_fim_laco_ir_gp(numero nivel) -> texto {
    retornar rotulos_fim_laco_ir_gp[nivel]
}
funcao obter_rotulo_continuar_laco_ir_gp(numero nivel) -> texto {
    retornar rotulos_continuar_laco_ir_gp[nivel]
}
funcao criar_registro_ir_gp(texto opcode, texto texto1, texto texto2, texto texto3, numero numero1, logico logico1) -> InstrucaoIR_GP {
    retornar InstrucaoIR_GP{opcode: opcode, texto1: texto1, texto2: texto2, texto3: texto3, numero1: numero1, logico1: logico1}
}
funcao obter_registro_lista_ir_gp(lista InstrucaoIR_GP registros, numero indice) -> InstrucaoIR_GP {
    retornar registros[indice]
}
funcao emitir_registro_ir_gp(texto opcode, texto texto1, texto texto2, texto texto3, numero numero1, logico logico1) -> logico {
    adicionar(instrucoes_ir_gp, criar_registro_ir_gp(opcode, texto1, texto2, texto3, numero1, logico1))
    retornar verdadeiro
}
funcao operador_ir_gp(texto operador) -> texto {
    se (operador == "+") { retornar "ADD" }
    se (operador == "-") { retornar "SUB" }
    se (operador == "*") { retornar "MUL" }
    se (operador == "/") { retornar "DIV" }
    se (operador == "%") { retornar "MOD" }
    se (operador == "==") { retornar "EQ" }
    se (operador == "!=") { retornar "NE" }
    se (operador == ">") { retornar "GT" }
    se (operador == "<") { retornar "LT" }
    se (operador == ">=") { retornar "GE" }
    se (operador == "<=") { retornar "LE" }
    se (operador == "&&") { retornar "AND" }
    se (operador == "||") { retornar "OR" }
    retornar ""
}
funcao gerar_expressao_ir_gp(numero indice_ir) -> logico {
    NoAST_GP no_ir = obter_no_ast_gp(indice_ir)
    texto tipo_literal_ir = ""
    texto valor_literal_ir = ""
    numero separador_literal_ir = 0
    numero cursor_literal_ir = 0
    texto opcode_ir = ""
    se (no_ir.categoria == "LITERAL") {
        enquanto (separador_literal_ir < tamanho(no_ir.valor)) {
            se (no_ir.valor[separador_literal_ir] == "|") { quebrar }
            tipo_literal_ir = tipo_literal_ir + no_ir.valor[separador_literal_ir]
            separador_literal_ir = separador_literal_ir + 1
        }
        cursor_literal_ir = separador_literal_ir + 1
        enquanto (cursor_literal_ir < tamanho(no_ir.valor)) {
            valor_literal_ir = valor_literal_ir + no_ir.valor[cursor_literal_ir]
            cursor_literal_ir = cursor_literal_ir + 1
        }
        se (tipo_literal_ir == "NUMERO") {
            retornar emitir_registro_ir_gp("CONST", tipo_literal_ir, "", valor_literal_ir, numero_decimal_ir_gp(valor_literal_ir), falso)
        }
        se (tipo_literal_ir == "TEXTO") {
            retornar emitir_registro_ir_gp("CONST", tipo_literal_ir, valor_literal_ir, "", 0, falso)
        }
        se (tipo_literal_ir == "LOGICO" || tipo_literal_ir == "PALAVRA_CHAVE") {
            retornar emitir_registro_ir_gp("CONST", tipo_literal_ir, valor_literal_ir, "", 0, valor_literal_ir == "verdadeiro")
        }
        se (tipo_literal_ir == "NULO") {
            retornar emitir_registro_ir_gp("CONST", tipo_literal_ir, "", "", 0, falso)
        }
        erro_ir_gp = verdadeiro
        diagnostico_ir_gp = "Tipo de literal nao suportado no IR: " + tipo_literal_ir
        retornar falso
    }
    se (no_ir.categoria == "IDENTIFICADOR") {
        emitir_registro_ir_gp("LOAD", no_ir.valor, "", "", 0, falso)
        retornar verdadeiro
    }
    se (no_ir.categoria == "ARRAY") {
        numero item_array_ir = 0
        enquanto (item_array_ir < quantidade_filhos_ast_gp(indice_ir)) {
            se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_ir, item_array_ir))) { retornar falso }
            item_array_ir = item_array_ir + 1
        }
        emitir_registro_ir_gp("BUILD_ARRAY", "", "", "", item_array_ir, falso)
        retornar verdadeiro
    }
    se (no_ir.categoria == "INDICE") {
        se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_ir, 0))) { retornar falso }
        se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_ir, 1))) { retornar falso }
        emitir_registro_ir_gp("GET_INDEX", "", "", "", 0, falso)
        retornar verdadeiro
    }
    se (no_ir.categoria == "CAMPO") {
        se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_ir, 0))) { retornar falso }
        emitir_registro_ir_gp("GET_FIELD", no_ir.valor, "", "", 0, falso)
        retornar verdadeiro
    }
    se (no_ir.categoria == "CHAMADA_NOMEADA") {
        numero campo_schema_nomeado_ir = 0
        numero argumento_schema_nomeado_ir = 0
        numero quantidade_campos_nomeados_ir = 0
        numero campo_argumento_nomeado_ir = 0
        numero argumento_encontrado_nomeado_ir = 0
        texto chave_schema_nomeado_ir = ""
        texto nome_campo_schema_nomeado_ir = ""
        NoAST_GP argumento_ast_nomeado_ir = NoAST_GP{categoria: "", valor: "", filhos: [], linha: 0, coluna: 0}
        logico encontrado_argumento_nomeado_ir = falso
        enquanto (campo_schema_nomeado_ir < tamanho(chaves_campos_estruturas_semanticas_gp)) {
            chave_schema_nomeado_ir = chaves_campos_estruturas_semanticas_gp[campo_schema_nomeado_ir]
            se (nome_estrutura_da_chave_campo_semantica_gp(chave_schema_nomeado_ir) == no_ir.valor) {
                nome_campo_schema_nomeado_ir = nome_campo_da_chave_ir_gp(chave_schema_nomeado_ir)
                argumento_schema_nomeado_ir = 0
                encontrado_argumento_nomeado_ir = falso
                enquanto (argumento_schema_nomeado_ir < quantidade_filhos_ast_gp(indice_ir)) {
                    argumento_ast_nomeado_ir = obter_no_ast_gp(obter_filho_ast_gp(indice_ir, argumento_schema_nomeado_ir))
                    se (argumento_ast_nomeado_ir.valor == nome_campo_schema_nomeado_ir) {
                        se (!gerar_expressao_ir_gp(obter_filho_ast_gp(obter_filho_ast_gp(indice_ir, argumento_schema_nomeado_ir), 0))) { retornar falso }
                        encontrado_argumento_nomeado_ir = verdadeiro
                        quebrar
                    }
                    argumento_schema_nomeado_ir = argumento_schema_nomeado_ir + 1
                }
                se (!encontrado_argumento_nomeado_ir) {
                    erro_ir_gp = verdadeiro
                    diagnostico_ir_gp = "Campo ausente no construtor nomeado: " + nome_campo_schema_nomeado_ir
                    retornar falso
                }
                quantidade_campos_nomeados_ir = quantidade_campos_nomeados_ir + 1
            }
            campo_schema_nomeado_ir = campo_schema_nomeado_ir + 1
        }
        emitir_registro_ir_gp("BUILD_STRUCT", no_ir.valor, "", "", quantidade_campos_nomeados_ir, falso)
        retornar verdadeiro
    }
    se (no_ir.categoria == "CHAMADA") {
        numero argumento_chamada_ir = 0
        se (estrutura_existe_semantica_gp(no_ir.valor)) {
            enquanto (argumento_chamada_ir < quantidade_filhos_ast_gp(indice_ir)) {
                se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_ir, argumento_chamada_ir))) { retornar falso }
                argumento_chamada_ir = argumento_chamada_ir + 1
            }
            emitir_registro_ir_gp("BUILD_STRUCT", no_ir.valor, "", "", argumento_chamada_ir, falso)
            retornar verdadeiro
        }
        enquanto (argumento_chamada_ir < quantidade_filhos_ast_gp(indice_ir)) {
            se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_ir, argumento_chamada_ir))) { retornar falso }
            argumento_chamada_ir = argumento_chamada_ir + 1
        }
        emitir_registro_ir_gp("CALL", no_ir.valor, "", "", argumento_chamada_ir, falso)
        retornar verdadeiro
    }
    se (no_ir.categoria == "AGRUPAMENTO") {
        retornar gerar_expressao_ir_gp(obter_filho_ast_gp(indice_ir, 0))
    }
    se (no_ir.categoria == "UNARIO") {
        se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_ir, 0))) { retornar falso }
        se (no_ir.valor == "!") { emitir_registro_ir_gp("NOT", "", "", "", 0, falso) }
        senao { emitir_registro_ir_gp("NEG", "", "", "", 0, falso) }
        retornar verdadeiro
    }
    se (no_ir.categoria == "BINARIO") {
        opcode_ir = operador_ir_gp(no_ir.valor)
        se (opcode_ir == "") {
            erro_ir_gp = verdadeiro
            diagnostico_ir_gp = "Operador nao suportado no IR: " + no_ir.valor
            retornar falso
        }
        se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_ir, 0))) { retornar falso }
        se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_ir, 1))) { retornar falso }
        emitir_registro_ir_gp(opcode_ir, "", "", "", 0, falso)
        retornar verdadeiro
    }
    erro_ir_gp = verdadeiro
    diagnostico_ir_gp = "Expressao ainda nao suportada no IR: " + no_ir.categoria
    retornar falso
}
funcao novo_rotulo_ir_gp(texto prefixo_rotulo) -> texto {
    contador_rotulo_ir_gp = contador_rotulo_ir_gp + 1
    retornar prefixo_rotulo + texto_de_numero_gp(contador_rotulo_ir_gp)
}
funcao emitir_rotulo_ir_gp(texto nome_rotulo) -> logico {
    retornar emitir_registro_ir_gp("LABEL", nome_rotulo, "", "", 0, falso)
}
funcao gerar_atualizacao_ir_gp(numero indice_atualizacao) -> logico {
    NoAST_GP no_atualizacao = obter_no_ast_gp(indice_atualizacao)
    se (no_atualizacao.categoria == "VAZIO") { retornar verdadeiro }
    se (no_atualizacao.categoria == "ATRIBUICAO" || no_atualizacao.categoria == "DECLARACAO") {
        retornar gerar_comando_ir_gp(indice_atualizacao)
    }
    se (!gerar_expressao_ir_gp(indice_atualizacao)) { retornar falso }
    emitir_registro_ir_gp("POP", "", "", "", 0, falso)
    retornar verdadeiro
}
funcao gerar_comando_ir_gp(numero indice_comando_ir) -> logico {
    NoAST_GP no_comando_ir = obter_no_ast_gp(indice_comando_ir)
    texto tipo_declaracao_ir = ""
    texto nome_declaracao_ir = ""
    numero separador_declaracao_ir = 0
    numero cursor_declaracao_ir = 0
    numero filho_ir = 0
    se (no_comando_ir.categoria == "ESTRUTURA" || no_comando_ir.categoria == "VAZIO") { retornar verdadeiro }
    se (no_comando_ir.categoria == "BLOCO") {
        enquanto (filho_ir < quantidade_filhos_ast_gp(indice_comando_ir)) {
            se (!gerar_comando_ir_gp(obter_filho_ast_gp(indice_comando_ir, filho_ir))) { retornar falso }
            filho_ir = filho_ir + 1
        }
        retornar verdadeiro
    }
    se (no_comando_ir.categoria == "SE") {
        numero condicao_se_ir = obter_filho_ast_gp(indice_comando_ir, 0)
        numero bloco_entao_ir = obter_filho_ast_gp(indice_comando_ir, 1)
        texto rotulo_senao_ir = novo_rotulo_ir_gp("SENAO")
        se (!gerar_expressao_ir_gp(condicao_se_ir)) { retornar falso }
        emitir_registro_ir_gp("JUMP_IF_FALSE", rotulo_senao_ir, "", "", 0, falso)
        se (!gerar_comando_ir_gp(bloco_entao_ir)) { retornar falso }
        se (quantidade_filhos_ast_gp(indice_comando_ir) == 3) {
            texto rotulo_fim_se_ir = novo_rotulo_ir_gp("FIM_SE")
            emitir_registro_ir_gp("JUMP", rotulo_fim_se_ir, "", "", 0, falso)
            emitir_rotulo_ir_gp(rotulo_senao_ir)
            se (!gerar_comando_ir_gp(obter_filho_ast_gp(indice_comando_ir, 2))) { retornar falso }
            emitir_rotulo_ir_gp(rotulo_fim_se_ir)
        } senao {
            emitir_rotulo_ir_gp(rotulo_senao_ir)
        }
        retornar verdadeiro
    }
    se (no_comando_ir.categoria == "ENQUANTO") {
        texto rotulo_inicio_enquanto_ir = novo_rotulo_ir_gp("ENQUANTO")
        texto rotulo_fim_enquanto_ir = novo_rotulo_ir_gp("FIM_ENQUANTO")
        emitir_rotulo_ir_gp(rotulo_inicio_enquanto_ir)
        se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_comando_ir, 0))) { retornar falso }
        emitir_registro_ir_gp("JUMP_IF_FALSE", rotulo_fim_enquanto_ir, "", "", 0, falso)
        se (profundidade_lacos_ir_gp >= 128) {
            erro_ir_gp = verdadeiro
            diagnostico_ir_gp = "Limite de 128 lacos aninhados excedido"
            retornar falso
        }
        rotulos_fim_laco_ir_gp[profundidade_lacos_ir_gp] = rotulo_fim_enquanto_ir
        rotulos_continuar_laco_ir_gp[profundidade_lacos_ir_gp] = rotulo_inicio_enquanto_ir
        profundidade_lacos_ir_gp = profundidade_lacos_ir_gp + 1
        se (!gerar_comando_ir_gp(obter_filho_ast_gp(indice_comando_ir, 1))) {
            profundidade_lacos_ir_gp = profundidade_lacos_ir_gp - 1
            retornar falso
        }
        profundidade_lacos_ir_gp = profundidade_lacos_ir_gp - 1
        emitir_registro_ir_gp("JUMP", rotulo_inicio_enquanto_ir, "", "", 0, falso)
        emitir_rotulo_ir_gp(rotulo_fim_enquanto_ir)
        retornar verdadeiro
    }
    se (no_comando_ir.categoria == "PARA") {
        numero inicio_para_no_ir = obter_filho_ast_gp(indice_comando_ir, 0)
        numero condicao_para_no_ir = obter_filho_ast_gp(indice_comando_ir, 1)
        numero atualizacao_para_no_ir = obter_filho_ast_gp(indice_comando_ir, 2)
        numero corpo_para_no_ir = obter_filho_ast_gp(indice_comando_ir, 3)
        NoAST_GP no_condicao_para_ir = obter_no_ast_gp(condicao_para_no_ir)
        texto rotulo_inicio_para_ir = novo_rotulo_ir_gp("PARA")
        texto rotulo_fim_para_ir = novo_rotulo_ir_gp("FIM_PARA")
        texto rotulo_atualizacao_para_ir = novo_rotulo_ir_gp("ATUALIZACAO")
        se (!gerar_atualizacao_ir_gp(inicio_para_no_ir)) { retornar falso }
        emitir_rotulo_ir_gp(rotulo_inicio_para_ir)
        se (no_condicao_para_ir.categoria != "VAZIO") {
            se (!gerar_expressao_ir_gp(condicao_para_no_ir)) { retornar falso }
            emitir_registro_ir_gp("JUMP_IF_FALSE", rotulo_fim_para_ir, "", "", 0, falso)
        }
        se (profundidade_lacos_ir_gp >= 128) {
            erro_ir_gp = verdadeiro
            diagnostico_ir_gp = "Limite de 128 lacos aninhados excedido"
            retornar falso
        }
        rotulos_fim_laco_ir_gp[profundidade_lacos_ir_gp] = rotulo_fim_para_ir
        rotulos_continuar_laco_ir_gp[profundidade_lacos_ir_gp] = rotulo_atualizacao_para_ir
        profundidade_lacos_ir_gp = profundidade_lacos_ir_gp + 1
        se (!gerar_comando_ir_gp(corpo_para_no_ir)) {
            profundidade_lacos_ir_gp = profundidade_lacos_ir_gp - 1
            retornar falso
        }
        profundidade_lacos_ir_gp = profundidade_lacos_ir_gp - 1
        emitir_rotulo_ir_gp(rotulo_atualizacao_para_ir)
        se (!gerar_atualizacao_ir_gp(atualizacao_para_no_ir)) { retornar falso }
        emitir_registro_ir_gp("JUMP", rotulo_inicio_para_ir, "", "", 0, falso)
        emitir_rotulo_ir_gp(rotulo_fim_para_ir)
        retornar verdadeiro
    }
    se (no_comando_ir.categoria == "CHAMADA_COMANDO") {
        se (quantidade_filhos_ast_gp(indice_comando_ir) != 1) {
            erro_ir_gp = verdadeiro
            diagnostico_ir_gp = "Comando de chamada invalido"
            retornar falso
        }
        se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_comando_ir, 0))) { retornar falso }
        emitir_registro_ir_gp("POP", "", "", "", 0, falso)
        retornar verdadeiro
    }
    se (no_comando_ir.categoria == "DECLARACAO") {
        enquanto (separador_declaracao_ir < tamanho(no_comando_ir.valor)) {
            se (no_comando_ir.valor[separador_declaracao_ir] == "|") { quebrar }
            tipo_declaracao_ir = tipo_declaracao_ir + no_comando_ir.valor[separador_declaracao_ir]
            separador_declaracao_ir = separador_declaracao_ir + 1
        }
        cursor_declaracao_ir = separador_declaracao_ir + 1
        enquanto (cursor_declaracao_ir < tamanho(no_comando_ir.valor)) {
            nome_declaracao_ir = nome_declaracao_ir + no_comando_ir.valor[cursor_declaracao_ir]
            cursor_declaracao_ir = cursor_declaracao_ir + 1
        }
        se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_comando_ir, 0))) { retornar falso }
        se (comeca_com_ir_gp(tipo_declaracao_ir, "lista<")) {
            texto elemento_lista_ir = ""
            numero cursor_elemento_lista_ir = 6
            enquanto (cursor_elemento_lista_ir < tamanho(tipo_declaracao_ir) - 1) {
                elemento_lista_ir = elemento_lista_ir + tipo_declaracao_ir[cursor_elemento_lista_ir]
                cursor_elemento_lista_ir = cursor_elemento_lista_ir + 1
            }
            se (elemento_lista_ir == "") {
                erro_ir_gp = verdadeiro
                diagnostico_ir_gp = "Tipo de elemento ausente na declaracao de lista"
                retornar falso
            }
            emitir_registro_ir_gp("MAKE_TYPED_ARRAY", elemento_lista_ir, "", "", 0, falso)
            emitir_registro_ir_gp("DECLARE", nome_declaracao_ir, "lista", elemento_lista_ir, 0, falso)
        } senao {
            emitir_registro_ir_gp("DECLARE", nome_declaracao_ir, tipo_declaracao_ir, "", 0, falso)
        }
        retornar verdadeiro
    }
    se (no_comando_ir.categoria == "ATRIBUICAO") {
        numero destino_ir = obter_filho_ast_gp(indice_comando_ir, 0)
        NoAST_GP no_destino_ir = obter_no_ast_gp(destino_ir)
        se (no_destino_ir.categoria == "IDENTIFICADOR") {
            se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_comando_ir, 1))) { retornar falso }
            emitir_registro_ir_gp("STORE", no_destino_ir.valor, "", "", 0, falso)
            retornar verdadeiro
        }
        se (no_destino_ir.categoria == "INDICE") {
            se (!gerar_expressao_ir_gp(obter_filho_ast_gp(destino_ir, 0))) { retornar falso }
            se (!gerar_expressao_ir_gp(obter_filho_ast_gp(destino_ir, 1))) { retornar falso }
            se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_comando_ir, 1))) { retornar falso }
            emitir_registro_ir_gp("SET_INDEX", "", "", "", 0, falso)
            retornar verdadeiro
        }
        se (no_destino_ir.categoria == "CAMPO") {
            se (!gerar_expressao_ir_gp(obter_filho_ast_gp(destino_ir, 0))) { retornar falso }
            se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_comando_ir, 1))) { retornar falso }
            emitir_registro_ir_gp("SET_FIELD", no_destino_ir.valor, "", "", 0, falso)
            retornar verdadeiro
        }
        erro_ir_gp = verdadeiro
        diagnostico_ir_gp = "Destino de atribuicao ainda nao suportado no IR"
        retornar falso
    }
    se (no_comando_ir.categoria == "QUEBRAR" || no_comando_ir.categoria == "CONTINUAR") {
        se (profundidade_lacos_ir_gp <= 0) {
            erro_ir_gp = verdadeiro
            diagnostico_ir_gp = no_comando_ir.categoria + " fora de laco no gerador IR"
            retornar falso
        }
        se (no_comando_ir.categoria == "QUEBRAR") {
            emitir_registro_ir_gp("JUMP", obter_rotulo_fim_laco_ir_gp(profundidade_lacos_ir_gp - 1), "", "", 0, falso)
        } senao {
            texto destino_continuar_ir = obter_rotulo_continuar_laco_ir_gp(profundidade_lacos_ir_gp - 1)
            emitir_registro_ir_gp("JUMP", destino_continuar_ir, "", "", 0, falso)
        }
        retornar verdadeiro
    }
    se (no_comando_ir.categoria == "RETORNAR") {
        se (quantidade_filhos_ast_gp(indice_comando_ir) > 0) {
            se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_comando_ir, 0))) { retornar falso }
        } senao {
            emitir_registro_ir_gp("CONST", "NULO", "", "", 0, falso)
        }
        emitir_registro_ir_gp("RETURN", "", "", "", 0, falso)
        retornar verdadeiro
    }
    se (no_comando_ir.categoria == "MOSTRAR") {
        enquanto (filho_ir < quantidade_filhos_ast_gp(indice_comando_ir)) {
            se (!gerar_expressao_ir_gp(obter_filho_ast_gp(indice_comando_ir, filho_ir))) { retornar falso }
            filho_ir = filho_ir + 1
        }
        emitir_registro_ir_gp("PRINT", "", "", "", filho_ir, falso)
        retornar verdadeiro
    }
    erro_ir_gp = verdadeiro
    diagnostico_ir_gp = "Comando ainda nao suportado no IR: " + no_comando_ir.categoria
    retornar falso
}
funcao gerar_funcao_ir_gp(numero indice_funcao_ir) -> logico {
    NoAST_GP no_funcao_ir = obter_no_ast_gp(indice_funcao_ir)
    texto nome_funcao_ir = ""
    texto retorno_funcao_ir = ""
    numero separador_nome_funcao_ir = 0
    numero cursor_nome_funcao_ir = 0
    numero cursor_retorno_funcao_ir = 0
    numero parametro_funcao_ir = 0
    lista InstrucaoIR_GP codigo_principal_salvo_ir = instrucoes_ir_gp
    numero contador_rotulo_salvo_ir = contador_rotulo_ir_gp
    lista InstrucaoIR_GP codigo_funcao_salvo_ir = []
    se (no_funcao_ir.categoria != "FUNCAO") {
        erro_ir_gp = verdadeiro
        diagnostico_ir_gp = "No nao e FUNCAO no gerador de funcoes"
        retornar falso
    }
    enquanto (separador_nome_funcao_ir < tamanho(no_funcao_ir.valor)) {
        se (no_funcao_ir.valor[separador_nome_funcao_ir] == " ") { quebrar }
        nome_funcao_ir = nome_funcao_ir + no_funcao_ir.valor[separador_nome_funcao_ir]
        separador_nome_funcao_ir = separador_nome_funcao_ir + 1
    }
    cursor_retorno_funcao_ir = separador_nome_funcao_ir + 4
    enquanto (cursor_retorno_funcao_ir < tamanho(no_funcao_ir.valor)) {
        retorno_funcao_ir = retorno_funcao_ir + no_funcao_ir.valor[cursor_retorno_funcao_ir]
        cursor_retorno_funcao_ir = cursor_retorno_funcao_ir + 1
    }
    se (nome_funcao_ir == "" || retorno_funcao_ir == "") {
        erro_ir_gp = verdadeiro
        diagnostico_ir_gp = "Assinatura de funcao invalida no IR"
        retornar falso
    }
    instrucoes_ir_gp = []
    contador_rotulo_ir_gp = 0
    numero profundidade_lacos_salva_ir = profundidade_lacos_ir_gp
    profundidade_lacos_ir_gp = 0
    // Cada funcao resolve seus rotulos isoladamente, sem herdar a pilha do main.
    se (!gerar_comando_ir_gp(obter_filho_ast_gp(indice_funcao_ir, quantidade_filhos_ast_gp(indice_funcao_ir) - 1))) {
        instrucoes_ir_gp = codigo_principal_salvo_ir
        contador_rotulo_ir_gp = contador_rotulo_salvo_ir
        profundidade_lacos_ir_gp = profundidade_lacos_salva_ir
        retornar falso
    }
    profundidade_lacos_ir_gp = profundidade_lacos_salva_ir
    emitir_registro_ir_gp("CONST", "NULO", "", "", 0, falso)
    emitir_registro_ir_gp("RETURN", "", "", "", 0, falso)
    // Sem rótulos, nenhuma passagem de patch é necessária.
    se (contador_rotulo_ir_gp > 0 && !resolver_rotulos_ir_gp()) {
        texto erro_funcao_local_ir = diagnostico_ir_gp
        instrucoes_ir_gp = codigo_principal_salvo_ir
        contador_rotulo_ir_gp = contador_rotulo_salvo_ir
        profundidade_lacos_ir_gp = profundidade_lacos_salva_ir
        erro_ir_gp = verdadeiro
        diagnostico_ir_gp = "Funcao " + nome_funcao_ir + ": " + erro_funcao_local_ir
        retornar falso
    }
    codigo_funcao_salvo_ir = instrucoes_ir_gp
    instrucoes_ir_gp = codigo_principal_salvo_ir
    contador_rotulo_ir_gp = contador_rotulo_salvo_ir
    adicionar(secoes_funcoes_ir_gp, criar_registro_ir_gp("FUNCTION", nome_funcao_ir, retorno_funcao_ir, "", quantidade_filhos_ast_gp(indice_funcao_ir) - 1, falso))
    NoAST_GP no_parametro_funcao_ir = obter_no_ast_gp(0)
    enquanto (parametro_funcao_ir < quantidade_filhos_ast_gp(indice_funcao_ir) - 1) {
        no_parametro_funcao_ir = obter_no_ast_gp(obter_filho_ast_gp(indice_funcao_ir, parametro_funcao_ir))
        adicionar(secoes_funcoes_ir_gp, criar_registro_ir_gp("PARAM", campo_registro_ir_gp(no_parametro_funcao_ir.valor, 0), campo_registro_ir_gp(no_parametro_funcao_ir.valor, 1), "", 0, falso))
        parametro_funcao_ir = parametro_funcao_ir + 1
    }
    adicionar(secoes_funcoes_ir_gp, criar_registro_ir_gp("CODE_BEGIN", nome_funcao_ir, "", "", 0, falso))
    numero instrucao_funcao_ir = 0
    enquanto (instrucao_funcao_ir < tamanho(codigo_funcao_salvo_ir)) {
        adicionar(secoes_funcoes_ir_gp, obter_registro_lista_ir_gp(codigo_funcao_salvo_ir, instrucao_funcao_ir))
        instrucao_funcao_ir = instrucao_funcao_ir + 1
    }
    adicionar(secoes_funcoes_ir_gp, criar_registro_ir_gp("CODE_END", nome_funcao_ir, "", "", 0, falso))
    retornar verdadeiro
}
funcao comeca_com_ir_gp(texto valor_prefixo_ir, texto prefixo_ir) -> logico {
    numero posicao_prefixo_ir = 0
    se (tamanho(valor_prefixo_ir) < tamanho(prefixo_ir)) { retornar falso }
    enquanto (posicao_prefixo_ir < tamanho(prefixo_ir)) {
        se (valor_prefixo_ir[posicao_prefixo_ir] != prefixo_ir[posicao_prefixo_ir]) { retornar falso }
        posicao_prefixo_ir = posicao_prefixo_ir + 1
    }
    retornar verdadeiro
}
funcao digito_numero_ir_gp(texto caractere_numero_ir) -> numero {
    se (caractere_numero_ir == "0") { retornar 0 }
    se (caractere_numero_ir == "1") { retornar 1 }
    se (caractere_numero_ir == "2") { retornar 2 }
    se (caractere_numero_ir == "3") { retornar 3 }
    se (caractere_numero_ir == "4") { retornar 4 }
    se (caractere_numero_ir == "5") { retornar 5 }
    se (caractere_numero_ir == "6") { retornar 6 }
    se (caractere_numero_ir == "7") { retornar 7 }
    se (caractere_numero_ir == "8") { retornar 8 }
    se (caractere_numero_ir == "9") { retornar 9 }
    retornar -1
}
funcao numero_decimal_ir_gp(texto lexema_numero_ir) -> numero {
    numero resultado_numero_ir = 0
    numero cursor_numero_ir = 0
    numero digito_atual_numero_ir = 0
    numero fator_decimal_numero_ir = 0.1
    logico parte_decimal_numero_ir = falso
    logico negativo_numero_ir = falso
    se (tamanho(lexema_numero_ir) == 0) { retornar -1 }
    se (lexema_numero_ir[0] == "-") {
        negativo_numero_ir = verdadeiro
        cursor_numero_ir = 1
    }
    enquanto (cursor_numero_ir < tamanho(lexema_numero_ir)) {
        se (lexema_numero_ir[cursor_numero_ir] == "." && !parte_decimal_numero_ir) {
            parte_decimal_numero_ir = verdadeiro
        } senao {
            digito_atual_numero_ir = digito_numero_ir_gp(lexema_numero_ir[cursor_numero_ir])
            se (digito_atual_numero_ir < 0) { retornar -1 }
            se (parte_decimal_numero_ir) {
                resultado_numero_ir = resultado_numero_ir + digito_atual_numero_ir * fator_decimal_numero_ir
                fator_decimal_numero_ir = fator_decimal_numero_ir / 10
            } senao {
                resultado_numero_ir = resultado_numero_ir * 10 + digito_atual_numero_ir
            }
        }
        cursor_numero_ir = cursor_numero_ir + 1
    }
    se (negativo_numero_ir) { retornar 0 - resultado_numero_ir }
    retornar resultado_numero_ir
}
funcao buscar_rotulo_ir_gp(texto nome_busca_rotulo_ir) -> numero {
    numero cursor_busca_rotulo_ir = 0
    enquanto (cursor_busca_rotulo_ir < tamanho(nomes_rotulos_ir_gp)) {
        se (nomes_rotulos_ir_gp[cursor_busca_rotulo_ir] == nome_busca_rotulo_ir) {
            retornar enderecos_rotulos_ir_gp[cursor_busca_rotulo_ir]
        }
        cursor_busca_rotulo_ir = cursor_busca_rotulo_ir + 1
    }
    retornar -1
}

funcao campo_registro_ir_gp(texto registro_campo_ir, numero indice_campo_ir) -> texto {
    texto resultado_campo_registro_ir = ""
    numero cursor_campo_registro_ir = 0
    numero campo_atual_registro_ir = 0
    enquanto (cursor_campo_registro_ir < tamanho(registro_campo_ir)) {
        se (registro_campo_ir[cursor_campo_registro_ir] == "|") {
            campo_atual_registro_ir = campo_atual_registro_ir + 1
        } senao {
            se (campo_atual_registro_ir == indice_campo_ir) {
                resultado_campo_registro_ir = resultado_campo_registro_ir + registro_campo_ir[cursor_campo_registro_ir]
            }
        }
        cursor_campo_registro_ir = cursor_campo_registro_ir + 1
    }
    retornar resultado_campo_registro_ir
}
funcao campo_numero_inteiro_ir_gp(numero valor_inteiro_ir) -> logico {
    retornar valor_inteiro_ir >= 0 && valor_inteiro_ir % 1 == 0
}
funcao validar_registro_ir_gp(InstrucaoIR_GP registro_validar_ir) -> logico {
    texto opcode_validar_ir = registro_validar_ir.opcode
    se (opcode_validar_ir == "GP-IR") {
        retornar registro_validar_ir.numero1 == 1
    }
    se (opcode_validar_ir == "CONST") {
        se (registro_validar_ir.texto1 == "NUMERO") {
            retornar lexer.classificar_lexema_gp(registro_validar_ir.texto3) == "NUMERO"
        }
        se (registro_validar_ir.texto1 == "TEXTO") {
            se (tamanho(registro_validar_ir.texto2) < 2) { retornar falso }
            retornar registro_validar_ir.texto2[0] == "\"" && registro_validar_ir.texto2[tamanho(registro_validar_ir.texto2) - 1] == "\""
        }
        se (registro_validar_ir.texto1 == "LOGICO" || registro_validar_ir.texto1 == "PALAVRA_CHAVE") {
            retornar (registro_validar_ir.texto2 == "verdadeiro" && registro_validar_ir.logico1) || (registro_validar_ir.texto2 == "falso" && !registro_validar_ir.logico1)
        }
        se (registro_validar_ir.texto1 == "NULO") { retornar registro_validar_ir.texto2 == "" }
        retornar falso
    }
    se (opcode_validar_ir == "STRUCT" || opcode_validar_ir == "BUILD_STRUCT") {
        retornar registro_validar_ir.texto1 != "" && campo_numero_inteiro_ir_gp(registro_validar_ir.numero1)
    }
    se (opcode_validar_ir == "STRUCT_FIELD" || opcode_validar_ir == "PARAM") {
        retornar registro_validar_ir.texto1 != "" && registro_validar_ir.texto2 != ""
    }
    se (opcode_validar_ir == "BUILD_ARRAY" || opcode_validar_ir == "PRINT" || opcode_validar_ir == "JUMP" || opcode_validar_ir == "JUMP_IF_FALSE") {
        retornar campo_numero_inteiro_ir_gp(registro_validar_ir.numero1)
    }
    se (opcode_validar_ir == "CALL") {
        retornar registro_validar_ir.texto1 != "" && campo_numero_inteiro_ir_gp(registro_validar_ir.numero1)
    }
    se (opcode_validar_ir == "FUNCTION") {
        retornar registro_validar_ir.texto1 != "" && registro_validar_ir.texto2 != "" && campo_numero_inteiro_ir_gp(registro_validar_ir.numero1)
    }
    se (opcode_validar_ir == "CODE_BEGIN" || opcode_validar_ir == "CODE_END" || opcode_validar_ir == "LOAD" || opcode_validar_ir == "STORE" || opcode_validar_ir == "GET_FIELD" || opcode_validar_ir == "SET_FIELD" || opcode_validar_ir == "MAKE_TYPED_ARRAY" || opcode_validar_ir == "LABEL") {
        retornar registro_validar_ir.texto1 != ""
    }
    se (opcode_validar_ir == "DECLARE") {
        retornar registro_validar_ir.texto1 != "" && registro_validar_ir.texto2 != ""
    }
    se (opcode_validar_ir == "POP" || opcode_validar_ir == "NEG" || opcode_validar_ir == "NOT" || opcode_validar_ir == "ADD" || opcode_validar_ir == "SUB" || opcode_validar_ir == "MUL" || opcode_validar_ir == "DIV" || opcode_validar_ir == "MOD" || opcode_validar_ir == "EQ" || opcode_validar_ir == "NE" || opcode_validar_ir == "GT" || opcode_validar_ir == "LT" || opcode_validar_ir == "GE" || opcode_validar_ir == "LE" || opcode_validar_ir == "AND" || opcode_validar_ir == "OR" || opcode_validar_ir == "GET_INDEX" || opcode_validar_ir == "SET_INDEX" || opcode_validar_ir == "RETURN") {
        retornar verdadeiro
    }
    retornar falso
}
funcao validar_registros_ir_gp() -> logico {
    numero indice_registro_validar_ir = 0
    InstrucaoIR_GP registro_validar_ir = criar_registro_ir_gp("", "", "", "", 0, falso)
    se (tamanho(instrucoes_ir_gp) == 0) {
        erro_ir_gp = verdadeiro
        diagnostico_ir_gp = "Cabecalho GP-IR ausente durante validacao"
        retornar falso
    }
    registro_validar_ir = obter_registro_lista_ir_gp(instrucoes_ir_gp, 0)
    se (registro_validar_ir.opcode != "GP-IR" || registro_validar_ir.numero1 != 1) {
        erro_ir_gp = verdadeiro
        diagnostico_ir_gp = "Cabecalho GP-IR ausente ou invalido durante validacao"
        retornar falso
    }
    enquanto (indice_registro_validar_ir < tamanho(instrucoes_ir_gp)) {
        registro_validar_ir = obter_registro_lista_ir_gp(instrucoes_ir_gp, indice_registro_validar_ir)
        se (indice_registro_validar_ir > 0 && registro_validar_ir.opcode == "GP-IR") {
            erro_ir_gp = verdadeiro
            diagnostico_ir_gp = "Cabecalho GP-IR duplicado"
            retornar falso
        }
        se (!validar_registro_ir_gp(registro_validar_ir)) {
            erro_ir_gp = verdadeiro
            diagnostico_ir_gp = "Registro IR invalido: " + registro_validar_ir.opcode
            retornar falso
        }
        indice_registro_validar_ir = indice_registro_validar_ir + 1
    }
    retornar verdadeiro
}

funcao resolver_rotulos_ir_gp() -> logico {
    numero cursor_primeira_passagem_ir = 0
    numero cursor_segunda_passagem_ir = 0
    numero endereco_instrucao_ir = 0
    InstrucaoIR_GP instrucao_rotulo_ir = criar_registro_ir_gp("", "", "", "", 0, falso)
    texto nome_rotulo_ir = ""
    numero endereco_rotulo_ir = -1
    lista InstrucaoIR_GP instrucoes_resolvidas_ir_gp = []
    nomes_rotulos_ir_gp = []
    enderecos_rotulos_ir_gp = []
    erro_ir_gp = falso
    diagnostico_ir_gp = ""
    // Primeira passagem: conta somente instruções executáveis e guarda LABEL.
    enquanto (cursor_primeira_passagem_ir < tamanho(instrucoes_ir_gp)) {
        instrucao_rotulo_ir = obter_registro_lista_ir_gp(instrucoes_ir_gp, cursor_primeira_passagem_ir)
        se (instrucao_rotulo_ir.opcode == "GP-IR" || instrucao_rotulo_ir.opcode == "STRUCT" || instrucao_rotulo_ir.opcode == "STRUCT_FIELD") {
            cursor_primeira_passagem_ir = cursor_primeira_passagem_ir + 1
        } senao {
            se (instrucao_rotulo_ir.opcode == "LABEL") {
                nome_rotulo_ir = instrucao_rotulo_ir.texto1
                se (nome_rotulo_ir == "") {
                    erro_ir_gp = verdadeiro
                    diagnostico_ir_gp = "Rotulo vazio no IR"
                    retornar falso
                }
                se (buscar_rotulo_ir_gp(nome_rotulo_ir) >= 0) {
                    erro_ir_gp = verdadeiro
                    diagnostico_ir_gp = "Rotulo duplicado no IR: " + nome_rotulo_ir
                    retornar falso
                }
                adicionar(nomes_rotulos_ir_gp, nome_rotulo_ir)
                adicionar(enderecos_rotulos_ir_gp, endereco_instrucao_ir)
                cursor_primeira_passagem_ir = cursor_primeira_passagem_ir + 1
            } senao {
                endereco_instrucao_ir = endereco_instrucao_ir + 1
                cursor_primeira_passagem_ir = cursor_primeira_passagem_ir + 1
            }
        }
    }
    // Segunda passagem: resolve destinos numéricos diretamente nos campos.
    enquanto (cursor_segunda_passagem_ir < tamanho(instrucoes_ir_gp)) {
        instrucao_rotulo_ir = obter_registro_lista_ir_gp(instrucoes_ir_gp, cursor_segunda_passagem_ir)
        se (instrucao_rotulo_ir.opcode == "GP-IR" || instrucao_rotulo_ir.opcode == "STRUCT" || instrucao_rotulo_ir.opcode == "STRUCT_FIELD") {
            adicionar(instrucoes_resolvidas_ir_gp, instrucao_rotulo_ir)
        } senao {
            se (instrucao_rotulo_ir.opcode == "LABEL") {
                // Labels são metadados e não ocupam endereço.
            } senao {
                se (instrucao_rotulo_ir.opcode == "JUMP" || instrucao_rotulo_ir.opcode == "JUMP_IF_FALSE") {
                    nome_rotulo_ir = instrucao_rotulo_ir.texto1
                    endereco_rotulo_ir = instrucao_rotulo_ir.numero1
                    se (nome_rotulo_ir != "") {
                        endereco_rotulo_ir = buscar_rotulo_ir_gp(nome_rotulo_ir)
                    }
                    se (endereco_rotulo_ir < 0) {
                        erro_ir_gp = verdadeiro
                        diagnostico_ir_gp = "Destino de salto inexistente: " + nome_rotulo_ir
                        retornar falso
                    }
                    adicionar(instrucoes_resolvidas_ir_gp, criar_registro_ir_gp(instrucao_rotulo_ir.opcode, "", "", "", endereco_rotulo_ir, falso))
                } senao {
                    adicionar(instrucoes_resolvidas_ir_gp, instrucao_rotulo_ir)
                }
            }
        }
        cursor_segunda_passagem_ir = cursor_segunda_passagem_ir + 1
    }
    instrucoes_ir_gp = instrucoes_resolvidas_ir_gp
    retornar verdadeiro
}
funcao nome_campo_da_chave_ir_gp(texto chave_campo_ir) -> texto {
    texto resultado_campo_ir = ""
    numero cursor_campo_ir = 0
    logico depois_separador_campo_ir = falso
    enquanto (cursor_campo_ir < tamanho(chave_campo_ir)) {
        se (chave_campo_ir[cursor_campo_ir] == "|") {
            depois_separador_campo_ir = verdadeiro
        } senao {
            se (depois_separador_campo_ir) {
                resultado_campo_ir = resultado_campo_ir + chave_campo_ir[cursor_campo_ir]
            }
        }
        cursor_campo_ir = cursor_campo_ir + 1
    }
    retornar resultado_campo_ir
}
funcao emitir_esquemas_estruturas_ir_gp() -> logico {
    numero indice_estrutura_emitir_ir = 0
    numero indice_campo_emitir_ir = 0
    numero quantidade_campos_emitir_ir = 0
    numero campo_emitir_ir = 0
    texto nome_estrutura_emitir_ir = ""
    texto chave_campo_emitir_ir = ""
    texto tipo_campo_emitir_ir = ""
    texto estrutura_campo_emitir_ir = ""
    texto nome_campo_emitir_ir = ""
    enquanto (indice_estrutura_emitir_ir < tamanho(nomes_estruturas_semanticas_gp)) {
        nome_estrutura_emitir_ir = nomes_estruturas_semanticas_gp[indice_estrutura_emitir_ir]
        quantidade_campos_emitir_ir = 0
        indice_campo_emitir_ir = 0
        enquanto (indice_campo_emitir_ir < tamanho(chaves_campos_estruturas_semanticas_gp)) {
            se (nome_estrutura_da_chave_campo_semantica_gp(chaves_campos_estruturas_semanticas_gp[indice_campo_emitir_ir]) == nome_estrutura_emitir_ir) {
                quantidade_campos_emitir_ir = quantidade_campos_emitir_ir + 1
            }
            indice_campo_emitir_ir = indice_campo_emitir_ir + 1
        }
        adicionar(secoes_estruturas_ir_gp, criar_registro_ir_gp("STRUCT", nome_estrutura_emitir_ir, "", "", quantidade_campos_emitir_ir, falso))
        campo_emitir_ir = 0
        enquanto (campo_emitir_ir < tamanho(chaves_campos_estruturas_semanticas_gp)) {
            chave_campo_emitir_ir = chaves_campos_estruturas_semanticas_gp[campo_emitir_ir]
            tipo_campo_emitir_ir = tipos_campos_estruturas_semanticas_gp[campo_emitir_ir]
            estrutura_campo_emitir_ir = nome_estrutura_da_chave_campo_semantica_gp(chave_campo_emitir_ir)
            se (estrutura_campo_emitir_ir == nome_estrutura_emitir_ir) {
                nome_campo_emitir_ir = nome_campo_da_chave_ir_gp(chave_campo_emitir_ir)
                adicionar(secoes_estruturas_ir_gp, criar_registro_ir_gp("STRUCT_FIELD", tipo_campo_emitir_ir, nome_campo_emitir_ir, "", 0, falso))
            }
            campo_emitir_ir = campo_emitir_ir + 1
        }
        indice_estrutura_emitir_ir = indice_estrutura_emitir_ir + 1
    }
    retornar verdadeiro
}
funcao gerar_ir_ast_gp(numero raiz_ir) -> logico {
    instrucoes_ir_gp = []
    secoes_funcoes_ir_gp = []
    secoes_estruturas_ir_gp = []
    erro_ir_gp = falso
    diagnostico_ir_gp = ""
    contador_rotulo_ir_gp = 0
    profundidade_lacos_ir_gp = 0
    rotulos_fim_laco_ir_gp = []
    rotulos_continuar_laco_ir_gp = []
    // Slots fixos evitam entradas obsoletas quando lacos sequenciais reutilizam profundidade.
    enquanto (tamanho(rotulos_fim_laco_ir_gp) < 128) {
        adicionar(rotulos_fim_laco_ir_gp, "")
        adicionar(rotulos_continuar_laco_ir_gp, "")
    }
    se (raiz_ir < 0 || raiz_ir >= tamanho(arvore_ast_gp)) {
        erro_ir_gp = verdadeiro
        diagnostico_ir_gp = "Raiz AST invalida para IR"
        retornar falso
    }
    se (obter_no_ast_gp(raiz_ir).categoria != "PROGRAMA") {
        erro_ir_gp = verdadeiro
        diagnostico_ir_gp = "No raiz precisa ser PROGRAMA"
        retornar falso
    }
    emitir_registro_ir_gp("GP-IR", "", "", "", 1, falso)
    se (!emitir_esquemas_estruturas_ir_gp()) { retornar falso }
    numero comando_raiz_ir = 0
    numero indice_comando_raiz_ir = -1
    NoAST_GP no_comando_raiz_ir = obter_no_ast_gp(0)
    enquanto (comando_raiz_ir < quantidade_filhos_ast_gp(raiz_ir)) {
        indice_comando_raiz_ir = obter_filho_ast_gp(raiz_ir, comando_raiz_ir)
        no_comando_raiz_ir = obter_no_ast_gp(indice_comando_raiz_ir)
        se (no_comando_raiz_ir.categoria == "FUNCAO") {
            se (!gerar_funcao_ir_gp(indice_comando_raiz_ir)) { retornar falso }
        } senao {
            se (!gerar_comando_ir_gp(indice_comando_raiz_ir)) { retornar falso }
        }
        comando_raiz_ir = comando_raiz_ir + 1
    }
    se (contador_rotulo_ir_gp > 0 && !resolver_rotulos_ir_gp()) { retornar falso }
    // Metadados de estrutura são anexados após resolver os saltos, para que
    // não contem como endereços de instruções do código principal.
    lista InstrucaoIR_GP instrucoes_com_esquemas_ir_gp = []
    adicionar(instrucoes_com_esquemas_ir_gp, obter_registro_lista_ir_gp(instrucoes_ir_gp, 0))
    numero cursor_esquema_final_ir = 0
    enquanto (cursor_esquema_final_ir < tamanho(secoes_estruturas_ir_gp)) {
        adicionar(instrucoes_com_esquemas_ir_gp, obter_registro_lista_ir_gp(secoes_estruturas_ir_gp, cursor_esquema_final_ir))
        cursor_esquema_final_ir = cursor_esquema_final_ir + 1
    }
    cursor_esquema_final_ir = 1
    enquanto (cursor_esquema_final_ir < tamanho(instrucoes_ir_gp)) {
        adicionar(instrucoes_com_esquemas_ir_gp, obter_registro_lista_ir_gp(instrucoes_ir_gp, cursor_esquema_final_ir))
        cursor_esquema_final_ir = cursor_esquema_final_ir + 1
    }
    instrucoes_ir_gp = instrucoes_com_esquemas_ir_gp
    numero secao_funcao_final_ir = 0
    enquanto (secao_funcao_final_ir < tamanho(secoes_funcoes_ir_gp)) {
        adicionar(instrucoes_ir_gp, obter_registro_lista_ir_gp(secoes_funcoes_ir_gp, secao_funcao_final_ir))
        secao_funcao_final_ir = secao_funcao_final_ir + 1
    }
    se (!validar_registros_ir_gp()) { retornar falso }
    retornar verdadeiro
}
funcao escapar_json_ir_gp(texto valor_json_ir) -> texto {
    texto resultado_json_ir = "\""
    texto caractere_json_ir = ""
    numero indice_json_ir = 0
    enquanto (indice_json_ir < tamanho(valor_json_ir)) {
        caractere_json_ir = valor_json_ir[indice_json_ir]
        se (caractere_json_ir == "\"") {
            resultado_json_ir = resultado_json_ir + "\\\""
        } senao {
            se (caractere_json_ir == "\\") {
                resultado_json_ir = resultado_json_ir + "\\\\"
            } senao {
                se (caractere_json_ir == "\n") {
                    resultado_json_ir = resultado_json_ir + "\\n"
                } senao {
                    se (caractere_json_ir == "\r") {
                        resultado_json_ir = resultado_json_ir + "\\r"
                    } senao {
                        se (caractere_json_ir == "\t") {
                            resultado_json_ir = resultado_json_ir + "\\t"
                        } senao {
                            resultado_json_ir = resultado_json_ir + caractere_json_ir
                        }
                    }
                }
            }
        }
        indice_json_ir = indice_json_ir + 1
    }
    retornar resultado_json_ir + "\""
}
funcao serializar_registro_json_ir_gp(InstrucaoIR_GP registro_json_ir) -> texto {
    texto saida_registro_json_ir = "[" + escapar_json_ir_gp(registro_json_ir.opcode)
    texto opcode_json_ir = registro_json_ir.opcode
    se (opcode_json_ir == "GP-IR") {
        retornar saida_registro_json_ir + ",1]"
    }
    se (opcode_json_ir == "CONST") {
        saida_registro_json_ir = saida_registro_json_ir + "," + escapar_json_ir_gp(registro_json_ir.texto1) + ","
        se (registro_json_ir.texto1 == "NUMERO") { retornar saida_registro_json_ir + registro_json_ir.texto3 + "]" }
        se (registro_json_ir.texto1 == "TEXTO") { retornar saida_registro_json_ir + registro_json_ir.texto2 + "]" }
        se (registro_json_ir.texto1 == "LOGICO" || registro_json_ir.texto1 == "PALAVRA_CHAVE") {
            se (registro_json_ir.logico1) { retornar saida_registro_json_ir + "true]" }
            retornar saida_registro_json_ir + "false]"
        }
        retornar saida_registro_json_ir + "null]"
    }
    se (opcode_json_ir == "STRUCT" || opcode_json_ir == "BUILD_STRUCT" || opcode_json_ir == "CALL") {
        retornar saida_registro_json_ir + "," + escapar_json_ir_gp(registro_json_ir.texto1) + "," + texto_de_numero_gp(registro_json_ir.numero1) + "]"
    }
    se (opcode_json_ir == "FUNCTION") {
        retornar saida_registro_json_ir + "," + escapar_json_ir_gp(registro_json_ir.texto1) + "," + escapar_json_ir_gp(registro_json_ir.texto2) + "," + texto_de_numero_gp(registro_json_ir.numero1) + "]"
    }
    se (opcode_json_ir == "STRUCT_FIELD" || opcode_json_ir == "PARAM") {
        retornar saida_registro_json_ir + "," + escapar_json_ir_gp(registro_json_ir.texto1) + "," + escapar_json_ir_gp(registro_json_ir.texto2) + "]"
    }
    se (opcode_json_ir == "BUILD_ARRAY" || opcode_json_ir == "PRINT" || opcode_json_ir == "JUMP" || opcode_json_ir == "JUMP_IF_FALSE") {
        retornar saida_registro_json_ir + "," + texto_de_numero_gp(registro_json_ir.numero1) + "]"
    }
    se (opcode_json_ir == "DECLARE") {
        saida_registro_json_ir = saida_registro_json_ir + "," + escapar_json_ir_gp(registro_json_ir.texto1) + "," + escapar_json_ir_gp(registro_json_ir.texto2)
        se (registro_json_ir.texto3 != "") { saida_registro_json_ir = saida_registro_json_ir + "," + escapar_json_ir_gp(registro_json_ir.texto3) }
        retornar saida_registro_json_ir + "]"
    }
    se (opcode_json_ir == "CODE_BEGIN" || opcode_json_ir == "CODE_END" || opcode_json_ir == "LOAD" || opcode_json_ir == "STORE" || opcode_json_ir == "GET_FIELD" || opcode_json_ir == "SET_FIELD" || opcode_json_ir == "MAKE_TYPED_ARRAY" || opcode_json_ir == "LABEL") {
        retornar saida_registro_json_ir + "," + escapar_json_ir_gp(registro_json_ir.texto1) + "]"
    }
    retornar saida_registro_json_ir + "]"
}
funcao serializar_schema_canonico_ir_gp(texto nome_schema) -> texto {
    texto saida_schema = "["
    numero cursor_schema = 0
    numero campos_schema = 0
    InstrucaoIR_GP campo_schema = criar_registro_ir_gp("", "", "", "", 0, falso)
    logico primeiro_schema = verdadeiro
    enquanto (cursor_schema < tamanho(secoes_estruturas_ir_gp)) {
        campo_schema = obter_registro_lista_ir_gp(secoes_estruturas_ir_gp, cursor_schema)
        se (campo_schema.opcode == "STRUCT" && campo_schema.texto1 == nome_schema) {
            campos_schema = campo_schema.numero1
            cursor_schema = cursor_schema + 1
            enquanto (cursor_schema < tamanho(secoes_estruturas_ir_gp)) {
                campo_schema = obter_registro_lista_ir_gp(secoes_estruturas_ir_gp, cursor_schema)
                se (campo_schema.opcode != "STRUCT_FIELD") { retornar saida_schema + "]" }
                se (!primeiro_schema) { saida_schema = saida_schema + "," }
                saida_schema = saida_schema + "[" + escapar_json_ir_gp(campo_schema.texto2) + "," + escapar_json_ir_gp(campo_schema.texto1) + "]"
                primeiro_schema = falso
                cursor_schema = cursor_schema + 1
            }
            retornar saida_schema + "]"
        }
        cursor_schema = cursor_schema + 1
    }
    retornar saida_schema + "]"
}
funcao serializar_argumentos_canonicos_ir_gp(InstrucaoIR_GP registro_canonico) -> texto {
    texto op_canonico = registro_canonico.opcode
    se (op_canonico == "CONST") {
        se (registro_canonico.texto1 == "NUMERO") { retornar "[" + registro_canonico.texto3 + "]" }
        se (registro_canonico.texto1 == "TEXTO") { retornar "[" + registro_canonico.texto2 + "]" }
        se (registro_canonico.texto1 == "LOGICO" || registro_canonico.texto1 == "PALAVRA_CHAVE") {
            se (registro_canonico.logico1) { retornar "[true]" }
            retornar "[false]"
        }
        retornar "[null]"
    }
    se (op_canonico == "DECLARE") {
        se (registro_canonico.texto3 == "") {
            retornar "[" + escapar_json_ir_gp(registro_canonico.texto1) + "," + escapar_json_ir_gp(registro_canonico.texto2) + ",null]"
        }
        retornar "[" + escapar_json_ir_gp(registro_canonico.texto1) + "," + escapar_json_ir_gp(registro_canonico.texto2) + "," + escapar_json_ir_gp(registro_canonico.texto3) + "]"
    }
    se (op_canonico == "BUILD_STRUCT") {
        retornar "[" + escapar_json_ir_gp(registro_canonico.texto1) + "," + serializar_schema_canonico_ir_gp(registro_canonico.texto1) + "]"
    }
    se (op_canonico == "CALL") {
        retornar "[" + escapar_json_ir_gp(registro_canonico.texto1) + "," + texto_de_numero_gp(registro_canonico.numero1) + "]"
    }
    se (op_canonico == "BUILD_ARRAY" || op_canonico == "PRINT" || op_canonico == "JUMP" || op_canonico == "JUMP_IF_FALSE") {
        retornar "[" + texto_de_numero_gp(registro_canonico.numero1) + "]"
    }
    se (op_canonico == "LOAD" || op_canonico == "STORE" || op_canonico == "GET_FIELD" || op_canonico == "SET_FIELD" || op_canonico == "MAKE_TYPED_ARRAY") {
        retornar "[" + escapar_json_ir_gp(registro_canonico.texto1) + "]"
    }
    retornar "[]"
}
funcao serializar_instrucao_canonica_ir_gp(InstrucaoIR_GP registro_canonico) -> texto {
    retornar "{\"op\":" + escapar_json_ir_gp(registro_canonico.opcode) + ",\"args\":" + serializar_argumentos_canonicos_ir_gp(registro_canonico) + "}"
}
funcao serializar_codigo_principal_canonico_ir_gp() -> texto {
    lista texto partes_main_canonico = []
    numero cursor_main_canonico = 0
    logico dentro_funcao_main_canonico = falso
    logico primeiro_main_canonico = verdadeiro
    InstrucaoIR_GP registro_main_canonico = criar_registro_ir_gp("", "", "", "", 0, falso)
    enquanto (cursor_main_canonico < tamanho(instrucoes_ir_gp)) {
        registro_main_canonico = obter_registro_lista_ir_gp(instrucoes_ir_gp, cursor_main_canonico)
        se (registro_main_canonico.opcode == "FUNCTION") { dentro_funcao_main_canonico = verdadeiro }
        senao {
            se (registro_main_canonico.opcode == "CODE_END") { dentro_funcao_main_canonico = falso }
            senao {
                se (!dentro_funcao_main_canonico && registro_main_canonico.opcode != "GP-IR" && registro_main_canonico.opcode != "STRUCT" && registro_main_canonico.opcode != "STRUCT_FIELD") {
                    se (!primeiro_main_canonico) { adicionar(partes_main_canonico, ",") }
                    adicionar(partes_main_canonico, serializar_instrucao_canonica_ir_gp(registro_main_canonico))
                    primeiro_main_canonico = falso
                }
            }
        }
        cursor_main_canonico = cursor_main_canonico + 1
    }
    retornar "[" + unir_textos(partes_main_canonico) + "]"
}
funcao serializar_funcoes_canonicas_ir_gp() -> texto {
    lista texto partes_funcoes_canonico = []
    lista texto partes_parametros_canonicos = []
    lista texto partes_codigo_funcao_canonico = []
    numero cursor_funcao_canonico = 0
    logico primeira_funcao_canonica = verdadeiro
    InstrucaoIR_GP cabecalho_funcao_canonico = criar_registro_ir_gp("", "", "", "", 0, falso)
    InstrucaoIR_GP registro_funcao_canonico = criar_registro_ir_gp("", "", "", "", 0, falso)
    texto retorno_funcao_canonico = "null"
    texto nome_funcao_canonico = ""
    numero cursor_parametro_canonico = 0
    logico primeiro_parametro_canonico = verdadeiro
    logico primeiro_codigo_funcao_canonico = verdadeiro
    enquanto (cursor_funcao_canonico < tamanho(instrucoes_ir_gp)) {
        cabecalho_funcao_canonico = obter_registro_lista_ir_gp(instrucoes_ir_gp, cursor_funcao_canonico)
        se (cabecalho_funcao_canonico.opcode == "FUNCTION") {
            nome_funcao_canonico = cabecalho_funcao_canonico.texto1
            se (!primeira_funcao_canonica) { adicionar(partes_funcoes_canonico, ",") }
            adicionar(partes_funcoes_canonico, escapar_json_ir_gp(nome_funcao_canonico) + ":{")
            se (cabecalho_funcao_canonico.texto2 == "vazio") { retorno_funcao_canonico = "null" }
            senao { retorno_funcao_canonico = escapar_json_ir_gp(cabecalho_funcao_canonico.texto2) }
            adicionar(partes_funcoes_canonico, "\"return_type\":")
            adicionar(partes_funcoes_canonico, retorno_funcao_canonico)
            adicionar(partes_funcoes_canonico, ",\"parameters\":[")
            cursor_parametro_canonico = cursor_funcao_canonico + 1
            primeiro_parametro_canonico = verdadeiro
            partes_parametros_canonicos = []
            enquanto (cursor_parametro_canonico < tamanho(instrucoes_ir_gp)) {
                registro_funcao_canonico = obter_registro_lista_ir_gp(instrucoes_ir_gp, cursor_parametro_canonico)
                se (registro_funcao_canonico.opcode != "PARAM") { quebrar }
                se (!primeiro_parametro_canonico) { adicionar(partes_parametros_canonicos, ",") }
                adicionar(partes_parametros_canonicos, "[" + escapar_json_ir_gp(registro_funcao_canonico.texto1) + "," + escapar_json_ir_gp(registro_funcao_canonico.texto2) + "]")
                primeiro_parametro_canonico = falso
                cursor_parametro_canonico = cursor_parametro_canonico + 1
            }
            adicionar(partes_funcoes_canonico, unir_textos(partes_parametros_canonicos))
            adicionar(partes_funcoes_canonico, "],\"code\":[")
            cursor_funcao_canonico = cursor_parametro_canonico + 1
            primeiro_codigo_funcao_canonico = verdadeiro
            partes_codigo_funcao_canonico = []
            enquanto (cursor_funcao_canonico < tamanho(instrucoes_ir_gp)) {
                registro_funcao_canonico = obter_registro_lista_ir_gp(instrucoes_ir_gp, cursor_funcao_canonico)
                se (registro_funcao_canonico.opcode == "CODE_END") { quebrar }
                se (!primeiro_codigo_funcao_canonico) { adicionar(partes_codigo_funcao_canonico, ",") }
                adicionar(partes_codigo_funcao_canonico, serializar_instrucao_canonica_ir_gp(registro_funcao_canonico))
                primeiro_codigo_funcao_canonico = falso
                cursor_funcao_canonico = cursor_funcao_canonico + 1
            }
            adicionar(partes_funcoes_canonico, unir_textos(partes_codigo_funcao_canonico))
            adicionar(partes_funcoes_canonico, "]}")
            primeira_funcao_canonica = falso
        }
        cursor_funcao_canonico = cursor_funcao_canonico + 1
    }
    retornar "{" + unir_textos(partes_funcoes_canonico) + "}"
}
funcao serializar_gp_ir_canonico_gp() -> texto {
    retornar "{\"format\":\"GP-IR\",\"ir_version\":1,\"version\":\"0.4\",\"main\":" + serializar_codigo_principal_canonico_ir_gp() + ",\"functions\":" + serializar_funcoes_canonicas_ir_gp() + "}"
}

funcao serializar_ir_json_gp() -> texto {
    texto saida_json_ir_gp = "["
    numero indice_saida_json_ir_gp = 0
    enquanto (indice_saida_json_ir_gp < tamanho(instrucoes_ir_gp)) {
        se (indice_saida_json_ir_gp > 0) { saida_json_ir_gp = saida_json_ir_gp + "," }
        saida_json_ir_gp = saida_json_ir_gp + serializar_registro_json_ir_gp(obter_registro_lista_ir_gp(instrucoes_ir_gp, indice_saida_json_ir_gp))
        indice_saida_json_ir_gp = indice_saida_json_ir_gp + 1
    }
    retornar saida_json_ir_gp + "]"
}

funcao texto_de_numero_gp(numero valor_numero_ir) -> texto {
    texto digitos_ir = "0123456789"
    numero quociente_inteiro_ir = 0
    numero resto_inteiro_ir = valor_numero_ir
    se (valor_numero_ir < 0) { retornar "-" + texto_de_numero_gp(0 - valor_numero_ir) }
    se (valor_numero_ir < 10) { retornar digitos_ir[valor_numero_ir] }
    // A linguagem ainda nao tem operador de divisao inteira; calcular o
    // quociente por subtracao evita indices fracionarios no texto de digitos.
    enquanto (resto_inteiro_ir >= 10) {
        resto_inteiro_ir = resto_inteiro_ir - 10
        quociente_inteiro_ir = quociente_inteiro_ir + 1
    }
    retornar texto_de_numero_gp(quociente_inteiro_ir) + digitos_ir[resto_inteiro_ir]
}

funcao validar_sintaxe_gp(texto fonte) -> logico {
    lista numero filhos_programa = []
    tokens_parser = lexer.lexer_gp(fonte)
    arvore_ast_gp = []
    cursor_parser = 0
    linha_parser = 1
    coluna_parser = 1
    profundidade_laco_parser = 0
    profundidade_funcao_parser = 0
    ultimo_no_ast_gp = -1
    raiz_ast_gp = -1
    erro_parser = falso
    mensagem_parser = ""
    enquanto (cursor_parser < tamanho(tokens_parser) && !erro_parser) {
        se (!parse_comando_gp()) { erro_parser = verdadeiro }
        senao { adicionar(filhos_programa, ultimo_no_ast_gp) }
    }
    se (!erro_parser && cursor_parser == tamanho(tokens_parser)) {
        raiz_ast_gp = criar_no_ast_gp("PROGRAMA", "", filhos_programa)
        retornar verdadeiro
    }
    retornar falso
}

logico exemplo_ast_valido = validar_sintaxe_gp("numero total = 10 + 2 * 3; mostrar(total, 42, somar(1, 2), [4, 5], total >= 1 && verdadeiro || falso, pessoa.nome, itens[0]); total = total + 1")
mostrar("Parser GP valido:", exemplo_ast_valido)
mostrar("AST raiz:", resumo_no_ast_gp(raiz_ast_gp), quantidade_filhos_ast_gp(raiz_ast_gp))
numero primeiro_comando_ast = obter_filho_ast_gp(raiz_ast_gp, 0)
mostrar("AST primeiro comando:", resumo_no_ast_gp(primeiro_comando_ast), quantidade_filhos_ast_gp(primeiro_comando_ast))
mostrar("Linha AST declaracao:", linha_no_ast_gp(primeiro_comando_ast))
mostrar("Coluna AST declaracao:", coluna_no_ast_gp(primeiro_comando_ast))
numero declaracao_expr_ast = obter_filho_ast_gp(primeiro_comando_ast, 0)
mostrar("AST expressao declaracao:", resumo_no_ast_gp(declaracao_expr_ast), quantidade_filhos_ast_gp(declaracao_expr_ast))
numero multiplicacao_ast = obter_filho_ast_gp(declaracao_expr_ast, 1)
mostrar("AST precedencia:", resumo_no_ast_gp(multiplicacao_ast))
numero comando_mostrar_ast = obter_filho_ast_gp(raiz_ast_gp, 1)
numero chamada_ast = obter_filho_ast_gp(comando_mostrar_ast, 2)
numero array_ast = obter_filho_ast_gp(comando_mostrar_ast, 3)
numero logica_ast = obter_filho_ast_gp(comando_mostrar_ast, 4)
numero campo_ast = obter_filho_ast_gp(comando_mostrar_ast, 5)
numero indice_ast = obter_filho_ast_gp(comando_mostrar_ast, 6)
mostrar("AST chamada:", resumo_no_ast_gp(chamada_ast), quantidade_filhos_ast_gp(chamada_ast))
mostrar("AST array:", resumo_no_ast_gp(array_ast), quantidade_filhos_ast_gp(array_ast))
mostrar("AST logico:", resumo_no_ast_gp(logica_ast))
mostrar("AST campo:", resumo_no_ast_gp(campo_ast))
mostrar("AST indice:", resumo_no_ast_gp(indice_ast))
logico exemplo_ast_invalido = validar_sintaxe_gp("numero total = 10 + ;")
mostrar("Parser GP rejeita erro:", !exemplo_ast_invalido)
mostrar("Diagnostico:", mensagem_parser)

logico exemplo_se_valido = validar_sintaxe_gp("se (verdadeiro) { numero x = 1; mostrar(x) } senao { mostrar(0) }")
mostrar("Parser GP aceita se/senao:", exemplo_se_valido)
mostrar("AST condicional:", resumo_no_ast_gp(obter_filho_ast_gp(raiz_ast_gp, 0)), quantidade_filhos_ast_gp(obter_filho_ast_gp(raiz_ast_gp, 0)))
numero no_se_ast = obter_filho_ast_gp(raiz_ast_gp, 0)
numero bloco_entao_ast = obter_filho_ast_gp(no_se_ast, 1)
numero bloco_senao_ast = obter_filho_ast_gp(no_se_ast, 2)
mostrar("AST bloco entao:", resumo_no_ast_gp(bloco_entao_ast), quantidade_filhos_ast_gp(bloco_entao_ast))
mostrar("AST bloco senao:", resumo_no_ast_gp(bloco_senao_ast), quantidade_filhos_ast_gp(bloco_senao_ast))
logico exemplo_se_invalido = validar_sintaxe_gp("se (verdadeiro) { mostrar(1) senao { mostrar(0) }")
mostrar("Parser GP rejeita bloco incompleto:", !exemplo_se_invalido)

logico exemplo_enquanto_valido = validar_sintaxe_gp("numero i = 0; enquanto (i < 3) { i = i + 1; se (i == 2) { mostrar(i) } }")
mostrar("Parser GP aceita enquanto aninhado:", exemplo_enquanto_valido)
numero no_enquanto_ast = obter_filho_ast_gp(raiz_ast_gp, 1)
mostrar("AST enquanto:", resumo_no_ast_gp(no_enquanto_ast), quantidade_filhos_ast_gp(no_enquanto_ast))
numero corpo_enquanto_ast = obter_filho_ast_gp(no_enquanto_ast, 1)
mostrar("AST corpo enquanto:", resumo_no_ast_gp(corpo_enquanto_ast), quantidade_filhos_ast_gp(corpo_enquanto_ast))

logico exemplo_para_valido = validar_sintaxe_gp("para (numero i = 0; i < 3; i = i + 1) { mostrar(i) }")
mostrar("Parser GP aceita para:", exemplo_para_valido)
mostrar("AST para:", resumo_no_ast_gp(obter_filho_ast_gp(raiz_ast_gp, 0)), quantidade_filhos_ast_gp(obter_filho_ast_gp(raiz_ast_gp, 0)))
logico exemplo_funcao_valida = validar_sintaxe_gp("funcao somar(numero a, numero b) -> numero { retornar a + b }")
mostrar("Parser GP aceita funcao/retornar:", exemplo_funcao_valida)
numero no_funcao_ast = obter_filho_ast_gp(raiz_ast_gp, 0)
mostrar("AST funcao:", resumo_no_ast_gp(no_funcao_ast), quantidade_filhos_ast_gp(no_funcao_ast))
mostrar("AST parametro:", resumo_no_ast_gp(obter_filho_ast_gp(no_funcao_ast, 0)))
numero corpo_funcao_ast = obter_filho_ast_gp(no_funcao_ast, 2)
mostrar("AST retorno:", resumo_no_ast_gp(obter_filho_ast_gp(corpo_funcao_ast, 0)))

logico exemplo_estrutura_valida = validar_sintaxe_gp("estrutura Pessoa { texto nome; numero idade; logico ativo; }")
mostrar("Parser GP aceita estrutura:", exemplo_estrutura_valida)
numero no_estrutura_ast = obter_filho_ast_gp(raiz_ast_gp, 0)
mostrar("AST estrutura:", resumo_no_ast_gp(no_estrutura_ast), quantidade_filhos_ast_gp(no_estrutura_ast))
mostrar("AST campo declarado:", resumo_no_ast_gp(obter_filho_ast_gp(no_estrutura_ast, 0)))
logico exemplo_controle_valido = validar_sintaxe_gp("enquanto (verdadeiro) { se (falso) { quebrar } senao { continuar } }")
mostrar("Parser GP aceita quebrar/continuar:", exemplo_controle_valido)
numero no_laco_controle_ast = obter_filho_ast_gp(raiz_ast_gp, 0)
numero no_se_controle_ast = obter_filho_ast_gp(obter_filho_ast_gp(no_laco_controle_ast, 1), 0)
numero bloco_senao_controle_ast = obter_filho_ast_gp(no_se_controle_ast, 2)
mostrar("AST quebrar:", resumo_no_ast_gp(obter_filho_ast_gp(obter_filho_ast_gp(no_se_controle_ast, 1), 0)))
mostrar("AST continuar:", resumo_no_ast_gp(obter_filho_ast_gp(bloco_senao_controle_ast, 0)))

logico quebrar_fora_laco_gp = validar_sintaxe_gp("quebrar")
mostrar("Parser GP rejeita quebrar fora de laco:", !quebrar_fora_laco_gp)
mostrar("Diagnostico quebrar:", mensagem_parser)
logico continuar_fora_laco_gp = validar_sintaxe_gp("continuar")
mostrar("Parser GP rejeita continuar fora de laco:", !continuar_fora_laco_gp)
logico retornar_fora_funcao_gp = validar_sintaxe_gp("retornar 10")
mostrar("Parser GP rejeita retornar fora de funcao:", !retornar_fora_funcao_gp)

// Analise semantica auto-hospedada inicial: declaracoes, escopos e expressoes primitivas.
lista texto nomes_semanticos_ast_gp = []
lista texto tipos_semanticos_ast_gp = []
lista numero escopos_semanticos_ast_gp = []
lista numero pais_semanticos_ast_gp = []
texto erro_semantico_ast_gp = ""
lista texto nomes_funcoes_semanticas_gp = []
lista texto retornos_funcoes_semanticas_gp = []
lista texto parametros_funcoes_semanticas_gp = []
texto retorno_funcao_atual_semantica_gp = ""
logico dentro_funcao_semantica_gp = falso
numero profundidade_lacos_semantica_ast_gp = 0

funcao resetar_semantica_ast_gp() -> logico {
    nomes_semanticos_ast_gp = []
    tipos_semanticos_ast_gp = []
    escopos_semanticos_ast_gp = []
    pais_semanticos_ast_gp = []
    erro_semantico_ast_gp = ""
    nomes_funcoes_semanticas_gp = []
    retornos_funcoes_semanticas_gp = []
    parametros_funcoes_semanticas_gp = []
    retorno_funcao_atual_semantica_gp = ""
    dentro_funcao_semantica_gp = falso
    profundidade_lacos_semantica_ast_gp = 0
    nomes_estruturas_semanticas_gp = []
    chaves_campos_estruturas_semanticas_gp = []
    tipos_campos_estruturas_semanticas_gp = []
    adicionar(pais_semanticos_ast_gp, -1)
    retornar verdadeiro
}
funcao novo_escopo_semantico_ast_gp(numero pai) -> numero {
    adicionar(pais_semanticos_ast_gp, pai)
    retornar tamanho(pais_semanticos_ast_gp) - 1
}
funcao buscar_tipo_semantico_ast_gp(texto nome, numero escopo) -> texto {
    numero atual = escopo
    numero i = tamanho(nomes_semanticos_ast_gp) - 1
    enquanto (atual >= 0) {
        i = tamanho(nomes_semanticos_ast_gp) - 1
        enquanto (i >= 0) {
            se (escopos_semanticos_ast_gp[i] == atual && nomes_semanticos_ast_gp[i] == nome) {
                retornar tipos_semanticos_ast_gp[i]
            }
            i = i - 1
        }
        se (atual >= tamanho(pais_semanticos_ast_gp)) { retornar "" }
        atual = pais_semanticos_ast_gp[atual]
    }
    retornar ""
}
funcao declarar_semantico_ast_gp(texto nome, texto tipo, numero escopo) -> logico {
    numero i = tamanho(nomes_semanticos_ast_gp) - 1
    enquanto (i >= 0) {
        se (escopos_semanticos_ast_gp[i] == escopo && nomes_semanticos_ast_gp[i] == nome) {
            erro_semantico_ast_gp = "Identificador duplicado: " + nome
            retornar falso
        }
        i = i - 1
    }
    adicionar(nomes_semanticos_ast_gp, nome)
    adicionar(tipos_semanticos_ast_gp, tipo)
    adicionar(escopos_semanticos_ast_gp, escopo)
    retornar verdadeiro
}
funcao estrutura_existe_semantica_gp(texto nome_estrutura_busca) -> logico {
    numero indice_estrutura_busca = 0
    enquanto (indice_estrutura_busca < tamanho(nomes_estruturas_semanticas_gp)) {
        se (nomes_estruturas_semanticas_gp[indice_estrutura_busca] == nome_estrutura_busca) { retornar verdadeiro }
        indice_estrutura_busca = indice_estrutura_busca + 1
    }
    retornar falso
}
funcao tipo_campo_estrutura_semantica_gp(texto nome_estrutura_busca, texto nome_campo_busca) -> texto {
    texto chave_campo_busca = nome_estrutura_busca + "|" + nome_campo_busca
    numero indice_campo_busca = 0
    enquanto (indice_campo_busca < tamanho(chaves_campos_estruturas_semanticas_gp)) {
        se (chaves_campos_estruturas_semanticas_gp[indice_campo_busca] == chave_campo_busca) {
            retornar tipos_campos_estruturas_semanticas_gp[indice_campo_busca]
        }
        indice_campo_busca = indice_campo_busca + 1
    }
    retornar ""
}
funcao tipo_semantico_conhecido_gp(texto tipo_busca) -> logico {
    texto elemento_tipo_busca = tipo_elemento_lista_semantica_ast_gp(tipo_busca)
    se (tipo_busca == "numero" || tipo_busca == "texto" || tipo_busca == "logico") { retornar verdadeiro }
    se (elemento_tipo_busca != "") {
        se (elemento_tipo_busca == "numero" || elemento_tipo_busca == "texto" || elemento_tipo_busca == "logico") { retornar verdadeiro }
        retornar estrutura_existe_semantica_gp(elemento_tipo_busca)
    }
    retornar estrutura_existe_semantica_gp(tipo_busca)
}
funcao nome_estrutura_da_chave_campo_semantica_gp(texto chave) -> texto {
    numero separador_chave = 0
    texto nome_estrutura_chave = ""
    enquanto (separador_chave < tamanho(chave)) {
        se (chave[separador_chave] == "|") { quebrar }
        nome_estrutura_chave = nome_estrutura_chave + chave[separador_chave]
        separador_chave = separador_chave + 1
    }
    retornar nome_estrutura_chave
}
funcao registrar_estrutura_semantica_gp(numero indice_estrutura_registro) -> logico {
    NoAST_GP estrutura_ast_registro = arvore_ast_gp[indice_estrutura_registro]
    se (estrutura_existe_semantica_gp(estrutura_ast_registro.valor)) {
        erro_semantico_ast_gp = "Estrutura duplicada: " + estrutura_ast_registro.valor
        retornar falso
    }
    adicionar(nomes_estruturas_semanticas_gp, estrutura_ast_registro.valor)
    numero campo_indice_registro = 0
    numero campo_no_registro = -1
    texto resumo_campo_registro = ""
    texto tipo_campo_registro = ""
    texto elemento_tipo_campo_registro = ""
    texto tipo_validado_campo_registro = ""
    texto nome_campo_registro = ""
    numero separador_campo_registro = 0
    numero cursor_campo_registro = 0
    texto chave_campo_registro = ""
    numero duplicado_campo = 0
    logico tipo_primitivo_ou_lista = falso
    logico nome_de_estrutura_futura = falso
    numero futura = 0
    numero no_futuro = -1
    enquanto (campo_indice_registro < quantidade_filhos_ast_gp(indice_estrutura_registro)) {
        campo_no_registro = obter_filho_ast_gp(indice_estrutura_registro, campo_indice_registro)
        resumo_campo_registro = resumo_no_ast_gp(campo_no_registro)
        separador_campo_registro = 0
        enquanto (separador_campo_registro < tamanho(resumo_campo_registro)) {
            se (resumo_campo_registro[separador_campo_registro] == "|") { quebrar }
            separador_campo_registro = separador_campo_registro + 1
        }
        tipo_campo_registro = ""
        nome_campo_registro = ""
        cursor_campo_registro = separador_campo_registro + 1
        enquanto (cursor_campo_registro < tamanho(resumo_campo_registro)) {
            se (resumo_campo_registro[cursor_campo_registro] == "|") { quebrar }
            tipo_campo_registro = tipo_campo_registro + resumo_campo_registro[cursor_campo_registro]
            cursor_campo_registro = cursor_campo_registro + 1
        }
        cursor_campo_registro = cursor_campo_registro + 1
        enquanto (cursor_campo_registro < tamanho(resumo_campo_registro)) {
            nome_campo_registro = nome_campo_registro + resumo_campo_registro[cursor_campo_registro]
            cursor_campo_registro = cursor_campo_registro + 1
        }
        se (tipo_campo_registro == estrutura_ast_registro.valor) {
            erro_semantico_ast_gp = "Campo nao pode conter estrutura por valor: " + nome_campo_registro
            retornar falso
        }
        // Para lista<T>, valida T como tipo real. Não basta reconhecer a
        // forma lista<...>; o elemento também precisa existir no programa.
        elemento_tipo_campo_registro = tipo_elemento_lista_semantica_ast_gp(tipo_campo_registro)
        tipo_validado_campo_registro = tipo_campo_registro
        se (elemento_tipo_campo_registro != "") {
            tipo_validado_campo_registro = elemento_tipo_campo_registro
        }
        tipo_primitivo_ou_lista = tipo_validado_campo_registro == "numero" || tipo_validado_campo_registro == "texto" || tipo_validado_campo_registro == "logico"
        se (!tipo_primitivo_ou_lista && !estrutura_existe_semantica_gp(tipo_validado_campo_registro)) {
            nome_de_estrutura_futura = falso
            futura = 0
            enquanto (futura < quantidade_filhos_ast_gp(raiz_ast_gp)) {
                no_futuro = obter_filho_ast_gp(raiz_ast_gp, futura)
                se (obter_no_ast_gp(no_futuro).categoria == "ESTRUTURA" && obter_no_ast_gp(no_futuro).valor == tipo_validado_campo_registro) { nome_de_estrutura_futura = verdadeiro }
                futura = futura + 1
            }
            se (!nome_de_estrutura_futura) {
                erro_semantico_ast_gp = "Tipo de campo desconhecido: " + tipo_validado_campo_registro
                retornar falso
            }
        }
        chave_campo_registro = estrutura_ast_registro.valor + "|" + nome_campo_registro
        duplicado_campo = 0
        enquanto (duplicado_campo < tamanho(chaves_campos_estruturas_semanticas_gp)) {
            se (chaves_campos_estruturas_semanticas_gp[duplicado_campo] == chave_campo_registro) {
                erro_semantico_ast_gp = "Campo duplicado: " + nome_campo_registro
                retornar falso
            }
            duplicado_campo = duplicado_campo + 1
        }
        adicionar(chaves_campos_estruturas_semanticas_gp, chave_campo_registro)
        adicionar(tipos_campos_estruturas_semanticas_gp, tipo_campo_registro)
        campo_indice_registro = campo_indice_registro + 1
    }
    retornar verdadeiro
}
funcao registrar_assinatura_funcao_semantica_ast_gp(numero indice) -> logico {
    NoAST_GP funcao_ast = arvore_ast_gp[indice]
    texto cabecalho_funcao = funcao_ast.valor
    numero separador_nome = 0
    enquanto (separador_nome < tamanho(cabecalho_funcao)) {
        se (cabecalho_funcao[separador_nome] == " ") { quebrar }
        separador_nome = separador_nome + 1
    }
    texto nome_funcao_registro = ""
    texto retorno_funcao_registro = ""
    numero posicao = 0
    enquanto (posicao < separador_nome) {
        nome_funcao_registro = nome_funcao_registro + cabecalho_funcao[posicao]
        posicao = posicao + 1
    }
    posicao = separador_nome + 4
    enquanto (posicao < tamanho(cabecalho_funcao)) {
        retorno_funcao_registro = retorno_funcao_registro + cabecalho_funcao[posicao]
        posicao = posicao + 1
    }
    se (retorno_funcao_registro != "vazio" && !tipo_semantico_conhecido_gp(retorno_funcao_registro)) {
        erro_semantico_ast_gp = "Tipo de retorno desconhecido: " + retorno_funcao_registro
        retornar falso
    }
    numero existente = 0
    enquanto (existente < tamanho(nomes_funcoes_semanticas_gp)) {
        se (nomes_funcoes_semanticas_gp[existente] == nome_funcao_registro) {
            erro_semantico_ast_gp = "Funcao duplicada: " + nome_funcao_registro
            retornar falso
        }
        existente = existente + 1
    }
    texto assinatura_registro = ""
    numero parametro_indice_registro = 0
    texto resumo_parametro_registro = ""
    numero separador_tipo_registro = 10
    texto tipo_parametro_registro = ""
    numero caractere_registro = 10
    enquanto (parametro_indice_registro < quantidade_filhos_ast_gp(indice) - 1) {
        resumo_parametro_registro = resumo_no_ast_gp(obter_filho_ast_gp(indice, parametro_indice_registro))
        separador_tipo_registro = 10
        enquanto (separador_tipo_registro < tamanho(resumo_parametro_registro)) {
            se (resumo_parametro_registro[separador_tipo_registro] == "|") { quebrar }
            separador_tipo_registro = separador_tipo_registro + 1
        }
        tipo_parametro_registro = ""
        caractere_registro = 10
        enquanto (caractere_registro < separador_tipo_registro) {
            tipo_parametro_registro = tipo_parametro_registro + resumo_parametro_registro[caractere_registro]
            caractere_registro = caractere_registro + 1
        }
        se (!tipo_semantico_conhecido_gp(tipo_parametro_registro)) {
            erro_semantico_ast_gp = "Tipo de parametro desconhecido: " + tipo_parametro_registro
            retornar falso
        }
        se (parametro_indice_registro > 0) { assinatura_registro = assinatura_registro + "|" }
        assinatura_registro = assinatura_registro + tipo_parametro_registro
        parametro_indice_registro = parametro_indice_registro + 1
    }
    adicionar(nomes_funcoes_semanticas_gp, nome_funcao_registro)
    adicionar(retornos_funcoes_semanticas_gp, retorno_funcao_registro)
    adicionar(parametros_funcoes_semanticas_gp, assinatura_registro)
    retornar verdadeiro
}
funcao tipo_elemento_lista_semantica_ast_gp(texto tipo_lista) -> texto {
    se (tamanho(tipo_lista) < 7) { retornar "" }
    se (tipo_lista[0] != "l" || tipo_lista[1] != "i" || tipo_lista[2] != "s" || tipo_lista[3] != "t" || tipo_lista[4] != "a" || tipo_lista[5] != "<") { retornar "" }
    numero posicao_elemento = 6
    texto tipo_elemento_lista = ""
    enquanto (posicao_elemento < tamanho(tipo_lista)) {
        se (tipo_lista[posicao_elemento] == ">") { retornar tipo_elemento_lista }
        tipo_elemento_lista = tipo_elemento_lista + tipo_lista[posicao_elemento]
        posicao_elemento = posicao_elemento + 1
    }
    retornar ""
}
funcao tipo_expressao_semantica_ast_gp(numero indice, numero escopo) -> texto {
    NoAST_GP no = arvore_ast_gp[indice]
    texto valor = no.valor
    texto tipo = ""
    texto esquerda = ""
    texto direita = ""
    numero filho_esquerdo = -1
    numero filho_direito = -1
    texto tipo_base_indice = ""
    texto tipo_indice_lista = ""
    texto tipo_elemento_array = ""
    texto tipo_item_array = ""
    numero indice_array = 0
    texto tipo_base_campo = ""
    texto tipo_campo_encontrado = ""
    se (no.categoria == "LITERAL") {
        se (valor[0] == "N") { retornar "numero" }
        se (valor[0] == "T") { retornar "texto" }
        se (valor == "PALAVRA_CHAVE|verdadeiro" || valor == "PALAVRA_CHAVE|falso") { retornar "logico" }
        retornar "desconhecido"
    }
    se (no.categoria == "IDENTIFICADOR") {
        tipo = buscar_tipo_semantico_ast_gp(valor, escopo)
        se (tipo == "") {
            erro_semantico_ast_gp = "Identificador nao declarado: " + valor
            retornar "desconhecido"
        }
        retornar tipo
    }
    se (no.categoria == "CHAMADA_NOMEADA") {
        se (!estrutura_existe_semantica_gp(valor)) {
            erro_semantico_ast_gp = "Estrutura nao declarada no construtor nomeado: " + valor
            retornar "desconhecido"
        }
        numero argumento_nomeado_sem = 0
        numero anterior_nomeado_sem = 0
        numero campo_schema_sem = 0
        numero argumento_schema_sem = 0
        texto nome_campo_nomeado_sem = ""
        texto tipo_esperado_nomeado_sem = ""
        texto tipo_recebido_nomeado_sem = ""
        texto nome_campo_schema_sem = ""
        logico campo_presente_nomeado_sem = falso
        NoAST_GP no_argumento_nomeado_sem = NoAST_GP{categoria: "", valor: "", filhos: [], linha: 0, coluna: 0}
        NoAST_GP no_argumento_anterior_sem = NoAST_GP{categoria: "", valor: "", filhos: [], linha: 0, coluna: 0}
        enquanto (argumento_nomeado_sem < quantidade_filhos_ast_gp(indice)) {
            no_argumento_nomeado_sem = obter_no_ast_gp(obter_filho_ast_gp(indice, argumento_nomeado_sem))
            nome_campo_nomeado_sem = no_argumento_nomeado_sem.valor
            tipo_esperado_nomeado_sem = tipo_campo_estrutura_semantica_gp(valor, nome_campo_nomeado_sem)
            se (tipo_esperado_nomeado_sem == "") {
                erro_semantico_ast_gp = "Campo desconhecido no construtor nomeado: " + nome_campo_nomeado_sem
                retornar "desconhecido"
            }
            anterior_nomeado_sem = 0
            enquanto (anterior_nomeado_sem < argumento_nomeado_sem) {
                no_argumento_anterior_sem = obter_no_ast_gp(obter_filho_ast_gp(indice, anterior_nomeado_sem))
                se (no_argumento_anterior_sem.valor == nome_campo_nomeado_sem) {
                    erro_semantico_ast_gp = "Campo duplicado no construtor nomeado: " + nome_campo_nomeado_sem
                    retornar "desconhecido"
                }
                anterior_nomeado_sem = anterior_nomeado_sem + 1
            }
            tipo_recebido_nomeado_sem = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(obter_filho_ast_gp(indice, argumento_nomeado_sem), 0), escopo)
            se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
            se (tipo_esperado_nomeado_sem != tipo_recebido_nomeado_sem) {
                texto elemento_esperado_nomeado_sem = tipo_elemento_lista_semantica_ast_gp(tipo_esperado_nomeado_sem)
                texto elemento_recebido_nomeado_sem = tipo_elemento_lista_semantica_ast_gp(tipo_recebido_nomeado_sem)
                se (elemento_esperado_nomeado_sem == "" || elemento_recebido_nomeado_sem != "desconhecido" && elemento_esperado_nomeado_sem != elemento_recebido_nomeado_sem) {
                    erro_semantico_ast_gp = "Tipo incorreto no campo nomeado " + nome_campo_nomeado_sem + " de " + valor + ": esperado " + tipo_esperado_nomeado_sem + ", recebido " + tipo_recebido_nomeado_sem
                    retornar "desconhecido"
                }
            }
            argumento_nomeado_sem = argumento_nomeado_sem + 1
        }
        campo_schema_sem = 0
        enquanto (campo_schema_sem < tamanho(chaves_campos_estruturas_semanticas_gp)) {
            se (nome_estrutura_da_chave_campo_semantica_gp(chaves_campos_estruturas_semanticas_gp[campo_schema_sem]) == valor) {
                nome_campo_schema_sem = nome_campo_da_chave_ir_gp(chaves_campos_estruturas_semanticas_gp[campo_schema_sem])
                campo_presente_nomeado_sem = falso
                argumento_schema_sem = 0
                enquanto (argumento_schema_sem < quantidade_filhos_ast_gp(indice)) {
                    no_argumento_nomeado_sem = obter_no_ast_gp(obter_filho_ast_gp(indice, argumento_schema_sem))
                    se (no_argumento_nomeado_sem.valor == nome_campo_schema_sem) { campo_presente_nomeado_sem = verdadeiro }
                    argumento_schema_sem = argumento_schema_sem + 1
                }
                se (!campo_presente_nomeado_sem) {
                    erro_semantico_ast_gp = "Campo ausente no construtor nomeado: " + nome_campo_schema_sem
                    retornar "desconhecido"
                }
            }
            campo_schema_sem = campo_schema_sem + 1
        }
        retornar valor
    }
    se (no.categoria == "CHAMADA") {
        se (valor == "entrada_fonte") {
            se (quantidade_filhos_ast_gp(indice) != 0) {
                erro_semantico_ast_gp = "entrada_fonte nao aceita argumentos"
                retornar "desconhecido"
            }
            retornar "texto"
        }
        se (valor == "unir_textos") {
            se (quantidade_filhos_ast_gp(indice) != 1) { erro_semantico_ast_gp = "unir_textos exige um argumento"; retornar "desconhecido" }
            tipo_base_indice = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 0), escopo)
            se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
            tipo_indice_lista = tipo_elemento_lista_semantica_ast_gp(tipo_base_indice)
            se (tipo_indice_lista != "texto") { erro_semantico_ast_gp = "unir_textos exige lista texto"; retornar "desconhecido" }
            retornar "texto"
        }
        se (valor == "tamanho") {
            se (quantidade_filhos_ast_gp(indice) != 1) { erro_semantico_ast_gp = "tamanho exige um argumento"; retornar "desconhecido" }
            tipo_base_indice = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 0), escopo)
            se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
            tipo_indice_lista = tipo_elemento_lista_semantica_ast_gp(tipo_base_indice)
            se (tipo_base_indice != "texto" && tipo_indice_lista == "") { erro_semantico_ast_gp = "tamanho exige texto ou lista"; retornar "desconhecido" }
            retornar "numero"
        }
        se (valor == "adicionar") {
            se (quantidade_filhos_ast_gp(indice) != 2) { erro_semantico_ast_gp = "adicionar exige dois argumentos"; retornar "desconhecido" }
            tipo_base_indice = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 0), escopo)
            se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
            tipo_indice_lista = tipo_elemento_lista_semantica_ast_gp(tipo_base_indice)
            se (tipo_indice_lista == "") { erro_semantico_ast_gp = "adicionar exige uma lista"; retornar "desconhecido" }
            tipo_item_array = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 1), escopo)
            se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
            se (tipo_indice_lista != tipo_item_array && tipo_item_array != "desconhecido") {
                erro_semantico_ast_gp = "Tipo incorreto no elemento adicionado"
                retornar "desconhecido"
            }
            retornar tipo_base_indice
        }
        se (valor == "remover") {
            se (quantidade_filhos_ast_gp(indice) != 2) { erro_semantico_ast_gp = "remover exige dois argumentos"; retornar "desconhecido" }
            tipo_base_indice = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 0), escopo)
            se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
            tipo_indice_lista = tipo_elemento_lista_semantica_ast_gp(tipo_base_indice)
            se (tipo_indice_lista == "") { erro_semantico_ast_gp = "remover exige uma lista"; retornar "desconhecido" }
            tipo_item_array = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 1), escopo)
            se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
            se (tipo_item_array != "numero") { erro_semantico_ast_gp = "Indice de remover deve ser numero"; retornar "desconhecido" }
            retornar tipo_indice_lista
        }
        se (estrutura_existe_semantica_gp(valor)) {
            numero quantidade_campos_construtor = 0
            numero campo_construtor = 0
            numero argumento_construtor = 0
            texto tipo_esperado_construtor = ""
            texto tipo_recebido_construtor = ""
            texto estrutura_chave_construtor = ""
            enquanto (campo_construtor < tamanho(chaves_campos_estruturas_semanticas_gp)) {
                estrutura_chave_construtor = nome_estrutura_da_chave_campo_semantica_gp(chaves_campos_estruturas_semanticas_gp[campo_construtor])
                se (estrutura_chave_construtor == valor) { quantidade_campos_construtor = quantidade_campos_construtor + 1 }
                campo_construtor = campo_construtor + 1
            }
            se (quantidade_filhos_ast_gp(indice) != quantidade_campos_construtor) {
                erro_semantico_ast_gp = "Quantidade de campos incorreta no construtor " + valor
                retornar "desconhecido"
            }
            campo_construtor = 0
            enquanto (campo_construtor < tamanho(chaves_campos_estruturas_semanticas_gp)) {
                estrutura_chave_construtor = nome_estrutura_da_chave_campo_semantica_gp(chaves_campos_estruturas_semanticas_gp[campo_construtor])
                se (estrutura_chave_construtor == valor) {
                    tipo_esperado_construtor = tipos_campos_estruturas_semanticas_gp[campo_construtor]
                    tipo_recebido_construtor = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, argumento_construtor), escopo)
                    se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
                    se (tipo_esperado_construtor != tipo_recebido_construtor) {
                        erro_semantico_ast_gp = "Tipo incorreto no campo do construtor " + valor
                        retornar "desconhecido"
                    }
                    argumento_construtor = argumento_construtor + 1
                }
                campo_construtor = campo_construtor + 1
            }
            retornar valor
        }
        numero f = 0
        numero encontrado = -1
        enquanto (f < tamanho(nomes_funcoes_semanticas_gp)) { se (nomes_funcoes_semanticas_gp[f] == valor) { encontrado = f }; f = f + 1 }
        se (encontrado < 0) { erro_semantico_ast_gp = "Funcao nao declarada: " + valor; retornar "desconhecido" }
        texto assinatura = parametros_funcoes_semanticas_gp[encontrado]
        numero esperados = 0
        se (assinatura != "") { esperados = 1; numero q = 0; enquanto (q < tamanho(assinatura)) { se (assinatura[q] == "|") { esperados = esperados + 1 }; q = q + 1 } }
        se (quantidade_filhos_ast_gp(indice) != esperados) { erro_semantico_ast_gp = "Quantidade de argumentos incorreta em " + valor; retornar "desconhecido" }
        numero a = 0
        numero inicio = 0
        numero fim = 0
        texto esperado = ""
        numero z = 0
        texto recebido = ""
        enquanto (a < esperados) {
            fim = inicio
            enquanto (fim < tamanho(assinatura)) {
                se (assinatura[fim] == "|") { quebrar }
                fim = fim + 1
            }
            esperado = ""
            z = inicio
            enquanto (z < fim) { esperado = esperado + assinatura[z]; z = z + 1 }
            recebido = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, a), escopo)
            se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
            se (esperado != recebido) { erro_semantico_ast_gp = "Tipo incorreto nos argumentos de " + valor; retornar "desconhecido" }
            inicio = fim + 1; a = a + 1
        }
        retornar retornos_funcoes_semanticas_gp[encontrado]
    }
    se (no.categoria == "ARRAY") {
        tipo_elemento_array = "desconhecido"
        indice_array = 0
        se (quantidade_filhos_ast_gp(indice) > 0) {
            tipo_elemento_array = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 0), escopo)
            se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
            indice_array = 1
            enquanto (indice_array < quantidade_filhos_ast_gp(indice)) {
                tipo_item_array = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, indice_array), escopo)
                se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
                se (tipo_item_array != tipo_elemento_array) {
                    erro_semantico_ast_gp = "Lista deve conter elementos de um unico tipo"
                    retornar "desconhecido"
                }
                indice_array = indice_array + 1
            }
        }
        retornar "lista<" + tipo_elemento_array + ">"
    }
    se (no.categoria == "CAMPO") {
        tipo_base_campo = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 0), escopo)
        se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
        tipo_campo_encontrado = tipo_campo_estrutura_semantica_gp(tipo_base_campo, valor)
        se (tipo_campo_encontrado == "") {
            erro_semantico_ast_gp = "Campo inexistente: " + valor + " em " + tipo_base_campo
            retornar "desconhecido"
        }
        retornar tipo_campo_encontrado
    }
    se (no.categoria == "INDICE") {
        tipo_base_indice = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 0), escopo)
        se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
        tipo_item_array = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 1), escopo)
        se (erro_semantico_ast_gp != "") { retornar "desconhecido" }
        se (tipo_item_array != "numero") { erro_semantico_ast_gp = "Indice de lista deve ser numero"; retornar "desconhecido" }
        se (tipo_base_indice == "texto") { retornar "texto" }
        tipo_indice_lista = tipo_elemento_lista_semantica_ast_gp(tipo_base_indice)
        se (tipo_indice_lista == "") { erro_semantico_ast_gp = "Indexacao exige lista ou texto"; retornar "desconhecido" }
        retornar tipo_indice_lista
    }
    se (no.categoria == "AGRUPAMENTO") {
        retornar tipo_expressao_semantica_ast_gp(no.filhos[0], escopo)
    }
    se (no.categoria == "UNARIO") {
        tipo = tipo_expressao_semantica_ast_gp(no.filhos[0], escopo)
        se (valor == "!" && tipo != "logico") {
            erro_semantico_ast_gp = "Operador ! exige logico"
            retornar "desconhecido"
        }
        se (valor == "-" && tipo != "numero") {
            erro_semantico_ast_gp = "Operador - exige numero"
            retornar "desconhecido"
        }
        retornar tipo
    }
    se (no.categoria == "BINARIO") {
        filho_esquerdo = no.filhos[0]
        filho_direito = no.filhos[1]
        esquerda = tipo_expressao_semantica_ast_gp(filho_esquerdo, escopo)
        direita = tipo_expressao_semantica_ast_gp(filho_direito, escopo)
        se (valor == "&&" || valor == "||") {
            se (esquerda != "logico" || direita != "logico") {
                erro_semantico_ast_gp = "Operador logico exige operandos logicos"
                retornar "desconhecido"
            }
            retornar "logico"
        }
        se (valor == "==" || valor == "!=" || valor == ">" || valor == "<" || valor == ">=" || valor == "<=") {
            se (esquerda != direita) {
                erro_semantico_ast_gp = "Comparacao entre tipos incompatíveis"
                retornar "desconhecido"
            }
            retornar "logico"
        }
        se (valor == "+" && esquerda == "texto" && direita == "texto") { retornar "texto" }
        se (esquerda != "numero" || direita != "numero") {
            erro_semantico_ast_gp = "Operacao aritmetica exige numeros"
            retornar "desconhecido"
        }
        retornar "numero"
    }
    erro_semantico_ast_gp = "Expressao ainda nao suportada: " + no.categoria
    retornar "desconhecido"
}
funcao comando_garante_retorno_semantico_gp(numero indice_retorno_fluxo) -> logico {
    NoAST_GP no_fluxo = obter_no_ast_gp(indice_retorno_fluxo)
    numero filho_fluxo = 0
    numero ramo_fluxo = -1
    se (no_fluxo.categoria == "RETORNAR") { retornar verdadeiro }
    se (no_fluxo.categoria == "BLOCO") {
        enquanto (filho_fluxo < quantidade_filhos_ast_gp(indice_retorno_fluxo)) {
            ramo_fluxo = obter_filho_ast_gp(indice_retorno_fluxo, filho_fluxo)
            se (comando_garante_retorno_semantico_gp(ramo_fluxo)) { retornar verdadeiro }
            filho_fluxo = filho_fluxo + 1
        }
        retornar falso
    }
    se (no_fluxo.categoria == "SE") {
        se (quantidade_filhos_ast_gp(indice_retorno_fluxo) < 3) { retornar falso }
        retornar comando_garante_retorno_semantico_gp(obter_filho_ast_gp(indice_retorno_fluxo, 1)) && comando_garante_retorno_semantico_gp(obter_filho_ast_gp(indice_retorno_fluxo, 2))
    }
    retornar falso
}
funcao analisar_comando_semantico_ast_gp(numero indice, numero escopo) -> logico {
    NoAST_GP no = arvore_ast_gp[indice]
    texto tipo_declarado = ""
    texto nome = ""
    texto tipo_real = ""
    texto tipo_base_destino = ""
    texto tipo_indice_destino = ""
    numero separador = 0
    numero novo_escopo = -1
    se (no.categoria == "DECLARACAO") {
        separador = tamanho(no.valor) - tamanho(no.valor)
        // O tipo e o nome sao separados pelo primeiro caractere '|'.
        enquanto (separador < tamanho(no.valor)) {
            se (no.valor[separador] == "|") { quebrar }
            separador = separador + 1
        }
        tipo_declarado = ""
        nome = ""
        numero j = 0
        enquanto (j < separador) { tipo_declarado = tipo_declarado + no.valor[j]; j = j + 1 }
        j = separador + 1
        enquanto (j < tamanho(no.valor)) { nome = nome + no.valor[j]; j = j + 1 }
        se (!tipo_semantico_conhecido_gp(tipo_declarado)) {
            erro_semantico_ast_gp = "Tipo de variavel desconhecido: " + tipo_declarado
            retornar falso
        }
        tipo_real = tipo_expressao_semantica_ast_gp(no.filhos[0], escopo)
        se (erro_semantico_ast_gp != "") { retornar falso }
        se (tipo_declarado != tipo_real) {
            texto elemento_esperado = tipo_elemento_lista_semantica_ast_gp(tipo_declarado)
            texto elemento_recebido = tipo_elemento_lista_semantica_ast_gp(tipo_real)
            se (elemento_esperado == "" || elemento_recebido != "desconhecido" && elemento_esperado != elemento_recebido) {
                erro_semantico_ast_gp = "Tipo incompativel em " + nome + ": esperado " + tipo_declarado + ", recebido " + tipo_real
                retornar falso
            }
        }
        retornar declarar_semantico_ast_gp(nome, tipo_declarado, escopo)
    }
    se (no.categoria == "CHAMADA_COMANDO") {
        se (tamanho(no.filhos) != 1) {
            erro_semantico_ast_gp = "Comando de chamada invalido"
            retornar falso
        }
        tipo_expressao_semantica_ast_gp(no.filhos[0], escopo)
        retornar erro_semantico_ast_gp == ""
    }
    se (no.categoria == "ATRIBUICAO") {
        NoAST_GP destino = arvore_ast_gp[no.filhos[0]]
        se (destino.categoria == "IDENTIFICADOR") {
            tipo_declarado = buscar_tipo_semantico_ast_gp(destino.valor, escopo)
            se (tipo_declarado == "") {
                erro_semantico_ast_gp = "Identificador nao declarado: " + destino.valor
                retornar falso
            }
        } senao {
            se (destino.categoria == "INDICE") {
                tipo_base_destino = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(no.filhos[0], 0), escopo)
                se (erro_semantico_ast_gp != "") { retornar falso }
                tipo_indice_destino = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(no.filhos[0], 1), escopo)
                se (erro_semantico_ast_gp != "") { retornar falso }
                se (tipo_indice_destino != "numero") {
                    erro_semantico_ast_gp = "Indice de atribuicao deve ser numero"
                    retornar falso
                }
                tipo_declarado = tipo_elemento_lista_semantica_ast_gp(tipo_base_destino)
                se (tipo_declarado == "") {
                    erro_semantico_ast_gp = "Atribuicao por indice exige lista"
                    retornar falso
                }
            } senao {
                se (destino.categoria == "CAMPO") {
                    tipo_declarado = tipo_expressao_semantica_ast_gp(no.filhos[0], escopo)
                    se (erro_semantico_ast_gp != "") { retornar falso }
                } senao {
                    erro_semantico_ast_gp = "Destino de atribuicao nao suportado"
                    retornar falso
                }
            }
        }
        tipo_real = tipo_expressao_semantica_ast_gp(no.filhos[1], escopo)
        se (erro_semantico_ast_gp != "") { retornar falso }
        se (tipo_declarado != tipo_real) {
            texto elemento_esperado_atribuicao = tipo_elemento_lista_semantica_ast_gp(tipo_declarado)
            texto elemento_recebido_atribuicao = tipo_elemento_lista_semantica_ast_gp(tipo_real)
            se (elemento_esperado_atribuicao == "" || elemento_recebido_atribuicao != "desconhecido" && elemento_esperado_atribuicao != elemento_recebido_atribuicao) {
                erro_semantico_ast_gp = "Atribuicao incompativel: " + destino.valor
                retornar falso
            }
        }
        retornar verdadeiro
    }
    se (no.categoria == "ESTRUTURA" || no.categoria == "VAZIO") { retornar verdadeiro }
    se (no.categoria == "FUNCAO") {
        texto cabecalho = no.valor
        numero sep = 0
        enquanto (sep < tamanho(cabecalho)) {
            se (cabecalho[sep] == " ") { quebrar }
            sep = sep + 1
        }
        texto nome_funcao = ""
        texto retorno_funcao = ""
        numero c = 0
        enquanto (c < sep) { nome_funcao = nome_funcao + cabecalho[c]; c = c + 1 }
        c = sep + 4
        enquanto (c < tamanho(cabecalho)) { retorno_funcao = retorno_funcao + cabecalho[c]; c = c + 1 }
        numero indice_funcao = 0
        logico assinatura_encontrada = falso
        enquanto (indice_funcao < tamanho(nomes_funcoes_semanticas_gp)) {
            se (nomes_funcoes_semanticas_gp[indice_funcao] == nome_funcao) { assinatura_encontrada = verdadeiro }
            indice_funcao = indice_funcao + 1
        }
        se (!assinatura_encontrada) {
            erro_semantico_ast_gp = "Assinatura de funcao ausente: " + nome_funcao
            retornar falso
        }
        numero escopo_funcao = novo_escopo_semantico_ast_gp(0)
        numero pidx = 0
        texto resumo_parametro = ""
        numero barra_parametro = 10
        texto tipo_parametro = ""
        texto nome_parametro = ""
        numero cursor_parametro = 10
        enquanto (pidx < quantidade_filhos_ast_gp(indice) - 1) {
            resumo_parametro = resumo_no_ast_gp(obter_filho_ast_gp(indice, pidx))
            barra_parametro = 10
            enquanto (barra_parametro < tamanho(resumo_parametro)) {
                se (resumo_parametro[barra_parametro] == "|") { quebrar }
                barra_parametro = barra_parametro + 1
            }
            tipo_parametro = ""
            nome_parametro = ""
            cursor_parametro = 10
            enquanto (cursor_parametro < barra_parametro) {
                tipo_parametro = tipo_parametro + resumo_parametro[cursor_parametro]
                cursor_parametro = cursor_parametro + 1
            }
            cursor_parametro = barra_parametro + 1
            enquanto (cursor_parametro < tamanho(resumo_parametro)) {
                nome_parametro = nome_parametro + resumo_parametro[cursor_parametro]
                cursor_parametro = cursor_parametro + 1
            }
            se (!declarar_semantico_ast_gp(nome_parametro, tipo_parametro, escopo_funcao)) { retornar falso }
            pidx = pidx + 1
        }
        logico anterior_dentro = dentro_funcao_semantica_gp
        texto anterior_retorno = retorno_funcao_atual_semantica_gp
        numero lacos_anteriores_funcao = profundidade_lacos_semantica_ast_gp
        dentro_funcao_semantica_gp = verdadeiro
        retorno_funcao_atual_semantica_gp = retorno_funcao
        profundidade_lacos_semantica_ast_gp = 0
        logico ok_corpo = analisar_comando_semantico_ast_gp(obter_filho_ast_gp(indice, quantidade_filhos_ast_gp(indice) - 1), escopo_funcao)
        dentro_funcao_semantica_gp = anterior_dentro
        retorno_funcao_atual_semantica_gp = anterior_retorno
        profundidade_lacos_semantica_ast_gp = lacos_anteriores_funcao
        se (!ok_corpo) { retornar falso }
        se (retorno_funcao != "vazio" && !comando_garante_retorno_semantico_gp(obter_filho_ast_gp(indice, quantidade_filhos_ast_gp(indice) - 1))) {
            erro_semantico_ast_gp = "Funcao pode terminar sem retornar: " + nome_funcao
            retornar falso
        }
        retornar verdadeiro
    }
    se (no.categoria == "RETORNAR") {
        se (!dentro_funcao_semantica_gp) { erro_semantico_ast_gp = "Retornar fora de funcao"; retornar falso }
        texto tipo_retorno = "vazio"
        se (quantidade_filhos_ast_gp(indice) > 0) { tipo_retorno = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 0), escopo) }
        se (erro_semantico_ast_gp != "") { retornar falso }
        se (tipo_retorno != retorno_funcao_atual_semantica_gp) { erro_semantico_ast_gp = "Retorno incompativel: esperado " + retorno_funcao_atual_semantica_gp + ", recebido " + tipo_retorno; retornar falso }
        retornar verdadeiro
    }
    se (no.categoria == "BLOCO") {
        novo_escopo = novo_escopo_semantico_ast_gp(escopo)
        numero k = 0
        enquanto (k < tamanho(no.filhos)) {
            se (!analisar_comando_semantico_ast_gp(no.filhos[k], novo_escopo)) { retornar falso }
            k = k + 1
        }
        retornar verdadeiro
    }
    se (no.categoria == "MOSTRAR") {
        numero m = 0
        enquanto (m < tamanho(no.filhos)) {
            tipo_expressao_semantica_ast_gp(no.filhos[m], escopo)
            se (erro_semantico_ast_gp != "") { retornar falso }
            m = m + 1
        }
        retornar verdadeiro
    }
    se (no.categoria == "SE") {
        tipo_real = tipo_expressao_semantica_ast_gp(no.filhos[0], escopo)
        se (erro_semantico_ast_gp != "") { retornar falso }
        se (tipo_real != "logico") {
            erro_semantico_ast_gp = "Condicao exige logico"
            retornar falso
        }
        se (!analisar_comando_semantico_ast_gp(no.filhos[1], escopo)) { retornar falso }
        se (tamanho(no.filhos) > 2) {
            se (!analisar_comando_semantico_ast_gp(no.filhos[2], escopo)) { retornar falso }
        }
        retornar verdadeiro
    }
    se (no.categoria == "ENQUANTO") {
        tipo_real = tipo_expressao_semantica_ast_gp(obter_filho_ast_gp(indice, 0), escopo)
        se (erro_semantico_ast_gp != "") { retornar falso }
        se (tipo_real != "logico") {
            erro_semantico_ast_gp = "Condicao de enquanto exige logico"
            retornar falso
        }
        profundidade_lacos_semantica_ast_gp = profundidade_lacos_semantica_ast_gp + 1
        logico resultado_enquanto = analisar_comando_semantico_ast_gp(obter_filho_ast_gp(indice, 1), escopo)
        profundidade_lacos_semantica_ast_gp = profundidade_lacos_semantica_ast_gp - 1
        retornar resultado_enquanto
    }
    se (no.categoria == "PARA") {
        numero escopo_para = novo_escopo_semantico_ast_gp(escopo)
        numero inicializacao_para = obter_filho_ast_gp(indice, 0)
        numero condicao_para = obter_filho_ast_gp(indice, 1)
        numero incremento_para = obter_filho_ast_gp(indice, 2)
        numero corpo_para = obter_filho_ast_gp(indice, 3)
        se (resumo_no_ast_gp(inicializacao_para) != "VAZIO|inicializacao") {
            se (!analisar_comando_semantico_ast_gp(inicializacao_para, escopo_para)) { retornar falso }
        }
        se (resumo_no_ast_gp(condicao_para) != "VAZIO|condicao") {
            tipo_real = tipo_expressao_semantica_ast_gp(condicao_para, escopo_para)
            se (erro_semantico_ast_gp != "") { retornar falso }
            se (tipo_real != "logico") {
                erro_semantico_ast_gp = "Condicao de para exige logico"
                retornar falso
            }
        }
        profundidade_lacos_semantica_ast_gp = profundidade_lacos_semantica_ast_gp + 1
        logico resultado_corpo_para = analisar_comando_semantico_ast_gp(corpo_para, escopo_para)
        profundidade_lacos_semantica_ast_gp = profundidade_lacos_semantica_ast_gp - 1
        se (!resultado_corpo_para) { retornar falso }
        se (resumo_no_ast_gp(incremento_para) != "VAZIO|incremento") {
            se (resumo_no_ast_gp(incremento_para)[0] == "A") {
                se (!analisar_comando_semantico_ast_gp(incremento_para, escopo_para)) { retornar falso }
            } senao {
                tipo_expressao_semantica_ast_gp(incremento_para, escopo_para)
                se (erro_semantico_ast_gp != "") { retornar falso }
            }
        }
        retornar verdadeiro
    }
    se (no.categoria == "QUEBRAR" || no.categoria == "CONTINUAR") {
        se (profundidade_lacos_semantica_ast_gp <= 0) {
            erro_semantico_ast_gp = no.categoria + " fora de laco"
            retornar falso
        }
        retornar verdadeiro
    }
    erro_semantico_ast_gp = "Comando ainda nao suportado: " + no.categoria
    retornar falso
}
funcao analisar_semantica_ast_gp(numero raiz) -> logico {
    resetar_semantica_ast_gp()
    se (raiz < 0 || raiz >= tamanho(arvore_ast_gp)) {
        erro_semantico_ast_gp = "Raiz AST invalida"
        retornar falso
    }
    se (resumo_no_ast_gp(raiz) != "PROGRAMA|") {
        erro_semantico_ast_gp = "AST nao e um programa"
        retornar falso
    }
    // Primeira passagem A: registra tipos e campos antes de validar construtores.
    numero i = 0
    numero item = -1
    enquanto (i < quantidade_filhos_ast_gp(raiz)) {
        item = obter_filho_ast_gp(raiz, i)
        se (obter_no_ast_gp(item).categoria == "ESTRUTURA") {
            se (!registrar_estrutura_semantica_gp(item)) { retornar falso }
        }
        i = i + 1
    }
    // Primeira passagem B: registra assinaturas de funcao antes de validar chamadas.
    i = 0
    enquanto (i < quantidade_filhos_ast_gp(raiz)) {
        item = obter_filho_ast_gp(raiz, i)
        se (resumo_no_ast_gp(item)[0] == "F") {
            se (!registrar_assinatura_funcao_semantica_ast_gp(item)) { retornar falso }
        }
        i = i + 1
    }
    // Segunda passagem: valida os corpos e os comandos globais.
    i = 0
    enquanto (i < quantidade_filhos_ast_gp(raiz)) {
        se (!analisar_comando_semantico_ast_gp(obter_filho_ast_gp(raiz, i), 0)) { retornar falso }
        i = i + 1
    }
    retornar verdadeiro
}

logico exemplo_semantica_ast_valida = validar_sintaxe_gp("numero idade = 29; texto nome = \"Gabriel\"; se (idade > 18) { logico ativo = verdadeiro; mostrar(nome, ativo) }")
logico resultado_semantica_ast_valida = falso
se (exemplo_semantica_ast_valida) { resultado_semantica_ast_valida = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP aceita programa tipado:", resultado_semantica_ast_valida)
mostrar("Diagnostico semantico GP:", erro_semantico_ast_gp)

logico exemplo_semantica_ast_tipo_invalido = validar_sintaxe_gp("numero idade = \"vinte\"")
logico resultado_semantica_ast_tipo_invalido = verdadeiro
se (exemplo_semantica_ast_tipo_invalido) { resultado_semantica_ast_tipo_invalido = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita tipo incorreto:", !resultado_semantica_ast_tipo_invalido)
mostrar("Diagnostico tipo incorreto:", erro_semantico_ast_gp)

logico exemplo_semantica_ast_nome_invalido = validar_sintaxe_gp("mostrar(nao_existe)")
logico resultado_semantica_ast_nome_invalido = verdadeiro
se (exemplo_semantica_ast_nome_invalido) { resultado_semantica_ast_nome_invalido = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita nome desconhecido:", !resultado_semantica_ast_nome_invalido)
mostrar("Diagnostico nome desconhecido:", erro_semantico_ast_gp)

logico exemplo_semantica_ast_duplicada = validar_sintaxe_gp("numero idade = 20; numero idade = 30")
logico resultado_semantica_ast_duplicada = verdadeiro
se (exemplo_semantica_ast_duplicada) { resultado_semantica_ast_duplicada = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita duplicata:", !resultado_semantica_ast_duplicada)
mostrar("Diagnostico duplicata:", erro_semantico_ast_gp)

logico exemplo_semantica_ast_sombra = validar_sintaxe_gp("numero idade = 20; se (verdadeiro) { texto idade = \"vinte\"; mostrar(idade) }")
logico resultado_semantica_ast_sombra = falso
se (exemplo_semantica_ast_sombra) { resultado_semantica_ast_sombra = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP permite sombra local:", resultado_semantica_ast_sombra)

logico exemplo_funcao_semantica_gp = validar_sintaxe_gp("funcao dobrar(numero valor) -> numero { retornar valor * 2 } numero total = dobrar(21)")
logico resultado_funcao_semantica_gp = falso
se (exemplo_funcao_semantica_gp) { resultado_funcao_semantica_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP valida parametros e retorno:", resultado_funcao_semantica_gp)
mostrar("Diagnostico funcao GP:", erro_semantico_ast_gp)

logico exemplo_argumento_invalido_gp = validar_sintaxe_gp("funcao dobrar(numero valor) -> numero { retornar valor * 2 } numero total = dobrar(\"vinte\")")
logico resultado_argumento_invalido_gp = verdadeiro
se (exemplo_argumento_invalido_gp) { resultado_argumento_invalido_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita argumento incorreto:", !resultado_argumento_invalido_gp)

logico exemplo_retorno_invalido_gp = validar_sintaxe_gp("funcao calcular() -> numero { retornar \"erro\" }")
logico resultado_retorno_invalido_gp = verdadeiro
se (exemplo_retorno_invalido_gp) { resultado_retorno_invalido_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita retorno incorreto:", !resultado_retorno_invalido_gp)

logico exemplo_chamada_antes_funcao_gp = validar_sintaxe_gp("numero resultado = somar(20, 22); funcao somar(numero a, numero b) -> numero { retornar a + b }")
logico resultado_chamada_antes_funcao_gp = falso
se (exemplo_chamada_antes_funcao_gp) { resultado_chamada_antes_funcao_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP aceita chamada antes da funcao:", resultado_chamada_antes_funcao_gp)

logico exemplo_quantidade_argumentos_gp = validar_sintaxe_gp("funcao somar(numero a, numero b) -> numero { retornar a + b } numero total = somar(20)")
logico resultado_quantidade_argumentos_gp = verdadeiro
se (exemplo_quantidade_argumentos_gp) { resultado_quantidade_argumentos_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita quantidade incorreta:", !resultado_quantidade_argumentos_gp)

logico exemplo_parametro_duplicado_gp = validar_sintaxe_gp("funcao somar(numero valor, numero valor) -> numero { retornar valor }")
logico resultado_parametro_duplicado_gp = verdadeiro
se (exemplo_parametro_duplicado_gp) { resultado_parametro_duplicado_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita parametro duplicado:", !resultado_parametro_duplicado_gp)

logico exemplo_lacos_semantica_gp = validar_sintaxe_gp("para (numero i = 0; i < 3; i = i + 1) { se (i == 1) { continuar } senao { quebrar } } enquanto (verdadeiro) { quebrar }")
logico resultado_lacos_semantica_gp = falso
se (exemplo_lacos_semantica_gp) { resultado_lacos_semantica_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP valida para, enquanto e controle de laco:", resultado_lacos_semantica_gp)

logico exemplo_condicao_laco_invalida_gp = validar_sintaxe_gp("enquanto (1) { mostrar(1) }")
logico resultado_condicao_laco_invalida_gp = verdadeiro
se (exemplo_condicao_laco_invalida_gp) { resultado_condicao_laco_invalida_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita condicao de laco nao logica:", !resultado_condicao_laco_invalida_gp)

logico exemplo_condicao_para_invalida_gp = validar_sintaxe_gp("para (numero i = 0; i; i = i + 1) { mostrar(i) }")
logico resultado_condicao_para_invalida_gp = verdadeiro
se (exemplo_condicao_para_invalida_gp) { resultado_condicao_para_invalida_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita condicao de para nao logica:", !resultado_condicao_para_invalida_gp)

logico exemplo_arrays_semantica_gp = validar_sintaxe_gp("lista numero valores = [1, 2, 3]; numero primeiro = valores[0]; lista numero ampliada = adicionar(valores, 4); numero removido = remover(ampliada, 1); numero quantidade = tamanho(ampliada); mostrar(primeiro, removido, quantidade)")
logico resultado_arrays_semantica_gp = falso
se (exemplo_arrays_semantica_gp) { resultado_arrays_semantica_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP valida listas tipadas e operacoes:", resultado_arrays_semantica_gp)

logico exemplo_array_misto_gp = validar_sintaxe_gp("lista numero valores = [1, \"dois\"]")
logico resultado_array_misto_gp = verdadeiro
se (exemplo_array_misto_gp) { resultado_array_misto_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita lista heterogenea:", !resultado_array_misto_gp)

logico exemplo_adicionar_tipo_invalido_gp = validar_sintaxe_gp("lista numero valores = [1, 2]; lista numero novos = adicionar(valores, \"erro\")")
logico resultado_adicionar_tipo_invalido_gp = verdadeiro
se (exemplo_adicionar_tipo_invalido_gp) { resultado_adicionar_tipo_invalido_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita elemento de lista incorreto:", !resultado_adicionar_tipo_invalido_gp)

logico exemplo_indice_invalido_gp = validar_sintaxe_gp("lista texto nomes = [\"Ana\"]; texto nome = nomes[verdadeiro]")
logico resultado_indice_invalido_gp = verdadeiro
se (exemplo_indice_invalido_gp) { resultado_indice_invalido_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita indice nao numerico:", !resultado_indice_invalido_gp)

logico exemplo_atribuicao_lista_gp = validar_sintaxe_gp("lista numero valores = [1, 2]; valores[0] = 7")
logico resultado_atribuicao_lista_gp = falso
se (exemplo_atribuicao_lista_gp) { resultado_atribuicao_lista_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP valida atribuicao por indice:", resultado_atribuicao_lista_gp)

logico exemplo_atribuicao_lista_tipo_gp = validar_sintaxe_gp("lista numero valores = [1, 2]; valores[0] = \"texto\"")
logico resultado_atribuicao_lista_tipo_gp = verdadeiro
se (exemplo_atribuicao_lista_tipo_gp) { resultado_atribuicao_lista_tipo_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita atribuicao de tipo incorreto na lista:", !resultado_atribuicao_lista_tipo_gp)

logico exemplo_atribuicao_lista_indice_gp = validar_sintaxe_gp("lista numero valores = [1, 2]; valores[verdadeiro] = 7")
logico resultado_atribuicao_lista_indice_gp = verdadeiro
se (exemplo_atribuicao_lista_indice_gp) { resultado_atribuicao_lista_indice_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita indice invalido na atribuicao:", !resultado_atribuicao_lista_indice_gp)

logico exemplo_estrutura_semantica_gp = validar_sintaxe_gp("estrutura Pessoa { texto nome; numero idade; logico ativo; } Pessoa pessoa = Pessoa(\"Gabriel\", 29, verdadeiro); texto nome_pessoa = pessoa.nome; pessoa.idade = 30; mostrar(nome_pessoa, pessoa.idade)")
logico resultado_estrutura_semantica_gp = falso
se (exemplo_estrutura_semantica_gp) { resultado_estrutura_semantica_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP valida estruturas, construtores e campos:", resultado_estrutura_semantica_gp)

logico exemplo_campo_inexistente_gp = validar_sintaxe_gp("estrutura Pessoa { texto nome; } Pessoa pessoa = Pessoa(\"Ana\"); mostrar(pessoa.idade)")
logico resultado_campo_inexistente_gp = verdadeiro
se (exemplo_campo_inexistente_gp) { resultado_campo_inexistente_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita campo inexistente:", !resultado_campo_inexistente_gp)

logico exemplo_construtor_tipo_gp = validar_sintaxe_gp("estrutura Pessoa { texto nome; numero idade; } Pessoa pessoa = Pessoa(\"Ana\", \"vinte\")")
logico resultado_construtor_tipo_gp = verdadeiro
se (exemplo_construtor_tipo_gp) { resultado_construtor_tipo_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita tipo incorreto no construtor:", !resultado_construtor_tipo_gp)

logico exemplo_atribuicao_campo_tipo_gp = validar_sintaxe_gp("estrutura Pessoa { texto nome; numero idade; } Pessoa pessoa = Pessoa(\"Ana\", 20); pessoa.idade = \"vinte\"")
logico resultado_atribuicao_campo_tipo_gp = verdadeiro
se (exemplo_atribuicao_campo_tipo_gp) { resultado_atribuicao_campo_tipo_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita atribuicao de tipo incorreto em campo:", !resultado_atribuicao_campo_tipo_gp)

logico exemplo_construtor_quantidade_gp = validar_sintaxe_gp("estrutura Pessoa { texto nome; numero idade; } Pessoa pessoa = Pessoa(\"Ana\")")
logico resultado_construtor_quantidade_gp = verdadeiro
se (exemplo_construtor_quantidade_gp) { resultado_construtor_quantidade_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita quantidade incorreta no construtor:", !resultado_construtor_quantidade_gp)

logico exemplo_estrutura_aninhada_gp = validar_sintaxe_gp("estrutura Endereco { texto rua; numero cep; } estrutura Pessoa { texto nome; Endereco endereco; } Endereco endereco = Endereco(\"Centro\", 28900); Pessoa pessoa = Pessoa(\"Gabriel\", endereco); numero cep = pessoa.endereco.cep; pessoa.endereco.cep = 28901; mostrar(pessoa.nome, cep)")
logico resultado_estrutura_aninhada_gp = falso
se (exemplo_estrutura_aninhada_gp) { resultado_estrutura_aninhada_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP valida estruturas aninhadas:", resultado_estrutura_aninhada_gp)

logico exemplo_funcao_estrutura_gp = validar_sintaxe_gp("estrutura Pessoa { texto nome; } funcao obter_nome(Pessoa pessoa) -> texto { retornar pessoa.nome } Pessoa pessoa = Pessoa(\"Alice\"); texto nome = obter_nome(pessoa)")
logico resultado_funcao_estrutura_gp = falso
se (exemplo_funcao_estrutura_gp) { resultado_funcao_estrutura_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP valida estrutura em parametro e retorno:", resultado_funcao_estrutura_gp)

logico exemplo_parametro_tipo_desconhecido_gp = validar_sintaxe_gp("funcao receber(Desconhecido valor) -> numero { retornar 1 }")
logico resultado_parametro_tipo_desconhecido_gp = verdadeiro
se (exemplo_parametro_tipo_desconhecido_gp) { resultado_parametro_tipo_desconhecido_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita tipo desconhecido em parametro:", !resultado_parametro_tipo_desconhecido_gp)

logico exemplo_retorno_tipo_desconhecido_gp = validar_sintaxe_gp("funcao criar() -> Desconhecido { retornar 1 }")
logico resultado_retorno_tipo_desconhecido_gp = verdadeiro
se (exemplo_retorno_tipo_desconhecido_gp) { resultado_retorno_tipo_desconhecido_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita tipo desconhecido em retorno:", !resultado_retorno_tipo_desconhecido_gp)

logico exemplo_estrutura_duplicada_gp = validar_sintaxe_gp("estrutura Pessoa { texto nome; } estrutura Pessoa { numero idade; }")
logico resultado_estrutura_duplicada_gp = verdadeiro
se (exemplo_estrutura_duplicada_gp) { resultado_estrutura_duplicada_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita estrutura duplicada:", !resultado_estrutura_duplicada_gp)

logico exemplo_campo_duplicado_gp = validar_sintaxe_gp("estrutura Pessoa { texto nome; numero nome; }")
logico resultado_campo_duplicado_gp = verdadeiro
se (exemplo_campo_duplicado_gp) { resultado_campo_duplicado_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita campo duplicado:", !resultado_campo_duplicado_gp)

logico exemplo_tipo_campo_desconhecido_gp = validar_sintaxe_gp("estrutura Pessoa { Desconhecido objeto; }")
logico resultado_tipo_campo_desconhecido_gp = verdadeiro
se (exemplo_tipo_campo_desconhecido_gp) { resultado_tipo_campo_desconhecido_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita tipo de campo desconhecido:", !resultado_tipo_campo_desconhecido_gp)

logico exemplo_tipo_variavel_desconhecido_gp = validar_sintaxe_gp("Fantasma objeto = Fantasma()")
logico resultado_tipo_variavel_desconhecido_gp = verdadeiro
se (exemplo_tipo_variavel_desconhecido_gp) { resultado_tipo_variavel_desconhecido_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita tipo de variavel desconhecido:", !resultado_tipo_variavel_desconhecido_gp)

logico exemplo_retorno_todos_ramos_gp = validar_sintaxe_gp("funcao escolher(logico valor) -> numero { se (valor) { retornar 1 } senao { retornar 2 } }")
logico resultado_retorno_todos_ramos_gp = falso
se (exemplo_retorno_todos_ramos_gp) { resultado_retorno_todos_ramos_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP aceita retorno em todos os ramos:", resultado_retorno_todos_ramos_gp)

logico exemplo_retorno_faltante_gp = validar_sintaxe_gp("funcao escolher(logico valor) -> numero { se (valor) { retornar 1 } }")
logico resultado_retorno_faltante_gp = verdadeiro
se (exemplo_retorno_faltante_gp) { resultado_retorno_faltante_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP rejeita caminho sem retorno:", !resultado_retorno_faltante_gp)

logico exemplo_retorno_em_laco_gp = validar_sintaxe_gp("funcao tentar() -> numero { enquanto (verdadeiro) { retornar 1 } }")
logico resultado_retorno_em_laco_gp = verdadeiro
se (exemplo_retorno_em_laco_gp) { resultado_retorno_em_laco_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
mostrar("Semantica GP nao presume retorno dentro de laco:", !resultado_retorno_em_laco_gp)

logico exemplo_geracao_ir_gp = validar_sintaxe_gp("numero total = 10 + 2 * 3; mostrar(total, 42); total = total + 1")
logico resultado_geracao_ir_gp = falso
se (exemplo_geracao_ir_gp) { resultado_geracao_ir_gp = gerar_ir_ast_gp(raiz_ast_gp) }
mostrar("Gerador GP produz IR para declaracao, expressao, saida e atribuicao:", resultado_geracao_ir_gp)
se (resultado_geracao_ir_gp) {
    numero linha_ir_gp = 0
    enquanto (linha_ir_gp < tamanho(instrucoes_ir_gp)) {
        mostrar("IR:", serializar_registro_json_ir_gp(obter_registro_lista_ir_gp(instrucoes_ir_gp, linha_ir_gp)))
        linha_ir_gp = linha_ir_gp + 1
    }
}

logico exemplo_ir_controle_gp = validar_sintaxe_gp("numero x = 0; se (x < 3) { x = x + 1; } senao { x = 9; } enquanto (x < 5) { x = x + 1; } para (numero i = 0; i < 2; i = i + 1) { x = x + 1; }")
logico resultado_ir_controle_gp = falso
se (exemplo_ir_controle_gp) { resultado_ir_controle_gp = gerar_ir_ast_gp(raiz_ast_gp) }
mostrar("Gerador GP produz IR para se, senao, enquanto e para:", resultado_ir_controle_gp)
mostrar("Diagnostico IR controle:", diagnostico_ir_gp)
se (resultado_ir_controle_gp) {
    numero linha_ir_controle_gp = 0
    enquanto (linha_ir_controle_gp < tamanho(instrucoes_ir_gp)) {
        mostrar("IR-NUM:", serializar_registro_json_ir_gp(obter_registro_lista_ir_gp(instrucoes_ir_gp, linha_ir_controle_gp)))
        linha_ir_controle_gp = linha_ir_controle_gp + 1
    }
}

instrucoes_ir_gp = []
emitir_registro_ir_gp("GP-IR", "", "", "", 1, falso)
emitir_registro_ir_gp("JUMP", "ROTULO_AUSENTE", "", "", 0, falso)
logico teste_rotulo_ausente_ir_gp = !resolver_rotulos_ir_gp()
mostrar("Teste IR rejeita salto sem destino:", teste_rotulo_ausente_ir_gp)
mostrar("Diagnostico salto ausente:", diagnostico_ir_gp)
instrucoes_ir_gp = []
emitir_registro_ir_gp("GP-IR", "", "", "", 1, falso)
emitir_registro_ir_gp("LABEL", "DUPLICADO", "", "", 0, falso)
emitir_registro_ir_gp("LABEL", "DUPLICADO", "", "", 0, falso)
logico teste_rotulo_duplicado_ir_gp = !resolver_rotulos_ir_gp()
mostrar("Teste IR rejeita rotulo duplicado:", teste_rotulo_duplicado_ir_gp)
mostrar("Diagnostico rotulo duplicado:", diagnostico_ir_gp)
instrucoes_ir_gp = []
emitir_registro_ir_gp("GP-IR", "", "", "", 1, falso)
emitir_registro_ir_gp("LABEL", "", "", "", 0, falso)
logico teste_rotulo_vazio_ir_gp = !resolver_rotulos_ir_gp()
mostrar("Teste IR rejeita rotulo vazio:", teste_rotulo_vazio_ir_gp)
mostrar("Diagnostico rotulo vazio:", diagnostico_ir_gp)

instrucoes_ir_gp = []
emitir_registro_ir_gp("GP-IR", "", "", "", 1, falso)
emitir_registro_ir_gp("PRINT", "", "", "", -1, falso)
logico teste_ir_rejeita_operando_numerico_invalido_gp = !validar_registros_ir_gp()
mostrar("Validacao IR GP rejeita campo numerico invalido:", teste_ir_rejeita_operando_numerico_invalido_gp)
instrucoes_ir_gp = []
emitir_registro_ir_gp("GP-IR", "", "", "", 1, falso)
emitir_registro_ir_gp("OPCODE_DESCONHECIDO", "", "", "", 0, falso)
logico teste_ir_rejeita_opcode_desconhecido_gp = !validar_registros_ir_gp()
mostrar("Validacao IR GP rejeita opcode desconhecido:", teste_ir_rejeita_opcode_desconhecido_gp)
instrucoes_ir_gp = []
emitir_registro_ir_gp("GP-IR", "", "", "", 1, falso)
emitir_registro_ir_gp("CONST", "LOGICO", "talvez", "", 0, falso)
logico teste_ir_rejeita_constante_logica_invalida_gp = !validar_registros_ir_gp()
mostrar("Validacao IR GP rejeita constante logica invalida:", teste_ir_rejeita_constante_logica_invalida_gp)
instrucoes_ir_gp = []
emitir_registro_ir_gp("GP-IR", "", "", "", 1, falso)
emitir_registro_ir_gp("GP-IR", "", "", "", 1, falso)
logico teste_ir_rejeita_cabecalho_duplicado_gp = !validar_registros_ir_gp()
mostrar("Validacao IR GP rejeita cabecalho duplicado:", teste_ir_rejeita_cabecalho_duplicado_gp)

logico exemplo_ir_funcao_gp = validar_sintaxe_gp("funcao somar(numero a, numero b) -> numero { retornar a + b } numero total = somar(20, 22); mostrar(total)")
logico resultado_ir_funcao_gp = falso
se (exemplo_ir_funcao_gp) { resultado_ir_funcao_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
se (resultado_ir_funcao_gp) { resultado_ir_funcao_gp = gerar_ir_ast_gp(raiz_ast_gp) }
mostrar("Gerador GP produz secoes de funcao, parametros, CALL e RETURN:", resultado_ir_funcao_gp)
se (resultado_ir_funcao_gp) {
    numero linha_ir_funcao_gp = 0
    logico imprimir_corpo_funcao_ir_gp = falso
    InstrucaoIR_GP linha_funcao_emitida_ir = criar_registro_ir_gp("", "", "", "", 0, falso)
    enquanto (linha_ir_funcao_gp < tamanho(instrucoes_ir_gp)) {
        linha_funcao_emitida_ir = obter_registro_lista_ir_gp(instrucoes_ir_gp, linha_ir_funcao_gp)
        se (linha_funcao_emitida_ir.opcode == "FUNCTION" || linha_funcao_emitida_ir.opcode == "PARAM" || linha_funcao_emitida_ir.opcode == "CALL") {
            mostrar("IR-FN:", serializar_registro_json_ir_gp(linha_funcao_emitida_ir))
        } senao {
            se (linha_funcao_emitida_ir.opcode == "CODE_BEGIN") {
                imprimir_corpo_funcao_ir_gp = verdadeiro
                mostrar("IR-FN:", serializar_registro_json_ir_gp(linha_funcao_emitida_ir))
            } senao {
                se (linha_funcao_emitida_ir.opcode == "CODE_END") {
                    mostrar("IR-FN:", serializar_registro_json_ir_gp(linha_funcao_emitida_ir))
                    imprimir_corpo_funcao_ir_gp = falso
                } senao {
                    se (imprimir_corpo_funcao_ir_gp) { mostrar("IR-FN:", serializar_registro_json_ir_gp(linha_funcao_emitida_ir)) }
                }
            }
        }
        linha_ir_funcao_gp = linha_ir_funcao_gp + 1
    }
}

logico exemplo_ir_recursao_gp = validar_sintaxe_gp("funcao fatorial(numero n) -> numero { se (n <= 1) { retornar 1 } senao { retornar n * fatorial(n - 1) } } numero resultado_fatorial = fatorial(5); mostrar(resultado_fatorial)")
logico resultado_ir_recursao_gp = falso
se (exemplo_ir_recursao_gp) { resultado_ir_recursao_gp = analisar_semantica_ast_gp(raiz_ast_gp) }
se (resultado_ir_recursao_gp) { resultado_ir_recursao_gp = gerar_ir_ast_gp(raiz_ast_gp) }
mostrar("Gerador GP produz IR para funcao recursiva com fluxo de controle:", resultado_ir_recursao_gp)
se (resultado_ir_recursao_gp) {
    numero linha_ir_recursao_gp = 0
    logico imprimir_corpo_recursao_ir_gp = falso
    InstrucaoIR_GP linha_recursao_emitida_ir = criar_registro_ir_gp("", "", "", "", 0, falso)
    enquanto (linha_ir_recursao_gp < tamanho(instrucoes_ir_gp)) {
        linha_recursao_emitida_ir = obter_registro_lista_ir_gp(instrucoes_ir_gp, linha_ir_recursao_gp)
        se (linha_recursao_emitida_ir.opcode == "FUNCTION" || linha_recursao_emitida_ir.opcode == "PARAM" || linha_recursao_emitida_ir.opcode == "CALL") {
            mostrar("IR-REC:", serializar_registro_json_ir_gp(linha_recursao_emitida_ir))
        } senao {
            se (linha_recursao_emitida_ir.opcode == "CODE_BEGIN") {
                imprimir_corpo_recursao_ir_gp = verdadeiro
                mostrar("IR-REC:", serializar_registro_json_ir_gp(linha_recursao_emitida_ir))
            } senao {
                se (linha_recursao_emitida_ir.opcode == "CODE_END") {
                    mostrar("IR-REC:", serializar_registro_json_ir_gp(linha_recursao_emitida_ir))
                    imprimir_corpo_recursao_ir_gp = falso
                } senao {
                    se (imprimir_corpo_recursao_ir_gp) { mostrar("IR-REC:", serializar_registro_json_ir_gp(linha_recursao_emitida_ir)) }
                }
            }
        }
        linha_ir_recursao_gp = linha_ir_recursao_gp + 1
    }
}
