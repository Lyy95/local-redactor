# 本地文档脱敏工具全流程原型 Acceptance Plan

## Deterministic Checks

| ID | Check | Command/evidence | Expected |
|---|---|---|---|
| A-001 | Production build | `npm run build` | Pass; Sites-ready files emitted |
| A-002 | Hosting contract | `npm run test:sites` | Pass |
| A-003 | Prototype overlay | Workflow verifier | Pass |
| A-004 | Forbidden copy/static structure | Source scan | No forbidden safety claim, overlay sidebar, or pin copy |
| A-005 | Production protection | Protected-baseline verifier | All 68 sibling production files unchanged |

## Browser Journeys

| ID | Journey | Steps | Expected visible result |
|---|---|---|---|
| B-001 | Inline sidebar | Open collapsed → click Task → inspect positions → collapse | Width changes in layout; workspace edge moves; no overlap/backdrop |
| B-002 | Review feedback | Click highlight → adopt suggestion | Pending count drops; marker resolves; toast and next finding appear |
| B-003 | State preservation | Resolve one item → expand/collapse → inspect | Count and selected task remain unchanged |
| B-004 | History navigation | Expand → select completed history → return current | Summary appears, then current review restores |
| B-005 | Keyboard/accessibility | Focus Task → Enter; expanded → Escape | Expand/collapse works; focus remains understandable |
| B-006 | Minimum viewport | Repeat at 1280 × 720 and 772 × 731 | No page-level horizontal scroll or covered content |
| B-007 | Single-file full loop | New → choose normal DOCX → acknowledge → check → review all → generate → result → history | Every step unlocks correctly; result/history reflect one task |
| B-008 | Blocked source | New → choose encrypted fictional DOCX → start check | Readable blocked reason; no review/generation; can choose another source |
| B-009 | Folder mixed queue | New → choose folder → inspect supported/excluded/failed rows → process next | One failed item does not turn successful or block later items; batch summary matches |
| B-010 | Rule CRUD and test | Rules → add → test → save → toggle → edit/copy → delete | Row/list state and feedback remain consistent |
| B-011 | Rule import conflict | Rules → import → choose existing/imported/cancel | No silent overwrite; result count and rows match choice |
| B-012 | Cited rule return | Review → open cited rule → edit/save → return | Same task/finding restored; suggestion and rule evidence update incrementally |
| B-013 | Mandatory review | Open mandatory fictional finding | Cited rule/basis visible; keep-original disabled with explanation |
| B-014 | Generate failure and recovery | Force final-check failure → return related finding → fix → generate again | Failed outputs remain unavailable; retry can complete |
| B-015 | History actions | Continue unfinished; retry failed; view completed result; delete one record | Only state-valid actions appear; no source/full-path data |
| B-016 | One-click review | Open Step 3 → choose one-click action | All findings resolve together and Step 4 opens; manual path remains available after return |
| B-017 | Collapsed rule evidence | Open a finding → inspect compact card → expand evidence | Card does not cover source text; rule/version/condition/basis appear only after expansion |
| B-018 | Unified module sidebar | Switch Task → Rule → Task; manually collapse; reopen | Expanded width persists across module switch; sidebar content swaps; only explicit collapse closes it |
| B-019 | Simplified New page | Open New task → inspect quick start → expand queue/settings | Primary source and start action are concise; details remain operable on demand |
| B-020 | Output naming and feedback | Complete task → inspect output; delete a rule; trigger toast | Folder/file use `<原文件名>-脱敏稿`; delete dialog is compact; toast appears at top |
| B-021 | Explicit sidebar expansion | Collapse sidebar → click Rule/Task → click expand icon | Module changes while width stays 104 px; only the dedicated icon expands to 400/420 px; collapse chevron still works |
| B-022 | Short sidebar actions | Open Task and Rule sidebars | Primary buttons read only `新建任务` and `新建规则` |
| B-023 | Anchored full-action review | Select a document entity → inspect popover and right rail → expand evidence | Popover is beside the selected entity; all four item actions and right list are visible; evidence disclosure is visually secondary |
| B-024 | Previous-step navigation | Step 2 → back; Step 3 → back; Step 4 → back | Each action returns exactly one stage without losing findings or resolutions |
| B-025 | Add redaction target | Step 3 → Add content → enter fictional value/replacement → confirm | New finding appears in document and right list, pending total increases, and normal actions resolve it |
| B-026 | Quiet expand control and single bulk action | Collapse sidebar; inspect rail; open Step 3 footer | Expand chevron is at rail bottom with no tile-like border; `采用全部普通建议` is absent; one-click bulk action remains |

## Regression Scope

| Protected surface | Why protected | Test |
|---|---|---|
| Four-step header | Existing confirmed flow | Labels/order unchanged |
| Review actions | Existing minimum loop | All four actions plus bulk action remain visible/functional |
| Safety copy | Product boundary | Required offline/read-only copy visible; forbidden claims absent |
| Product repository | User-owned production code | All protected-file hashes remain unchanged |
| New/task/rule navigation | Confirmed full scope | Every rail entry opens a real workspace and can return |
| Rule citation | Latest annotation | Suggested value includes cited rule and basis; jump/edit/return preserves task and finding |
| Output separation | Existing product boundary | AI copy separated from mapping/report; mapping marked `严禁上传` |
| Prior interaction fixes | Previously verified defects | Keep-original, cancel-edit, active-task, and count linkage remain correct |

## Completion Record — simplification recheck complete

- Deterministic checks A-001 through A-005: PASS.
- Browser checks B-001 through B-021: PASS. B-021 verified that Task/Rule clicks keep the rail at 104 px, the dedicated icon expands to 400 px at the current viewport, and the matching header chevron collapses it again.
- Browser checks B-022 through B-025: PASS. Sidebar actions expose only the short labels; the selected-content popover stays 8 px from its anchor with all four actions and an 11 px evidence disclosure; the right finding list is visible; a user-added item changed the list/pending total from 6 to 7 and was resolved through the normal action; Step 3 → 2 → 3 and Step 4 → 3 preserved all 7 findings and resolution state.
- Browser check B-026: PASS. The 32 px borderless expand chevron sits 24 px above the rail bottom and still opens the selected module to 400 px; `采用全部普通建议` is absent while `一键采用全部建议并继续` remains available.
- 1280 × 720 and 772 × 731 layout checks: PASS with no page-level horizontal scroll.
- Console/page errors: 0 errors and 0 warnings in the working-session final check.
- Artifact: Rebuilt from the integrated full-flow source.
- Independent reviewer result: Previous full-flow PASS retained as regression evidence; B-016 through B-020 passed the focused browser recheck on the integrated source.
- Simplification evidence: rule evidence is collapsed by default and expands in place; the suggestion card is non-sticky and ends before the document preview; one-click review resolves all 6 findings and opens Step 4; Task and Rule keep the same 400 px expanded sidebar; New has no global rail entry and its queue/settings stay collapsed by default; output and toast naming/position match the confirmed baseline.
- Folder batch evidence: q1 → q2 → q5 complete without q3 blocking; q3 supports retry or skip; q4 remains excluded; dynamic progress reaches `4 / 4`; skip branch ends at `成功 3 / 失败 0 / 跳过 1 / 排除 1`.
- Deployment: Not authorized and not performed.
