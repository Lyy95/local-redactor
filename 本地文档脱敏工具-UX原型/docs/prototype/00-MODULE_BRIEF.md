# 本地文档脱敏完整闭环 UX 原型 Module Confirmation

Updated: 2026-08-10  
Status: Confirmed for implementation by the user's latest explicit instructions

## Problem and User

- Problem: The earlier task/history drawer floated over the document and required pinning, which made the navigation feel indirect and unstable.
- Primary user: A Windows office user reviewing fictional DOCX/XLSX redaction tasks locally.
- Usage moment: Switch between current/history tasks while reviewing a document without losing context.
- Expected value: A calm ChatGPT-like document workspace with predictable inline expand/collapse behavior.

## Source Inventory and Authority

| Priority | Source | Role | Notes |
|---:|---|---|---|
| 1 | User wording on 2026-08-10 | Business and interaction truth | White-green theme; collapsed rail from image 2; expanded sidebar occupies width; no floating panel |
| 2 | `references/sidebar-collapsed-reference.png` | Collapsed visual truth | Logo and `新建 / 任务 / 规则` narrow rail |
| 3 | `references/sidebar-expanded-target.png` | Expanded visual truth | Continuous inline sidebar and pushed document workspace |
| 4 | Existing program `DESIGN.md` and state contract | Copy and safety truth | Read-only reference; existing program is not modified |

## Entry and Relationship

- Entry: Prototype root route `/`.
- Parent menu: None; standalone prototype.
- Relationship: Visual/interaction prototype only, with no connection to the Python processing engine.
- Return path: Historical task view can return to the current review task.

## Confirmed 2026-08-10 scope extension

- User wording: `所有的功能原型都要完善好，整个流程可以闭环走通`.
- Follow-up wording: `上面的那些未改完的要继续改，然后再修改注释内容`.
- Browser annotations: move the current-task list upward; complete New and Rules; show the rule/basis behind each suggested result.
- This wording replaces the prior non-goals that excluded a complete rule library and export flow.

## Minimum Closed Loop

```text
new task -> choose fictional file/folder -> confirm boundary -> automatic check
-> review findings with cited rule/basis -> resolve all required items
-> generate separated result set -> final technical-check result
-> task/history reflection -> view result or start another task
```

Supporting loops:

```text
review finding -> open cited rule -> edit/test/save -> incremental-apply feedback
-> return to the same finding with prior decisions preserved

rules -> add/edit/test/toggle/copy/delete -> list reflection
rules -> import preview -> resolve conflict -> import result

blocked/failed fictional file -> readable cause -> return/retry/skip -> valid end state
```

## Surfaces and Operations

| Surface | Purpose | Required operations | Result feedback |
|---|---|---|---|
| Collapsed rail | Preserve maximum document width | Open tasks; New; Rules | Selected task state remains visible |
| Expanded task/history sidebar | Switch current and historical tasks | Collapse; select task; view all history | Workspace is pushed, never covered |
| Document review | Resolve fictional findings | Select highlight; adopt; edit; keep; delete; adopt ordinary suggestions | Pending count, markers, status bar and short toast update immediately |
| Historical task summary | Prove task switching | Return to current task | Selected row and workspace title update |
| New task | Create a fictional processing task | Choose file/folder; set mode; acknowledge boundary; start check | Queue/source summary and next step update |
| Automatic check | Explain local inspection without technical overload | View stages; cancel/retry blocked example; start review | Deterministic progress and result summary |
| Rules | Maintain reusable local handling decisions | Search/filter; add/edit/copy/toggle/delete/test/import | Rule list, citation and return target update |
| Generation | Show what the user receives | Review output structure; generate; view result cards | Progress, final technical-check result and history update |
| All history | Continue or inspect tasks | Filter/search; continue/retry/view result/delete record | Action availability follows task state |

## Must Preserve

- Four-step flow: `选文件 → 自动检查 → 确认处理 → 生成文件`.
- `本机离线 · 文件不上传`, `原文件只读`, and plain-language review actions.
- White/mint/deep-green visual system and fictional task data.
- Existing Python project remains fully untouched.

## Explicit Non-Goals

- No real file reading, redaction, OCR, encryption, filesystem writes, Explorer opening, backend, API, upload, deployment, or modification of the production program.
- No floating/overlay sidebar, pinning, hover-to-open behavior, or automatic responsive state switching.
- No claim that a prototype check generated real files or changed a file's security classification.
- No password workflow for the mapping table; the current baseline is direct local opening with a persistent `严禁上传` warning.

## Change Scope

### Allowed

- This standalone prototype folder only: `src/**`, `public/assets/**`, `references/**`, the prototype control documents, and package metadata.

### Protected

- Product Design runtime/hosting files: `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, `tests/sites-worker.test.mjs`.
- Entire sibling repository `D:\AI\GPT项目\通用\本地文档脱敏工具/**`.

## Confirmation

- Confirmed by: User.
- Confirmation date: 2026-08-10.
- Wording: “还是用一开始白底绿色那版…收起状态用第二张图，展开状态直接展开，不要还弄个浮窗”.
- Scope-extension confirmation date: 2026-08-10.
- Scope-extension wording: `所有的功能原型都要完善好，整个流程可以闭环走通`; followed by `上面的那些未改完的要继续改，然后再修改注释内容`.
