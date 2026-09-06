import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  CircleAlert,
  FileCheck2,
  FileOutput,
  FileText,
  FolderOpen,
  HardDrive,
  Image as ImageIcon,
  ListChecks,
  LoaderCircle,
  Plus,
  RefreshCcw,
  ScanSearch,
  ShieldCheck,
  Sheet,
  Trash2,
  WandSparkles,
  X,
  XCircle,
} from "lucide-react";
import { outputFiles as fallbackOutputFiles, scanStages as fallbackScanStages } from "../prototypeData.js";
import "./task-flow.css";

const STEP_LABELS = ["选文件", "自动检查", "确认处理", "生成文件"];
const GENERATION_STAGES = [
  { id: "copy", label: "生成脱敏稿", detail: "按已确认结果生成同格式副本" },
  { id: "local", label: "整理本地保管文件", detail: "生成映射表和技术检查报告" },
  { id: "rescan", label: "重新检查实际结果", detail: "检查副本、图片、隐藏对象和输出结构" },
  { id: "finish", label: "整理任务结果", detail: "只在最终检查通过后提供结果入口" },
];

const STEP_BY_STATE = {
  idle: 1,
  source_ready: 1,
  queue_ready: 1,
  checking: 2,
  blocked: 2,
  failed: 2,
  cancelled: 2,
  review_required: 3,
  review: 3,
  ready_to_generate: 4,
  generating: 4,
  rescanning: 4,
  check_failed: 4,
  completed: 4,
};

const RESOLUTION_LABELS = {
  adopt: "已采用建议",
  edit: "已修改",
  keep: "已保留原文",
  delete: "已删除",
  automatic: "已自动处理",
};

function normalizeStep(step, model) {
  if (Number.isFinite(Number(step))) return Math.max(1, Math.min(4, Number(step)));
  const state = step || model.generationState || model.scanState || "idle";
  return STEP_BY_STATE[state] || 1;
}

function normalizeStageIndex(value, stages, fallback = 0) {
  if (typeof value === "string") {
    const index = stages.findIndex((stage) => stage.id === value);
    return index < 0 ? fallback : index;
  }
  if (Number.isFinite(Number(value))) return Math.max(0, Math.min(stages.length - 1, Number(value)));
  return fallback;
}

function getResolution(resolutions, findingId) {
  const value = resolutions?.[findingId];
  if (!value) return null;
  if (typeof value === "string") return { action: value };
  return value;
}

function isResolved(resolutions, findingId) {
  return Boolean(getResolution(resolutions, findingId));
}

function sourceIcon(type) {
  if (type === "XLSX") return Sheet;
  if (type === "文件夹") return FolderOpen;
  return FileText;
}

function categoryIcon(category) {
  if (category === "图片") return ImageIcon;
  if (category === "隐藏内容") return ShieldCheck;
  if (category === "组合风险") return ListChecks;
  return FileText;
}

function action(actions, name, ...args) {
  const callback = actions?.[name];
  if (typeof callback === "function") callback(...args);
}

function actionOrToast(actions, name, toastMessage, ...args) {
  if (typeof actions?.[name] === "function") actions[name](...args);
  else action(actions, "onToast", toastMessage);
}

