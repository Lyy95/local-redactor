from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from generate_model_manifest import build_manifest

FORBIDDEN_IMPORTS = {
    "boto3",
    "ftplib",
    "httpx",
    "paramiko",
    "requests",
    "urllib3",
    "websocket",
}
GUARANTEE_TERMS = ("已脱密", "可安全上传", "100%安全", "100% 安全")
NEGATING_TERMS = ("不等于", "不代表", "并非", "不是", "不得", "禁止")
REQUIRED_SOCKET_AUDIT_EVENTS = {
    "socket.__new__",
    "socket.bind",
    "socket.connect",
    "socket.getaddrinfo",
    "socket.gethostbyaddr",
    "socket.gethostbyname",
    "socket.gethostbyname_ex",
    "socket.getnameinfo",
    "socket.sendmsg",
    "socket.sendto",
}
FORBIDDEN_PERSISTENCE_TERMS = {
    "LocalRedactorInternalKey_2026",
    "task_history.json",
    ' / "decisions"',
}


def source_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", maxsplit=1)[0])
    return imports


def verify_offline_subprocesses(root: Path) -> None:
    """Exercise irreversible audit hooks in isolated child processes."""

    source_root = root / "src"
    prelude = f"import socket, sys\nsys.path.insert(0, {str(source_root)!r})\n"
    probes = {
        "socket.__new__": (
            "from local_redactor.runtime import enforce_offline_runtime\n"
            "enforce_offline_runtime()\n"
            "socket.socket()\n"
        ),
        "socket.sendto": (
            "probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n"
            "from local_redactor.runtime import enforce_offline_runtime\n"
            "enforce_offline_runtime()\n"
            "try:\n"
            "    probe.sendto(b'x', ('127.0.0.1', 9))\n"
            "finally:\n"
            "    probe.close()\n"
        ),
        "socket.connect": (
            "probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "from local_redactor.runtime import enforce_offline_runtime\n"
            "enforce_offline_runtime()\n"
            "try:\n"
            "    probe.connect(('127.0.0.1', 9))\n"
            "finally:\n"
            "    probe.close()\n"
        ),
        "socket.getaddrinfo": (
            "from local_redactor.runtime import enforce_offline_runtime\n"
            "enforce_offline_runtime()\n"
            "socket.getaddrinfo('localhost', 80)\n"
        ),
    }
    for event, probe in probes.items():
        script = (
            prelude
            + "try:\n"
            + "".join(f"    {line}\n" for line in probe.splitlines())
            + "except PermissionError:\n"
            + "    raise SystemExit(0)\n"
            + "except Exception as exc:\n"
            + "    raise SystemExit(f'unexpected:{type(exc).__name__}')\n"
            + "raise SystemExit('network operation was not blocked')\n"
        )
        completed = subprocess.run(
            [sys.executable, "-I", "-c", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(
                f"离线运行时未封堵 {event}（子进程结果：{detail or completed.returncode}）"
            )


def verify() -> None:
    root = Path(__file__).resolve().parents[1]
    source_files = sorted((root / "src").rglob("*.py"))
    imports = set().union(*(source_imports(path) for path in source_files))
    leaked_imports = sorted(imports & FORBIDDEN_IMPORTS)
    if leaked_imports:
        raise RuntimeError(f"业务源代码包含网络客户端依赖：{leaked_imports}")

    copy_files = source_files
    violations: list[str] = []
    for path in copy_files:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if any(term in line for term in GUARANTEE_TERMS) and not any(
                negation in line for negation in NEGATING_TERMS
            ):
                violations.append(f"{path.relative_to(root)}:{line_number}")
    if violations:
        raise RuntimeError("发现禁止的保证性文案：" + "；".join(violations))
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
    leaked_persistence = sorted(
        term for term in FORBIDDEN_PERSISTENCE_TERMS if term in source_text
    )
    if leaked_persistence:
        raise RuntimeError(
            "发现禁止的明文任务持久化或固定密钥实现："
            + "；".join(leaked_persistence)
        )

    manifest_path = build_manifest(root / "build" / "generated" / "model-manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("assets"):
        raise RuntimeError("离线模型清单为空")
    runtime_text = (root / "src" / "local_redactor" / "runtime.py").read_text(encoding="utf-8")
    missing_events = sorted(
        event for event in REQUIRED_SOCKET_AUDIT_EVENTS if event not in runtime_text
    )
    if "sys.addaudithook" not in runtime_text or missing_events:
        raise RuntimeError("离线运行时网络阻断未启用")
    verify_offline_subprocesses(root)
    mapping_text = (
        root / "src" / "local_redactor" / "artifacts" / "encryption.py"
    ).read_text(encoding="utf-8")
    if "create_local_mapping" not in mapping_text or "仅限本地保管，严禁上传" not in mapping_text:
        raise RuntimeError("本地映射表未配置独立生成和严禁上传警示")
    print(f"release verification passed: {len(source_files)} source files")
    print(f"model assets verified: {len(manifest['assets'])}")


if __name__ == "__main__":
    verify()
