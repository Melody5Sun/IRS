# Lessons Learned

团队知识库 — 记录开发过程中踩过的坑和应遵守的规则。

**格式**: `[日期] | 症状/错误 | 规则/解决方案 | 涉及文件`

---

<!-- 新条目追加在此行下方，最新的在最上面 -->
[2026-10-04] | 改写事实检查把 "2,000" 当成编造数字：用户回答 "2000"，LLM 自然写成 "2,000" 就被拒 | 比较数字前先去掉千分位逗号（`rewrite_applier._numbers`）；涉及用户补充数据的检查要用「同一个数的不同写法」做测试 | SystemCode/backend/app/resume/rewrite_applier.py
[2026-10-04] | 在 Bash 工具里用 `<<'PYEOF'` heredoc 写 Python 编辑脚本，脚本里的 `"\\n"` 落到文件里变成了真换行，生成 `"` + 换行 + `".join(` 导致 SyntaxError | 含反斜杠转义的编辑脚本用 Write 工具写成文件再执行，或直接用 Edit 工具改；heredoc 只用于不含 `\\` 的内容 | 本机环境
[2026-10-04] | 用 `SystemCode/backend/.venv/Scripts/python.exe -m pytest` 跑测试，加载 conftest 时报 `ModuleNotFoundError: No module named 'sqlalchemy'` | `.venv`（2026-09-15 那条用 uv 建的）没跟上 PostgreSQL 迁移后的依赖，已过时；跑测试/alembic 一律用 conda 环境的解释器 `/d/APP/Downloads/anaconda3/envs/careerpilot-backend/python.exe`（Git Bash 里没有 `conda` 命令，见 2026-09-22 那条） | SystemCode/backend/.venv, requirements.txt
[2026-10-04] | 新增一个会读画像的路由模块（`targets.py` 里 `from app.services.profile_service import profile_service`），测试里画像始终读不到 / 会去连真实 PostgreSQL | 路由模块在导入时就绑定了 `profile_service` 这个名字，conftest 的 autouse fixture 只替换了列出的模块；新增读画像的路由时，要在 `tests/conftest.py` 的 `profile_service` fixture 里补一行 `monkeypatch.setattr(新路由模块, "profile_service", service)` | SystemCode/backend/tests/conftest.py, SystemCode/backend/app/api/routes/targets.py

[2026-10-04] | `POST /resumes/parse-pdf` 的 LLM 出错（输出两次不合法、限流/503）直接变成 500，而改写接口早已转成 502——10-02 那条规则只修了改写路由 | 修一个调 LLM 的路由的错误处理时，`grep -rn "OpenAICompatibleClient\|parse_text\|rewrite(" app/api` 把所有调 LLM 的路由一起检查；统一捕获「自己的输出不合法异常 + `openai.APIError`」转 502 | SystemCode/backend/app/api/routes/resumes.py

[2026-10-04] | 用 Bash 工具的 heredoc（`python - <<'EOF'`）往 .py 文件里写含 `"\\n".join(...)` 的代码，写出来的是真换行，导致 `SyntaxError: unterminated string literal` | 含转义序列（\n、\t、正则反斜杠）的代码改动一律用 Write/Edit 工具，不要经 shell heredoc 再由 Python 字符串二次转义；改完先 `python -m py_compile` | 本机环境（Claude Code Bash 工具）
[2026-10-04] | 简历改写检索把一行的多个问题合并成一次查询、每块截到 4 条，被动语态 11 次里只有 2 次检索到对应条目，LLM 照样改并错引条目（Gemini 两次输出错引 2/7、5/11）；按问题类型分开后每类只取向量最近 1 条，弱动词又拿到“大数据要写数据量”、与 JD 无关拿到“删掉保密信息” | 向量按主题匹配：① 每个问题类型单独检索；② 写法类和 JD 关系类问题再用“问题描述”作 query 各取 1 条（对题率 16/39→35/39）；③ 引用只认同问题类型下检索到的 key。按句切片（覆盖 0.86→0.85、噪音 +31%）和用 JD 职责向量当 query（相似度更高但条目更不对）都实测无收益。改检索前先用 `scripts/evaluate_rewrite_retrieval.py` 量化 | SystemCode/backend/app/resume/resume_rewriter.py

