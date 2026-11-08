// Lexer GP 0.2: retorna lexemas, preserva strings e reconhece operadores compostos.
funcao letra_gp(texto ch) -> logico {
    retornar (ch >= "a" && ch <= "z") || (ch >= "A" && ch <= "Z") || ch == "_"
}
funcao digito_gp(texto ch) -> logico {
    retornar ch >= "0" && ch <= "9"
}
funcao espaco_gp(texto ch) -> logico {
    retornar ch == " " || ch == "\n" || ch == "\t" || ch == "\r"
}
funcao lexer_gp(texto fonte) -> lista texto {
    lista texto saida = []
    numero i = 0
    numero n = tamanho(fonte)
    texto ch = ""
    texto proximo = ""
    texto lexema = ""
    logico comentario = falso
    logico decimal = falso
    logico escape = falso
    enquanto (i < n) {
        ch = fonte[i]
        se (espaco_gp(ch)) {
            i = i + 1
        } senao {
            comentario = falso
            se (ch == "/") {
                se (i + 1 < n) {
                    proximo = fonte[i + 1]
                    se (proximo == "/") {
                        comentario = verdadeiro
                    }
                }
            }
            se (comentario) {
                enquanto (i < n) {
                    se (fonte[i] == "\n") {
                        quebrar
                    }
                    i = i + 1
                }
            } senao {
                se (letra_gp(ch)) {
                    lexema = ch
                    i = i + 1
                    enquanto (i < n) {
                        se (letra_gp(fonte[i]) || digito_gp(fonte[i])) {
                            lexema = lexema + fonte[i]
                            i = i + 1
                        } senao {
                            quebrar
                        }
                    }
                    adicionar(saida, lexema)
                } senao {
                    se (digito_gp(ch)) {
                        lexema = ch
                        decimal = falso
                        i = i + 1
                        enquanto (i < n) {
                            se (digito_gp(fonte[i])) {
                                lexema = lexema + fonte[i]
                                i = i + 1
                            } senao {
                                se (fonte[i] == "." && !decimal) {
                                    decimal = verdadeiro
                                    lexema = lexema + "."
                                    i = i + 1
                                } senao {
                                    quebrar
                                }
                            }
                        }
                        adicionar(saida, lexema)
                    } senao {
                        se (ch == "\"") {
                            lexema = ch
                            escape = falso
                            i = i + 1
                            enquanto (i < n) {
                                ch = fonte[i]
                                lexema = lexema + ch
                                i = i + 1
                                se (escape) {
                                    escape = falso
                                } senao {
                                    se (ch == "\\") {
                                        escape = verdadeiro
                                    } senao {
                                        se (ch == "\"") {
                                            quebrar
                                        }
                                    }
                                }
                            }
                            adicionar(saida, lexema)
                        } senao {
                            lexema = ch
                            se (i + 1 < n) {
                                proximo = fonte[i + 1]
                                se ((ch == "=" && proximo == "=") || (ch == "!" && proximo == "=") || (ch == ">" && proximo == "=") || (ch == "<" && proximo == "=") || (ch == "-" && proximo == ">") || (ch == "&" && proximo == "&") || (ch == "|" && proximo == "|")) {
                                    lexema = lexema + proximo
                                    i = i + 1
                                }
                            }
                            adicionar(saida, lexema)
                            i = i + 1
                        }
                    }
                }
            }
        }
    }
    retornar saida
}
// Classificação lexical inicial: tipo:lexema.
funcao palavra_chave_gp(texto palavra) -> logico {
    retornar palavra == "programa" || palavra == "numero" || palavra == "texto" || palavra == "logico" || palavra == "lista" || palavra == "mostrar" || palavra == "se" || palavra == "senao" || palavra == "verdadeiro" || palavra == "falso" || palavra == "funcao" || palavra == "retornar" || palavra == "enquanto" || palavra == "para" || palavra == "estrutura" || palavra == "quebrar" || palavra == "continuar" || palavra == "usar" || palavra == "como"
}
funcao delimitador_gp(texto lexema) -> logico {
    retornar lexema == "(" || lexema == ")" || lexema == "{" || lexema == "}" || lexema == "[" || lexema == "]" || lexema == ";" || lexema == "," || lexema == "." || lexema == ":"
}
funcao operador_gp(texto lexema) -> logico {
    retornar lexema == "=" || lexema == "+" || lexema == "-" || lexema == "*" || lexema == "/" || lexema == "%" || lexema == "==" || lexema == "!=" || lexema == ">" || lexema == "<" || lexema == ">=" || lexema == "<=" || lexema == "->" || lexema == "&&" || lexema == "||" || lexema == "!"
}
funcao classificar_lexema_gp(texto lexema) -> texto {
    numero n = tamanho(lexema)
    se (n == 0) { retornar "INVALIDO" }
    se (delimitador_gp(lexema)) { retornar "DELIMITADOR" }
    se (lexema[0] == "\"") {
        se (n >= 2 && lexema[n - 1] == "\"") { retornar "TEXTO" }
        retornar "INVALIDO"
    }
    se (palavra_chave_gp(lexema)) { retornar "PALAVRA_CHAVE" }
    logico identificador = letra_gp(lexema[0])
    se (identificador) {
        numero i = 1
        enquanto (i < n) {
            se (!letra_gp(lexema[i]) && !digito_gp(lexema[i])) { retornar "INVALIDO" }
            i = i + 1
        }
        retornar "IDENTIFICADOR"
    }
    se (digito_gp(lexema[0])) {
        logico ponto = falso
        logico digito_depois_ponto = falso
        numero i = 1
        enquanto (i < n) {
            se (digito_gp(lexema[i])) {
                se (ponto) { digito_depois_ponto = verdadeiro }
            } senao {
                se (lexema[i] == "." && !ponto && i + 1 < n) { ponto = verdadeiro }
                senao { retornar "INVALIDO" }
            }
            i = i + 1
        }
        se (ponto && !digito_depois_ponto) { retornar "INVALIDO" }
        retornar "NUMERO"
    }
    se (operador_gp(lexema)) { retornar "OPERADOR" }
    retornar "INVALIDO"
}
funcao lexer_tipos_gp(texto fonte) -> lista texto {
    lista texto lexemas = lexer_gp(fonte)
    lista texto tokens = []
    numero i = 0
    texto item_token = ""
    enquanto (i < tamanho(lexemas)) {
        item_token = lexemas[i]
        adicionar(tokens, classificar_lexema_gp(item_token) + ":" + item_token)
        i = i + 1
    }
    retornar tokens
}
