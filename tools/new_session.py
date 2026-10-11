#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_session.py — 会谈记忆落盘（写前强制过 guard；同日多轮默认合并，不碎裂）

用法：
  python tools/new_session.py --json '{"date":"<YYYY-MM-DD>", ... }'   # 当天第一次 → 新建
  python tools/new_session.py --json '{...}'                            # 当天已有文件 → 自动合并进那次会谈
  python tools/new_session.py --json '{...}' --merge S<YYYY-MM-DD>-01   # 指定合并到哪个文件
  python tools/new_session.py --json '{...}' --new                      # 确实是同一天第二次独立会谈
  python tools/new_session.py --check memory/sessions/<year>/<file>.md  # 写后抽检

payload 字段：
  date(必填) turns tags[] mood_before mood_after signals[] cards[]
  threads_touched[] threads_opened[] verbatim(必填) narr(必填) cares left miss
  fidelity style_era channel

退出码：0 已写入/已合并 / 2 CREDENTIAL_BLOCK 未写入 / 3 用法或字段错误
"""
import os, re, io, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import guard  # noqa: E402

ROOT = os.path.dirname(HERE)

TPL = """---
id: {sid}
date: {date}
channel: {channel}
turns: {turns}
fidelity: {fidelity}
style_era: {era}
tags: [{tags}]
mood_before: {mood_before}
mood_after: {mood_after}
signals: [{signals}]
techniques_used: [{cards}]
threads_touched: [{touched}]
threads_opened: [{opened}]
---

## 他的原话
{verbatim}

## 发生了什么
{narr}

## 他当下真正在意的
{cares}

## 留了什么
{left}

## 你自己没做好的
{miss}
"""

SEG = """
## 后续轮次 · 第 {turns} 段（{time}）

### 他的原话
{verbatim}

### 发生了什么
{narr}

### 他当下真正在意的
{cares}

### 留了什么
{left}

