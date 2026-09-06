# 本地文档脱敏工具 MVP Field Matrix

Legend: `●` visible, `*` required, `○` optional, `read-only`, `—` absent.

## Document Task

Legend: `●` visible, `*` required, `○` optional, `read-only`, `—` absent.

| Field | Select | Preflight | Review | Export | Report | Source and rule |
|---|---:|---:|---:|---:|---:|---|
| Input display name | ● | ● | ● | ● | — | 仅显示文件名，不显示完整路径 |
| Input type | read-only | ● | ● | ● | ● | DOCX / XLSX |
| File size | read-only | ● | — | — | ● | 不记录到应用日志 |
| Processing mode | * | ● | ● | ● | ● | 平衡模式 / 严格模式，默认平衡 |
| Page/sheet/section count | — | ● | ● | — | ● | Word 页/节估算；Excel 工作表/行列 |
| Boundary acknowledgement | * | read-only | read-only | read-only | ● | 不改变密级，外发仍需制度确认 |
| Preflight status | — | ● | ● | ● | ● | supported / warning / blocked |
| OOXML part/relation count | — | ● | ● | ● | ● | 清单扫描必须覆盖全部部件 |
| Text/cell extraction coverage | — | ● | ● | ● | ● | 不确定时阻断 |
| Image/drawing count | — | ● | ● | ● | ● | 每个对象都必须有人工处理决定 |
| Hidden/object count | — | ● | ● | ● | ● | 属性、隐藏、批注、修订、附件、外链等 |
| Combination-risk count | — | ● | ● | ● | ● | 高风险项未解决时不得导出 |
| Total finding count | — | ● | ● | ● | ● | 仅显示数量，不写入原始值 |
| Unreviewed finding count | — | — | ● | ● | ● | 导出前必须为 0 |
| Result root directory | — | — | — | * | — | 用户选择；自动建立 `AI交付/本地保管` |
| Analysis-copy format | — | — | — | read-only | ● | DOCX 输入输出 DOCX；XLSX 输入输出 XLSX |
| Analysis-copy name | — | — | — | read-only | ● | `AI交付/AI分析副本.docx` 或 `.xlsx` |
| Mapping password | — | — | — | — | — | 最新用户结论取消密码输入 |
| Mapping-table name | — | — | — | read-only | ● | `本地保管/脱敏映射表.xlsx`，可直接打开，严禁上传 |
| Report name | — | — | — | read-only | ● | `本地保管/脱敏检查报告.html`，无远程资源 |
| Output SHA-256 | — | — | — | read-only | ● | 记录副本、映射表和报告哈希 |
| Technical check status | — | — | — | ● | ● | completed / warning / failed |

## Finding

| Field | Candidate list | Context detail | Editable | Exported copy | Report | Source and rule |
|---|---:|---:|---:|---:|---:|---|
| Finding ID | ● | ● | — | — | — | 任务内随机 ID，不跨任务关联 |
| Modality | ● | ● | — | — | 仅计数 | text / cell / image / metadata / hidden / relation |
| Category | ● | ● | ● | 通过别名、模拟值或视觉标签体现 | 仅类别计数 | 见类别选项 |
| Original value | 局部遮罩 | ● | — | — | — | 仅当前任务内存；禁止日志/报告 |
| Context | 摘要 | ● | — | 脱敏后上下文 | — | 只在界面内展示原文上下文 |
| Source location | ● | ● | — | — | 仅位置标识 | Word 部件/段落/表格；Excel 工作表/单元格；图片坐标 |
| Detector | ● | ● | — | — | 仅来源计数 | rule / task-term / NER / OCR / QR / vision / manual |
| Confidence | ● | ● | — | — | 分级计数 | low / medium / high；不等同安全概率 |
| Occurrence count | ● | ● | — | — | ● | 相同实体归一后的数量 |
| Combination-risk score | ● | ● | — | — | 分级计数 | 显示共同贡献字段 |
| Review decision | ● | ● | * | — | 决策计数 | transform / keep-as-false-positive / remove |
| Replacement method | ● | ● | * | 结果值 | 类别计数 | alias / simulate / generalize / range / pixel-redact / remove |
| Preserved semantics | ● | ● | ● | 结果语义 | — | 角色、层级、顺序、数量级、同一性等 |
| Replacement value | ● | ● | ○ | ● | — | 姓名保留姓氏；手机、身份证和银行卡保留批准的前后位；邮箱保留用户名两位；固定电话保留后四位；可人工修改 |
| Visual bounding box | 图片项 | ● | ● | 像素结果 | — | 图片必须支持手动画框和整图处理 |
| Object disposition | 对象项 | ● | ● | 占位或移除 | 决策计数 | include-as-visible-note / remove / separate-task |
| Ignore reason | — | ● | * when ignored | — | 仅原因类别 | 忽略候选必须给出原因类别 |

