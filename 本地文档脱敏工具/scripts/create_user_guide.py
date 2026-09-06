from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "assets" / "使用说明.pdf"
FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")

TEAL = colors.HexColor("#176B62")
DARK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#5F6B76")
LINE = colors.HexColor("#D7DCE2")
LIGHT = colors.HexColor("#F4F6F8")
GREEN_BG = colors.HexColor("#ECFDF3")
ORANGE = colors.HexColor("#B45309")
ORANGE_BG = colors.HexColor("#FFF7ED")
RED = colors.HexColor("#B42318")
RED_BG = colors.HexColor("#FEF3F2")


def register_fonts() -> None:
    if not FONT_REGULAR.is_file() or not FONT_BOLD.is_file():
        raise RuntimeError("缺少微软雅黑字体，无法生成中文使用说明")
    pdfmetrics.registerFont(TTFont("GuideSans", str(FONT_REGULAR), subfontIndex=0))
    pdfmetrics.registerFont(TTFont("GuideSansBold", str(FONT_BOLD), subfontIndex=0))


class NumberBadge(Flowable):
    def __init__(self, number: int) -> None:
        super().__init__()
        self.number = number
        self.width = 12 * mm
        self.height = 12 * mm

    def draw(self) -> None:
        canvas = self.canv
        canvas.setFillColor(TEAL)
        canvas.circle(6 * mm, 6 * mm, 5.5 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("GuideSansBold", 11)
        canvas.drawCentredString(6 * mm, 4.25 * mm, str(self.number))


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleCN",
            parent=base["Title"],
            fontName="GuideSansBold",
            fontSize=28,
            leading=39,
            textColor=TEAL,
            alignment=TA_LEFT,
            spaceAfter=10 * mm,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleCN",
            parent=base["BodyText"],
            fontName="GuideSans",
            fontSize=13,
            leading=22,
            textColor=MUTED,
            spaceAfter=8 * mm,
        ),
        "h1": ParagraphStyle(
            "H1CN",
            parent=base["Heading1"],
            fontName="GuideSansBold",
            fontSize=20,
            leading=29,
            textColor=TEAL,
            spaceBefore=1 * mm,
            spaceAfter=6 * mm,
        ),
        "h2": ParagraphStyle(
            "H2CN",
            parent=base["Heading2"],
            fontName="GuideSansBold",
            fontSize=13,
            leading=20,
            textColor=DARK,
            spaceBefore=7 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "BodyCN",
            parent=base["BodyText"],
            fontName="GuideSans",
            fontSize=10.5,
            leading=18,
            textColor=DARK,
            spaceAfter=3 * mm,
        ),
        "small": ParagraphStyle(
            "SmallCN",
            parent=base["BodyText"],
            fontName="GuideSans",
            fontSize=8.5,
            leading=14,
            textColor=MUTED,
        ),
        "card_title": ParagraphStyle(
            "CardTitleCN",
            parent=base["BodyText"],
            fontName="GuideSansBold",
            fontSize=11,
            leading=18,
            textColor=DARK,
        ),
        "card_body": ParagraphStyle(
            "CardBodyCN",
            parent=base["BodyText"],
            fontName="GuideSans",
            fontSize=9.5,
            leading=16,
            textColor=DARK,
        ),
        "center": ParagraphStyle(
            "CenterCN",
            parent=base["BodyText"],
            fontName="GuideSans",
            fontSize=10,
            leading=17,
            textColor=DARK,
            alignment=TA_CENTER,
        ),
        "code": ParagraphStyle(
            "CodeCN",
            parent=base["Code"],
            fontName="GuideSans",
            fontSize=9,
            leading=16,
            textColor=DARK,
            leftIndent=3 * mm,
        ),
    }


