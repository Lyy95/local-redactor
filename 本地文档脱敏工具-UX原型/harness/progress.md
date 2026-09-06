# 本地文档脱敏工具全流程原型 Harness Progress

## Current Stage

- Date: 2026-08-10
- Phase: Full-flow verification
- Baseline: White background + green accent; inline collapsed/expanded task sidebar; complete New/Task/Rule prototype loop
- Target artifact: Local interactive Vite prototype

## Scope

- Allowed change paths: Only this standalone prototype folder, as listed in `prototype-contract.json`.
- Protected paths/workflows: Hosting runtime files and the entire sibling production Python repository.
- Deployment: Not authorized and not performed.

## Completed

- Sidebar follows the confirmed two-state interaction: 104 px collapsed; 420 px expanded, or 400 px at narrower desktop widths; expanding directly pushes the workspace with no floating panel, backdrop, pin, or second-stage fixation.
- The history header is compressed to 64 px and the current-task list begins directly below it.
- New-task flow supports fictional DOCX/XLSX sources, mixed folder batches, failed/excluded rows, mode selection, subfolder option, and a required local-processing boundary acknowledgement.
- Automatic checking supports progress, cancellation, retry, blocked encrypted sources, and transition into review.
- Review supports text, image, hidden-content, and combined-risk findings; each suggestion shows the cited rule, version/source, match condition, and judgment basis.
- Mandatory rules disable “保留原文” with a visible explanation; adopt/edit/keep/delete, remember-same-treatment, and bulk ordinary suggestions are interactive.
- Rules support search/filter, add/edit/copy/toggle/delete, testing, import conflict resolution, template feedback, default restoration, cited-rule focus, incremental application, and return to the same review finding.
- Generation is gated by unresolved findings, includes a simulated final-check failure/recovery path, and separates `AI交付` from `本地保管`; mapping artifacts are marked `严禁上传`.
- History supports continue pending, retry failed, view completed output, return to current task, and delete confirmation.
- Previous regressions remain fixed: keep-original preserves original text, cancel-edit discards the draft, and sidebar collapse/reopen preserves the active task and review state.

## Verification Evidence

| Check/journey | Result | Evidence |
|---|---|---|
| Production build | PASS | `npm run build`; current output in `dist/client` |
| Hosting contract | PASS | `npm run test:sites`; 4/4 tests passed |
| Prototype overlay | PASS | `harness/prototype-results.json` |
| Protected production repository | PASS | All 68 protected files match `harness/protected-baseline.json` |
| Inline sidebar | PASS | 1280 px viewport: 104/400 px sidebar and 1176/880 px workspace; edges align with no overlap or page-level horizontal scroll |
| Minimum viewport | PASS | 772 × 731: no page-level horizontal scroll; collapsed review card stays inside the review region; expanded panel remains a direct push layout |
| New/check flow | PASS | Normal source reaches review; encrypted source is blocked with a reason and recovery; mixed folder rows remain distinguishable |
| Review and rule evidence | PASS | Cited rule, source/version, match condition, basis, mandatory explanation, and incremental rule update/return verified |
| Generation recovery | PASS | Forced final-check failure hides outputs, returns to the related finding, and completes after correction and retry |
| Result/history | PASS | Output groups, safety copy, history result, return-to-current state, and state-valid history actions verified |
| Rule library | PASS | CRUD, test, toggle, copy, delete, import conflict, template feedback, built-in read-only behavior verified |
| Regression scope | PASS | Keep-original, cancel-edit, active-task preservation, and pending-count linkage verified |
| Browser runtime | PASS | Final working-session console contained no error or warning entries |

## Reviewer Findings

| Priority | Finding | Resolution |
|---|---|---|
| P1 | Keep-original rendered the suggestion instead of the original value | Rendering branches by resolution action; browser regression passed |
| P1 | Cancel-edit retained the draft value | Edit draft is isolated and only committed on confirm; browser regression passed |
| P1 | Reopening the sidebar reset a selected history task | Removed active-task reset from expand; browser regression passed |
| P1 | Saving a cited fixed-replacement rule did not update the current suggestion value | Incremental apply now updates the finding suggestion and replacement map; browser regression passed |
| P1 | Folder mixed queue stopped at a static preview and used a hard-coded sidebar count | Added shared queue state, q1 → q2 → q5 processing, retry/skip for q3, exclusion for q4, dynamic sidebar progress, and a consistent batch summary; B-009 passed independently |
| P2 | Narrow browser width caused page-level horizontal scrolling and suggestion-card overlap | Reduced shell minimum width, kept three-column review down to 520 px, and removed the negative card offset; 772 × 731 regression passed |

Independent full-flow review: PASS — no remaining P0, P1, or P2 findings. The final B-009 recheck observed dynamic `0 / 4 → 4 / 4` progress, q3 not blocking q5, q4 remaining excluded, and a consistent `成功 3 / 失败 0 / 跳过 1 / 排除 1` summary.

Focused simplification recheck: PASS — Task/Rule use the same persistent secondary-sidebar pattern; New is inside Task and presents a compact quick-start view; Step 3 defaults to one-click processing with optional manual adjustment; rule evidence expands on demand; the suggestion card no longer covers the document; generated names use `<原文件名>-脱敏稿`; delete confirmation is compact; global feedback appears at the top.

Explicit sidebar-control recheck: PASS — collapsed Task/Rule clicks switch modules without changing the 104 px rail; the visible `展开侧栏` icon opens the selected module's inline sidebar to 400 px at 1280 × 720; the header chevron collapses it; no overlay or page-level horizontal scroll appears.

Review-control restoration recheck: PASS — sidebar actions now read only `新建任务 / 新建规则`; Step 3 shows the right finding list and all four original item actions by default; the compact popover is anchored 8 px from the selected content and its rule disclosure is 11 px; adding a fictional item updates document/list/pending count and resolves normally; Step 2/3/4 return paths preserve findings and decisions.

Rail/footer declutter recheck: PASS — the expand control is now a 32 px borderless chevron at the rail bottom and still opens the 400 px inline sidebar; the redundant `采用全部普通建议` action is removed while the primary one-click action remains.

## Remaining Business Questions

- No implementation blocker. Integrating this prototype into the production application remains a separately authorized future phase.

## Development Deployment

- Final approval: Not received
- Build: Local production build only
- Upload: Not performed
- Access URL: `http://localhost:4173/`
- HTTP verification: Local preview only
