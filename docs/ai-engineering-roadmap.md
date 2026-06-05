# VolShape AI Engineering Roadmap

最后更新：2026-06-04

这份文档是 VolShape 当前的执行版计划书。它不替代早期的概念方案，而是把我们已经完成的能力、接下来真正要做的工程工作，以及为了面试价值而优先的模块整理成一份可执行路线图。

## 当前目标

把 VolShape 打造成一个可以稳定演示以下能力的 AI 应用工程项目：

- 多轮、分层记忆驱动的健身 Agent
- 具备正式账号体系、套餐、额度与可观测性的 AI 产品
- 可扩展到多模态输入，并能通过 MCP Gateway / Factory 管理外部能力
- 在“低频、低成本、适合面试展示”的约束下依然保持工程完整性

## 已完成的核心模块

### 用户与订阅体系

- 正式注册、登录、刷新令牌、鉴权与用户态恢复
- 免费 / Pro / Premium 分层套餐
- 基于 New API 的额度策略、模型访问控制与用户令牌托管

### AI 工作流

- 快速模式 / 专家模式双工作流
- LangGraph 编排
- SSE 流式返回
- 显式错误链路，避免“假成功”

### 记忆与上下文

- 多层用户记忆
- Mem0 语义记忆
- 训练计划、历史对话、近期训练事件注入上下文
- 训练完成组数写回并参与后续上下文构造

### 前端交互

- 聊天历史持久化与多会话
- 会话列表、置顶、删除、最后一次会话恢复
- 键盘弹起/收起动画修复
- 处理状态精简成单行文案

### 工程保障

- auth / quota / chat / workflow / memory / payment / migration 等测试
- Alembic baseline migration
- Langfuse tracing 基础接入

## 接下来最重要的技术方向

## P0：多模态 MCP 能力接入

这是当前最值得推进的新模块，因为它能同时提升产品能力和面试含金量。

目标不是把很多供应商直接暴露给模型，而是构建一个稳定的能力层：

- `nutrition_text.analyze`
- `nutrition_photo.analyze`
- `movement_video.analyze`

模型只面对上面 3 个能力接口；具体由哪个提供商执行、是否走本地算法、何时切换 fallback，都由后端的 MCP Gateway / Factory 决定。

### 我们的首选方案：credit-first，而不是月订阅优先

用户当前约束很明确：

- 产品短期不会大规模铺开
- 使用频率低
- 主要用于面试和作品展示
- 因此应该优先选择按次计费、免费额度、试用额度或本地零边际成本方案

### 最终推荐的主方案

#### 1. 饮食文字输入

主链路：

1. 用户输入自然语言饮食描述
2. 现有 LLM / New API 负责解析食物、份量候选与结构化意图
3. `FatSecret` 负责做规范化食物查询和营养映射
4. LLM 生成饮食建议

选择理由：

- `FatSecret` 对 startup / student / non-profit 有 `Premier Free` 计划，适合当前阶段
- 不需要先背月订阅成本
- 文字解析完全可以复用你现有的 LLM 网关

备选：

- `Edamam` 只作为补充 fallback，不作为当前主方案

#### 2. 食物照片输入

主链路：

1. 用户上传食物照片
2. 现有多模态 LLM（经 New API）先做食物识别与份量候选
3. `FatSecret` 做规范化食物匹配与营养估算
4. 前端要求用户确认份量
5. LLM 输出饮食调整建议

选择理由：

- 这是当前最符合“按次付费”的路径
- 不必为了低频使用单独订阅一整套 food vision SaaS
- 同时还能把“LLM + structured nutrition lookup”的工程能力讲清楚

试用期备份：

- `LogMeal` 适合做食物照片识别备用链路
- `YMove` 也可在 demo / 试用窗口期作为备用

#### 3. 训练视频输入

主链路：

1. 用户上传训练视频
2. `MediaPipe` 本地提取关键点、关节角度、轨迹与关键帧
3. 本地规则模块给出动作稳定性、对称性、节奏、ROM 等结构化问题
4. LLM 把结构化分析转成“教练式反馈 + 改正建议”

选择理由：

- `MediaPipe` 零边际成本，最适合低频面试项目
- 可以很好地展示“传统 CV / 姿态估计 + LLM 反馈生成”的分层架构
- 避免长期被单一商业供应商绑定

试用期备份：

- `QuickPose`
- `YMove`

### 暂不作为主方案的提供商

- `Passio`：能力强，但对当前阶段来说成本门槛偏高
- `Edamam`：文本营养能力成熟，但更适合做后续补充而不是主入口
- `YMove`：非常适合快速 demo，但长期主路径更适合作为可插拔 adapter，而不是核心依赖

## P1：MCP Gateway / Factory 工程化

我们接下来要做的不是“多接几个 API”，而是把多模态能力整理成一个清晰的工程模块。

建议结构：

```text
backend/app/services/mcp/
  __init__.py
  types.py
  catalog.py
  factory.py
  router.py
  providers/
```

职责划分：

- `router.py`
  - 判断当前输入属于哪类能力
- `factory.py`
  - 根据 capability、成本策略、可用性、用户套餐返回执行蓝图
- `catalog.py`
  - 维护 provider 元数据、价格模型、支持能力
- `providers/`
  - 每个提供商一个 adapter
- 现有 workflow
  - 只消费稳定能力接口，不直接关心供应商细节

## P1：评测与可观测性补强

### 1. Evals

补齐最小 eval 闭环：

```text
evals/
  cases/
    memory_extraction.jsonl
    intent_routing.jsonl
    nutrition_estimation.jsonl
    movement_feedback.jsonl
  run_eval.py
  rubrics.md
```

### 2. Langfuse tracing 完整化

新增或收紧这些 span / attributes：

- workflow node
- memory extraction
- quota check
- prompt name / version
- session id
- user tier
- selected MCP capability
- selected provider chain
- fallback reason
- error code

## P2：生产化成熟度

### 1. Prompt 版本化

将 prompt 从 Python 常量拆到独立文件，并记录：

- prompt_name
- prompt_version
- model
- temperature

### 2. CI / CD

至少补齐：

- backend pytest
- frontend `npx tsc --noEmit`
- migration check
- import / compile check

### 3. 架构文档

新增一份面试友好的 `docs/architecture.md`，用 Mermaid 画清楚：

- 移动端
- Auth / Subscription
- Quota / New API
- LangGraph workflow
- Memory layers
- MCP Gateway / Factory
- Langfuse

## 近期执行顺序

1. 落地 MCP Gateway / Factory 骨架
2. 先接 `nutrition_text.analyze`
3. 再接 `nutrition_photo.analyze`
4. 最后接 `movement_video.analyze`
5. 补 tracing 和 tests
6. 再做 architecture 文档与 evals

## 面试叙事建议

这个项目最该强调的不是“我接了很多 API”，而是：

- 我把 LLM、结构化数据源、姿态估计、本地状态与用户记忆组织成了一个真实的 AI 应用系统
- 我做了正式账号与配额，而不是 demo user
- 我用 Gateway / Factory 管理多模态能力，而不是把供应商直接耦死在业务里
- 我考虑了成本模型、fallback、可观测性与测试
