import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  ClipboardList,
  FileText,
  FolderOpen,
  HardDrive,
  RotateCcw,
  Sheet,
  SkipForward,
  SquarePlus,
  Trash2,
  XCircle,
} from "lucide-react";
import NewTaskView from "./components/NewTaskView";
import RuleLibraryView from "./components/RuleLibraryView";
import TaskFlowView from "./components/TaskFlowView";
import { desktopBridge } from "./desktopBridge";
import {
  builtinRuleExplanations,
  initialFindings,
  initialHistory,
  initialRules,
  outputFiles,
  sampleSources,
  scanStages,
} from "./prototypeData";

function asBoolean(value) {
  return typeof value === "boolean" ? value : Boolean(value?.target?.checked);
}

function asValue(value) {
  return typeof value === "string" ? value : value?.target?.value;
}

function FileGlyph({ type }) {
  const isSheet = String(type).toUpperCase() === "XLSX";
  const Icon = isSheet ? Sheet : FileText;
  return (
    <span className={`file-icon ${isSheet ? "sheet" : "word"}`} aria-hidden="true">
      <Icon size={22} strokeWidth={1.8} />
    </span>
  );
}

function StatusGlyph({ tone }) {
  if (tone === "error") return <XCircle size={15} aria-hidden="true" />;
  if (tone === "success") return <CheckCircle2 size={15} aria-hidden="true" />;
  return <CircleAlert size={15} aria-hidden="true" />;
}

function currentTaskPresentation(taskState, pendingCount) {
  const presentations = {
    idle: ["尚未开始", "neutral"],
    source_ready: ["待检查", "neutral"],
    checking: ["自动检查中", "warning"],
    blocked: ["已阻断", "error"],
    failed: ["检查失败", "error"],
    cancelled: ["已取消", "neutral"],
    ready_to_generate: ["待生成", "warning"],
    generating: ["正在生成", "warning"],
    rescanning: ["技术复查中", "warning"],
    check_failed: ["最终检查异常", "error"],
    completed: ["已完成", "success"],
  };
  if (taskState === "review_required") return [`待确认 ${pendingCount} 项`, "warning"];
  return presentations[taskState] ?? [`待确认 ${pendingCount} 项`, "warning"];
}

function historyRows(entries = []) {
  return entries.map((item) => ({
    id: item.id,
    name: item.name,
    type: item.type,
    status: item.status === "completed" ? "已完成" : "检查失败",
    tone: item.status === "completed" ? "success" : "error",
    time: item.time,
    summary: `处理 ${item.findingCount} 项`,
    resultAvailable: item.resultAvailable,
    group: "today",
  }));
}

function Rail({ activeNav, expanded, taskButtonRef, ruleButtonRef, onNavigate, onExpand }) {
  return (
    <nav className="rail" aria-label="主导航">
      <button
        className={`rail-expand-button ${expanded ? "is-hidden" : ""}`}
        type="button"
        onClick={onExpand}
        aria-label="展开侧栏"
        title="展开侧栏"
        aria-hidden={expanded}
        tabIndex={expanded ? -1 : 0}
      >
        <ChevronRight size={18} strokeWidth={1.8} aria-hidden="true" />
      </button>
      <img className="brand-logo" src="./assets/logo.png" alt="本地文档脱敏工具" />
      <div className="rail-actions">
        <button
          ref={taskButtonRef}
          className={`rail-action ${["tasks", "new"].includes(activeNav) ? "selected" : ""}`}
          type="button"
          onClick={() => onNavigate("tasks")}
          aria-expanded={expanded && activeNav !== "rules"}
          aria-controls="history-panel"
        >
          <ClipboardList size={26} strokeWidth={1.8} aria-hidden="true" /><span>任务</span>
        </button>
        <button ref={ruleButtonRef} className={`rail-action ${activeNav === "rules" ? "selected" : ""}`} type="button" onClick={() => onNavigate("rules")} aria-expanded={expanded && activeNav === "rules"} aria-controls="rule-sidebar">
          <FileText size={27} strokeWidth={1.8} aria-hidden="true" /><span>规则</span>
        </button>
      </div>
    </nav>
  );
}

function TaskRow({ task, active, onSelect }) {
  return (
    <button className={`task-row ${active ? "active" : ""}`} type="button" onClick={() => onSelect(task.id)} aria-current={active ? "page" : undefined}>
      <FileGlyph type={task.type} />
      <span className="task-copy">
        <span className="task-name">{task.name}</span>
        <span className={`task-status ${task.tone || "neutral"}`}>
          <StatusGlyph tone={task.tone} />{task.status}
        </span>
      </span>
    </button>
  );
}

function HistoryPanel({ activeNav, activeTaskId, currentTask, folderBatch, history, onNewTask, onSelectTask, onOpenFolder, onShowAll, onCollapse }) {
  return (
    <section className="history-panel" id="history-panel" aria-label="任务与历史">
      <div className="history-panel-head">
        <strong>任务与历史</strong>
        <button className="collapse-button" type="button" onClick={onCollapse} aria-label="收起任务侧栏" title="收起任务侧栏">
          <ChevronLeft size={21} />
        </button>
      </div>
      <div className="history-scroll">
        <button className={`sidebar-primary-action ${activeNav === "new" ? "active" : ""}`} type="button" onClick={onNewTask}>
          <SquarePlus size={19} /><strong>新建任务</strong><ChevronRight size={17} />
        </button>
        {currentTask && <div className="history-group compact-first">
          <h2>当前任务</h2>
          <TaskRow task={currentTask} active={activeTaskId === "current"} onSelect={onSelectTask} />
        </div>}
        {folderBatch && <div className="history-group">
          <h2>文件夹批次</h2>
          <button className="task-row folder-row" type="button" onClick={onOpenFolder}>
            <span className="file-icon folder" aria-hidden="true"><FolderOpen size={22} strokeWidth={1.8} /></span>
            <span className="task-copy">
              <span className="task-name">{folderBatch.name}&nbsp; {folderBatch.progressText}</span>
              <span className={`task-status ${folderBatch.tone}`}><StatusGlyph tone={folderBatch.tone} />{folderBatch.statusText}</span>
            </span>
          </button>
        </div>}
        {["today", "earlier"].map((group) => {
          const rows = history.filter((item) => item.group === group);
          if (!rows.length) return null;
          return (
            <div className="history-group" key={group}>
              <h2>{group === "today" ? "今天" : "更早"}</h2>
              {rows.map((item) => <TaskRow key={item.id} task={item} active={activeTaskId === item.id} onSelect={onSelectTask} />)}
            </div>
          );
        })}
        {!currentTask && history.length === 0 && <div className="history-group compact-first"><h2>任务历史</h2><p className="module-sidebar-note">暂无本机历史。</p></div>}
      </div>
      <button className="all-history" type="button" onClick={onShowAll}>查看全部历史 <ChevronRight size={17} /></button>
    </section>
  );
}