## Local Rule Library

The library has two user-facing types: `固定替换` and `判断标准`.

| Field | Fixed replacement | Judgment standard | Add/edit | Persisted | Task mapping/report | Rule |
|---|---:|---:|---:|---:|---:|---|
| Rule ID | read-only | read-only | — | encrypted | Mapping source only / — | Random local ID; not a cross-user identifier |
| Rule name | ○ | * | ● | encrypted | Mapping source / report count only | Rule names never enter the HTML report |
| Source term | * | ○ | ● | encrypted | Local-custody mapping only | Exact or case-insensitive fixed match |
| Replacement/code | * | ○ | ● | encrypted | Result / local-custody mapping | `公安 → GA`, `网警 → WJ` |
| Match condition | Literal contains | * | ● | encrypted | — | Fixed replacements match the literal source term inside supported text; standards support equals, contains, controlled format, any/all keywords, or manual-only |
| Output action | Fixed code | * | ● | encrypted | Result / method count | Fixed code, middle masking, sequence code, or remove |
| Code prefix | — | ○ | ● | encrypted | Result / local-custody mapping | User-defined opaque prefix such as `jz` or `qb` |
| Correct example | read-only pair | * | ● | encrypted | — | For example `530网 → 5**网` |
| Incorrect example | — | ○ | ● | encrypted | — | Calibration only |
| Mandatory | Default true | * | ● | encrypted | Rule source only | Mandatory match cannot keep original |
| Applies to | All supported text surfaces | * | ● | encrypted | — | Text, cells, OCR, headers/footers, hidden text |
| Enabled | * | * | ● | encrypted | — | Disabled rules remain stored |
| Priority | read-only/default | read-only/default | — | encrypted | — | Current task > fixed > mandatory standard > built-in |
| Created/updated time | read-only | read-only | — | encrypted | — | Local audit only; never logged with rule text |

Storage and lifecycle:

- `rules.dat` uses Windows current-user DPAPI encryption with no plaintext fallback.
- Loading/decryption/integrity failure blocks scanning.
- Each scan freezes one rule snapshot; changing the library requires rescanning the active task.
- Import supports local read-only `.xlsx` and `.csv`; complete duplicates are skipped and conflicts require resolution.

## Mapping Table

| Column | Required | Contains sensitive original? | Rule |
|---|---:|---:|---|
| Mapping ID | * | No | 稳定编号，如 `PERSON-001` |
| Category | * | No | 与 Finding 类别一致 |
| Original value | * | Yes | 只存在于 `本地保管` XLSX；密码、密钥、令牌不写入 |
| Replacement value | * | No | 与分析副本完全一致 |
| Replacement method | * | No | 别名、模拟、泛化、区间、移除等 |
| Rule source/name | ○ | Indirect risk | 仅实际命中的规则名称；只存在于 `本地保管` XLSX |
| Occurrence count | * | No | 与复核结果一致 |
| Locations | * | Indirect risk | Word 段落/表格/图片；Excel 工作表/单元格 |
| Restore note | ○ | No | 说明日期平移、金额比例等还原规则 |

Mapping rules:

- 生成文件页不再要求映射表密码；映射表作为本地敏感文件直接生成。
- 映射表不得进入 `AI交付`、HTML 报告或 AI 分析副本。
- 完成页和文件内首行均显示“仅限本地保管，严禁上传”。

## Filters and Options

