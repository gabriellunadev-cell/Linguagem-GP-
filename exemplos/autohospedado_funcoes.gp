funcao fatorial(numero n) -> numero {
    se (n <= 1) {
        retornar 1
    } senao {
        retornar n * fatorial(n - 1)
    }
}

numero resultado = fatorial(6)
mostrar("Fatorial calculado pelo frontend GP:", resultado)
