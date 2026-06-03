# AI 应用工程后续路线图

这份文档记录 P1/P2 技术项，等 P0 完成后继续推进。目标是把 VolShape 打造成适合 AI 应用工程师面试展示的完整工程案例。

## 已确定原则

- 记忆抽取继续以 LLM 总结为核心。
- 不把身高、体重、目标等信息写成产品级硬编码规则抽取。
- 规则可以用于测试 mock、输入校验或防御性校验，但不作为主记忆抽取路径。
- LLM/New API 失败必须显式暴露，不能返回假成功。

## P1：AI 工程能力增强

### 1. Eval 体系

建议新增：

```text
evals/
  cases/
    memory_extraction.jsonl
    intent_routing.jsonl
    fitness_advice.jsonl
    safety_refusal.jsonl
  run_eval.py
  rubrics.md
```

评估维度：

- 记忆抽取是否完整。
- 意图分类是否正确。
- 训练建议是否匹配用户画像。
- 是否尊重伤病限制。
- 是否避免危险运动建议。
- 多轮对话中是否使用历史记忆。

面试价值：

- 展示“我知道 LLM 应用不能只靠感觉，需要可重复评估”。

### 2. Langfuse / Trace 完整化

当前已有 LLM tracing 基础，后续应补：

- workflow node span
- memory extraction span
- New API token provisioning span
- quota check span
- prompt version
- session id
- user tier
- error code

面试价值：

- 可以展示一条真实用户请求从 App 到 workflow 到 New API 到 DB 的完整 trace。

### 3. Prompt 版本管理

建议把 prompt 从 Python 常量逐步拆到文件：

```text
backend/app/prompts/
  memory_extraction_v1.md
  intent_classifier_v1.md
  plan_builder_v1.md
  response_builder_v1.md
```

并在 `llm_requests` 中记录：

- prompt_name
- prompt_version
- model
- temperature

面试价值：

- 展示 prompt 可以像代码一样版本化、回滚和评估。

### 4. Workflow 架构文档

建议新增 `docs/architecture.md`：

- 移动端请求
- Auth
- Quota
- New API
- LangGraph workflow
- Memory layers
- SSE streaming
- Observability

使用 Mermaid 画图，方便面试现场讲解。

## P2：工程成熟度

### 1. CI/CD

GitHub Actions 推荐步骤：

- backend pytest
- frontend `npx tsc --noEmit`
- Python import/compile check
- secret scan
- migration check

### 2. Docker Compose 部署

推荐生产组件：

- backend FastAPI
- PostgreSQL
- Redis
- New API
- Nginx
- optional Langfuse

需要明确区分：

- 本地开发 SQLite fallback
- 生产 PostgreSQL
- 测试 SQLite memory

### 3. 安全加固

必须完成：

- 旋转已暴露过的服务器 SSH 密码。
- 关闭 SSH password login，改为 key only。
- 旋转 New API access token。
- `.env` 永不提交。
- CI secret scanning。
- 定期 token rotation。

### 4. README 面试版

README 应包含：

- 项目简介
- 技术栈
- 架构图
- AI workflow
- 分层记忆系统
- New API 多用户额度系统
- Auth/Subscription
- Observability
- Evals
- 本地启动
- Demo script

## 建议推进顺序

1. Alembic migration baseline。
2. AI evals 最小闭环。
3. Langfuse workflow node tracing。
4. Prompt 文件化与版本记录。
5. README + 架构图。
6. CI/CD。
7. Docker Compose 生产化。