### 你自己没做好的
{miss}
"""


def q(lst):
    return ", ".join('"%s"' % str(x) for x in (lst or []) if str(x).strip())


def unquote(s):
    return re.findall(r'"([^"]*)"', s or "")


def ul(*lists):
    """列表并集：保序去重"""
    out = []
    for l in lists:
        for x in (l or []):
            x = str(x).strip()
            if x and x not in out:
                out.append(x)
    return out


def parse(txt):
    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
    if not m:
        return {}, txt
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, txt[m.end():]


def year_dir(date):
    return os.path.join(ROOT, "memory", "sessions", date[:4])


def files_for_day(date):
    """文件名形如 S<YYYY-MM-DD>-<NN>.md（带连字符），同时兼容紧凑写法。"""
    d = year_dir(date)
    if not os.path.isdir(d):
        return []
    compact = "S" + date.replace("-", "")
    return sorted(x for x in os.listdir(d)
                  if x.endswith(".md") and (x.startswith("S" + date) or x.startswith(compact)))


def next_sid(day):
    n = 1
    for x in files_for_day(day):
        m = re.search(r"(\d{2})\.md$", x)
        if m:
            n = max(n, int(m.group(1)) + 1)
    return "S%s-%02d" % (day, n)


def find_target(date, sid=None):
    fs = files_for_day(date)
    if not fs:
        return None
    if sid:
        want = sid if sid.endswith(".md") else sid + ".md"
        return want if want in fs else None
    return fs[-1]


def merge(old_txt, d, fname):
    fm, old_body = parse(old_txt)
    try:
        turns = int(fm.get("turns", "1")) + 1
    except ValueError:
        turns = 2
    fields = [
        ("id", fm.get("id", fname[:-3])),
        ("date", fm.get("date", d["date"])),
        ("channel", fm.get("channel", "本地")),
        ("turns", turns),
        ("fidelity", fm.get("fidelity", "含原话")),
        ("style_era", fm.get("style_era", "新")),
        ("tags", "[%s]" % q(ul(unquote(fm.get("tags")), d.get("tags")))),
        ("mood_before", fm.get("mood_before", "")),
        ("mood_after", d.get("mood_after") or fm.get("mood_after", "")),
        ("signals", "[%s]" % q(ul(unquote(fm.get("signals")), d.get("signals")))),
        ("techniques_used", "[%s]" % q(ul(unquote(fm.get("techniques_used")), d.get("cards")))),
        ("threads_touched", "[%s]" % q(ul(unquote(fm.get("threads_touched")),
                                          d.get("threads_touched") or d.get("touched")))),
        ("threads_opened", "[%s]" % q(ul(unquote(fm.get("threads_opened")),
                                         d.get("threads_opened") or d.get("opened")))),
    ]
    fm_text = "---\n" + "\n".join("%s: %s" % (k, v) for k, v in fields) + "\n---\n"
    seg = SEG.format(turns=turns, time=datetime.datetime.now().strftime("%H:%M"),
                     verbatim=d["verbatim"], narr=d["narr"], cares=d.get("cares", ""),
                     left=d.get("left", "无。"), miss=d.get("miss", "无。"))
    return fm_text + old_body.rstrip() + "\n" + seg, dict(fields)["id"], turns


def emit(o, code=0):
    sys.stdout.buffer.write((json.dumps(o, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    sys.exit(code)


def main():
    a = sys.argv[1:]
    if not a:
        emit({"error": "用法见文件头"}, 3)

    # —— 写后抽检 ——
    if a[0] == "--check":
        if len(a) < 2:
            emit({"error": "--check 需要一个文件路径"}, 3)
        p = a[1] if os.path.isabs(a[1]) else os.path.join(ROOT, a[1])
        if not os.path.exists(p):
            emit({"error": "文件不存在", "tried": os.path.relpath(p, ROOT).replace("\\", "/"),
                  "note": "若上一轮被 CREDENTIAL_BLOCK 拦下，本来就不该有这个文件——这是正确状态"}, 3)
        txt = io.open(p, encoding="utf-8").read()
        cred = guard.scan_credentials(txt)
        if cred:
            emit({"file": os.path.relpath(p, ROOT), "verdict": "CREDENTIAL_PRESENT", "matched": cred,
                  "action": "MEMORY_POLICY §6：手工把凭据替换为元描述（『已剔除凭据类信息』），不保留原文"}, 2)
        emit({"file": os.path.relpath(p, ROOT).replace("\\", "/"), "verdict": "CLEAN"}, 0)

    raw = (sys.stdin.read() if a[0] == "-" else
           io.open(a[a.index("--file") + 1], encoding="utf-8").read() if "--file" in a else
           a[a.index("--json") + 1] if "--json" in a else None)
    if raw is None:
        emit({"error": "需要 --json / --file / - 三者之一"}, 3)
    try:
        d = json.loads(raw)
    except Exception as e:
        emit({"error": "payload 不是合法 JSON: %s" % e}, 3)

    for req in ("date", "narr"):
        if not str(d.get(req, "")).strip():
            emit({"error": "缺必填字段 %s" % req}, 3)
    if not str(d.get("verbatim", "")).strip():
        emit({"error": "缺 verbatim。每次会谈至少保留 1 条原话；确实没有就写「（本轮未留存原话）」，不得留空"}, 3)

    force_new = "--new" in a
    merge_to = a[a.index("--merge") + 1] if "--merge" in a else None

    # —— 默认合并：一次会谈一个文件。原库 10-06 一天挂 10 条 session 就是这个病 ——
    if not force_new:
        target = find_target(d["date"], merge_to)
        if target:
            path = os.path.join(year_dir(d["date"]), target)
            txt, sid, turns = merge(io.open(path, encoding="utf-8").read(), d, target)
            cred = guard.scan_credentials(txt)
            if cred:
                emit({"verdict": "CREDENTIAL_BLOCK", "would_be": sid, "matched": cred, "written": False,
                      "action": "不落盘，原文件也未被改动。按 MEMORY_POLICY §6 改成元描述后重跑"}, 2)
            io.open(path, "w", encoding="utf-8").write(txt)
            emit({"verdict": "MERGED", "id": sid, "turns": turns,
                  "file": os.path.relpath(path, ROOT).replace("\\", "/"), "guard": "WRITE_OK",
                  "next": ["frontmatter 的 tags/signals/cards/threads 已自动取并集",
                            "如有新风险条目则追加 signals.md",
                            "本轮若出现过危机信号：signals.md 必须写 unresolved + verbatim"]}, 0)
        if merge_to:
            emit({"error": "--merge 指定的文件不存在", "tried": merge_to, "date": d["date"]}, 3)

    # —— 新建 ——
    sid = d.get("id") or next_sid(d["date"])
    content = TPL.format(
        sid=sid, date=d["date"], channel=d.get("channel", "本地"),
        turns=d.get("turns", 1), fidelity=d.get("fidelity", "含原话"),
        era=d.get("style_era", "新"), tags=q(d.get("tags")),
        mood_before=d.get("mood_before", ""), mood_after=d.get("mood_after", ""),
        signals=q(d.get("signals")), cards=q(d.get("cards")),
        touched=q(d.get("threads_touched") or d.get("touched")),
        opened=q(d.get("threads_opened") or d.get("opened")),
        verbatim=d["verbatim"], narr=d["narr"],
        cares=d.get("cares", ""), left=d.get("left", "无。"), miss=d.get("miss", "无。"),
    )
    cred = guard.scan_credentials(content)
    if cred:
        emit({"verdict": "CREDENTIAL_BLOCK", "would_be": sid, "matched": cred, "written": False,
              "action": "不落盘。按 MEMORY_POLICY §6 把具体值改成元描述后重跑。这是硬拦截，不能用参数绕过"}, 2)

    outdir = year_dir(d["date"])
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, sid + ".md")
    if os.path.exists(path):
        emit({"verdict": "EXISTS", "file": os.path.relpath(path, ROOT),
              "action": "该 id 已存在。同一轮会谈请用 --merge（也是默认行为），确实要新开会谈用 --new"}, 3)
    io.open(path, "w", encoding="utf-8").write(content)
    emit({"verdict": "WRITTEN", "id": sid, "file": os.path.relpath(path, ROOT).replace("\\", "/"),
          "guard": "WRITE_OK",
          "next": ["同步 threads.md（touched/opened 的状态与 last_touch）",
                    "如有新风险条目则追加 signals.md",
                    "本轮若出现过危机信号：signals.md 必须写 unresolved + verbatim"]}, 0)


if __name__ == "__main__":
    main()