function RuleSidebar({ rules, builtinCount, activeTab, onSelectTab, onAdd, onCollapse }) {
  const items = [
    { id: "fixed", label: "固定替换", count: rules.filter((rule) => rule.type === "fixed").length },
    { id: "standard", label: "判断标准", count: rules.filter((rule) => rule.type === "standard").length },
    { id: "builtin", label: "系统识别说明", count: builtinCount },
  ];
  return (
    <section className="history-panel rule-sidebar" id="rule-sidebar" aria-label="规则库导航">
      <div className="history-panel-head">
        <strong>规则库</strong>
        <button className="collapse-button" type="button" onClick={onCollapse} aria-label="收起规则侧栏" title="收起规则侧栏"><ChevronLeft size={21} /></button>
      </div>
      <div className="rule-sidebar-body">
        <button className="sidebar-primary-action" type="button" onClick={onAdd}>
          <SquarePlus size={19} /><strong>新建规则</strong><ChevronRight size={17} />
        </button>
        <p className="module-sidebar-label">规则类型</p>
        <nav className="module-sidebar-list" aria-label="规则类型">
          {items.map((item) => (
            <button key={item.id} type="button" className={activeTab === item.id ? "active" : ""} onClick={() => onSelectTab(item.id)} aria-current={activeTab === item.id ? "page" : undefined}>
              <span>{item.label}</span><b>{item.count}</b>
            </button>
          ))}
        </nav>
        <p className="module-sidebar-note">规则仅用于当前本机原型，不读取真实文件。</p>
      </div>
    </section>
  );
}

