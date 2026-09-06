import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  ChevronRight,
  Copy,
  Download,
  FileCheck2,
  FlaskConical,
  Info,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  Upload,
  X,
} from "lucide-react";

import "./rules.css";

const TAB_META = {
  fixed: { label: "固定替换", description: "把明确原词统一换成固定代号，适合单位、项目和约定称谓。" },
  standard: { label: "判断标准", description: "保存什么情况需要处理、如何处理，以及用于判断的正例和反例。" },
  builtin: { label: "系统识别说明", description: "查看程序自带的识别边界和默认处理说明；这些说明为只读。" },
};

const MATCH_OPTIONS = {
  fixed: ["等于", "包含"],
  standard: ["等于", "包含", "符合格式", "包含任一关键词", "同时包含全部关键词", "仅人工判断"],
};

const ACTION_OPTIONS = {
  fixed: ["换成固定代号"],
  standard: ["换成固定代号", "保留首尾并加星号", "生成顺序代号", "遮住敏感区域", "删除", "仅人工判断"],
};

const SCOPE_OPTIONS = ["正文", "表格", "页眉页脚", "图片 OCR"];

const RESTORE_RULES = [
  {
    id: "preset-ga-code",
    type: "fixed",
    name: "公安简称统一代号",
    matchMode: "包含",
    pattern: "公安",
    action: "换成固定代号",
    replacement: "GA",
    scope: "正文、表格、页眉页脚、图片 OCR",
    mandatory: true,
    enabled: true,
    updatedAt: "默认预置",
    builtIn: false,
    preset: true,
  },
  {
    id: "preset-phone-mask",
    type: "standard",
    name: "手机号结构化掩码",
    matchMode: "符合格式",
    pattern: "11 位手机号及联系方式上下文",
    action: "保留首尾并加星号",
    replacement: "138****5678",
    scope: "正文、表格、图片 OCR",
    mandatory: false,
    enabled: true,
    updatedAt: "默认预置",
    positiveExample: "联系人：13812345678",
    negativeExample: "设备编号：13812345678",
    builtIn: false,
    preset: true,
  },
];

const IMPORT_NEW_RULE = {
  id: "import-project-code",
  type: "fixed",
  name: "项目名称统一代号",
  matchMode: "包含",
  pattern: "星河协同建设项目",
  action: "换成固定代号",
  replacement: "项目 A",
  scope: "正文、表格",
  mandatory: false,
  enabled: true,
  updatedAt: "刚刚导入",
  builtIn: false,
};

function makeId(prefix = "rule") {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 7)}`;
}

function includesText(value, query) {
  return String(value ?? "").toLocaleLowerCase("zh-CN").includes(query);
}

function normalizeScopes(value) {
  const scopes = String(value ?? "")
    .split(/[、,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
  return scopes.length ? scopes : ["正文", "表格"];
}

function formatReturnTarget(returnContext) {
  if (!returnContext) return "当前复核项";
  if (returnContext.findingLabel) return returnContext.findingLabel;
  if (returnContext.section) return returnContext.section;
  const explicit = returnContext.itemNumber ?? returnContext.findingNumber;
  if (Number.isFinite(Number(explicit))) return `第 ${Number(explicit)} 项`;
  if (Number.isFinite(Number(returnContext.findingIndex))) {
    return `第 ${Number(returnContext.findingIndex) + 1} 项`;
  }
  return "当前复核项";
}

function createDraft(type = "fixed") {
  return {
    id: makeId(type),
    type,
    name: "",
    matchMode: type === "fixed" ? "等于" : "包含",
    pattern: "",
    action: type === "fixed" ? "换成固定代号" : "保留首尾并加星号",
    replacement: "",
    scope: ["正文", "表格"],
    mandatory: type === "standard",
    enabled: true,
    positiveExample: "",
    negativeExample: "",
    builtIn: false,
  };
}

function toDraft(rule) {
  return {
    ...rule,
    scope: normalizeScopes(rule.scope),
  };
}

function isReplacementRequired(draft) {
  return !["删除", "仅人工判断", "遮住敏感区域"].includes(draft.action);
}

function ruleActionSummary(rule) {
  if (rule.action === "删除") return "删除命中内容";
  if (rule.action === "仅人工判断") return "命中后逐项确认";
  if (rule.action === "遮住敏感区域") return "遮住敏感区域";
  return rule.replacement ? `${rule.action}：${rule.replacement}` : rule.action;
}

function ModalShell({ title, description, size = "medium", onClose, children, footer }) {
  return (
    <div className="rule-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className={`rule-modal rule-modal-${size}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="rule-modal-head">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button type="button" className="rule-icon-button" onClick={onClose} aria-label="关闭">
            <X size={20} aria-hidden="true" />
          </button>
        </header>
        {children && <div className="rule-modal-body">{children}</div>}
        {footer && <footer className="rule-modal-footer">{footer}</footer>}
      </section>
    </div>
  );
}

