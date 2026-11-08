# GP Bytecode v2 — golden fixtures

These binary files are reference artifacts produced by the current bootstrap compiler.
They are deliberately committed as test inputs, not regenerated during test execution.

For each fixture, the regression suite:
1. verifies the binary envelope through the Python decoder;
2. executes the exact same .gbc bytes in GPVirtualMachine;
3. executes the exact same .gbc bytes in the native ARM64 VM;
4. compares stdout and exit status against the expected behavior recorded in the test.

The corresponding .gp source files are kept beside the binary artifacts to make the
fixture provenance reproducible. SHA256SUMS records the exact binary contents.
A deliberate compiler/format change must review and update the fixture corpus explicitly.
