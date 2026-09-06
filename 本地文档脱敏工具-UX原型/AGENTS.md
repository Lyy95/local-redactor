# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

## Confirmed visual and interaction baseline (2026-08-10)

- Use the user-selected white background with mint/deep-green accents.
- The collapsed navigation must match `references/sidebar-collapsed-reference.png`: a narrow white rail with the logo and the vertical `新建 / 任务 / 规则` entries.
- Expanding `任务` must widen the real page grid and push the document workspace to the right. Never use a floating drawer, overlay, pin action, detached card, backdrop, or hover-to-open behavior.
- The expanded visual target is `references/sidebar-expanded-target.png`; the original white-green reference is `references/source-white-green-reference.png`.
- The prototype is isolated from `D:\AI\GPT项目\通用\本地文档脱敏工具`. Treat that existing Python project and all of its files as read-only.
- Use only fictional content. Do not show full local paths, persist source text, upload data, or add any network-dependent asset.

## Confirmed full-flow prototype baseline (2026-08-10)

- The user's latest instruction expands this prototype from a sidebar/review proof into a complete functional prototype. Every visible primary entry must lead to an operable closed loop; placeholder toasts such as “入口已保留” are no longer acceptable.
- Preserve the four-step task flow: `选文件 → 自动检查 → 确认处理 → 生成文件`. The normal single-file path must reach a result view and then appear in history.
- `新建` must support fictional single-file and folder-queue selection, readable processing options, boundary acknowledgement, normal/blocked examples, and a start-check action.
- `规则` must be a complete local rule-library prototype with fixed replacements and judgment standards, search/filter, add/edit/copy/enable/disable/delete, rule testing, import conflict handling, template guidance, and return-to-review behavior.
- Review cards must show both `引用规则` and a plain-language `判断依据`. A rule name can navigate to the matching rule and return to the same task/finding without losing prior decisions.
- Generation must show the separated output structure: `AI交付/AI分析副本.*` and `本地保管/脱敏映射表.xlsx + 脱敏检查报告.html`; the mapping table must be marked `严禁上传` and there is no upload action.
- Task/history must use one shared state source and support continuing unfinished work, viewing completed results, retrying failed/blocked fictional examples, and returning without resetting the current task.
- Reduce the expanded task panel's empty header area. Show `任务与历史` and the collapse chevron in a compact 56–64 px header, then start the current-task group directly below it.
- This remains a deterministic interaction prototype: it does not read real files, perform OCR/redaction, write output files, open Explorer, encrypt local data, or call any network. Clearly distinguish fictional interaction feedback from real processing capability.

## Confirmed simplification refinement (2026-08-10)

- Global navigation now uses two modules: `任务 / 规则`. `新建任务` belongs inside the task/history sidebar instead of appearing as a separate global module.
- Switching between task and rule modules keeps the inline secondary sidebar visible; it swaps content instead of automatically collapsing. Manual collapse remains available and must never become a floating drawer.
- The rules module uses the same inline-sidebar pattern as tasks. Its sidebar contains rule categories and the new-rule entry; the workspace contains search, actions and rows.
- The new-task page is a compact quick-start surface. Source choice, selected item and the primary start action remain visible; queue details and advanced settings are collapsed until requested.
- Step 3 must offer `一键采用全部建议并继续` as the primary path. Per-item review remains available as an optional adjustment path and must preserve all prior actions.
- Rule citation evidence is collapsed by default behind one clear disclosure. Expanding it reveals the cited rule, version/source, match condition, basis and open-rule action.
- The suggestion surface stays in normal document flow and must not use sticky positioning that covers the original text.
- Generated AI-copy names use `<原文件名>-脱敏稿.<扩展名>`; the result also names the output folder `<原文件名>-脱敏稿`.
- Destructive confirmation dialogs are compact and text-led; do not place a large standalone trash icon in the center.
- Global lightweight feedback appears at the top center, never at the bottom.
- When the shared module sidebar is collapsed, the narrow rail shows a dedicated `展开侧栏` icon. Clicking `任务` or `规则` only switches the module and must not expand the sidebar; expansion and collapse are explicit independent actions.
- Sidebar primary actions use short labels only: `新建任务` and `新建规则`.
- Step 3 restores the visible finding list and all per-item actions by default. Its compact suggestion popover is anchored beside the selected content, while cited-rule evidence remains a small disclosure.
- Every workflow stage after Step 1 exposes a return-to-previous-step action. Step 3 also supports adding a fictional user-selected redaction item, which joins the same pending count, finding list and processing actions.
- Keep the collapsed-rail expand control visually quiet at the bottom of the rail. Do not place it below the logo as another menu tile. Remove `采用全部普通建议`; keep only the primary `一键采用全部建议并继续` bulk action.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.
