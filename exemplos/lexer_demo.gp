usar "../linguagem/lexer_gp.gp" como lexer
lista texto resultado = lexer.lexer_gp("numero total = 42; // comentario\nmostrar(total + 1)")
mostrar("Quantidade:", tamanho(resultado))
mostrar(resultado)
lista texto operadores = lexer.lexer_gp("a==b && c!=d -> x>=2.5")
mostrar(operadores)

mostrar("Tokens tipados:", lexer.lexer_tipos_gp("numero total = 42; mostrar(total + 1)"))

mostrar("Classificacao:", lexer.classificar_lexema_gp("("), lexer.classificar_lexema_gp("=="), lexer.classificar_lexema_gp("12.5"), lexer.classificar_lexema_gp("12..5"), lexer.classificar_lexema_gp("@"))
