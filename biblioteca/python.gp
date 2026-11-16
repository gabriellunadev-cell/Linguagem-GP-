// Wrappers para capacidades Python autorizadas.
// Use com o runtime híbrido habilitado (--python-interop).
// Os nomes públicos permanecem GP; py_chamar atravessa a fronteira do host.

funcao raiz_quadrada(numero valor) -> numero {
    retornar py_chamar("math.sqrt", [valor])
}

funcao seno(numero valor) -> numero {
    retornar py_chamar("math.sin", [valor])
}

funcao cosseno(numero valor) -> numero {
    retornar py_chamar("math.cos", [valor])
}

funcao logaritmo(numero valor) -> numero {
    retornar py_chamar("math.log", [valor])
}

funcao fatorial(numero valor) -> numero {
    retornar py_chamar("math.factorial", [valor])
}

funcao media(lista numero valores) -> numero {
    retornar py_chamar("statistics.mean", [valores])
}

funcao mediana(lista numero valores) -> numero {
    retornar py_chamar("statistics.median", [valores])
}

funcao desvio_padrao(lista numero valores) -> numero {
    retornar py_chamar("statistics.stdev", [valores])
}

funcao sha256(texto valor) -> texto {
    retornar py_chamar("hashlib.sha256", [valor])
}

funcao normalizar_nfc(texto valor) -> texto {
    retornar py_chamar("unicodedata.normalize", ["NFC", valor])
}
