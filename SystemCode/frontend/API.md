# IT CareerPilot 前端接口文档

> 以后端现有代码为准（`SystemCode/backend/app/api/routes/`）。字段的完整定义看后端启动后的 Swagger：`http://localhost:8000/docs`。
> 原型 `IT CareerPilot demo.html` 里有、后端没有的功能，见文末「原型中不实现的元素」。

## 1. 通用约定

| 项 | 说明 |
|---|---|
| Base URL | `http://localhost:8000/api`（下文路径都省略 `/api` 前缀） |
| 跨域 | 后端只放行 `http://localhost:5173`（Vite dev server） |
| 用户 | 本地单用户，无登录；画像全库只有一份 |
| 请求格式 | JSON；上传文件的两个接口用 `multipart/form-data` |
| 语言 | 简历、岗位、画像选项等业务数据都是英文；错误提示有中文也有英文 |

**错误格式**

- 一般错误：`{"detail": "错误说明字符串"}`
- 校验错误（422）：`{"detail": [{"loc": ["body", "resume", "educations", 0, "major"], "msg": "...", "type": "..."}]}`。`PUT /profile` 的「不能为空」也用同一格式（`type: "empty"`, `msg: "不能为空"`），前端可以用同一套逻辑按 `loc` 定位到出错字段

**状态码**

| 码 | 含义 |
|---|---|
| 404 | 资源不存在（岗位、上传记录、改写稿、画像） |
| 409 | 前置条件不满足：还没保存画像 / 岗位还没有结构化分析结果 |
| 413 | 上传音频超过 25 MB |
| 422 | 请求校验失败 |
| 502 | 大模型或语音转写服务出错（额度用完、服务繁忙等），提示用户稍后重试 |
| 503 | 语音转写服务未配置 |
## 2. 主流程

```
上传简历 PDF ──▶ 补全画像 + 填求职意向 ──▶ 岗位推荐（排序） ──▶ 岗位匹配详情
 parse-pdf        PUT /profile               POST /ranking         POST /jobs/{id}/match-detail
                                                  │
                                                  ├──▶ 简历改写      POST /resumes/rewrite → PUT /resumes/rewrites/{job_id}
                                                  └──▶ 面试准备      sample 出题 → 录音 → transcription 转写
```

**关键前置条件**：`/ranking`、`/resumes/rewrite`、`/resumes/rewrites/*` 都读库里保存的画像，没有画像返回 **409**。所以用户第一次使用必须先走完「上传 → 补全 → `PUT /profile`」。

## 3. 按页面的接口

### 页面 01：简历画像与求职意向

| 接口 | 用途 |
|---|---|
| `POST /resumes/parse-pdf` | 上传 PDF，解析成结构化简历 |
| `GET /resumes/history` | 上传历史列表 |
| `GET /resumes/history/{id}` | 取某次上传的完整简历 |
| `GET /profile/options` | 目标岗位、目标行业下拉框的选项 |
| `GET /profile` | 读当前画像 |
| `PUT /profile` | 整体保存画像（**唯一的创建入口**） |
| `PATCH /profile` | 局部修改已有画像 |

#### `POST /resumes/parse-pdf`
- 请求：`multipart/form-data`，字段名 `file`，只接受 PDF
- 响应：`ResumeUpload` = `{id, filename, name, uploaded_at, resume: ParsedResume}`
- **只存进上传记录，不改画像**。前端拿到后让用户检查、补全，再 `PUT /profile`，并把 `id` 填进 `resume_upload_id`
- `resume.about`（简历里的自我介绍）只在这里有，前端用它预填求职意向的 `notes`（`notes` 为空时）
- ⏱ **耗时提示**：后端调用大模型解析，需要几秒到十几秒，要有 loading 状态和较长的请求超时
- 错误：400 不是 PDF；422 提取不到文字（扫描件图片 PDF，提示用户手动填写）；502 大模型出错或输出两次都不合法（提示「解析失败，请重试或手动填写」）

#### `GET /resumes/history`
- 响应：`[{id, filename, name, uploaded_at}]`（不含简历内容）

#### `GET /resumes/history/{id}`
- 响应：`ResumeUpload`（同 parse-pdf）。**不改画像**
- 原型里的「用此版本覆盖画像」= 调这个接口 → 用户补全 → `PUT /profile`（带上这条的 `id`）
- 错误：404

