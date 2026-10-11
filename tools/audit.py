#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit.py — 「到底有没有在存」自查（A 形态下唯一能自己验落盘的办法）

用法：
  python tools/audit.py                 # 今天落盘了没有 + 记忆层最后修改时间
  python tools/audit.py --date <YYYY-MM-DD>
  python tools/audit.py --deep          # 全库凭据/PII 扫描（MEMORY_POLICY §6）
  python tools/audit.py --orphans       # session 引用的 T-/SIG- id 是否真的存在
  python tools/audit.py --gaps 14       # 超过 N 天没有会谈的空档（陪伴节奏，不是评判）

退出码：
  0  正常
  2  发现凭据形态内容（--deep）
  11 今天有队列改动但没有会谈文件（很可能漏写会谈）
  12 存在引用孤儿（--orphans）
"""
import os, re, io, sys, json, datetime, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEM = os.path.join(ROOT, "memory")
SESS = os.path.join(MEM, "sessions")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import guard  # noqa: E402


def mtime(p):
    return datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M") if os.path.exists(p) else None


def all_sessions():
    out = []
    for d, _, fs in os.walk(SESS):
        for x in fs:
            if x.endswith(".md"):
                out.append(os.path.join(d, x))
    return sorted(out, key=lambda p: os.path.basename(p))


def day_files(date):
    """文件名形如 S<YYYY-MM-DD>-<NN>.md（带连字符），同时兼容紧凑写法。"""
    d = os.path.join(SESS, date[:4])
    if not os.path.isdir(d):
        return []
    compact = "S" + date.replace("-", "")
    return sorted(os.path.join(d, x) for x in os.listdir(d)
                  if x.endswith(".md") and (x.startswith("S" + date) or x.startswith(compact)))


def emit(o, code):
    sys.stdout.buffer.write((json.dumps(o, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    sys.exit(code)


def main():
    a = sys.argv[1:]
    today = a[a.index("--date") + 1] if "--date" in a else datetime.date.today().isoformat()

    # ---- 深扫凭据 ----
    if "--deep" in a:
        bad = {}
        for p in [os.path.join(MEM, x) for x in ("profile.md", "threads.md", "signals.md", "no_repeat.md", "insights.md")] + all_sessions():
            cred = guard.scan_credentials(io.open(p, encoding="utf-8").read())
            if cred:
                bad[os.path.relpath(p, ROOT).replace("\\", "/")] = cred
        emit({"scan": "credential_deep", "files_checked": len(all_sessions()) + 5,
              "hits": bad,
              "verdict": "CLEAN" if not bad else "CREDENTIAL_PRESENT",
              "action": "" if not bad else "按 MEMORY_POLICY §6 手工改成元描述。注意：若正文确实在讨论“密码”这个词而非具体值，可忽略"},
             0 if not bad else 2)

    # ---- 引用完整性 ----
    if "--orphans" in a:
        th = io.open(os.path.join(MEM, "threads.md"), encoding="utf-8").read() if os.path.exists(os.path.join(MEM, "threads.md")) else ""
        sg = io.open(os.path.join(MEM, "signals.md"), encoding="utf-8").read() if os.path.exists(os.path.join(MEM, "signals.md")) else ""
        known_t, known_s = set(re.findall(r"T-\d{3}", th)), set(re.findall(r"SIG-\d{3}", sg))
        orphans = {}
        for p in all_sessions():
            txt = io.open(p, encoding="utf-8").read()
            mt = [t for t in set(re.findall(r"T-\d{3}", txt)) if t not in known_t]
            ms = [s for s in set(re.findall(r"SIG-\d{3}", txt)) if s not in known_s]
            if mt or ms:
                orphans[os.path.basename(p)] = {"unknown_threads": mt, "unknown_signals": ms}
        # 反向：队列里挂着但没有任何 session 引用的，说明 id 是凭空造的
        used_t = set()
        for p in all_sessions():
            used_t.update(re.findall(r"T-\d{3}", io.open(p, encoding="utf-8").read()))
        emit({"scan": "orphans", "sessions": len(all_sessions()),
              "threads_defined": len(known_t), "signals_defined": len(known_s),
              "sessions_reference_unknown_id": orphans,
              "threads_never_referenced_by_session": sorted(known_t - used_t),
              "verdict": "CONSISTENT" if not orphans else "DANGLING_REFERENCE"},
             0 if not orphans else 12)

    # ---- 空档 ----
    if "--gaps" in a:
        n = int(a[a.index("--gaps") + 1]) if a.index("--gaps") + 1 < len(a) else 14
        ds = []
        for p in all_sessions():
            b = os.path.basename(p)
            m = re.search(r"S(\d{4})-?(\d{2})-?(\d{2})", b)
            if m:
                try:
                    ds.append(datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
                except ValueError:
                    pass
        if not ds:
            # 一个日期都没解析出来 = 文件名格式或解析逻辑坏了。宁可报错，也不能静默返回空列表
            emit({"scan": "gaps", "verdict": "PARSE_FAILURE",
                  "sessions_on_disk": len(all_sessions()),
                  "action": "文件名里的日期没被解析出来。检查 sessions/ 命名是否为 S<YYYY-MM-DD>-<序号>.md"}, 3)
        ds.sort()
        gaps = [{"from": x.isoformat(), "to": y.isoformat(), "days": (y - x).days}
                for x, y in zip(ds, ds[1:]) if (y - x).days > n]
        emit({"scan": "gaps", "sessions": len(ds), "first": ds[0].isoformat(), "last": ds[-1].isoformat(),
              "threshold_days": n, "gaps": gaps, "verdict": "OK",
              "note": "空档本身不说明状态好坏，只用于判断要不要温和回访"}, 0)

    # ---- 默认：今天落盘了没有 ----
    fs = day_files(today)
    tmod = mtime(os.path.join(MEM, "threads.md"))
    smod = mtime(os.path.join(MEM, "signals.md"))
    newest = all_sessions()[-1] if all_sessions() else None
    queue_touched_today = (tmod or "").startswith(today) or (smod or "").startswith(today)

    verdict, code = "OK", 0
    if fs:
        verdict = "WRITTEN_TODAY"
    elif queue_touched_today:
        verdict, code = "QUEUE_TOUCHED_WITHOUT_SESSION", 11
    else:
        verdict = "NO_SESSION_TODAY"

    emit({"today": today,
          "sessions_today": [os.path.basename(x)[:-3] for x in fs],
          "latest_session": os.path.basename(newest)[:-3] if newest else None,
          "latest_session_mtime": mtime(newest) if newest else None,
          "last_modified": {"threads.md": tmod, "signals.md": smod,
                            "profile.md": mtime(os.path.join(MEM, "profile.md")),
                            "no_repeat.md": mtime(os.path.join(MEM, "no_repeat.md"))},
          "total_sessions": len(all_sessions()),
          "verdict": verdict,
          "meaning": {
              "WRITTEN_TODAY": "今天已经落盘，记忆在存",
              "QUEUE_TOUCHED_WITHOUT_SESSION": "队列今天动过，但今天没有会谈文件。**今天聊过 = 漏写，立刻补**；今天没聊（只是在改库/建库）= 正常",
              "NO_SESSION_TODAY": "今天没有会谈文件，队列也没动过 → 今天没聊，正常",
          }.get(verdict, "")}, code)


if __name__ == "__main__":
    main()
