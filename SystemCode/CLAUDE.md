# IT CareerPilot — IRS Project

## 项目简介
- **名称**: IT CareerPilot — Intelligent Internship and Graduate Job Assistant for IT Students
- **课程**: NUS-ISS Intelligent Reasoning Systems (IRS) Practice Module
- **学生**: Sun Wenjing (A0326610N)
- **最终提案**: [Miscellaneous/IRS-Project-Proposal-V1-CN.docx](../Miscellaneous/IRS-Project-Proposal-V1-CN.docx)；最终报告见 [ProjectReport/](../ProjectReport/)

## 项目目标
面向 IT 学生的智能求职助手：简历解析 → JD 分析 → 智能匹配 → 可解释推荐 → 简历优化 → 面试准备 → 投递规划。

覆盖 IRS 四大技术方向：
1. **决策自动化**: 基于规则的资格筛选（签证、学历、经验约束）
2. **资源优化**: 遗传算法进行投递排期优化
3. **知识发现与挖掘**: 混合匹配（Sentence-BERT + 技能覆盖 + 经验契合度）
4. **认知技术**: NER 解析、知识图谱（ESCO + Neo4j）、LLM Agent、RAG

## 目录结构
```
IRS-v1/                                # 按 IRS-PM 提交模板组织
├── README.md                          # 提交用 README（模板 7 节）
├── ProjectReport/                     # 最终报告（docx，PDF 导出后也放这里）
├── SystemCode/                        # backend/ frontend/ evaluation/，以及：
│   ├── CLAUDE.md                      # 本文件
│   ├── start-backend.ps1              # 一键启动后端（运行 .\SystemCode\start-backend.ps1）
│   ├── docker-compose.yml             # 本地 PostgreSQL；name: irs-v1 固定项目名，沿用原有容器和数据卷
│   ├── .gitignore                     # 代码相关忽略规则（Video/、.claude/ 下各有自己的 .gitignore）
│   └── backend/.env(.example)         # config.py 读 SystemCode/backend/.env；.env 不提交
├── Video/                             # 只跟踪 README.md（YouTube 链接）；mp4 超过 100MB，由 Video/.gitignore 忽略
├── Miscellaneous/                     # 提案、proposal-assets/、video-production/、旧版报告
└── .claude/                           # Claude Code 配置（工作流规则、primer、lessons、hooks、模板）
```

## 交付要求（截止 2026-10-25）
- [ ] GitHub 仓库（SystemCode/、ProjectReport/、Video/、Miscellaneous/，遵循 IRS-PM 模板）
- [ ] 项目报告 PDF
- [ ] 2 个演示视频（推广 + 系统演示，禁用 AI 配音）
- [ ] 成员属性文件

## 开发环境
> 后端已用 FastAPI 搭建，启动命令见 [.claude/primer.md](../.claude/primer.md#-快速启动)。
> 前端为 **React + TypeScript**（Vite），在 `SystemCode/frontend/` 下运行 `npm install` 后 `npm run dev`。

## Claude Code 使用说明
- AI 工作流规则详见 [.claude/CLAUDE.md](../.claude/CLAUDE.md)
- 开发进度追踪详见 [.claude/primer.md](../.claude/primer.md)
- 踩坑记录详见 [.claude/lessons.md](../.claude/lessons.md)
- **提交规范**: 禁止 Co-Authored-By 行——无论学生本人还是其他协作者提交，一律以实际提交者自己的身份提交，不加共同作者标注。详见 [.claude/CLAUDE.md](../.claude/CLAUDE.md#提交规范)。首次克隆本仓库后需运行一次（`.git/hooks/` 不随仓库同步）：
  ```bash
  git config core.hooksPath .claude/hooks
  ```
