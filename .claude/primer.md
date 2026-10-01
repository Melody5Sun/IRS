# IRS Project Primer

> 最后更新: 2026-09-24（面试题 role 列改为 roles_json 列表，215 条逐题重新标注岗位）

## ⏭️ 下一步
- [ ] 最早的 83 道面试题（agent-interview-hub 导入）的 `keywords_json` 仍是旧的中文小节标题（如 "一、Agent 核心面试题"），不是真正的关键词——`question_text_en`/`standard_answer_en`/`role` 已经回填完，只剩这一项历史遗留问题没修
- [ ] 0voice 仓库只有 110 道可用的结构化题目（远少于最初设想的约 200）：`01.阿里篇`(29)/`02.华为篇`(12)/`03.百度篇`(2)/`05.美团篇`(1)/`06.头条篇`(1)/`08.京东篇`(1)/`09.MySQL篇`(10)/`10.Redis篇`(10)/`11.MongoDB篇`(25)/`12.Zookeeper篇`(19)；其余"公司篇"目录（腾讯/滴滴/Nginx/算法/内存/CPU/磁盘/网络通信/安全/并发）只有占位 `.gitkeep`，`21.面经` 是非结构化的个人面经叙述（未导入）
- [ ] Devinterview-io 每个仓库的 README 只公开前 15 道题的完整答案（第 16 题起要跳转官网付费查看），本次只从 11 个仓库各挑了 1~2 道凑够 200+；如果还想从这个组织继续补充，同一个仓库最多还能再挖 13 道左右（已用掉的 repo：python/sql/java/react/aws/docker/javascript/data-structures/software-architecture/golang/node-interview-questions），还有 20 多个未碰过的仓库（typescript/css/html5/mongodb/microservices/concurrency/django/net-core/computer-vision/express/nlp/oop 等）
- [ ] 用真实 PDF 简历走一遍 `/parse-pdf` → `GET/PUT /profile` → `POST /ranking`，检查排序结果和技能评分质量（解析质量本身已用真实简历验证过，见下）
- [ ] 与 DB 同事对齐：`classify_company_industry` 对词典外公司返回默认 "Software & IT Services"（"没查到"被当成"查到了"），最终 ~1000 条数据公司变多后，规则 6 会据此静默剔除这些岗位；建议词典外返回 `not_stated`。最终数据到位后用合成画像重跑 `python -m app.rule_engine <profile.json> data/careerpilot.db --stats`
- [ ] 待讨论怎么开发（规则层扩展）：**A** 更多硬约束——`deadline_at`/`posted_at`/`min_experience_years`/`visa`/`seniority` 已被 schema 迁移有意删除，做之前先定数据侧是否加回；另需先定 `target_roles/target_industries` 由规则硬筛还是由评分文档预留的 35 分（职业意向契合度）软评。**B** 简历改写的事实一致性检查器（校验 LLM 改写要点里的技能/数字/公司/日期是否有原简历证据）。**D** 技能差距 → 建议/准备进度推导，若做成多层推导，是 Experta 前向链最能体现价值的地方
- [ ] 画像持久化到数据库（目前存在内存里）
- [ ] 求职约束（目标岗位/行业/工作模式）参与推荐：JD schema 还没有这几个字段
- [ ] 将已加载的 MIND 图谱接入简历/JD 技能标准化与匹配评分
- [ ] JD 解析继续升级：在规则与 LLM 结构化抽取基础上评估 Sentence-BERT 语义匹配
- [ ] 提案中尚未开始的部分：遗传算法投递排期、Neo4j 知识图谱、RAG 面试准备

## 📊 项目阶段
**当前**: 第 1 阶段 — 简历和 JD 已可结构化，MIND 图谱已加载，匹配仍是基线版本
**截止日期**: 2026-10-25

