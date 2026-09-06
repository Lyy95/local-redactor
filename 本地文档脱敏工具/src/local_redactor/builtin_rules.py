from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BuiltinRuleInfo:
    name: str
    recognition: str
    treatment: str
    example: str
    review: str


BUILTIN_RULES: tuple[BuiltinRuleInfo, ...] = (
    BuiltinRuleInfo("中文姓名", "姓名字段或本地姓名实体；支持常见复姓", "保留姓氏，其余改为星号", "张三 → 张*；欧阳菲菲 → 欧阳**", "可批量采用"),
    BuiltinRuleInfo("手机号码", "中国大陆 11 位手机号及 +86 格式", "保留前三位和后四位", "13812345678 → 138****5678", "可批量采用"),
    BuiltinRuleInfo("身份证号", "18 位号码、出生日期及校验码联合校验", "保留前六位和后四位", "420101199003051234 → 420101********1234", "可批量采用"),
    BuiltinRuleInfo("银行卡号", "银行卡标签；无标签时校验 16–19 位和 Luhn", "保留前六位和后四位", "6222021234567890 → 622202******7890", "可批量采用"),
    BuiltinRuleInfo("电子邮箱", "邮箱用户名、@ 和域名结构校验", "用户名仅保留前两位", "abcde@163.com → ab***@163.com", "可批量采用"),
    BuiltinRuleInfo("固定电话", "区号加 7–8 位座机号码", "仅保留后四位", "010-88888888 → ****8888", "可批量采用"),
    BuiltinRuleInfo("详细地址", "地址标签、行政区划及道路门牌结构", "保留必要行政层级，隐藏门牌房间", "某市某区", "需要确认"),
    BuiltinRuleInfo("车牌号", "省份简称、号牌字母和 5–6 位号码", "改为一致车辆代号并保留车辆类型", "闽A12345 → 车辆甲（小型汽车）", "可批量采用"),
    BuiltinRuleInfo("密码与口令", "密码、口令、PIN 等明确字段标签", "直接删除，不写入映射表", "密码：Abc#1234 → 删除", "自动处理"),
    BuiltinRuleInfo("密钥与令牌", "Token、API Key、AccessKey、SecretKey 等标签", "直接删除，不写入映射表", "token: eyJ... → 删除", "自动处理"),
    BuiltinRuleInfo("用户名", "用户名、登录名、用户 ID 等字段标签", "使用一致用户代号", "zhangsan → user01", "可批量采用"),
    BuiltinRuleInfo("账号", "银行账号、平台账号、收款账号等字段标签", "银行卡用分段掩码，其余用一致代号", "账号甲", "可批量采用"),
    BuiltinRuleInfo("IPv4 / IPv6", "标准 IP 地址解析并区分内外网", "使用模拟地址并保留网络属性", "203.0.113.x", "可批量采用"),
    BuiltinRuleInfo("域名", "域名结构和后缀校验，排除文件扩展名", "使用一致的无效示例域名", "org01.example.invalid", "可批量采用"),
    BuiltinRuleInfo("案件编号", "案件编号、案件号、案号等标签", "使用一致案件代号", "CASE-2026-0001", "可批量采用"),
    BuiltinRuleInfo("设备编号", "设备编号、终端编号、序列号、SN 等标签", "使用一致设备代号", "DEVICE-0001", "可批量采用"),
    BuiltinRuleInfo("单位与机构", "机构后缀、本地实体模型和固定词规则", "保留机构类型，使用一致代号", "某中心甲", "需要确认"),
    BuiltinRuleInfo("部门", "部门标签、处室后缀和本地实体模型", "保留通用职能，使用一致代号", "业务部门甲", "需要确认"),
    BuiltinRuleInfo("项目", "项目、工程、专项等名称结构", "保留项目类型，使用一致代号", "建设项目甲", "需要确认"),
    BuiltinRuleInfo("系统名称", "系统、平台等名称结构", "保留系统用途，使用一致代号", "业务系统甲", "需要确认"),
    BuiltinRuleInfo("地点", "真实行政区划或本地地点实体；排除各地市等泛称", "保留必要区域层级或采用地名预置", "海南 → HN", "需要确认"),
    BuiltinRuleInfo("金额", "数值、币种和金额单位联合识别", "保留数量级，改为金额范围", "约 100万–150万元", "可批量采用"),
    BuiltinRuleInfo("时间", "当前版本不生成时间候选", "保持原文不变", "2026-08-07 → 原文不变", "无需确认"),
    BuiltinRuleInfo("文件属性", "作者、最后修改者及创建/修改时间", "自动清除，不进入待确认", "作者与历史属性 → 清除", "自动处理"),
    BuiltinRuleInfo("隐藏内容与对象", "批注、修订、隐藏文字、脚注尾注、附件、外链和嵌入对象", "自动移除；危险对象继续阻断", "脚注、尾注 → 自动移除", "自动处理"),
)


__all__ = ["BUILTIN_RULES", "BuiltinRuleInfo"]
