// Demonstração do GP Host Capabilities ABI v1.
// Funciona nas VMs Python e C sem habilitar --python-interop.

usar "../biblioteca/host.gp" como nativo

numero raiz = nativo.raiz_quadrada(81)
numero divisor = nativo.mdc(18, 24)
numero multiplo = nativo.mmc(6, 8)
numero media = nativo.media([2, 4, 6, 8])
numero desvio = nativo.desvio_padrao([2, 4, 6, 8])
numero hipotenusa = nativo.hipotenusa(3, 4)

mostrar("Raiz:", raiz)
mostrar("MDC:", divisor)
mostrar("MMC:", multiplo)
mostrar("Média:", media)
mostrar("Desvio padrão:", desvio)
mostrar("Hipotenusa:", hipotenusa)
