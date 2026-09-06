# 本地文档脱敏工具 Design Baseline

Updated: 2026-07-29

> The simplified review flow and persistent local rule library in
> `docs/prototype/06-UX_AND_RULE_LIBRARY_REVISION.md` were confirmed by the user
> on 2026-07-29 with `按这版实施` and are now the implementation baseline.

## Design Truth

| Priority | Source | Role |
|---|---|---|
| 1 | Current user-confirmed requirement | Business and interaction truth |
| 2 | Current runnable project | Existing layout, components, density, and behavior |
| 3 | Named screenshots/reference pages | Visual reference only unless explicitly promoted |
| 4 | Historical assets | Traceability only |

## Product Context

- Primary users: 需要阅读内部、敏感但经制度允许进行技术脱敏后分析的普通办公人员。
- Usage environment: Windows 10/11 单机受控终端；断网时功能完整。
- Domain tone: 克制、可信、非技术化；强调“保留业务语义、隐藏真实身份”和人工复核，不营造“自动安全”错觉。
- Target viewport: 1440 × 900 优先，最低支持 1280 × 720。
- Accessibility or compliance constraints: 关键状态不能只靠颜色表达；所有阻断原因和下一步都要有文字说明；工具不替代定密、解密和外发审批。

## Locked Layout

- Global navigation: 单窗口四步流程，不增加侧边栏或后台管理。
- Secondary navigation: 顶部轻量步骤条 `选文件 → 自动检查 → 确认处理 → 生成文件`。
- Main content structure: 每屏只突出一个任务和一个主操作；详细检查范围和技术清单默认收起，第 3 步修改面板按最新要求默认展开。
- Review structure: 使用“待办列表 + 当前卡片”，默认显示原内容、建议结果、易懂的修改项和 `采用建议 / 修改 / 保留原文 / 删除`。
- Persistent controls: 顶部常驻 `本机离线`、当前文件名和低干扰 `规则库` 入口；底部固定上一步/下一步主操作。
- Areas this module must not change: 原文件、系统网络设置、用户云盘/剪贴板设置和外部 AI 平台。

## Visual Tokens

| Token | Value | Usage |
|---|---|---|
| Primary color | `#176B62` | 主操作、已选中状态和离线标识 |
| Info color | `#2563EB` | 中性信息和识别中状态 |
| Warning color | `#B45309` | 待复核、内容不完整和制度提醒 |
| Error color | `#B42318` | 阻断、解析失败和复扫残留 |
| Success color | `#15803D` | 仅用于“技术检查完成”，不得写成“安全可上传” |
| Page background | `#F4F6F8` | 主窗口背景 |
| Surface | `#FFFFFF` | 内容面板、卡片和对话框 |
| Border | `#D7DCE2` | 分区、输入框和表格边界 |
| Border radius | 8 px | 卡片、对话框和输入控件 |
| Spacing unit | 8 px | 8 / 16 / 24 / 32 的布局节奏 |
| Type scale | 14 px 基准 | 20 px 页面标题、16 px 分区标题、12 px 辅助说明 |

Do not invent a new design system when the project already has one.

## Component Rules

### Navigation

- 步骤必须按状态解锁；被阻断的任务不能跳到导出检查。
- 用户返回上一步时保留本次任务内的复核结果，但关闭任务后不保留实体映射。

### Tables and Lists

- 主复核页不再使用 8 列密集表格，只展示类别、脱敏后的原文摘要、建议结果、位置和状态。
- 使用 `文字 / 图片 / 隐藏内容` 三个复核标签，只显示各自剩余数量；不做统计仪表盘。
- 长上下文、识别来源、置信度和全部出现位置放入当前卡片的 `查看详情`。
- 操作遵循 `04-STATE_MATRIX.md`。

### Forms

- 文件选择前必须展示处理边界并要求确认“工具不改变密级，外发仍需按单位制度审批”。
- 标签、顺序、必填状态、选项和默认值遵循 `03-FIELD_MATRIX.md`。
- 默认使用“保留可读性（推荐）”；“更严格”放入 `更多设置`，两种模式都允许用户逐项调整。
- 对“忽略候选”“保留图片”“整图移除”“移除附件”“以静态值替代公式”等后果提供清楚说明。