#### `GET /profile/options`
- 响应：`{target_role_categories: {大类: [岗位, ...]}, target_industries: [行业, ...]}`
- 目标岗位是二级结构：先选职能大类（10 个），再选具体岗位；行业 15 个。提交不在清单里的值会 422

#### `GET /profile`
- 响应：`UserProfile`（见第 4 节）
- 错误：404 还没有画像（引导用户去上传简历）

#### `PUT /profile`
- 请求：完整的 `UserProfile`，**`resume_upload_id` 必填**
- 响应：保存后的 `UserProfile`
- 校验：除选填字段外都不能为空（`null`、空串、空数组都算空），选填字段见第 4 节
- 保存时补全后的简历会回写到 `resume_upload_id` 那条上传记录
- 画像改了之后，再调 `/ranking` 就是按新画像重新排序的结果
- 错误：422 有字段没填（按 `loc` 跳到第一个待填项）；404 `resume_upload_id` 不存在

#### `PATCH /profile`
- 请求：只传要改的字段，例如 `{"constraints": {"work_modes": ["remote"]}}`（对象递归合并，数组整体替换）
- 不做「不能为空」检查，但枚举值等字段校验照常
- 错误：404 还没有画像；422 字段值非法

### 页面 02：岗位推荐

| 接口 | 用途 |
|---|---|
| `POST /ranking` | 按画像筛选并排序，返回 Top 30 |
| `POST /jobs/{job_id}/match-detail` | 展开某个岗位：匹配理由、命中证据、差距、提升建议 |
| `GET /jobs` | 浏览原始岗位列表（可选） |

#### `POST /ranking`
- 请求：**无请求体**，用库里保存的画像实时计算
- 响应：
  ```
  {
    total_jobs, passed_count, returned_count,
    rejected_by_rule: {"status": n, "degree": n, "work_mode": n, "employment_type": n, "candidate_type": n, "industry": n},
    results: [{rank, job_id, company, title, location: {city, country} | null, employment_type, final_score}]
  }
  ```
- 流程：规则引擎硬筛选（状态/学历/工作模式/雇佣类型/候选人类型/行业）→ 匹配评分 → 按 `final_score`（0–100）降序取前 30
- 列表只有轻量字段；推荐理由、技能标签、证据要展开时调 `match-detail`
- 分页、「最低匹配度」筛选由前端在这 30 条里做
- `rejected_by_rule` 是各规则单独剔除的数量，一个岗位可能被多条规则剔除，各项相加可能大于 `total_jobs - passed_count`
- 错误：409 还没有画像

#### `POST /jobs/{job_id}/match-detail`
- 请求：完整的 `UserProfile`（前端先 `GET /profile` 拿到后原样传）
- 响应：
  - `job`：`{job_id, source, company, title, location, employment_type, url（申请链接）, description, summary, responsibilities[], required_skills[], preferred_skills[], collected_at（抓取时间）}`
  - `match`：`{final_score, core_score, preferred_skill_bonus, component_points: {required_skill_direct(≤40), responsibility(≤30), required_skill_graph(≤20), career_intent(≤10)}, ...}`
  - `recommendation`：`{level: excellent|strong|moderate|developing, level_label, summary（推荐理由）, highlights[], evidence[]}`
    - `evidence[]`：`{requirement（JD 要求）, candidate_evidence（简历命中内容）, evidence_source: skills|experience|project|research|career_intent, match_type: direct_skill|knowledge_graph|responsibility_semantic|career_intent|preferred_skill, similarity, relation, path[]}`
  - `gaps[]`：`{name, gap_type: transferable|hard_gap|optional_gap|experience_gap|intent_gap, importance: required|preferred|responsibility|career_intent, current_evidence, reason, suggestion}`
  - `improvement_plan`：`{summary, priorities: [{priority: high|medium|low, title, items[], advice}], next_action}`
- 原型对照：推荐理由 → `recommendation.summary`；技能标签 → `job.required_skills`；「抽取职责 N 条、技能要求 N 条」→ `responsibilities.length` / `required_skills.length`；申请链接 → `job.url`
- 错误：404 岗位不存在；409 岗位还没有结构化分析结果