function HistoryWorkspace({ history, selectedId, output, onSelect, onContinue, onRetry, onViewResult, onDelete, onBackCurrent }) {
  const selected = history.find((item) => item.id === selectedId);
  if (selected) {
    return (
      <section className="history-workspace page-workspace" aria-label={`${selected.name} 历史任务详情`}>
        <header className="workspace-page-header">
          <div><span className="page-eyebrow">历史任务</span><h1>{selected.name}</h1></div>
          <span className="offline-chip"><HardDrive size={17} />本机离线 · 文件不上传</span>
        </header>
        <div className="history-detail-card">
          <FileGlyph type={selected.type} />
          <div className={`detail-status ${selected.tone}`}><StatusGlyph tone={selected.tone} />{selected.status}</div>
          <p className="detail-time">{selected.time} · {selected.summary}</p>
          {selected.tone === "success" && selected.resultAvailable && (
            <div className="history-output-preview">
              <h2>本机结果记录</h2>
              <div className="history-output-grid">
                <div><strong>AI 交付</strong><span>{output.ai[0].name}</span></div>
                <div><strong>本地保管</strong><span>{output.local.length} 个检查辅助文件</span></div>
              </div>
              <p>技术检查已完成，仍需按单位制度确认是否可外发。</p>
            </div>
          )}
          {selected.tone === "error" && <p className="history-state-note error">该任务未生成可用结果。失败原因已保留，可重新选择虚构样例重试。</p>}
          {selected.tone === "warning" && <p className="history-state-note warning">该任务仍有待确认项，可以回到原处理位置继续。</p>}
          <div className="history-detail-actions">
            {selected.tone === "warning" && <button className="primary-button" type="button" onClick={() => onContinue(selected)}>继续处理</button>}
            {selected.tone === "error" && <button className="primary-button" type="button" onClick={() => onRetry(selected)}>重新尝试</button>}
            {selected.tone === "success" && selected.resultAvailable && <button className="primary-button" type="button" onClick={() => onViewResult(selected)}>查看结果记录</button>}
            <button type="button" onClick={onBackCurrent}><RotateCcw size={17} />返回当前任务</button>
            <button className="danger-button" type="button" onClick={() => onDelete(selected)}><Trash2 size={17} />删除记录</button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="history-workspace page-workspace" aria-label="全部任务历史">
      <header className="workspace-page-header">
        <div><span className="page-eyebrow">仅保留本机任务摘要</span><h1>全部任务历史</h1></div>
        <span className="offline-chip"><HardDrive size={17} />不展示原文、完整路径或映射内容</span>
      </header>
      <div className="history-list-page">
        <div className="history-list-head"><span>文件与时间</span><span>状态</span><span>摘要</span><span>可用操作</span></div>
        {history.map((item) => (
          <div className="history-list-row" key={item.id}>
            <button className="history-file-button" type="button" onClick={() => onSelect(item.id)}><FileGlyph type={item.type} /><span><strong>{item.name}</strong><small>{item.time}</small></span></button>
            <span className={`task-status ${item.tone}`}><StatusGlyph tone={item.tone} />{item.status}</span>
            <span>{item.summary}</span>
            <span className="history-row-actions">
              {item.tone === "warning" && <button type="button" onClick={() => onContinue(item)}>继续</button>}
              {item.tone === "error" && <button type="button" onClick={() => onRetry(item)}>重试</button>}
              {item.tone === "success" && item.resultAvailable && <button type="button" onClick={() => onViewResult(item)}>查看结果</button>}
              <button type="button" aria-label={`删除 ${item.name} 的历史记录`} onClick={() => onDelete(item)}><Trash2 size={16} /></button>
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function ConfirmDialog({ item, onCancel, onConfirm }) {
  if (!item) return null;
  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-history-title">
        <h2 id="delete-history-title">删除这条历史记录？</h2>
        <p>将移除“{item.name}”的原型摘要，不影响其他任务。此操作仅发生在当前虚构原型中。</p>
        <div><button type="button" onClick={onCancel}>取消</button><button className="danger-solid" type="button" onClick={onConfirm}>删除记录</button></div>
      </section>
    </div>
  );
}

const BATCH_STATE_COPY = {
  ready: ["待处理", "neutral"],
  processing: ["处理中", "warning"],
  completed: ["已完成", "success"],
  failed: ["检查失败", "error"],
  skipped: ["已跳过", "neutral"],
  excluded: ["已排除", "neutral"],
};

function summarizeBatch(items = []) {
  return items.reduce((summary, item) => {
    const key = item.state in summary ? item.state : "ready";
    return { ...summary, [key]: summary[key] + 1 };
  }, { ready: 0, processing: 0, completed: 0, failed: 0, skipped: 0, excluded: 0 });
}

function batchTaskSource(item, session) {
  const primaryIndex = session.primaryIds.indexOf(item.id);
  const sequence = primaryIndex >= 0
    ? `批次第 ${primaryIndex + 1} / ${session.primaryIds.length} 个可处理文件`
    : "预置失败项重试";
  return {
    id: `batch-${item.id}`,
    batchItemId: item.id,
    kind: "file",
    name: item.name,
    type: item.type,
    size: sequence,
    description: `${session.name} · ${sequence}`,
  };
}

function BatchContextBar({ session, onContinue, onRetry, onSkip }) {
  const counts = summarizeBatch(session.items);
  const current = session.items.find((item) => item.id === session.currentId);
  const primaryIndex = current ? session.primaryIds.indexOf(current.id) : -1;
  const unresolvedFailure = session.items.find((item) => item.state === "failed");
  const sequenceText = primaryIndex >= 0
    ? `当前第 ${primaryIndex + 1} / ${session.primaryIds.length} 个可处理文件`
    : current ? "正在重试预置失败项" : "处理剩余失败项";
  const actionableTotal = session.items.filter((item) => item.state !== "excluded").length;
  const finishedTotal = counts.completed + counts.skipped;

  return (
    <section className={`batch-context-bar is-${session.phase}`} aria-label="文件夹批次进度" data-testid="batch-context-bar">
      <div className="batch-context-heading">
        <span className="batch-folder-icon"><FolderOpen size={21} /></span>
        <div>
          <span className="batch-eyebrow">文件夹批次 · {finishedTotal} / {actionableTotal}</span>
          <strong>{session.name}</strong>
          <small>{current ? `${sequenceText} · ${current.name}` : sequenceText}</small>
        </div>
        <div className="batch-counts" aria-label="批次状态数量">
          <span className="success">成功 {counts.completed}</span>
          <span className="error">失败 {counts.failed}</span>
          <span>跳过 {counts.skipped}</span>
          <span>排除 {counts.excluded}</span>
        </div>
      </div>

      <div className="batch-item-strip" aria-label="批次文件状态">
        {session.items.map((item) => {
          const [label, tone] = BATCH_STATE_COPY[item.state] || BATCH_STATE_COPY.ready;
          return (
            <span key={item.id} className={`batch-item-chip ${tone} ${item.id === session.currentId ? "is-current" : ""}`}>
              <strong>{item.name}</strong><small>{label}</small>
            </span>
          );
        })}
      </div>

      {session.phase === "item_completed" && (
        <div className="batch-next-row">
          <span><CheckCircle2 size={17} />当前文件已完成，结果已加入任务历史。</span>
          <button className="primary-button" type="button" onClick={onContinue}>继续下一项 <ChevronRight size={17} /></button>
        </div>
      )}

      {session.phase === "needs_resolution" && unresolvedFailure && (
        <div className="batch-next-row is-error">
          <span><XCircle size={17} />“{unresolvedFailure.name}”检查失败，不会阻塞其他文件；可重试或跳过。</span>
          <div>
            <button type="button" onClick={() => onSkip(unresolvedFailure.id)}><SkipForward size={16} />跳过失败项</button>
            <button className="primary-button" type="button" onClick={() => onRetry(unresolvedFailure.id)}><RotateCcw size={16} />重试该项</button>
          </div>
        </div>
      )}
    </section>
  );
}

function BatchSummaryWorkspace({ session, onNewTask, onViewHistory }) {
  const counts = summarizeBatch(session.items);
  return (
    <section className="batch-summary-workspace page-workspace" aria-labelledby="batch-summary-title" data-testid="batch-summary">
      <header className="workspace-page-header">
        <div><span className="page-eyebrow">文件夹批次已结束</span><h1 id="batch-summary-title">{session.name}</h1></div>
        <span className="offline-chip"><HardDrive size={17} />本机离线 · 文件不上传</span>
      </header>
      <div className="batch-summary-content">
        <div className="batch-summary-hero">
          <span><CheckCircle2 size={29} /></span>
          <div><h2>批次处理结果</h2><p>一个文件失败或跳过不会改变其他文件的结果，也不会被误标为成功。</p></div>
        </div>
        <div className="batch-summary-counts">
          <div className="success"><strong>{counts.completed}</strong><span>成功</span></div>
          <div className="error"><strong>{counts.failed}</strong><span>失败</span></div>
          <div><strong>{counts.skipped}</strong><span>跳过</span></div>
          <div><strong>{counts.excluded}</strong><span>排除</span></div>
        </div>
        <div className="batch-summary-list">
          {session.items.map((item) => {
            const [label, tone] = BATCH_STATE_COPY[item.state] || BATCH_STATE_COPY.ready;
            return (
              <div key={item.id} className={`batch-summary-row ${tone}`}>
                <FileGlyph type={item.type} />
                <span><strong>{item.name}</strong><small>{item.reason || (item.state === "completed" ? "结果已加入任务历史" : "未生成结果")}</small></span>
                <span className={`task-status ${tone}`}><StatusGlyph tone={tone} />{label}</span>
              </div>
            );
          })}
        </div>
        <div className="batch-summary-actions">
          <button type="button" onClick={onNewTask}><SquarePlus size={17} />新建任务</button>
          <button className="primary-button" type="button" onClick={onViewHistory}><ClipboardList size={17} />查看任务历史</button>
        </div>
      </div>
    </section>
  );
}

export function App() {
  const [expanded, setExpanded] = useState(() => typeof window !== "undefined" && window.sessionStorage.getItem("prototype-sidebar") === "expanded");
  const [activeNav, setActiveNav] = useState("new");
  const [selectedSource, setSelectedSource] = useState(null);
  const [mode, setMode] = useState("balanced");
  const [includeSubfolders, setIncludeSubfolders] = useState(true);
  const [boundaryAccepted, setBoundaryAccepted] = useState(false);
  const [workflowStep, setWorkflowStep] = useState(1);
  const [taskState, setTaskState] = useState("source_ready");
  const [scanStage, setScanStage] = useState(0);
  const [findings, setFindings] = useState([]);
  const [resolutions, setResolutions] = useState({});
  const [replacements, setReplacements] = useState({});
  const [selectedFindingId, setSelectedFindingId] = useState(null);
  const [editingFindingId, setEditingFindingId] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [rules, setRules] = useState([]);
  const [ruleTab, setRuleTab] = useState("fixed");
  const [ruleAddRequest, setRuleAddRequest] = useState(0);
  const [focusRuleId, setFocusRuleId] = useState(null);
  const [returnContext, setReturnContext] = useState(null);
  const [rememberedDecisions, setRememberedDecisions] = useState([]);
  const [generationState, setGenerationState] = useState("idle");
  const [generationShouldFail, setGenerationShouldFail] = useState(false);
  const [batchSession, setBatchSession] = useState(null);
  const [history, setHistory] = useState([]);
  const [activeTaskId, setActiveTaskId] = useState("current");
  const [historyView, setHistoryView] = useState("current");
  const [selectedHistoryId, setSelectedHistoryId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [resultRecord, setResultRecord] = useState(null);
  const [toast, setToast] = useState(null);
  const [desktopStatus, setDesktopStatus] = useState("checking");
  const [demoMode, setDemoMode] = useState(false);
  const [desktopTaskId, setDesktopTaskId] = useState(null);
  const [desktopPreview, setDesktopPreview] = useState(null);
  const [realArtifacts, setRealArtifacts] = useState(null);
  const taskButtonRef = useRef(null);
  const ruleButtonRef = useRef(null);

  const desktopReady = desktopStatus === "ready";
  const pendingCount = findings.filter((item) => !resolutions[item.id]).length;
  const [currentStatus, currentTone] = currentTaskPresentation(taskState, pendingCount);
  const currentTask = useMemo(() => selectedSource ? ({
    id: "current",
    name: selectedSource.name,
    type: selectedSource.type || "DOCX",
    status: currentStatus,
    tone: currentTone,
  }) : null, [selectedSource, currentStatus, currentTone]);
  const folderSource = useMemo(() => demoMode ? sampleSources.find((source) => source.kind === "folder") : null, [demoMode]);
  const folderBatch = useMemo(() => {
    if (!folderSource) return null;
    const items = batchSession?.items || folderSource?.queue || [];
    const counts = summarizeBatch(items);
    const actionableTotal = items.filter((item) => item.state !== "excluded").length;
    const finishedTotal = counts.completed + counts.skipped;
    const active = items.find((item) => item.state === "processing");
    const statusText = batchSession?.phase === "completed"
      ? `成功 ${counts.completed} · 失败 ${counts.failed} · 跳过 ${counts.skipped} · 排除 ${counts.excluded}`
      : active
        ? `正在处理 ${active.name}`
        : `待处理 ${counts.ready} · 失败 ${counts.failed} · 排除 ${counts.excluded}`;
    return {
      name: batchSession?.name || folderSource?.name || "项目资料文件夹",
      progressText: `${finishedTotal} / ${actionableTotal}`,
      statusText,
      tone: batchSession?.phase === "completed" ? "success" : counts.failed > 0 ? "warning" : "neutral",
    };
  }, [batchSession, folderSource]);
  const taskOutputFiles = useMemo(() => {
    if (realArtifacts) {
      return {
        folderName: realArtifacts.resultRoot,
        ai: [{ id: "ai-copy", name: realArtifacts.ai.name, path: realArtifacts.ai.path, note: "保留版式结构，仅包含已确认的替代内容" }],
        local: [
          { id: "mapping", name: realArtifacts.mapping.name, path: realArtifacts.mapping.path, note: "含真实原值，仅限本地保管，严禁上传", danger: true },
          { id: "report", name: realArtifacts.report.name, path: realArtifacts.report.path, note: "记录技术检查范围、处理数量和结果" },
        ],
      };
    }
    const sourceName = selectedSource?.name || "虚构项目方案.docx";
    const lastDot = sourceName.lastIndexOf(".");
    const baseName = lastDot > 0 ? sourceName.slice(0, lastDot) : sourceName;
    const extension = selectedSource?.type === "XLSX" ? "xlsx" : "docx";
    return {
    ...outputFiles,
    folderName: `${baseName}-脱敏稿`,
    ai: outputFiles.ai.map((file) => ({
      ...file,
      name: `${baseName}-脱敏稿.${extension}`,
    })),
  };
  }, [realArtifacts, selectedSource?.name, selectedSource?.type]);

  const showToast = (message, tone = "success") => setToast({ message, tone });

  const applyDesktopSnapshot = (snapshot) => {
    if (!snapshot) return;
    const nextFindings = snapshot.findings || [];
    const nextResolutions = snapshot.resolutions || {};
    setFindings(nextFindings);
    setResolutions(nextResolutions);
    setReplacements(Object.fromEntries(nextFindings.map((item) => [item.id, item.suggestion])));
    setSelectedFindingId(nextFindings.find((item) => !nextResolutions[item.id])?.id || nextFindings[0]?.id || null);
    setWorkflowStep(snapshot.currentStep || 1);
    setTaskState(snapshot.state || "source_ready");
    setDesktopPreview(snapshot.preview || null);
    if (snapshot.artifacts) setRealArtifacts(snapshot.artifacts);
  };

  useEffect(() => {
    let active = true;
    const initializeDesktop = async () => {
      const result = await desktopBridge.runtimeInfo();
      if (!active) return;
      const ready = Boolean(result?.ok && result.runtime === "native-windows-desktop");
      setDesktopStatus(ready ? "ready" : "unavailable");
      if (!ready) return;
      const isDemo = Boolean(result.demoMode);
      setDemoMode(isDemo);
      if (isDemo) {
        setSelectedSource(sampleSources[0]);
        setBoundaryAccepted(true);
        setWorkflowStep(3);
        setTaskState("review_required");
        setScanStage(scanStages.length - 1);
        setFindings(initialFindings);
        setReplacements(Object.fromEntries(initialFindings.map((item) => [item.id, item.suggestion])));
        setSelectedFindingId(initialFindings[0]?.id || null);
        setRules(initialRules);
        setHistory(initialHistory);
        setActiveNav("tasks");
        return;
      }
      const historyResult = await desktopBridge.listHistory();
      if (!active) return;
      if (historyResult?.ok) setHistory(historyRows(historyResult.data?.entries));
      else showToast(historyResult?.error?.message || "无法读取本机历史", "error");
      const rulesResult = await desktopBridge.listRules();
      if (!active) return;
      if (rulesResult?.ok) setRules(rulesResult.data?.rules || []);
      else showToast(rulesResult?.error?.message || "无法读取本机规则库", "error");
    };
    initializeDesktop();
    return () => { active = false; };
  }, []);

  useEffect(() => { window.sessionStorage.setItem("prototype-sidebar", expanded ? "expanded" : "collapsed"); }, [expanded]);
  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape" && expanded) {
        setExpanded(false);
        window.requestAnimationFrame(() => (activeNav === "rules" ? ruleButtonRef : taskButtonRef).current?.focus());
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeNav, expanded]);

  useEffect(() => {
    if (selectedSource?.native) return undefined;
    if (taskState !== "checking") return undefined;
    const timer = window.setTimeout(() => {
      if (selectedSource?.blocked) {
        setTaskState("blocked");
        return;
      }
      if (scanStage < scanStages.length - 1) {
        setScanStage((value) => value + 1);
        return;
      }
      setWorkflowStep(3);
      setTaskState(pendingCount === 0 ? "ready_to_generate" : "review_required");
      showToast(`自动检查完成，发现 ${findings.length} 个需要确认的候选项`);
    }, 460);
    return () => window.clearTimeout(timer);
  }, [taskState, scanStage, selectedSource, pendingCount, findings.length]);

  useEffect(() => {
    if (desktopTaskId) return undefined;
    if (generationState !== "generating" && generationState !== "rescanning") return undefined;
    const timer = window.setTimeout(() => {
      if (generationState === "generating") {
        setGenerationState("rescanning");
        setTaskState("rescanning");
        return;
      }
      if (generationShouldFail) {
        setGenerationState("check_failed");
        setTaskState("check_failed");
        showToast("最终检查发现一项需要返回确认，未生成可用结果", "error");
        return;
      }
      const completedBatchItemId = batchSession?.currentId;
      const completedRecord = {
        id: completedBatchItemId ? `history-batch-${completedBatchItemId}` : "history-current-result",
        name: selectedSource?.name || "虚构项目方案.docx",
        type: selectedSource?.type || "DOCX",
        status: "已完成",
        tone: "success",
        time: "刚刚",
        summary: `处理 ${findings.length} 项 · 结果可用`,
        resultAvailable: true,
        group: "today",
      };
      setGenerationState("completed");
      setTaskState("completed");
      setResultRecord(completedRecord);
      setHistory((items) => [completedRecord, ...items.filter((item) => item.id !== completedRecord.id)]);
      if (completedBatchItemId) {
        setBatchSession((session) => session ? {
          ...session,
          phase: "item_completed",
          items: session.items.map((item) => item.id === completedBatchItemId ? {
            ...item,
            state: "completed",
            stateText: "已完成",
            resultRecordId: completedRecord.id,
            reason: "结果已加入任务历史",
          } : item),
        } : session);
        showToast("当前批次文件已完成，可继续处理下一项");
      } else {
        showToast("生成与技术复查完成，结果已加入本机历史");
      }
    }, 760);
    return () => window.clearTimeout(timer);
  }, [generationState, generationShouldFail, selectedSource, findings.length, batchSession?.currentId, desktopTaskId]);

  const collapseSidebar = () => {
    setExpanded(false);
    window.requestAnimationFrame(() => (activeNav === "rules" ? ruleButtonRef : taskButtonRef).current?.focus());
  };

  const navigate = (target) => {
    if (target === "tasks" && !selectedSource) {
      setActiveNav("new");
      setHistoryView("current");
      return;
    }
    setActiveNav(target);
    if (target === "rules") setFocusRuleId(null);
    if (target === "tasks" && historyView === "current") setActiveTaskId("current");
  };

  const openNewTask = () => {
    setSelectedSource(null);
    setBoundaryAccepted(false);
    setWorkflowStep(1);
    setTaskState("source_ready");
    setDesktopTaskId(null);
    resetReviewState();
    setActiveNav("new");
    setExpanded(true);
    setHistoryView("current");
  };

  const resetReviewState = () => {
    const nextFindings = demoMode ? initialFindings : [];
    setFindings(nextFindings);
    setResolutions({});
    setReplacements(Object.fromEntries(nextFindings.map((item) => [item.id, item.suggestion])));
    setSelectedFindingId(nextFindings[0]?.id || null);
    setEditingFindingId(null);
    setEditValue("");
    setRememberedDecisions([]);
    setGenerationState("idle");
    setResultRecord(null);
    setDesktopPreview(null);
    setRealArtifacts(null);
  };

  const chooseDesktopFile = async () => {
    const result = await desktopBridge.chooseFile();
    if (!result?.ok) {
      showToast(result?.error?.message || "无法打开本机文件选择器", "error");
      return null;
    }
    if (result.data?.cancelled) return null;
    const source = result.data?.source;
    if (source) {
      setSelectedSource(source);
      showToast(`已选择：${source.name}`);
    }
    return source || null;
  };

  const launchWorkflow = (source) => {
    setDesktopTaskId(null);
    setSelectedSource(source);
    resetReviewState();
    setActiveNav("tasks");
    setExpanded(true);
    setActiveTaskId("current");
    setHistoryView("current");
    setWorkflowStep(2);
    setScanStage(0);
    setTaskState("checking");
  };

  const startTask = async (payload = selectedSource) => {
    const source = payload?.source || payload;
    if (payload?.mode) setMode(payload.mode);
    if (typeof payload?.includeSubfolders === "boolean") setIncludeSubfolders(payload.includeSubfolders);
    if (!source) {
      showToast(demoMode ? "请先选择一个虚构样例" : "请先选择一个本机 DOCX 文件", "error");
      return;
    }
    if (!boundaryAccepted) {
      showToast("请先确认本机离线处理边界", "error");
      return;
    }
    if (source.native) {
      resetReviewState();
      setSelectedSource(source);
      setBatchSession(null);
      setActiveNav("tasks");
      setExpanded(true);
      setActiveTaskId("current");
      setHistoryView("current");
      setWorkflowStep(2);
      setTaskState("checking");
      setFindings([]);
      setResolutions({});
      const created = await desktopBridge.createTask({ source, mode: payload?.mode || mode });
      if (!created?.ok) {
        setTaskState("failed");
        showToast(created?.error?.message || "无法创建本机任务", "error");
        return;
      }
      const taskId = created.data.taskId;
      setDesktopTaskId(taskId);
      const scanned = await desktopBridge.startScan(taskId);
      applyDesktopSnapshot(scanned?.data || scanned?.snapshot);
      if (!scanned?.ok) {
        showToast(scanned?.error?.message || "自动检查失败", "error");
        return;
      }
      showToast(`自动检查完成，发现 ${scanned.data?.findings?.length || 0} 个需要确认的候选项`);
      return;
    }
    if (source.kind === "folder") {
      const items = (source.queue || []).map((item) => ({ ...item }));
      const primaryIds = items.filter((item) => item.state === "ready").map((item) => item.id);
      const first = items.find((item) => item.state === "ready");
      if (!first) {
        showToast("该文件夹没有可处理的虚构文件", "error");
        return;
      }
      const session = {
        id: `batch-${Date.now()}`,
        name: source.name,
        sourceId: source.id,
        primaryIds,
        items: items.map((item) => item.id === first.id ? { ...item, state: "processing", stateText: "处理中" } : item),
        currentId: first.id,
        phase: "processing",
      };
      setBatchSession(session);
      launchWorkflow(batchTaskSource(first, session));
      showToast(`文件夹批次已开始，当前处理第 1 / ${primaryIds.length} 个可处理文件`);
      return;
    }

    setBatchSession(null);
    launchWorkflow(source);
  };

  const activateBatchItem = (itemId) => {
    if (!batchSession) return;
    const item = batchSession.items.find((candidate) => candidate.id === itemId);
    if (!item || item.state === "excluded") return;
    const nextSession = {
      ...batchSession,
      currentId: item.id,
      phase: "processing",
      items: batchSession.items.map((candidate) => candidate.id === item.id ? { ...candidate, state: "processing", stateText: "处理中" } : candidate),
    };
    setBatchSession(nextSession);
    launchWorkflow(batchTaskSource(item, nextSession));
  };

  const continueBatch = () => {
    if (!batchSession) return;
    const nextReady = batchSession.items.find((item) => item.state === "ready");
    if (nextReady) {
      activateBatchItem(nextReady.id);
      const index = batchSession.primaryIds.indexOf(nextReady.id);
      showToast(`继续处理批次第 ${index + 1} / ${batchSession.primaryIds.length} 个文件`);
      return;
    }
    const failed = batchSession.items.find((item) => item.state === "failed");
    if (failed) {
      setBatchSession({ ...batchSession, currentId: null, phase: "needs_resolution" });
      showToast("三个可处理文件均已完成，请处理剩余失败项", "warning");
      return;
    }
    setBatchSession({ ...batchSession, currentId: null, phase: "completed" });
    showToast("文件夹批次已完成");
  };

  const retryBatchItem = (itemId) => {
    activateBatchItem(itemId);
    showToast("已重试预置失败项，开始重新检查");
  };

  const skipBatchItem = (itemId) => {
    if (!batchSession) return;
    const nextItems = batchSession.items.map((item) => item.id === itemId ? {
      ...item,
      state: "skipped",
      stateText: "已跳过",
      reason: "用户选择跳过失败项",
    } : item);
    const stillFailed = nextItems.some((item) => item.state === "failed");
    const stillReady = nextItems.some((item) => item.state === "ready");
    setBatchSession({ ...batchSession, items: nextItems, currentId: null, phase: stillFailed ? "needs_resolution" : stillReady ? "item_completed" : "completed" });
    showToast(stillFailed || stillReady ? "失败项已跳过，可继续批次" : "失败项已跳过，文件夹批次已完成");
  };

  const selectFinding = (id) => {
    setSelectedFindingId(id);
    setEditingFindingId(null);
    if (resolutions[id]) showToast("该项已确认，可重新选择处理方式", "neutral");
  };

  const completeResolution = (id, action, value) => {
    const nextResolutions = { ...resolutions, [id]: action };
    if (value !== undefined) setReplacements((items) => ({ ...items, [id]: value }));
    setResolutions(nextResolutions);
    setEditingFindingId(null);
    setEditValue("");
    const next = findings.find((item) => !nextResolutions[item.id]);
    if (next) {
      setSelectedFindingId(next.id);
      setTaskState("review_required");
      showToast("已保存处理决定，进入下一项");
    } else {
      setTaskState("ready_to_generate");
      showToast("全部候选项已确认，可以生成文件");
    }
  };

  const resolveDesktopFinding = async (id, action, value = "") => {
    const result = await desktopBridge.resolveFinding(desktopTaskId, id, action, value);
    if (!result?.ok) {
      showToast(result?.error?.message || "无法保存处理决定", "error");
      return false;
    }
    applyDesktopSnapshot(result.data);
    showToast(result.data?.pendingCount ? "已保存处理决定，进入下一项" : "全部候选项已确认，可以生成文件");
    return true;
  };

  const applySuggestion = async (findingOrId) => {
    const id = typeof findingOrId === "string" ? findingOrId : findingOrId?.id || selectedFindingId;
    if (desktopTaskId) {
      await resolveDesktopFinding(id, "adopt");
      return;
    }
    completeResolution(id, "adopt", replacements[id] || findings.find((item) => item.id === id)?.suggestion);
  };
  const keepOriginal = async (findingOrId) => {
    const id = typeof findingOrId === "string" ? findingOrId : findingOrId?.id || selectedFindingId;
    const finding = findings.find((item) => item.id === id);
    if (finding?.rule?.mandatory) {
      showToast("该项命中强制规则，不能保留原文", "error");
      return;
    }
    if (desktopTaskId) {
      await resolveDesktopFinding(id, "keep");
      return;
    }
    completeResolution(id, "keep", finding?.original);
  };
  const deleteFinding = async (findingOrId) => {
    const id = typeof findingOrId === "string" ? findingOrId : findingOrId?.id || selectedFindingId;
    if (desktopTaskId) {
      await resolveDesktopFinding(id, "delete");
      return;
    }
    completeResolution(id, "delete", "已删除");
  };
  const startEdit = (findingOrId) => {
    const id = typeof findingOrId === "string" ? findingOrId : findingOrId?.id || selectedFindingId;
    setSelectedFindingId(id);
    setEditingFindingId(id);
    setEditValue(replacements[id] || findings.find((item) => item.id === id)?.suggestion || "");
  };
  const saveEdit = async () => {
    if (!editValue.trim()) {
      showToast("替换内容不能为空", "error");
      return;
    }
    if (desktopTaskId) {
      await resolveDesktopFinding(editingFindingId || selectedFindingId, "edit", editValue.trim());
      setEditingFindingId(null);
      setEditValue("");
      return;
    }
    completeResolution(editingFindingId || selectedFindingId, "edit", editValue.trim());
  };
  const applyAllAndContinue = async () => {
    if (desktopTaskId) {
      for (const finding of findings.filter((item) => !resolutions[item.id])) {
        const result = await desktopBridge.resolveFinding(desktopTaskId, finding.id, "adopt", "");
        if (!result?.ok) {
          showToast(result?.error?.message || "批量采用在当前项停止", "error");
          return;
        }
        applyDesktopSnapshot(result.data);
      }
      const snapshot = await desktopBridge.taskSnapshot(desktopTaskId);
      if (snapshot?.ok) applyDesktopSnapshot(snapshot.data);
      setWorkflowStep(4);
      showToast(`已一键采用 ${findings.length} 项建议，进入生成确认`);
      return;
    }
    const nextResolutions = Object.fromEntries(findings.map((item) => [item.id, "adopt"]));
    setResolutions(nextResolutions);
    setReplacements((values) => ({ ...values, ...Object.fromEntries(findings.map((item) => [item.id, item.suggestion])) }));
    setSelectedFindingId(findings.at(-1)?.id || selectedFindingId);
    setEditingFindingId(null);
    setEditValue("");
    setTaskState("ready_to_generate");
    setWorkflowStep(4);
    showToast(`已一键采用 ${findings.length} 项建议，进入生成确认`);
  };

  const openRule = (ruleOrFinding, meta) => {
    const item = meta?.finding || (ruleOrFinding?.id ? ruleOrFinding : findings.find((candidate) => candidate.id === selectedFindingId));
    if (!item) return;
    const index = findings.findIndex((candidate) => candidate.id === item.id) + 1;
    const context = { taskId: "current", findingId: item.id, findingIndex: index, section: item.section };
    setReturnContext(context);
    setFocusRuleId(item.rule.id);
    setRuleTab(item.rule.source === "fixed" ? "fixed" : item.rule.source === "standard" ? "standard" : "builtin");
    setActiveNav("rules");
    setExpanded(true);
  };

  const updateFindingRule = (updatedRule) => {
    if (!updatedRule?.id) return;
    const affectedIds = findings.filter((item) => item.rule?.id === updatedRule.id).map((item) => item.id);
    if (updatedRule.replacement) {
      setReplacements((values) => ({
        ...values,
        ...Object.fromEntries(affectedIds.map((id) => [id, updatedRule.replacement])),
      }));
    }
    setFindings((items) => items.map((item) => item.rule?.id === updatedRule.id ? {
      ...item,
      suggestion: updatedRule.replacement || item.suggestion,
      rule: {
        ...item.rule,
        name: updatedRule.name || item.rule.name,
        revision: "刚刚更新",
        matchSummary: updatedRule.pattern || item.rule.matchSummary,
        mandatory: Boolean(updatedRule.mandatory),
      },
      basis: `当前建议已按“${updatedRule.name || item.rule.name}”重新判断；其他已确认项保持不变。`,
    } : item));
  };

  const applyRulesIncrementallyToTask = async (updatedRule = null) => {
    if (desktopTaskId && desktopReady && !demoMode) {
      const result = await desktopBridge.applyRulesIncrementally(desktopTaskId);
      if (!result?.ok) {
        const message = result?.error?.message || "无法增量应用到当前任务。";
        showToast(message, "error");
        throw new Error(message);
      }
      if (result.data?.skipped) {
        if (updatedRule) updateFindingRule(updatedRule);
        showToast(result.data?.message || "当前任务尚未完成检查，新规则将在下次扫描时生效。", "info");
        return result.data;
      }
      applyDesktopSnapshot(result.data);
      const added = Number(result.data?.addedCount || 0);
      showToast(
        result.data?.message
          || (added > 0 ? `规则已增量应用，新增 ${added} 个候选项` : "规则已增量应用到当前任务"),
      );
      return result.data;
    }
    if (updatedRule) updateFindingRule(updatedRule);
    if (updatedRule || findings.length) {
      showToast("新规则已增量应用到当前任务");
    }
    return { applied: false, skipped: true, addedCount: 0 };
  };

  const returnFromRule = (context, updatedRule) => {
    // Engine refresh already happened in applyRulesIncrementallyToTask when desktop task is active.
    if (!desktopTaskId) updateFindingRule(updatedRule);
    const target = context || returnContext;
    setActiveNav("tasks");
    setActiveTaskId("current");
    setHistoryView("current");
    setExpanded(true);
    setWorkflowStep(3);
    setTaskState((current) => {
      if (current === "ready_to_generate" || current === "review_required") return current;
      return pendingCount === 0 ? "ready_to_generate" : "review_required";
    });
    if (target?.findingId) setSelectedFindingId(target.findingId);
    setFocusRuleId(null);
    setReturnContext(null);
    showToast("已返回原确认位置");
  };

  const rememberDecision = (finding, action, value) => {
    if (!finding?.id) return;
    setRememberedDecisions((items) => [...items.filter((item) => item.findingId !== finding.id), { findingId: finding.id, ruleId: finding.rule.id, action, value }]);
    showToast("已记为当前任务的同类处理方式");
  };

  const addManualFinding = async ({ original, suggestion }) => {
    const safeOriginal = String(original || "").trim();
    const safeSuggestion = String(suggestion || "").trim();
    if (!safeOriginal || !safeSuggestion) {
      showToast("请填写要处理的内容和建议结果", "error");
      return false;
    }
    if (desktopTaskId) {
      const result = await desktopBridge.addManualFinding(desktopTaskId, { original: safeOriginal, suggestion: safeSuggestion });
      if (!result?.ok) {
        showToast(result?.error?.message || "无法添加该脱敏内容", "error");
        return false;
      }
      applyDesktopSnapshot(result.data);
      showToast("已添加一条待脱敏内容");
      return true;
    }
    const id = `manual-${Date.now()}`;
    const finding = {
      id,
      category: "文字",
      original: safeOriginal,
      suggestion: safeSuggestion,
      section: "用户补充",
      location: "正文复核中手动添加",
      occurrences: 1,
      severity: "建议替换",
      confidence: "用户确认",
      source: "用户补充",
      actionSet: "text",
      rule: {
        id: "manual-user-added",
        source: "builtin",
        type: "用户补充",
        name: "用户指定脱敏内容",
        mandatory: false,
        revision: "当前任务",
        matchSummary: "由用户在确认处理阶段手动添加",
      },
      basis: "该内容由用户在正文复核阶段主动标记，需要纳入本次任务的待确认列表。",
      detail: "仅用于当前虚构任务，不会写入全局规则库。",
    };
    setFindings((items) => [...items, finding]);
    setReplacements((items) => ({ ...items, [id]: safeSuggestion }));
    setSelectedFindingId(id);
    setEditingFindingId(null);
    setTaskState("review_required");
    setWorkflowStep(3);
    showToast("已添加一条待脱敏内容");
    return true;
  };

  const goPreviousStep = () => {
    if (workflowStep >= 4) {
      setGenerationState("idle");
      setWorkflowStep(3);
      setTaskState(pendingCount === 0 ? "ready_to_generate" : "review_required");
      return;
    }
    if (workflowStep === 3) {
      setWorkflowStep(2);
      setScanStage(Math.max(0, scanStages.length - 1));
      setTaskState("review_required");
      return;
    }
    if (workflowStep === 2) {
      setWorkflowStep(1);
      setTaskState("source_ready");
    }
  };

  const goGenerate = () => {
    if (pendingCount > 0) {
      showToast(`还有 ${pendingCount} 项未确认，暂不能生成`, "error");
      return;
    }
    setWorkflowStep(4);
    setGenerationState("idle");
    setTaskState("ready_to_generate");
  };

  const startGeneration = async (forceFailure = false) => {
    if (pendingCount > 0) {
      showToast("请先完成全部确认", "error");
      return;
    }
    if (desktopTaskId) {
      setWorkflowStep(4);
      setGenerationState("generating");
      setTaskState("generating");
      const result = await desktopBridge.exportTask(desktopTaskId, "");
      if (result?.ok && result.data?.cancelled) {
        setGenerationState("idle");
        setTaskState("ready_to_generate");
        showToast("已取消选择保存位置", "neutral");
        return;
      }
      if (!result?.ok) {
        setGenerationState("check_failed");
        setTaskState("check_failed");
        showToast(result?.error?.message || "生成文件失败", "error");
        return;
      }
      const artifacts = result.data.artifacts;
      setRealArtifacts(artifacts);
      applyDesktopSnapshot(result.data.snapshot);
      setGenerationState("completed");
      setTaskState("completed");
      const completedRecord = {
        id: `history-${desktopTaskId}`,
        name: selectedSource?.name || "DOCX 任务",
        type: "DOCX",
        status: "已完成",
        tone: "success",
        time: "刚刚",
        summary: `处理 ${findings.length} 项 · 结果可用`,
        resultAvailable: true,
        group: "today",
      };
      setResultRecord(completedRecord);
      const historyResult = await desktopBridge.listHistory();
      if (historyResult?.ok) {
        setHistory(historyRows(historyResult.data.entries));
      } else {
        setHistory((items) => [completedRecord, ...items]);
      }
      showToast("生成与技术复查完成，结果已加入本机历史");
      return;
    }
    setWorkflowStep(4);
    setGenerationShouldFail(Boolean(forceFailure));
    setGenerationState("generating");
    setTaskState("generating");
  };

  const rescanOrRepair = () => {
    if (generationState === "check_failed") {
      const targetId = "combined-risk";
      setResolutions((items) => {
        const next = { ...items };
        delete next[targetId];
        return next;
      });
      setSelectedFindingId(targetId);
      setGenerationState("idle");
      setGenerationShouldFail(false);
      setWorkflowStep(3);
      setTaskState("review_required");
      showToast("已定位到组合风险项，请重新确认后再生成", "warning");
      return;
    }
    setWorkflowStep(2);
    setScanStage(0);
    setTaskState("checking");
    setGenerationState("idle");
  };

  const showAllHistory = () => {
    setActiveNav("tasks");
    setActiveTaskId("history-all");
    setSelectedHistoryId(null);
    setHistoryView("history");
  };

  const selectTask = (id) => {
    if (id === "current" && !selectedSource) {
      setActiveNav("new");
      return;
    }
    setActiveNav("tasks");
    setActiveTaskId(id);
    if (id === "current") {
      setHistoryView("current");
      setSelectedHistoryId(null);
    } else {
      setHistoryView("history");
      setSelectedHistoryId(id);
    }
  };

  const continueHistory = (item) => {
    if (!demoMode) {
      showToast("未完成任务恢复将在历史完整迁移阶段接入", "neutral");
      return;
    }
    setSelectedSource({ ...sampleSources[0], name: item.name, type: item.type });
    resetReviewState();
    setResolutions({ person: "adopt", company: "adopt", place: "keep", "seal-image": "adopt" });
    setSelectedFindingId("hidden-meta");
    setWorkflowStep(3);
    setTaskState("review_required");
    setActiveTaskId("current");
    setHistoryView("current");
    showToast("已恢复未完成任务及原确认位置");
  };

  const retryHistory = async (item) => {
    if (!demoMode) {
      const source = await chooseDesktopFile();
      if (source) await startTask(source);
      return;
    }
    const source = { ...sampleSources[0], name: item.name, type: item.type };
    setSelectedSource(source);
    setBoundaryAccepted(true);
    startTask(source);
    showToast("已创建重试任务，开始重新检查");
  };

  const viewHistoryResult = (item) => {
    setHistoryView("history");
    setSelectedHistoryId(item.id);
    setActiveTaskId(item.id);
    showToast(demoMode ? "已打开虚构结果摘要" : "已打开本机结果摘要");
  };

  const confirmDeleteHistory = () => {
    if (!deleteTarget) return;
    if (!demoMode) {
      setDeleteTarget(null);
      showToast("历史删除将在历史完整迁移阶段接入", "neutral");
      return;
    }
    setHistory((items) => items.filter((item) => item.id !== deleteTarget.id));
    if (selectedHistoryId === deleteTarget.id) {
      setSelectedHistoryId(null);
      setActiveTaskId("history-all");
    }
    setDeleteTarget(null);
    showToast("历史摘要已删除");
  };

  const backToNew = () => {
    if (batchSession && ["item_completed", "needs_resolution"].includes(batchSession.phase)) {
      continueBatch();
      return;
    }
    setActiveNav("new");
    setExpanded(true);
    setWorkflowStep(1);
    setTaskState("source_ready");
  };

  const startNewAfterBatch = () => {
    setBatchSession(null);
    setSelectedSource(demoMode ? sampleSources[0] : null);
    resetReviewState();
    setActiveNav("new");
    setExpanded(true);
    setWorkflowStep(1);
    setTaskState("source_ready");
  };

  const taskFlowModel = {
    step: workflowStep,
    taskState,
    boundaryAcknowledged: boundaryAccepted,
    selectedSource,
    scanState: taskState,
    scanStage,
    scanStages,
    findings,
    resolutions,
    replacements,
    selectedFindingId,
    editingFindingId,
    editValue,
    generationState,
    failedFindingId: generationState === "check_failed" ? "combined-risk" : null,
    generationMessage: generationState === "check_failed" ? "技术复查发现组合风险项需要重新确认。当前没有可用结果，请返回该项修复后再试。" : "",
    outputFiles: taskOutputFiles,
    resultRecord,
    rememberedDecisions,
    documentPreview: desktopPreview,
    isDesktopTask: Boolean(desktopTaskId),
  };

  const taskFlowActions = {
    onBoundaryAcknowledge: (value) => setBoundaryAccepted(Boolean(value)),
    onStartScan: (source) => launchWorkflow(source || selectedSource),
    onCancelScan: () => {
      setTaskState("cancelled");
      if (batchSession?.currentId) {
        setBatchSession((session) => session ? {
          ...session,
          phase: "item_completed",
          items: session.items.map((item) => item.id === session.currentId ? { ...item, state: "failed", stateText: "检查失败", reason: "用户取消检查，可稍后重试或跳过" } : item),
        } : session);
      }
      showToast("已取消本次检查", "neutral");
    },
    onRetryScan: () => {
      if (batchSession?.currentId) {
        setBatchSession((session) => session ? {
          ...session,
          phase: "processing",
          items: session.items.map((item) => item.id === session.currentId ? { ...item, state: "processing", stateText: "处理中" } : item),
        } : session);
      }
      setScanStage(0);
      setTaskState("checking");
    },
    onContinueReview: (targetId) => {
      if (generationState === "check_failed") {
        rescanOrRepair();
        if (targetId) setSelectedFindingId(targetId);
        return;
      }
      setWorkflowStep(3);
      setTaskState(pendingCount === 0 ? "ready_to_generate" : "review_required");
    },
    onSelectFinding: selectFinding,
    onApplySuggestion: applySuggestion,
    onKeepOriginal: keepOriginal,
    onDeleteFinding: deleteFinding,
    onStartEdit: startEdit,
    onEditValue: (value) => setEditValue(asValue(value) ?? ""),
    onSaveEdit: saveEdit,
    onCancelEdit: () => { setEditingFindingId(null); setEditValue(""); },
    onApplyAllAndContinue: applyAllAndContinue,
    onOpenRule: openRule,
    onRememberDecision: rememberDecision,
    onAddFinding: addManualFinding,
    onPreviousStep: goPreviousStep,
    onGoGenerate: goGenerate,
    onStartGeneration: startGeneration,
    onRescan: rescanOrRepair,
    onViewOutput: (file) => showToast(`“${file?.name || "结果文件"}”仅为虚构输出，本原型不会创建真实文件`),
    onViewHistory: showAllHistory,
    onBackToNew: backToNew,
    onToast: showToast,
  };

  return (
    <main className={`app-shell ${expanded ? "sidebar-open" : "sidebar-closed"}`} data-testid="app-shell" data-sidebar-state={expanded ? "expanded" : "collapsed"}>
      <aside className="sidebar" data-testid="sidebar" aria-label="任务导航">
        <Rail activeNav={activeNav} expanded={expanded} taskButtonRef={taskButtonRef} ruleButtonRef={ruleButtonRef} onNavigate={navigate} onExpand={() => setExpanded(true)} />
        {expanded && activeNav !== "rules" && (
          <HistoryPanel
            activeNav={activeNav}
            activeTaskId={activeTaskId}
            currentTask={currentTask}
            folderBatch={folderBatch}
            history={history}
            onNewTask={openNewTask}
            onSelectTask={selectTask}
            onOpenFolder={() => {
              if (batchSession) {
                setActiveNav("tasks");
                setHistoryView("current");
                setActiveTaskId("current");
                showToast(batchSession.phase === "completed" ? "已打开文件夹批次结果" : "已返回正在处理的文件夹批次");
                return;
              }
              setSelectedSource(folderSource);
              setBoundaryAccepted(true);
              setActiveNav("new");
              setExpanded(true);
              setWorkflowStep(1);
              showToast("已打开虚构文件夹批次");
            }}
            onShowAll={showAllHistory}
            onCollapse={collapseSidebar}
          />
        )}
        {expanded && activeNav === "rules" && (
          <RuleSidebar
            rules={rules}
            builtinCount={builtinRuleExplanations.length}
            activeTab={ruleTab}
            onSelectTab={setRuleTab}
            onAdd={() => { if (ruleTab === "builtin") setRuleTab("fixed"); setRuleAddRequest((value) => value + 1); }}
            onCollapse={collapseSidebar}
          />
        )}
      </aside>

      <section className="main-workspace" data-testid="workspace">
        {activeNav === "new" && (
          <NewTaskView
            selectedSource={selectedSource}
            mode={mode}
            includeSubfolders={includeSubfolders}
            boundaryAccepted={boundaryAccepted}
            onSelectSource={setSelectedSource}
            onModeChange={(value) => setMode(asValue(value) || value)}
            onIncludeSubfoldersChange={(value) => setIncludeSubfolders(asBoolean(value))}
            onBoundaryChange={(value) => setBoundaryAccepted(asBoolean(value))}
            onStart={startTask}
            desktopReady={desktopReady}
            desktopStatus={desktopStatus}
            demoMode={demoMode}
            onChooseFile={chooseDesktopFile}
            onToast={showToast}
          />
        )}
        {activeNav === "rules" && (
          <RuleLibraryView
            rules={rules}
            setRules={setRules}
            builtinExplanations={builtinRuleExplanations}
            activeTab={ruleTab}
            onActiveTabChange={setRuleTab}
            addRequest={ruleAddRequest}
            showTabs={!expanded}
            focusRuleId={focusRuleId}
            returnContext={returnContext}
            hasActiveTask={Boolean(desktopTaskId)}
            onReturnToReview={returnFromRule}
            onIncrementalApply={applyRulesIncrementallyToTask}
            persistRules={!demoMode && desktopReady}
            onToast={showToast}
          />
        )}
        {activeNav === "tasks" && historyView === "current" && batchSession?.phase === "completed" && (
          <BatchSummaryWorkspace session={batchSession} onNewTask={startNewAfterBatch} onViewHistory={showAllHistory} />
        )}
        {activeNav === "tasks" && historyView === "current" && batchSession?.phase !== "completed" && (
          <div className={batchSession ? "batch-task-shell" : "single-task-shell"}>
            {batchSession && (
              <BatchContextBar
                session={batchSession}
                onContinue={continueBatch}
                onRetry={retryBatchItem}
                onSkip={skipBatchItem}
              />
            )}
            <div className="batch-task-flow"><TaskFlowView model={taskFlowModel} actions={taskFlowActions} /></div>
          </div>
        )}
        {activeNav === "tasks" && historyView === "history" && (
          <HistoryWorkspace
            history={history}
            selectedId={selectedHistoryId}
            output={taskOutputFiles}
            onSelect={(id) => { setSelectedHistoryId(id); setActiveTaskId(id); }}
            onContinue={continueHistory}
            onRetry={retryHistory}
            onViewResult={viewHistoryResult}
            onDelete={setDeleteTarget}
            onBackCurrent={() => selectTask("current")}
          />
        )}
      </section>

      {toast && (
        <div className={`toast ${toast.tone || "success"}`} role="status" aria-live="polite">
          {toast.tone === "error" ? <CircleAlert size={18} /> : <CheckCircle2 size={18} />}{toast.message}
        </div>
      )}
      <ConfirmDialog item={deleteTarget} onCancel={() => setDeleteTarget(null)} onConfirm={confirmDeleteHistory} />
    </main>
  );
}
