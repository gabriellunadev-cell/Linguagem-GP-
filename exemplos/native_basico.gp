funcao somar(numero a, numero b) -> numero {
    retornar a + b
}
numero total = 0
para (numero i = 1; i <= 5; i = i + 1) {
    total = total + i
}
mostrar("Soma da função:", somar(19, 23))
mostrar("Total do laço:", total)
