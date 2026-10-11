#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retrieve.py — 记忆检索（纯标准库 BM25 + frontmatter 过滤，不上云、不用向量库）

用法：
  python tools/retrieve.py q "<用来访者自己的词>"            # 关键词检索，默认 top 2
  python tools/retrieve.py q "..." -k 4 --full               # 带正文节选
  python tools/retrieve.py thread T-001                      # 队列反查：这个话题牵扯过哪几次会谈
  python tools/retrieve.py signal SIG-001
  python tools/retrieve.py card C13                          # 某张技术卡哪些次用过（验有效性）
  python tools/retrieve.py recent 5
  python tools/retrieve.py stats                             # 会谈总数 / 时间跨度 / mood 分布 / 卡片使用频次

默认排除 fidelity 为「链路测试 / 系统验证」的合成记录（否则会有一条假数据排在真实会谈前面）。
加 --include-test 才把它们算进来。

输出 UTF-8 JSON。
"""
import os, re, io, sys, json, math, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESS = os.path.join(ROOT, "memory", "sessions")


def files():
    out = []
    for d, _, fs in os.walk(SESS):
        for x in sorted(fs):
            if x.endswith(".md"):
                out.append(os.path.join(d, x))
    return out


def parse(path):
    txt = io.open(path, encoding="utf-8").read()
    fm = {}
    body = txt
    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
    if m:
        body = txt[m.end():]
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
    secs = {}
    cur = None
    for line in body.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            secs[cur] = []
        elif cur:
            secs[cur].append(line)
    for k in secs:
        secs[k] = "\n".join(secs[k]).strip()
    return fm, secs, body


def toks(s):
    """ASCII 词 + 中文单字 + 中文二元组（够用的中文分词替代）"""
    s = s.lower()
    ascii_words = re.findall(r"[a-z0-9_\-]{2,}", s)
    cjk = re.findall(r"[\u4e00-\u9fff]", s)
    big = ["".join(p) for p in zip(cjk, cjk[1:])]
    return ascii_words + cjk + big


def load_index(include_test=False):
    docs = []
    for p in files():
        fm, secs, body = parse(p)
        # fidelity: 链路测试 / 系统验证 的记录默认排除——否则一条合成数据会排在真实会谈前面
        fid = fm.get("fidelity", "")
        if not include_test and ("链路测试" in fid or "系统验证" in fid):
            continue
        text = " ".join([
            " ".join(re.findall(r'"([^"]+)"', fm.get("tags", ""))),
            secs.get("他的原话", ""), secs.get("他当下真正在意的", ""),
            secs.get("发生了什么", ""), secs.get("留了什么", ""), body,
        ])
        docs.append({"path": p, "fm": fm, "secs": secs, "tf": collections.Counter(toks(text))})
    return docs


def bm25(docs, query, k=2, k1=1.5, b=0.75):
    N = len(docs) or 1
    avg = sum(sum(d["tf"].values()) for d in docs) / N or 1
    q = set(toks(query))
    df = collections.Counter()
    for d in docs:
        for t in q:
            if t in d["tf"]:
                df[t] += 1
    scored = []
    for d in docs:
        s = 0.0
        dl = sum(d["tf"].values()) or 1
        for t in q:
            f = d["tf"].get(t, 0)
            if not f:
                continue
            idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / avg))
        if s > 0:
            scored.append((s, d))
    scored.sort(key=lambda x: -x[0])
    return scored[:k]


def brief(d, full=False):
    fm, secs = d["fm"], d["secs"]
    o = {
        "id": fm.get("id"), "date": fm.get("date"),
        "tags": re.findall(r'"([^"]+)"', fm.get("tags", "")),
        "mood_before": fm.get("mood_before"), "mood_after": fm.get("mood_after"),
        "signals": re.findall(r'SIG-\d{3}', fm.get("signals", "")),
        "cards": re.findall(r'"([A-K]\d{1,2})"', fm.get("techniques_used", "")),
        "threads": sorted(set(re.findall(r'T-\d{3}', open(d["path"], encoding="utf-8").read()))),
        "file": os.path.relpath(d["path"], ROOT).replace("\\", "/"),
    }
    if full:
        o["verbatim"] = secs.get("他的原话", "")[:600]
        o["cares"] = secs.get("他当下真正在意的", "")[:200]
        o["left"] = secs.get("留了什么", "")[:300]
    return o


def by_field(docs, key, val):
    pat = re.compile(re.escape(val), re.I)
    return [d for d in docs if pat.search(d["fm"].get(key, ""))]


def emit(obj, code=0):
    sys.stdout.buffer.write((json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    sys.exit(code)


def main():
    a = sys.argv[1:]
    if not a:
        emit({"error": "用法见文件头"}, 3)
    docs = load_index(include_test=("--include-test" in a))
    cmd = a[0]

    if cmd == "q" and len(a) > 1:
        k, parts, full = 2, [], ("--full" in a)
        i = 1
        while i < len(a):
            if a[i] == "-k":
                k = int(a[i + 1]); i += 2; continue
            if a[i] == "--full":
                i += 1; continue
            parts.append(a[i]); i += 1
        query = " ".join(parts)
        if not query:
            emit({"error": "空查询"}, 3)
        hits = bm25(docs, query, k=k)
        emit({"query": query, "top": k,
              "results": [dict(brief(d, full), score=round(s, 2)) for s, d in hits]})

    if cmd in ("thread", "signal", "card"):
        key = {"thread": "threads_touched", "signal": "signals", "card": "techniques_used"}[cmd]
        val = a[1]
        # threads_touched 只在 frontmatter 里存 touched，opened 也要算
        hits = [d for d in docs if re.search(re.escape(val), io.open(d["path"], encoding="utf-8").read())]
        hits.sort(key=lambda d: d["fm"].get("date", ""))
        emit({"filter": key, "value": val, "matched": len(hits), "results": [brief(d) for d in hits]})

    if cmd == "recent":
        n = int(a[1]) if len(a) > 1 else 5
        hs = sorted(docs, key=lambda d: d["fm"].get("date", ""))[-n:]
        hs.reverse()
        emit({"recent": n, "results": [brief(d, "--full" in a) for d in hs]})

    if cmd == "stats":
        dates = sorted(d["fm"].get("date", "") for d in docs if d["fm"].get("date"))
        cards = collections.Counter()
        for d in docs:
            cards.update(re.findall(r'"([A-K]\d{1,2})"', d["fm"].get("techniques_used", "")))
        eras = collections.Counter(d["fm"].get("style_era", "")[:1] or "?" for d in docs)
        emit({
            "sessions": len(docs), "span": [dates[0], dates[-1]] if dates else None,
            "style_era": dict(eras),
            "post_style_sessions": sum(1 for d in docs if "新" in d["fm"].get("style_era", "")),
            "card_usage": dict(sorted(cards.items(), key=lambda x: -x[1])),
            "note": "card_usage 只统计**使用次数**，不代表有效。有效性要看 threads 是否闭环、"
                    "以及后续 session 是否引用了同一次的动作（脚本判断不了，去看 insights.md I-003）",
        })
    emit({"error": "未知命令"}, 3)


if __name__ == "__main__":
    main()
