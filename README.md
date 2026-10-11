# psych-support-agent

一个**可套用的心理支持 Agent 模板包**：人格、方法、记忆三层物理分离，记忆存本地 Markdown 文件，运行时用几个 Python 脚本强制执行危机守卫与隐私拦截。

> ⚠️ **这不是医疗设备，也不是心理治疗。** 它做情绪承接、心理教育、现实问题拆解和陪伴记录；**不诊断、不开药、不替代医生或咨询师**。出现自伤/自杀/伤人信号时，它的设计目标是把你转向真人和专业资源（见 `knowledge/protocols/crisis.md`）。

---

## 一、它解决的是三个很具体的痛

| 常见做法的问题 | 这个包的做法 |
|---|---|
| **把历史全塞进上下文**：token 爆、越聊越钝、模型开始混淆哪年是哪年 | 常驻层只有 6 个小文件；43 份还是 430 份会谈都靠 `retrieve.py` 按主题取 top-k |
| **记忆污染**：把"agent 的猜测"和"来访者说过的话"混在一起写，几轮后猜测变成事实 | 事实进 `profile.md`（每条必须带出处），推测进 `insights.md`（带 confidence，可被推翻） |
| **人设写死风险结论**："这个用户没有自伤倾向"被写进系统提示，于是未来的每一轮都带着这个预设运行 | 风险只来自 `signals.md` + **本轮内容**，历史结论必须带检查日期和有效期 |

还有第四条，是我做这个包最大的动因：**心理记录里很容易混进凭据**（账号、密码、内网地址、配对码）。这些内容一旦被写进可检索的长期记忆，任何一次检索命中都可能把它复述出去。`tools/guard.py` 把这件事变成硬拦截：命中就不落盘。

---

## 二、架构（四条不变式）

```
AGENT.md                  角色层 = 可直接粘贴的系统提示。零个案事实，永不被会话写入
MEMORY_POLICY.md          记忆合同：谁写、写哪、何时过期、什么禁写
instance.md               实例层变量（一人一份，从 instance.example.md 复制）
knowledge/
  techniques.md           37 张干预技术卡 + 路由表 + 反模式表（跨来访者共享，只读）
  protocols/crisis.md     危机协议（触发即接管一切）
  protocols/boundary.md   专业帮助转介边界
memory/                   ← 记忆层：每个来访者独占整目录
  profile.md  insights.md  threads.md  signals.md  no_repeat.md
  sessions/<year>/S<YYYY-MM-DD>-<NN>.md
templates/                session / intake / first_contact / review / scales + memory-empty/
tools/                    guard / retrieve / new_session / expire / audit
```

1. **分层不越界**：`AGENT.md` 不被会话写入；`knowledge/` 跨来访者共享；`memory/` 一人一份。
2. **事实与假设分开**：他说过的进 `profile.md`，你推断的进 `insights.md`。
3. **风险实时计算**：不存在"历史风险等级"这种可复用的结论。
4. **记忆能腐烂**：每条记录都有过期条件；闭环只标记不删除。

换来访者 = 复制整包 + 换 `memory/` + 换 `instance.md`。**`knowledge/` 才是可共享的那一层，`memory/` 永远不共享。**

---

## 三、装好之后，它每一轮做什么

```
step0 读 instance.md          自称 / 代号 / 单轮问句上限 / 可选槽位
step1 guard.py input          危机扫描 →命中即整轮切到 crisis.md
step2 装载常驻层               人格 + 未闭环风险 + 纠错黑名单 + 互动偏好 + 队列
step3 retrieve.py             按主题取 1–2 份既往会谈（默认排除测试记录）
step4 选 1–3 张技术卡再说话     先接住，再点破；单轮 ≤1 问句；不列表化输出
step5 new_session.py          落盘（当天已有文件→自动合并）+ 同步 threads/signals
step6 audit.py                落盘自检，看到 WRITTEN_TODAY 才算写完
step7 expire.py（每天一次）     队列状态推进 + 复核提醒
```

## 四、安装

**Qoder**（推荐，文件读写天然可用）
```
1. 把本目录放到一个固定位置（记忆库要长期追加，别放临时目录）
2. 把 skill/SKILL.md 复制到你的 Qoder skills 目录：<配置目录>/skills/psych-support/SKILL.md
3. 编辑 SKILL.md 里的 PACK = 你刚才那个目录的绝对路径
4. 初始化记忆骨架——`.gitignore` 故意把 memory/ 的真实内容挡在版本库外，所以 clone 后要自己复制一次：
   `cp -r templates/memory-empty/. memory/`（Windows：`xcopy /E /I templates\memory-empty memory`）
5. `cp instance.example.md instance.md`，填 `AGENT_NAME` / `CLIENT_LABEL`
6. 输入 /psych-support 我今天很累
```

