# 本地文档脱敏工具 MVP Acceptance Plan

## Deterministic Checks

| ID | Check | Command/evidence | Expected |
|---|---|---|---|
| A-001 | Unit/integration tests | `.venv\Scripts\python.exe -m pytest -q` | Pass |
| A-002 | Type checks | `.venv\Scripts\python.exe -m mypy src` | Pass |
| A-003 | Lint | `.venv\Scripts\python.exe -m ruff check src tests` | Pass |
| A-004 | Security release check | `.venv\Scripts\python.exe scripts\verify_release.py` | No source canary, forbidden OOXML part, plaintext mapping, network capability or remote asset |
| A-005 | Windows build | `.venv\Scripts\python.exe scripts\build_windows.py` | Pass |
| A-006 | Delivery artifact | `dist\本地文档脱敏工具\本地文档脱敏工具.exe --self-test` | Exit 0 in disconnected environment |
| A-007 | Model manifest | Build manifest and SHA-256 verification | All OCR/NER/vision assets are local, licensed, fixed, and no runtime download exists |
| A-008 | Local mapping isolation | Export without a password; inspect the output layout and workbook | Directly openable XLSX exists only under `本地保管`; no plaintext staging remains |

## Desktop UI Journeys

| ID | Journey | Steps | Expected visible result |
|---|---|---|---|
| UI-001 | DOCX minimum loop | Select fictional DOCX → balanced mode → scan → review three tabs → compare → export | `AI交付/AI分析副本.docx` and two `本地保管` files exist |
| UI-002 | XLSX minimum loop | Select fictional XLSX with repeated entities and formulas → review → export | Grid/merged cells/basic styles remain; formulas are safe static values; outputs complete |
| UI-003 | Semantic readability | Compare the same mixed-entity paragraph/row in balanced and strict modes | Balanced result preserves roles, relationships, sequence and amount scale; strict result preserves entity identity links |
| UI-004 | Cross-surface consistency | Same person/unit/project appears in Word body/table/image OCR or several Excel sheets | Every occurrence uses one consistent replacement and one mapping row |
| UI-005 | Visual minimum loop | Review structured sensitive OCR, QR and face candidates; add manual box | Sensitive images have a decision; clean images do not enter todo and are safely re-encoded; sensitive pixels/QR payload do not survive |
| UI-006 | Combination risk | Open exact place+time+rare role+event fixture | Combination card appears and recommends the smallest necessary precision reduction |
| UI-007 | Unsupported source block | Import legacy, encrypted, macro-enabled, damaged or dangerous OOXML fixture | Red blocked state; no export |
| UI-008 | Mapping-table delivery | Finish export without entering a password | Directly openable XLSX under `本地保管`; red “严禁上传”; no mapping under `AI交付` |
| UI-009 | Rescan failure | Inject source value, original image or forbidden relation into staging | Check failed; completed state impossible |
| UI-010 | Return and clear | Finish task → new task → inspect safe diagnostics | Prior original and plaintext mapping are unavailable in application state; local-custody output remains |
| UI-011 | Minimum viewport | Complete UI-001 and UI-002 at 1280×720 and 150% Windows scale | No clipped primary action, Excel grid, image controls or risk copy |
| UI-012 | Simplified first screen | Launch at 1280×720 | One primary task/action; long coverage and technical explanations are collapsed |
| UI-013 | Immediate review feedback | Choose `采用建议` on an ordinary text item | Item completes, pending count decreases, short success feedback appears and next pending item is selected |
| UI-014 | Safe batch confirmation | Choose `采用全部普通建议` on a mixed task | Ordinary and deterministic-rule findings complete; images, low-confidence unknowns, combination risk and objects remain pending |
| UI-015 | Plain-language actions | Open the review page and expand `修改` | Main UI contains none of the forbidden internal strategy terms in the revision contract |
| UI-016 | Persistent fixed rule | Add `公安 → GA`, restart and scan a fictional Office document | Rule remains, matches text/cell/OCR consistently and cannot keep the original |
| UI-017 | Mandatory judgment standard | Add `530网 → 5**网` as mandatory and attempt to keep original | Correct masked result is used and keep-original is unavailable |
| UI-018 | Local rule import | Import fictional XLSX/CSV with duplicates and conflicts | Duplicates skip; conflicts require resolution; no source path or rule text enters logs |
| UI-019 | Preserve time expressions | Scan a fictional Office document containing dates and times | Time expressions do not enter review, are not replaced and do not contribute to combination risk |
| UI-020 | Common personal-field masks | Scan fictional names, mobile numbers, ID cards, bank cards, emails and landlines | Suggestions preserve only the approved prefix/suffix: compound names retain the surname, mobile numbers retain the first three and last four digits, and landlines retain the last four digits |
| UI-021 | Standalone bank-card validation | Scan fictional valid and invalid 16–19 digit values without a field label | Only values passing length, boundary and Luhn validation enter review as bank cards; valid values use the approved first-six/last-four mask |
| UI-022 | Completed-review export gate | Resolve the last required item, enter final preview, then repeat with one pending image or object | Completed review enters step 4; any pending required item keeps the primary action disabled |
| UI-023 | Rule-library source layers | Open the encrypted rule library on a new user profile | System built-in types are read-only; industry/place/judgment presets and user rules have distinct sources; presets can be edited/deleted and restored explicitly |
| UI-024 | Public-security and place presets | Scan fictional text containing 公安、网警、技侦、海南省、福建、广东省 | Suggestions use GA、WJ、JZ、HN、FJ、GD; the longest full place name wins without leaving 省/市 suffix fragments |
| UI-025 | Automatic hidden-content handling | Scan a fictional document containing author properties, timestamps, hidden text, comments, revisions, footnotes, endnotes, links and embedded objects | Metadata does not appear in the text todo; hidden rows show `已自动移除`; no hidden-item selector blocks step 4 |
| UI-026 | Visible system detection standards | Open the rule library | A read-only system tab lists at least name, mobile, ID card, bank card, email, landline, address, plate, password/key/token and network identifiers; no edit/toggle/delete action applies |
| UI-027 | Expanded edit and incremental rules | Enter review, select a finding, then save `以后都这样处理` | Edit panel is already expanded; saving incrementally reuses parsed text/OCR cache and preserves non-conflicting decisions |
| UI-028 | Password-free export | Enter step 4 and generate a fictional delivery | No password fields exist; local mapping opens as XLSX, remains under `本地保管`, and the UI keeps the `严禁上传` warning |
| UI-029 | Generic-location false-positive filter | Scan `指导各地市完善流程，并面向各地市开展培训` | Neither generic phrase is shown as a location candidate |

