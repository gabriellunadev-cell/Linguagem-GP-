lista numero valores = [2, 3]
numero primeiro = valores[0]
valores[1] = 7

lista numero expandidos = adicionar(valores, 4)
numero removido = remover(expandidos, 0)

mostrar(
    "Primeiro:", primeiro,
    "Original:", valores[1], tamanho(valores),
    "Copia:", expandidos[0], tamanho(expandidos),
    "Removido:", removido
)
