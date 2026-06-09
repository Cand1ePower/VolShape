# VolShape

[English README](README_en.md)

VolShape 是一个 AI-native 健身教练应用。该项目解决了两类产品之间长期存在的断层:

- 像 ChatGPT、Gemini、DeepSeek 这样的通用对话式大模型，虽然很会回答问题，但并不会规范地存储和追踪一个用户长期的身体数据、训练历史、饮食记录与偏好变化。
- 传统健身 App 虽然能记录体重、体脂、训练和饮食，但大多缺少一个真正能基于这些数据持续理解用户、动态调整计划、解释原因并陪用户一起成长的智能教练。

VolShape 试图把这两边的长处真正接起来。

该项目通过结合大模型、生成式 UI、结构化数据存储、长期记忆和领域知识检索，让用户可以只通过自然对话，就完成训练计划生成、饮食记录、身体状态更新、恢复管理和知识问答，逐步形成一个会随着用户一起成长的 AI 健身教练 Agent。

## 该项目带来的体验

在 VolShape 里，用户不需要把“记录”和“提问”拆成两个完全不同的动作。

你可以像和教练聊天一样，直接说:

- “今天想练胸肩，但左肩有点不舒服，帮我安排一个安全一点的训练计划。”
- “我昨天的训练完成得怎么样？”
- “我最近体重掉到 78kg 了，睡眠一般，帮我看看训练量要不要调。”
- “这是我今晚的晚饭，帮我估算热量和三大营养。”
- “讲讲 DOMS 到底是什么，应该怎么恢复？”

系统会在理解这些内容后，自动把其中一部分变成:

- 训练计划
- 饮食卡片
- 用户画像更新
- 近期事件记录
- 长期记忆
- 专家模式下的知识检索

所以它不只是一个回答问题的聊天框，而是一个真正围绕“训练与饮食管理”运作的产品系统。

## 目前已实现的功能

### 1. 对话生成训练计划

用户可以直接在聊天页提出训练目标、疲劳状态、伤病限制、想练的部位或时间预算。

VolShape 会结合用户画像、近期训练历史、最近事件和长期记忆，生成结构化训练计划，并以卡片形式展示，方便直接执行。

### 2. 训练计划可以真正落地执行

训练计划不是停留在文字里。

生成后的训练计划卡片可以直接应用到训练页，用户在训练中可以逐组打卡、查看完成情况，训练结果会回写成真实训练事件，供下一次对话继续使用。

这意味着系统会越来越知道:

- 你最近练了什么
- 哪些动作做完了
- 哪些组没有完成
- 你的训练节奏和恢复状态在怎样变化

### 3. 饮食照片识别与营养记录

用户可以上传食物图片，系统会分析当前这顿饭的热量与三大营养，并生成饮食卡片。

这些结果不只是一次性回答，也会同步到饮食记录与统计视图中，方便后续持续追踪。

### 4. 无感更新用户信息与偏好变化

用户不需要专门进入一个资料编辑页面去手动维护所有状态。

当用户在对话里自然提到:

- 体重变化
- 训练年限
- 当前目标
- 睡眠情况
- 疲劳状态
- 伤病或疼痛
- 训练偏好

系统会自动提取其中适合长期保存的信息，并更新用户画像、动态指标或近期事件。

### 5. 专家模式知识问答

在专家模式下，VolShape 不只是调用通用大模型。

它会结合内部的运动科学 RAG 知识库，对 DOMS、恢复、Omega-3、肌肥大、疲劳管理、训练安排、营养等主题进行更有依据的回答，并在消息底部展示简洁的参考来源。

### 6. 流式交互与生成式 UI

前端会实时显示当前处理过程，例如:

- 正在分析用户意图
- 正在同步画像
- 正在检索知识
- 正在制定计划
- 正在审核安全
- 正在生成回复

同时，系统会按内容类型动态渲染训练卡片、饮食卡片和来源尾注，让整个体验更接近一个真正的 AI 产品，而不是传统 IM 聊天窗口。

## 产品使用逻辑

你可以把 VolShape 理解成一个不断循环的产品闭环:

```mermaid
flowchart LR
  A["用户通过对话提出需求"] --> B["系统读取画像 / 训练历史 / 近期事件 / 长期记忆"]
  B --> C["如有需要，进入专家知识检索"]
  C --> D["生成回复与结构化卡片"]
  D --> E["用户应用训练计划或确认饮食记录"]
  E --> F["训练完成情况 / 饮食结果写回系统"]
  F --> G["用户画像与长期记忆继续更新"]
  G --> A
```

一个典型流程可能是这样的:

1. 用户在聊天页提出今天的训练目标。  
2. Agent 读取用户的身高、目标、训练年限、近期训练记录、疲劳状态和历史偏好。  
3. 如果用户处于专家模式，系统会额外检索相关运动科学知识。  
4. 系统输出训练建议和结构化训练卡片。  
5. 用户把训练卡片应用到训练页，按组打卡。  
6. 打卡结果回写数据库，形成真实训练历史。  
7. 下一次用户再来问“昨天练得怎么样”或“今天该不该加量”，系统就不再凭空猜，而是基于真实数据继续回答。  

这就是 VolShape 和普通聊天式大模型应用最大的不同:  
它不是只回答一轮，而是在逐渐积累一个真实、持续更新的用户训练世界模型。

## 项目实现

VolShape 的目标不是把很多 AI 名词堆在一起，而是把“对话、记忆、检索、执行、安全、回写”串成一条能跑通的链路。

