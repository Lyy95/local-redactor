from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

TEXT_SUFFIXES = {".css", ".html", ".js", ".jsx", ".json", ".md", ".py", ".toml"}
COMMAND_NAMES = (
    "uiBuild",
    "shellSelfTest",
    "unitTests",
    "staticCheck",
    "typeCheck",
    "step3VisualHarness",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check(checks: list[dict[str, object]], name: str, passed: bool, detail: str = "") -> None:
    checks.append({"name": name, "passed": passed, "detail": detail})


def _run(root: Path, name: str, command: str) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=root,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    return {
        "name": name,
        "command": command,
        "returnCode": completed.returncode,
        "tail": output[-5000:],
    }


def _has_unsafe_claim(corpus: str, term: str) -> bool:
    offset = 0
    while (index := corpus.find(term, offset)) >= 0:
        prefix = corpus[max(0, index - 24) : index]
        if not any(marker in prefix for marker in ("不代表", "不等于", "不得", "禁止")):
            return True
        offset = index + len(term)
    return False


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "harness" / "prototype-contract.json").read_text("utf-8"))
    baseline = json.loads((root / "harness" / "protected-baseline.json").read_text("utf-8"))
    checks: list[dict[str, object]] = []
    commands: list[dict[str, object]] = []

    _check(checks, "implementation phase confirmed", contract.get("phase") == "implementation")
    for relative in contract["requiredFiles"]:
        _check(checks, f"required file: {relative}", (root / relative).is_file())
    for relative in contract["baselineDocuments"]:
        path = root / relative
        exists = path.is_file()
        _check(checks, f"baseline document exists: {relative}", exists)
        if exists:
            text = path.read_text("utf-8")
            _check(
                checks,
                f"no unresolved template token: {relative}",
                "{{" not in text and "TODO:" not in text,
            )

    changed: list[str] = []
    missing: list[str] = []
    for relative, expected in baseline["protectedFiles"].items():
        path = (root / relative).resolve()
        if not path.is_file():
            missing.append(relative)
        elif _sha256(path) != expected:
            changed.append(relative)
    _check(
        checks,
        "protected sources unchanged",
        not changed and not missing,
        json.dumps({"changed": changed, "missing": missing}, ensure_ascii=False),
    )

    source_parts: list[str] = []
    document_parts: list[str] = []
    for relative in contract["sourceRoots"]:
        path = root / relative
        paths = [path] if path.is_file() else path.rglob("*") if path.is_dir() else []
        for candidate in paths:
            if candidate.is_file() and candidate.suffix.casefold() in TEXT_SUFFIXES:
                source_parts.append(candidate.read_text("utf-8", errors="ignore"))
    for relative in contract["baselineDocuments"]:
        path = root / relative
        if path.is_file():
            document_parts.append(path.read_text("utf-8", errors="ignore"))
    source_corpus = "\n".join(source_parts)
    corpus = "\n".join([source_corpus, *document_parts])
    _check(checks, "source corpus found", bool(corpus))
    for term in contract["requiredTerms"]:
        _check(checks, f"required term: {term}", term in corpus)
    for term in contract["forbiddenTerms"]:
        _check(checks, f"unsafe claim absent: {term}", not _has_unsafe_claim(source_corpus, term))

    from local_redactor_v2.bridge import DesktopBridge

    missing_methods = [
        method
        for method in contract["bridgeContract"]["methods"]
        if not hasattr(DesktopBridge, method)
    ]
    _check(
        checks, "bridge contract implemented", not missing_methods, "\u3001".join(missing_methods)
    )
    _check(checks, "browser journeys configured", bool(contract.get("browserJourneys")))
    _check(checks, "desktop journeys configured", bool(contract.get("desktopJourneys")))
    failed_gates = [
        f"{gate['id']}:{gate['name']}={gate['status']}"
        for gate in contract.get("hardAcceptanceGates", [])
        if gate.get("status") != "passed"
    ]
    _check(
        checks,
        "all P0 desktop acceptance gates passed",
        not failed_gates,
        "\u3001".join(failed_gates),
    )

    for name in COMMAND_NAMES:
        result = _run(root, name, contract["commands"][name])
        commands.append(result)
        _check(checks, f"command passed: {name}", result["returnCode"] == 0, str(result["tail"]))
    release = _run(root, "verifyRelease", contract["commands"]["verifyRelease"])
    commands.append(release)
    _check(checks, "release artifacts verified", release["returnCode"] == 0, str(release["tail"]))

    passed = all(bool(item["passed"]) for item in checks)
    result = {
        "passed": passed,
        "checkedAt": datetime.now(UTC).isoformat(),
        "phase": contract["phase"],
        "baselineStatus": contract["baselineStatus"],
        "checks": checks,
        "commands": commands,
    }
    output = root / "harness" / "prototype-results.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(
        json.dumps(
            {"passed": passed, "checks": len(checks), "results": str(output)}, ensure_ascii=False
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