function SwitchButton({ enabled, onClick }) {
  return (
    <button
      type="button"
      className={`rule-switch ${enabled ? "on" : "off"}`}
      role="switch"
      aria-checked={enabled}
      onClick={onClick}
      title={enabled ? "点击停用" : "点击启用"}
    >
      <span aria-hidden="true" />
      <b>{enabled ? "启用" : "停用"}</b>
    </button>
  );
}

function RuleEditorDialog({ editor, returnTarget, onClose, onSave }) {
  const [draft, setDraft] = useState(() => toDraft(editor.rule));
  const [error, setError] = useState("");
  const [sample, setSample] = useState(editor.rule.positiveExample || editor.rule.pattern || "");
  const [sampleResult, setSampleResult] = useState(null);

  const update = (key, value) => {
    setDraft((current) => ({ ...current, [key]: value }));
    setError("");
    setSampleResult(null);
  };

  const changeType = (type) => {
    setDraft((current) => ({
      ...createDraft(type),
      id: current.id,
      name: current.name,
      enabled: current.enabled,
    }));
    setError("");
    setSampleResult(null);
  };

  const toggleScope = (scope) => {
    setDraft((current) => {
      const scopes = current.scope.includes(scope)
        ? current.scope.filter((item) => item !== scope)
        : [...current.scope, scope];
      return { ...current, scope: scopes };
    });
    setError("");
  };

  const testDraft = () => {
    if (!sample.trim()) {
      setSampleResult({ ok: false, text: "请先输入一段虚构样例。" });
      return;
    }
    const matched = sampleMatchesRule(sample, draft);
    setSampleResult(
      matched
        ? { ok: true, text: `已命中。原型结果：${simulateTreatment(sample, draft)}` }
        : { ok: false, text: "未命中，请检查判断方式、条件和样例。" },
    );
  };

  const submit = () => {
    if (!draft.name.trim()) {
      setError("请填写规则名称。此名称会显示在复核项的“引用规则”中。");
      return;
    }
    if (!draft.pattern.trim()) {
      setError("请填写完整原词、关键词或判断条件。");
      return;
    }
    if (!draft.scope.length) {
      setError("请至少选择一个适用范围。");
      return;
    }
    if (isReplacementRequired(draft) && !draft.replacement.trim()) {
      setError("当前处理方式需要填写固定代号、前缀或示例结果。");
      return;
    }
    if (draft.type === "standard" && !draft.positiveExample.trim()) {
      setError("判断标准至少需要一个正确示例。");
      return;
    }
    onSave({
      ...draft,
      name: draft.name.trim(),
      pattern: draft.pattern.trim(),
      replacement: draft.replacement.trim(),
      scope: draft.scope.join("、"),
      positiveExample: draft.positiveExample?.trim() || "",
      negativeExample: draft.negativeExample?.trim() || "",
      updatedAt: "刚刚",
      builtIn: false,
    }, editor.returnAfterSave);
  };

  const title = editor.mode === "add" ? "新增规则" : editor.mode === "copy" ? "复制规则" : "编辑规则";
  const primaryLabel = editor.returnAfterSave
    ? `保存并应用到当前任务后返回${returnTarget}`
    : "保存规则";

  return (
    <ModalShell
      title={title}
      description="规则和样例均为本原型中的虚构本机数据，不会读取或上传文件。"
      size="large"
      onClose={onClose}
      footer={(
        <>
          <button type="button" className="rule-button secondary" onClick={onClose}>取消</button>
          <button type="button" className="rule-button primary" onClick={submit}>
            <Check size={17} aria-hidden="true" />{primaryLabel}
          </button>
        </>
      )}
    >
      <div className="rule-type-choice" aria-label="规则类型">
        <button type="button" className={draft.type === "fixed" ? "active" : ""} onClick={() => changeType("fixed")}>固定替换</button>
        <button type="button" className={draft.type === "standard" ? "active" : ""} onClick={() => changeType("standard")}>判断标准</button>
      </div>

      <div className="rule-form-grid">
        <label className="rule-field span-2">
          <span>规则名称 <em>必填</em></span>
          <input value={draft.name} onChange={(event) => update("name", event.target.value)} placeholder="例如：合作单位统一别名" autoFocus />
        </label>
        <label className="rule-field">
          <span>判断方式 <em>必填</em></span>
          <select value={draft.matchMode} onChange={(event) => update("matchMode", event.target.value)}>
            {MATCH_OPTIONS[draft.type].map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <label className="rule-field">
          <span>处理方式 <em>必填</em></span>
          <select value={draft.action} onChange={(event) => update("action", event.target.value)}>
            {ACTION_OPTIONS[draft.type].map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <label className="rule-field span-2">
          <span>{draft.type === "fixed" ? "完整原词" : "关键词、格式或判断条件"} <em>必填</em></span>
          <input value={draft.pattern} onChange={(event) => update("pattern", event.target.value)} placeholder={draft.type === "fixed" ? "输入需要统一替换的完整原词" : "多个关键词可使用顿号分隔"} />
        </label>
        {isReplacementRequired(draft) && (
          <label className="rule-field span-2">
            <span>固定代号、前缀或示例结果 <em>必填</em></span>
            <input value={draft.replacement} onChange={(event) => update("replacement", event.target.value)} placeholder="例如：GA、项目 A、138****5678" />
          </label>
        )}
        <fieldset className="rule-field span-2 scope-field">
          <legend>适用范围 <em>至少选择一项</em></legend>
          <div>
            {SCOPE_OPTIONS.map((scope) => (
              <label key={scope} className={draft.scope.includes(scope) ? "checked" : ""}>
                <input type="checkbox" checked={draft.scope.includes(scope)} onChange={() => toggleScope(scope)} />
                <span>{scope}</span>
              </label>
            ))}
          </div>
        </fieldset>
        {draft.type === "standard" && (
          <>
            <label className="rule-field">
              <span>正确示例 <em>必填</em></span>
              <input value={draft.positiveExample || ""} onChange={(event) => update("positiveExample", event.target.value)} placeholder="会命中的虚构示例" />
            </label>
            <label className="rule-field">
              <span>反例 <small>选填</small></span>
              <input value={draft.negativeExample || ""} onChange={(event) => update("negativeExample", event.target.value)} placeholder="不应命中的虚构示例" />
            </label>
          </>
        )}
      </div>

      <div className="rule-check-row">
        <label>
          <input type="checkbox" checked={draft.mandatory} onChange={(event) => update("mandatory", event.target.checked)} />
          <span><b>强制执行</b><small>命中后不能保留原文</small></span>
        </label>
        <label>
          <input type="checkbox" checked={draft.enabled} onChange={(event) => update("enabled", event.target.checked)} />
          <span><b>立即启用</b><small>停用后规则仍保留</small></span>
        </label>
      </div>

      <section className="editor-test-panel" aria-label="保存前测试规则">
        <div>
          <FlaskConical size={18} aria-hidden="true" />
          <span><b>保存前测试</b><small>只对当前虚构样例测试，不读取文件。</small></span>
        </div>
        <div className="editor-test-input">
          <input value={sample} onChange={(event) => setSample(event.target.value)} placeholder="输入一段虚构样例" />
          <button type="button" className="rule-button secondary" onClick={testDraft}>测试</button>
        </div>
        {sampleResult && <p className={sampleResult.ok ? "success" : "warning"}>{sampleResult.text}</p>}
      </section>
      {error && <p className="rule-form-error" role="alert"><AlertTriangle size={17} aria-hidden="true" />{error}</p>}
    </ModalShell>
  );
}

function sampleMatchesRule(sample, rule) {
  const value = sample.toLocaleLowerCase("zh-CN");
  const pattern = String(rule.pattern || "").toLocaleLowerCase("zh-CN");
  if (!pattern) return false;
  if (rule.matchMode === "等于") return value.trim() === pattern.trim();
  if (rule.matchMode === "包含") return value.includes(pattern);
  const tokens = pattern.split(/[、,，\s]+/).filter((item) => item.length > 1);
  if (rule.matchMode === "同时包含全部关键词") return tokens.length > 0 && tokens.every((item) => value.includes(item));
  if (rule.matchMode === "包含任一关键词") return tokens.some((item) => value.includes(item));
  if (rule.matchMode === "仅人工判断") return true;
  return value.includes(pattern) || tokens.some((item) => value.includes(item));
}

function simulateTreatment(sample, rule) {
  if (rule.action === "删除") return "（已删除）";
  if (rule.action === "仅人工判断") return "需要逐项确认";
  if (rule.action === "遮住敏感区域") return "已标记为遮挡处理";
  if (rule.action === "生成顺序代号") return `${rule.replacement || "代号"}01`;
  if (rule.action === "保留首尾并加星号") {
    const value = sample.trim();
    if (value.length <= 2) return "**";
    return `${value.slice(0, 1)}${"*".repeat(Math.min(6, value.length - 2))}${value.slice(-1)}`;
  }
  return rule.replacement || "（请填写处理结果）";
}

function TestRuleDialog({ rule, onClose }) {
  const [sample, setSample] = useState(rule.positiveExample || rule.pattern || "");
  const [result, setResult] = useState(null);

  const run = () => {
    if (!sample.trim()) {
      setResult({ ok: false, text: "请先输入一段虚构样例。" });
      return;
    }
    const matched = sampleMatchesRule(sample, rule);
    setResult(matched
      ? { ok: true, text: `已命中“${rule.name}”。处理后：${simulateTreatment(sample, rule)}` }
      : { ok: false, text: `未命中“${rule.name}”，当前样例不会应用此规则。` });
  };

  return (
    <ModalShell
      title="测试规则"
      description="测试只发生在当前窗口的虚构样例中，不读取文件，也不会改变当前任务。"
      onClose={onClose}
      footer={<button type="button" className="rule-button primary" onClick={onClose}>完成</button>}
    >
      <div className="test-rule-summary">
        <span className="rule-kind-chip">{TAB_META[rule.type].label}</span>
        <h3>{rule.name}</h3>
        <p>{rule.matchMode}“{rule.pattern}” → {ruleActionSummary(rule)}</p>
      </div>
      <label className="rule-field">
        <span>虚构测试内容</span>
        <textarea value={sample} onChange={(event) => { setSample(event.target.value); setResult(null); }} rows={4} />
      </label>
      <button type="button" className="rule-button test-wide" onClick={run}><FlaskConical size={17} aria-hidden="true" />运行测试</button>
      {result && (
        <div className={`test-result ${result.ok ? "success" : "warning"}`} role="status">
          {result.ok ? <Check size={19} aria-hidden="true" /> : <Info size={19} aria-hidden="true" />}
          <span>{result.text}</span>
        </div>
      )}
    </ModalShell>
  );
}

function ImportDialog({ conflictRule, stage, onStage, onCancel, onChoose }) {
  const importedConflict = conflictRule
    ? {
        ...conflictRule,
        replacement: conflictRule.replacement === "星河合作机构" ? "辰光合作机构" : "星河合作机构",
        updatedAt: "刚刚导入",
      }
    : null;

  if (stage === "conflict" && importedConflict) {
    return (
      <ModalShell
        title="发现 1 条冲突规则"
        description="同一原词对应了不同结果。请选择本次导入方式，系统不会静默覆盖。"
        size="large"
        onClose={onCancel}
      >
        <div className="conflict-compare">
          <section>
            <span>本机现有规则</span>
            <h3>{conflictRule.name}</h3>
            <dl><div><dt>原词</dt><dd>{conflictRule.pattern}</dd></div><div><dt>替换为</dt><dd>{conflictRule.replacement}</dd></div></dl>
          </section>
          <ChevronRight size={22} aria-hidden="true" />
          <section className="imported">
            <span>导入文件中的规则</span>
            <h3>{importedConflict.name}</h3>
            <dl><div><dt>原词</dt><dd>{importedConflict.pattern}</dd></div><div><dt>替换为</dt><dd>{importedConflict.replacement}</dd></div></dl>
          </section>
        </div>
        <div className="conflict-actions">
          <button type="button" className="rule-button secondary" onClick={() => onChoose("keep", importedConflict)}>保留现有规则</button>
          <button type="button" className="rule-button primary" onClick={() => onChoose("import", importedConflict)}>采用导入规则</button>
          <button type="button" className="rule-button text" onClick={onCancel}>取消导入</button>
        </div>
      </ModalShell>
    );
  }

  return (
    <ModalShell
      title="导入规则预览"
      description="原型使用两条虚构规则展示导入结果，不读取真实 CSV 或 XLSX。"
      size="large"
      onClose={onCancel}
      footer={(
        <>
          <button type="button" className="rule-button secondary" onClick={onCancel}>取消导入</button>
          <button type="button" className="rule-button primary" onClick={() => conflictRule ? onStage("conflict") : onChoose("keep", null)}>
            继续导入
          </button>
        </>
      )}
    >
      <div className="prototype-file-row"><FileCheck2 size={22} aria-hidden="true" /><span><b>虚构规则导入表.xlsx</b><small>本机虚构文件 · 2 条规则</small></span></div>
      <div className="import-preview-list">
        {conflictRule && (
          <article className="conflict"><AlertTriangle size={18} aria-hidden="true" /><div><h3>{conflictRule.name}</h3><p>原词“{conflictRule.pattern}”已存在，但替换结果不同。</p></div><span>需要选择</span></article>
        )}
        <article><Check size={18} aria-hidden="true" /><div><h3>{IMPORT_NEW_RULE.name}</h3><p>{IMPORT_NEW_RULE.pattern} → {IMPORT_NEW_RULE.replacement}</p></div><span>可新增</span></article>
      </div>
      <p className="import-note"><Info size={16} aria-hidden="true" />完整重复项会自动跳过；冲突项必须由你选择。</p>
    </ModalShell>
  );
}

function ConfirmDialog({ title, body, confirmLabel, danger = false, onCancel, onConfirm }) {
  return (
    <ModalShell
      title={title}
      description={body}
      size="small"
      onClose={onCancel}
      footer={(
        <>
          <button type="button" className="rule-button secondary" onClick={onCancel}>取消</button>
          <button type="button" className={`rule-button ${danger ? "danger" : "primary"}`} onClick={onConfirm}>{confirmLabel}</button>
        </>
      )}
    />
  );
}

function RuleRow({ rule, focused, setRowRef, onEdit, onCopy, onToggle, onDelete, onTest }) {
  return (
    <article ref={setRowRef} className={`rule-row ${focused ? "focused" : ""}`} data-rule-id={rule.id} tabIndex={focused ? -1 : undefined}>
      <div className="rule-main-cell">
        <div className="rule-name-line">
          <h3>{rule.name}</h3>
          {rule.preset && <span className="preset-chip">默认预置</span>}
          {rule.mandatory && <span className="mandatory-chip"><ShieldCheck size={13} aria-hidden="true" />强制执行</span>}
        </div>
        <p>{rule.matchMode}“{rule.pattern}”</p>
        <small>适用：{rule.scope}</small>
      </div>
      <div className="rule-result-cell">
        <span>{ruleActionSummary(rule)}</span>
        <small>更新于 {rule.updatedAt || "刚刚"}</small>
      </div>
      <div className="rule-status-cell">
        <SwitchButton enabled={Boolean(rule.enabled)} onClick={() => onToggle(rule)} />
      </div>
      <div className="rule-actions-cell" aria-label={`${rule.name} 操作`}>
        <button type="button" onClick={() => onTest(rule)}><FlaskConical size={16} aria-hidden="true" />测试</button>
        <button type="button" onClick={() => onEdit(rule)}><Pencil size={16} aria-hidden="true" />编辑</button>
        <button type="button" onClick={() => onCopy(rule)}><Copy size={16} aria-hidden="true" />复制</button>
        <button type="button" className="danger-text" onClick={() => onDelete(rule)}><Trash2 size={16} aria-hidden="true" />删除</button>
      </div>
    </article>
  );
}

function BuiltinRow({ item, focused, setRowRef }) {
  return (
    <article ref={setRowRef} className={`builtin-row ${focused ? "focused" : ""}`} data-rule-id={item.id} tabIndex={focused ? -1 : undefined}>
      <div><span className="builtin-icon"><ShieldCheck size={18} aria-hidden="true" /></span><h3>{item.category}</h3></div>
      <dl>
        <div><dt>识别标准</dt><dd>{item.standard}</dd></div>
        <div><dt>默认处理</dt><dd>{item.treatment}</dd></div>
        <div><dt>示例</dt><dd>{item.example}</dd></div>
      </dl>
      <span className="read-only-label">只读说明</span>
    </article>
  );
}

export default function RuleLibraryView({
  rules = [],
  setRules,
  builtinExplanations = [],
  focusRuleId = "",
  returnContext = null,
  onReturnToReview,
  onIncrementalApply,
  onToast,
  activeTab: controlledActiveTab,
  onActiveTabChange,
  addRequest = 0,
  showTabs = true,
}) {
  const [internalActiveTab, setInternalActiveTab] = useState("fixed");
  const activeTab = controlledActiveTab ?? internalActiveTab;
  const setActiveTab = (nextTab) => {
    setInternalActiveTab(nextTab);
    onActiveTabChange?.(nextTab);
  };
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [editor, setEditor] = useState(null);
  const [testRule, setTestRule] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [restoreOpen, setRestoreOpen] = useState(false);
  const [importStage, setImportStage] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const rowRefs = useRef(new Map());
  const returnTarget = formatReturnTarget(returnContext);

  const focusedRule = useMemo(
    () => rules.find((rule) => rule.id === focusRuleId) || builtinExplanations.find((item) => item.id === focusRuleId) || null,
    [builtinExplanations, focusRuleId, rules],
  );

  useEffect(() => {
    if (!focusRuleId) return undefined;
    const editable = rules.find((rule) => rule.id === focusRuleId);
    setActiveTab(editable?.type || "builtin");
    setQuery("");
    setStatusFilter("all");
    const timer = window.setTimeout(() => {
      const row = rowRefs.current.get(focusRuleId);
      row?.scrollIntoView({ block: "center", behavior: "smooth" });
      row?.focus?.();
    }, 80);
    return () => window.clearTimeout(timer);
  }, [focusRuleId, rules]);

  useEffect(() => {
    const modalOpen = editor || testRule || deleteTarget || restoreOpen || importStage;
    if (!modalOpen) return undefined;
    const onKeyDown = (event) => {
      if (event.key !== "Escape") return;
      setEditor(null);
      setTestRule(null);
      setDeleteTarget(null);
      setRestoreOpen(false);
      setImportStage(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteTarget, editor, importStage, restoreOpen, testRule]);

  const notify = (message, tone = "success") => {
    setFeedback(null);
    onToast?.(message, tone);
  };

  const commitRules = (nextRules) => {
    if (typeof setRules === "function") setRules(nextRules);
  };

  const filteredRules = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
    return rules.filter((rule) => {
      if (rule.type !== activeTab) return false;
      if (statusFilter === "enabled" && !rule.enabled) return false;
      if (statusFilter === "disabled" && rule.enabled) return false;
      if (!normalizedQuery) return true;
      return [rule.name, rule.pattern, rule.replacement, rule.scope, rule.action]
        .some((value) => includesText(value, normalizedQuery));
    });
  }, [activeTab, query, rules, statusFilter]);

  const filteredBuiltin = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
    if (!normalizedQuery) return builtinExplanations;
    return builtinExplanations.filter((item) => [item.category, item.standard, item.treatment, item.example]
      .some((value) => includesText(value, normalizedQuery)));
  }, [builtinExplanations, query]);

  const openAdd = (returnAfterSave = false) => {
    const type = activeTab === "standard" ? "standard" : "fixed";
    setEditor({ mode: "add", rule: createDraft(type), returnAfterSave });
  };

  useEffect(() => {
    if (!addRequest) return;
    openAdd(false);
  }, [addRequest]);

  const openEdit = (rule, returnAfterSave = Boolean(returnContext && rule.id === focusRuleId)) => {
    setEditor({ mode: "edit", rule, returnAfterSave });
  };

  const openCopy = (rule) => {
    setEditor({
      mode: "copy",
      returnAfterSave: false,
      rule: { ...rule, id: makeId(rule.type), name: `${rule.name}（副本）`, preset: false, updatedAt: "刚刚" },
    });
  };

  const saveRule = async (savedRule, returnAfterSave) => {
    const exists = rules.some((rule) => rule.id === savedRule.id);
    const nextRules = exists
      ? rules.map((rule) => rule.id === savedRule.id ? savedRule : rule)
      : [savedRule, ...rules];
    commitRules(nextRules);
    setEditor(null);
    notify(exists ? `“${savedRule.name}”已更新。` : `“${savedRule.name}”已新增并启用。`);
    if (!returnAfterSave) return;
    try {
      await onIncrementalApply?.(savedRule, returnContext);
      notify(`规则已保存并增量应用，正在返回${returnTarget}。`);
      onReturnToReview?.(returnContext, savedRule);
    } catch (error) {
      notify(error?.message || "规则已保存，但增量应用未完成，请检查后重试。", "error");
    }
  };

  const toggleRule = (rule) => {
    const enabled = !rule.enabled;
    commitRules(rules.map((item) => item.id === rule.id ? { ...item, enabled, updatedAt: "刚刚" } : item));
    notify(`“${rule.name}”已${enabled ? "启用" : "停用"}。`);
  };

  const deleteRule = () => {
    if (!deleteTarget) return;
    commitRules(rules.filter((rule) => rule.id !== deleteTarget.id));
    notify(`“${deleteTarget.name}”已从本机原型规则库删除。`);
    setDeleteTarget(null);
  };

  const restoreDefaults = () => {
    const ids = new Set(rules.map((rule) => rule.id));
    const missing = RESTORE_RULES.filter((rule) => !ids.has(rule.id));
    commitRules([...missing, ...rules]);
    notify(missing.length ? `已恢复 ${missing.length} 条缺失的默认预置。` : "默认预置均已存在，没有覆盖我的规则。");
    setRestoreOpen(false);
  };

  const conflictRule = rules.find((rule) => rule.type === "fixed") || null;

  const finishImport = (policy, importedConflict) => {
    const newAlreadyExists = rules.some((rule) => rule.id === IMPORT_NEW_RULE.id);
    let nextRules = [...rules];
    let replaced = 0;
    if (policy === "import" && conflictRule && importedConflict) {
      nextRules = nextRules.map((rule) => rule.id === conflictRule.id ? { ...importedConflict, id: conflictRule.id } : rule);
      replaced = 1;
    }
    if (!newAlreadyExists) nextRules = [IMPORT_NEW_RULE, ...nextRules];
    commitRules(nextRules);
    setImportStage(null);
    notify(`导入完成：新增 ${newAlreadyExists ? 0 : 1} 条，${policy === "keep" ? "保留现有 1 条" : `采用导入 ${replaced} 条`}。`);
  };

  const applyAndReturn = async () => {
    const editable = rules.find((rule) => rule.id === focusRuleId);
    if (editable) {
      openEdit(editable, true);
      return;
    }
    if (!focusRuleId) {
      openAdd(true);
      return;
    }
    try {
      await onIncrementalApply?.(focusedRule, returnContext);
      notify(`系统识别说明为只读，已返回${returnTarget}。`);
      onReturnToReview?.(returnContext, focusedRule);
    } catch (error) {
      notify(error?.message || "暂时无法返回当前复核项。", "error");
    }
  };

  const isBuiltin = activeTab === "builtin";
  const counts = {
    fixed: rules.filter((rule) => rule.type === "fixed").length,
    standard: rules.filter((rule) => rule.type === "standard").length,
    builtin: builtinExplanations.length,
  };

  return (
    <section className="rule-library-view" aria-label="规则库">
      <header className="rule-page-header">
        <div>
          <p className="rule-eyebrow"><ShieldCheck size={17} aria-hidden="true" />本机规则库原型</p>
          <h1>规则库</h1>
          <p>固定替换用于明确词语，判断标准用于长期复用的识别和处理方式。</p>
        </div>
        <div className="rule-local-chip"><ShieldCheck size={17} aria-hidden="true" />虚构本机数据 · 不上传</div>
      </header>

      {returnContext && (
        <div className="rule-return-banner" role="status">
          <div>
            <ArrowLeft size={20} aria-hidden="true" />
            <span>
              <b>从当前任务的{returnTarget}查看规则</b>
              <small>{focusedRule ? `已定位“${focusedRule.name || focusedRule.category}”` : "保存后会增量应用，并保留其他已完成决定。"}</small>
            </span>
          </div>
          <div>
            <button type="button" className="rule-button secondary" onClick={() => onReturnToReview?.(returnContext, null)}>直接返回{returnTarget}</button>
            <button type="button" className="rule-button primary" onClick={applyAndReturn}>
              {rules.some((rule) => rule.id === focusRuleId) ? `编辑、应用并返回${returnTarget}` : focusRuleId ? `返回${returnTarget}` : `新增、应用并返回${returnTarget}`}
            </button>
          </div>
        </div>
      )}

      {feedback && (
        <div className={`rule-feedback ${feedback.tone || "success"}`} role="status" aria-live="polite">
          {feedback.tone === "error" ? <AlertTriangle size={18} aria-hidden="true" /> : <Check size={18} aria-hidden="true" />}
          <span>{feedback.message}</span>
          <button type="button" onClick={() => setFeedback(null)} aria-label="关闭提示"><X size={16} aria-hidden="true" /></button>
        </div>
      )}

      {showTabs && <nav className="rule-tabs" aria-label="规则类型">
        {Object.entries(TAB_META).map(([key, item]) => (
          <button
            key={key}
            type="button"
            className={activeTab === key ? "active" : ""}
            aria-current={activeTab === key ? "page" : undefined}
            onClick={() => { setActiveTab(key); setStatusFilter("all"); }}
          >
            <span>{item.label}</span><b>{counts[key]}</b>
          </button>
        ))}
      </nav>}

      <div className="rule-tab-description">
        <div><Info size={17} aria-hidden="true" /><span>{TAB_META[activeTab].description}</span></div>
        {isBuiltin && <span className="read-only-label">只读说明</span>}
      </div>

      <div className="rule-toolbar">
        <label className="rule-search">
          <Search size={18} aria-hidden="true" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={isBuiltin ? "搜索数据类型或识别标准" : "搜索名称、原词、条件或处理结果"} />
          {query && <button type="button" onClick={() => setQuery("")} aria-label="清空搜索"><X size={16} aria-hidden="true" /></button>}
        </label>
        {!isBuiltin && (
          <label className="rule-filter">
            <SlidersHorizontal size={17} aria-hidden="true" />
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="按启用状态筛选">
              <option value="all">全部状态</option>
              <option value="enabled">仅启用</option>
              <option value="disabled">仅停用</option>
            </select>
          </label>
        )}
        <div className="rule-toolbar-actions">
          {!isBuiltin && <button type="button" className="rule-button primary" onClick={() => openAdd(false)}><Plus size={17} aria-hidden="true" />新建规则</button>}
          {!isBuiltin && <button type="button" className="rule-button secondary" onClick={() => setImportStage("preview")}><Upload size={17} aria-hidden="true" />导入规则</button>}
          {!isBuiltin && <button type="button" className="rule-button secondary" onClick={() => notify("空白模板原型反馈已生成；本交互原型不会下载或写入真实文件。", "info")}><Download size={17} aria-hidden="true" />下载模板</button>}
          {!isBuiltin && <button type="button" className="rule-button text" onClick={() => setRestoreOpen(true)}><RotateCcw size={17} aria-hidden="true" />恢复默认</button>}
        </div>
      </div>

      {isBuiltin ? (
        <div className="builtin-list-head" aria-hidden="true">
          <span>数据类型</span><span>识别标准、默认处理与示例</span><span>状态</span>
        </div>
      ) : (
        <div className="rule-list-head" aria-hidden="true">
          <span>规则与适用范围</span><span>处理结果</span><span>状态</span><span>操作</span>
        </div>
      )}

      <div className={`rule-list ${isBuiltin ? "builtin-list" : ""}`}>
        {isBuiltin ? (
          filteredBuiltin.length ? filteredBuiltin.map((item) => (
            <BuiltinRow
              key={item.id}
              item={item}
              focused={item.id === focusRuleId}
              setRowRef={(node) => { if (node) rowRefs.current.set(item.id, node); else rowRefs.current.delete(item.id); }}
            />
          )) : <EmptyRules query={query} builtin />
        ) : filteredRules.length ? filteredRules.map((rule) => (
          <RuleRow
            key={rule.id}
            rule={rule}
            focused={rule.id === focusRuleId}
            setRowRef={(node) => { if (node) rowRefs.current.set(rule.id, node); else rowRefs.current.delete(rule.id); }}
            onEdit={openEdit}
            onCopy={openCopy}
            onToggle={toggleRule}
            onDelete={setDeleteTarget}
            onTest={setTestRule}
          />
        )) : <EmptyRules query={query} onAdd={() => openAdd(false)} />}
      </div>

      <footer className="rule-page-footer">
        <span><ShieldCheck size={16} aria-hidden="true" />本原型不保存真实规则，不读取文件，也不执行 OCR 或脱敏。</span>
        <b>共 {isBuiltin ? filteredBuiltin.length : filteredRules.length} 项</b>
      </footer>

      {editor && (
        <RuleEditorDialog
          key={`${editor.mode}-${editor.rule.id}`}
          editor={editor}
          returnTarget={returnTarget}
          onClose={() => setEditor(null)}
          onSave={saveRule}
        />
      )}
      {testRule && <TestRuleDialog rule={testRule} onClose={() => setTestRule(null)} />}
      {deleteTarget && (
        <ConfirmDialog
          title="删除这条规则？"
          body={`删除“${deleteTarget.name}”后，它不会再参与当前原型中的处理建议。此操作不会删除任何任务或结果。`}
          confirmLabel="确认删除"
          danger
          onCancel={() => setDeleteTarget(null)}
          onConfirm={deleteRule}
        />
      )}
      {restoreOpen && (
        <ConfirmDialog
          title="恢复默认预置？"
          body="只恢复缺失的虚构默认预置，不覆盖你已新增或修改的规则。"
          confirmLabel="恢复缺失预置"
          onCancel={() => setRestoreOpen(false)}
          onConfirm={restoreDefaults}
        />
      )}
      {importStage && (
        <ImportDialog
          conflictRule={conflictRule}
          stage={importStage}
          onStage={setImportStage}
          onCancel={() => { setImportStage(null); notify("已取消导入，现有规则没有变化。", "info"); }}
          onChoose={finishImport}
        />
      )}
    </section>
  );
}

function EmptyRules({ query, builtin = false, onAdd }) {
  return (
    <div className="rule-empty-state">
      <Search size={28} aria-hidden="true" />
      <h3>{query ? "没有符合条件的内容" : builtin ? "暂无系统说明" : "还没有此类规则"}</h3>
      <p>{query ? "可以调整搜索词或筛选状态后再试。" : builtin ? "系统说明数据尚未传入。" : "新增一条虚构规则，测试完整维护闭环。"}</p>
      {!query && !builtin && <button type="button" className="rule-button primary" onClick={onAdd}><Plus size={17} aria-hidden="true" />新建规则</button>}
    </div>
  );
}
