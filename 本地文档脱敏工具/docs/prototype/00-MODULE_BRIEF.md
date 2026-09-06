# 本地文档脱敏工具 MVP Module Confirmation

Updated: 2026-07-29
Status: Confirmed - UX and rule-library revision implementation authorized

## Problem and User

- Problem to solve: 用户希望借助外部 AI 阅读和分析 Word/Excel 内部敏感资料，但原文件不能直接上传；需要在本机识别正文、表格、图片和隐藏对象中的敏感信息，生成仍保留业务语义与文档结构的分析副本。
- Primary user: 能判断资料来源和外发制度、但不具备文档取证或编程能力的 Windows 办公用户。
- Usage moment: 用户拿到一份现代 Word `.docx` 或 Excel `.xlsx`，准备提交给外部 AI 之前。
- Expected value: 在完全离线的工具中完成 Office 包清单扫描、文字/图片/隐藏内容识别、人工复核、语义保留替换、同格式纯净重建和导出复扫，并生成独立加密的脱敏映射表用于后续对应还原。
- Product boundary: 本工具是“AI 分析副本生成器”，不是定密、解密、脱密鉴定或外发审批工具。

## Source Inventory and Authority

| Priority | Source | Business truth or style reference | Notes |
|---:|---|---|---|
| 1 | 当前会话中的用户表述 | Business truth | 首版至少支持 Excel/Word；覆盖明确列出的文字、图片、文件对象和组合风险；脱敏后仍要看得懂；产出形式必须清楚 |
| 2 | 用户确认后的本确认包 | Business truth | 确认后成为首版实施基线 |
| 3 | Microsoft/Open XML、python-docx、openpyxl 文档 | Security reference | Office 包中正文之外的批注、修订、元数据、外链和隐藏对象需要专门枚举与清理 |
| 4 | NIST IR 8053 去标识指南 | Security reference | 简单替换仍可能存在组合重识别风险 |
| 5 | 当前项目行为 | Existing implementation truth | 新项目，尚无业务代码 |

## Entry and Relationship

- Entry path: 双击 Windows 应用后进入“选择文件”。
- Parent menu/page: 无父级系统；首版为独立单窗口应用。
- Relationship to existing modules: 无。
- Return path: 完成或取消当前任务后返回“选择文件”；关闭任务即清除本次实体映射。

## Minimum Closed Loop

```text
entry -> view/select -> key action -> confirmation
-> result feedback -> data/state reflection -> return
```

Describe the concrete loop:

1. 用户选择单个 `.docx` 或 `.xlsx`，确认工具边界；默认使用“保留可读性”，更严格方式按需展开。
2. 用户可在“规则库”维护固定替换和强制判断标准；规则使用当前 Windows 用户级加密长期保存，处理中变更时增量刷新当前快照。
3. 工具只读预检 OOXML 容器，枚举正文/单元格、图片、隐藏内容、属性、关系、附件和嵌入对象；加密、宏、旧格式、损坏或无法安全解析的对象失败关闭。
4. 工具在本机运行结构化规则、用户规则库、中文实体候选、图片 OCR、二维码/人脸/印章/签名启发式和组合重识别评分。
5. 用户在“文字 / 图片”中确认；可一键采用普通文字和确定性规则建议，仅有人脸、结构化敏感信息或强制规则命中的图片以及低置信度未知项和组合风险须明确决定；隐藏内容和对象自动移除并展示结果。
6. 点击单项操作后界面立即反馈、更新剩余数量并自动进入下一项；命中强制规则的内容不能保留原文。
7. 工具并排预览原内容与“保留可读性”或“更严格”结果；同一实体保持一致代号，保留角色、关系、先后顺序和数量级。
8. 工具在原版式结构的安全副本上生成同格式 `.docx` 或 `.xlsx` AI 分析副本，保留允许的版式并清理未允许的原始部件。
9. 工具重新解包并扫描实际导出文件，复查 XML、关系、媒体、OCR、二维码、元数据和敏感金丝雀。
10. 无阻断项时生成分析副本、本地 HTML 检查报告和可直接打开的本地 XLSX 脱敏映射表；分析副本与映射表自动放入不同目录，映射表严禁上传。
11. 用户只把 `AI交付` 目录中的分析副本交给外部 AI；映射表留在 `本地保管` 目录，用于后续对应还原。

## Pages and Operations

| Surface | Purpose | Required operations | Result feedback |
|---|---|---|---|
| 选文件 | 选择 DOCX/XLSX 并确认处理边界 | 选择文件、使用推荐方式、按需展开更严格方式、打开规则库、开始检查 | 支持、注意或阻断原因 |
| 自动检查 | 枚举文字、单元格、图片、隐藏内容和文件对象并本地识别 | 查看四类进度；按需查看技术清单；取消任务 | 需要确认的总数和阻断原因 |
| 确认处理 | 处理文字、图片和隐藏对象 | 采用建议、修改、保留原文、删除、采用全部普通建议、手动画框、整图移除、以后都这样处理 | 即时完成标记、剩余数、自动下一项、强制规则提示 |
| 生成文件 | 并排核对语义保留效果并生成同格式纯净副本 | 切换前后对照、选择输出目录、设置密码、生成、复扫 | 技术检查完成、完整性警告或复扫阻断 |
| 规则库 | 长期维护固定替换和判断标准 | 新增、编辑、启停、删除、导入 XLSX/CSV、恢复默认预置 | 冲突提示、加密保存和当前缓存增量应用 |