def page_decor(canvas, document) -> None:  # type: ignore[no-untyped-def]
    width, height = A4
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFont("GuideSans", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9.5 * mm, "本地文档脱敏工具 0.4")
    canvas.drawRightString(
        width - 18 * mm,
        9.5 * mm,
        f"第 {document.page} 页",
    )
    canvas.restoreState()


def card(
    title: str,
    body: str,
    styles: dict[str, ParagraphStyle],
    *,
    background=LIGHT,
    accent=TEAL,
) -> Table:
    table = Table(
        [
            [
                "",
                [
                    Paragraph(title, styles["card_title"]),
                    Spacer(1, 1.2 * mm),
                    Paragraph(body, styles["card_body"]),
                ],
            ]
        ],
        colWidths=[2.5 * mm, 159 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BACKGROUND", (0, 0), (0, 0), accent),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 0),
                ("TOPPADDING", (1, 0), (1, 0), 4 * mm),
                ("BOTTOMPADDING", (1, 0), (1, 0), 4 * mm),
                ("LEFTPADDING", (1, 0), (1, 0), 5 * mm),
                ("RIGHTPADDING", (1, 0), (1, 0), 5 * mm),
            ]
        )
    )
    return table


def step_row(
    number: int,
    title: str,
    body: str,
    styles: dict[str, ParagraphStyle],
) -> KeepTogether:
    table = Table(
        [
            [
                NumberBadge(number),
                [
                    Paragraph(title, styles["card_title"]),
                    Paragraph(body, styles["card_body"]),
                ],
            ]
        ],
        colWidths=[16 * mm, 145 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )
    return KeepTogether([table, Spacer(1, 2 * mm)])


def bullet(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(f"• {text}", styles["body"])


def make_pdf() -> Path:
    register_fonts()
    styles = build_styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame = Frame(
        18 * mm,
        19 * mm,
        A4[0] - 36 * mm,
        A4[1] - 34 * mm,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    template = PageTemplate(id="guide", frames=[frame], onPage=page_decor)
    document = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        title="本地文档脱敏工具使用说明",
        author="Local Redactor",
        subject="离线生成供 AI 分析使用的 Word 和 Excel 副本",
    )
    document.addPageTemplates([template])
    story: list[Flowable] = []

    story.extend(
        [
            Spacer(1, 26 * mm),
            Paragraph("本地文档脱敏工具", styles["title"]),
            Paragraph(
                "在资料不离开本机的前提下，为 Word 或 Excel 生成一份便于外部 AI 阅读的分析副本。",
                styles["subtitle"],
            ),
            Spacer(1, 6 * mm),
            card(
                "你最终会得到什么",
                "<b>AI交付</b>：一份同格式的 AI分析副本.docx 或 .xlsx。<br/>"
                "<b>本地保管</b>：可直接打开的脱敏映射表.xlsx，以及不含原值的脱敏检查报告.html。映射表严禁上传。",
                styles,
                background=GREEN_BG,
            ),
            Spacer(1, 7 * mm),
            card(
                "先说清楚边界",
                "本工具提供技术识别、人工确认、纯净重建和导出复扫。"
                "技术检查完成不等于文件已脱密，也不代表可安全上传或已获准外发。"
                "是否能交给外部 AI，仍须遵守所在单位的保密和数据管理制度。",
                styles,
                background=ORANGE_BG,
                accent=ORANGE,
            ),
            Spacer(1, 12 * mm),
            Paragraph("版本 0.4  |  Windows 绿色版  |  完全离线运行", styles["small"]),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("1. 能处理什么", styles["h1"]),
            Paragraph("可处理单个现代 Office 文件，也可从文件夹建立逐个确认的处理队列。", styles["body"]),
            Table(
                [
                    [
                        Paragraph("<b>支持</b>", styles["center"]),
                        Paragraph("<b>暂不支持</b>", styles["center"]),
                    ],
                    [
                        Paragraph(
                            "Word .docx<br/>Excel .xlsx<br/>正文、表格、单元格、图片、"
                            "页眉页脚、批注、隐藏内容、超链接和嵌入对象清单",
                            styles["card_body"],
                        ),
                        Paragraph(
                            ".doc、.xls、.docm、.xlsm、.xlsb<br/>PDF、PPT、压缩包<br/>"
                            "密码或 IRM 文件、含宏文件、损坏文件",
                            styles["card_body"],
                        ),
                    ],
                ],
                colWidths=[81 * mm, 81 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, 0), GREEN_BG),
                        ("BACKGROUND", (1, 0), (1, 0), RED_BG),
                        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ]
                ),
            ),
            Spacer(1, 7 * mm),
            Paragraph("会识别哪些内容", styles["h2"]),
            bullet("身份信息：姓名、身份证号、手机号、座机、邮箱、地址、车牌和账号。", styles),
            bullet(
                "业务信息：单位、部门、项目、系统名称、地点、金额。时间保持原文，"
                "暂不自动识别或替换。",
                styles,
            ),
            bullet("编号和网络：案件编号、设备编号、IP、域名、邮箱、用户名。", styles),
            bullet("凭据：带明确标签的密码、口令、PIN、Token、API Key 和密钥会自动删除。", styles),
            bullet("图片内容：运行 OCR、二维码和人脸检查；仅人脸、结构化敏感信息和强制规则命中进入待办。", styles),
            bullet(
                "隐藏信息：文件属性、作者、修订、批注、隐藏文字、页眉页脚、水印、"
                "附件、嵌入对象和超链接。",
                styles,
            ),
            bullet("组合风险：普通字段共同出现后可能指向特定人员或事件。", styles),
            Spacer(1, 4 * mm),
            card(
                "自动识别不是最终结论",
                "图片与组合风险候选可能漏检或误报。只有人脸、结构化敏感信息、"
                "二维码或强制规则命中的图片需由你决定；普通图片安全重编码，隐藏内容自动清理。",
                styles,
                background=ORANGE_BG,
                accent=ORANGE,
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("2. 四步完成一次任务", styles["h1"]),
            step_row(
                1,
                "选择文件",
                "打开程序，选择一个 .docx/.xlsx，或选择文件夹建立处理队列。默认使用“保留可读性”；"
                "需要更强保护时，可在“更多设置”中改为“隐藏更多细节”。"
                "阅读边界说明并勾选确认。原文件只读，不会被覆盖。",
                styles,
            ),
            step_row(
                2,
                "自动检查",
                "程序在本机检查 Office 文件结构，再识别文字、表格、图片和隐藏对象。"
                "文件若已加密、含宏、损坏或无法安全解析，任务会被阻断。",
                styles,
            ),
            step_row(
                3,
                "确认处理",
                "先点“采用全部普通建议”，快速处理确定性较高的文字和单元格。"
                "敏感图片、低把握内容和组合风险仍需逐项确认；普通图片不进入待办，隐藏内容和对象自动移除。"
                "全部待确认数量归零后，才会进入下一步。",
                styles,
            ),
            step_row(
                4,
                "生成文件",
                "查看原内容和替代效果，选择本地结果目录；不再要求设置映射表密码。"
                "工具重建分析副本并复扫实际落盘文件，通过后才显示完成。",
                styles,
            ),
            Spacer(1, 5 * mm),
            card(
                "保留可读性（推荐）",
                "默认推荐。隐藏具体身份，同时尽量保留角色、关系、时间顺序、"
                "金额数量级和数据类型，适合一般归纳、对比和写作分析。",
                styles,
                background=GREEN_BG,
            ),
            Spacer(1, 4 * mm),
            card(
                "隐藏更多细节",
                "使用人员01、机构01等更强替代，并降低地点和金额精度；时间保持原文。"
                "重识别风险更低，但可读性和分析细节也会减少。",
                styles,
                background=LIGHT,
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("3. 怎样确认处理", styles["h1"]),
            Paragraph("文字与表格", styles["h2"]),
            bullet(
                "<b>采用建议</b>：候选确实敏感，直接使用工具给出的代号或概括结果。",
                styles,
            ),
            bullet(
                "<b>修改</b>：建议值不合适时，直接改成你需要的代号；"
                "点击“以后都这样处理”后，会保存到本机规则库，并在当前文字与 OCR 缓存上增量应用。",
                styles,
            ),
            bullet(
                "<b>保留原文</b>：仅用于确认是误报、公开信息或确有必要保留的内容。"
                "命中强制规则时不能保留原文。",
                styles,
            ),
            bullet(
                "<b>删除</b>：内容没有必要进入分析副本，或无法找到合适代号时使用。",
                styles,
            ),
            Paragraph("图片与二维码", styles["h2"]),
            bullet(
                "<b>遮住敏感区域</b>：对已识别区域重写真实像素并重新编码；"
                "遮挡区会写入代号或编号，并在图片旁保留对应说明。"
                "如果没有可靠区域，程序会按整图处理。",
                styles,
            ),
            bullet(
                "<b>删除整张图片</b>：图片风险高、无分析价值或无法可靠识别时使用。",
                styles,
            ),
            bullet(
                "<b>确认安全后保留</b>：仅在逐项确认图片候选均为误报或可保留时使用。"
                "有已确认敏感候选时，工具会阻止直接保留。",
                styles,
            ),
            Paragraph("隐藏内容与对象", styles["h2"]),
            bullet(
                "文件属性、隐藏文字、批注、修订、脚注尾注、外链、附件和嵌入对象由系统自动移除，不再逐项询问。",
                styles,
            ),
            bullet(
                "隐藏内容页保留处理清单，结果统一显示“已自动移除”，方便核对程序做了什么。",
                styles,
            ),
            bullet(
                "无法安全解析或移除的危险对象仍会阻断任务，不会为了减少确认而静默带入副本。",
                styles,
            ),
            Spacer(1, 4 * mm),
            card(
                "组合风险怎么判断",
                "如果精确地点、少见岗位和特定事件一起出现，即使每项看似普通，"
                "也可能指向唯一人员。优先降低最少必要字段的精度，再保留事件主干。",
                styles,
                background=ORANGE_BG,
                accent=ORANGE,
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("4. 让规则越用越顺手", styles["h1"]),
            Paragraph(
                "点击右上角“规则库”，可以沉淀长期使用的固定替换和判断标准。"
                "这些规则只保存在当前 Windows 用户的本机加密文件中，关闭程序后仍会保留。",
                styles["body"],
            ),
            Paragraph("固定替换", styles["h2"]),
            bullet(
                "适合明确且稳定的对应关系，例如“公安 → GA”“网警 → WJ”。"
                "原词出现在一句话中时，也会只替换命中的部分。",
                styles,
            ),
            bullet(
                "规则库会区分系统内置识别、行业与地名预置、我的规则。"
                "系统内置页完整展示姓名、手机、身份证、银行卡、邮箱、座机、密码、车牌等标准，"
                "始终只读；行业、地名和判断标准预置可编辑、停用或删除，需要时可点击“恢复默认预置”。",
                styles,
            ),
            bullet(
                "已内置公安行业和全国省级地名常用代号，例如“技侦 → JZ”、"
                "“海南 → HN”、“福建 → FJ”、“广东 → GD”。时间仍保持原文。",
                styles,
            ),
            bullet(
                "新增或编辑规则时，可输入一段虚构样例并点击“验证样例”，"
                "确认实际替换效果后再保存。样例不会写入任务历史。",
                styles,
            ),
            bullet(
                "在确认处理时修改代号并点击“以后都这样处理”，也能直接加入规则库。"
                "保存后不重读文件、不重跑 OCR，且保留无冲突的已完成决定。",
                styles,
            ),
            Paragraph("判断标准", styles["h2"]),
            bullet(
                "适合一类内容的统一处理，例如带编号的内部系统名统一隐藏中间字符："
                "“530网 → 5**网”。",
                styles,
            ),
            bullet(
                "jz、qb 等无法从字面判断含义的代号，不会擅自扩写；"
                "只有命中你明确提供的例子或条件时才会处理。",
                styles,
            ),
            bullet(
                "标记为“强制”的规则命中后，必须改为代号或删除，不能保留原文。",
                styles,
            ),
            Paragraph("导入和维护", styles["h2"]),
            bullet(
                "可下载空白 Excel 模板，批量填写后导入；也支持 CSV。"
                "导入前会校验必填项和示例，错误规则不会静默生效。",
                styles,
            ),
            bullet(
                "导入内容与现有规则处理结果不同时，程序会要求选择“保留现有规则”、"
                "“采用导入规则”或“取消导入”，不会自行覆盖。",
                styles,
            ),
            bullet(
                "可随时新增、编辑、停用或删除自己的规则。多人或多个窗口同时修改时，"
                "旧窗口会提示内容已变化，不会覆盖较新的规则。",
                styles,
            ),
            Spacer(1, 4 * mm),
            card(
                "正在处理文件时改了规则",
                "规则库发生变化后，程序在当前已解析文字和原始 OCR 缓存上增量应用，"
                "仅新增或冲突项重新打开，并用刷新后的唯一规则快照导出。",
                styles,
                background=ORANGE_BG,
                accent=ORANGE,
            ),
            Spacer(1, 4 * mm),
            card(
                "规则库也属于敏感资产",
                "规则名称、原词和示例可能透露单位内部用语。请只在受控电脑使用，"
                "不要把规则模板、加密规则文件或脱敏映射表上传给外部 AI。",
                styles,
                background=RED_BG,
                accent=RED,
            ),
            Spacer(1, 8 * mm),
        ]
    )

    story.extend(
        [
            Paragraph("5. 导出文件放在哪里", styles["h1"]),
            Paragraph(
                "每次成功后都会新建一个带时间的结果目录。只把 AI交付 目录中的分析副本"
                "作为拟交给 AI 的文件；本地保管目录不要上传。",
                styles["body"],
            ),
            Table(
                [
                    [Paragraph("脱敏结果_YYYYMMDD_HHMMSS/", styles["code"])],
                    [Paragraph("├─ AI交付/", styles["code"])],
                    [Paragraph("│  └─ AI分析副本.docx  或  .xlsx", styles["code"])],
                    [Paragraph("└─ 本地保管/", styles["code"])],
                    [Paragraph("   ├─ 脱敏映射表.xlsx", styles["code"])],
                    [Paragraph("   └─ 脱敏检查报告.html", styles["code"])],
                ],
                colWidths=[162 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
                    ]
                ),
            ),
            Spacer(1, 7 * mm),
            card(
                "AI分析副本.docx / .xlsx",
                "在原 Office 版式结构的安全副本上改写，不保留活动外链、宏、OLE 和未知对象。"
                "Word 保留页面、分节、样式、编号、表格和图片锚点；Excel 保留可见单元格和基本样式，"
                "公式默认转换为缓存显示值。",
                styles,
                background=GREEN_BG,
            ),
            Spacer(1, 4 * mm),
            card(
                "脱敏映射表.xlsx",
                "记录映射编号、类别、原始值、脱敏值、处理方式、规则来源、出现次数、"
                "位置和还原说明。"
                "它包含集中后的敏感原值，只能留在本地保管。",
                styles,
                background=RED_BG,
                accent=RED,
            ),
            Spacer(1, 4 * mm),
            card(
                "脱敏检查报告.html",
                "记录处理统计、对象清理、复扫状态和文件哈希，不包含原始敏感值、"
                "映射内容。",
                styles,
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("6. 本地映射表与后续核对", styles["h1"]),
            bullet("生成文件时不再要求设置密码，映射表可以直接用桌面 Excel 或兼容软件打开。", styles),
            bullet("映射表包含真实原值，必须只留在本地保管目录，不能发送、上传或与 AI 分析副本一起交付。", styles),
            bullet("密码、口令、密钥和令牌会直接删除，不写入映射表，避免形成新的凭据集中泄漏点。", styles),
            bullet(
                "首版提供映射表方便人工核对或后续程序化对应；暂不自动还原 AI 返回文档。",
                styles,
            ),
            Spacer(1, 6 * mm),
            card(
                "打开本地映射表",
                "直接使用桌面 Excel 或兼容软件打开。首行红色警示用于提醒该文件含真实原值，严禁上传。",
                styles,
                background=GREEN_BG,
            ),
            Spacer(1, 6 * mm),
            card(
                "映射表严禁上传",
                "映射表集中包含所有原始值，一旦外泄，脱敏副本中的别名可被整体反向对应。"
                "即使分析副本需要交给 AI，映射表也必须留在受控本机。",
                styles,
                background=RED_BG,
                accent=RED,
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("7. 完成前的 30 秒检查", styles["h1"]),
            bullet("原文件仍在原位置，名称、大小和内容未被工具改写。", styles),
            bullet("确认处理页面中的待确认数量均为 0。", styles),
            bullet("前后对照仍能看懂业务角色、关系、顺序和数量级。", styles),
            bullet("AI交付 目录中只有一份 AI分析副本。", styles),
            bullet("本地保管 目录中有可直接打开的映射表和检查报告。", styles),
            bullet("确认映射表首行显示“仅限本地保管，严禁上传”。", styles),
            bullet("首页历史只保存本机加密的文件名、哈希、状态、数量和结果位置，可单条删除或清空。", styles),
            bullet("按单位制度再次确认资料是否允许交给外部 AI。", styles),
            Spacer(1, 6 * mm),
            Paragraph("常见阻断", styles["h2"]),
            Table(
                [
                    [
                        Paragraph("<b>现象</b>", styles["card_body"]),
                        Paragraph("<b>怎么处理</b>", styles["card_body"]),
                    ],
                    [
                        Paragraph("文件无法进入识别", styles["card_body"]),
                        Paragraph(
                            "确认文件是 .docx 或 .xlsx，未加密、未含宏且未损坏。"
                            "另存为新 OOXML 文件后可重试。",
                            styles["card_body"],
                        ),
                    ],
                    [
                        Paragraph("本地识别能力异常", styles["card_body"]),
                        Paragraph(
                            "姓名等文字实体组件异常时任务会直接阻断；"
                            "图片 OCR、二维码等组件异常时，只能选择遮住整张图片或删除整张图片。",
                            styles["card_body"],
                        ),
                    ],
                    [
                        Paragraph("无法进入导出", styles["card_body"]),
                        Paragraph(
                            "检查文字、图片和隐藏对象是否全部作出决定；"
                            "图片有敏感候选时不要直接选择保留。",
                            styles["card_body"],
                        ),
                    ],
                    [
                        Paragraph("生成后显示技术检查失败", styles["card_body"]),
                        Paragraph(
                            "结果不会被标记为完成。返回复核、换一个空目录重试；"
                            "如持续失败，保留原文件并联系维护人员。",
                            styles["card_body"],
                        ),
                    ],
                ],
                colWidths=[45 * mm, 117 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ]
                ),
            ),
            Spacer(1, 7 * mm),
            card(
                "最后提醒",
                "分析副本适合阅读和 AI 分析，不应替代原文件继续盖章、正式排版、"
                "执行业务公式或归档。",
                styles,
                background=ORANGE_BG,
                accent=ORANGE,
            ),
        ]
    )
    document.build(story)
    return OUTPUT


if __name__ == "__main__":
    print(make_pdf())
