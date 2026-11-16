// Funcoes matematicas puras da biblioteca padrao GP 0.8.x.
// Estas funcoes usam apenas operadores e controle de fluxo do nucleo.
funcao valor_absoluto(numero valor) -> numero {
    se (valor < 0) { retornar 0 - valor }
    retornar valor
}

funcao menor_numero(numero primeiro, numero segundo) -> numero {
    se (primeiro < segundo) { retornar primeiro }
    retornar segundo
}

funcao maior_numero(numero primeiro, numero segundo) -> numero {
    se (primeiro > segundo) { retornar primeiro }
    retornar segundo
}

funcao limitar_numero(numero valor, numero limite_inferior, numero limite_superior) -> numero {
    se (limite_inferior > limite_superior) { retornar limite_inferior }
    se (valor < limite_inferior) { retornar limite_inferior }
    se (valor > limite_superior) { retornar limite_superior }
    retornar valor
}
