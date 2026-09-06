# 白底绿色双态侧栏交互原型 Decision Log

## Effective

| ID | Date | Decision | Reason | Affected surfaces |
|---|---|---|---|---|
| D-001 | 2026-08-10 | White/mint/deep-green visual system is final for this prototype | User rejected other palettes and returned to the first direction | All surfaces |
| D-002 | 2026-08-10 | Collapsed sidebar is the narrow image-2 rail | Latest explicit user instruction | Sidebar |
| D-003 | 2026-08-10 | Expanded sidebar is a real grid column that pushes content | Floating drawer was the core usability problem | Sidebar/workspace |
| D-004 | 2026-08-10 | No pin, overlay, backdrop, hover opening or detached task card | Removes the indirect two-stage interaction | Sidebar |
| D-005 | 2026-08-10 | Build in a sibling standalone Vite prototype | Keeps the dirty production repository untouched | Delivery boundary |
| D-006 | 2026-08-10 | All primary entries and the full four-step path must be operable | Latest explicit user instruction | New, Tasks, Rules, Review, Generate, History |
| D-007 | 2026-08-10 | The expanded history header is compact and labeled | Latest browser annotation | Task/history sidebar |
| D-008 | 2026-08-10 | Suggestion results show both a cited rule and a plain-language basis | Latest browser annotation | Review card and Rules return path |
| D-009 | 2026-08-10 | Prototype file operations use deterministic fictional sources and results | Keeps the interaction testable without touching real files | New, Check, Generate, Result |
| D-010 | 2026-08-10 | Mapping-table password UI is excluded; local-only warning remains mandatory | Current production requirement supersedes older password wording | Generate and Result |
| D-011 | 2026-08-10 | `新建任务` moves into the task sidebar; global rail becomes `任务 / 规则` | Module switching should not mix navigation levels | Global/task navigation |
| D-012 | 2026-08-10 | Task and Rule use the same persistent inline-sidebar pattern | Switching modules should not implicitly collapse navigation | Task and Rule modules |
| D-013 | 2026-08-10 | Step 3 defaults to one-click adoption and advance | Per-item confirmation is too slow for the main path | Review |
| D-014 | 2026-08-10 | Rule evidence is collapsed by default and suggestion card is non-sticky | Keep the page concise and avoid covering source text | Review card |
| D-015 | 2026-08-10 | Output uses the original basename plus `-脱敏稿` | User-facing result naming must be immediately recognizable | Generate and Result |
| D-016 | 2026-08-10 | Global toast moves to top center and delete confirmation removes the central illustration | Feedback and destructive actions should be lighter and more conventional | Global feedback and Rules |
| D-017 | 2026-08-10 | Sidebar expansion uses a dedicated rail icon; module buttons never expand it | Module selection and layout control should not be coupled | Global navigation |
| D-018 | 2026-08-10 | Review defaults to the visible right finding list and an entity-anchored compact popover with all original actions | Latest annotated feedback restores direct per-item control without removing one-click processing | Review |
| D-019 | 2026-08-10 | Steps 2–4 can return; Step 3 can add a user-defined fictional finding | Users need correction paths and a way to cover missed sensitive content | Workflow and Review |
| D-020 | 2026-08-10 | Sidebar create actions use short labels only | Reduce visual noise | Task and Rule sidebars |
| D-021 | 2026-08-10 | The expand control moves to the rail bottom as a ghost chevron; the ordinary-only bulk action is removed | Latest annotations reduce visual clutter and duplicate bulk choices | Global rail and Review footer |

## Replaced

| Old rule | Replaced by | Reason |
|---|---|---|
| Narrow rail opens a floating task/history panel that can be pinned | Narrow rail expands inline and pushes the workspace | Explicit user rejection |
| Alternative purple/gold, blue/coral, graphite/amber and terracotta palettes | Original white-green palette | Explicit user selection |
| “No exhaustive rule-library or export workflow” | Complete Rules and four-step result prototype | User explicitly requested every functional prototype and a closed loop |
| 118 px unlabeled history-panel head | 60 px labeled header with collapse chevron | User annotated excessive empty space |
| Suggestion card shows only a generic reason | Card shows cited rule plus user-readable basis | User browser annotation |
| `新建 / 任务 / 规则` are equal global modules | `新建任务` is an action inside the task module; global rail shows `任务 / 规则` | Latest navigation feedback |
| Switching away from Tasks collapses the secondary sidebar | Module sidebar stays expanded and swaps Task/Rule content | Latest navigation feedback |
| Every finding must be handled individually | One-click adoption is the primary path; per-item adjustment remains optional | Latest efficiency feedback |
| Rule evidence is always expanded in the suggestion card | Evidence is collapsed by default and expands on demand | Latest simplicity feedback |
| `AI分析副本.*` | `<原文件名>-脱敏稿.*` | Latest output naming feedback |
| Clicking a collapsed module entry also expands its sidebar | Module entries only switch modules; a dedicated icon expands the sidebar | Latest navigation feedback |
| Step 3 hides the finding rail by default | Finding rail is visible by default; one-click processing remains in the footer | Latest review feedback |
| Suggestion card is a full-width in-flow summary above the document | Compact popover is anchored beside the selected content | Latest annotated feedback |

## Pending

No pending item blocks the deterministic prototype. Exact production integration, real local-file processing and packaging remain separate future approvals.
