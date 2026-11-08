programa "GP Bytecode — primeiro executável"

funcao fatorial(numero n) -> numero {
    se (n <= 1) {
        retornar 1
    }
    retornar n * fatorial(n - 1)
}

numero total = 0
para (numero i = 1; i <= 5; i = i + 1) {
    total = total + i
}

mostrar("Soma:", total)
mostrar("Fatorial:", fatorial(5))
