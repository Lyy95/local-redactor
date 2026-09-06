# 本地文档脱敏工具 MVP Requirement Coverage

Updated: 2026-07-29

Simplify only after every source requirement is mapped.

| ID | Source | Requirement/object/function | Priority | Planned surface | Acceptance evidence | Status |
|---|---|---|---|---|---|---|
| R-001 | 用户表述 | 工具在 Windows 本机运行，断网时功能完整，运行期零外连 | Must | 全局 | 断网与连接监测测试 | Implemented; subprocess probes pass; clean-VM observation pending |
| R-002 | 安全基线 | 原文件只读，永不原地覆盖、移动或重命名 | Must | 文件接入层 | 原文件哈希和时间戳前后不变 | Verified |
| R-003 | 用户表述 | 首版同时支持现代 Word `.docx` 和 Excel `.xlsx` 单文件输入 | Must | 选择文件 | DOCX/XLSX 虚构夹具进入扫描 | Verified |
| R-004 | 安全基线 | `.doc/.xls/.docm/.xlsm/.xlsb`、加密/IRM、宏、扩展名伪装、损坏包和危险压缩包失败关闭 | Must | 选择文件 | 阻断夹具不能进入导出 | Verified |
| R-005 | 用户表述 | Word 输出同格式 DOCX；Excel 输出同格式 XLSX，并保留可理解的内容顺序、表格结构和基本格式 | Must | 对照导出 | Word/Excel 用例与结构比对 | Verified |
| R-006 | Office 安全 | 在高层库读取前完成 OOXML 全部部件、关系、文件名、压缩配额和外部目标清单 | Must | 全面识别 | 包清单覆盖测试 | Verified |
| R-007 | 用户清单 | 自动候选覆盖姓名、身份证号、手机号、地址、车牌、银行/平台等账号 | Must | 文字与表格复核 | 结构化规则、校验和 NER 测试 | Verified |
| R-008 | 用户清单 | 自动候选覆盖单位、部门、项目、系统名称，并支持任务本地词库补充 | Must | 文字与表格复核 | NER、后缀规则与词库测试 | Verified |
| R-009 | 用户清单 | 自动候选覆盖地点、金额、案件编号、设备编号；时间类按最新要求暂不自动识别或替换 | Must | 文字与表格复核 | 类别夹具与语义策略测试 | Verified，时间类由 R-043 覆盖 |
| R-010 | 用户清单 | 自动候选覆盖公网 IP、域名、内网地址、邮箱、用户名 | Must | 文字与表格复核 | 网络标识夹具与关系映射测试 | Verified |
| R-011 | 用户清单 | 对每张嵌入图片运行本地 OCR，图片文字进入与正文相同的实体识别与替换流程 | Must | 图片与二维码复核 | OCR 坐标、替换和复扫测试 | Verified |
| R-012 | 用户清单 | 自动检测二维码及载荷；仅人脸、结构化敏感信息和强制规则命中的图片进入复核，普通图片安全重编码 | Must | 图片与二维码复核 | 敏感图片闭环与普通图片过滤测试 | Verified |
| R-013 | 用户清单 | 枚举并处理文件属性、作者、最后保存者、修订记录、批注和隐藏文字/单元格 | Must | 隐藏内容与对象复核 | 元数据及隐藏内容夹具 | Verified |
| R-014 | 用户清单 | 枚举并处理页眉页脚、水印、附件、OLE/嵌入对象、超链接显示文字与真实目标 | Must | 隐藏内容与对象复核 | OOXML 关系及对象夹具 | Verified |
| R-015 | 用户清单 | 对段落、表格行、工作表和全篇计算组合重识别风险，提示最小必要泛化字段 | Must | 文字与表格复核 | 精确时空+岗位+事件组合用例 | Verified |
| R-016 | Word 规则 | 扫描正文、表格、列表、页眉页脚、脚注尾注、文本框、形状文字、字段、替代文字、批注、修订和隐藏文字 | Must | 全面识别 | DOCX 多部件金丝雀覆盖 | Verified |
| R-017 | Excel 规则 | 扫描所有单元格/公式缓存、工作表名、隐藏/非常隐藏工作表、隐藏行列、批注、定义名称、外链、图片和对象 | Must | 全面识别 | XLSX 多部件金丝雀覆盖 | Verified |
| R-018 | 语义保留 | 默认“平衡模式”保留角色、关系、顺序、数量级和数据类型；另提供“严格模式” | Must | 人工复核/对照导出 | 前后文可理解性用例 | Verified |
| R-019 | 一致性替换 | 人员、单位、部门、项目、系统等使用全文/全工作簿一致别名；日期、金额、地址和网络标识使用类别适配的泛化或结构保持模拟值 | Must | 人工复核/导出 | 跨正文、表格、工作表和图片一致性测试 | Verified |
| R-020 | 离线识别 | 固定离线 OCR、中文 NER、二维码和人脸候选模型随应用提供，启动校验 SHA-256，缺失时禁止联网下载 | Must | 全面识别 | 模型完整性与断网启动测试 | Verified |
| R-021 | 人工复核 | 支持确认、忽略、改类、改处理策略、手动选中文字、手动画图片区域、整图移除和查看全部出现位置 | Must | 人工复核 | 完整交互旅程 | Verified by Qt integration tests and native screenshots |
| R-022 | 图片安全 | 遮挡必须重写像素并重新编码、清除 EXIF/XMP；原始图片字节、可移除遮罩和未处理图像不得进入副本 | Must | 图片复核/导出 | 媒体哈希、OCR、二维码复扫 | Verified |
| R-023 | Word 重建 | 从空白 DOCX 重建标题、段落、列表、表格和基本样式；修订按最终显示状态，批注/隐藏内容可脱敏后转为可见附注或移除 | Must | 导出 | DOCX 结构与禁用部件检查 | Verified |
| R-024 | Excel 重建 | 从空白 XLSX 重建可见单元格、合并、宽高、基本样式和数据类型；公式默认使用缓存显示值，所有输出工作表/行/列可见 | Must | 导出 | XLSX 结构、公式与隐藏状态检查 | Verified |
| R-025 | 对象处理 | 活动超链接、外链、数据连接、宏、ActiveX、远程模板、OLE 和未知对象不得复制；支持的附件可另开任务处理 | Must | 对象复核/导出 | 输出关系允许清单检查 | Verified |
| R-026 | 导出复扫 | 重新解包实际输出，检查 XML、关系、属性、文件名、媒体 OCR、二维码、原始图片哈希和全部确认原值 | Must | 导出检查 | 注入残留必须阻断 | Verified |
| R-027 | 用户补充 | 每次生成一张本地 XLSX 脱敏映射表，含编号、类型、原始值、脱敏值、处理方式、规则来源、次数和位置；不要求输入密码，只能位于 `本地保管` 且明确严禁上传 | Must | 导出/本地保管 | 可直接打开核对，与 AI 交付目录严格隔离 | Confirmed 2026-08-07 |
| R-028 | 映射安全 | 映射表不进入 AI 分析副本、报告、日志或 `AI交付` 目录，并持续标记“严禁上传”；密码、密钥、令牌不进入映射表 | Must | 导出/完成页 | 目录隔离和泄漏扫描 | Confirmed 2026-08-07 |
| R-029 | 检查报告 | 生成不含原值和映射的本地 HTML 报告，记录类别数量、对象清理、低置信度、组合风险、人工决定和输出哈希 | Must | 本地保管 | 报告内容与泄漏扫描 | Verified |
| R-030 | 外发边界 | 不提供 AI 上传、自动复制、分享链接或云同步；状态不得出现“已脱密”“安全可上传” | Must | 全局 | 网络与文案检查 | Verified |
| R-031 | 本地隐私 | 不记录原文、命中值、映射、密码和完整路径；临时目录按任务隔离并尽力清理 | Must | 应用内核 | 崩溃恢复和残留测试 | Verified |
| R-032 | 产出形态 | 交付可解压双击的 Windows 绿色版，无需 Python、Office、浏览器、账号或互联网 | Must | 项目交付 | 全新断网 Windows 机器运行 | Built on Windows 11; clean disconnected Windows 10/11 run pending |
| R-033 | 可用性 | 单窗口四步流程，原文/副本并排，关键风险使用图标、颜色和文字 | Should | 全局 | 1280×720 与高 DPI 视觉检查 | Verified at 1280×720 with native Windows rendering |