### 1. 多节点 Agent 工作流

后端使用 LangGraph 构建多节点工作流。

当前主链路会把一次请求拆成多个阶段，例如:

- 意图识别
- 用户画像聚合
- 知识检索
- 训练策略规划
- 动作细化
- 计划评审
- 结果修正
- 最终回复构建

### 2. 分层记忆，而不是把所有历史硬塞进 Prompt

VolShape 当前使用的是分层记忆体系，大致包括:

- 稳定不常变化的用户画像
- 动态身体指标
- 近期事件
- 语义长期记忆
- 周期性摘要

它解决的是“系统怎么长期理解一个用户”的问题。

这也是为什么用户只是在聊天里说一句“我这周睡得不太好”或“左手腕还是有点不舒服”，后续回复就能逐渐体现出这些变化。

### 3. 结构化卡片驱动的生成式 UI

大模型输出并不总是直接显示为纯文本。

系统会把某些结果组织成结构化对象，例如:

- `WorkoutCard`
- `DietCard`

前端再根据这些结构化对象渲染成真正可操作的界面，这使得 AI 输出可以直接进入业务流程，而不仅是“建议你做什么”。

### 4. 专家模式 RAG

为了让系统在运动科学、营养和恢复问题上回答得更稳，VolShape 在专家模式下引入了领域知识检索。

也就是说，专家模式不是简单“换个 prompt”，而是会在回答前真正引入知识依据。

### 5. 训练安全审查

训练建议属于风险敏感场景。

VolShape 当前在训练计划生成后，还会做一层额外的安全审查，包括:

- 基于 ACWR 的训练负荷底线判断
- 独立 evaluator 节点审查计划
- 在评分不足时触发 corrector 修正

这样可以尽量避免模型直接给出不合适的训练强度或恢复建议。

### 6. 会话、配额与可观测性

除了 AI 本身，VolShape 也实现了真实产品常见的一些基础能力:

- 登录与注册
- 多会话聊天
- 基于 NewAPI 的用户额度管理
- 模型调用记录
- Langfuse 全链路可观测性

## 系统架构概览

```mermaid
flowchart TB
  User["用户"]

  subgraph FE["前端 · Expo / React Native"]
    Chat["教练页<br/>流式对话 + 生成式 UI"]
    Train["训练页<br/>应用计划 + 打卡"]
    Explore["我的 / 发现页<br/>画像 / 饮食 / 额度"]
  end

  subgraph API["后端 · FastAPI"]
    Stream["Chat Stream API"]
    Workout["Workout API"]
    Media["Media API"]
    Auth["Auth / Session / Quota"]
  end

  subgraph Agent["Agent Workflow"]
    Intent["Intent"]
    Profile["Profile"]
    Knowledge["Knowledge"]
    Planner["Planner"]
    Executor["Executor"]
    Evaluator["Evaluator"]
    Response["Response Builder"]
  end

  subgraph Data["数据与检索"]
    SQL["PostgreSQL / SQLite"]
    Mem["Mem0 + Qdrant"]
    RAG["Qdrant + BM25"]
  end

  subgraph Obs["可观测性"]
    Trace["Langfuse"]
  end

  User --> Chat
  User --> Train
  User --> Explore

  Chat --> Stream
  Train --> Workout
  Explore --> Auth
  Chat --> Media

  Stream --> Intent --> Profile --> Knowledge --> Planner --> Executor --> Evaluator --> Response

  Profile --> SQL
  Profile --> Mem
  Knowledge --> RAG
  Response --> SQL
  Workout --> SQL

  Stream --> Trace
  Executor --> Trace
  Response --> Trace
```

## 本地运行

### 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

如果你本地已经有 PostgreSQL，推荐直接使用 PostgreSQL:

```bash
set DATABASE_URL=postgresql+asyncpg://postgres:你的密码@localhost:5432/volshape
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

如果你只是快速体验或临时测试，也可以直接使用 SQLite:

```bash
set DATABASE_URL=sqlite+aiosqlite:///volshape_local.db
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

```bash
cd frontend
npm install
npx expo start
```

如果使用 Expo Go 在手机上测试，请使用 LAN 模式，并把前端 API 地址配置为手机可访问的后端地址。

## 常用命令

### 预览 RAG 语料

```bash
backend\.venv\Scripts\python.exe backend/ingest_rag.py --preview --json
```

### 增量执行 RAG 入库

```bash
backend\.venv\Scripts\python.exe backend/ingest_rag.py --json
```

### 本地验证 RAG 检索效果

```bash
backend\.venv\Scripts\python.exe backend/query_rag.py "DOMS recovery fatigue" --json
```

### 运行离线评测

```bash
backend\.venv\Scripts\python.exe backend/evals/run_evals.py --no-report
```

## 仓库结构

```text
backend/
  app/
    api/              FastAPI 路由
    graphs/           Agent 工作流与状态
    services/         memory / rag / llm / tracing / quota / media
    database/         ORM 模型与数据库会话
  ingest_rag.py       RAG 离线入库入口
  query_rag.py        RAG 检索验证入口
  evals/              离线评测

frontend/
  src/
    app/              聊天页 / 训练页 / 我的页
    contexts/         认证与训练计划状态
    services/         SSE 与 API 客户端

ragdata/
  运动科学与训练营养相关知识源数据

docs/
  更详细的架构、RAG 与项目说明文档
```

## License

MIT
