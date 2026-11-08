programa "GP arrays no bytecode"

lista numero valores = [10, 20, 30]
valores[1] = 25
adicionar(valores, 40)

numero total = 0
para (numero i = 0; i < tamanho(valores); i = i + 1) {
    total = total + valores[i]
}

mostrar("Quantidade:", tamanho(valores))
mostrar("Soma:", total)
mostrar("Removido:", remover(valores, 0))
mostrar("Primeiro agora:", valores[0])