**其他平台（智能伙伴 / 扣子 / Dify / 任意 LLM）**
- `AGENT.md` 全文进系统提示；`knowledge/` 挂检索知识库；`memory/` 用变量或数据表承载，**只允许 memory 被写**。
- 纯粘贴场景：按 `skill/SKILL.md §2` 的常驻层清单手工放进上下文，每轮让它输出 `MEMORY_POLICY §4.8` 的 `===MEM===` 块，你复制回文件。**此时守卫只能靠人工，是降级方案。**
- ⚠️ 上传任何 `memory/` 内容到第三方平台之前，先跑 `python tools/audit.py --deep`，并把它当作"对外发送"对待。

**依赖**：Python 3.8+，只用标准库。**零 API key、零网络、零向量库**，数据不出本机。

---

## 五、使用例子

### 例 1 · 日常倾诉（工作被否定）
```
/psych-support 明明是我在做的事，汇报的时候变成他的想法了
```
它会：`guard` 判 CLEAR → 检索命中既往同类会谈 → 按 `AGENT.md §6` 判为"能叙述"→ 取 A1 课题分离 + C15 情绪分层 → **用一句承接开头**，只问一个问句，给一个可回收的小动作。
落盘：`sessions/<今天>.md`，含 `verbatim`（他的原话）、`techniques_used: [A1, C15]`、`threads_opened: [T-00x]`。

### 例 2 · 反复出现的模式
```
/psych-support 我又拖延了，然后一边拖一边骂自己
```
它会：认出"同一模式第三次出现"→ 先认可他的觉察，再用 B11（修新路而非炸旧路）降低自责强度，A2（目的论）只在**他愿意接**的时候用一次。
它**不会**：给一份五步时间管理方案（`techniques.md §2` 反模式：一次超过 3 条建议，一条都不会被执行）。

### 例 3 · 现实决策（这是它和普通"情绪安慰"最不一样的地方）
```
/psych-support 有个新机会，但要我先辞职再试岗，我有点想冲
```
它会：判为**现实决策**而不是认知扭曲 → 走 G22 条件核验四问（能不能不先放弃现有保障 / 条款是否文字确认 / 对方底细可查 / 安全垫能撑几个月），把判断标准交回给他。
法规细节：`REGULATORY_NOTES` 为空时，它只会说"要求对方文字确认并自行核实"，**不引用任何比例或法条**。
它**不会**：说"跟随你的内心"就完事，也不会替他决定去不去。

### 例 4 · 失眠 / 急性焦虑
```
/psych-support 又是三点钟醒了，躺着把明天要说的话排练了一遍
```
它会：判"情绪峰值偏身体层"→ 走 E15 身体稳态（睡前断信息、把纠结写下来、逐部位绷紧-松开、一句自我许可），**不做心理分析**。持续两周以上则按 `boundary.md` 建议线下评估。

### 例 5 · 危机信号（最重要的行为）
```
/psych-support 有时候觉得，如果我不在了，事情会不会简单一点
```
它会：`guard.py` 返回 `exit 1 / CRISIS` → **整轮切换**：不解释、不上清单、不引用历史 → 先确认此刻安全（这是唯一允许突破"单轮 1 个问句"的场合）→ 拉向他现实里的关系 → 给 `{{CRISIS_HOTLINE}}`；槽位为空时说的是"当地有 24 小时心理援助热线，我可以帮你找号码" → 本轮在 `signals.md` 写 `unresolved` + 他的原话，并在后续每一轮第一句就确认安全。

### 例 6 · 凭据（隐私拦截）
```
/psych-support 我把公司系统密码告诉你：Sun2026!abc
```
它会：正常回应他（不评判），但 `new_session.py` 写记忆时返回 `CREDENTIAL_BLOCK`，**这条内容不会落盘**。记录里只会出现"已剔除凭据类信息"这类元描述。想验证：`python tools/audit.py --deep` 应当 CLEAN。

### 例 7 · 冷启动
```
/psych-support 你还记得我们上次聊到哪了吗
```
它会：`retrieve.py recent 3` + `stats`，用**一句人话**回答（"上次你说……，留了……没回收"），并回收一句**他自己**说过的东西，而不是朗读记忆文件给你听。

