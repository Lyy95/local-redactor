# 本地文档脱敏工具 MVP State and Action Matrix

List and detail actions must use the same rule.

| State | List actions | Detail actions | Transition/action result | Feedback |
|---|---|---|---|---|
| Empty | Select DOCX/XLSX | View product boundary and modes | Select → Preflighting | “文件仅在本机处理” |
| Preflighting | Cancel | View format, OOXML parts, size and risky objects | Supported → Scanning; invalid/unsafe → Blocked | Explicit inventory or blocking reason |
| Blocked | Start new task | View reason and safe next step | Reset → Empty | Red state; no export action |
| Scanning | Cancel | View structure/text/image/model progress | Scan complete → Review required; unknown object → Object resolution | No partial “passed” state |
| Object resolution | Remove, process separately, cancel | View attachment/object type and source position | All resolved → Review required; unresolved → stay | Unknown content cannot be silently skipped |
| Review required | Adopt suggestion, edit, keep original, delete, adopt all ordinary suggestions, manual text/image mark | Inspect original/result, occurrences, image boxes and combination risk | All text/high-risk/image/object items resolved → Preview ready | Immediate completion mark, pending-count update, short feedback and automatic next item |
| Preview ready | Compare, return to review, set result location | View full Word/Excel semantic preview and local-mapping warning | Result location confirmed → Ready | Show preserved and changed semantics |
| Ready | Generate, return to review, cancel | Review `AI交付/本地保管` outputs | Generate → Rebuilding | Mapping-table risk warning |
| Rebuilding | Cancel only before first final write | View Word/Excel and local mapping rebuild stage | Outputs built → Rescanning | No partial completed state |
| Rescanning | Wait | View OOXML/media/OCR/QR/mapping/report checks | All pass → Completed; residual/error → Check failed | Independent output-byte checks |
| Check failed | Delete staged output, return to review, retry | View sanitized category/location only | Correct → Rebuilding | Red state; never show completed |
| Completed | Open `AI交付`, open `本地保管`, view report, new task | View hashes/counts/warnings | New task → Empty | “技术检查已完成，仍需按单位制度确认是否可外发” plus “映射表严禁上传” |
| Error | Start over | View sanitized error | Reset → Empty | No raw text, full path or stack trace in user log |
| Rule library ready | Add, edit, enable, disable, delete, import | View fixed replacements and judgment standards | Save → Rule library ready; close → prior workflow state | Encrypted local save confirmation |
| Rule library conflict | Resolve conflict, cancel import | Compare rule names and non-sensitive action summary | Resolve → Rule library ready; cancel → prior library snapshot | Never silently overwrite |
| Rule library unavailable | View recovery message, start without scanning | No rule plaintext or storage path | Repair/reset by explicit user action → Rule library ready | Scanning remains blocked |

## Transition Rules

| From | Action | Confirmation | To | Data update |
|---|---|---|---|---|
| Empty | Select supported DOCX/XLSX | Required boundary acknowledgement and mode | Preflighting | Create in-memory task |
| Preflighting | Encounter legacy/encrypted/macro/damaged/unsafe package | None; cannot override | Blocked | Record sanitized reason only |
| Preflighting | Inventory accepted | None | Scanning | Load fixed local models after hash verification |
| Scanning | Encounter removable attachment/unknown object | None | Object resolution | Create mandatory disposition item |
| Scanning | Finish all detectors | None | Review required | Populate text, visual, hidden and combination findings |
| Review required | Adopt/edit/keep/delete/mark | Keep requires reason; every image/object requires decision; mandatory rules cannot keep original | Review required/Preview ready | Update entities, mappings and pending counts, then select the next pending item |
| Review required | Adopt all ordinary suggestions | Confirm fixed batch scope | Review required/Preview ready | Resolve ordinary text and deterministic rules only; leave excluded items pending |
| Any non-scanning state | Open rule library | None | Rule library ready | Preserve current page |
| Rule library ready | Save a changed library while a task exists | Confirm rescan requirement | Empty/Preflighting | Clear task rule snapshot and rescan from source selection |
| Preview ready | Review local mapping warning | Two-directory result layout is visible | Ready | Do not create any task-history or decision snapshot |
| Ready | Generate output | Confirm two-directory result layout | Rebuilding | Freeze one task snapshot in memory |
| Rebuilding | Create AI copy/report/local mapping in protected staging | None | Rescanning | No output is yet final; publish atomically after validation |
| Rescanning | Independent checks pass | None | Completed | Atomically publish final result directories |
| Rescanning | Original value, forbidden OOXML part or original image found in AI delivery/report | None | Check failed | Quarantine/delete staged outputs where safe |
| Any active task | Cancel/new task | Warn that in-memory original and mapping will clear | Empty | Clear task memory; keep only completed local-custody files |

## Forbidden Combinations

- Do not show an action that is invalid for the current state.
- Do not expose duplicate action paths on the same surface.
- Do not allow detail actions that exceed corresponding list permissions.
- `Blocked` + export action is forbidden.
- unresolved text/high-risk/image/object findings > 0 + `Ready` is forbidden.
- mandatory-rule match + keep-original action is forbidden.
- batch confirmation + image/low-confidence unknown/combination-risk/attachment/embedded-object resolution is forbidden.
- changed rule library + continuing an old task snapshot without rescan is forbidden.
- unreadable, damaged or undecryptable rule store + `Scanning` is forbidden.
- rescan failure + `Completed` is forbidden.
- unsupported format, invalid model hash or unknown OOXML part + `Scanning/Ready` is forbidden.
- unchanged original media bytes, removable visual overlay or unprocessed image + `Completed` is forbidden.
- macro, ActiveX, OLE, active external relationship, Word revision/hidden node, Excel formula/hidden sheet/hidden row/hidden column + `Completed` is forbidden.
- plaintext mapping staging outside `本地保管`, task-history/decision snapshots, or mapping table under `AI交付` + `Completed` is forbidden.
- analysis copy under `本地保管` or mapping/report under `AI交付` is forbidden.
- mapping-table row without a corresponding transformed value, or transformed value without mapping row when reversible, is forbidden.
- `技术检查完成` + `可安全上传/已脱密` wording is forbidden.

## Round 3 transitions

| From | Action | To | Required result |
|---|---|---|---|
| Empty | Select folder | Queue ready | Supported files only; first file selected |
| Review required | Save/edit/delete rule | Review required | Incremental apply only; no file reopen or OCR rerun; existing decisions retained |
| Rule library ready | Delete shipped preset | Rule library ready | The row remains deleted after restart |
| Rule library ready | Restore defaults | Rule library ready | Restore missing shipped presets without overwriting custom rules |
| Queue item completed/failed | Process next | Preflighting | Advance one item and preserve queue summary |
| Completed/failed export | Refresh history | Same state | Append one encrypted status record without content values |

The former transition `changed rule library -> reset/rescan` is replaced by incremental application. A full rescan is reserved for recognition-capability or OCR-setting changes explicitly chosen by the user.