#### `GET /jobs`
- 查询参数：`status`（默认 `active`，可选 `expired`/`inactive`）、`company`、`limit`（默认 100）
- 响应：`{jobs: [{id, source, company, external_id, title, location, description, url, employment_type, collected_at, last_seen_at, status, ...}]}`

### 页面 03：简历改写

| 接口 | 用途 |
|---|---|
| `POST /resumes/rewrite` | 针对某个岗位生成改写建议 |
| `PUT /resumes/rewrites/{job_id}` | 保存用户确认后的终稿 |
| `GET /resumes/rewrites/{job_id}` | 读已保存的终稿 |

#### `POST /resumes/rewrite`
- 请求：`{"job_id": 123}`。简历由后端从画像读取，求职意向不参与改写
- ⏱ **耗时提示**：后端调用大模型，单次约 **1 分钟**，要有明确的 loading 状态，请求超时调到 2 分钟以上。当前使用免费额度，**每天约 20 次**；额度用完或模型繁忙时返回 502，提示用户稍后重试。开发调试时尽量用 `GET /resumes/rewrites/{job_id}` 读已保存的结果，节省额度
- 响应 `ResumeRewriteResult`：
  - `blocks[]`：按块组织（每条经历/项目/研究 + 整个技能栏各一块），`{section: experience|project|research|skills, index, heading（如 "Backend Intern · Shopee"）, changes[], removed_skills[]}`。`changes` 为空表示这块不用改
  - `changes[]`（每条改动）：`{section, index, field: description|summary|technologies|skill_groups, original（原文）, value（改写后）, reasons[], needs_user_input[]}`
    - `reasons[]`：`{issue_type, explanation: {en, zh}, guideline_keys[], jd_responsibility}`。理由中英双语都有，切换语言不用重新请求
    - `issue_type` 取值：`weak_action_verb` 弱动词 / `passive_voice` 被动语态 / `buzzword` 空话 / `missing_quantification` 缺量化 / `missing_outcome` 缺结果 / `unclear_tech_stack` 技术栈不清 / `weak_jd_alignment` 与 JD 对齐弱 / `unsurfaced_skill` 技能未体现 / `irrelevant_content` 与 JD 无关
    - `needs_user_input[]`：`{placeholder（如 "[number of users]"）, question: {en, zh}, reason: {en, zh}}`。改写稿里缺数据的地方用占位符代替，向用户提问
  - `removed_skills[]`（仅技能栏块）：改写后技能栏删掉的技能，提醒用户确认
  - `rewritten_resume`：已应用全部改动的完整简历（`ResumeDocument`）
  - `deletion_suggestions[]`：`{section, index, line（null=删整条）, original, reasons[]}`，**后端没有应用**
  - `rejected_changes[]` / `rejected_deletions[]`：被后端事实校验拒掉的改动及原因（编造数字、编造技能等），可以不展示，或作为「系统已拦截」的说明
  - `guidelines[]`：引用的写作指南出处 `{key, title, source, source_url}`，用 `reasons[].guideline_keys` 关联
- 错误：409 没有画像 / 岗位没有结构化分析；404 岗位不存在；502 大模型出错

**前端负责的部分**（后端不提供）：
1. 逐块 Accept / Reject：Reject 的块用画像里的原文还原
2. 删除建议：逐条让用户确认，确认后按 `section` + `index`（+ `line`：把 description/summary 按换行拆开后的第几行）从简历里删掉
3. 补充问询：用户回答后，把改写稿里的 `placeholder` 原样替换成回答（不会重新请求模型）
4. 手动编辑、导出 PDF
5. 最后把整份简历 `PUT /resumes/rewrites/{job_id}` 保存

#### `PUT /resumes/rewrites/{job_id}`
- 请求：完整的 `ResumeDocument`（用户确认后的终稿）
- 响应：`{resume, stale, updated_at}`
- 按「当前画像对应的那份简历 + 岗位」覆盖保存，不再做改写检查
- 错误：409 没有画像；404 岗位不存在

#### `GET /resumes/rewrites/{job_id}`
- 响应：`{resume, stale, updated_at}`。`stale: true` 表示画像在保存之后又改过，提示用户「改写稿基于旧画像」
- 错误：409 没有画像；404 还没保存过这个岗位的改写稿

