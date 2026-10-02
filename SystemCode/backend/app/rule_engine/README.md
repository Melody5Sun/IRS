# 规则引擎：岗位硬约束筛选

岗位匹配之前的一道筛选：基于 [Experta](https://github.com/nilp0inter/experta)（前向链推理，CLIPS 风格）按硬规则剔除岗位，**只筛选，不排序**。不依赖 FastAPI，不调用 LLM。

- 入口：
  - `screen_jobs(profile: UserProfile) -> ScreeningResult`：从 PostgreSQL（`DATABASE_URL`）读全部岗位跑规则，返回通过的 `JobRequirementDocument` 列表（按 job_id 升序，读自 `job_analyses.raw_analysis`，`industry` 按公司回填）+ `total_jobs` + `rejected_by_rule`；单条分析还原失败会打 WARNING 并跳过。下游评分吃的就是它
  - `screen_rows(profile, rows) -> ScreeningResult`：同上，但岗位行由调用方给（纯函数，测试用）
- 学生画像直接用 `app.schemas.profile.UserProfile`
- 岗位数据：`engine._JOBS_SQL` 一条查询，`job_postings INNER JOIN job_analyses`（没有分析记录的岗位不输出），行业取公司的 `companies.industry_id`，公司没有行业时为 not_stated
- HTTP 接口不在本包里（本包不依赖 FastAPI）：`POST /api/rules-screening`（只筛选）和 `POST /api/ranking`（筛选后接技能评分）在 `app/api/routes/`，请求体都是 `UserProfile`

| 文件 | 作用 |
|---|---|
| `constants.py` | 所有取值常量和映射表（学历等级、hybrid 放行、岗位侧词表） |
| `rules.py` | 规则：`FilterEngine` 里每个 `@Rule` 方法对应一条规则 |
| `engine.py` | 主流程：读库（`load_job_rows`）、清洗岗位字段（`to_job_fact`）、构造学生 fact、运行引擎（`screen_rows`） |
| `__main__.py` | CLI |

## 规则清单（岗位必须通过全部规则）

| # | 规则 | 剔除条件 | 不约束的情况 |
|---|---|---|---|
| 1 | 状态 | `job_postings.status != 'active'` | — |
| 2 | 学历 | 学生最高学历 < `degree_required`（等级 not_applicable < diploma < bachelor < master < phd，取所有条目中的最大值，含在读） | 岗位为 not_stated / not_applicable；学生没有学历条目或只有 not_applicable（如只有交换经历） |
| 3 | 工作模式 | `remote_policy` 不在学生 `work_modes` 中 | 岗位为 not_stated；**岗位为 hybrid**；学生 work_modes 为空 |
| 4 | 雇佣类型 | `job_analyses.employment_type` 不在学生 `target_employment_types` 中 | 岗位为 not_stated；学生列表为空 |
| 5 | 候选人类型 | 岗位 `candidate_type == experienced`，且学生没有任何 `employment_type == full_time` 的经历 | 其他 candidate_type。**注意：经历为空不会放行** |
| 6 | 行业 | 岗位所属公司的行业（`companies.industry_id`）不在学生 `target_industries` 中 | 公司没有行业；学生列表为空 |

通用处理：
- 岗位侧空值（NULL / 空串）一律视为 not_stated，即不约束。
- 岗位侧出现词表外的取值（词表来自 `app/schemas/common.py` 的 Literal 和 `TARGET_INDUSTRIES`）：记一条 WARNING 日志，按 not_stated 处理。
- 规则 1 例外：只有 `'active'` 能通过，其他任何状态值都会被剔除。

### 规则 3 的 hybrid 处理
- **岗位是 hybrid**：学生选了任何工作模式都放行（hybrid 岗位本身包含现场和远程）。
- **学生选了 hybrid，岗位是 onsite 或 remote**：按字面匹配，不放行。例如学生只选了 `["hybrid"]`，onsite 岗位会被剔除；想接受现场岗位就要同时勾选 onsite。
- 放行哪些岗位取值由 `constants.REMOTE_POLICY_MATCHES_ANY` 控制。

## 如何新增一条规则
1. 用到的取值字符串加进 `constants.py`。
2. 在 `rules.py` 的 `FilterEngine` 里加一个方法：
   ```python
   # 规则 7 xxx：一句中文说明
   @Rule(
       Student(some_field=MATCH.value),
       Job(id=MATCH.job_id, some_column=MATCH.column),
       TEST(lambda value, column: ...),  # 返回 True 表示剔除
   )
   def reject_xxx(self, job_id: int) -> None:
       self._reject(job_id, "xxx")
   ```
3. 规则要用到岗位的新列时，在 `engine._JOBS_SQL` 里加这一列，并在 `tests/job_db.py` 的 `make_rows` 里加同名键（两边列名必须一致）。如果需要新的学生侧字段，在 `engine.build_student_fact` 里加一行。如果新列需要词表校验，在 `constants.JOB_FIELD_VOCAB` 里登记。
4. 在 `tests/test_rule_engine.py` 里补"应剔除"和"应保留"两类用例。测试不建库，用 `make_rows` 直接造岗位行喂给 `screen_rows`；改了 SQL 之后用下面的 CLI `--stats` 在真实库上跑一遍，确认各规则的剔除数不是全 0。

## 运行
在 `SystemCode/backend` 目录下：
```bash
python -m pytest tests/test_rule_engine.py -q
python -m app.rule_engine path/to/profile.json              # 打印 {"job_ids": [...]}（读根目录 .env 的 DATABASE_URL）
python -m app.rule_engine path/to/profile.json --stats      # 打印每条规则单独剔除的岗位数
python -m app.rule_engine path/to/profile.json --documents  # 打印 {"jobs": [JobRequirementDocument, ...]}
```
`--stats` 的"单独剔除数"是被该规则拒绝的岗位数，不管其他规则是否也拒绝了它，所以各项相加会大于实际剔除总数。

## 已知事项
- Experta 1.9.4 锁定的 `frozendict==1.2` 在 Python 3.10+ 下无法导入，`rules.py` 顶部有一行 `collections.Mapping` 兼容补丁，不要删。
