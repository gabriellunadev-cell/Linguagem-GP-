funcao ajustar(lista numero valores) -> numero {
    valores[0] = valores[0] + 5
    retornar valores[0] + tamanho(valores)
}

funcao ampliar(lista numero valores) -> lista numero {
    valores = adicionar(valores, 9)
    retornar valores
}

lista numero dados = [2, 4]
numero resultado = ajustar(dados)
lista numero expandidos = ampliar(dados)

mostrar("Resultado:", resultado)
mostrar("Lista alterada:", dados[0], dados[1])
mostrar("Lista retornada:", tamanho(expandidos), expandidos[2])
