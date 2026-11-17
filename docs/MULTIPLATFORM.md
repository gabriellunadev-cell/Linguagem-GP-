# GP — matriz de alvos multiplataforma

Revalidado em 2026-11-15 na VPS Linux x86_64. O estado de cada alvo é classificado por execução observada, não apenas pela presença de um compilador ou binário. Os resultados Termux/Android e WASI históricos são identificados separadamente e não são confundidos com esta rodada.

## Matriz de validação — 2026-11-15

| Alvo | Estado nesta revisão | Evidência |
|---|---|---|
| Linux x86_64 | **Host validado** | GCC; suíte completa de 318 testes sem falhas ou skips; projeto modular executado pelo runtime C |
| Linux AArch64 | **Runtime verificado via QEMU** | ELF AArch64 reconstruído; mesmo bytecode modular executado por QEMU; saída Resultado do módulo: 42 |
| Windows x64 | **Runtime verificado no windows-latest** | VM C compilada e executada no runner Windows; o projeto modular gerou a saída Resultado do módulo: 42; artefato CI publicado |
| WebAssembly WASI preview1 | **Verificação histórica; não repetida nesta rodada** | Existe evidência anterior de execução com Wasmtime 50.0.1 em 2026-11-08; runtime e prefixo zlib WASI não disponíveis nesta VPS |
| Android arm64 | **Validação NDK/Bionic pendente nesta VPS** | Registros anteriores de validação Termux/ARM64 existem, mas esta rodada não usou Android NDK nem executou em dispositivo Android; QEMU Linux não comprova Bionic |

## Evidências desta execução

- GP_C_COMPILER=/usr/bin/gcc make validate CLANG=/usr/bin/gcc: exit code 0.
- Suíte: **318 testes aprovados em 137,463 s, zero falhas e zero skips**.
- Corpus diferencial: 6/6 em cada uma das seis dimensões (frontend_supported, direct_legacy_exact, frontend_bootstrap_exact, native_runner_exact, native_encoder_exact, python_c_semantic).
- Fuzz determinístico: 64 iterações, seed 0x47505632, 38 rejeições, 26 entradas aceitas/executadas e zero divergências.
- SHA-256 de todos os fixtures GP-IR: aprovados; git diff --check: aprovado.
- Linux x86_64 e Linux AArch64 via QEMU executaram o mesmo build/cross-target-module-smoke.gbc; ambos produziram Resultado do módulo: 42.
- Windows x64: runtime real aprovado no GitHub Actions em windows-latest. A VM compilou, o projeto modular executou e a saída foi Resultado do módulo: 42. Run 43780443476; artefato gp-windows-x64-runtime-validation (ID 14188530982).
- GP Programinha: npm run typecheck e npm run build aprovados; Vite transformou 1.578 módulos.
- Integração HTTP local: 7/7 verificações aprovadas (health, compile/run de projeto modular, traversal, import em arquivo único, preflight CORS do PWA e Host não autorizado).
- O WASI runtime foi ignorado por ausência do prefixo de zlib WASI e do binding/runtime Wasmtime nesta VPS. A validação Android NDK/Bionic também não foi executada.

### Hashes SHA-256

| Artefato | SHA-256 |
|---|---|
| build/gpvm-native (Linux x86_64) | 02e3a38567dea2c85830be44eac7d975eedfa95146013fe568e910e1c8adbdd5 |
| build/gpvm-native-linux-arm64 | 2e3ec0fc9b3a2a2d43dec71ec4663367595e524d8e5dff421f636aef8833065d |
| build/gpvm-native-windows.exe (cross-build local MinGW) | 459d75d42c1c75c5550a778af2177a6b4be6965b0304ad33aac7cdf9d7e80083 |
| build/cross-target-module-smoke.gbc | 0c9cb71ae5d473a29d0f5c9c9d5d3cd01c97623622a99968d546711f2f66c651 |

## Reproduzir Linux AArch64 e Windows x64

Com GCC cross, MinGW-w64 e QEMU instalados:

~~~bash
make cross-native
~~~

O alvo gera build/gpvm-native-linux-arm64 e build/gpvm-native-windows.exe, compila exemplos/modulos/aplicacao.gp pelo pipeline do projeto e executa a VM ARM64 via QEMU. O teste exige a saída Resultado do módulo: 42.

### Executar o Windows real por CI

O workflow .github/workflows/windows-native-runtime.yml prepara MinGW UCRT64, compila a VM no runner windows-latest, compila o mesmo projeto GP modular e executa a VM nativa Windows. O job deve terminar com GP_WINDOWS_X64_RUNTIME_OK e publica os artefatos de validação.

**Estado do workflow nesta revisão:** runtime Windows verificado com sucesso em windows-latest. A primeira execução encontrou a incompatibilidade de fsync de diretório; o código foi corrigido mantendo o fsync do arquivo e a substituição atômica. A segunda execução passou e publicou o artefato. Evidência: https://github.com/gabriellunadev-cell/Linguagem-GP-/actions/runs/43780443476 (job Windows x64 native VM execution; marcador GP_WINDOWS_X64_RUNTIME_OK).

## Reproduzir WASI preview1

Requisitos: Clang com alvo wasm32-wasi, sysroot wasi-libc, zlib estática compilada para wasm32-wasi e runtime Wasmtime com binding Python.

```bash
export GP_WASI_CC=clang-18
export GP_WASI_SYSROOT=/usr
export GP_WASI_ZLIB_PREFIX=/caminho/para/zlib-wasi
export GP_WASMTIME_PYTHON=/caminho/para/python-com-wasmtime
make wasi-native
```

O runner WASI recebe somente o workspace explicitamente pré-aberto e um caminho relativo de bytecode. WASI não fornece API padrão para RSS do processo; os contadores internos do alocador/GC permanecem ativos. Não confundir a evidência histórica Wasmtime de 2026-11-08 com um novo runtime test nesta sessão.

## Alvo Android arm64

Android usa Bionic e o sysroot do Android NDK. Linux AArch64 testado via QEMU não equivale a Android. A validação exige:
1. Android NDK e toolchain LLVM apropriados.
2. Compilação do runtime para `aarch64-linux-android`.
3. Testes de execução no dispositivo Android/Termux.
4. Verificação da integração de arquivos, sinais, I/O, memória e publicação atômica em Bionic.

O NDK exige aceitação explícita de termos de licença Android SDK. Essa aceitação não é automatizada nesta operação.

## Fronteiras e critérios

- POSIX/Linux: métricas de RSS por procfs e getrusage.
- Windows: APIs Win32 para memória, wrappers de I/O e publicação atômica por MoveFileEx.
- WASI: filesystem pré-aberto, escopo limitado ao workspace e RSS não disponível pela API padrão.
- GP-IR v1 e GGPC v2 são formatos independentes da arquitetura, mas a paridade do bytecode não substitui testes de runtime por alvo.

A GP permanece experimental 0.x. Não declarar estabilidade 1.0.0 enquanto os critérios de `docs/RELEASE_CRITERIA_1.0.0.md` não estiverem satisfeitos.
