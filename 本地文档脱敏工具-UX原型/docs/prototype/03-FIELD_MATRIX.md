# 白底绿色双态侧栏交互原型 Field Matrix

Legend: `●` visible, `read-only` display only, `—` absent.

| Field | Collapsed rail | Expanded task list | Document review | Historical summary | Rule |
|---|---:|---:|---:|---:|---|
| Logo | ● | ● | — | — | Same local asset |
| New / Task / Rules navigation | ● | ● | — | — | Same order and selected state |
| Filename | — | ● | ● | ● | Filename only, never full path |
| Task status | Icon/selection | ● | Pending count | ● | Icon + color + text when expanded |
| Folder-batch progress | — | ● | — | — | `2 / 5`, fictional |
| Time group | — | ● | — | ● | `今天 / 更早` only |
| Original value | — | — | read-only | — | Fictional and current task only |
| Suggested value | — | — | ● | — | Plain-language result |
| Review actions | — | — | ● | — | Adopt/edit/keep/delete |
| Pending count | Selected task indicator | ● | ● | — | Updates immediately |
| Rule citation | — | — | ● | — | Rule type + operable rule name when matched |
| Judgment basis | — | — | ● | — | Always plain-language; details on demand |
| Workflow step | — | Current task status | ● | ● | One shared task state |

## Consistency Rules

- Sidebar expansion changes width only; task order, active task and review state remain unchanged.
- Hidden expanded content is removed from keyboard navigation when collapsed.
- Current task/list status and right-side pending count use the same data source.
- Historical items never show full local paths, source text or reversible mappings.

## Task creation / check / result parity

| Field | New | Check | Review | Generate | Result/History |
|---|---:|---:|---:|---:|---:|
| File display name | ● | ● | ● | ● | ● |
| Type (`DOCX/XLSX`) | ● | ● | ● | ● | ● |
| File size | ● | optional | — | — | — |
| Source mode (`单文件/文件夹`) | ● | ● | — | — | batch label |
| Include subfolders | folder only | read-only | — | — | batch summary |
| Processing mode | ● | read-only | affects copy only | read-only | — |
| Boundary acknowledgement | required | read-only | — | — | — |
| Queue status/reason | folder only | ● | current file | batch state | ● |
| Finding totals by category | — | ● | ● | processed/pending | summary only |
| Output location display name | — | — | — | ● | ● |
| AI analysis copy | — | — | — | planned | ● |
| Mapping table | — | — | — | planned + warning | ● + `严禁上传` |
| Technical report | — | — | — | planned | ● |

## Rule parity

| Field | Rule list | Create/Edit | Test | Review citation | Import conflict |
|---|---:|---:|---:|---:|---:|
| Rule ID | internal | internal | internal | link target | conflict key |
| Rule type | ● | required | ● | ● | ● |
| Name | ● | required | ● | ● | ● |
| Match mode/condition | summary | required | ● | details | ● |
| Treatment/result | summary | required | ● | suggested result | ● |
| Scope | ● | required | selectable sample surface | details | ● |
| Mandatory | badge | ● | ● | disables keep when true | ● |
| Enabled | switch + text | ● | — | only enabled rules cite | ● |
| Positive example | — | required for standards | input seed | — | ● |
| Negative example | — | optional | — | — | ● |
| Updated time | ● | auto | — | revision/details | imported timestamp |

## Simplification parity

| Field/action | Default review | Expanded evidence/manual mode | Generation | History |
|---|---|---|---|---|
| Original and suggested value | ● | ● | confirmed result | count only |
| Cited rule summary | disclosure label | type + name + link | rule snapshot | — |
| Version/source/condition/basis | collapsed | ● | rule snapshot | — |
| One-click adopt-all | primary | still available | unlocks step 4 | processed count |
| Per-item actions | hidden until `逐项调整` | adopt/edit/keep/delete | reflected | summary only |
| Output folder name | — | — | `<原文件名>-脱敏稿` | ● |
| AI copy name | — | — | `<原文件名>-脱敏稿.<ext>` | ● |