function Stepper({ currentStep, completed }) {
  return (
    <ol className="tf-stepper" aria-label="任务处理进度">
      {STEP_LABELS.map((label, index) => {
        const stepNumber = index + 1;
        const done = completed ? stepNumber <= currentStep : stepNumber < currentStep;
        const current = stepNumber === currentStep && !completed;
        return (
          <li key={label} className={done ? "is-done" : current ? "is-current" : "is-future"} aria-current={current ? "step" : undefined}>
            <span className="tf-step-content">
              <span className="tf-step-dot" aria-hidden="true">{done ? <Check size={17} /> : stepNumber}</span>
              <span className="tf-step-label">{label}</span>
            </span>
            {index < STEP_LABELS.length - 1 && <ArrowRight className="tf-step-arrow" size={21} aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}

function SourceSummary({ model, actions }) {
  const source = model.selectedSource;
  const boundaryAcknowledged = Boolean(model.boundaryAcknowledged);
  const SourceIcon = sourceIcon(source?.type);

  return (
    <section className="tf-page tf-source-page" aria-labelledby="tf-source-title">
      <header className="tf-page-heading">
        <span className="tf-heading-icon"><FileText size={22} /></span>
        <div>
          <p className="tf-eyebrow">第 1 步</p>
          <h2 id="tf-source-title">选择要处理的文件</h2>
          <p>这里使用虚构示例演示操作，不会读取真实文件或文件内容。</p>
        </div>
      </header>

      {!source ? (
        <div className="tf-empty-state">
          <FileText size={36} aria-hidden="true" />
          <h3>还没有选择示例来源</h3>
          <p>可选择单个 DOCX、XLSX，或包含多个示例文件的文件夹队列。</p>
          <div className="tf-inline-actions">
            <button className="tf-primary-button" type="button" onClick={() => action(actions, "onChooseSource", "file")}><FileText size={17} />选择示例文件</button>
            <button className="tf-secondary-button" type="button" onClick={() => action(actions, "onChooseSource", "folder")}><FolderOpen size={17} />选择示例文件夹</button>
          </div>
        </div>
      ) : (
        <div className="tf-source-grid">
          <div className={`tf-source-card ${source.blocked ? "is-warning" : ""}`}>
            <span className="tf-source-icon"><SourceIcon size={27} /></span>
            <div className="tf-source-copy">
              <div className="tf-source-title-row"><h3>{source.name}</h3><span className="tf-type-badge">{source.type}</span></div>
              <p>{source.description || "虚构任务来源"}</p>
              <div className="tf-meta-line"><span>{source.size}</span><span>{source.kind === "folder" ? "文件夹队列" : "单个文件"}</span></div>
            </div>
            <button className="tf-text-button" type="button" onClick={() => action(actions, "onChooseSource", source.kind || "file")}>重新选择</button>
          </div>

          {source.queue?.length > 0 && (
            <div className="tf-queue-card">
              <div className="tf-card-heading"><div><p className="tf-eyebrow">文件队列</p><h3>已识别 {source.queue.length} 个项目</h3></div><span className="tf-status-pill neutral">逐个处理</span></div>
              <ul className="tf-queue-list">
                {source.queue.map((item) => (
                  <li key={item.id} className={`is-${item.state}`}>
                    <span className="tf-queue-state" aria-hidden="true">{item.state === "failed" ? <XCircle size={17} /> : item.state === "excluded" ? <CircleAlert size={17} /> : <Circle size={17} />}</span>
                    <span className="tf-queue-name">{item.name}</span>
                    <span className="tf-queue-label">{item.stateText}</span>
                    {item.reason && <span className="tf-queue-reason">{item.reason}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="tf-options-card">
            <div className="tf-option-row">
              <div><h3>处理方式</h3><p>默认保留角色、关系、结构和数量级。</p></div>
              <span className="tf-choice-value">{model.processingMode || "保留可读性（推荐）"}</span>
            </div>
            <label className="tf-acknowledgement">
              <input type="checkbox" checked={boundaryAcknowledged} onChange={(event) => action(actions, "onBoundaryAcknowledge", event.target.checked)} />
              <span><strong>我已了解处理边界</strong><small>本原型仅演示本机离线流程，不会读取、上传或生成真实文件。</small></span>
            </label>
            <div className="tf-page-actions">
              <span className="tf-local-note"><HardDrive size={16} />本机离线 · 文件不上传</span>
              <button className="tf-primary-button" type="button" disabled={!boundaryAcknowledged} onClick={() => action(actions, "onStartScan", source)}>
                开始自动检查 <ArrowRight size={17} />
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function ScanStageList({ stages, activeIndex, complete }) {
  return (
    <ol className="tf-progress-stages">
      {stages.map((stage, index) => {
        const done = complete || index < activeIndex;
        const active = !complete && index === activeIndex;
        return (
          <li key={stage.id} className={done ? "is-done" : active ? "is-active" : "is-waiting"}>
            <span className="tf-stage-glyph" aria-hidden="true">{done ? <Check size={17} /> : active ? <LoaderCircle className="tf-spin" size={18} /> : index + 1}</span>
            <span><strong>{stage.label}</strong><small>{stage.detail}</small></span>
          </li>
        );
      })}
    </ol>
  );
}

function ScanView({ model, actions }) {
  const scanState = model.scanState || "checking";
  const stages = model.scanStages?.length ? model.scanStages : fallbackScanStages;
  const activeIndex = normalizeStageIndex(model.scanStage, stages, 0);
  const source = model.selectedSource;
  const blocked = scanState === "blocked" || (source?.blocked && scanState !== "checking");
  const failed = scanState === "failed";
  const cancelled = scanState === "cancelled";
  const complete = ["complete", "completed", "review_ready", "review_required"].includes(scanState);
  const progress = Number.isFinite(Number(model.scanProgress)) ? Number(model.scanProgress) : complete ? 100 : Math.round(((activeIndex + 0.45) / stages.length) * 100);
  const categoryCounts = model.categoryCounts || model.findings?.reduce((result, finding) => ({ ...result, [finding.category]: (result[finding.category] || 0) + 1 }), {}) || {};

  if (blocked || failed || cancelled) {
    const title = blocked ? "当前文件无法继续检查" : failed ? "自动检查没有完成" : "已取消本次检查";
    const message = blocked
      ? source?.blockReason || model.scanMessage || "该示例文件不符合处理条件，请重新选择。"
      : failed
        ? model.scanMessage || "示例检查在文件结构阶段遇到异常，可重试或返回重选。"
        : "本次示例任务已停止，没有生成复核结果。";
    return (
      <section className="tf-page tf-feedback-page" aria-labelledby="tf-scan-result-title">
        <div className={`tf-feedback-card ${blocked || failed ? "is-error" : "is-neutral"}`}>
          <span className="tf-feedback-icon">{blocked || failed ? <XCircle size={28} /> : <CircleAlert size={28} />}</span>
          <p className="tf-eyebrow">第 2 步 · 自动检查</p>
          <h2 id="tf-scan-result-title">{title}</h2>
          <p>{message}</p>
          <div className="tf-inline-actions">
            {(failed || cancelled) && <button className="tf-primary-button" type="button" onClick={() => action(actions, "onRetryScan")}><RefreshCcw size={17} />重新检查</button>}
            <button className="tf-secondary-button" type="button" onClick={() => action(actions, "onBackToNew")}><ArrowLeft size={17} />返回重新选择</button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="tf-page tf-scan-page" aria-labelledby="tf-scan-title">
      <header className="tf-page-heading">
        <span className="tf-heading-icon"><ScanSearch size={22} /></span>
        <div>
          <p className="tf-eyebrow">第 2 步</p>
          <h2 id="tf-scan-title">{complete ? "自动检查已完成" : "正在本机自动检查"}</h2>
          <p>{complete ? "已整理需要人工确认的项目，自动清理结果也会在复核页说明。" : `正在检查 ${source?.name || "虚构示例文件"}，期间不会上传任何内容。`}</p>
        </div>
      </header>

      <div className="tf-scan-card">
        <div className="tf-progress-heading">
          <div><strong>{complete ? "4 项检查已完成" : stages[activeIndex]?.label}</strong><span>{complete ? "可以进入确认处理" : stages[activeIndex]?.detail}</span></div>
          <span className="tf-progress-number">{Math.max(0, Math.min(100, progress))}%</span>
        </div>
        <div className="tf-progress-track" aria-label={`检查进度 ${progress}%`}><span style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} /></div>
        <ScanStageList stages={stages} activeIndex={activeIndex} complete={complete} />

        {complete && (
          <div className="tf-scan-summary">
            <div><strong>{model.findings?.length || 0}</strong><span>需要确认</span></div>
            <div><strong>{categoryCounts["文字"] || 0}</strong><span>文字</span></div>
            <div><strong>{categoryCounts["图片"] || 0}</strong><span>图片</span></div>
            <div><strong>{(categoryCounts["隐藏内容"] || 0) + (categoryCounts["组合风险"] || 0)}</strong><span>其他风险</span></div>
          </div>
        )}

        <div className="tf-page-actions">
          <button className="tf-text-button tf-back-step" type="button" onClick={() => action(actions, "onPreviousStep")}><ArrowLeft size={16} />返回上一步</button>
          {complete ? (
            <button className="tf-primary-button" type="button" onClick={() => action(actions, "onContinueReview")}>进入确认处理 <ArrowRight size={17} /></button>
          ) : (
            <button className="tf-secondary-button" type="button" onClick={() => action(actions, "onCancelScan")}><X size={17} />取消检查</button>
          )}
        </div>
      </div>
    </section>
  );
}

function FindingValue({ finding, selected, resolution, replacement, onSelect }) {
  const actionName = resolution?.action;
  const visibleValue = actionName === "keep" ? finding.original : actionName === "delete" ? "已删除" : actionName ? replacement || finding.suggestion : finding.original;
  return (
    <button
      className={`tf-entity ${selected ? "is-selected" : ""} ${actionName ? "is-resolved" : ""}`}
      data-finding-id={finding.id}
      type="button"
      onClick={() => onSelect(finding.id)}
      aria-label={`查看 ${finding.original} 的处理建议`}
    >
      {visibleValue}
    </button>
  );
}

function previewRanges(block, findings, selectedFindingId) {
  const candidates = findings.flatMap((finding) => (finding.locations || [])
    .filter((location) => location.blockId === block.id && Number.isInteger(location.start) && Number.isInteger(location.end) && location.start >= 0 && location.end > location.start && location.end <= block.text.length)
    .map((location) => ({ finding, start: location.start, end: location.end })));
  candidates.sort((left, right) => {
    const selectedOrder = Number(right.finding.id === selectedFindingId) - Number(left.finding.id === selectedFindingId);
    if (selectedOrder) return selectedOrder;
    return left.start - right.start || right.end - left.end;
  });
  const accepted = [];
  candidates.forEach((candidate) => {
    if (accepted.some((item) => candidate.start < item.end && candidate.end > item.start)) return;
    accepted.push(candidate);
  });
  return accepted.sort((left, right) => left.start - right.start);
}

function PreviewBlock({ block, findings, resolutions, replacements, selectedFindingId, onSelectFinding }) {
  const ranges = previewRanges(block, findings, selectedFindingId);
  const content = [];
  let cursor = 0;
  ranges.forEach(({ finding, start, end }) => {
    if (start > cursor) content.push(block.text.slice(cursor, start));
    content.push(
      <FindingValue
        key={`${block.id}-${finding.id}-${start}`}
        finding={finding}
        selected={selectedFindingId === finding.id}
        resolution={getResolution(resolutions, finding.id)}
        replacement={replacements?.[finding.id]}
        onSelect={onSelectFinding}
      />,
    );
    cursor = end;
  });
  if (cursor < block.text.length) content.push(block.text.slice(cursor));
  const styleId = String(block.style?.styleId || "").toLowerCase();
  const isHeading = styleId.includes("heading") || styleId.includes("title") || styleId.includes("标题");
  return <section data-preview-block-id={block.id}>{isHeading ? <h2>{content}</h2> : <p>{content}</p>}</section>;
}

function DocumentPreview({ findings, resolutions, replacements, selectedFindingId, onSelectFinding, preview, sourceName }) {
  const textFindings = findings.filter((finding) => finding.category === "文字");
  const person = textFindings[0];
  const company = textFindings[1];
  const place = textFindings[2];
  const manualFindings = textFindings.slice(3);
  const imageFinding = findings.find((finding) => finding.category === "图片");
  const otherFindings = findings.filter((finding) => !["文字", "图片"].includes(finding.category));
  const entity = (finding, fallback) => finding ? (
    <FindingValue
      finding={finding}
      selected={selectedFindingId === finding.id}
      resolution={getResolution(resolutions, finding.id)}
      replacement={replacements?.[finding.id]}
      onSelect={onSelectFinding}
    />
  ) : fallback;

  if (preview?.blocks?.length) {
    const blocks = preview.blocks.filter((block) => block?.id && typeof block.text === "string" && block.text.length > 0);
    const titleIndex = blocks.findIndex((block) => {
      const styleId = String(block.style?.styleId || "").toLowerCase();
      return styleId.includes("title") || styleId === "heading1" || styleId === "heading 1" || styleId === "标题1";
    });
    const titleBlock = titleIndex >= 0 ? blocks[titleIndex] : null;
    const documentTitle = titleBlock?.text || String(sourceName || "文档内容预览").replace(/\.docx$/i, "");
    const displayedBlocks = blocks.filter((_block, index) => index !== titleIndex);
    const anchoredFindingIds = new Set(blocks.flatMap((block) => previewRanges(block, findings, selectedFindingId).map((item) => item.finding.id)));
    const unanchoredFindings = findings.filter((finding) => !anchoredFindingIds.has(finding.id) && finding.category !== "图片");
    return (
      <article className="tf-document" aria-label="DOCX 正文预览">
        <div className="tf-document-chip"><FileText size={15} />原文件只读</div>
        <h1>{documentTitle}</h1>
        {displayedBlocks.map((block) => <PreviewBlock key={block.id} block={block} findings={findings} resolutions={resolutions} replacements={replacements} selectedFindingId={selectedFindingId} onSelectFinding={onSelectFinding} />)}
        {imageFinding && (
          <section>
            <h2>附件图片</h2>
            <button data-finding-id={imageFinding.id} className={`tf-image-placeholder ${selectedFindingId === imageFinding.id ? "is-selected" : ""} ${isResolved(resolutions, imageFinding.id) ? "is-resolved" : ""}`} type="button" onClick={() => onSelectFinding(imageFinding.id)}>
              <span className="tf-image-mark"><ImageIcon size={25} /><small>{imageFinding.original || "文档图片"}</small></span>
              <span className="tf-mask-box">待处理区域</span>
            </button>
          </section>
        )}
        {unanchoredFindings.length > 0 && (
          <section className="tf-technical-section">
            <h2>其他检查结果</h2>
            <div className="tf-technical-list">
              {unanchoredFindings.map((finding) => {
                const Icon = categoryIcon(finding.category);
                return <button key={finding.id} data-finding-id={finding.id} type="button" className={`${selectedFindingId === finding.id ? "is-selected" : ""} ${isResolved(resolutions, finding.id) ? "is-resolved" : ""}`} onClick={() => onSelectFinding(finding.id)}><Icon size={17} /><span><strong>{finding.original}</strong><small>{finding.location}</small></span><ChevronRight size={16} /></button>;
              })}
            </div>
          </section>
        )}
      </article>
    );
  }

  return (
    <article className="tf-document" aria-label="虚构项目方案正文预览">
      <div className="tf-document-chip"><FileText size={15} />原文件只读</div>
      <h1>虚构项目方案</h1>
      <section>
        <h2>1．项目背景</h2>
        <p>为提升企业内部协作效率，特提出本项目方案。项目由 {entity(person, "陈顾问")} 牵头，联合 {entity(company, "合作单位")} 共同推进，并计划在 {entity(place, "某城市")} 实施试点。</p>
      </section>
      <section>
        <h2>2．项目目标</h2>
        <ol><li>打通关键业务流程，提升数据流转效率；</li><li>建立统一协作机制，降低沟通成本；</li><li>保留角色、关系、顺序和必要数量级。</li></ol>
      </section>
      {manualFindings.length > 0 && (
        <section className="tf-manual-findings">
          <h2>用户补充的脱敏内容</h2>
          <p>{manualFindings.map((finding, index) => <span key={finding.id}>{index > 0 ? "、" : ""}{entity(finding, finding.original)}</span>)}</p>
        </section>
      )}
      {imageFinding && (
        <section>
          <h2>3．附件图片</h2>
          <button data-finding-id={imageFinding.id} className={`tf-image-placeholder ${selectedFindingId === imageFinding.id ? "is-selected" : ""} ${isResolved(resolutions, imageFinding.id) ? "is-resolved" : ""}`} type="button" onClick={() => onSelectFinding(imageFinding.id)}>
            <span className="tf-image-mark"><ImageIcon size={25} /><small>虚构确认页图片</small></span>
            <span className="tf-mask-box">待处理区域</span>
          </button>
        </section>
      )}
      {otherFindings.length > 0 && (
        <section className="tf-technical-section">
          <h2>其他检查结果</h2>
          <div className="tf-technical-list">
            {otherFindings.map((finding) => {
              const Icon = categoryIcon(finding.category);
              return (
                <button key={finding.id} data-finding-id={finding.id} type="button" className={`${selectedFindingId === finding.id ? "is-selected" : ""} ${isResolved(resolutions, finding.id) ? "is-resolved" : ""}`} onClick={() => onSelectFinding(finding.id)}>
                  <Icon size={17} /><span><strong>{finding.original}</strong><small>{finding.location}</small></span><ChevronRight size={16} />
                </button>
              );
            })}
          </div>
        </section>
      )}
    </article>
  );
}

function SuggestionCard({ finding, resolution, replacement, editing, editValue, rememberDecision, onRememberChange, position, actions }) {
  if (!finding) return null;
  const mandatory = Boolean(finding.rule?.mandatory);
  const resolved = Boolean(resolution);
  const replacementValue = replacement ?? finding.suggestion;
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const ruleSource = finding.rule?.source === "fixed" ? "本机固定替换" : finding.rule?.source === "standard" ? "本机判断标准" : "系统识别说明";
  const openRule = (intent = "view") => action(actions, "onOpenRule", finding.rule?.id, { intent, findingId: finding.id, finding });
  const remember = (decisionAction, value) => {
    if (rememberDecision) action(actions, "onRememberDecision", finding, decisionAction, value);
  };

  useEffect(() => setEvidenceOpen(false), [finding.id]);

  return (
    <aside className="tf-suggestion-card" style={position} aria-label={`处理 ${finding.original}`}>
      <div className="tf-suggestion-head">
        <div><p className="tf-eyebrow">处理建议</p><h3>{finding.category} · {finding.section}</h3></div>
        <div className="tf-badge-row">
          <span className={`tf-status-pill ${mandatory ? "danger" : "warning"}`}>{mandatory ? "强制执行" : finding.severity}</span>
          {resolved && <span className="tf-status-pill success">{RESOLUTION_LABELS[resolution.action] || "已处理"}</span>}
        </div>
      </div>

      <dl className="tf-evidence-list compact">
        <div><dt>原内容</dt><dd>{finding.original}</dd></div>
        <div><dt>建议结果</dt><dd className="tf-suggested-value">{replacementValue}</dd></div>
      </dl>

      <button className={`tf-evidence-toggle ${evidenceOpen ? "open" : ""}`} type="button" onClick={() => setEvidenceOpen((value) => !value)} aria-expanded={evidenceOpen}>
        <span>查看引用规则与判断依据</span><ChevronRight size={16} />
      </button>
      {evidenceOpen && (
        <div className="tf-rule-evidence-panel">
          <dl className="tf-evidence-list">
            <div><dt>引用规则</dt><dd><button className="tf-rule-link" type="button" onClick={() => openRule("view")}>{finding.rule?.type || "系统识别"} · {finding.rule?.name || "未命名规则"}</button></dd></div>
            <div><dt>版本/来源</dt><dd>{finding.rule?.revision || "当前"} · {ruleSource}</dd></div>
            <div><dt>判断条件</dt><dd>{finding.rule?.matchSummary || "根据当前内容和位置判断"}</dd></div>
            <div><dt>判断依据</dt><dd>{finding.basis || finding.detail || "根据当前任务中的出现位置和语义关系给出建议。"}</dd></div>
          </dl>
          <button className="tf-text-button" type="button" onClick={() => openRule("view")}>打开完整规则</button>
        </div>
      )}

      {editing ? (
        <div className="tf-edit-panel">
          <label htmlFor={`tf-edit-${finding.id}`}>替换为</label>
          <input id={`tf-edit-${finding.id}`} value={editValue ?? replacementValue} onChange={(event) => action(actions, "onEditValue", event.target.value, finding.id)} autoFocus />
          <button className="tf-primary-button compact" type="button" onClick={() => { remember("edit", editValue ?? replacementValue); action(actions, "onSaveEdit", finding.id, editValue ?? replacementValue); }}>保存修改</button>
          <button className="tf-icon-button" type="button" onClick={() => action(actions, "onCancelEdit", finding.id)} aria-label="取消修改"><X size={17} /></button>
        </div>
      ) : (
        <>
          {!resolved && (
            <label className="tf-remember-choice">
              <input type="checkbox" checked={rememberDecision} onChange={(event) => onRememberChange(event.target.checked)} />
              <span>以后遇到同类内容都这样处理</span>
            </label>
          )}
          <div className="tf-suggestion-actions">
            {!resolved && <button className="tf-primary-button compact" type="button" onClick={() => { remember("adopt", replacementValue); action(actions, "onApplySuggestion", finding.id); }}>采用建议</button>}
            {!resolved && <button className="tf-secondary-button compact" type="button" onClick={() => action(actions, "onStartEdit", finding.id)}>修改</button>}
            {!resolved && <button className="tf-secondary-button compact" type="button" disabled={mandatory} aria-describedby={mandatory ? `tf-mandatory-${finding.id}` : undefined} onClick={() => action(actions, "onKeepOriginal", finding.id)}>保留原文</button>}
            {!resolved && <button className="tf-secondary-button compact danger-text" type="button" onClick={() => action(actions, "onDeleteFinding", finding.id)}><Trash2 size={15} />删除</button>}
          </div>
          {mandatory && !resolved && <p className="tf-mandatory-note" id={`tf-mandatory-${finding.id}`}><CircleAlert size={15} />该项命中强制规则，不能保留原文；可采用建议、修改或删除。</p>}
        </>
      )}
    </aside>
  );
}

function AddFindingControl({ onAdd }) {
  const [original, setOriginal] = useState("项目编号 HX-2048");
  const [suggestion, setSuggestion] = useState("项目编号 P-001");
  const detailsRef = useRef(null);
  const close = () => { if (detailsRef.current) detailsRef.current.open = false; };
  return (
    <details className="tf-add-control" ref={detailsRef}>
      <summary className="tf-secondary-button compact"><Plus size={16} />添加脱敏内容</summary>
      <section className="tf-add-popover" role="dialog" aria-labelledby="tf-add-title">
        <div className="tf-add-dialog-head"><div><p className="tf-eyebrow">当前任务</p><h3 id="tf-add-title">添加脱敏内容</h3></div><button className="tf-icon-button" type="button" onClick={close} aria-label="关闭添加脱敏内容"><X size={17} /></button></div>
        <p>补充自动检查未识别的虚构内容，添加后会进入右侧待确认列表。</p>
        <label><span>要脱敏的内容</span><input value={original} onChange={(event) => setOriginal(event.target.value)} autoFocus /></label>
        <label><span>建议结果</span><input value={suggestion} onChange={(event) => setSuggestion(event.target.value)} /></label>
        <div className="tf-add-dialog-actions"><button className="tf-secondary-button" type="button" onClick={close}>取消</button><button className="tf-primary-button" type="button" onClick={() => { if (onAdd({ original, suggestion }) !== false) close(); }}><Plus size={16} />添加到待确认</button></div>
      </section>
    </details>
  );
}

function FindingRail({ findings, resolutions, selectedFindingId, onSelectFinding }) {
  const pendingCount = findings.filter((finding) => !isResolved(resolutions, finding.id)).length;
  return (
    <aside className="tf-finding-rail" aria-label="发现项目列表">
      <div className="tf-finding-rail-head">
        <div><p className="tf-eyebrow">发现列表</p><h3>{pendingCount > 0 ? `待确认 ${pendingCount}` : "已全部确认"}</h3></div>
        {pendingCount > 0 ? <CircleAlert size={21} /> : <CheckCircle2 size={21} />}
      </div>
      <div className="tf-finding-list">
        {findings.map((finding, index) => {
          const Icon = categoryIcon(finding.category);
          const resolution = getResolution(resolutions, finding.id);
          return (
            <button key={finding.id} type="button" className={`${selectedFindingId === finding.id ? "is-selected" : ""} ${resolution ? "is-resolved" : ""}`} onClick={() => onSelectFinding(finding.id)}>
              <span className="tf-finding-index">{resolution ? <Check size={15} /> : index + 1}</span>
              <span className="tf-finding-copy"><strong><Icon size={15} />{finding.category} · {finding.section}</strong><small>{resolution ? RESOLUTION_LABELS[resolution.action] || "已处理" : finding.original}</small></span>
              {finding.rule?.mandatory && <span className="tf-mini-badge">强制</span>}
            </button>
          );
        })}
      </div>
    </aside>
  );
}

function ReviewView({ model, actions }) {
  const findings = model.findings || [];
  const resolutions = model.resolutions || {};
  const replacements = model.replacements || {};
  const fallbackSelection = findings.find((finding) => !isResolved(resolutions, finding.id))?.id || findings[0]?.id;
  const selectedFindingId = model.selectedFindingId || fallbackSelection;
  const selectedFinding = findings.find((finding) => finding.id === selectedFindingId) || findings[0];
  const selectedResolution = selectedFinding ? getResolution(resolutions, selectedFinding.id) : null;
  const pendingCount = findings.filter((finding) => !isResolved(resolutions, finding.id)).length;
  const [rememberDecision, setRememberDecision] = useState(false);
  const [manualMode, setManualMode] = useState(true);
  const [cardPosition, setCardPosition] = useState({ top: 20, left: 20 });
  const documentAreaRef = useRef(null);

  useEffect(() => setRememberDecision(false), [selectedFindingId]);
  useEffect(() => {
    const area = documentAreaRef.current;
    if (!area || !selectedFindingId) return undefined;
    const updatePosition = () => {
      const anchor = area.querySelector(`[data-finding-id="${selectedFindingId}"]`);
      if (!anchor) return;
      const areaRect = area.getBoundingClientRect();
      const anchorRect = anchor.getBoundingClientRect();
      const cardWidth = Math.min(360, Math.max(220, area.clientWidth - 24));
      const rightSpace = areaRect.right - anchorRect.right;
      const preferredLeft = rightSpace >= cardWidth + 18 ? anchorRect.right - areaRect.left + area.scrollLeft + 10 : anchorRect.left - areaRect.left + area.scrollLeft;
      const left = Math.max(12, Math.min(preferredLeft, area.scrollWidth - cardWidth - 12));
      const top = Math.max(12, anchorRect.bottom - areaRect.top + area.scrollTop + 8);
      setCardPosition({ top, left, width: cardWidth });
    };
    updatePosition();
    area.addEventListener("scroll", updatePosition, { passive: true });
    window.addEventListener("resize", updatePosition);
    return () => { area.removeEventListener("scroll", updatePosition); window.removeEventListener("resize", updatePosition); };
  }, [selectedFindingId, manualMode, findings.length]);

  if (!findings.length) {
    return (
      <section className="tf-page tf-feedback-page">
        <div className="tf-feedback-card is-neutral"><CircleAlert size={28} /><h2>还没有复核项目</h2><p>请先完成自动检查，再进入确认处理。</p><button className="tf-secondary-button" type="button" onClick={() => action(actions, "onRetryScan")}>返回自动检查</button></div>
      </section>
    );
  }

  return (
    <section className="tf-review-page" aria-label="确认处理">
      <div className="tf-review-toolbar">
        <div><p className="tf-eyebrow">第 3 步 · 确认处理</p><h2>{model.selectedSource?.name || "虚构项目方案.docx"}</h2></div>
        <div className="tf-review-toolbar-actions">
          <AddFindingControl onAdd={(payload) => actions?.onAddFinding?.(payload)} />
          <div className="tf-review-counts">
            {["文字", "图片", "隐藏内容", "组合风险"].map((category) => <span key={category}>{category} <strong>{findings.filter((finding) => finding.category === category && !isResolved(resolutions, finding.id)).length}</strong></span>)}
          </div>
        </div>
      </div>

      <div className={`tf-review-layout ${manualMode ? "manual" : "quick"}`}>
        <div className="tf-document-area" ref={documentAreaRef}>
          <SuggestionCard
            finding={selectedFinding}
            resolution={selectedResolution}
            replacement={selectedFinding ? replacements[selectedFinding.id] : ""}
            editing={model.editingFindingId === selectedFinding?.id}
            editValue={model.editValue}
            rememberDecision={rememberDecision}
            onRememberChange={setRememberDecision}
            position={cardPosition}
            actions={actions}
          />
          <DocumentPreview findings={findings} resolutions={resolutions} replacements={replacements} selectedFindingId={selectedFindingId} preview={model.documentPreview} sourceName={model.selectedSource?.name} onSelectFinding={(id) => action(actions, "onSelectFinding", id)} />
        </div>
        {manualMode && <FindingRail findings={findings} resolutions={resolutions} selectedFindingId={selectedFindingId} onSelectFinding={(id) => action(actions, "onSelectFinding", id)} />}
      </div>

      <footer className="tf-review-footer">
        <div className="tf-review-status"><button className="tf-text-button tf-back-step" type="button" onClick={() => action(actions, "onPreviousStep")}><ArrowLeft size={16} />返回上一步</button><CheckCircle2 size={18} /><span>已处理 <strong>{findings.length - pendingCount}</strong> 项 · 还剩 <strong>{pendingCount}</strong> 项需要确认</span></div>
        <div className="tf-inline-actions">
          <button className="tf-secondary-button compact" type="button" onClick={() => setManualMode((value) => !value)}>{manualMode ? "隐藏修改列表" : "显示修改列表"}</button>
          {pendingCount > 0 ? (
            <button className="tf-primary-button one-click" type="button" onClick={() => action(actions, "onApplyAllAndContinue")}><WandSparkles size={17} />一键采用全部建议并继续</button>
          ) : (
            <button className="tf-primary-button" type="button" onClick={() => action(actions, "onGoGenerate")}>进入生成文件 <ArrowRight size={17} /></button>
          )}
        </div>
      </footer>
    </section>
  );
}

function OutputGroups({ files, actions, interactive = false }) {
  const groups = [
    { id: "ai", title: "给 AI 的文件", subtitle: "AI交付", icon: FileOutput, files: files?.ai || [] },
    { id: "local", title: "仅本地保管", subtitle: "本地保管", icon: HardDrive, files: files?.local || [] },
  ];
  return (
    <div className="tf-output-grid">
      {groups.map((group) => {
        const Icon = group.icon;
        return (
          <section key={group.id} className={`tf-output-card ${group.id === "local" ? "is-local" : ""}`}>
            <div className="tf-output-head"><span><Icon size={21} /></span><div><p>{group.subtitle}</p><h3>{group.title}</h3></div></div>
            <ul>
              {group.files.map((file) => (
                <li key={file.id || file.name}>
                  <span className="tf-output-file-icon">{file.name?.endsWith(".xlsx") ? <Sheet size={18} /> : <FileText size={18} />}</span>
                  <span><strong>{file.name}</strong><small>{file.note}</small></span>
                  {file.danger && <span className="tf-danger-badge">严禁上传</span>}
                  {interactive && <button className="tf-icon-button" type="button" aria-label={`查看 ${file.name}`} title="查看示例结果" onClick={() => actionOrToast(actions, "onViewOutput", `已打开 ${file.name} 的示例摘要`, file, group.id)}><ChevronRight size={17} /></button>}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function GenerationProgress({ model }) {
  const state = model.generationState;
  const fallback = state === "rescanning" ? 2 : 0;
  const activeIndex = normalizeStageIndex(model.generationStage, GENERATION_STAGES, fallback);
  const progress = Number.isFinite(Number(model.generationProgress)) ? Number(model.generationProgress) : Math.round(((activeIndex + 0.45) / GENERATION_STAGES.length) * 100);
  return (
    <div className="tf-generation-progress">
      <div className="tf-progress-heading"><div><strong>{state === "rescanning" ? "正在重新检查实际结果" : model.isDesktopTask ? "正在生成本机结果" : "正在生成示例结果"}</strong><span>{GENERATION_STAGES[activeIndex]?.detail}</span></div><span className="tf-progress-number">{progress}%</span></div>
      <div className="tf-progress-track"><span style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} /></div>
      <ScanStageList stages={GENERATION_STAGES} activeIndex={activeIndex} complete={false} />
      <p className="tf-generation-note"><LoaderCircle className="tf-spin" size={17} />结果卡片只会在最终检查通过后出现。</p>
    </div>
  );
}

function GenerateView({ model, actions }) {
  const findings = model.findings || [];
  const pendingCount = findings.filter((finding) => !isResolved(model.resolutions || {}, finding.id)).length;
  const state = model.generationState || "ready";
  const files = model.outputFiles || fallbackOutputFiles;

  if (state === "completed") {
    return (
      <section className="tf-page tf-result-page" aria-labelledby="tf-result-title">
        <div className="tf-complete-heading">
          <span><CheckCircle2 size={30} /></span>
          <div><p className="tf-eyebrow">第 4 步 · 已完成</p><h2 id="tf-result-title">技术检查已完成</h2><p>技术检查已完成，仍需按单位制度确认是否可外发。</p></div>
        </div>
        {model.resultRecord && <div className="tf-result-record"><FileCheck2 size={19} /><span><strong>{model.resultRecord.name || model.selectedSource?.name}</strong><small>{model.resultRecord.summary || "示例结果已写入任务历史"} {model.resultRecord.time ? `· ${model.resultRecord.time}` : ""}</small></span></div>}
        {files.folderName && <div className="tf-output-folder"><FolderOpen size={18} /><span>输出文件夹</span><strong>{files.folderName}</strong></div>}
        <OutputGroups files={files} actions={actions} interactive />
        <div className="tf-result-warning"><AlertTriangle size={18} /><span><strong>请只将“AI交付”中的分析副本交给外部 AI。</strong>“本地保管”中的映射表含真实原值，严禁上传。</span></div>
        <div className="tf-page-actions">
          <button className="tf-secondary-button" type="button" onClick={() => action(actions, "onPreviousStep")}><ArrowLeft size={17} />返回确认处理</button>
          <button className="tf-secondary-button" type="button" onClick={() => action(actions, "onBackToNew")}><RefreshCcw size={17} />再处理一个文件</button>
          <button className="tf-primary-button" type="button" onClick={() => action(actions, "onViewHistory")}><ListChecks size={17} />查看任务历史</button>
        </div>
      </section>
    );
  }

  if (state === "check_failed") {
    return (
      <section className="tf-page tf-feedback-page" aria-labelledby="tf-check-failed-title">
        <div className="tf-feedback-card is-error wide">
          <span className="tf-feedback-icon"><XCircle size={28} /></span>
          <p className="tf-eyebrow">最终检查未通过</p>
          <h2 id="tf-check-failed-title">结果暂不可用</h2>
          <p>{model.generationMessage || "在示例副本中发现一处仍需处理的内容。结果卡片已隐藏，请返回相关项修复后重试。"}</p>
          {model.failedFindingId && <p className="tf-failure-reference"><AlertTriangle size={16} />相关项目：{findings.find((finding) => finding.id === model.failedFindingId)?.section || model.failedFindingId}</p>}
          <div className="tf-inline-actions">
            <button className="tf-primary-button" type="button" onClick={() => action(actions, "onContinueReview", model.failedFindingId)}><ArrowLeft size={17} />返回相关项</button>
            <button className="tf-secondary-button" type="button" onClick={() => action(actions, "onRescan")}><RefreshCcw size={17} />修复后重新检查</button>
          </div>
        </div>
      </section>
    );
  }

  if (["generating", "rescanning"].includes(state)) {
    return (
      <section className="tf-page tf-generate-page" aria-labelledby="tf-generating-title">
        <header className="tf-page-heading"><span className="tf-heading-icon"><WandSparkles size={22} /></span><div><p className="tf-eyebrow">第 4 步</p><h2 id="tf-generating-title">{state === "rescanning" ? "重新检查实际结果" : "生成文件"}</h2><p>{model.isDesktopTask ? "正在本机生成文件并检查实际落盘结果。" : "这是确定性的原型进度，不会写入真实文件。"}</p></div></header>
        <GenerationProgress model={model} />
        <div className="tf-page-actions"><button className="tf-secondary-button" type="button" onClick={() => action(actions, "onPreviousStep")}><ArrowLeft size={17} />返回上一步</button></div>
      </section>
    );
  }

  if (pendingCount > 0) {
    return (
      <section className="tf-page tf-feedback-page">
        <div className="tf-feedback-card is-warning"><CircleAlert size={28} /><p className="tf-eyebrow">生成前检查</p><h2>还有 {pendingCount} 项需要确认</h2><p>只有全部待办都完成后才能生成结果，强制规则和最终检查不能跳过。</p><button className="tf-primary-button" type="button" onClick={() => action(actions, "onContinueReview")}><ArrowLeft size={17} />返回确认处理</button></div>
      </section>
    );
  }

  return (
    <section className="tf-page tf-generate-page" aria-labelledby="tf-generate-title">
      <header className="tf-page-heading"><span className="tf-heading-icon"><FileOutput size={22} /></span><div><p className="tf-eyebrow">第 4 步</p><h2 id="tf-generate-title">确认生成内容</h2><p>全部待办已确认。生成后会先重新检查实际结果，再提供结果入口。</p></div></header>
      {files.folderName && <div className="tf-output-folder"><FolderOpen size={18} /><span>输出文件夹</span><strong>{files.folderName}</strong></div>}
      <OutputGroups files={files} actions={actions} />
      <div className="tf-result-warning neutral"><ShieldCheck size={18} /><span>映射表和检查报告仅放在“本地保管”；界面不提供上传操作。</span></div>
      <div className="tf-page-actions">
        <button className="tf-secondary-button" type="button" onClick={() => action(actions, "onContinueReview")}><ArrowLeft size={17} />返回确认处理</button>
        <div className="tf-inline-actions">
          {!model.isDesktopTask && <button className="tf-secondary-button" type="button" onClick={() => action(actions, "onStartGeneration", true)}><AlertTriangle size={16} />模拟检查异常</button>}
          <button className="tf-primary-button" type="button" onClick={() => action(actions, "onStartGeneration", false)}>开始生成文件 <ArrowRight size={17} /></button>
        </div>
      </div>
    </section>
  );
}

export default function TaskFlowView({ model = {}, actions = {} }) {
  const currentStep = normalizeStep(model.step, model);
  const completed = model.generationState === "completed";
  let content;
  if (currentStep === 1) content = <SourceSummary model={model} actions={actions} />;
  else if (currentStep === 2) content = <ScanView model={model} actions={actions} />;
  else if (currentStep === 3) content = <ReviewView model={model} actions={actions} />;
  else content = <GenerateView model={model} actions={actions} />;

  return (
    <div className="task-flow" data-step={currentStep} data-scan-state={model.scanState || "idle"} data-generation-state={model.generationState || "idle"}>
      <Stepper currentStep={currentStep} completed={completed} />
      <div className="tf-stage-body">{content}</div>
    </div>
  );
}
