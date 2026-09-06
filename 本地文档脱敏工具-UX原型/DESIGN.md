# 本地文档脱敏工具 UX 原型 Design Baseline

Updated: 2026-08-10

## Visual Truth

1. `references/sidebar-collapsed-reference.png` — collapsed navigation truth.
2. `references/sidebar-expanded-target.png` — corrected expanded-state truth.
3. `references/source-white-green-reference.png` — document workspace, palette, typography and content truth.
4. Current user wording — overrides every earlier mock.

## Product Context

- Desktop Windows-like local tool for ordinary office users.
- Calm, trustworthy, low-density, non-technical Chinese.
- Target: 1536 × 1024 comparison, 1440 × 900 normal, 1280 × 720 minimum.
- Status must use icon, color and text where space permits.

## Locked Layout

- Root is a two-column CSS grid: inline sidebar + `minmax(0, 1fr)` workspace.
- Collapsed sidebar: 104 px white rail, matching the supplied second image.
- Expanded sidebar: 420 px total, comprising the unchanged 104 px rail plus a 316 px inline task/history area on the same continuous white surface.
- Expanding pushes/reflows the workspace. The sidebar never uses fixed/absolute positioning to cover content.
- The expanded history area has no outer card, radius, shadow, close X, pin, backdrop or separate floating layer.
- Main workspace: title/security row, four-step row, document review, right pending rail, bottom status.

## Visual Tokens

| Token | Value | Usage |
|---|---|---|
| Primary | `#0D7C68` | Main action, active step, selected navigation |
| Primary dark | `#075F51` | Active text and hover |
| Mint selected | `#E7F4F0` | Selected `任务` tile |
| Mint border | `#B8DDD3` | Offline chip and focus accents |
| Warning | `#D97706` | Pending count and markers |
| Error | `#DC2626` | Failed historical task |
| Success | `#0B8A6A` | Technical completion only |
| Text | `#1E2328` | Primary text |
| Muted | `#667078` | Secondary text |
| Border | `#E1E5E8` | Section separation |
| Surface | `#FFFFFF` | All primary surfaces |
| Highlight | `#FDE7B2` | Fictional entity highlights |
| Radius | 8–10 px | Controls and suggestion popover only |

## Interaction Rules

- The collapsed rail exposes a dedicated `展开侧栏` icon. `任务 / 规则` only switch modules and never implicitly expand the sidebar. Expanded state exposes a dedicated collapse chevron.
- `Enter`/`Space` work on buttons; `Escape` collapses the expanded sidebar.
- No hover expansion. No automatic responsive expansion/collapse.
- Transition duration: 220 ms, ease `cubic-bezier(.2,0,0,1)`; respect reduced motion.
- Expand/collapse preserves active task, active finding, pending count, document scroll and review decisions.
- Review actions immediately update pending count, right markers and short feedback, then move to the next finding.

## Copy and Data

- Required: `本机离线 · 文件不上传`, `原文件只读`, `采用建议`, `修改`, `保留原文`, `删除`, `一键采用全部建议并继续`.
- Forbidden: `已脱密`, `可安全上传`, `绝对安全`, `100%安全` and internal strategy jargon.
- Use fictional filenames/entities and never display a full local path.

## QA

- Compare both collapsed and expanded states at the same viewport as their source.
- Measure sidebar/workspace bounding boxes to prove push layout and zero overlap.
- Test keyboard, pending-count feedback, state preservation, console errors, 1440 × 900 and 1280 × 720.

## Full-flow extension (confirmed 2026-08-10)

### Navigation and information architecture

- The 104 px rail remains the only global navigation and shows `新建 / 任务 / 规则` with one active state.
- `任务` may expose the inline 316 px task/history column. `新建` and `规则` are full workspace pages; they are never tooltip-only or toast-only placeholders.
- The task/history header is 60 px high, labels the area `任务与历史`, keeps only the collapse chevron on the right, and removes the earlier large blank block.
- Task sidebar state, active navigation, active task, workflow step, active finding, rule return target and history selection are independent states; changing one must not silently reset another.

### Four-step workspace

1. `选文件`: source cards, fictional sample chooser, file/folder queue, mode and boundary acknowledgement.
2. `自动检查`: one primary progress surface with four readable stages, completion summary, cancellation, retry and blocked feedback.
3. `确认处理`: document preview, category/filter counts, current finding card, rule citation, rationale and immediate result reflection.
4. `生成文件`: output separation, generation/rescan progress, result cards and return/history actions.

### Rule library

- Use a calm page layout with tabs for `固定替换 / 判断标准 / 系统识别说明`, a compact toolbar and table/list rows.
- Create/edit/test uses one bounded dialog. Import uses a conflict-confirmation dialog and never silently overwrites an existing rule.
- Rule status is shown through switch state plus text. Destructive actions require a confirmation dialog.
- Returning from a cited rule restores the same task and finding and shows one incremental-application result.

### Review evidence

- The suggestion card always shows a plain-language `判断依据`.
- When a local rule is responsible, show `引用规则：<规则类型> · <规则名称>` as an operable text link plus a `强制执行` badge when applicable.
- `保留原文` is disabled only for a fictional mandatory-rule example and explains why.
- `以后都这样处理` opens a prefilled rule editor; saving it returns to review and preserves unrelated decisions.

### Result and history

- Completion copy is fixed to `技术检查已完成，仍需按单位制度确认是否可外发。`
- Result cards separate `给 AI 的文件` from `仅本地保管`; `脱敏映射表.xlsx` receives a red `严禁上传` mark.
- History shows filenames, types, times, state, count summary and result availability only—never source values, reversible mappings or full paths.

## Simplified interaction refinement (confirmed 2026-08-10)

- Global rail: `任务 / 规则`. The expanded 316 px inline column is a shared module sidebar. Switching modules replaces its content without closing it; only the chevron or `Escape` collapses it.
- Task sidebar begins with a full-width `新建任务` action, then current task, folder batch and history.
- Rule sidebar begins with `新增规则`, then `固定替换 / 判断标准 / 系统识别说明` and their live counts.
- New task uses one compact source card, two small source-type buttons, a collapsed queue-details disclosure, a collapsed `更多设置` disclosure, one boundary line and one primary start button.
- Review uses a compact in-flow suggestion card. Only original value, suggestion result and primary actions are visible by default; rule evidence opens from `查看引用规则与判断依据`.
- The preferred Step-3 path is one green `一键采用全部建议并继续` button. `逐项调整` reveals the finding rail and compact per-item controls.
- Toasts are top-centered and do not obscure bottom action bars.
- Delete confirmation uses a small warning icon beside the message, with no central illustration band.
- Expand/collapse is independent from module selection: the narrow rail owns one explicit expand icon, while the secondary-sidebar header owns the collapse chevron.
- Sidebar primary actions show one short label only; do not add explanatory subtitles inside these buttons.
- Step 3 defaults to document + anchored compact popover + visible right finding list. The popover sits next to the selected entity and retains `采用建议 / 修改 / 保留原文 / 删除`.
- `查看引用规则与判断依据` is a small secondary text disclosure, never the visual focus of the popover.
- Steps 2–4 expose a clear previous-step action. `添加脱敏内容` creates a fictional user-added finding and immediately reflects it in the document, right list and pending total.
- The collapsed rail's expand control is a quiet bottom action, not a third menu tile under the logo. Step 3 does not show the redundant `采用全部普通建议` action; the single bulk path is `一键采用全部建议并继续`.
