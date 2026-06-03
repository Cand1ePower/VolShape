# VolShape — AI 健身教练 App

> 具备运动医学安全护栏、五层混合记忆系统、双模式 LangGraph Agent 的 AI 健身教练应用

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-purple.svg)](https://github.com/langchain-ai/langgraph)
[![Expo](https://img.shields.io/badge/Expo-React_Native-black.svg)](https://expo.dev)

---

## 项目简介

VolShape 是一款 AI 驱动的个人健身教练应用，通过自然语言对话生成个性化训练计划。区别于简单的 Prompt Chaining，本项目采用 **LangGraph 状态图引擎** 构建了具备意图分类、画像聚合、策略规划、执行细化、安全评审、自我修正的完整 Agent 工作流。

### 核心特点

- 🧠 **双模式 Agent**: 快速模式（3节点直出） vs 专家模式（8节点+Evaluator自反射循环）
- 🗄️ **五层记忆架构**: 结构化 DB（L1-L4） + Mem0/Qdrant 语义向量长期记忆
- 🏃 **运动医学安全护栏**: ACWR 急慢性负荷比模型 + LLM-as-Evaluator + 硬安全覆盖机制
- 📡 **SSE 流式 + Generative UI**: 实时推送 Agent 状态 + 动态渲染训练卡片
- 🔍 **Langfuse 全链路追踪**: 一次对话的所有节点以树状 Trace 展示
- 💳 **多租户计费**: NewAPI 网关路由 + Free/Pro/Premium 三档配额

---

## 技术架构

```
┌─────────────────────────────────┐
│        📱 前端 (Expo RN)         │
│  聊天页 · 训练页 · 发现页        │
│  SSE 流式接收 · Generative UI    │
└──────────────┬──────────────────┘
               │ SSE / REST
┌──────────────▼──────────────────┐
│       ⚙️ 后端 (FastAPI)          │
│                                  │
│  ┌────────────────────────────┐  │
│  │   🧠 LangGraph Agent 图    │  │
│  │                            │  │
│  │  Intent → Profile → Plan   │  │
│  │       ↓              ↓     │  │
│  │    [quick]       [detailed]│  │
│  │   Combined    Exec→Eval→   │  │
│  │      ↓        Correct→RB   │  │
│  │   Response                 │  │
│  └──────────┬─────────────────┘  │
│             │                    │
│  ┌──────────▼─────────────────┐  │
│  │  🗄️ 记忆系统 (5层)         │  │
│  │  L1 Profile  L2 Metrics    │  │
│  │  L3 Events   L4 Summary    │  │
│  │  L∞ Mem0 + Qdrant 向量     │  │
│  └────────────────────────────┘  │
│                                  │
│  配额管理 · NewAPI网关 · Langfuse │
└──────────────┬──────────────────┘
               │
    ┌──────────▼──────────┐
    │  PostgreSQL / SQLite │
    │  Qdrant (向量存储)    │
    └─────────────────────┘
```

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **前端** | Expo React Native + TypeScript | 跨平台移动端 |
| **后端框架** | FastAPI + Uvicorn | 异步 API 服务 |
| **Agent 引擎** | LangGraph (StateGraph) | 多节点 Agent 工作流 |
| **LLM** | DeepSeek Chat (via OpenAI SDK) | 大语言模型推理 |
| **记忆** | PostgreSQL (L1-L4) + Mem0/Qdrant (L∞) | 混合记忆系统 |
| **通信** | SSE (Server-Sent Events) | 流式响应 + Generative UI |
| **可观测性** | Langfuse | 全链路 LLM 追踪 |
| **API 网关** | NewAPI | 多租户 Token 路由 + 计费 |
| **Web 搜索** | Tavily | 动作知识增强 |
| **认证** | JWT (Access + Refresh Token) | 用户认证与会话管理 |

---

## Agent 工作流详解

### 快速模式 (Quick)

```
用户输入 → 意图分类 → 画像聚合 → Planner → Quick Combined → 输出
                                              (策略+执行+评估合一)
```

**特点**: 2-3 次 LLM 调用，低延迟，适合日常快速使用

### 专家模式 (Detailed)

```
用户输入 → 意图分类 → 画像聚合 → Planner → Executor → Evaluator
                                                        ↓
                                            score ≥ 85 → Response Builder → 输出
                                            score < 85 → Corrector → Executor (循环)
```

**特点**: 独立的执行-评审-修正循环，ACWR 安全模型硬覆盖，最多 1 次修正

### ACWR 安全模型

```
急性负荷 (7天) / 慢性负荷 (28天/4) = ACWR

ACWR < 1.3  → ✅ 安全 (绿灯)
1.3 ≤ ACWR ≤ 1.5 → ⚠️ 中度风险
ACWR > 1.5  → 🔴 高风险 → 硬覆盖：强制降级评分，触发 Corrector 修正
```

---

## 五层记忆架构

| 层级 | 表名 | 数据类型 | 变化频率 | 作用 |
|------|------|---------|---------|------|
| **L1** | `user_profile` | 身高/目标/伤病/训练年限 | 极慢（月级） | 个性化基础 |
| **L2** | `user_metrics` | 体重/体脂/PR 重量 | 中频（日级） | 趋势追踪 |
| **L3** | `events` | 训练/饮食/伤病事件 | 高频（每次交互） | 短期上下文 |
| **L4** | `weekly_summaries` | LLM 压缩摘要 | 周级 | 降低 Context 开销 |
| **L∞** | Mem0 + Qdrant | 语义向量 | 每次对话 | 长期记忆检索 |

**核心机制**:
- LLM 自动从自然语言中提取结构化记忆（用户说"我今天卧推65kg"→ 自动写入 `bench_press=65`）
- 轻量前置过滤（`_should_skip_extraction`）避免对闲聊触发 LLM
- 记忆垃圾回收（每 10 轮对话触发一次 LLM 驱动的短期记忆清理）

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ (或使用 SQLite fallback)

### 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 等

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动 Expo 开发服务器
npx expo start
```

### 关键环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | ❌ | API 基地址 (默认 `https://api.deepseek.com/v1`) |
| `DATABASE_URL` | ❌ | 数据库连接串 (默认 PostgreSQL localhost) |
| `LANGFUSE_PUBLIC_KEY` | ❌ | Langfuse 公钥 (可观测性追踪) |
| `LANGFUSE_SECRET_KEY` | ❌ | Langfuse 密钥 |
| `TAVILY_API_KEY` | ❌ | Tavily 搜索 API 密钥 |
| `NEWAPI_BASE_URL` | ❌ | NewAPI 网关地址 (多租户路由) |

---

## 项目结构

```
VolShape/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI 路由
│   │   │   ├── chat.py       # SSE 流式对话 + Langfuse Trace 入口
│   │   │   ├── workout.py    # 训练计划 CRUD + ACWR 闭环
│   │   │   ├── diet.py       # 饮食记录 API
│   │   │   ├── auth.py       # JWT 认证 (Access + Refresh)
│   │   │   └── payment.py    # 会员订阅
│   │   ├── graphs/           # LangGraph Agent 图
│   │   │   ├── workflow.py   # 8 节点工作流 (含 NodeSpan 追踪)
│   │   │   ├── state.py      # AgentState 类型定义
│   │   │   └── acwr.py       # ACWR 运动医学安全计算
│   │   ├── services/         # 业务服务层
│   │   │   ├── memory.py     # 五层记忆管理 + LLM 提取
│   │   │   ├── llm_client.py # 统一 LLM 客户端 (Langfuse auto-trace)
│   │   │   ├── tracing.py    # Langfuse 全链路追踪工具
│   │   │   ├── quota.py      # 配额管理 (日次数+月Token)
│   │   │   ├── newapi.py     # NewAPI 网关路由
│   │   │   ├── mem0_client.py # Mem0 语义向量记忆
│   │   │   ├── compress.py   # 事件压缩 (L3→L4)
│   │   │   └── errors.py     # 统一错误体系
│   │   ├── database/
│   │   │   ├── models.py     # 15 张 SQLAlchemy ORM 表
│   │   │   └── session.py    # 异步数据库会话
│   │   ├── core/
│   │   │   ├── config.py     # 环境变量配置
│   │   │   └── auth.py       # JWT 验证中间件
│   │   ├── prompts.py        # 集中式 Prompt 注册表 (393行)
│   │   └── main.py           # FastAPI 应用入口
│   ├── tests/                # 自动化测试
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── app/              # 页面
│   │   │   ├── index.tsx     # 聊天页 (SSE + 键盘适配)
│   │   │   ├── train.tsx     # 训练页 (计划执行 + 打卡)
│   │   │   └── explore.tsx   # 发现页 (会员 + 画像)
│   │   ├── contexts/
│   │   │   ├── AuthContext.tsx  # 认证状态管理
│   │   │   └── PlanContext.tsx  # 训练计划全局状态
│   │   └── services/
│   │       ├── sse.ts        # SSE 流式客户端
│   │       └── api.ts        # API 基地址配置
│   └── package.json
│
└── README.md
```

---

## Langfuse 追踪示例

一次用户对话在 Langfuse 中的展示:

```
Trace: volshape_chat_quick (user_id: xxx, session_id: yyy)
  ├── Span: intent_classifier        [12ms]
  │     ├── input: {user_input: "帮我安排今天的胸部训练"}
  │     ├── output: {intent: "training_plan", memory_changes: 0}
  │     └── Generation: deepseek-chat [意图分类 JSON]
  ├── Span: profile_retrieval        [25ms]
  │     └── output: {goal: "bulk", training_years: 2, recent_plans: 3}
  ├── Span: planner                  [800ms]
  │     ├── output: {plan_steps: [...], steps_count: 4}
  │     └── Generation: deepseek-chat [策略规划 JSON]
  └── Span: quick_combined           [1200ms]
        ├── output: {exercises: 5, safety_score: 92, has_ui_card: true}
        └── Generation: deepseek-chat [完整训练计划 JSON]
```

---

## License

MIT