## Must Preserve

- Existing navigation: 无。
- Existing functions: 无。
- Existing fields/states: 无。
- Existing delivery method: 无。
- Security invariants: 原文件只读、零外连、无原文日志、映射表只落在 `本地保管`、全量 Office 部件清单、隐藏对象自动清理、图片敏感命中必审、原版式安全副本、实际导出物复扫。

## Explicit Non-Goals

- 不判断或改变国家秘密、工作秘密或商业秘密的密级和法律状态。
- 不输出“安全可上传”“已脱密”或任何外发许可结论。
- 首版不支持旧格式 `.doc/.xls`、宏格式 `.docm/.xlsm/.xlsb`、PPT/PDF、压缩包、密码/IRM 文件。
- 不承诺印章、签名、照片和组合重识别能全自动准确判断；模型只给候选，全量图片和高风险项必须人工复核。
- 不做人脸身份识别，不根据照片判断具体人员身份。
- 不追求原版式、Word 精确分页、浮动形状、Excel 公式/宏/图表/透视表/外部连接的无损保留。
- 不支持批量任务、文件夹监控、数据库、账号、权限平台、网盘同步和自动审批。
- 不集成云模型、云 OCR、AI 平台上传、遥测、自动更新或远程资源。
- 首版生成本地映射表，但不自动把 AI 返回内容反向替换成还原文档；自动还原属于后续可确认增强。
- 不把分析副本当作可继续盖章、正式排版、执行业务公式或归档的原文件替代品。

## Reuse Plan

- Existing components: 无；新建边界清晰的桌面组件。
- Existing data/config: 使用统一 Office 文档模型、视觉对象模型、候选实体模型、组合风险模型和类别替换配置，界面不得直接操作 OOXML。
- Existing visual patterns: 使用 `DESIGN.md` 与 `06-UX_AND_RULE_LIBRARY_REVISION.md` 中的极简四步流程和风险状态规范。

## Final Deliverables

### Project delivery

```text
本地文档脱敏工具_绿色版.zip
├─ 本地文档脱敏工具.exe
├─ 离线识别组件/
└─ 使用说明.pdf
```

- 解压后双击运行，不需要安装 Python、Office 或联网。
- 项目同时保留源代码、虚构测试文档、检查规则和构建脚本。

### Per-document result

```text
脱敏结果_YYYYMMDD_HHMMSS/
├─ AI交付/
│  └─ AI分析副本.docx   或 .xlsx
└─ 本地保管/
   ├─ 脱敏映射表.xlsx
   └─ 脱敏检查报告.html
```

- Word 输入输出 Word，Excel 输入输出 Excel；分析副本才是拟交给 AI 的文件。
- Word 副本加入脱敏说明页；Excel 副本加入可见的“脱敏说明”工作表。
- 报告仅供本地核对，记录处理类别、位置、对象清理和未决风险，不包含真实敏感值或映射表。
- 映射表包含映射编号、类型、原始值、脱敏值、处理方式、出现次数和 Word/Excel 位置，可直接打开；必须留在 `本地保管`，密码、密钥和令牌不进入映射表。
- 映射表和分析副本默认分目录存放，界面持续标注“映射表严禁上传”；用户遗失密码时工具无法代为恢复。
- 原文件不变。

## Change Scope

### Allowed change paths

- `src/**`
- `tests/**`
- `scripts/**`
- `assets/**`
- `pyproject.toml`
- `requirements*.txt`
- `*.spec`
- `docs/prototype/**`
- `harness/**`
- `DESIGN.md`

### Protected paths and workflows

- `AGENTS.md`：除非新确认的项目规则要求更新，否则实施阶段不修改。
- 项目目录之外的任何文件和配置。
- 用户原文件、真实敏感词典、实体映射和导出副本：不得进入 Git 或测试夹具。
- 原文件只读、零外连、无原文日志和导出复扫四条安全路径。

## Risks and Pending Questions

| Item | Blocks implementation? | Temporary handling |
|---|---:|---|
| 本地中文实体模型、OCR、二维码和人脸候选组件 | No | 已纳入首版，模型随应用离线提供并固定校验值；人工复核仍是完成条件 |
| 印章/签名通用模型准确率不足 | No | 使用 OCR、颜色/笔迹/邻域启发式与全量图片必审兜底，不承诺全自动 |
| Word/Excel 复杂对象无法安全重建 | No | 显示清单，要求移除或作为单独任务处理；未处理则阻断 |
| 后续是否需要自动还原 AI 返回文档 | No | 首版交付加密 XLSX 映射表，满足人工或后续程序化对应还原；自动反向替换另行确认 |

## Confirmation

- Confirmed by: User
- Confirmation date: 2026-07-29
- Initial confirmation wording: `开干吧`
- UX/rule-library revision confirmation date: 2026-07-29
- UX/rule-library revision confirmation wording: `按这版实施`
- Material changes after confirmation: Implement the confirmed revision in `06-UX_AND_RULE_LIBRARY_REVISION.md`.
