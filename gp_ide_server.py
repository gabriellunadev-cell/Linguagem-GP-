#!/usr/bin/env python3
"""Loopback-only HTTP bridge between GP Programinha and the GP compiler."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

GP_ROOT = Path(__file__).resolve().parent
COMPILER = GP_ROOT / "gp_compile.py"
GP_VERSION = "0.8.52"
MAX_REQUEST_BYTES = 1_048_576
COMPILE_TIMEOUT_SECONDS = 20
RUN_TIMEOUT_SECONDS = 5
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
DEFAULT_ORIGINS = {
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:4174",
    "http://127.0.0.1:4174",
}
FILE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}\.gp$")


class BridgeError(ValueError):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def allowed_origins() -> set[str]:
    configured = os.environ.get("GP_BRIDGE_ORIGINS")
    if not configured:
        return set(DEFAULT_ORIGINS)
    return {item.strip() for item in configured.split(",") if item.strip()}


def validate_payload(payload: object, *, require_runtime: bool = False) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise BridgeError("O corpo precisa ser um objeto JSON.")
    source = payload.get("source")
    if not isinstance(source, str):
        raise BridgeError("O campo 'source' precisa ser texto.")
    try:
        source_bytes = source.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise BridgeError("A fonte contém texto Unicode inválido.") from exc
    if len(source_bytes) > MAX_REQUEST_BYTES:
        raise BridgeError("A fonte excede o limite de 1 MiB.", 413)
    if "\x00" in source:
        raise BridgeError("A fonte não pode conter bytes NUL.")

    file_name = payload.get("fileName", "principal.gp")
    if not isinstance(file_name, str) or not FILE_NAME_RE.fullmatch(file_name):
        raise BridgeError("O campo 'fileName' precisa ser um nome simples terminado em .gp.")

    if require_runtime and payload.get("runtime", "reference") != "reference":
        raise BridgeError("Apenas o runtime de referência está disponível nesta versão.")
    return source, file_name


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def execute_source(
    source: str,
    file_name: str,
    *,
    run: bool,
    timeout_seconds: float | None = None,
) -> dict[str, object]:
    """Compile one in-memory source file in a disposable workspace."""
    if not COMPILER.is_file():
        raise RuntimeError("O compilador GP não foi encontrado nesta instalação.")

    timeout = timeout_seconds if timeout_seconds is not None else (
        RUN_TIMEOUT_SECONDS if run else COMPILE_TIMEOUT_SECONDS
    )
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="gp-programinha-") as temp_dir:
        workspace = Path(temp_dir)
        source_path = workspace / file_name
        output_path = workspace / "programa.gbc"
        source_path.write_text(source, encoding="utf-8", newline="")
        command = [
            sys.executable,
            str(COMPILER),
            str(source_path),
            "--output",
            str(output_path),
        ]
        if run:
            command.extend(["--run", "--run-vm", "python", "--run-max-steps", "1000000"])

        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                env={**os.environ, "PYTHONPATH": str(GP_ROOT)},
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
            stdout = completed.stdout.replace(str(workspace), "<workspace>")
            stderr = completed.stderr.replace(str(workspace), "<workspace>")
            return {
                "ok": completed.returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "exitCode": completed.returncode,
                "durationMs": round((time.perf_counter() - started) * 1000),
                "diagnostics": [],
            }
        except subprocess.TimeoutExpired as exc:
            stdout = _timeout_text(exc.stdout).replace(str(workspace), "<workspace>")
            stderr = _timeout_text(exc.stderr).replace(str(workspace), "<workspace>")
            message = f"Tempo limite de {timeout:g} segundos excedido."
            stderr = (stderr + "\n" + message).strip()
            return {
                "ok": False,
                "stdout": stdout,
                "stderr": stderr,
                "exitCode": 124,
                "durationMs": round((time.perf_counter() - started) * 1000),
                "diagnostics": [],
            }


class GPBridgeHandler(BaseHTTPRequestHandler):
    server_version = "GPBridge/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        # Avoid logging source code or request bodies.
        sys.stderr.write("[gp-bridge] " + (fmt % args) + "\n")

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        origin = self.headers.get("Origin")
        if origin and origin in allowed_origins():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _host_is_local(self) -> bool:
        host_header = self.headers.get("Host", "")
        hostname = urlsplit("//" + host_header).hostname
        return hostname in ALLOWED_HOSTS

    def _origin_is_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        return origin is None or origin in allowed_origins()

    def do_OPTIONS(self) -> None:
        if not self._host_is_local() or not self._origin_is_allowed():
            self._send_json(403, {"ok": False, "error": "Origem ou host não autorizado."})
            return
        self.send_response(204)
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "300")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._host_is_local() or not self._origin_is_allowed():
            self._send_json(403, {"ok": False, "error": "Origem ou host não autorizado."})
            return
        if urlsplit(self.path).path != "/api/health":
            self._send_json(404, {"ok": False, "error": "Endpoint não encontrado."})
            return
        self._send_json(200, {
            "ok": True,
            "service": "gp-bridge",
            "version": GP_VERSION,
            "compilerAvailable": COMPILER.is_file(),
        })

    def do_POST(self) -> None:
        if not self._host_is_local() or not self._origin_is_allowed():
            self._send_json(403, {"ok": False, "error": "Origem ou host não autorizado."})
            return
        endpoint = urlsplit(self.path).path
        if endpoint not in {"/api/compile", "/api/run"}:
            self._send_json(404, {"ok": False, "error": "Endpoint não encontrado."})
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"ok": False, "error": "Envie application/json."})
            return
        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(400, {"ok": False, "error": "Content-Length inválido."})
            return
        if content_length < 0:
            self._send_json(400, {"ok": False, "error": "Content-Length inválido."})
            return
        if content_length > MAX_REQUEST_BYTES:
            self._send_json(413, {"ok": False, "error": "Corpo acima do limite de 1 MiB."})
            return
        raw = self.rfile.read(content_length)
        if len(raw) != content_length:
            self._send_json(400, {"ok": False, "error": "Corpo da requisição incompleto."})
            return
        try:
            payload = json.loads(raw.decode("utf-8", errors="strict"))
            source, file_name = validate_payload(payload, require_runtime=endpoint == "/api/run")
            result = execute_source(source, file_name, run=endpoint == "/api/run")
            self._send_json(200, result)
        except UnicodeDecodeError:
            self._send_json(400, {"ok": False, "error": "O corpo precisa usar UTF-8 válido."})
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "JSON inválido."})
        except BridgeError as exc:
            self._send_json(exc.status, {"ok": False, "error": str(exc)})
        except Exception:
            # Internal paths and stack traces must not cross the browser boundary.
            self._send_json(500, {"ok": False, "error": "Falha interna ao executar a operação GP."})


class LoopbackHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GP Bridge local para o GP Programinha")
    parser.add_argument("--host", choices=(DEFAULT_HOST,), default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port precisa estar entre 1 e 65535")
    server = LoopbackHTTPServer((args.host, args.port), GPBridgeHandler)
    print(f"GP Bridge {GP_VERSION} disponível em http://{args.host}:{args.port}")
    print("Apenas loopback; pressione Ctrl+C para encerrar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando GP Bridge...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
