# 本地文档脱敏工具 V2

V2 是 Windows 本地桌面应用程序重构工程。最终交付为可脱网运行的便携包/EXE，不是网页应用，不依赖浏览器、云端 API、CDN、遥测或上传服务。

## 参考关系

- `../本地文档脱敏工具`：旧版生产程序，保留运行，不在 V2 开发过程中修改。
- `../本地文档脱敏工具-UX原型`：已完成的视觉和交互基线，仅作为界面规范，不作为处理引擎。
- `src/`：V2 正式 Python 源码，包含本地文档引擎、桌面壳和 QWebChannel 桥接。
- `ui/`：受控的 React/CSS 界面快照，通过本地桥接调用 Python，不访问网络。

## 第一交付闭环

单个虚构/测试 DOCX：选择文件 → 自动检查 → 逐项复核 → 生成 AI 副本、脱敏映射表和检查报告 → 历史记录。

## 当前阶段

Gate 2 已完成：单文件 DOCX 真实检查、复核、手工补充、导出与历史闭环已接入。已生成 PyInstaller `onedir` 便携目录和 ZIP，并通过发布物校验。规则库扩展、XLSX 和文件夹队列属于后续 Gate 3。

## 验证入口

- `python scripts/verify_harness.py`：一次执行 UI 构建、壳自检、测试、Ruff、Mypy、保护基线与发布物校验。
- `python scripts/verify_release.py`：校验 EXE、Qt WebEngine、本地 UI、ZIP 和 SHA-256。
- `dist/本地文档脱敏工具-V2/本地文档脱敏工具-V2.exe`：便携目录启动入口。

## macOS 源码运行

见 [docs/MAC.md](docs/MAC.md)。离线 whl/模型在仓库外的 `../../offline-downloads/`（相对本目录）。
