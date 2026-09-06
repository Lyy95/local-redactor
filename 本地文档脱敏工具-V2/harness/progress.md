# V2 Harness Progress

## 2026-09-01：第 3 步真实 DOCX 页面按原型修复

- 根因已确认：真实 DOCX 曾使用“整段原文 + 独立识别列表”的临时渲染分支，绕过了原型的正文行内命中和锚定建议卡结构。
- 已增加结构化预览块与命中位置桥接，真实 DOCX 复核页恢复为正文内高亮、选中项下方建议卡、右侧发现列表和原型四项处理操作。
- 原型 CSS 未改；旧版和 UX 原型仍为只读保护区。
- 新增确定性 `step3VisualHarness`，使用虚构 DOCX 验证 1536×1024、1440×900、1280×720 三种窗口尺寸。
- 自动证据：三种尺寸均有 7 个行内锚点、建议卡和右侧列表；无“本机识别结果”降级区、无横向溢出。
- 源码回归：UI build、Ruff、Mypy、`8 passed` 均通过。
- 冻结包根因修复：构建环境曾从 Codex 自带 Poppler PATH 误收集不兼容的 `icuuc.dll`，导致 QtCore WinError 127；构建脚本现过滤 Codex runtime PATH、阻断污染 ICU，并关闭窗口式异常弹窗。
- 新 EXE 隐藏自检 PASS；发布校验 PASS；34 个离线模型资产、Qt WebEngine 和 UI 页面完整；正式 ZIP 已重新生成。
- EXE SHA-256：`1c5393ebb45f93a8d11f6ed8331f0bfed61070d707a5d7b279ad3f0ccc0bf667`。
- ZIP SHA-256：`895b005c0e78ace4611e8a65e4c83073dc9cec0695b7084a26cdaded5b5b950f`。
- A–D 黑盒硬门槛仍保持 pending，不得据此宣布 Gate 2 完成。

## 2026-08-31：Gate 2 正式启动、历史和打包修复进度

- 正式前端冷启动已改为第 1 步：无选中文件、无虚构命中项、无虚构历史；只有显式 `--demo-docx` 才加载原型数据。
- 启动时已通过 QWebChannel 读取本机加密历史；桌面桥接不可用时，选文件明确阻断，不再回退到虚构样例弹窗。
- 构建页面 DOM 已验证：首屏是“选择内容，开始检查”，文件夹按钮在 Gate 2 禁用，无桥接点击文件按钮只显示“本地能力未就绪”。
- Ruff PASS；Mypy PASS；V2 `8 passed`；正式和演示源码桌面壳自检均通过。
- 两次 PyInstaller 打包都完成便携目录，34 个离线资产完整且哈希正确，但冻结 EXE `--self-test` 在 120 秒内未退出，因此未生成 ZIP，不得标记 Gate 2 通过。
- 已将冻结环境的模型校验改为直接访问 `_internal/<package>`，不再为定位资产导入大型库；用当前便携目录模拟冻结校验用时约 0.64 秒。
- 遵循连续两轮无有效包产出即停止的规则，本轮不再第三次打包。下一轮应只执行一次干净构建，验证该单点修复。

## 2026-08-31：离线识别组件复用盘点

- 未联网、未下载模型，旧版目录保持只读。
- V2 当前便携目录已有 RapidOCR 的 3 个 ONNX 模型、ONNX Runtime、spaCy 和 `zh_core_web_sm 3.8.0`；34 个受校验资产中 33 个存在且与旧版 SHA-256 一致。
- 当前已打包目录缺少 OpenCV `haarcascade_frontalface_default.xml`，且缺少 `model-manifest.json`，因此现有发布物不能通过新验收。
- 已复用旧版实现方式：新增本地清单生成、打包携带 OpenCV 资产和清单、EXE 启动时强制离线并按 SHA-256 校验。
- 已移除 `pyproject.toml` 中的 GitHub 中文模型下载地址；后续构建只使用本机已存在的组件，缺失时直接失败。
- 验证：新清单 34 个资产与旧版模型哈希完全一致；Ruff PASS；V2 `4 passed`。尚未重新打包，避免在 Gate 2 主流程修复前制造新的不完整发布物。

## 2026-08-31：Gate 2 验收结论撤回

