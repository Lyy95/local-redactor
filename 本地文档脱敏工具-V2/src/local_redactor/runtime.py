from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_OFFLINE_GUARD_INSTALLED = False


class ModelIntegrityError(RuntimeError):
    """Raised when a frozen build is missing or has altered model assets."""


def enforce_offline_runtime() -> None:
    """Disable common model download paths and Python-level network access.

    The application has no network feature.  The audit hook is deliberately
    process-wide and fail-closed; it cannot be removed later by a dependency.
    """

    global _OFFLINE_GUARD_INSTALLED
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("NO_PROXY", "*")
    os.environ.setdefault("no_proxy", "*")
    if _OFFLINE_GUARD_INSTALLED:
        return

    blocked_events = {
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

    def deny_network(event: str, _arguments: tuple[Any, ...]) -> None:
        if event in blocked_events:
            raise PermissionError("本工具禁止网络访问")

    sys.addaudithook(deny_network)
    _OFFLINE_GUARD_INSTALLED = True


def verify_bundled_models(*, require_manifest: bool | None = None) -> None:
    """Verify the build-time hashes of OCR, NER and face-candidate assets."""

    frozen = bool(getattr(sys, "frozen", False))
    strict = frozen if require_manifest is None else require_manifest
    runtime_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    manifest_path = runtime_root / "model-manifest.json"
    if not manifest_path.is_file():
        if strict:
            raise ModelIntegrityError("离线识别组件清单缺失，程序已停止")
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest["assets"]
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise ModelIntegrityError("离线识别组件清单无效，程序已停止") from exc
    if not isinstance(entries, list) or not entries:
        raise ModelIntegrityError("离线识别组件清单为空，程序已停止")

    package_roots: dict[str, Path] = {}
    for entry in entries:
        try:
            package_name = str(entry["package"])
            relative = Path(str(entry["relative"]))
            expected = str(entry["sha256"]).casefold()
        except (KeyError, TypeError) as exc:
            raise ModelIntegrityError("离线识别组件清单记录无效") from exc
        if relative.is_absolute() or ".." in relative.parts:
            raise ModelIntegrityError("离线识别组件清单路径无效")
        root = package_roots.get(package_name)
        if root is None:
            if frozen:
                root = (runtime_root / package_name).resolve(strict=False)
            else:
                try:
                    module = importlib.import_module(package_name)
                    module_file = Path(module.__file__ or "").resolve(strict=True)
                except (ImportError, OSError, RuntimeError) as exc:
                    raise ModelIntegrityError("离线识别组件缺失，程序已停止") from exc
                root = module_file.parent
            package_roots[package_name] = root
        asset = (root / relative).resolve(strict=False)
        try:
            asset.relative_to(root)
        except ValueError as exc:
            raise ModelIntegrityError("离线识别组件路径越界") from exc
        if not asset.is_file() or _sha256_file(asset) != expected:
            raise ModelIntegrityError("离线识别组件校验失败，程序已停止")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


class LazyRapidOcr:
    """Create the bundled RapidOCR engine only when an image is scanned."""

    def __init__(self) -> None:
        self._engine: Callable[[Any], Any] | None = None

    def __call__(self, image: Any) -> Any:
        if self._engine is None:
            import rapidocr
            from rapidocr import RapidOCR

            package_root = Path(rapidocr.__file__ or "").resolve(strict=True).parent
            model_root = package_root / "models"
            model_paths = {
                "Det.model_path": model_root / "PP-OCRv6_det_small.onnx",
                "Cls.model_path": (model_root / "ch_ppocr_mobile_v2.0_cls_mobile.onnx"),
                "Rec.model_path": model_root / "PP-OCRv6_rec_small.onnx",
            }
            if any(not path.is_file() for path in model_paths.values()):
                raise ModelIntegrityError("本地 OCR 模型缺失；禁止联网下载，图片识别未启动")
            params = {key: str(path) for key, path in model_paths.items()}
            params["Global.log_level"] = "error"
            self._engine = RapidOCR(params=params)
        return self._engine(image)


class OpenCvFaceCandidateDetector:
    """Conservative local face-candidate detector; never identifies a person."""

    def __init__(self) -> None:
        self._cv2: Any | None = None
        self._cascade: Any | None = None

    def detect(self, rgb_image: Any) -> list[tuple[int, int, int, int, float]]:
        cv2 = self._load()
        if cv2 is None or self._cascade is None:
            return []
        gray = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)
        boxes = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.12,
            minNeighbors=6,
            minSize=(28, 28),
        )
        return [(int(x), int(y), int(width), int(height), 0.62) for x, y, width, height in boxes]

    def _load(self) -> Any | None:
        if self._cv2 is not None:
            return self._cv2
        try:
            import cv2

            cv2_data = getattr(cv2, "data", None)
            cascade_root = getattr(cv2_data, "haarcascades", "")
            if not cascade_root:
                return None
            cascade_path = Path(str(cascade_root)) / "haarcascade_frontalface_default.xml"
            cascade_xml = cascade_path.read_text(encoding="utf-8")
            storage = cv2.FileStorage(
                cascade_xml,
                cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY,
            )
            if not storage.isOpened():
                return None
            cascade = cv2.CascadeClassifier()
            loaded = cascade.read(storage.getFirstTopLevelNode())
            storage.release()
            if not loaded:
                return None
            if cascade.empty():
                return None
            self._cv2 = cv2
            self._cascade = cascade
            return cv2
        except (AttributeError, ImportError, OSError):
            return None


def create_local_image_analyzer() -> Any:
    """Return an analyzer wired only to models already bundled on disk."""

    from .core import LocalImageAnalyzer, StructuredDetector

    return LocalImageAnalyzer(
        ocr_engine=LazyRapidOcr(),
        face_detector=OpenCvFaceCandidateDetector(),
        text_detectors=(StructuredDetector(),),
        auto_load_qr=True,
        enable_seal_heuristic=True,
    )


__all__ = [
    "LazyRapidOcr",
    "ModelIntegrityError",
    "OpenCvFaceCandidateDetector",
    "create_local_image_analyzer",
    "enforce_offline_runtime",
    "verify_bundled_models",
]
