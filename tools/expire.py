#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""expire.py — 记忆腐烂控制（MEMORY_POLICY §5）

默认 **只提议不改动**；加 --apply 才写文件。

用法：
  python tools/expire.py                     # 打印将要发生的状态迁移（dry-run）
  python tools/expire.py --apply             # 真的改写 threads.md 状态列 + 追加维护日志
  python tools/expire.py --today <YYYY-MM-DD>  # 指定"今天"，用于推演或补跑
  python tools/expire.py --stale-days 120

退出码：0 无需迁移 / 10 有迁移（dry-run 下表示"需要处理"）/ 0 且已写入（--apply）/ 3 解析失败
"""
import os, re, io, sys, json, datetime, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THREADS = os.path.join(ROOT, "memory", "threads.md")
SESSIONS = os.path.join(ROOT, "memory", "sessions")

ACTIVE = ("open", "waiting-him", "waiting-others")
DAYS_ACTIVE_TO_STALLED = 90
DAYS_STALLED_TO_ARCHIVED = 90
REVIEW_EVERY_SESSIONS = 20
BASELINE_SESSIONS = None   # 建库时的会谈数；留空则按总数取模
PROFILE_CHECK_EVERY = 15
MIGRATION_ASSERT_DAYS = 90   # signals.md 里"迁移检查声明"的有效期


def d(s):
    try:
        return datetime.date.fromisoformat(s.strip()[:10])
    except Exception:
        return None


def count_sessions():
    return sum(1 for _, _, fs in os.walk(SESSIONS) for x in fs if x.endswith(".md"))


def split_status(cell):
    """状态列可能写着 'stalled → 到期归档' 或 'done（部分）'，取出主状态"""
    for s in ("open", "waiting-him", "waiting-others", "stalled", "archived", "done"):
        if cell.strip().startswith(s) or ("`%s`" % s) in cell or re.match(r"^\*\*%s" % s, cell.strip()):
            return s
    m = re.search(r"\b(open|waiting-him|waiting-others|stalled|archived|done)\b", cell)
    return m.group(1) if m else None


def main():
    args = sys.argv[1:]
    apply_ = "--apply" in args
    today = d(args[args.index("--today") + 1]) if "--today" in args else datetime.date.today()
    n_act = int(args[args.index("--stale-days") + 1]) if "--stale-days" in args else DAYS_ACTIVE_TO_STALLED

    if not os.path.exists(THREADS):
        sys.stdout.buffer.write(json.dumps({"error": "找不到 memory/threads.md",
                                            "fix": "先复制空骨架：cp -r templates/memory-empty/. memory/"
                                                   "（Windows: xcopy /E /I templates\\memory-empty memory）"},
                                           ensure_ascii=False).encode("utf-8"))
        sys.exit(3)

    txt = io.open(THREADS, encoding="utf-8").read()
    lines = txt.splitlines()
    proposals, rowmap = [], {}

    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7 or cells[0] in ("id", "---") or set(cells[0]) <= set("-: "):
            continue
        tid, topic, status_cell, prio, created, last_touch, expiry = cells[:7]
        st = split_status(status_cell)
        if not st:
            continue
        lt = d(last_touch) or d(created)
        age = (today - lt).days if lt else None
        new = None
        if st in ACTIVE and age is not None and age > n_act:
            new = "stalled"
        elif st == "stalled" and age is not None and age > DAYS_STALLED_TO_ARCHIVED:
            new = "archived"
        if new:
            proposals.append({"id": tid, "topic": topic[:40], "from": st, "to": new,
                              "days_since_touch": age, "priority": prio})
            rowmap[i] = (tid, st, new)

    # 迁移断言有效期检查
    checks = []
    m = re.search(r"检查日期[：:]\s*(\d{4}-\d{2}-\d{2})", txt)
    sig_txt = ""
    sp = os.path.join(ROOT, "memory", "signals.md")
    if os.path.exists(sp):
        sig_txt = io.open(sp, encoding="utf-8").read()
    mm = re.search(r"检查日期[：:]\s*(\d{4}-\d{2}-\d{2})", sig_txt)
    if mm:
        age = (today - d(mm.group(1))).days
        checks.append({"item": "signals.md 迁移检查声明（无自伤表述）", "checked": mm.group(1),
                       "age_days": age,
                       "action": "已过期，重新全库检查并更新日期" if age > MIGRATION_ASSERT_DAYS else "在有效期内"})

    nsess = count_sessions()
    base = 0
    inst = os.path.join(ROOT, "instance.md")
    if os.path.exists(inst):
        mb = re.search(r"BASELINE_SESSIONS[^0-9]*(\d+)", io.open(inst, encoding="utf-8").read())
        if mb:
            base = int(mb.group(1))
    if (nsess - base) and (nsess - base) % REVIEW_EVERY_SESSIONS == 0:
        checks.append({"item": "队列与现实一致性复核", "action": "本轮跑 templates/review.md 清单（每 %d 次会谈一次）" % REVIEW_EVERY_SESSIONS})
    if base and nsess > base and (nsess - base) % PROFILE_CHECK_EVERY == 0:
        checks.append({"item": "profile.md 慢变区复核", "action": "核对工作/节奏/目标/薪资口径（每 %d 次会谈一次）" % PROFILE_CHECK_EVERY})

    # 按条目切块再判断状态，避免懒匹配跨条目串味（旧写法会把 resolved 条目误报成 unresolved）
    unresolved = []
    for b in re.split(r"(?=\[SIG-\d{3}\])", sig_txt):
        head = re.match(r"\[(SIG-\d{3})\]", b)
        if head and re.search(r"状态:\s*\**\s*unresolved", b):
            unresolved.append(head.group(1))
    if unresolved:
        checks.append({"item": "unresolved 风险条目", "ids": unresolved,
                       "action": "每轮必读（MEMORY_POLICY §3 优先级第 1 位）"})

    written = False
    if apply_ and rowmap:
        for i, (tid, old, new) in rowmap.items():
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            cells[2] = "%s（%s 自动迁移，原 %s）" % (new, today.isoformat(), old)
            lines[i] = "| " + " | ".join(cells) + " |"
        block = "\n\n## 自动维护日志\n- %s：迁移 %d 条 → %s\n" % (
            today.isoformat(), len(rowmap),
            "、".join("%s %s→%s" % (t[0], t[1], t[2]) for t in rowmap.values()))
        txt2 = "\n".join(lines)
        if "## 自动维护日志" not in txt2:
            txt2 += block
        io.open(THREADS, "w", encoding="utf-8").write(txt2)
        written = True

    out = {"today": today.isoformat(), "sessions_total": nsess,
           "thread_transitions": proposals,
           "applied": written,
           "housekeeping": checks,
           "note": "dry-run：未改动任何文件。确认后加 --apply" if proposals and not written else ""}
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    sys.exit(10 if proposals and not written else 0)


if __name__ == "__main__":
    main()