## Semantic-Preserving Defaults

平衡模式默认隐藏身份、保留业务语义；严格模式提高泛化强度。用户可逐项调整。

| Category | Balanced default | Strict default | Preserved meaning |
|---|---|---|---|
| 姓名 | 保留姓氏，其余使用星号，如 `张*`、`欧阳**` | 同平衡模式 | 姓氏和姓名长度结构 |
| 身份证号 | 保留前六后四，如 `420101********1234` | 同平衡模式 | 证件地域前缀和尾号核对 |
| 手机号 | 保留前三后四，如 `138****5678` | 同平衡模式 | 运营商号段和尾号核对 |
| 地址 | 泛化为`某市某区`或用户确认粒度 | `某地区` | 行政层级 |
| 车牌 | `车辆甲（小型汽车）` | `车辆01` | 车辆类别、同一车辆关系 |
| 账号 | `对公账户甲`、`平台账号甲` | `账号01` | 账号类别、同一性 |
| 单位 | `甲公司（技术服务商）`或`市级单位甲` | `机构01` | 行业、层级、甲乙方关系 |
| 部门 | `业务部门甲` | `部门01` | 通用职能 |
| 项目 | `数据治理类项目甲` | `项目01` | 项目类别 |
| 系统 | `案件管理类系统甲` | `系统01` | 系统用途 |
| 地点 | 命中行业地名预置时使用大写代号，如 `海南 → HN` | 泛化到大区或省级 | 区域关系与一致性 |
| 时间 | 保留原文，不进入自动候选 | 保留原文，不进入自动候选 | 时间顺序与相对间隔 |
| 金额 | 区间化或统一比例变换 | 更宽区间/数量级 | 大小关系、数量级 |
| 案件编号 | 同格式模拟编号 `CASE-2026-0001` | `案件01` | 年份/类型、同一案件关系 |
| 设备编号 | 结构保持模拟值 `DEVICE-0001` | `设备01` | 同一设备关系 |
| 公网 IP | 映射到 RFC 文档保留地址，如 `192.0.2.17` | `网络地址01` | 主机/关系属性 |
| 内网地址 | 映射到任务模拟私网并尽量保持同网段关系 | `内网地址01` | 内外网属性、拓扑关系 |
| 域名 | `api.org01.example.invalid` | `域名01` | 服务角色、层级 |
| 邮箱 | `user01@org01.example.invalid` | `邮箱01` | 用户与单位关系 |
| 用户名 | `user01`，与邮箱/账号联动 | `用户01` | 同一用户关系 |
| 图片文字 | OCR 定位后按同类规则改写真实像素 | 敏感文字区域整体移除 | 图片上下文与布局 |
| 印章 | 移除印章像素并标注`[印章甲·合同章]` | 整块移除 | 印章存在及类别 |
| 签名 | 移除笔迹并标注`[签名甲·审批人]` | 整块移除 | 签署动作与角色 |
| 二维码 | 移除整个编码区；必要时显示脱敏后的载荷类型 | 整块移除 | 二维码存在及用途 |
| 照片 | 局部实心处理人脸/证件/车牌/屏幕，风险过高则整图移除 | 整图移除 | 经确认可保留的场景信息 |
| 属性/作者/修订/隐藏内容 | 扫描后删除身份历史；有分析价值的内容脱敏后转为可见附注 | 删除 | 当前可见业务内容 |
| 页眉页脚/水印 | 正常文字经脱敏重建；敏感水印移除并报告 | 全部移除 | 页码、必要章节信息 |
| 附件/嵌入对象 | 列清单，移除或作为单独任务处理 | 移除 | 对象存在及类型 |
| 超链接 | 保留脱敏显示文字，目标映射为不可解析文本或移除活动链接 | 转普通文本 | 链接用途 |
| 组合重识别 | 只降低贡献最大的非时间精确字段，如地点/唯一岗位 | 多字段同时泛化 | 事件主干、因果和关系 |

