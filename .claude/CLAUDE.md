# Claude Code 工作流规则

本文档定义了 Claude 在 IRS 项目中的工作规范和自学规则。

## 提交规范

### ❌ 禁止事项
- **不添加 Co-Authored-By 行** — 无论谁实际执行提交（学生本人或其他协作者），一律不添加 Co-Authored-By（含 Claude 的共同作者标注）。提交以实际执行 `git commit` 操作者自己的身份进行，即"提交者本人名义"——这是学术项目的要求，不能绕过。
  - **强制机制**: `.claude/hooks/commit-msg` 是一个真正的 git `commit-msg` 钩子，会拒绝任何包含 "Co-Authored-By" 字样的提交——无论提交是 Claude Code 触发、学生本人还是协作者在终端手动执行。
  - **首次克隆后必须运行一次**（`.git/hooks/` 不受版本控制，无法随仓库自动生效）:
    ```bash
    git config core.hooksPath .claude/hooks
    ```
  - 钩子只检查提交信息文本是否含 "Co-Authored-By"，不检查/不限制 git 提交者身份（`user.name`/`user.email`）——按上述规则这已经足够，不需要额外的身份白名单。

### ✓ 必须遵守
- **提交信息语言**: 描述（主题行 `<描述>` 部分和正文要点）一律用中文，提升团队可读性；类型前缀（`feat:`/`fix:` 等）保留英文关键字，这是 Conventional Commits 的固定格式，不属于"描述内容"
- **提交信息格式**: 完整规则和示例见 [`.claude/templates/commit-message.txt`](templates/commit-message.txt)。核心规则：
  - 主题行 `<类型>: <描述>`（描述用中文），祈使语气，不超过 72 个字符
  - 空行后正文用 `-` 列出 2–5 条要点（中文），说明改了什么、为什么改
  - 类型选择顺序: `fix` → `feat` → `refactor` → `style` → `chore` → `docs` → `test` → `perf` → `ci` → 其他（如 `move`/`rename`/`wip`/`revert`）

- **分支命名**（前缀与提交类型一致，避免两套体系，仅在需要开 PR 时使用）:
  - `feat/user-auth-system`
  - `fix/env-loading-issue`
  - `docs/architecture-guide`
  - 允许直接 push 到 `main`，不强制走 PR

## 回复规范

**每次修改了文件后，回复中必须逐项说明**（不只是罗列改了哪些文件）：
1. **解决的具体问题** — 这项修改针对什么问题/症状
2. **可能改变的行为** — 这项修改会让什么行为发生变化（新增/移除功能、改变输出、改变默认值等）
3. **如何验证** — 怎么确认这项修改确实生效（命令、测试步骤，或读哪个文件确认）

多个改动可以合并成一张表或一份清单，但每一项都要覆盖这三点；不允许只写"已修改 xxx.md"而不说明以上内容。

## 代码风格与模式

### 必须遵守
- **所有代码注释使用中文** — 提升团队（学生本人 + 协作者）的可读性，不需要在阅读代码时切换语言
  - 适用范围: 行内注释、函数/类的说明性注释、TODO 标记等
  - 不适用于: 变量名、函数名、类名等标识符——保持英文（编程语言/框架惯例，也便于和第三方库、AI 工具生态对接）
  - 不适用于: 提交类型关键字（`feat:`/`fix:` 等）——这是 Conventional Commits 的固定英文关键字，不算"注释内容"

### 禁用
- Python: 避免 `any` 类型，除非有明确的必要
- JS/TS: 避免过度工程化的抽象

### 优先
- 简洁方案胜过复杂方案
- 代码清晰胜过代码量少
- 复用现有工具库胜过重新实现

## 错误处理与自学规则

**适用范围**: 每次使用 Claude Code 进行代码生成 / 开发时都适用，尤其是 **debug（排查报错、修复异常行为）** 和 **重构（调整已有代码结构）** 这两类任务——这两类工作最容易反复踩同一个坑，也最容易发现值得记录的规则。

### 每次修复 bug 或踩坑后的必做事项
1. 立即在 `.claude/lessons.md` 中记录新条目
2. 格式: `[日期] | 症状 | 规则 | 文件路径`
3. 例子:
   ```
   [2026-09-15] | ModuleNotFoundError | 检查虚拟环境激活（venv\Scripts\activate） | src/parser.py
   [2026-09-15] | 换行符问题 | Windows 上的 sed 需要 `-i.bak` 备份后缀，或使用 Python 替代 | build/convert.sh
   ```

### 知识查阅流程
- 开始新任务时，先查看 `.claude/lessons.md`
- 查找相关的规则提醒（用关键字搜索：文件名、错误类型、技术栈）
- 应用已知规则，避免重复踩坑

### 进度追踪
- 完成主要阶段后，更新 `.claude/primer.md`
- 记录: 当前进度、下一步优先项、新发现的限制
- 保持 < 100 行便于快速查阅

## 项目交付要求

完整清单（截止日期、GitHub 仓库结构、报告、视频等）见 [`SystemCode/CLAUDE.md`](../SystemCode/CLAUDE.md#交付要求截止-2026-10-25) — 避免两处维护同一份清单导致失步。

## 快捷命令

```bash
# 查看 lessons 知识库
cat .claude/lessons.md

# 查看当前阶段
cat .claude/primer.md

# 检查 git 状态（提交前必做）
git status
git log --oneline -5
```