[2026-10-02] | 新建 `resume_rewrites`（外键指向 `resume_uploads`）后，`start-backend.ps1` 重新导入快照时的 `TRUNCATE user_profile, resume_uploads` 会报 `cannot truncate a table referenced in a foreign key constraint`（被引用表为空也一样） | 给 `resume_uploads`/`user_profile` 这类启动脚本会备份+清空的表加外键时，同步把引用表加进 `start-backend.ps1` 的 TRUNCATE 列表；用 `BEGIN; TRUNCATE ...; ROLLBACK;` 在真实库上验证 | start-backend.ps1

[2026-10-02] | 真实端到端调用 `POST /resumes/rewrite` 时 Gemini 返回 503 "model is currently experiencing high demand"，`openai.InternalServerError` 一路抛到 FastAPI，变成 500 + 整页 traceback | 调 LLM 的路由除了捕获自己的“输出不合法”异常，还要捕获 `openai.APIError`（限流、503 过载、鉴权失败都是它的子类）并转成 502 + 可读信息；503 是临时过载，稍后重试即可 | SystemCode/backend/app/api/routes/resumes.py

[2026-10-02] | 用 `apply_changes` 规则自检技能栏示例时，加分类标签（"Databases: MySQL"、"Cloud: AWS"、"Networking: TCP/IP"）被判成编造技能 databases / cloud computing / computer networks；"before go-live" 被识别出技能 Go | `_check_skill_groups` 把 `groups_text`（"分类: 描述"）整体送进 `extract_skills`，分类名命中词表别名；知识库 skills-01/skills-10 等条目推荐的分组写法在真实改写中会被拒。写示例时避开 go-live 这类撞词；检查器已改为只对 description 抽技能（见 901d836） | SystemCode/backend/app/resume/rewrite_applier.py
[2026-10-02] | Git Bash 里 `docker exec 容器 pg_dump -f /tmp/x.dump` 报 `could not open output file "C:/Users/.../Temp/x.dump"` | Git Bash 把参数里的 `/tmp/...` 自动转成 Windows 路径再传给 docker；命令前加 `export MSYS_NO_PATHCONV=1` 关掉路径转换 | 本机环境
[2026-10-02] | 想让写法类问题（被动语态、空话）检索时“通用条目优先”，实测 hit@3 反而 0.905→0.892，被动语态的正确条目在通用条目里也只排第 4 | 向量模型分不出写法问题，排序怎么调都绕不开；要么在规则检测阶段把问题类型分细、用标签过滤直接定位（拆出 passive_voice / buzzword 后 0.872→0.936），要么换能理解写法的模型/重排器。改检索策略前先跑评测再决定 | SystemCode/backend/app/schemas/resume_guideline.py, SystemCode/backend/alembic/versions/20261002_0011_split_style_issue_types.py
[2026-10-02] | 知识库从 149 条扩到 377 条后，原 42 条评测 hit@3 0.952→0.833，被动语态/空话类用例检索到的是同主题的岗位条目（Excel 报表、测试报告） | all-MiniLM-L6-v2 按主题而不是写法匹配；扩库后先用原标注跑一次评测量化稀释，再只对“新条目同样正确”的用例补标注，两个数字都报，不要只报补标注后的 | SystemCode/backend/scripts/evaluate_guideline_retrieval.py
[2026-10-02] | 不带 ORDER BY 浏览知识库表时 id 乱序（如 11,124,1,2…），重新导出快照后 pg_restore 出来仍有个别行跳位 | PostgreSQL 表没有固有顺序：`ON CONFLICT DO UPDATE` 会把行的新版本写到表尾，pg_restore 的 COPY 也可能把行塞进前面页的空隙。要物理重排用 `CLUSTER 表 USING 主键索引` 后再 `ALTER TABLE 表 SET WITHOUT CLUSTER`（不把聚簇标记留进 schema）；要稳定的顺序只能靠查询写 `ORDER BY id` | SystemCode/backend/data/database/careerpilot-postgresql-20261002.dump