Example:

```text
Original:
2026年7月12日14:36，海川科技有限公司研发部张伟
在广州市天河区某路18号登录星河项目案件协同系统，
账号 zhangwei，内网 IP 10.23.8.17，处理案件 AJ-20260712-0048，
使用设备 DEV-GZ-2391，预算137.6万元。

Balanced:
2026年7月12日14:36，甲公司研发部门的张*
在GD广州市某区登录项目甲的案件协同类系统，
账号 user01，内网 IP 10.254.1.17，处理案件 CASE-2026-0001，
使用设备 DEVICE-0001，预算100万—150万元。
```

## Minimum Loop Requirements

| Step | Actor action | System response | Data/state change | Evidence |
|---|---|---|---|---|
| Entry | 选择 DOCX/XLSX、平衡/严格模式并确认边界 | 只读预检格式、OOXML 部件和危险对象 | `empty → preflighting → scanning/blocked` | UI-001 |
| Scan | 等待本地文字、图片、隐藏内容和组合风险识别 | 建立全量候选与对象清单 | `scanning → review_required` | UI-002 |
| Review | 逐项处理文字、图片和对象；人工补充 | 合并实体、生成语义保留替代值和前后预览 | 全部高风险与图片未决项归零 | UI-003 |
| Key action | 选择本地结果目录 | 在原版式安全副本上改写、生成本地映射表并独立复扫 | `ready → rebuilding → rescanning → completed/check_failed` | UI-004 |
| Result | 查看 `AI交付` 与 `本地保管` 两个目录 | 显示副本、报告和本地映射表，不提供上传 | 三类输出存在且相互隔离 | SEC-001 |
| Return | 结束当前任务 | 清除内存中的任务原文和明文映射 | `completed/blocked → empty` | SEC-002 |