### 页面 04：模拟面试

| 接口 | 用途 |
|---|---|
| `POST /jobs/{job_id}/interview-questions/sample` | 按岗位从题库抽题 |
| `POST /jobs/{job_id}/interview-questions/{question_id}/transcription` | 上传一题的作答录音，返回英文转写 |

#### `POST /jobs/{job_id}/interview-questions/sample`
- 请求（都可选）：
  ```
  {
    "count": 10,                                          // 5–20，默认 10
    "difficulty_mix": {"easy": 4, "medium": 4, "hard": 2}, // 三项之和必须等于 count，否则 422
    "exclude_question_ids": [1, 2],                       // 换一批时排除已出过的题
    "seed": 42                                            // 固定随机种子可复现同一组题
  }
  ```
- 响应：
  - `{job_id, job_title, seed, generated_at, requested_count, returned_count, basic_question_count, difficulty_distribution, role_allocation[], warnings[]}`
  - `questions[]`：`{sequence, id, question_type: basic_programming|role_specific, allocated_role, question_text, standard_answer, question_text_en, standard_answer_en, difficulty_level: easy|medium|hard|not_stated, roles[], source, company}`
  - 题目和参考答案中英双语
  - `warnings` 非空时（如某个难度的题不够）展示给用户
- 错误：404 岗位不存在；409 这个岗位还没有算出对应的标准岗位（出题按标准岗位分配题目），无法出题

#### `POST /jobs/{job_id}/interview-questions/{question_id}/transcription`
- 请求：`multipart/form-data`，字段名 `audio`；格式 WebM / WAV / MP3 / M4A / MP4 / OGG（浏览器 `MediaRecorder` 录的 `audio/webm` 可直接传），≤ 25 MB
- 响应：`{job_id, question_id, transcript, language: "en", model}`
- **只支持英文**，而且是录完后整段上传，不是实时转写；视频录制和回放由前端用浏览器 API 实现，后端只要音频
- 错误：404 岗位或题目不存在；413 超过 25 MB；422 文件为空或格式不支持；502 转写服务出错；503 转写服务未配置

### 页面 05：我的目标岗位 —— ⚠️ 后端待开发

原型里的以下功能**后端还没有接口**，前端先不做或只做静态占位：

- 设为目标岗位 / 移出目标岗位
- 每个目标岗位的四步准备进度（JD 解析、简历改写、模拟面试、提交申请）
- 申请阶段记录（未申请 → 已提交申请 → 笔试 → 一面 → … → 已收到 Offer / 未通过）和自填备注
- 移出目标时级联删除该岗位的改写稿、面试记录和申请进度
- 面试作答记录的保存（目前转写结果不落库）

仪表盘里依赖这些数据的部分（「已投递 / 进笔试」统计、目标岗位卡片）同样待开发。

### 其他：健康检查

`GET /health` → `{status: "ok", service, version}`，可以用来判断后端是否启动。

## 4. 核心数据结构

### `UserProfile`
```
{
  resume: ResumeDocument,
  constraints: JobSearchConstraints,
  resume_upload_id: int        // PUT /profile 时必填
}
```

### `JobSearchConstraints`（求职意向）
| 字段 | 类型 | 说明 |
|---|---|---|
| `target_roles` | `string[]` | 必填，取值来自 `/profile/options` 的岗位清单 |
| `target_industries` | `string[]` | 必填，取值来自 `/profile/options` 的行业清单 |
| `work_modes` | `("onsite"\|"hybrid"\|"remote")[]` | 必填 |
| `target_employment_types` | `("full_time"\|"internship")[]` | 必填 |
| `notes` | `string` | 选填，补充说明 |

### `ResumeDocument`（简历）
| 字段 | 类型 | `PUT /profile` 时 |
|---|---|---|
| `name` / `email` / `phone` | `string \| null` | 必填 |
| `experiences` | `Experience[]` | 可以为空数组 |
| `projects` | `Project[]` | 可以为空数组 |
| `research` | `Research[]` | 可以为空数组 |
| `skills` | `string[]` | 必填（匹配用的扁平技能列表） |
| `skill_groups` | `SkillGroup[]` | 可以为空（技能栏原文，改写用） |
| `educations` | `Education[]` | 必填 |
| `certificates` | `Certificate[]` | 可以为空数组 |
| `languages` | `string[]` | 必填 |
| `awards` | `Award[]` | 可以为空数组 |
| `additional_info` | `string[]` | 可以为空，"Label: value" 形式的零散信息 |