[2026-10-02] | 运行库迁到 PostgreSQL 后，规则引擎、画像、简历历史都保留了一份只给测试用的 SQLite 代码；测试全绿，但测的是旧 `schema.sql` 的 `jobs/job_analysis`（生产库已没有这两张表），线上真正跑的 `screen_jobs_postgres` 零覆盖 | 一份逻辑只留一条读写路径：把"读库"和"纯逻辑"拆开，测试直接喂数据行（`make_rows`）或注入 Fake 仓库，SQL 本身用真实库跑一遍验证；不要为了测试另养一份数据库实现 | SystemCode/backend/app/rule_engine/engine.py, SystemCode/backend/tests/job_db.py, SystemCode/backend/tests/conftest.py

[2026-10-02] | 含中文注释的 `.ps1` 脚本在 Windows PowerShell 5.1 里报 `UnexpectedToken '}'`、`EmptyPipeElement`，代码本身没问题 | PowerShell 5.1 把无 BOM 的 UTF-8 文件按系统代码页（GBK）读，中文被读乱并吞掉相邻字符；`.ps1` 一律存成 **UTF-8 with BOM**。检查语法：`[System.Management.Automation.Language.Parser]::ParseFile(...)` | start-backend.ps1

[2026-10-02] | 按旧记录把 `DATABASE_URL`/`LLM_*` 写进 `SystemCode/backend/.env`，后端却读不到（下面 2026-09-17 那条已过时） | PostgreSQL 迁移后 `config.py` 改为 `ENV_FILE = PROJECT_ROOT / ".env"`，只读**仓库根目录**的 `.env`；`SystemCode/backend/.env` 已不生效。验证：在 `SystemCode/backend` 下运行 `python -c "from app.core.config import settings, ENV_FILE; print(ENV_FILE); print(settings.database_url); print(bool(settings.llm_api_key))"`（不打印密钥） | .env, SystemCode/backend/app/core/config.py

[2026-10-02] | 知识库检索用"标题 + 建议 + 一句示例"整体向量化时，用户的弱要点和条目相似度只有 0.15–0.5，42 条评测用例 hit@3 只有 0.714 | 检索 query 是简历原句，应该和"改写前"原句比，而不是和说明文字比：知识层与向量层分表，每个示例单独成块（`resume_guideline_chunks`），每条取最相近的块，hit@3 升到 0.952。改检索方式前后都用 `scripts/evaluate_guideline_retrieval.py` 量化对比 | SystemCode/backend/app/repositories/resume_guideline_repository.py
[2026-10-02] | 导出团队快照时，Claude Code 的 Bash（Git Bash）报 `docker: command not found`，`wsl -e docker` 也报"不能在 docker-desktop 发行版里调用 docker CLI" | docker CLI 在 `C:/Users/melod/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe`，用完整路径调用；容器内路径（如 `/tmp/x.dump`）作参数时预防性地先 `export MSYS_NO_PATHCONV=1`，避免 Git Bash 把它改写成 Windows 路径 | 本机环境

[2026-10-02] | 用改写检查器（`apply_changes` 的 new_skill 规则）自检知识库示例时，合理改写被判成"编造技能"：`Google Cloud Platform` 命中别名 cloud → `cloud computing`，`Docker containers` 命中 containers → `containerization`，"两周冲刺 + 每日站会"改写成 `Agile Scrum` 命中 `agile` | 技能词表的宽泛别名会让 new_skill 检查误拒同义展开；由已有经历推断出的技能（Scrum→agile）在加上蕴含关系前一律会被拒。写知识库示例和 LLM prompt 时避开这些措辞，导入前用同一套检查跑一遍"改写后只用改写前事实"；以后可用 MIND 的 `impliesKnowingSkills` 放行蕴含技能 | SystemCode/backend/app/resume/rewrite_applier.py, SystemCode/backend/app/parsers/skill_lexicon.py

[2026-09-24] | 跑 `pytest tests/` 在收集阶段就报 `ModuleNotFoundError: No module named 'numpy'`，连不相关的测试文件也跑不了（`.venv` 和 conda `careerpilot-backend` 两个环境都缺） | `tests/conftest.py` 导入了 ranking 路由 → `career_intent_scorer` → numpy，任何测试都会先加载它；`requirements.txt` 新增依赖后要重新 `pip install -r requirements.txt`。临时只跑某个不依赖这条链的测试文件可加 `--noconftest` | SystemCode/backend/tests/conftest.py, requirements.txt