## Non-Functional Boundaries

- Target viewport: Windows 1440×900；最低 1280×720；支持系统缩放。
- Browser/runtime: Python + PySide6 原生桌面应用，不启动本地 HTTP 服务，不依赖浏览器。
- Offline or single-file delivery: 运行时完全离线；首版交付 PyInstaller `onedir` 免安装目录包，不强制单 EXE。
- Performance constraints: 对压缩前大小、解压后总量、XML 数量、图片像素和单元格数量设置硬上限；数值在实现基准测试后写入界面，不承诺处理超大型工作簿。
- Data desensitization: 仓库和测试只使用虚构数据；真实文件、敏感词、明文映射和导出结果不进入项目目录或版本控制。
- Security failure mode: 解析不确定、复扫异常和未知对象均失败关闭，不能自动降级为“通过”。

## Excluded By Confirmation

| Item | Reason | Reconsider trigger |
|---|---|---|
| PDF、PPT、旧式 Word/Excel 和宏格式 | 首版聚焦现代 DOCX/XLSX 的完整安全闭环 | DOCX/XLSX 稳定后明确提出 |
| 宏、活动公式、外链、修订、批注和嵌入对象无损保留 | 必须按安全允许清单清理 | 有经过安全评审的新允许清单方案 |
| 云模型、云 OCR、AI 平台直传 | 与资料不出受控环境的目标冲突 | 获得独立合规批准并另立范围 |
| 账号、数据库、批量任务、后台管理 | 非最小闭环 | 单文件闭环稳定后另行确认 |
| 自动将 AI 返回文档反向还原 | 用户本轮要求的是映射表，自动还原会增加误替换和二次输出风险 | 用户另行确认还原规则 |
| 自动定密、解密或外发审批 | 不属于软件的技术判断能力 | 不纳入本产品 |

## Confirmed UX and Rule-Library Revision

The detailed confirmation package is
`docs/prototype/06-UX_AND_RULE_LIBRARY_REVISION.md`.

