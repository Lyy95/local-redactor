import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronRight,
  FileText,
  Files,
  FolderOpen,
  FolderTree,
  HardDrive,
  Info,
  LockKeyhole,
  Search,
  Sheet,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { sampleSources } from "../prototypeData.js";
import "./new-task.css";

const sourceKindCopy = {
  file: {
    title: "选择单个文件",
    description: "从虚构 DOCX / XLSX 样例开始一项任务",
  },
  folder: {
    title: "选择文件夹",
    description: "预览包含成功、失败和排除项的虚构队列",
  },
};

function SourceGlyph({ source, size = 24 }) {
  if (source?.kind === "folder") return <FolderOpen size={size} strokeWidth={1.8} aria-hidden="true" />;
  if (source?.type === "XLSX") return <Sheet size={size} strokeWidth={1.8} aria-hidden="true" />;
  return <FileText size={size} strokeWidth={1.8} aria-hidden="true" />;
}

function QueueStateIcon({ state }) {
  if (state === "failed") return <XCircle size={16} aria-hidden="true" />;
  if (state === "excluded") return <Info size={16} aria-hidden="true" />;
  return <CheckCircle2 size={16} aria-hidden="true" />;
}

function SampleChooser({ kind, selectedId, onChoose, onClose, dialogRef }) {
  const options = sampleSources.filter((source) => source.kind === kind);
  const title = kind === "folder" ? "选择虚构文件夹" : "选择虚构文件";

  return (
    <div
      className="new-task-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="new-task-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-task-dialog-title"
        aria-describedby="new-task-dialog-note"
        ref={dialogRef}
      >
        <div className="new-task-dialog-head">
          <div>
            <p className="new-task-eyebrow">原型样例</p>
            <h2 id="new-task-dialog-title">{title}</h2>
          </div>
          <button className="new-task-icon-button" type="button" onClick={onClose} aria-label="关闭样例选择">
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        <div className="new-task-fictional-note" id="new-task-dialog-note">
          <ShieldCheck size={18} aria-hidden="true" />
          <span><strong>仅使用虚构样例</strong>，不会打开或读取你的真实文件。</span>
        </div>

        <div className="new-task-sample-list">
          {options.map((source) => {
            const isSelected = selectedId === source.id;
            return (
              <button
                className={`new-task-sample-card${isSelected ? " is-selected" : ""}${source.blocked ? " is-blocked" : ""}`}
                type="button"
                key={source.id}
                onClick={() => onChoose(source)}
                aria-pressed={isSelected}
              >
                <span className="new-task-sample-icon"><SourceGlyph source={source} size={27} /></span>
                <span className="new-task-sample-copy">
                  <span className="new-task-sample-title-row">
                    <strong>{source.name}</strong>
                    <span>{source.type}</span>
                  </span>
                  <span>{source.description}</span>
                  <small>{source.size}</small>
                </span>
                {source.blocked ? (
                  <span className="new-task-sample-state blocked"><LockKeyhole size={16} aria-hidden="true" />阻断样例</span>
                ) : isSelected ? (
                  <span className="new-task-sample-state selected"><Check size={16} aria-hidden="true" />已选择</span>
                ) : (
                  <ChevronRight className="new-task-sample-arrow" size={20} aria-hidden="true" />
                )}
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}

export default function NewTaskView({
  selectedSource,
  mode = "balanced",
  includeSubfolders = false,
  boundaryAccepted = false,
  onSelectSource,
  onModeChange,
  onIncludeSubfoldersChange,
  onBoundaryChange,
  onStart,
  desktopReady = false,
  desktopStatus = "checking",
  demoMode = false,
  onChooseFile,
  onToast,
}) {
  const [chooserOpen, setChooserOpen] = useState(false);
  const [chooserKind, setChooserKind] = useState("file");
  const [validationMessage, setValidationMessage] = useState("");
  const dialogRef = useRef(null);
  const lastTriggerRef = useRef(null);
  const boundaryRef = useRef(null);

  const source = useMemo(() => {
    if (typeof selectedSource === "string") {
      return sampleSources.find((item) => item.id === selectedSource) ?? null;
    }
    return selectedSource ?? null;
  }, [selectedSource]);

  const isFolder = source?.kind === "folder";
  const normalizedMode = mode === "strict" ? "strict" : "balanced";
  const queueSummary = useMemo(() => {
    const queue = source?.queue ?? [];
    return queue.reduce(
      (summary, item) => ({ ...summary, [item.state]: (summary[item.state] ?? 0) + 1 }),
      { ready: 0, failed: 0, excluded: 0 },
    );
  }, [source]);

  useEffect(() => {
    if (!chooserOpen) return undefined;
    const focusable = dialogRef.current?.querySelector("button");
    focusable?.focus();

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setChooserOpen(false);
        window.requestAnimationFrame(() => lastTriggerRef.current?.focus());
        return;
      }

      if (event.key === "Tab") {
        const focusableItems = Array.from(
          dialogRef.current?.querySelectorAll(
            'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
          ) ?? [],
        );
        const first = focusableItems[0];
        const last = focusableItems.at(-1);
        if (!first || !last) return;
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [chooserOpen]);

  const openChooser = (kind, trigger) => {
    lastTriggerRef.current = trigger;
    if (!demoMode) {
      if (kind === "file" && desktopReady && onChooseFile) {
        setValidationMessage("");
        onChooseFile();
        return;
      }
      const message = desktopStatus === "checking"
        ? "本地能力正在连接，请稍候再试。"
        : "本地能力未就绪，请重启应用。";
      setValidationMessage(message);
      onToast?.(message, "error");
      return;
    }
    setChooserKind(kind);
    setChooserOpen(true);
    setValidationMessage("");
  };

  const closeChooser = () => {
    setChooserOpen(false);
    window.requestAnimationFrame(() => lastTriggerRef.current?.focus());
  };

  const chooseSource = (nextSource) => {
    onSelectSource?.(nextSource);
    setValidationMessage("");
    onToast?.(`已载入虚构样例：${nextSource.name}`);
    closeChooser();
  };

  const validateAndStart = () => {
    if (!source) {
      const message = demoMode ? "请先选择一个虚构样例文件或文件夹。" : "请先选择一个本机 DOCX 文件。";
      setValidationMessage(message);
      onToast?.(message);
      return;
    }

    if (!boundaryAccepted) {
      const message = "请先确认本机处理边界，再开始检查。";
      setValidationMessage(message);
      onToast?.(message);
      boundaryRef.current?.focus();
      return;
    }

    setValidationMessage("");
    onStart?.({
      source,
      mode: normalizedMode,
      includeSubfolders: isFolder ? includeSubfolders : false,
      boundaryAccepted: true,
    });
  };

  return (
    <section className="new-task-view" aria-labelledby="new-task-title" data-testid="new-task-view">
      <header className="new-task-header compact">
        <div><p className="new-task-eyebrow">新建任务</p><h1 id="new-task-title">选择内容，开始检查</h1><p>{demoMode ? "使用虚构样例体验本机处理流程。" : "选择本机 DOCX，文件不上传。"}</p></div>
        <span className="new-task-offline-chip"><HardDrive size={17} aria-hidden="true" />本机离线 · 文件不上传</span>
      </header>

      <div className="new-task-content compact">
        <section className="new-task-section quick-source" aria-labelledby="new-task-source-title">
          <div className="new-task-quick-head"><div><h2 id="new-task-source-title">检查来源</h2><p>{demoMode ? "选择单个文件或文件夹样例" : "Gate 2 当前支持单个 DOCX 文件"}</p></div></div>
          <div className="new-task-source-actions compact">
            {Object.entries(sourceKindCopy).map(([kind, copy]) => {
              const Icon = kind === "folder" ? FolderTree : Files;
              const unavailable = !demoMode && kind === "folder";
              return <button key={kind} className={`new-task-source-button${source?.kind === kind ? " is-active" : ""}`} type="button" onClick={(event) => openChooser(kind, event.currentTarget)} aria-haspopup={demoMode ? "dialog" : undefined} disabled={unavailable} title={unavailable ? "文件夹队列将在后续阶段接入" : undefined}><Icon size={19} /><span><strong>{copy.title}</strong></span></button>;
            })}
          </div>

          {source ? (
            <div className={`new-task-selected-source compact${source.blocked ? " is-blocked" : ""}`} aria-live="polite">
              <div className="new-task-selected-summary"><span className="new-task-selected-icon"><SourceGlyph source={source} size={25} /></span><div><div className="new-task-selected-name"><strong>{source.name}</strong><span>{source.type}</span></div><p>{source.description}</p></div><button className="new-task-text-button" type="button" onClick={(event) => openChooser(source.kind, event.currentTarget)}>更换</button></div>
              {source.blocked && <div className="new-task-blocked-note" role="note"><AlertTriangle size={18} /><div><strong>加密文件阻断样例</strong><span>开始后会显示原因并允许返回重选。</span></div></div>}
              {isFolder && (
                <details className="new-task-disclosure queue">
                  <summary><span>查看 5 个文件</span><small>{queueSummary.ready} 待处理 · {queueSummary.failed} 失败 · {queueSummary.excluded} 排除</small><ChevronRight size={17} /></summary>
                  <ul className="new-task-queue-list">{source.queue.map((item) => <li key={item.id} className={`is-${item.state}`}><span className="new-task-queue-file"><SourceGlyph source={item} size={18} /><span><strong>{item.name}</strong><small>{item.type}</small></span></span><span className="new-task-queue-status"><QueueStateIcon state={item.state} /><span>{item.stateText}{item.reason ? <small>{item.reason}</small> : null}</span></span></li>)}</ul>
                </details>
              )}
            </div>
          ) : <div className="new-task-empty-source"><Search size={21} /><div><strong>还没有选择内容</strong><span>{demoMode ? "请选择文件或文件夹样例。" : "请选择一个本机 DOCX 文件。"}</span></div></div>}
        </section>

        <details className="new-task-disclosure settings">
          <summary><span>更多设置</span><small>{normalizedMode === "strict" ? "更严格" : "保留可读性（推荐）"}{isFolder && includeSubfolders ? " · 包含子文件夹" : ""}</small><ChevronRight size={17} /></summary>
          <div className="new-task-settings-body">
            <fieldset className="new-task-mode-fieldset"><legend className="new-task-sr-only">处理方式</legend><label className={`new-task-mode-card${normalizedMode === "balanced" ? " is-selected" : ""}`}><input type="radio" name="processing-mode" value="balanced" checked={normalizedMode === "balanced"} onChange={() => onModeChange?.("balanced")} /><span className="new-task-radio-mark" /><span><strong>保留可读性 <em>推荐</em></strong><small>保留角色关系和必要数量级。</small></span></label><label className={`new-task-mode-card${normalizedMode === "strict" ? " is-selected" : ""}`}><input type="radio" name="processing-mode" value="strict" checked={normalizedMode === "strict"} onChange={() => onModeChange?.("strict")} /><span className="new-task-radio-mark" /><span><strong>更严格</strong><small>减少可见细节。</small></span></label></fieldset>
            {isFolder && <label className="new-task-switch-row"><span><strong>包含子文件夹</strong></span><input type="checkbox" role="switch" checked={includeSubfolders} onChange={(event) => onIncludeSubfoldersChange?.(event.target.checked)} /><span className="new-task-switch"><span /></span></label>}
          </div>
        </details>

        <label className="new-task-boundary-line"><ShieldCheck size={19} /><input ref={boundaryRef} type="checkbox" checked={boundaryAccepted} onChange={(event) => { onBoundaryChange?.(event.target.checked); setValidationMessage(""); }} /><span><strong>原文件只读，本机处理</strong><small>外发仍需按单位制度审批</small></span></label>
        {validationMessage && <div className="new-task-validation" role="alert"><AlertTriangle size={18} />{validationMessage}</div>}
        <footer className="new-task-footer compact"><span><Info size={16} />开始后自动检查，可在结果页继续处理。</span><button className="new-task-primary" type="button" onClick={validateAndStart}>开始检查 <ChevronRight size={19} /></button></footer>
      </div>

      {chooserOpen && (
        <SampleChooser
          kind={chooserKind}
          selectedId={source?.id}
          onChoose={chooseSource}
          onClose={closeChooser}
          dialogRef={dialogRef}
        />
      )}
    </section>
  );
}
