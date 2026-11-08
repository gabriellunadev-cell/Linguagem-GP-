# GP Bytecode v2 — golden fixtures

The exact GP bytecode v2 snapshots are versioned as Base64 text files (`*.gbc.b64`).
This preserves the binary test inputs in Git even though the repository ignores generated `*.gbc` files.

Before the test suite runs, `make test` invokes `ferramentas/materializar_fixtures_bytecode.py`.
The script decodes each snapshot, verifies the SHA-256 and exact byte length against `SHA256SUMS`,
and only then writes the `.gbc` file used by the Python and native VM tests.

The binary files are exact golden inputs: tests do not regenerate them from `.gp` source at runtime.
The corresponding GP sources remain alongside the snapshots as provenance and review material.
A deliberate compiler or format change must explicitly review the GP source, snapshot, hash manifest
and expected VM output together.
