// Biblioteca portável de capacidades GP Host ABI v1.
// Funciona nos runtimes Python e C sem habilitar interoperabilidade Python.

funcao raiz_quadrada(numero valor) -> numero {
    retornar host_chamar("gp.core.v1.math.sqrt", [valor])
}

funcao seno(numero valor) -> numero {
    retornar host_chamar("gp.core.v1.math.sin", [valor])
}

funcao cosseno(numero valor) -> numero {
    retornar host_chamar("gp.core.v1.math.cos", [valor])
}

funcao logaritmo(numero valor) -> numero {
    retornar host_chamar("gp.core.v1.math.log", [valor])
}

funcao fatorial(numero valor) -> numero {
    retornar host_chamar("gp.core.v1.math.factorial", [valor])
}

funcao mdc(numero primeiro, numero segundo) -> numero {
    retornar host_chamar("gp.core.v1.math.gcd", [primeiro, segundo])
}

funcao mmc(numero primeiro, numero segundo) -> numero {
    retornar host_chamar("gp.core.v1.math.lcm", [primeiro, segundo])
}

funcao hipotenusa(numero a, numero b) -> numero {
    retornar host_chamar("gp.core.v1.math.hypot", [a, b])
}

funcao media(lista numero valores) -> numero {
    retornar host_chamar("gp.core.v1.statistics.mean", [valores])
}

funcao mediana(lista numero valores) -> numero {
    retornar host_chamar("gp.core.v1.statistics.median", [valores])
}

funcao variancia_populacional(lista numero valores) -> numero {
    retornar host_chamar("gp.core.v1.statistics.pvariance", [valores])
}

funcao desvio_padrao(lista numero valores) -> numero {
    retornar host_chamar("gp.core.v1.statistics.stdev", [valores])
}