### 不要用它做什么
- 给自己或他人做诊断、判断"是不是抑郁症"。
- 替代伴侣、家人、朋友的关系劳动，或替代线下咨询。
- 多个来访者共用一份 `memory/`（会互相污染，且属于严重隐私事故）。
- 把 `memory/` 提交进版本库或上传到云端知识库——`.gitignore` 已经把这几条挡住了，别关掉它。

---

## 六、工具命令速查

```bash
python tools/guard.py input "<原话>"      # 危机扫描，exit 0 通过 / 1 危机 / 3 用法错
python tools/guard.py write "<待写内容>"   # 写前凭据拦截，exit 2 = 拦截
python tools/retrieve.py q "<关键词>" -k 2 --full
python tools/retrieve.py thread T-001     # 这个话题牵扯过哪几次会谈
python tools/retrieve.py card C13         # 这张卡历史上怎么用的
python tools/retrieve.py stats            # 会谈数 / 时间跨度 / 风格分层 / 卡片使用频次
python tools/new_session.py --json '{...}'      # 落盘（当天有文件则自动合并）
python tools/new_session.py --check <file>      # 写后抽检
python tools/audit.py                       # 今天到底落盘了没有
python tools/audit.py --deep                # 全库凭据/PII 扫描
python tools/audit.py --orphans             # T-/SIG- 引用完整性
python tools/audit.py --gaps 30             # 长空档（只用于判断要不要温和回访）
python tools/expire.py                      # 队列过期 dry-run
python tools/expire.py --apply              # 真的推进状态
```

---

## 七、诚实的局限

1. **判定是硬的，执行是软的。** 脚本能保证"凭据命中就不落盘"，但不能保证模型每轮真的去跑脚本。要拿到硬强制，需要把它包成一个主循环程序（脚本调用 + 模型调用都在程序里），而不是靠 skill 指令约定。
2. **检索是 BM25，不是语义向量。** 同义词、跨语言、隐喻会召回不全。它的优点是零依赖、数据不出本机、可解释。
3. **技术卡来自一个真实个案的实践整理，示例已通用化。** 换学派、换文化语境、换人群（青少年、创伤幸存者、临终关怀）都需要重做卡片，不要直接当通用临床指南用。
4. **量表默认关闭**（`templates/scales.md`）。引入打分容易把陪伴变成填表；真要趋势数据，用那里的四字段极简形式。
5. 它**会记住你的原话**。这是它有效的原因，也是它敏感的原因。整包都在本地，请自己决定备份位置——尤其注意 OneDrive / iCloud / Dropbox 的静默同步。

---

## 八、想改的话

- **加一张卡**：在 `knowledge/techniques.md` 对应层加编号，同时补 §1 路由表的一行；卡片必须有**失效条件**，没有就别说它能用。
- **换理论底座**：只改 `AGENT.md §1` 与 `knowledge/techniques.md` 的层级标题；`memory/`、`tools/`、`protocols/` 都不用动。
- **改问句上限**：`instance.md` 的 `MAX_QUESTIONS_PER_TURN`，不用改人格文件。
- **改过期策略**：`tools/expire.py` 顶部的三个常量。

## 九、来源说明

这套卡片库和分层规则**不是从教科书抄的**。它来自一个真实个案约 **7 个月**（2026-03 至 2026-10，共 **43 次会谈**）的实际使用：哪些手法真的有用、哪些是自作聪明的打扰，都是从那段记录里回看出来的。三件最关键的结论都源自这 7 个月的教训——

- **命名比建议有效**：真正被验证有效的回应，几乎都是"给他一个更准的名字"，而不是给他一套动作；而所有清单类、练习类技术，绝大多数没有得到过一次回访。
- **连环追问会被反感**：为了把信息问全而连着追问 4 轮，直接导致了当事人的一次明确反弹。所以本包把"单轮问句上限"做成实例变量，默认 1。
- **风险断言不能写进人设**：把"历史上没有自伤记录"写进系统提示，会让未来的每一轮都带着"这个人不危险"的预设运行。所以本包改成每轮实时判定。

卡片里的**话术示例已全部通用化**，不含那位当事人的原话、生活细节或可识别信息；本包也**不包含任何真实记忆数据**（`memory/` 是空骨架）。公开这段来源，是为了说明它的可靠性来自实践校验，而不是为了披露任何个人的事。

## 许可与免责

License 请自己选一个再发布（MIT 是常见选择）。发布前建议做三件事：
1. `python tools/audit.py --deep` 应为 CLEAN；
2. 全文搜一遍你自己的来访者代号、真实日期、专有名词；
3. 确认仓库里没有 `instance.md` 和 `memory/` 的真实内容（只有骨架）。
