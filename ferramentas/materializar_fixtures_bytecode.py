"""Materialize verified GP bytecode v2 golden fixtures from Base64 snapshots."""
from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / 'tests' / 'fixtures' / 'bytecode_v2'
MANIFEST = FIXTURE_DIR / 'SHA256SUMS'


def main() -> int:
    if not MANIFEST.is_file():
        raise SystemExit('Manifest SHA256SUMS não encontrado.')
    count = 0
    for number, line in enumerate(MANIFEST.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        fields = line.split(maxsplit=2)
        if len(fields) != 3:
            raise SystemExit(f'Linha {number} inválida no manifest.')
        expected_hash, filename, size_text = fields
        if Path(filename).name != filename or not filename.endswith('.gbc'):
            raise SystemExit(f'Nome de fixture inválido na linha {number}.')
        try:
            expected_size = int(size_text.split()[0])
        except (ValueError, IndexError) as exc:
            raise SystemExit(f'Tamanho inválido na linha {number}.') from exc
        snapshot = FIXTURE_DIR / (filename + '.b64')
        if not snapshot.is_file():
            raise SystemExit(f'Snapshot ausente: {snapshot.name}')
        try:
            raw = base64.b64decode(snapshot.read_text(encoding='ascii').strip(), validate=True)
        except (UnicodeError, binascii.Error) as exc:
            raise SystemExit(f'Base64 inválido: {snapshot.name}') from exc
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != expected_hash:
            raise SystemExit(f'SHA-256 divergente em {filename}: {actual_hash}')
        if len(raw) != expected_size:
            raise SystemExit(f'Tamanho divergente em {filename}: {len(raw)} != {expected_size}')
        (FIXTURE_DIR / filename).write_bytes(raw)
        print(f'OK {filename}: {expected_size} bytes {actual_hash}')
        count += 1
    if count != 6:
        raise SystemExit(f'Esperados 6 fixtures; encontrados {count}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
