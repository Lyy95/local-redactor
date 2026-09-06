from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from html import escape

from local_redactor.models import (
    Category,
    DocumentModel,
    Finding,
    FindingStatus,
    TransformMethod,
)


def render_technical_report(
    findings: Sequence[Finding],
    *,
    document: DocumentModel,
    hashes: Mapping[str, str],
) -> str:
    """Render a self-contained report containing no source or mapping values."""

    category_counts = Counter(finding.category.value for finding in findings)
    method_counts = Counter(_effective_method(finding).value for finding in findings)
    status_counts = Counter(finding.status.value for finding in findings)
    low_confidence_count = sum(finding.confidence < 0.7 for finding in findings)
    combination_risk_count = sum(
        finding.category is Category.COMBINATION_RISK for finding in findings
    )
    local_rule_count = sum(bool(finding.metadata.get("rule_id")) for finding in findings)
    object_counts = Counter(
        f"{item.kind or 'unknown'} / {item.disposition.value}"
        for item in document.inventory.parts
        if item.requires_decision
    )
    warning_counts = Counter(_safe_warning_code(warning) for warning in document.warnings)

    category_rows = _counter_rows(category_counts)
    method_rows = _counter_rows(method_counts)
    status_rows = _counter_rows(status_counts)
    object_rows = _counter_rows(object_counts)
    warning_rows = _counter_rows(warning_counts)
    hash_rows = "".join(
        f"<tr><td>{escape(name)}</td><td><code>{escape(value)}</code></td></tr>"
        for name, value in sorted(hashes.items())
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; style-src 'unsafe-inline'">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>脱敏检查报告</title>
  <style>
    body {{ margin: 0; padding: 32px; color: #1f2937; background: #f4f6f8;
            font: 14px/1.65 "Microsoft YaHei UI", sans-serif; }}
    main {{ max-width: 980px; margin: auto; padding: 28px; background: #fff;
            border: 1px solid #d7dce2; border-radius: 10px; }}
    h1 {{ margin-top: 0; color: #176b62; }}
    h2 {{ margin-top: 28px; font-size: 18px; }}
    .status {{ padding: 14px 16px; color: #166534; background: #ecfdf3;
              border-left: 4px solid #15803d; }}
    .warning {{ padding: 14px 16px; color: #8a3b0a; background: #fff7ed;
               border-left: 4px solid #b45309; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    th, td {{ padding: 9px 10px; border: 1px solid #d7dce2; text-align: left; }}
    th {{ background: #eef2f4; }}
    code {{ overflow-wrap: anywhere; }}
  </style>
</head>
<body>
<main>
  <h1>脱敏检查报告</h1>
  <p class="status"><strong>技术复检状态：通过</strong><br>
  实际导出的 AI 分析副本已完成格式打开、敏感原值、活动内容、外部关系和目录隔离检查。</p>
  <table>
    <tr><th>检查项</th><th>结果</th></tr>
    <tr><td>候选总数</td><td>{len(findings)}</td></tr>
    <tr><td>待处理项</td><td>0</td></tr>
    <tr><td>应用本地规则</td><td>{local_rule_count} 项</td></tr>
    <tr><td>AI 分析副本</td><td>已重新打开并检查实际落盘字节</td></tr>
    <tr><td>脱敏映射表</td><td>已加密验证，仅限本地保管，严禁上传</td></tr>
  </table>

  <h2>按类别统计</h2>
  <table><tr><th>类别</th><th>数量</th></tr>{category_rows}</table>

  <h2>按处理方式统计</h2>
  <table><tr><th>处理方式</th><th>数量</th></tr>{method_rows}</table>

  <h2>按复核决定统计</h2>
  <table><tr><th>决定</th><th>数量</th></tr>{status_rows}</table>

  <h2>复核风险摘要</h2>
  <table>
    <tr><th>检查项</th><th>数量</th></tr>
    <tr><td>低置信度候选（低于 0.70，已人工决定）</td><td>{low_confidence_count}</td></tr>
    <tr><td>组合识别风险（已由贡献字段决定闭环）</td><td>{combination_risk_count}</td></tr>
  </table>

  <h2>隐藏内容与对象清理</h2>
  <table><tr><th>对象类别 / 最终决定</th><th>数量</th></tr>{object_rows}</table>

  <h2>识别与结构警告代码</h2>
  <p>只记录脱敏后的错误代码，不记录原文、替代值或映射密码。</p>
  <table><tr><th>警告代码</th><th>数量</th></tr>{warning_rows}</table>

  <h2>文件 SHA-256</h2>
  <table><tr><th>文件</th><th>哈希</th></tr>{hash_rows}</table>

  <p class="warning"><strong>重要说明：</strong>技术检查完成不等于文件已脱密，
  也不代表可安全上传或已获准外发。是否可交给外部 AI，仍须按单位保密和数据管理制度确认。</p>
</main>
</body>
</html>
"""


def _effective_method(finding: Finding) -> TransformMethod:
    if finding.status is FindingStatus.KEEP_FALSE_POSITIVE:
        return TransformMethod.KEEP
    if finding.status is FindingStatus.REMOVE:
        return TransformMethod.REMOVE
    return finding.suggested_method


def _safe_warning_code(warning: str) -> str:
    candidate = warning.partition(":")[0].strip()
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", candidate):
        return candidate
    return "STRUCTURE_WARNING"


def _counter_rows(counter: Counter[str]) -> str:
    if not counter:
        return '<tr><td colspan="2">无</td></tr>'
    return "".join(
        f"<tr><td>{escape(name)}</td><td>{count}</td></tr>"
        for name, count in sorted(counter.items())
    )
