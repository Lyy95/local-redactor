# macOS 运行说明

## 目录关系（容易搞错）

离线资源在仓库外：`…/本地脱敏工具/offline-downloads/`，与 `local-redactor/` 同级。
从本目录引用请用 `../../offline-downloads/`，不要用 `../offline-downloads/`。


V2 现在可以在 Mac 上跑图形界面和命令行。Windows 专属的 DPAPI 已换成：

- Windows：继续用当前用户 DPAPI
- macOS / Linux：本机目录里的 Fernet 密钥文件（权限 600）

数据目录：

```text
~/Library/Application Support/LocalRedactor/本地文档脱敏工具/
  rules.dat
  history.dat
  store.key
```

## 需要的软件

- Python 3.11–3.13：https://www.python.org/downloads/macos/
- Node.js LTS：https://nodejs.org/
- 建议用官方 pkg，不要用系统自带的 `/usr/bin/python3` 去装 PySide6

Apple Silicon（M 系列）和 Intel 都可以，PySide6 有对应 wheel。

## 安装

在 `本地文档脱敏工具-V2` 目录：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install rapidocr onnxruntime
pip install ../../offline-downloads/zh_core_web_sm-3.8.0-py3-none-any.whl
```

若 whl 路径不对，用联网安装：

```bash
python -m spacy download zh_core_web_sm
```

RapidOCR 模型也可直接用已下载的：

`../../offline-downloads/rapidocr-models/*.onnx`

拷到：

`.venv/lib/python3.*/site-packages/rapidocr/models/`

人脸 xml：

`.venv/lib/python3.*/site-packages/cv2/data/haarcascade_frontalface_default.xml`

没有就把 `../../offline-downloads/haarcascade_frontalface_default.xml` 拷过去。

## 编界面

```bash
cd ui
npm ci
npm run build
cd ..
```

## 启动图形界面

```bash
source .venv/bin/activate
python -m local_redactor_v2.app
```

演示数据（不要当正式包）：

```bash
python -m local_redactor_v2.app --demo-docx
```

## 命令行（不需要 Qt 窗口）

```bash
python -m local_redactor_v2.cli \
  "../测试样本/青云专项人员名册-脱敏测试样本.xlsx" \
  --out "../测试样本/脱敏输出" \
  --apply-ordinary --keep-rest --regex-only
```

文件夹也可以：

```bash
python -m local_redactor_v2.cli "../测试样本" --out "../测试样本/脱敏输出" --apply-ordinary --keep-rest --regex-only
```

## 打 Mac 应用包

在这台 Linux 上打不出 `.app`。你在 Mac 上装好依赖后可用 PyInstaller：

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name "本地文档脱敏工具-V2" \
  --add-data "ui/dist/client:ui/dist/client" \
  src/local_redactor_v2/app.py
```

首次建议先用 `python -m local_redactor_v2.app` 确认窗口和选文件能用，再打包。