### Details

- 点击候选项时先显示原内容、建议结果和一行原因；前后文、识别方式和全部位置按需展开。
- 原值只在当前任务界面显示，不进入日志、报告和导出包。
- 同一实体在 Word 正文/表格/图片 OCR 与 Excel 单元格/工作表之间可展开核对，并保持统一代号。
- 文本候选显示“保留什么、改变什么”；图片候选显示原图与像素处理后的局部预览。
- 组合风险卡片展示共同出现的字段及建议降低精度的最小字段集合。

### Dialogs and Feedback

- 解析失败、加密文件、旧格式、宏和无法安全拆解的对象必须使用红色阻断页。
- 点击 `采用建议` 后必须立即显示完成标记、减少剩余数量、给出短提示并自动进入下一项；失败不得静默。
- `采用全部普通建议`只处理普通文字和结果确定的本地规则，不得处理图片、低置信度未知项、组合风险、附件和嵌入对象。
- 仅人脸、结构化敏感信息和强制规则命中的图片进入待办；普通 OCR 文字和无敏感命中图片安全重编码后保留。
- 文件属性、隐藏内容、附件和嵌入对象由系统自动移除并展示处理结果；无法安全解析或移除时阻断，不能静默带入副本。
- 导出完成文案固定为“技术检查已完成，仍需按单位制度确认是否可外发”。
- 空状态、识别中、待复核、复扫失败和完成状态均要有明确下一步。

### Output Result

- 完成页必须直接展示用户实际拿到的三个层次：
  1. `本地文档脱敏工具_绿色版.zip`：项目最终交付，解压后双击运行。
  2. `AI交付/AI分析副本.docx` 或 `.xlsx`：每次任务中真正交给 AI 的文件。
  3. `脱敏检查报告.html` 与可直接打开的 `脱敏映射表.xlsx`：仅在本机核对和后续还原，映射表严禁上传。
- Word 副本首页、Excel 副本首个“脱敏说明”工作表必须说明别名、模拟日期、模拟号码和区间金额不是真实事实。
- 完成页按 `AI交付` 和 `本地保管` 两张卡片分开显示；映射表使用红色“严禁上传”标识。
- 生成前不再设置映射表密码；必须持续显示映射表含真实原值、仅限本地保管且严禁上传的警示。
- 完成页不提供“上传 AI”按钮，只提供打开 `AI交付`、打开 `本地保管` 和查看报告。

## Copy and Data

- 使用简洁、正式、易懂的中文，不使用“零风险”“100%识别”等保证性措辞。
- 不在面向用户的界面暴露 `演示`、`模拟`、`当前阶段` 等内部研发词。
- 使用虚构机构、人员、编号和事件；样例统一使用 `GA` 等非真实标识。
- 文件列表和报告不显示原始完整路径；导出文件使用中性名称。
- 不主动复制内容到系统剪贴板，避免剪贴板同步带来的额外风险。
- 脱敏副本必须显式标注“别名/替代值”，避免 AI 把替代信息当成真实事实；该提示不使用内部研发语气。

## Visual QA

- 在目标窗口尺寸和最低窗口尺寸下检查。
- 检查中文长文件名、Word 长段落、Excel 宽表格、图片局部框选、候选列表、对话框、滚动和高 DPI 显示。
- 检查每个风险状态都有图标、颜色和文字三重表达。
- 检查平衡模式前后仍可理解角色、关系、顺序和数量级。
- 截图只支持视觉核对，不能代替完整桌面交互验证。
- 重大差异和已接受取舍记录在 `harness/progress.md`。

## Round 3 experience rules

- DOCX output edits the reviewed values inside a sanitized clone of the original OOXML layout; it no longer rebuilds the document from a blank container.
- The first page supports a single file or a folder queue and shows a compact encrypted-history table.
- Rule changes during review stay on the current step and use cached parsed text/OCR results.
- Shipped fixed replacements and judgment standards behave like manageable local rows; only the read-only built-in-recognition explanation is immutable.
- Image review lists faces and confirmed structured sensitive matches only. Clean images remain in place after metadata removal and re-encoding.
