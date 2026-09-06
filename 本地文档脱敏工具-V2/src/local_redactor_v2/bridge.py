from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QWidget

from local_redactor.models import Category, Finding, FindingStatus, Modality, ProcessingMode, TransformMethod
from local_redactor.service import LocalDesktopController
from local_redactor.ui.controller import ReviewBundle

_CATEGORY_LABELS = {
    Category.COMBINATION_RISK: "组合风险",
    Category.IMAGE_TEXT: "图片",
    Category.SEAL: "图片",
    Category.SIGNATURE: "图片",
    Category.QR_CODE: "图片",
    Category.PHOTO: "图片",
}


@dataclass(slots=True)
class TaskRecord:
    id: str
    source_path: Path
    mode: ProcessingMode
    controller: Any
    state: str = "source_ready"
    bundle: ReviewBundle | None = None
    error: dict[str, Any] | None = None
    artifacts: Any | None = None


class DesktopBridge(QObject):
    """JSON-only QWebChannel boundary for one-file DOCX tasks."""

    toast = Signal(str, str)

    def __init__(
        self,
        ui_root: Path,
        parent: QObject | None = None,
        *,
        controller_factory: Callable[[], Any] | None = None,
        file_selector: Callable[[], Path | None] | None = None,
        folder_selector: Callable[[], Path | None] | None = None,
        demo_mode: bool = False,
    ) -> None:
        super().__init__(parent)
        self._ui_root = ui_root.resolve()
        self._controller_factory = controller_factory or LocalDesktopController
        self._file_selector = file_selector
        self._folder_selector = folder_selector
        self._demo_mode = demo_mode
        self._sources: dict[str, Path] = {}
        self._tasks: dict[str, TaskRecord] = {}

    @Property(str, constant=True)
    def runtime_kind(self) -> str:
        return "native-windows-desktop"

    @Slot(result=str)
    def get_runtime_info(self) -> str:
        return self._json(
            {
                "ok": True,
                "runtime": "native-windows-desktop",
                "offline": True,
                "demoMode": self._demo_mode,
                "uiRoot": self._ui_root.name,
                "bridgeVersion": "0.2.0",
                "capabilities": ["single-docx", "review", "export", "history"],
            }
        )

    @Slot(result=str)
    def self_test(self) -> str:
        return self._json({"ok": self._ui_root.is_dir(), "network": "disabled"})

    @Slot(result=str)
    def choose_file(self) -> str:
        try:
            path = self._file_selector() if self._file_selector else self._native_choose_file()
            if path is None:
                return self._ok({"cancelled": True})
            path = Path(path).resolve()
            if path.suffix.casefold() != ".docx":
                return self._error("UNSUPPORTED_FILE", "Gate 2 当前只支持 DOCX 文件。")
            if not path.is_file():
                return self._error(
                    "FILE_NOT_FOUND", "所选文件已不存在，请重新选择。", True, "choose_file"
                )
            source_id = uuid4().hex
            self._sources[source_id] = path
            return self._ok(
                {
                    "cancelled": False,
                    "source": {
                        "id": source_id,
                        "kind": "file",
                        "native": True,
                        "name": path.name,
                        "type": "DOCX",
                        "size": self._display_size(path.stat().st_size),
                        "description": "本机 DOCX 文件 · 原文件只读",
                    },
                }
            )
        except OSError:
            return self._error(
                "FILE_ACCESS_ERROR", "无法读取所选文件，请检查权限后重试。", True, "choose_file"
            )

    @Slot(str, result=str)
    def create_task(self, payload_json: str) -> str:
        try:
            payload = self._object(payload_json)
            source = payload.get("source", payload)
            source_id = str(source.get("id", ""))
            path = self._sources.get(source_id)
            if path is None:
                return self._error(
                    "SOURCE_EXPIRED", "文件选择已失效，请重新选择。", True, "choose_file"
                )
            mode = (
                ProcessingMode.STRICT
                if payload.get("mode") == "strict"
                else ProcessingMode.BALANCED
            )
            task_id = uuid4().hex
            self._tasks[task_id] = TaskRecord(
                id=task_id,
                source_path=path,
                mode=mode,
                controller=self._controller_factory(),
            )
            return self._ok({"taskId": task_id, "snapshot": self._snapshot(self._tasks[task_id])})
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._error("INVALID_REQUEST", "无法创建任务，请重新选择文件。")

    @Slot(str, result=str)
    def start_scan(self, task_id: str) -> str:
        task = self._tasks.get(task_id)
        if task is None:
            return self._error("TASK_NOT_FOUND", "当前任务不存在。", True, "new_task")
        task.state = "checking"
        task.error = None
        try:
            task.bundle = task.controller.scan(task.source_path, task.mode)
            task.state = "blocked" if task.bundle.blocking_issues else "review_required"
            return self._ok(self._snapshot(task))
        except Exception as exc:
            task.state = "failed"
            task.error = self._error_object(
                "SCAN_FAILED", self._safe_message(exc, "自动检查失败。"), True, "retry_scan"
            )
            with suppress(Exception):
                task.controller.record_failed_task(task.source_path)
            return self._json({"ok": False, "error": task.error, "snapshot": self._snapshot(task)})

    @Slot(str, result=str)
    def get_task_snapshot(self, task_id: str) -> str:
        task = self._tasks.get(task_id)
        if task is None:
            return self._error("TASK_NOT_FOUND", "当前任务不存在。", True, "new_task")
        return self._ok(self._snapshot(task))

    @Slot(str, str, str, str, result=str)
    def resolve_finding(self, task_id: str, finding_id: str, action: str, value: str) -> str:
        task = self._tasks.get(task_id)
        if task is None or task.bundle is None:
            return self._error("TASK_NOT_READY", "任务尚未完成检查。")
        finding = next((item for item in task.bundle.findings if item.id == finding_id), None)
        if finding is None:
            return self._error("FINDING_NOT_FOUND", "该复核项已不存在。")
        try:
            if action == "keep":
                status, method, reason, replacement = (
                    FindingStatus.KEEP_FALSE_POSITIVE,
                    TransformMethod.KEEP,
                    "用户确认为可保留原文",
                    "",
                )
            elif action == "delete":
                status, method, reason, replacement = (
                    FindingStatus.REMOVE,
                    TransformMethod.REMOVE,
                    "",
                    "",
                )
            elif action in {"adopt", "edit"}:
                status, method, reason = FindingStatus.TRANSFORM, finding.suggested_method, ""
                replacement = value.strip() if action == "edit" else ""
            else:
                return self._error("INVALID_ACTION", "不支持该处理方式。")
            task.controller.resolve_finding(
                finding_id, status, method, ignore_reason=reason, replacement=replacement
            )
            task.state = (
                "ready_to_generate" if task.controller.is_review_complete() else "review_required"
            )
            return self._ok(self._snapshot(task))
        except Exception as exc:
            return self._error("RESOLVE_FAILED", self._safe_message(exc, "无法保存该处理决定。"))

    @Slot(str, str, result=str)
    def add_manual_finding(self, task_id: str, payload_json: str) -> str:
        task = self._tasks.get(task_id)
        if task is None or task.bundle is None:
            return self._error("TASK_NOT_READY", "任务尚未完成检查。")
        try:
            payload = self._object(payload_json)
            finding = task.controller.add_manual_finding(
                str(payload.get("original", "")), Category.OTHER, TransformMethod.ALIAS
            )
            suggestion = str(payload.get("suggestion", "")).strip()
            if suggestion:
                finding.replacement = suggestion
                finding.metadata["manual_replacement"] = suggestion
            task.state = "review_required"
            return self._ok(self._snapshot(task))
        except Exception as exc:
            return self._error("MANUAL_FINDING_FAILED", self._safe_message(exc, "无法添加该内容。"))

    @Slot(str, result=str)
    def preview_task(self, task_id: str) -> str:
        task = self._tasks.get(task_id)
        if task is None or task.bundle is None:
            return self._error("TASK_NOT_READY", "任务尚未完成检查。")
        preview = task.controller.preview()
        return self._ok(
            {
                "original": preview.original,
                "replacement": preview.replacement,
                "preservedSummary": preview.preserved_summary,
                "kind": getattr(preview, "kind", "docx"),
                "sheets": list(getattr(preview, "sheets", ())),
                "blocks": list(preview.blocks),
            }
        )

    @Slot(str, str, result=str)
    def export_task(self, task_id: str, output_root: str) -> str:
        task = self._tasks.get(task_id)
        if task is None or task.bundle is None:
            return self._error("TASK_NOT_READY", "任务尚未完成检查。")
        try:
            root = (
                Path(output_root).resolve() if output_root.strip() else self._native_choose_folder()
            )
            if root is None:
                return self._ok({"cancelled": True, "snapshot": self._snapshot(task)})
            task.state = "generating"
            task.artifacts = task.controller.export(root, "")
            task.state = "completed"
            return self._ok(
                {
                    "cancelled": False,
                    "artifacts": self._artifact_dto(task.artifacts),
                    "snapshot": self._snapshot(task),
                }
            )
        except Exception as exc:
            task.state = "failed"
            task.error = self._error_object(
                "EXPORT_FAILED", self._safe_message(exc, "生成文件失败。"), True, "review"
            )
            return self._json({"ok": False, "error": task.error, "snapshot": self._snapshot(task)})

    @Slot(result=str)
    def list_history(self) -> str:
        try:
            controller = (
                next(iter(self._tasks.values())).controller
                if self._tasks
                else self._controller_factory()
            )
            return self._ok(
                {"entries": [self._history_dto(item) for item in controller.history_entries()]}
            )
        except Exception as exc:
            return self._error(
                "HISTORY_FAILED", self._safe_message(exc, "无法读取本机历史。"), True
            )

    @Slot(str, result=str)
    def open_history(self, entry_id: str) -> str:
        result = json.loads(self.list_history())
        if not result.get("ok"):
            return self._json(result)
        entry = next((item for item in result["data"]["entries"] if item["id"] == entry_id), None)
        return (
            self._ok(entry) if entry else self._error("HISTORY_NOT_FOUND", "该历史记录已不存在。")
        )

    def _native_choose_file(self) -> Path | None:
        parent_object = self.parent()
        parent = parent_object if isinstance(parent_object, QWidget) else None
        selected, _ = QFileDialog.getOpenFileName(
            parent, "选择 DOCX 文件", "", "Word 文档 (*.docx)"
        )
        return Path(selected) if selected else None

    def _native_choose_folder(self) -> Path | None:
        if self._folder_selector:
            return self._folder_selector()
        parent_object = self.parent()
        parent = parent_object if isinstance(parent_object, QWidget) else None
        selected = QFileDialog.getExistingDirectory(parent, "选择脱敏结果保存位置")
        return Path(selected) if selected else None

    def _snapshot(self, task: TaskRecord) -> dict[str, Any]:
        bundle = task.bundle
        pending = (
            sum(item.status is FindingStatus.PENDING for item in bundle.findings) if bundle else 0
        )
        return {
            "taskId": task.id,
            "name": task.source_path.name,
            "type": "DOCX",
            "state": task.state,
            "currentStep": self._step_for(task.state),
            "pendingCount": pending,
            "findings": [self._finding_dto(item) for item in bundle.findings] if bundle else [],
            "resolutions": {
                item.id: self._decision(item)
                for item in bundle.findings
                if item.status is not FindingStatus.PENDING
            }
            if bundle
            else {},
            "preview": {
                "original": bundle.preview.original,
                "replacement": bundle.preview.replacement,
                "preservedSummary": bundle.preview.preserved_summary,
                "kind": getattr(bundle.preview, "kind", "docx"),
                "sheets": list(getattr(bundle.preview, "sheets", ())),
                "blocks": list(bundle.preview.blocks),
            }
            if bundle
            else None,
            "blockingIssues": list(bundle.blocking_issues) if bundle else [],
            "capabilityWarnings": list(bundle.capability_warnings) if bundle else [],
            "resultAvailable": task.artifacts is not None,
            "artifacts": self._artifact_dto(task.artifacts) if task.artifacts else None,
            "error": task.error,
        }

    @staticmethod
    def _finding_dto(finding: Finding) -> dict[str, Any]:
        location = finding.locations[0] if finding.locations else None
        suggestion = (
            str(finding.metadata.get("manual_replacement", "")) or finding.replacement or "[待替换]"
        )
        return {
            "id": finding.id,
            "category": _CATEGORY_LABELS.get(finding.category, "文字"),
            "categoryCode": finding.category.value,
            "original": finding.original,
            "suggestion": suggestion,
            "section": location.display if location else "文档内容",
            "location": location.display if location else "文档内容",
            "locations": [
                {
                    "blockId": item.block_id,
                    "start": item.start,
                    "end": item.end,
                    "display": item.display,
                    "part": item.part,
                    "imageId": item.image_id,
                }
                for item in finding.locations
            ],
            "occurrences": finding.occurrence_count,
            "severity": "强制执行" if finding.metadata.get("rule_mandatory") else "建议替换",
            "confidence": f"{round(finding.confidence * 100)}%",
            "source": finding.detector,
            "actionSet": (
                "image"
                if finding.modality is Modality.IMAGE
                or any(item.image_id for item in finding.locations)
                or finding.category
                in {
                    Category.IMAGE_TEXT,
                    Category.SEAL,
                    Category.SIGNATURE,
                    Category.QR_CODE,
                    Category.PHOTO,
                }
                else "hidden"
                if finding.modality is Modality.HIDDEN
                else "combined"
                if finding.category is Category.COMBINATION_RISK
                else "text"
            ),
            "rule": {
                "id": str(finding.metadata.get("rule_id", f"detector:{finding.detector}")),
                "source": "fixed" if finding.metadata.get("rule_id") else "builtin",
                "type": "本机规则" if finding.metadata.get("rule_id") else "系统识别",
                "name": str(finding.metadata.get("rule_name", finding.detector)),
                "mandatory": bool(finding.metadata.get("rule_mandatory")),
                "revision": "当前任务",
                "matchSummary": finding.context or "根据内容、位置和语义关系识别",
            },
            "basis": finding.preserved_semantics or finding.context or "本机离线识别候选项。",
            "detail": finding.context,
            "status": finding.status.value,
        }

    @staticmethod
    def _artifact_dto(artifacts: Any) -> dict[str, Any]:
        return {
            "resultRoot": str(artifacts.result_root),
            "ai": {"name": artifacts.ai_copy.name, "path": str(artifacts.ai_copy)},
            "mapping": {
                "name": artifacts.encrypted_mapping.name,
                "path": str(artifacts.encrypted_mapping),
            },
            "report": {"name": artifacts.report.name, "path": str(artifacts.report)},
            "hashes": dict(artifacts.hashes),
            "warnings": list(artifacts.warnings),
        }

    @staticmethod
    def _history_dto(entry: Any) -> dict[str, Any]:
        return {
            "id": entry.id,
            "name": entry.source_name,
            "type": str(entry.document_kind).upper(),
            "time": entry.created_at,
            "status": entry.status,
            "findingCount": entry.finding_count,
            "transformedCount": entry.transformed_count,
            "removedCount": entry.removed_count,
            "resultAvailable": entry.status == "completed" and bool(entry.result_path),
        }

    @staticmethod
    def _decision(finding: Finding) -> str:
        if finding.status is FindingStatus.REMOVE:
            return "delete"
        if finding.status is FindingStatus.KEEP_FALSE_POSITIVE:
            return "keep"
        return "edit" if finding.metadata.get("manual_replacement") else "adopt"

    @staticmethod
    def _step_for(state: str) -> int:
        if state in {"idle", "source_ready"}:
            return 1
        if state in {"checking", "blocked", "failed"}:
            return 2
        if state in {"review_required", "ready_to_generate"}:
            return 3
        return 4

    @staticmethod
    def _display_size(size: int) -> str:
        return (
            f"{max(1, round(size / 1024))} KB"
            if size < 1024 * 1024
            else f"{size / 1024 / 1024:.1f} MB"
        )

    @staticmethod
    def _object(payload_json: str) -> dict[str, Any]:
        value = json.loads(payload_json or "{}")
        if not isinstance(value, dict):
            raise TypeError("object required")
        return value

    @classmethod
    def _ok(cls, data: Any) -> str:
        return cls._json({"ok": True, "data": data})

    @classmethod
    def _error(
        cls, code: str, message: str, retryable: bool = False, return_action: str = ""
    ) -> str:
        return cls._json(
            {"ok": False, "error": cls._error_object(code, message, retryable, return_action)}
        )

    @staticmethod
    def _error_object(
        code: str, message: str, retryable: bool, return_action: str
    ) -> dict[str, Any]:
        return {
            "code": code,
            "message": message,
            "retryable": retryable,
            "returnAction": return_action,
        }

    @staticmethod
    def _safe_message(exc: Exception, fallback: str) -> str:
        message = str(exc).strip()
        return message if message and len(message) <= 240 else fallback

    @staticmethod
    def _json(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