- 用户对打包软件做黑盒验收后确认三个 P0：启动直接进入第 3 步、第 1 步选择文件不可用、任务历史未显示。
- 代码证据：`ui/src/App.jsx` 仍以 `sampleSources[0]`、`workflowStep = 3`、`taskState = review_required`、`initialFindings`和 `initialHistory` 作为正式启动初始状态。
- 原验收只证明桥接函数和导出服务可单独运行，没有证明打包 EXE 能从第 1 步完成闭环，也没有做历史跨进程重启验收。
- `baselineStatus` 已改为 `gate-2-rejected-startup-file-history-2026-08-31`。A–D P0 硬门槛全部通过前，harness 必须返回失败，不得再声称 Gate 2 完成。

## 2026-08-25：Gate 2 单 DOCX 真实闭环完成

- 已完成：React 原型快照通过 `desktopBridge` 接入 QWebChannel；Python 桥接实现选文件、创建任务、检查、四类复核决定、手工补充、预览、导出和历史。
- 真实文件证据：测试创建 DOCX，完成本地识别、人工替换、生成 `AI交付/本地保管` 三类结果，确认原件 SHA-256 不变、AI 副本不含原值、历史不含完整路径或原文。
- 本地能力：RapidOCR/ONNX Runtime、OpenCV、spaCy 和官方 `zh_core_web_sm` 已纳入运行依赖与打包清单。
- 验证：UI build PASS；Ruff PASS；Mypy PASS；V2 `4 passed`；旧版 `129 passed`；harness `51/51 PASS`。
- 发布物：PyInstaller onedir 和 Windows x64 ZIP 已生成；EXE `--self-test` PASS；release verifier PASS；实际桌面窗口已启动并读取到完整 WebEngine 可访问树。
- 保护证据：旧版和 UX 原型的 156 个基线文件哈希全部一致。
- 未做外部发布或部署。无 Python、无 Node、无网络的独立干净 Windows 机仍需用户环境验收。

## 2026-08-25：侧栏顶部控件精调

- 根据用户标注，展开按钮改为紧贴左侧导航右上角分隔线的绝对定位，不再占用单独垂直布局；Logo 同步上移。
- 验证：Vite 构建通过；`pytest` 2 passed；Ruff 通过。

## 2026-08-11：计划基线与 Gate 1 壳实现

- 阶段：Implementation / Gate 1
- 已完成：确认 V2 必须是 Windows 本地桌面应用；确定旧版和 UX 原型保护；建立第一阶段单文件 DOCX 闭环范围；建立需求、字段、状态和验收矩阵。
- 已完成：原型 React/CSS 已复制为 V2 UI 快照；Vite 相对路径构建通过；PySide6 Qt WebEngine 本地壳启动自检通过；桥接运行时单元测试通过。
- 尚未完成：QWebChannel 前端适配、真实 DOCX 引擎接入、EXE/ZIP 打包、真实文件回归。
- 未授权：部署、发布、修改旧版、继续生成视觉原型。
- 设计基线：用户明确要求 V2 完全按照 `本地文档脱敏工具-UX原型` 实现；原型目录为只读唯一界面设计源。

## 下一步（Gate 3）

1. 用户在干净 Windows 机上验收 Gate 2 便携包。
2. 通过后再按计划迁移规则库、历史操作、XLSX 和文件夹队列。

## 风险

- 旧版当前工作树可能存在未提交修改，迁移前必须记录来源状态。
- PySide6/QML 的最终打包方式需通过一次技术验证确定。
- 当前已确认 Qt WebEngine 壳可运行；PyInstaller 扫描 Qt WebEngine 资源耗时过长，尚未形成包体证据。

## Gate 1 evidence

- UI build: `npm.cmd run build` in `ui/` — PASS.
- Bridge tests: `2 passed`.
- Ruff check: PASS for `src/local_redactor_v2` and `tests/test_bridge.py`.
- Desktop shell self-test: PASS with `QT_QPA_PLATFORM=offscreen`; Qt emitted expected headless GPU fallback warnings, but the process exited with code 0.
- Packaging: NOT PASS/NOT RECORDED. The first two PyInstaller attempts exceeded the execution window while scanning Qt WebEngine resources and were stopped; no generated V2 package is claimed.
- 原型是确定性模拟交互，不代表真实文件处理已完成。