`ParsedResume`（parse-pdf 返回的）= `ResumeDocument` + `about: string | null`。

子结构（**加粗**为选填，其余在 `PUT /profile` 时必填）：

| 结构 | 字段 |
|---|---|
| `Experience` | `company`, `title`, `employment_type: full_time\|part_time\|internship`（解析时可能为 null，保存前用户必须选）, `start_date`, `end_date`, `description`, `country` |
| `Project` | `title`, `summary`, `technologies: string[]`, **`role`**, **`start_date`**, **`end_date`** |
| `Research` | `type: paper\|patent\|software_copyright\|thesis\|research_project\|other`, `title`, **`institution`**, `summary`, **`start_date`**, **`end_date`** |
| `Education` | `institution`, `entry_type: degree\|exchange`, `degree: bachelor\|master\|phd\|diploma\|not_applicable`, **`major`**, `start_date`, `end_date`, `country`, **`school_tier`**, **`research_direction`**, **`gpa`**, **`ranking`**, **`courses: string[]`** |
| `Certificate` | `name`, **`issuer`**, **`issue_date`**, **`expiry_date`**, **`score`** |
| `SkillGroup` | **`category`**, `description` |
| `Award` | `name`, **`date`** |

日期字段都是字符串，保留简历原文写法（如 `"2024-06"`、`"Present"`）。

## 5. 前端现有代码需要调整

`src/components/ResumeUpload.tsx`、`src/components/ProfileForm.tsx`、`src/lib/profileStorage.ts` 是按旧接口写的：
- `parse-pdf` 现在返回整条上传记录 `{id, filename, name, uploaded_at, resume}`，不再是裸简历
- `PUT /profile` 必须带 `resume_upload_id`
- 上传历史由后端保存（`GET /resumes/history`），不需要再用 localStorage 存历史
- 还缺补全简历字段的表单

## 6. 调试 / 内部接口（前端一般不用）

| 接口 | 说明 |
|---|---|
| `POST /rules-screening` | 只跑规则引擎，请求体 `UserProfile`，返回通过的岗位文档 + 剔除统计（`/ranking` 内部已包含） |
| `POST /matches/skills` | 单独算技能分（`/ranking`、`match-detail` 内部已包含） |
| `POST /matches/responsibilities` | 单独算职责相似度 |
| `POST /matches/career-intent` | 单独算职业意向契合度 |
| `POST /jobs/analyze`、`POST /jobs/analyze-requirements` | 对一段 JD 文本做结构化分析 |
| `POST /jobs/{job_id}/analyze-requirements` | 对库里某个岗位重新做结构化分析 |
| `GET /jobs/sources`、`POST /jobs/sync` | 岗位数据源列表、同步岗位（运维用） |
| `POST /recommendations` | 旧版推荐基线，已被 `/ranking` 取代 |

## 7. 原型中不实现的元素（以后端为准）

原型里有、后端有意没做或已删除的功能，前端不要照着原型做：

- 岗位卡片的**薪资、工作准证、截止日期**，以及「可申请准证」「14 天内截止」筛选（这些字段已从岗位 schema 删除）
- 面试**单题评分、评分维度（rubric）、点评**，以及「目光在镜头」比例
- 面试**实时转写**（后端是录完整段上传，且只支持英文）。语速、填充词可以由前端根据转写文本和录音时长自己算
- 题目的**出题依据、提示要点、建议时长**，以及「系统设计 / 行为面」这类分类（题库只有难度和 basic_programming / role_specific 两种类型）
- 简历改写的**个人摘要块**；回答问询后「重写该块」（前端直接替换占位符）
- 原型写的「工作模式只影响排序」：后端的工作模式是**硬筛选**，不符合的岗位直接不出现在推荐里
- 「JD 库同步于 xx:xx」、「画像更新于 x 月 x 日」：后端没有这两个时间字段

---

需要 TypeScript 类型时，可以从后端的 OpenAPI 直接生成，不用手写：
`npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts`