## ✅ 已完成
- 提案定稿（IRS-Project-Proposal-V1-CN.docx）、proposal-assets/ 整理、`.claude/` 配置系统
- 后端 FastAPI 骨架（`SystemCode/backend/`）：health / resumes / jobs / recommendations 四组路由
- 简历解析：只保留 `POST /resumes/parse-pdf`（pdfminer 提取文本，纯文本的 `/parse` 已删除），调用 Gemini（OpenAI 兼容接口）抽取成结构化 `ResumeDocument`，校验失败自动重试一次
- 简历 schema：
  - 包含 name/email/phone、experiences、projects、research、skills（`list[str]`）、educations、certificates、languages（`list[str]`）
  - about 已合并进求职约束的 notes：LLM 仍抽取 about（`ParsedResume`），上传时若 notes 为空就预填进去
  - 已移出：location、desired_position（改到求职约束）、skill level、language level、visa_status/requires_sponsorship（签证相关全部删除，岗位侧 `visa_sponsorship` 和签证硬约束也一并删除）
- 用户画像 + 求职约束（本地部署，单用户）：`parse-pdf` 解析后自动存入画像 → `GET /profile` 读取 → 用户修改画像、填写求职约束（target_roles / target_industries / work_modes: onsite|hybrid|remote / notes，均可多选）→ `PUT /profile` 整体保存；重新上传简历只替换画像，保留约束
  - PUT 时除选填字段（notes、expiry_date、major、role）外都不能为空（null、空串、空列表、not_stated），experiences/projects/research/certificates 可以一条都没有；返回 422，错误里的 loc 指出具体字段，格式与 FastAPI 自带校验错误一致
  - target_roles / target_industries 已从自由文本收紧为固定范围（内容用英文，和简历 schema 保持一致）：`GET /profile/options` 返回 `target_role_categories`（10 个一级职能大类 → 具体岗位的二级索引，如 Software Development / AI & Machine Learning / Data，参考 ISCO-08/ESCO 的 ICT 职业分类整理）和 `target_industries`（15 个 IT 相关行业，参考 GICS Information Technology 板块整理），供前端渲染下拉框；`PUT /profile` 提交不在这两份清单里的值会被拒（422），清单定义见 `app/schemas/profile.py`
  - 求职约束新增 `target_employment_types`（正职 `full_time` / 实习 `internship`，可多选，`Literal` 类型自动校验），和 `work_modes` 一样是必填列表（不能提交空数组），定义见 `app/schemas/profile.py`
  - `AI & Machine Learning` 分类补充了生成式 AI/Agent 浪潮下的新岗位（AI Engineer、Generative AI Engineer、LLM Engineer、Prompt Engineer、Agent Engineer、MLOps Engineer、AI Solutions Architect），其他分类也补了 AI Product Manager、AI Governance & Compliance Specialist、Forward Deployed Engineer、Data Annotator，参考 2026 年 LinkedIn Jobs on the Rise 等招聘趋势报道
