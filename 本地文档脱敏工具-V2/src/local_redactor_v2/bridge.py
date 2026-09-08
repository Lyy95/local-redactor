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
from local_redactor.rule_library import (
    ActionKind,
    MatchMode,
    RuleDefinition,
    RuleImportConflictError,
    RuleImportError,
    RuleKind,
    RuleLibraryError,
    allowing_untested_examples,
    dry_run_rule,
    import_rules,
    preview_import_rules,
    restore_default_rules as apply_restore_default_rules,
)
from local_redactor.service import LocalDesktopController
from local_redactor.ui.controller import ReviewBundle


_MATCH_UI = {
    MatchMode.EXACT: "等于",
    MatchMode.CONTAINS: "包含",
    MatchMode.REGEX: "符合格式",
    MatchMode.ANY_KEYWORD: "包含任一关键词",
    MatchMode.ALL_KEYWORDS: "同时包含全部关键词",
    MatchMode.MANUAL: "仅人工判断",
}
_MATCH_FROM_UI = {label: mode for mode, label in _MATCH_UI.items()}
_ACTION_UI = {
    ActionKind.FIXED_REPLACEMENT: "换成固定代号",
    ActionKind.MASK_MIDDLE: "保留首尾并加星号",
    ActionKind.SEQUENCE_CODE: "生成顺序代号",
    ActionKind.DELETE: "删除",
}
_ACTION_FROM_UI = {label: action for action, label in _ACTION_UI.items()}
_SCOPE_UI = {"text": "正文", "cell": "表格", "ocr": "图片 OCR", "metadata": "页眉页脚", "hidden": "页眉页脚"}
_SCOPE_FROM_UI = {"正文": "text", "表格": "cell", "页眉页脚": "text", "图片 OCR": "ocr"}

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
        self._import_files: dict[str, Path] = {}
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
                "capabilities": ["single-docx", "review", "export", "history", "rules"],
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

    def _rule_controller(self) -> Any:
        if self._tasks:
            return next(iter(self._tasks.values())).controller
        return self._controller_factory()

    @Slot(result=str)
    def list_rules(self) -> str:
        try:
            library = self._rule_controller().rule_store.load()
            return self._ok({"revision": library.revision, "rules": [_rule_dto(rule) for rule in library.rules]})
        except Exception as exc:
            return self._error("RULES_FAILED", self._safe_message(exc, "无法读取本机规则库。"), True)

    @Slot(str, result=str)
    def save_rule(self, payload_json: str) -> str:
        try:
            payload = json.loads(payload_json or "{}")
            store = self._rule_controller().rule_store
            library = store.load()
            rule = _rule_from_ui(payload)
            existing = next((item for item in library.rules if item.id == rule.id), None)
            library = library.update(rule) if existing is not None else library.add(rule)
            store.save(library)
            return self._ok({"revision": library.revision, "rules": [_rule_dto(item) for item in library.rules]})
        except RuleLibraryError as exc:
            return self._error("RULE_INVALID", str(exc), True)
        except Exception as exc:
            return self._error("RULE_SAVE_FAILED", self._safe_message(exc, "无法保存规则。"), True)

    @Slot(str, result=str)
    def delete_rule(self, rule_id: str) -> str:
        try:
            store = self._rule_controller().rule_store
            library = store.delete(rule_id) if hasattr(store, "delete") else None
            if library is None:
                library = store.load().delete(rule_id)
                store.save(library)
            return self._ok({"revision": library.revision, "rules": [_rule_dto(item) for item in library.rules]})
        except KeyError:
            return self._error("RULE_NOT_FOUND", "该规则已不存在。")
        except Exception as exc:
            return self._error("RULE_DELETE_FAILED", self._safe_message(exc, "无法删除规则。"), True)

    @Slot(result=str)
    def restore_default_rules(self) -> str:
        try:
            store = self._rule_controller().rule_store
            library = store.load()
            before_ids = {rule.id for rule in library.rules}
            restored = apply_restore_default_rules(library)
            added_count = sum(1 for rule in restored.rules if rule.id not in before_ids)
            if restored.revision != library.revision:
                store.save(restored)
            return self._ok(
                {
                    "revision": restored.revision,
                    "rules": [_rule_dto(item) for item in restored.rules],
                    "restoredCount": added_count,
                }
            )
        except Exception as exc:
            return self._error(
                "RULE_RESTORE_FAILED", self._safe_message(exc, "无法恢复默认预置。"), True
            )

    @Slot(str, bool, result=str)
    def set_rule_enabled(self, rule_id: str, enabled: bool) -> str:
        try:
            store = self._rule_controller().rule_store
            library = store.load().set_enabled(rule_id, bool(enabled))
            store.save(library)
            return self._ok({"revision": library.revision, "rules": [_rule_dto(item) for item in library.rules]})
        except KeyError:
            return self._error("RULE_NOT_FOUND", "该规则已不存在。")
        except Exception as exc:
            return self._error("RULE_SAVE_FAILED", self._safe_message(exc, "无法更新规则状态。"), True)

    @Slot(str, result=str)
    def test_rule(self, payload_json: str) -> str:
        """Dry-run one rule definition against sample text via the rule engine."""

        try:
            payload = self._object(payload_json)
            sample = str(payload.get("sample") or payload.get("text") or "")
            if not sample.strip():
                return self._error("RULE_TEST_EMPTY", "请先输入一段虚构样例。")
            rule_payload = payload.get("rule")
            if isinstance(rule_payload, dict):
                rule_data = rule_payload
            else:
                rule_data = {
                    key: value
                    for key, value in payload.items()
                    if key not in {"sample", "text", "appliesTo", "rule"}
                }
            with allowing_untested_examples():
                rule = _rule_from_ui(rule_data)
                applies_raw = str(payload.get("appliesTo") or "").strip()
                if applies_raw in _SCOPE_FROM_UI:
                    applies_to = _SCOPE_FROM_UI[applies_raw]
                elif applies_raw in {"text", "cell", "ocr", "metadata", "hidden"}:
                    applies_to = applies_raw
                else:
                    applies_to = next(
                        (scope for scope in rule.applies_to if scope != "all"),
                        "text",
                    )
                if applies_to == "hidden":
                    applies_to = "metadata" if "metadata" in rule.applies_to else "text"
                result = dry_run_rule(rule, sample, applies_to=applies_to)
            return self._ok(result)
        except RuleLibraryError as exc:
            return self._error("RULE_INVALID", str(exc), True)
        except Exception as exc:
            return self._error(
                "RULE_TEST_FAILED", self._safe_message(exc, "无法试跑规则。"), True
            )

    @Slot(result=str)
    def choose_rule_import_file(self) -> str:
        try:
            # Keep DOCX task picker separate from rule-sheet picker.
            path = self._native_choose_rule_import_file()
            if path is None:
                return self._ok({"cancelled": True})
            path = Path(path).resolve()
            suffix = path.suffix.casefold()
            if suffix not in {".csv", ".xlsx"}:
                return self._error("UNSUPPORTED_FILE", "规则导入只支持 .csv 和 .xlsx。")
            if not path.is_file():
                return self._error(
                    "FILE_NOT_FOUND", "所选文件已不存在，请重新选择。", True, "choose_rule_import_file"
                )
            import_id = uuid4().hex
            self._import_files[import_id] = path
            return self._ok(
                {
                    "cancelled": False,
                    "importId": import_id,
                    "name": path.name,
                    "type": suffix[1:].upper(),
                    "size": self._display_size(path.stat().st_size),
                }
            )
        except OSError:
            return self._error(
                "FILE_ACCESS_ERROR", "无法读取所选文件，请检查权限后重试。", True, "choose_rule_import_file"
            )

    def _native_choose_rule_import_file(self) -> Path | None:
        parent_object = self.parent()
        parent = parent_object if isinstance(parent_object, QWidget) else None
        selected, _ = QFileDialog.getOpenFileName(
            parent,
            "选择规则导入文件",
            "",
            "规则表 (*.csv *.xlsx);;CSV (*.csv);;Excel 工作簿 (*.xlsx)",
        )
        return Path(selected) if selected else None

    def _resolve_import_path(self, import_ref: str) -> Path | None:
        key = str(import_ref or "").strip()
        if not key:
            return None
        cached = self._import_files.get(key)
        if cached is not None:
            return cached
        candidate = Path(key)
        return candidate if candidate.is_file() else None

    @Slot(str, result=str)
    def preview_rule_import(self, import_id: str) -> str:
        try:
            path = self._resolve_import_path(import_id)
            if path is None:
                return self._error(
                    "IMPORT_EXPIRED", "导入文件选择已失效，请重新选择。", True, "choose_rule_import_file"
                )
            library = self._rule_controller().rule_store.load()
            preview = preview_import_rules(path, library)
            return self._ok(
                {
                    "importId": import_id if import_id in self._import_files else "",
                    "name": path.name,
                    "newCount": preview.new_count,
                    "duplicateCount": preview.duplicate_count,
                    "conflictCount": preview.conflict_count,
                    "newRules": [_rule_dto(item.imported) for item in preview.items if item.status == "new"],
                    "duplicates": [
                        {
                            "imported": _rule_dto(item.imported),
                            "existing": _rule_dto(item.existing) if item.existing else None,
                        }
                        for item in preview.items
                        if item.status == "duplicate"
                    ],
                    "conflicts": [
                        {
                            "imported": _rule_dto(item.imported),
                            "existing": _rule_dto(item.existing) if item.existing else None,
                        }
                        for item in preview.items
                        if item.status == "conflict"
                    ],
                }
            )
        except RuleImportError as exc:
            return self._error("RULE_IMPORT_INVALID", str(exc), True)
        except Exception as exc:
            return self._error(
                "RULE_IMPORT_FAILED", self._safe_message(exc, "无法预览规则导入。"), True
            )

    @Slot(str, str, result=str)
    def commit_rule_import(self, import_id: str, conflict_policy: str) -> str:
        try:
            path = self._resolve_import_path(import_id)
            if path is None:
                return self._error(
                    "IMPORT_EXPIRED", "导入文件选择已失效，请重新选择。", True, "choose_rule_import_file"
                )
            policy = str(conflict_policy or "error").strip()
            if policy not in {"error", "keep_existing", "use_imported"}:
                return self._error("INVALID_REQUEST", "导入冲突处理方式无效。")
            store = self._rule_controller().rule_store
            library = store.load()
            result = import_rules(path, library, conflict_policy=policy)  # type: ignore[arg-type]
            store.save(result.library)
            self._import_files.pop(import_id, None)
            return self._ok(
                {
                    "revision": result.library.revision,
                    "rules": [_rule_dto(item) for item in result.library.rules],
                    "addedCount": result.added_count,
                    "skippedDuplicateCount": result.skipped_duplicate_count,
                    "keptExistingCount": result.kept_existing_count,
                    "replacedExistingCount": result.replaced_existing_count,
                }
            )
        except RuleImportConflictError as exc:
            conflicts = [
                {
                    "imported": _rule_dto(imported),
                    "existing": _rule_dto(existing),
                }
                for existing, imported in exc.conflicts
            ]
            return self._json(
                {
                    "ok": False,
                    "error": self._error_object(
                        "RULE_IMPORT_CONFLICT",
                        str(exc),
                        True,
                        "resolve_import_conflict",
                    ),
                    "data": {"conflicts": conflicts, "conflictCount": len(conflicts)},
                }
            )
        except RuleImportError as exc:
            return self._error("RULE_IMPORT_INVALID", str(exc), True)
        except RuleLibraryError as exc:
            return self._error("RULE_INVALID", str(exc), True)
        except Exception as exc:
            return self._error(
                "RULE_IMPORT_FAILED", self._safe_message(exc, "无法完成规则导入。"), True
            )

    @Slot(str, result=str)
    def apply_rules_incrementally(self, task_id: str) -> str:
        """Re-apply the latest rule-library snapshot to an in-progress task.

        Uses the controller's cached document / OCR findings (no full re-scan).
        If the task has not been scanned yet, returns a soft skip so callers can
        keep the library mutation and wait for the next scan.
        """

        task = self._tasks.get(task_id)
        if task is None:
            return self._error("TASK_NOT_FOUND", "当前任务不存在。", True, "new_task")
        if task.bundle is None:
            snapshot = self._snapshot(task)
            snapshot.update(
                {
                    "applied": False,
                    "skipped": True,
                    "addedCount": 0,
                    "message": "当前任务尚未完成检查，新规则将在下次扫描时生效。",
                }
            )
            return self._ok(snapshot)
        try:
            added_count = int(task.controller.apply_rules_incrementally())
            snapshot = self._snapshot(task)
            snapshot.update(
                {
                    "applied": True,
                    "skipped": False,
                    "addedCount": added_count,
                    "message": (
                        f"已增量应用规则，新增 {added_count} 个候选项。"
                        if added_count
                        else "已按最新规则刷新当前复核结果。"
                    ),
                }
            )
            return self._ok(snapshot)
        except RuntimeError as exc:
            snapshot = self._snapshot(task)
            snapshot.update(
                {
                    "applied": False,
                    "skipped": True,
                    "addedCount": 0,
                    "message": self._safe_message(
                        exc, "当前没有正在复核的文档，新规则将在下次扫描时生效。"
                    ),
                }
            )
            return self._ok(snapshot)
        except ValueError as exc:
            return self._error("RULE_APPLY_FAILED", str(exc), True)
        except Exception as exc:
            return self._error(
                "RULE_APPLY_FAILED",
                self._safe_message(exc, "无法增量应用规则到当前任务。"),
                True,
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


def _rule_dto(rule: RuleDefinition) -> dict[str, Any]:
    scopes = [_SCOPE_UI.get(scope, scope) for scope in rule.applies_to if scope != "all"]
    if not scopes:
        scopes = ["正文", "表格"]
    unique_scopes = list(dict.fromkeys(scopes))
    return {
        "id": rule.id,
        "type": rule.kind.value,
        "name": rule.name,
        "matchMode": _MATCH_UI.get(rule.match_mode, "包含"),
        "pattern": "、".join(rule.patterns),
        "action": _ACTION_UI.get(rule.action, "换成固定代号"),
        "replacement": rule.replacement,
        "scope": "、".join(unique_scopes),
        "mandatory": rule.mandatory,
        "enabled": rule.enabled,
        "updatedAt": "本机已保存",
        "builtIn": False,
        "preset": rule.id.startswith("preset-"),
        "positiveExample": rule.positive_examples[0] if rule.positive_examples else "",
        "negativeExample": rule.negative_examples[0] if rule.negative_examples else "",
    }


def _rule_from_ui(payload: dict[str, Any]) -> RuleDefinition:
    kind = RuleKind.STANDARD if payload.get("type") == "standard" else RuleKind.FIXED
    match_label = str(payload.get("matchMode") or "包含")
    action_label = str(payload.get("action") or "换成固定代号")
    scopes = [
        _SCOPE_FROM_UI.get(item.strip(), "text")
        for item in str(payload.get("scope") or "正文、表格").replace(",", "、").split("、")
        if item.strip()
    ]
    patterns = tuple(
        part.strip()
        for part in str(payload.get("pattern") or "").replace(",", "、").split("、")
        if part.strip()
    )
    if action_label == "仅人工判断" or match_label == "仅人工判断":
        match_mode = MatchMode.MANUAL
        action = ActionKind.FIXED_REPLACEMENT
        patterns = ()
    elif action_label == "遮住敏感区域":
        match_mode = _MATCH_FROM_UI.get(match_label, MatchMode.CONTAINS)
        action = ActionKind.DELETE
    else:
        match_mode = _MATCH_FROM_UI.get(match_label, MatchMode.CONTAINS)
        action = _ACTION_FROM_UI.get(action_label, ActionKind.FIXED_REPLACEMENT)
    replacement = "" if action is ActionKind.DELETE else str(payload.get("replacement") or "")
    return RuleDefinition(
        id=str(payload.get("id") or uuid4().hex),
        name=str(payload.get("name") or "").strip(),
        kind=kind,
        match_mode=match_mode,
        patterns=patterns,
        action=action,
        replacement=replacement,
        mandatory=bool(payload.get("mandatory", kind is RuleKind.STANDARD)),
        enabled=bool(payload.get("enabled", True)),
        positive_examples=tuple(
            filter(None, [str(payload.get("positiveExample") or "").strip()])
        ),
        negative_examples=tuple(
            filter(None, [str(payload.get("negativeExample") or "").strip()])
        ),
        applies_to=tuple(dict.fromkeys(scopes)) or ("text", "cell"),
    )