| ID | Requirement | Priority | Planned surface | Acceptance evidence | Status |
|---|---|---|---|---|---|
| R-034 | 首页和扫描页大幅减字，每屏只保留一个主任务和一个主操作，详细说明按需展开 | Must | 全局/选文件/自动检查 | UXR-001 | Verified |
| R-035 | 第 3 步改为待办列表与当前卡片，主操作使用“采用建议/修改/保留原文/删除”，不显示内部策略术语 | Must | 确认处理 | UXR-002 / UXR-005 | Verified |
| R-036 | 每次处理必须立即反馈、更新剩余数量并自动进入下一项；失败不能静默 | Must | 确认处理 | UXR-002 / UXR-004 | Verified |
| R-037 | 提供“采用全部普通建议”，但不得批量跳过图片、低置信度未知项、组合风险和嵌入对象 | Must | 确认处理 | UXR-003 / SEC-R-001 | Verified |
| R-038 | 提供本机长期规则库，支持固定替换手工维护与 Excel/CSV 导入 | Must | 规则库 | LIBR-001 / LIBR-002 | Verified |
| R-039 | 提供可复用判断标准，保存适用条件、处理方式、强制级别和正反例 | Must | 规则库 | LIBR-004 / LIBR-005 | Verified |
| R-040 | 命中强制规则或被人工标为必须隐藏的内容只能使用代号、星号形式或删除，不能保留原文 | Must | 扫描/确认处理/导出 | LIBR-004 / SEC-R-002 | Verified |
| R-041 | 规则库使用 Windows 当前用户级加密持久化，损坏或无法解密时失败关闭，不进入日志、报告、AI 副本或任务输出目录 | Must | 本地存储/全局 | LIBR-006 / LIBR-007 | Verified |
| R-042 | 任务保持一份可刷新规则快照；变更时在已解析文字与 OCR 缓存上增量应用，同一实体保持一致，冲突不得静默覆盖 | Must | 扫描/转换/映射表 | LIBR-003 / LIBR-004 / SEC-028 | Verified |
| R-043 | 时间类暂不自动识别、不进入第 3 步、不自动替换，也不参与组合风险；正文时间原样保留 | Must | 扫描/确认处理/导出 | TIME-001 | Confirmed 2026-08-07 |
| R-044 | 常用个人敏感字段默认采用保留结构的星号掩码：姓名保留姓氏，手机号保留前三后四，身份证与银行卡保留前六后四，邮箱保留用户名前两位，带区号固定电话保留后四位 | Must | 自动检查/确认处理/导出 | PII-001 | Confirmed 2026-08-07 |
| R-045 | 内置规则按“敏感类型、识别条件、处理方法、作用范围、优先级、是否强制、结果校验”统一管理；无标签银行卡仅在长度和 Luhn 校验同时通过时自动识别 | Must | 自动检查/规则库/导出 | PII-002 | Confirmed 2026-08-07 |
| R-046 | 禁止固定内部密钥、明文处理决定、明文任务历史和完整路径持久化；映射表按最新用户结论取消密码，但严格限制在 `本地保管` | Must | 生成文件/本地存储 | SEC-021 / SEC-024 | Confirmed 2026-08-07 |
| R-047 | 第 3 步只有在文字与图片必确认项全部处理后才能进入最终效果；隐藏内容自动移除；保存长期规则后增量刷新当前任务 | Must | 确认处理/步骤流转 | UI-022 / UI-025 / SEC-028 | Confirmed 2026-08-07 |
| R-048 | 规则库明确区分系统内置识别、公安行业与地名预置、我的规则；系统能力说明只读，固定与判断标准预置可编辑、停用和删除 | Must | 规则库 | LIBR-008 / SEC-029 | Confirmed 2026-08-07 |
| R-049 | 公安、网警、技侦等公安行业词使用不冲突的大写拼音首字母代号；海南、福建、广东分别默认替换为 HN、FJ、GD，并覆盖全国省级地名 | Must | 规则库/自动检查 | LIBR-009 | Confirmed 2026-08-07 |
| R-050 | Word 安全重建应保留段落间距以及未被删除内容的混合字体、字号、颜色、粗体、斜体和下划线；替换文字继承所在原词格式 | Must | DOCX 导出 | DOCX-STYLE-001 | Confirmed 2026-08-07 |
| R-051 | 文件作者、最后修改者、创建/修改时间以及隐藏文字、批注、修订、脚注尾注、附件、外链和嵌入对象默认自动移除，不再进入逐项确认；无法安全移除的危险对象继续阻断 | Must | 自动检查/确认处理/导出 | UI-025 / SEC-023 | Confirmed 2026-08-07 |
| R-052 | 地点识别必须排除“指导各地市、各地市、各省市、相关地市”等通用行政表达，不能仅因以“市”结尾就认定为真实地点 | Must | 自动检查 | LOC-NEG-001 | Confirmed 2026-08-07 |
| R-053 | 规则库必须以只读表格完整展示系统内置识别标准，至少包括姓名、手机号、身份证、银行卡、邮箱、座机、密码密钥、车牌、地址、网络信息、案件和设备编号等 | Must | 规则库 | UI-026 | Confirmed 2026-08-07 |
| R-054 | 明确带标签的密码、口令、PIN、Token、API Key、AccessKey、SecretKey 等必须自动删除，且不得写入映射表 | Must | 自动检查/导出 | SECRET-001 | Confirmed 2026-08-07 |
| R-055 | 第 3 步选中候选后修改面板默认展开；保存“以后都这样处理”规则后在当前文字与 OCR 缓存上增量应用，不返回第 1 步重复操作 | Must | 确认处理 | UI-027 / SEC-028 | Confirmed 2026-08-07 |
| R-056 | 生成文件页取消映射表密码及二次确认输入；映射表作为含真实原值的本地敏感文件直接生成，并持续显示“严禁上传” | Must | 生成文件/完成页 | UI-028 / SEC-024 | Confirmed 2026-08-07 |
| R-057 | Claude Code 两轮问题记录仅合并经验证且符合最新用户结论的改动；固定内部密钥、明文决策快照和明文任务历史不得恢复 | Must | 全局 | SEC-021 | Confirmed 2026-08-07 |
| R-058 | Word 输出以原文件为格式模板，保留页面、分节、样式、编号、run 格式、表格和图片锨点，同时清理危险对象并复扫 | Must | DOCX 导出 | UI-030 / SEC-026 | Confirmed 2026-08-07 |
| R-059 | 使用指定 `福建省信息化运营管理规范V2.1.docx` 可完成导出，图片残留失败要显示可操作原因 | Must | DOCX/图片/错误反馈 | UI-031 | Confirmed 2026-08-07 |
| R-060 | 判断标准页预置个人信息、凭据、账号网络和业务对象标准，可编辑、停用、删除和恢复默认 | Must | 规则库 | UI-032 | Confirmed 2026-08-07 |
| R-061 | 行业/地名/判断预置只初始化一次，删除后重启不自动恢复 | Must | 规则存储 | UI-033 | Confirmed 2026-08-07 |
| R-062 | 处理中规则变更只增量应用到缓存文字/OCR，保留无冲突决定且不重跑结构扫描和 OCR | Must | 规则库/确认处理 | UI-034 / SEC-027 | Confirmed 2026-08-07 |
| R-063 | 使用 DPAPI 加密保留成功、失败和批次历史，可打开结果、删除单条和清空，不保存原文或映射 | Must | 首页/历史 | UI-035 / SEC-028 | Confirmed 2026-08-07 |
| R-064 | 选择文件夹后生成 DOCX/XLSX 队列，默认当前层、可选子文件夹，单个失败不阻断后续文件 | Must | 选文件/队列/批次汇总 | UI-036 | Confirmed 2026-08-07 |
| R-065 | 图片只将人脸、结构化敏感信息和强制规则命中列为待处理；其他图片自动去元数据并重新编码 | Must | 图片检查/导出 | UI-037 / SEC-029 | Confirmed 2026-08-07 |

## Security Design References

- Microsoft Support: [Remove hidden data and personal information by inspecting documents](https://support.microsoft.com/en-us/office/collab-files/remove-hidden-data-and-personal-information-by-inspecting-documents-presentations-or-workbooks)
- Microsoft Learn: [WordprocessingML document structure](https://learn.microsoft.com/en-us/office/open-xml/word/overview)
- openpyxl: [Loading and saving workbooks](https://openpyxl.readthedocs.io/en/stable/tutorial.html)
- RapidOCR: [Installation and offline models](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/install/)
- spaCy: [Chinese pipelines and rule-based matching](https://spacy.io/models/zh/)
- OpenCV: [QRCodeDetector](https://docs.opencv.org/master/de/dc3/classcv_1_1QRCodeDetector.html)
- msoffcrypto-tool: [Password encryption mode](https://msoffcrypto-tool.readthedocs.io/en/latest/cli.html)
- NIST IR 8053: [De-Identification of Personal Information](https://csrc.nist.gov/pubs/ir/8053/final)