- `SYSTEM_PROMPT` 重写为英文：逐字段说明、禁止编造、强制英文输出，约 838 token
- 测试 `test_system_prompt_covers_every_schema_field`：schema 字段和 prompt 不同步时直接失败
- 旧推荐基线 `/recommendations`：技能关键词交集打分，`min_experience_years` 硬约束已随 27d2066 删除；已被下面的 `/ranking` 取代，代码保留未动
- JD 数据链路：从公开 ATS/API 同步岗位到 SQLite，支持结构化要求解析、持久化和失效岗位处理
- MIND 技能知识图谱：固定 3,333 个技能和 974 个概念的版本快照，应用启动时完成校验与内存加载
- 简历解析 → 推荐已打通：`/recommendations` 的 `candidate` 直接接收 `ResumeDocument`。技能用 JD 同一套词表归一化；经验年限按 experiences 日期的月份并集计算，重叠不重复算
- 代码结构整理（PR #8，已合并到 main）：OpenAI 兼容客户端（`ChatClient`/`OpenAICompatibleClient`）从 `llm_resume_parser.py` 拆到 `app/services/openai_client_service.py`；简历解析文件（`llm_resume_parser.py`、`resume_parser.py`）从 `app/parsers/` 提到顶层 `app/resume/`，和 `api`/`core`/`knowledge`/`parsers`/`services` 平级；合并后 `python -m pytest tests/ -q` 全量 27 个测试通过
- GitHub Actions CI 运行 backend pytest（PR #2，只对目标为 main 的 PR 和 push 触发）；当前共 94 个测试
- `launch.json` 配置好后端启动（PR #5，已合并）；`config.py` 固定读取 `SystemCode/backend/.env`，从任何目录启动都能读到
- `settings.json` 的 deny 规则禁止 Claude 读取 `.env`、打印环境变量
- `PATCH /api/profile`：局部更新画像，只传要改的字段（类似 JSON Merge Patch，`profile_service.merge_patch`），不跑 `PUT` 的“非空”校验，但仍跑 pydantic 字段校验（枚举范围等），非法值 422；无画像时和 `GET` 一样 404
- 新增 `SystemCode/frontend/` 最小 Vite + React + TypeScript 工程（原来只有一个打包过的静态 demo.html，两者共存不冲突）：
  - `src/lib/profileStorage.ts` 实现“简历解析结果存 localStorage”：画像和简历历史共用一个 key（`careerpilot:profile`），存的形状是完整 Profile（`{resume, constraints}`），首次上传 `constraints` 全空、之后重传保留已填的 `constraints`；`resumeHistory` 最新在前，超过 3 条自动裁剪；`saveProfile()` 在 PUT 成功后把后端返回结果同步回本地缓存
  - `ResumeUpload.tsx` 调 `POST /resumes/parse-pdf` 后把结果存进 localStorage；`ProfileForm.tsx` 读 `GET /profile/options` 渲染目标岗位/行业下拉框 + 工作模式/工作类型（正职/实习）勾选框，点“保存画像”调 `PUT /profile` 整体保存；本地跑通需要先起 `backend`（8000）和 `frontend`（5173，已加进 `launch.json`），backend 已加 CORS 放行 `localhost:5173`
  - `npm run test`（vitest + jsdom）覆盖 `profileStorage.ts` 的空值/保留/裁剪三个行为；`PUT /profile` 的完整链路（选目标岗位/行业、勾工作模式和工作类型、保存）已用真实浏览器交互 + 真实后端手动验证通过