[2026-09-22] | agent-interview-hub 导入的 83 条面试题里有 8 条 `standard_answer` 结尾拼进了下一个小节的 markdown 标题（如 "...兜底机制\n\n---\n\n## 二、大模型基础"），原始导入脚本没保留、事后无法复现问题根因，只能推测是按 "### Q:" 分块时把最后一题一路吃到了下一个 `##` 大标题 | 用markdown 做数据导入时，每题的正文边界不能只用"下一个同级标题"兜底，要同时按更高级的标题（如 `##`/`---`分隔线）做二次截断；批量导入后应抽样或全量 grep 一下 `---`、`^##` 这类章节标记有没有混进正文字段，而不是假设解析器一定按预期切好了 | SystemCode/backend/data/careerpilot.db（interview_questions 表）

[2026-09-22] | 本机（本 Claude Code 会话的 Bash 工具，Git Bash）没有 `conda` 命令，`conda activate` 直接报 `command not found` | conda 装在 `D:\APP\Downloads\anaconda3`（未加进这个 shell 的 PATH），`careerpilot-backend` 环境的解释器在 `D:/APP/Downloads/anaconda3/envs/careerpilot-backend/python.exe`，直接用完整路径调用即可，不依赖 `conda activate` | 本机环境
[2026-09-22] | 用 Git Bash 的 `/c/...`、`/tmp/...` 这类 POSIX 路径给原生 Windows `python.exe` 的 `sqlite3.connect()` 传参，只在**直接作为命令行参数**时才会被 Git Bash 自动转换成 Windows 路径；一旦路径是嵌在 `python -c "..."` 的脚本文本里（字符串字面量），就不会被转换，导致 `sqlite3.OperationalError: unable to open database file` | 传给原生 Windows 可执行文件、且不是独立命令行参数的路径，一律手写成 `C:/Users/...` 这种带盘符的正斜杠形式（Windows API 原生支持正斜杠），不要依赖 Git Bash 的路径自动转换 | 本机环境

[2026-09-21] | 上游 schema 把 `job_analysis.industry` 删掉、改存公司级 `company_industries` 后，规则引擎规则 6（行业）静默失效：`SELECT a.*` 读不到该列，Experta 的模式匹配不上就不触发，既不报错也不筛选（单选 AI 行业的画像该剔除 103/105，实际剔除 0），而 41 个测试全绿 | ① 测试造库要用真实的 `app/db/schema.sql`（`tests/job_db.py` 的 `make_db`），不要在测试里另写一份 DDL，否则 schema 一变测试就和真实结构脱节；② 规则依赖的数据来源读不到时必须打 WARNING（Experta 规则的缺失字段是静默不匹配，不会抛异常）；③ 别人改 schema 后，用合成画像在真实库上跑一次 `--stats`，看各规则的剔除数是不是全为 0 | SystemCode/backend/app/rule_engine/engine.py, SystemCode/backend/tests/job_db.py

[2026-09-21] | Experta 1.9.4 在 Python 3.10+ 导入即报 `AttributeError: module 'collections' has no attribute 'Mapping'` | Experta 硬性锁定 `frozendict==1.2`（该版本用了已移除的 `collections.Mapping`）；强装 frozendict 2.x 会与锁定冲突，最省事的做法是在导入 experta 前执行 `collections.Mapping = collections.abc.Mapping`，保留原依赖不动 | 规则引擎选型 spike
[2026-09-21] | durable_rules 2.0.28 在 Windows 上 `DLL load failed ... 文件名或扩展名太长`；换短路径后在 Python 3.12 上只要规则引用另一个 fact（join）就必然 segfault，3.11 正常 | durable_rules 自 2020 年未更新、PyPI 只有源码包，项目 venv 是 3.12，不要选用；venv 放在长路径（如 scratchpad）下会触发 Windows MAX_PATH 限制 | 规则引擎选型 spike