## Security Scenarios

| ID | Scenario | Evidence | Expected |
|---|---|---|---|
| SEC-001 | Source remains untouched | Input hash, size, timestamps before/after | Unchanged |
| SEC-002 | DOCX complete inventory | Canaries in body, table, headers/footers, footnote/endnote, textbox, field, alt text, comment, revision, hidden text, custom XML, hyperlink, media and embedded object | Every part is enumerated and resolved; no forbidden part/canary in AI copy |
| SEC-003 | XLSX complete inventory | Canaries in visible/hidden/veryHidden sheets, hidden rows/columns, cells, formulas, comments, names, headers/footers, links, drawings, external connections, pivot cache and embedded object | Every part is enumerated and resolved; all output areas visible |
| SEC-004 | Metadata clean rebuild | Author/company/title/template/path/thumbnail/custom-property canaries | No source metadata in DOCX/XLSX copy or report |
| SEC-005 | Visual irreversible processing | Original image hash, EXIF/XMP, OCR text, QR payload, seal/signature/photo regions | New media bytes and sanitized pixels; no original metadata/text/payload |
| SEC-006 | Output byte rescan | Independent parser, OOXML unzip, OCR, QR and file-name search | All confirmed originals absent from AI copy/report; only the local-custody mapping contains reversible originals |
| SEC-007 | Mapping isolation | Open the XLSX directly; scan delivery, local custody, logs and package | Mapping opens without a password and exists only under `本地保管`; red warning remains visible |
| SEC-008 | Mapping completeness | Compare transformed entities, occurrences and locations with mapping rows | One-to-one reversible mapping where applicable; no orphan or duplicate mapping |
| SEC-009 | No network | Full flow in disconnected clean Windows VM plus DNS/TCP/UDP observation | No listener/outbound connection or model download; functionality complete |
| SEC-010 | Safe logging | Force parse, OCR and export errors | Logs contain codes only; no original, mapping, full path or raw stack dump |
| SEC-011 | Crash residue | Terminate during recognition, rebuild and mapping generation, then restart | Plain staging is absent or safely cleaned before new work |
| SEC-012 | Formula and link safety | Formula injection strings, WEBSERVICE/HYPERLINK, external workbook, UNC and remote template fixtures | Output contains safe static/string values and no active external relationship |
| SEC-013 | OOXML attack resistance | Zip slip, XML entity, compression bomb, excessive pixels/parts and spoofed extension | Fail closed within resource limits |
| SEC-014 | Idempotency | Process an already sanitized copy again | Existing replacement markers remain stable; no nested mapping |
| SEC-015 | Copy boundary | Search all user-facing copy | No “已脱密”“可安全上传”“100%安全”等保证 |
| SEC-016 | Office interoperability | Open fictional outputs in current desktop Word/Excel | No repair warning; readable structure and stated limitations match report |
| SEC-017 | Encrypted rule-store lifecycle | Reopen, tamper and corrupt `rules.dat` | Current-user DPAPI decrypts valid data; ciphertext contains no rule plaintext; tampered/corrupt data blocks scanning |
| SEC-018 | Rule-library output isolation | Search task outputs, AI copy, HTML report, logs and file properties | No complete rule library, rule name, keyword or replacement pair appears outside the encrypted task mapping |
| SEC-019 | Mandatory-rule export gate | Inject or retain a mandatory-rule source value in staging | Independent output rescan fails and completion is impossible |
| SEC-020 | Refreshed task snapshot | Change the rule library during an active task | Rules apply to cached parsed text/OCR without rereading the file; the refreshed snapshot is the only export baseline |
| SEC-021 | No plaintext task persistence | Complete, fail and restart fictional tasks; inspect LocalAppData and task output | No original value, replacement pair, full source path, decision snapshot or task-history file exists outside the explicit local-custody mapping |
| SEC-022 | DOCX mixed-run preservation | Replace a value spanning one formatted run between differently formatted runs | Replacement inherits the original run style; later runs retain their own style and paragraph spacing uses correct Word units |
| SEC-023 | Automatic hidden-object removal | Inventory every hidden/object kind supported by DOCX/XLSX adapters | Removable hidden parts receive `remove` before review; unresolved dangerous structures still fail closed |
| SEC-024 | Local plaintext mapping isolation | Export without entering a password; inspect delivery, report, logs and AI copy | Mapping is a valid directly openable XLSX only under `本地保管`; warning is present; no mapping value leaks elsewhere; passwords/keys/tokens are absent from the mapping |
| SEC-025 | Secret deletion | Scan labeled password, PIN, token, API key, AccessKey and SecretKey fixtures | Values are automatically removed, cannot be kept, do not enter the AI copy or mapping, and do not survive output rescan |
| SEC-026 | DOCX original-layout preservation | Export the designated `福建省信息化运营管理规范V2.1.docx` | Paragraph/run/numbering/section/table/image-anchor/style counts remain aligned; Word opens without repair |
| SEC-027 | Image review precision | Scan ordinary screenshots/photos plus faces and structured sensitive values | Only faces and real sensitive matches enter review; clean images are silently re-encoded |
| SEC-028 | Incremental rules | Change a rule after partial review | No structure/OCR progress appears; decisions remain; only new/conflicting items reopen |
| SEC-029 | Preset deletion lifecycle | Delete one shipped and one custom rule, restart, then restore defaults | Both stay deleted after restart; explicit restore returns only shipped presets |
| SEC-030 | Encrypted history | Complete and fail tasks, then inspect `history.dat` | DPAPI ciphertext contains no source content, mappings or password; single delete and clear work |
| SEC-031 | Folder queue | Select a folder containing supported, unsupported, temporary and prior-result files | Queue includes only valid DOCX/XLSX; a failed item does not block the next |