- 真实 Gemini LLM 简历解析已跑通：`SystemCode/backend/.env` 配好 `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` 后，用一份真实 PDF 简历直接 `POST /resumes/parse-pdf` 返回了结构完整的 `ResumeDocument`（姓名/邮箱/电话/多段经历/项目/教育背景全部正确抽取），解析结果也用真实前端代码验证过能正确存进 localStorage
- 硬约束规则引擎 `app/rule_engine/`（Experta，包本身不依赖 FastAPI；课程要求 Decision automation 选 "Business rules & process OR Knowledge-based reasoning"，所以保留 Experta）：6 条规则（状态/学历/工作模式/雇佣类型/候选人类型/行业），`filter_jobs` 输出 job_ids，`screen_jobs` 输出通过筛选的 `JobRequirementDocument` + 统计，CLI 支持 `--stats`/`--documents`；规则清单和新增方法见该目录 README
- 修复：27d2066 把 `industry` 从 `job_analysis` 删掉、改存公司级 `company_industries` 后，规则 6 曾静默失效（测试自带 DDL 与真实 schema 脱节所以全绿）。现在按 `normalize_company_name(jobs.company)` 查 `company_industries`，读不到该表会打 WARNING；测试库改由 `tests/job_db.py` 用真实 `schema.sql` 建表
- 三个接口（请求体都是 `UserProfile`，与 `GET /profile` 返回同形）：`POST /api/rules-screening`（规则引擎，返回通过的岗位文档 + `total_jobs/passed_count/rejected_by_rule`）；`POST /api/matches/skills`（技能评分，未改）；`POST /api/ranking`（入口：进程内先调规则筛选、再对每个通过的岗位调技能评分，按 `partial_score` 降序返回 `RankedJob{job_id, company, title, skill_score}`）。真实库 + 合成画像端到端验证：105 个岗位 → 62 通过，`/ranking` 约 260 ms；规则引擎单独实测 1000 条合成岗位约 0.4 s
- 面试题库 `interview_questions` 表（`app/db/schema.sql`）+ `InterviewQuestionRepository`（`app/repositories/interview_question_repository.py`）：`source`/`external_id` 做 `UNIQUE` 去重（同 `jobs` 表模式），`skills_json`/`keywords_json` 是 flat 字符串数组（同 `job_analysis` 的 `keywords_json` 同构），`question_embedding_json` 先留空列（项目没有 Sentence-BERT/numpy 依赖，向量值等语义匹配上线时再批量回填）。数据已一次性插入 `data/careerpilot.db`：来自 [agent-interview-hub](https://github.com/Zchary1106/agent-interview-hub) 13 个公司文件夹的 `面试题与面经.md`（`### Q:`/`**参考答案：**` 结构），`source="agent-interview-hub"`，技能标签用 `app.parsers.text_parser.extract_skills` 抽取，共 83 题（Alibaba 11、ByteDance 10、小红书 9……）；按用户要求不保留抓取/导入代码模块，也不在仓库里存源 Markdown 快照——数据已落库，之后要追加/刷新需要重新一次性处理
- 面试题库改为中英双语存储：删除未使用的 `published_at` 列，新增 `question_text_en`/`standard_answer_en` 列（迁移逻辑同 `job_analysis` 已有的 `_drop_column_if_exists` 模式，新增 `_add_column_if_not_exists`，见 `app/db/sqlite.py`）。**这两列只是普通可空字段，仓库层不做任何自动翻译/LLM 调用**——按用户要求，双语内容由人工/Claude 在导入数据时直接生成好再写库，不放进后端代码里。另新增 `role` 列（可空 TEXT），取值限定在 `app/schemas/profile.py` 的 `TARGET_ROLES`（`TARGET_ROLE_CATEGORIES` 展平后的岗位清单）范围内，没有匹配的岗位就存 `NULL`；校验逻辑在 `InterviewQuestion` 的 `field_validator`（`app/schemas/interview_question.py`），和 `JobSearchConstraints.target_roles` 复用同一份清单。真实库 `data/careerpilot.db` 已跑过迁移（83 条旧数据的 `question_text_en`/`standard_answer_en`/`role` 目前都是 NULL，见下面"下一步"）
- 从 [0voice/interview_internal_reference](https://github.com/0voice/interview_internal_reference) 导入 110 道面试题到 `interview_questions`（`source="0voice/interview_internal_reference"`，`external_id` 为仓库内的相对路径）：中英文问题/答案、`skills_json`、`keywords_json`（英文，风格对齐 `job_analysis.keywords_json`）、`role`（`TARGET_ROLES` 范围内或 `NULL`）、`difficulty_level`、`company` 均由 Claude 逐题人工判断/翻译后直接写库，没有调用任何 LLM 接口或新增后端代码——按用户要求，这类一次性数据导入不进后端代码，只改数据。导入脚本本身是临时脚本（在会话 scratchpad 里执行），未保留在仓库中，和 agent-interview-hub 那次导入的处理方式一致。库现在共 193 条题目（83 + 110）
- 从 [Devinterview.io](https://github.com/orgs/Devinterview-io/repositories) 补充导入 22 道面试题（`source="Devinterview.io"`），凑够用户要求的 200+ 条：这批原文是英文，处理方向和 0voice 相反——`question_text_en`/`standard_answer_en` 直接存原文，`question_text`/`standard_answer` 是 Claude 翻译出的中文版本；覆盖 Python/SQL/Java/React/AWS/Docker/JavaScript/数据结构/软件架构/Go/Node.js 共 11 个技术方向，每个方向挑了 1~2 道，`role` 按内容映射到 `TARGET_ROLES`（如 "Frontend Developer"/"DevOps Engineer"/"Cloud Engineer"/"Software Architect"），同样没有调用任何 LLM 接口或新增后端代码。库现在共 **215** 条题目（83 + 110 + 22）
- 回填最早导入的 83 条 agent-interview-hub 数据的 `question_text_en`/`standard_answer_en`（Claude 翻译，中→英，和 0voice 那批同方向）和 `role`（几乎全部标了 "Agent Engineer"，大模型基础/微调类题目标了 "LLM Engineer"，端侧部署/鸿蒙类标了 "Embedded Software Engineer"/"Mobile Developer (Android)"，ML Pipeline/TPU-GPU 混合架构类标了 "MLOps Engineer"）。顺带发现并修复了 8 条历史脏数据——原 markdown 转存时把下一个小节的标题（如 "---\n## 二、大模型基础"）错误地拼接进了上一题的 `standard_answer` 末尾，本次一并清理（中英文都是干净版本）。全库 215 条题目的 `question_text_en`/`standard_answer_en` 已 100% 填充
- 面试题 `role`（单值 TEXT）改为 `roles_json`（JSON 数组，模型字段 `roles: list[str]`）：215 条逐题按题干重新判定，可对应多个岗位（83 条多岗位）；数据结构/算法、C/C++/Java/Python 语言基础等匹配不到具体岗位的题统一标为 `["Basic Programming Problems"]`（26 条，常量 `GENERAL_PROGRAMMING_ROLE`），空列表会被校验器自动补成该值。旧库启动时由 `_migrate_interview_role_to_roles_json` 迁移（旧值转成单元素数组后删列）

## 📖 需要先读
- [CLAUDE.md](../CLAUDE.md) — 项目完整指南
- [lessons.md](lessons.md) — 踩坑记录（**本机 Python 环境搭建方法在这里**）

## ⚠️ 已知限制
- JD 和候选人的技能匹配目前仍依赖 `skill_lexicon.py`；MIND 图谱已经加载，但尚未接入提取和评分
- MIND 上游少量 `impliesKnowingSkills` 关系指向未定义技能，加载器会统计但不会阻断应用启动
- 画像只存在进程内存里，后端重启后需要重新上传简历或 PUT；求职约束暂时不参与推荐
- 提案「决策自动化」里提到的签证约束已按需求删除；经验年限、截止日期也已从岗位 schema 删除，规则层目前只有 6 条（见上）
- `/ranking` 的 `partial_score` 最高 65（职责相似度、职业意向契合度未实现），不是最终匹配分
- 前端最小工程已打通“上传简历→解析→localStorage 缓存→编辑求职约束→PUT 保存画像”全链路，但没有接 `PATCH /profile`（只用 `PUT` 整体保存），也没有登录态/多用户概念；`SystemCode/frontend/IT CareerPilot demo.html` 仍是独立的静态打包文件，两者未打通
- 仓库里没有样例简历，prompt 效果只能靠各自本地的真实简历人工验证
- 后端使用 Conda 环境 `careerpilot-backend`；依赖安装命令为 `conda activate careerpilot-backend` 后执行 `python -m pip install -r SystemCode/backend/requirements.txt`
- 各自机器要在 `SystemCode/backend/.env` 里填入真实的 Gemini `LLM_API_KEY` 才能调用 LLM（模板见 `.env.example`）
- 禁止 Co-Authored-By 行，PR 描述里也不加 "Generated with Claude Code"。由 `.claude/hooks/commit-msg` 钩子强制检查，新克隆的仓库需要运行一次 `git config core.hooksPath .claude/hooks`
- 允许直接 push 到 main，不强制走 PR（Claude 已获得 `git push` 免确认权限，见 `.claude/settings.json`）

## 🛠️ 快速启动
```bash
conda activate careerpilot-backend
cd SystemCode/backend
python -m pytest tests/ -q          # 跑测试
python -m uvicorn app.main:app --reload   # 启动后端，文档在 /docs
```
- 也可以用 `.claude/launch.json` 里的 `backend` 配置启动（端口 8000，要先关掉占用该端口的进程）。

## 🗓️ 关键日期
- 2026-10-25 — 最终交付截止日期（代码、报告、视频、成员属性文件）