[2026-09-17] | 简历上传一直报 `LLM 未配置`，用户确认已经配置了 `LLM_API_KEY` 等变量，但报错不变 | `.env` 被放在了仓库根目录，而 `config.py` 里 `BACKEND_ROOT = Path(__file__).resolve().parents[2]` 固定只读 `SystemCode/backend/.env`，不认系统环境变量也不认根目录的 `.env`；用 `mv` 把文件挪到 `SystemCode/backend/.env`（不读取/打印文件内容）即可，不用改代码 | SystemCode/backend/.env, SystemCode/backend/app/core/config.py
[2026-09-17] | `gh pr merge <N> --auto --merge` 在仓库关闭了 `allow_auto_merge` 设置时不报错也不等待，如果此刻已满足合并条件就直接静默合并；随后 `gh pr merge` 命令切换本地工作目录回 base 分支，但没有 pull，导致本地文件短暂显示成合并前的旧内容（容易误判为改动丢失） | 判断 PR 是否已合并用 `gh pr view <N> --json state,mergedAt`，不要看 `--auto` 命令有没有报错；合并后如果本地分支被切回 base，先 `git pull` 同步再继续操作 | GitHub PR 流程
[2026-09-17] | Windows 新克隆仓库执行 `commit-msg` 钩子时报 `grep: command not found`，提交检查被跳过 | 钩子的核心校验应使用 POSIX shell 内建的 `while` 和 `case`，避免依赖目标机器未必提供的 `grep` | .claude/hooks/commit-msg
[2026-09-17] | 扩充技能同义词后，普通的 `API`/`APIs` 被识别成独立的 `api development` 技能，改变了既有推荐结果 | 技能别名应采用能明确代表能力的短语，避免把通用技术名词直接提升为额外技能；用完整回归测试检查 matched/missing 列表 | SystemCode/backend/app/parsers/skill_lexicon.py
[2026-09-17] | MIND 概念数据中同一个别名可能对应多个概念，若按唯一索引加载会阻断应用启动 | 概念别名索引必须保留全部候选；精确名称优先，歧义别名由调用方消歧 | SystemCode/backend/app/knowledge/mind_ontology.py
[2026-09-17] | 旧工作区和远端同时修改配置、技能解析与测试，直接拉取会产生冲突并可能静默删除经验年限字段 | 从最新远端创建独立集成分支，逐项迁移模块并保留远端 schema 契约，再运行完整测试 | SystemCode/backend
[2026-09-15] | 叠放 PR（#4 的目标分支是 #3 的分支）场景下，用 `gh pr merge 3 --merge --delete-branch` 合并 #3 后，#4 没有自动改为合并到 main，而是随目标分支被删而自动关闭，并且无法直接改目标分支 | 合并叠放 PR 的底层 PR 时，**先** `gh pr edit <上层PR> --base main`，**再**合并并删除底层分支。如果已经被关闭：把被删分支按原 commit 推回（`git push origin <sha>:refs/heads/<分支>`）→ `gh pr reopen` → `gh pr edit --base main` → 再删分支。另外，只改目标分支不会触发 `pull_request` CI，需要再推一个提交 | GitHub PR 流程

[2026-09-15] | JD 写 "Build APIs with Python, FastAPI and SQL." 时 sql 没被识别成必需技能；老测试用的就是这句话，但没断言 sql，所以一直没发现 | 技能词边界正则的后向断言不能直接排除 "."，否则位于句末的技能全部漏掉；只在 "." 后面还跟着字母数字时才算词的一部分（`(?![\w+#-]|\.\w)`）。写测试时要对抽取结果做完整断言（matched 和 missing 都要查），不能只看排序 | SystemCode/backend/app/parsers/text_parser.py

[2026-09-15] | 简历解析接 Gemini 时把真实 API Key 误粘贴进了 `.env.example`（该文件不在 `.gitignore` 里，是要提交的模板） | 真实密钥只能放进 `.env`（已被 `.gitignore` 排除）；`.env.example` 永远只放占位注释，不放真实值；一旦真实密钥出现在了会被提交或会进入对话记录的地方，就当作已泄露处理——去申请方（如 Google AI Studio）重新生成一个 | .env.example, SystemCode/backend/.env
[2026-09-15] | 用 `gemini-2.5-flash` 调 Gemini 的 OpenAI 兼容接口报 404 "no longer available to new users" | Gemini 免费模型名会随时间下线/更替，接入时以报错信息里 Google 给出的替代模型名为准（当前是 `gemini-3.6-flash`），不要死记某个具体型号名 | SystemCode/backend/.env, .env.example
[2026-09-15] | 本机没有系统级 Python（`python`/`py` 只是 Windows Store 空壳，运行即 exit 49 无输出） | 用 `uv`（已装在 `~/.local/bin`）自建环境：`uv python install 3.12` 下载解释器 + `uv venv --python 3.12 .venv` + `uv pip install --python .venv -r requirements.txt`，不用等系统装 Python | SystemCode/backend
[2026-09-15] | `uv python install` 报错 `failed to rename file ... 系统无法将文件移到不同的磁盘驱动器` | 本机 `%APPDATA%\Roaming` 被重定向到了跟当前目录不同的物理盘符，uv 下载后"移动安装"这一步跨盘失败；设置 `UV_PYTHON_INSTALL_DIR` 指向当前项目所在盘符下的一个目录（比如项目内的 `.uv-python/`）即可绕过 | SystemCode/backend

