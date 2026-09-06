# 白底绿色双态侧栏交互原型 Requirement Coverage

Updated: 2026-08-10

| ID | Source | Requirement | Priority | Surface | Acceptance evidence | Status |
|---|---|---|---|---|---|---|
| R-001 | User | Restore white background and green visual direction | Must | Whole app | Token and screenshot comparison | Confirmed |
| R-002 | User image 2 | Collapsed state uses the narrow logo/new/task/rules rail | Must | Sidebar collapsed | 104 px rail, same vertical hierarchy | Confirmed |
| R-003 | User | Expanded state directly occupies width and pushes content | Must | Sidebar expanded | Sidebar and workspace edges touch; no overlap | Confirmed |
| R-004 | User | No floating drawer/pinning workflow | Must | Sidebar | No overlay, backdrop, pin or detached task card in DOM/UI | Confirmed |
| R-005 | Prior request | Current task, folder batch, today and earlier history remain available | Must | Expanded sidebar | All groups visible with fictional filenames/statuses | Confirmed |
| R-006 | Existing baseline | Preserve four-step review and safe copy | Must | Header/review | Required labels visible; forbidden safety claims absent | Confirmed |
| R-007 | Existing baseline | Review actions give immediate feedback | Must | Suggestion popover | Count decreases, marker resolves, next item selected | Confirmed |
| R-008 | User | Do not modify the actual program | Must | Delivery boundary | Only sibling prototype folder changes | Confirmed |
| R-009 | User annotation | Remove excessive blank space above current tasks | Must | Expanded task sidebar | Compact labeled header is 56–64 px; current-task group follows directly | Confirmed |
| R-010 | User | Complete all visible functional prototype entries | Must | Whole app | No primary rail action ends in a placeholder-only toast | Confirmed |
| R-011 | User annotation | Complete New-task interactions | Must | New / select / check | Single file, folder queue, mode, boundary acknowledgement, normal and blocked sample all operate | Confirmed |
| R-012 | Existing program baseline | Preserve the fixed four-step task flow | Must | Task workspace | Select → check → review → generate reaches result and history | Confirmed |
| R-013 | Existing program baseline | Folder queue handles mixed outcomes without false success | Must | New / check / batch result | Supported, excluded and failed fictional rows remain distinguishable; next item can continue | Confirmed |
| R-014 | User annotation | Complete the Rules module | Must | Rules | Fixed replacements and judgment standards support search, CRUD, toggle, test and import conflict | Confirmed |
| R-015 | User annotation | Show cited rule or basis for suggestions | Must | Review suggestion card | Rule type/name link and plain-language rationale are visible | Confirmed |
| R-016 | Existing program baseline | Rule change can return to the same finding | Must | Review ↔ Rules | Rule save shows incremental-apply feedback and preserves unrelated decisions | Confirmed |
| R-017 | Existing program baseline | Only completed review can enter generation | Must | Review / Generate | Pending > 0 blocks generation; pending = 0 unlocks it | Confirmed |
| R-018 | Existing program baseline | Separate AI-delivery and local-only outputs | Must | Generate / Result | AI copy, mapping table and report appear in correct cards; mapping table marked 严禁上传 | Confirmed |
| R-019 | Existing program baseline | History actions reflect task state | Must | Sidebar / All history | Continue, retry, view result and delete-record appear only where valid | Confirmed |
| R-020 | Safety boundary | Use deterministic fictional prototype data only | Must | Whole app | No real file read/write, OCR, full path, network request or upload action | Confirmed |
| R-021 | User annotations | Make Step 3 one-click by default | Must | Review | One primary action adopts all suggestions and advances to generation; manual adjustment remains available | Confirmed |
| R-022 | User annotations | Keep rule evidence available without visual overload | Must | Suggestion card | Citation, version, condition and basis are collapsed by default and expand on demand | Confirmed |
| R-023 | User annotations | Do not cover the original text | Must | Review layout | Suggestion card participates in normal flow; no sticky overlay over the document | Confirmed |
| R-024 | User annotations | Unify task/rule navigation and move New under Task | Must | Global/module navigation | Task and Rule share inline secondary sidebars; switching modules preserves expanded state | Confirmed |
| R-025 | User annotations | Simplify the New page | Must | New task | Quick source choice and start remain primary; queue and advanced settings are disclosures | Confirmed |
| R-026 | User annotations | Name output from the original file | Must | Generation/result/history | AI copy and output folder use `<原文件名>-脱敏稿` | Confirmed |
| R-027 | User annotations | Improve destructive confirmation and toast placement | Must | Rules/global feedback | Compact text-led delete dialog; global toast appears at top center | Confirmed |

## Minimum Loop

| Step | Actor action | System response | State change | Evidence |
|---|---|---|---|---|
| Entry | Open prototype | Collapsed rail and current document appear | `sidebar=collapsed` | Browser capture |
| Navigate | Click `任务` | Sidebar widens inline; document narrows/reflows | `sidebar=expanded` | Measured bounding boxes |
| Key action | Click a highlight and `采用建议` | Short feedback appears; next pending item opens | Finding resolved | Pending count/marker change |
| Return | Click collapse chevron | Rail returns to collapsed image; review state remains | `sidebar=collapsed` | Same resolved count and selection |
| Create | Open New and choose a fictional DOCX | Source summary appears and start-check becomes available after boundary acknowledgement | `task=source_ready` | Form and stepper |
| Check | Start automatic check | Stages complete and review summary appears | `task=review_required` | Progress and result summary |
| Review | Resolve all findings | Generation becomes available | `task=ready_to_generate` | Pending 0 and enabled CTA |
| Generate | Generate results | Four stages finish and result cards appear | `task=completed` | Result view and updated history |
| Rule maintenance | Add/test/save a rule | New row appears and is cited where applicable | `rules=ready` | Rule list and feedback |

## Non-Functional Boundaries

## Latest Review Refinement Coverage

| ID | Requirement | Surface | Acceptance |
|---|---|---|---|
| R-028 | Sidebar create buttons use only short action labels | Task and Rule sidebars | B-022 |
| R-029 | Step 3 keeps the original per-item controls and right finding list visible | Anchored suggestion popover + finding rail | B-023 |
| R-030 | Rule evidence is a small secondary disclosure | Suggestion popover | B-023 |
| R-031 | Every stage after Step 1 can return to the previous stage | Steps 2–4 actions | B-024 |
| R-032 | User can add a fictional redaction target during review | Add-item dialog → document/list/count reflection | B-025 |

- Target viewport: 1536 × 1024 for source comparison; 1440 × 900 product baseline; 1280 × 720 minimum interaction check.
- Runtime: Local React/Vite prototype in the Codex in-app browser.
- Assets: Bundled locally; no CDN, telemetry or outbound requests.
- Data: Fictional names and files only; no full paths or real sensitive values.

## Excluded By Confirmation

| Item | Reason | Reconsider trigger |
|---|---|---|
| Production Python code changes | User explicitly requested prototype first | Separate explicit implementation approval |
| Real document processing/OCR/file generation | Prototype scope | Separate engineering phase |
| Publishing/deployment | Not requested | Explicit sharing/deployment request |