| Field | Type | Options/source | Default | Dependency | Validation |
|---|---|---|---|---|---|
| Processing mode | Radio | 平衡、严格 | 平衡 | — | 必选 |
| Finding category | Select | 姓名、身份证、手机、地址、车牌、账号、单位、部门、项目、系统、地点、金额、案件编号、设备编号、IP、域名、内网地址、邮箱、用户名、图片文字、印章、签名、二维码、照片、文件属性、修订、批注、隐藏内容、页眉页脚、水印、附件、嵌入对象、超链接、组合风险、其他；时间类暂不进入自动候选 | Detector result | — | 必选 |
| Review status | Filter | 待处理、已替换、已忽略 | 待处理 | — | — |
| Review surface | Tabs | 文字、图片、隐藏内容 | 文字 | — | — |
| Detector source | Filter | 规则、任务敏感词、NER、OCR、QR、视觉候选、手动 | 全部 | — | — |
| Replacement action | Select under `修改` | 换成统一代号、星号掩码、换成虚构值、模糊一些、显示大致范围、调整数值但保持大小关系、遮住敏感区域、保留成普通文字、删除 | Category default | Category/mode | 时间不进入候选；内部枚举不在主界面显示 |
| Ignore reason | Select | 误报、公开信息、分析必需且经确认、其他 | — | Decision=ignore | 必选 |
| Image action | Select | 保留经处理图片、局部实心遮挡、整图移除 | — | Image finding | 每张图必选 |
| Hidden content action | Read-only result | 自动移除 | 移除 | Hidden finding | 不要求用户逐项选择 |
| Embedded object action | Read-only result | 自动移除；无法安全处理时阻断 | 移除 | Object finding | 无安全处理结果时禁止导出 |
| Mapping password | — | 不显示、不输入 | — | Export | 最新用户结论取消密码输入 |
| Rule source | Read-only label | 系统内置、行业预置、我的规则 | System derived | Rule library | 系统内置能力说明不可编辑/停用/删除；行业与判断标准预置可编辑、停用和删除 |
| Rule sample | Text input + preview | Fictional sample | — | Rule editor | 保存前显示命中与替换结果；不得写入日志 |

## Consistency Rules

- 同一标准化实体在一个任务内只能有一个类别和一个替换值。
- 命中强制规则的实体不能选择保留原文；导出前必须再次校验。
- 替换结果不参加当前扫描的二次规则匹配，避免连锁替换。
- 同一原值出现在 Word/Excel 文字、表格、图片 OCR 和隐藏部件时，复核决定和替换方式必须同步。
- 被用户确认替换的原值不得出现在 AI 分析副本、HTML 报告、日志和临时清单中；只允许出现在 `本地保管` 映射表；密码、密钥和令牌例外，必须直接删除且不进入映射表。
- 忽略候选必须记录原因类别，但报告不得包含被忽略的原文。
- 平衡模式必须保留角色、关系、先后顺序和数量级；严格模式也必须保留实体之间的同一性。
- Word/Excel 副本、映射表和报告使用同一任务快照生成，映射行与副本替代值必须一一对应。
- 图片必须有人工决定；隐藏内容、批注、附件和对象必须由系统显式记录自动移除结果，不能依赖格式库静默丢失。
- 字段变化必须先更新本矩阵，再修改源码。

## Round 3 additions

| Surface | Field | Rule |
|---|---|---|
| File selection | Source folder / include subfolders | Build a DOCX/XLSX queue; exclude `~$`, hidden files and generated result folders |
| File queue | Current / completed / failed / pending | One failed file does not block the next file |
| History | Time, display name, type, status, counts, result directory | Entire store is current-user DPAPI encrypted; never store original text, mappings or passwords |
| Judgment standards | Match method, action, mandatory, positive and negative examples | Shipped presets are visible, editable, disableable and deletable |
| Rule lifecycle | Preset version | Seed once during migration; deletion persists until explicit restore |
| Active review | Incremental-rule result | Reuse parsed text and OCR cache, retain non-conflicting decisions, show newly added count |
| Image review | Face or structured sensitive match | Ordinary OCR text and clean images do not enter review; all retained images are re-encoded |