## Cross-Surface Checks

- Select/preflight/review/compare/export/report/mapping fields match `03-FIELD_MATRIX.md`.
- Candidate list and context actions match `04-STATE_MATRIX.md`.
- Total, reviewed, ignored, transformed, visual, object and unresolved counts reconcile.
- AI-copy replacement counts and mapping rows reconcile one-to-one where reversible.
- `AI交付` contains only the analysis copy; `本地保管` contains only the directly openable sensitive mapping and report.
- Required acknowledgements, warnings and completion copy are present.

## Regression Scope

| Protected module/entry | Why protected | Test |
|---|---|---|
| Original-file adapter | Must remain read-only | SEC-001 |
| Offline runtime and fixed local models | Any network capability changes the trust model | A-007 / SEC-009 |
| Local mapping lifecycle | Mapping is the highest-value sensitive output and must remain in local custody | SEC-007 / SEC-010 / SEC-011 |
| Clean DOCX/XLSX rebuild and independent rescan | Primary leakage control | SEC-002–SEC-006 |
| Sensitive-image human decision | Automatic visual detection is incomplete; clean images should not create false work | UI-005 / SEC-005 / SEC-027 |
| Fail-closed state machine | Prevents ambiguous results from appearing complete | UI-007 / UI-009 |

## Completion Record

