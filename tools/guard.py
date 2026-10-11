#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guard.py — 每轮强制守卫（危机扫描 + 写前凭据拦截）

用法：
  python tools/guard.py input  "<当轮文本>"      # 或 --file <path> 或 - 从 stdin
  python tools/guard.py write  "<待写入内容>"    # 落盘前必须过一遍

退出码：
  0 = 通过
  1 = CRISIS      命中危机信号 → 必须加载 knowledge/protocols/crisis.md，风格规则让位
  2 = CREDENTIAL  命中凭据/PII 形态 → 禁止写入任何 memory 文件
  3 = USAGE       参数错误

输出为 UTF-8 字节（避开 Windows 控制台编码问题），只打印类别与字段名，不回显命中原文，
避免守卫器本身成为二次泄露通道。
"""
import sys, os, re, json, io

# ---------------- 危机词表 ----------------
CRISIS_DIRECT = [
    "不想活", "活不下去", "活不了", "去死", "自杀", "寻死", "一了百了",
    "结束自己", "不想撑", "撑不下去", "消失就好了", "不在了就好了",
    "自残", "割腕", "吞药", "跳下去", "伤害自己",
]
CRISIS_OTHER = [
    "杀了他", "杀了那", "弄死", "弄死他", "同归于尽", "让他付出代价", "报复社会",
]
# 间接：需要先确认当下安全（protocols/crisis.md §1）
CRISIS_SOFT = [
    "解脱", "没意思透了", "彻底没希望", "什么都没有了", "不如消失", "撑不住了",
    "再也不", "算了不活了", "如果我不在",
]
# 明确排除：这些是日常口语，单独出现不构成信号
CRISIS_NEG = [
    "笑死", "累死", "忙死", "烦死", "气死", "困死", "卷死", "亏死", "打死我也不会",
]

# ---------------- 凭据 / PII 形态 ----------------
# 硬拦截：命中即禁止落盘（值形态本身就像秘密）
CRED_PATTERNS = {
    "ipv4":               re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "long_digits":        re.compile(r"\b\d{8,20}\b"),
    "id_card":            re.compile(r"\b\d{17}[\dXx]\b"),
    "bank_like":          re.compile(r"\b\d{16,19}\b"),
    "opaque_id":          re.compile(r"\b(?:ou_|on_|cli_|lq_)[0-9a-zA-Z]{8,}\b"),
    # 形如「密码是 abcd1234」「token: xyz789」——值必须是 ASCII 形态，否则中文普通叙述会误报
    "secret_assignment":  re.compile(
        r"(密码|口令|密钥|账号|帐号|配对码|验证码|token|secret|api[-_]?key|pwd|password)"
        r"\s*(?:是|为|[:：=])?\s*[A-Za-z0-9_\-\.@#]{4,}", re.I),
}
# 软提示：只提到"密码/账号"这类词但没出现值形态 → 不拦，但提醒人工看一眼
KEYWORD_ONLY = re.compile(r"(密码|口令|密钥|账号|帐号|配对码|验证码|token|secret|api\s?-?\s?key|password|passwd)", re.I)
# 长数字白名单：ISO 日期 / 时间 / 年月，避免把 20261011 之类当账号
DATE_LIKE = re.compile(r"\b(?:19|20)\d{2}(?:-?\d{2}){0,2}\b|\b\d{1,2}:\d{2}(?::\d{2})?\b")


def _strip_dates(text):
    return DATE_LIKE.sub(" ", text)


def scan_crisis(text):
    hits = []
    probe = text
    for n in CRISIS_NEG:                 # 先剔除口语误报
        probe = probe.replace(n, "")
    for w in CRISIS_DIRECT:
        if w in probe:
            hits.append(("direct", w))
    for w in CRISIS_OTHER:
        if w in probe:
            hits.append(("harm_others", w))
    for w in CRISIS_SOFT:
        if w in probe:
            hits.append(("soft", w))
    return hits


def scan_credentials(text):
    probe = _strip_dates(text)
    found = {}
    for name, pat in CRED_PATTERNS.items():
        m = pat.findall(probe)
        if m:
            found[name] = len(m)
    return found


def scan_credential_words(text):
    """软提示：出现了"密码/账号"这类词但没有值形态。不拦，只提醒看一眼。"""
    return len(KEYWORD_ONLY.findall(text))


def _read(args):
    """支持三种输入：直接文本 / --file / - (stdin)"""
    if not args:
        return io.open(0, "r", encoding="utf-8", errors="replace").read()
    if args[0] == "-":
        return sys.stdin.read()
    if args[0] == "--file":
        return io.open(args[1], encoding="utf-8", errors="replace").read()
    return " ".join(args)


def emit(payload, code):
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    sys.exit(code)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("input", "write"):
        emit({"verdict": "USAGE", "help": "guard.py input|write [--file path] | - "}, 3)
    mode = sys.argv[1]
    text = _read(sys.argv[2:])
    if not text.strip():
        emit({"verdict": "EMPTY_INPUT"}, 3)

    crisis = scan_crisis(text)
    cred = scan_credentials(text)

    if mode == "input":
        # 输入守卫只看危机；凭据不参与（他有权对你说出一个密码，但不能被存下来）
        if crisis:
            kinds = sorted({k for k, _ in crisis})
            emit({"verdict": "CRISIS", "kinds": kinds,
                  "matched_count": len(crisis),
                  "action": "STOP. 完整加载 knowledge/protocols/crisis.md，按 §2 顺序执行；AGENT.md §3 风格约束让位；本轮结束必须写 signals.md（状态 unresolved，verbatim 必填）"}, 1)
        emit({"verdict": "CLEAR", "credential_shapes_in_input": sorted(cred) if cred else [],
              "note": "本轮不含危机信号，按 AGENT.md §6 判定状态后正常回应"
                      + ("；输入里出现凭据形态内容 → 可回应但绝不写入记忆（guard.py write 会拦）" if cred else "")}, 0)

    # write 模式：落盘前拦凭据
    if cred:
        emit({"verdict": "CREDENTIAL_BLOCK", "matched": cred,
              "action": "禁止写入。按 MEMORY_POLICY §6：在 session 里只写『已剔除凭据类信息』这类元描述，不复述内容本身。剔除后重跑本命令。"}, 2)
    words = scan_credential_words(text)
    emit({"verdict": "WRITE_OK", "crisis_terms_present": sorted({k for k, _ in crisis}) or [],
          "credential_words_without_value": words,
          "hint": ("正文提到密码/账号类词但没有值形态，未拦截；确认没有把具体值写进去即可" if words else "")}, 0)


if __name__ == "__main__":
    main()
