from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run_probe(probe: str) -> subprocess.CompletedProcess[str]:
    source_root = ROOT / "src"
    script = (
        "import socket, sys\n"
        f"sys.path.insert(0, {str(source_root)!r})\n"
        "try:\n"
        + "".join(f"    {line}\n" for line in probe.splitlines())
        + "except PermissionError:\n"
        + "    raise SystemExit(0)\n"
        + "except Exception as exc:\n"
        + "    raise SystemExit(f'unexpected:{type(exc).__name__}')\n"
        + "raise SystemExit('network operation was not blocked')\n"
    )
    return subprocess.run(
        [sys.executable, "-I", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )


@pytest.mark.parametrize(
    ("event", "probe"),
    [
        (
            "socket.__new__",
            "from local_redactor.runtime import enforce_offline_runtime\n"
            "enforce_offline_runtime()\n"
            "socket.socket()",
        ),
        (
            "socket.sendto",
            "probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n"
            "from local_redactor.runtime import enforce_offline_runtime\n"
            "enforce_offline_runtime()\n"
            "try:\n"
            "    probe.sendto(b'x', ('127.0.0.1', 9))\n"
            "finally:\n"
            "    probe.close()",
        ),
        (
            "socket.connect",
            "probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "from local_redactor.runtime import enforce_offline_runtime\n"
            "enforce_offline_runtime()\n"
            "try:\n"
            "    probe.connect(('127.0.0.1', 9))\n"
            "finally:\n"
            "    probe.close()",
        ),
        (
            "socket.getaddrinfo",
            "from local_redactor.runtime import enforce_offline_runtime\n"
            "enforce_offline_runtime()\n"
            "socket.getaddrinfo('localhost', 80)",
        ),
    ],
)
def test_runtime_blocks_network_in_isolated_process(
    event: str,
    probe: str,
) -> None:
    completed = _run_probe(probe)

    assert completed.returncode == 0, (
        f"{event} probe failed: stdout={completed.stdout!r}, stderr={completed.stderr!r}"
    )
