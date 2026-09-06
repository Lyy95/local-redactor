# 白底绿色双态侧栏交互原型 State and Action Matrix

| State | Available actions | Transition/result | Feedback |
|---|---|---|---|
| Sidebar collapsed | New, open Tasks, Rules | Open Tasks → expanded | Real grid width changes; no overlay |
| Sidebar expanded | Collapse, choose current/history task, view all history | Collapse → collapsed; choose task → workspace reflects selection | Selected row and title update |
| Review pending | Select highlight/marker; adopt/edit/keep/delete; adopt ordinary suggestions | Resolve → next pending or review complete | Count, marker, status bar and toast update |
| Edit finding | Enter replacement; confirm/cancel | Confirm → pending/complete | New replacement visible |
| Review complete | Reopen a resolved highlight; inspect state | Remains complete | `可以生成` text; no upload-safety claim |
| Historical task selected | Return to current task | Current task review restored | Prior review state remains |
| New task / no source | Choose fictional file/folder | Source ready | Source card/queue and enabled boundary control |
| Source ready | Confirm boundary; start check | Checking | Step 2 and progress stages appear |
| Checking | Complete / cancel / block / fail | Review ready / cancelled / blocked / failed | Explicit result and next action |
| Review ready | Resolve finding / open cited rule / bulk ordinary | Review ready / rule editing / generation ready | Shared counts and task status update |
| Rule list | Add/edit/copy/toggle/delete/test/import | Rule list / dialog / conflict | List row and feedback update |
| Rule return target set | Save rule and return | Review ready | Incremental-apply feedback; same finding restored |
| Generation ready | Generate | Generating → rescanning | Four-stage progress |
| Rescanning | Pass / fail | Completed / check failed | Results available only on pass |
| Completed | View result / history / new task | Result/history/new | Completed task remains in history |
| History item | Continue/retry/view/delete record | State-specific target | No invalid action shown |

## Transition Rules

| From | Action | To | Data update |
|---|---|---|---|
| Collapsed | Click `任务` | Expanded | Preserve selected task/finding and scroll |
| Expanded | Click collapse chevron or press Escape | Collapsed | Preserve selected task/finding and resolved set |
| Review pending | Choose review action | Review pending/complete | Resolve current; update count; select next |
| Any review state | Select history task | Historical selected | Store current review state in memory |
| Historical selected | Return current task | Prior review state | Restore current task view |
| Idle | Choose normal fictional source | Source ready | Set file/folder metadata only |
| Idle | Choose blocked fictional source | Blocked after preflight | Record reason; generation unavailable |
| Source ready | Start automatic check | Checking | Advance progress stages |
| Checking | Scan completes | Review required | Populate fictional findings and task counts |
| Review required | Open cited rule | Rule editing | Store return target: task + finding + scroll context |
| Rule editing | Save | Incremental apply | Update rule revision and affected finding only |
| Incremental apply | Return | Review required | Preserve unrelated completed decisions |
| Review required | Pending becomes 0 | Ready to generate | Enable generation CTA |
| Ready to generate | Generate | Generating | Lock final-write actions |
| Generating | Four stages pass | Completed | Add/update history; expose result cards |
| Generating | Final check fails | Check failed | Hide outputs; allow return/retry |
| Queue ready | Process current item | Completed/failed/skipped | Advance to next without rewriting prior state |

## Forbidden Combinations

- Sidebar expanded + overlay/backdrop/floating task panel/pin action.
- Sidebar collapsed + hidden history controls in the Tab order.
- Hover-only or focus-only expansion.
- Sidebar toggle + document reload, reset, scroll loss or pending-count reset.
- Completed copy containing `已脱密`, `可安全上传`, `绝对安全` or equivalent claims.
- Pending count greater than 0 + generation enabled.
- Blocked/check-failed task + completed result cards.
- Mandatory rule + enabled `保留原文`.
- Bulk ordinary action + image/low-confidence/combination/object finding.
- Rule edited + stale rule snapshot exported without incremental-apply feedback.
- Mapping table displayed under `AI交付`.
- Failed queue item rendered as successful or silently blocking later items.
- History/report exposing source text, full path or reversible mapping values.

## Canonical state names

```text
idle → source_ready → checking
checking → blocked | failed | cancelled | review_required
review_required ↔ incremental_rule_apply
review_required → ready_to_generate → generating → rescanning
rescanning → check_failed | completed
```

Folder queue:

```text
queue_ready → current_processing
→ current_completed | current_failed | current_skipped
→ next_item → batch_completed
```

Rules:

```text
rules_ready → editing → testing → saving → rules_ready
rules_ready → import_preview → import_conflict → rules_ready
```

Simplified navigation and review:

```text
module_sidebar_expanded(task) ↔ module_sidebar_expanded(rule)
module_sidebar_expanded → manual_collapse → module_sidebar_collapsed
module_sidebar_collapsed(task|rule) → click_expand_icon → module_sidebar_expanded(task|rule)
module_sidebar_collapsed(task) ↔ click_module → module_sidebar_collapsed(rule)
review_required → one_click_apply_all → ready_to_generate
review_required ↔ manual_adjustment
evidence_collapsed ↔ evidence_expanded
review_required → add_finding_open → user_finding_added → review_required
step_4 → previous_step → step_3
step_3 → previous_step → step_2_complete
step_2 → previous_step → step_1
```

Forbidden combinations added:

- Switching `任务 ↔ 规则` + implicit sidebar collapse.
- Clicking `任务 / 规则` while collapsed + implicit sidebar expansion.
- User-added finding + missing right-list/pending-count reflection.
- Step 2/3/4 + no return path to the previous stage.
- Suggestion card + sticky/absolute placement that covers document text.
- One-click review action + unresolved finding remaining without visible error.
- Output file name + generic `AI分析副本` name after a source is known.