- Deterministic checks: refreshed after the 2026-08-07 version 0.4.0 third-round merge. Ruff, mypy strict (30 source files), release verification (30 source files and 34 model assets), 128 automated tests and the packaged self-test all pass.
- Desktop UI checks: Packaged Windows application launches successfully; Qt interaction tests cover the four-step loop, immediate feedback, folder queue, encrypted history, automatic hidden cleanup, visible/editable preset layers, default-expanded editing, cached incremental rules and password-free export. Detailed packaged-window control-tree interaction could not be executed by the available desktop-control runtime.
- Console/page errors: No unresolved test, type, lint, acceptance, build or packaged self-test error.
- Reviewer result: No unresolved P0 or P1 remains in the current merged-correction scope. Regression coverage includes step-3 completion gating, partial rule overlap, changed rule snapshots, normalized mandatory residuals, bounded regex safety, combination-risk batch exclusion, explicit import-conflict choices, plaintext-persistence rejection and DOCX mixed-run formatting.
- Artifact: `dist/本地文档脱敏工具-Windows-x64.zip`, version 0.4.0, 253,626,041 bytes, SHA-256 `4ec6be5f9286536099dedc7655276738153ed4d353b9a835127247f267c92f59`; ZIP CRC and 1,651-file directory parity pass.
- Remaining business questions: Run the same ZIP on a separate clean, disconnected Windows 10/11 x64 machine and open generated files in desktop Word/Excel before organizational rollout.

## Local Release Gate

- Final implementation approval wording: Received from user — `开干吧` and `按这版实施`.
- Approval date: 2026-07-29.
- Windows build result: Pass on Windows 11 x64; packaged EXE `--self-test` exits 0 and bundled model hashes match.
- Clean-machine offline run: Not yet executed on a second machine; Python subprocess probes block socket creation, UDP, TCP and DNS on the build machine.
- Word/Excel interoperability: Generated DOCX/XLSX reopen and pass structural/byte/OCR checks with independent libraries; desktop Microsoft Word/Excel manual opening is still pending.
- Portable ZIP: `dist/本地文档脱敏工具-Windows-x64.zip`; ZIP CRC/path/content parity checks pass with 1,651 entries.
- Warnings: The executable is not code-signed, so Windows SmartScreen may prompt. Technical checks do not change classification or grant external-release approval.
- Failed build archive path, if any:

This project delivers a local Windows package and does not deploy to a development web environment.