[2026-09-15] | commit-msg 钩子用 `grep -qi "Co-Authored-By"` 做纯子串匹配，导致提交信息里只要*描述*这个功能（比如 "block Co-Authored-By trailer"）也会被误拦 | 只应匹配真正的尾注行，用 `grep -qiE "^Co-Authored-By:"`（限定行首+冒号），不要用宽松的子串匹配去检查提交信息里"提到某个词"和"真的包含该格式的行"这两件不同的事 | .claude/hooks/commit-msg
[2026-09-15] | settings.json 里写了 `"hooks": {"PreCommit": [...]}`，看起来配置正确但从未生效 | "PreCommit" 不是 Claude Code 合法的 hook 事件名（合法列表：PreToolUse/PostToolUse/Stop 等，没有 PreCommit）；真正要拦截 git commit（含手动终端提交）必须用真实 git 钩子——把脚本命名为 `commit-msg`（接收 `$1` 消息文件路径），放进 `.claude/hooks/`，并让每个克隆者运行一次 `git config core.hooksPath .claude/hooks` | .claude/settings.json, .claude/hooks/commit-msg
[2026-09-15] | 项目有多个草稿提案文件（.md/.pptx）容易混淆 | IRS-Project-Proposal-V1-CN.docx 是唯一最终版，其他文件仅供参考可忽略 | 根目录
[2026-09-21] | 跑 `pytest tests/` 后被 git 跟踪的 `SystemCode/backend/data/careerpilot.db` 出现二进制 diff（内容没变但字节变了） | 不要在模块导入时（路由文件顶层、构造函数里）连接/迁移数据库：`JobRepository` 改为第一次访问时才 `initialize_database`，路由里会读写库的 `JobSyncService` 用 `@lru_cache` getter 延迟创建；测试要写库一律传 `tmp_path` | SystemCode/backend/app/repositories/job_repository.py, SystemCode/backend/app/api/routes/jobs.py
[2026-10-02] | `pdfminer.extract_text` 读两栏版式简历时日期与条目错位（LLMApplicationAlgorithmEngineer_CN 的硕士日期 2025.09–2026.10 被抽到项目标题后面，像是项目时间）；部分 PDF 的页眉（姓名/教育）是图片或已裁掉，文本里完全没有 | 手工解析或排查解析结果时要对照 PDF 版面核对日期归属；文本里找不到的字段留空，不要猜 | SystemCode/backend/app/api/routes/resumes.py
[2026-10-02] | LLM 按知识库建议（skills-01/skills-10 等）把技能栏拆成 "Databases"/"Cloud"/"ML/Data" 等分组后被整条拒绝为 new_skill，实际没加任何技能 | 分类名本身会命中技能词表别名（databases、cloud computing、analytics…），技能栏的新技能检查只能扫各组 description，不能扫 groups_text 拼出的 "category: description"；数字和目标公司名检查仍扫整段 | SystemCode/backend/app/resume/rewrite_applier.py
[2026-10-09] | 拆分压缩的 styles.css 时把同一选择器的多次定义合并到最后一次出现的位置，`.recommendation-job{gap:24px}` 被挪到 `@media(max-width:620px){gap:14px}` 之后，手机端间距被覆盖（桌面端看不出来） | 合并重复规则只能放在它前面所有同名媒体查询规则之前；拆分/合并 CSS 后要在桌面和 375px 两种宽度下对比 getComputedStyle 快照 | SystemCode/frontend/src/features/jobs/jobs.css
