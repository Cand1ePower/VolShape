---
tags: [VolShape, 架构设计, Agent, 健身APP, 项目规划]
created: 2026-05-31
updated: 2026-05-31
---

### 与 ChatGPT/通用大模型的差异（面试必问 "Why not just use ChatGPT?"）

| 维度 | ChatGPT | VolShape |
|------|---------|-----------|
| 记忆 | 单次对话，窗口关闭即忘 | 持久化长期记忆，跨会话追踪体重/训练/饮食变化 |
| 训练计划 | 一次性生成，无审查 | Plan→Execute→Reflection 三阶段，含生理学逻辑校验 |
| 饮食记录 | 需手动描述 | 拍照→视觉识别→USDA API 校准→自动入仓 |
| 进度追踪 | 无 | 自动生成力量增长曲线、体重变化图、训练热力图 |
| 主动性 | 被动问答 | 主动检测异常（如体重下降过快），推送调整建议 |
| 个性化 | 靠 Prompt | 基于用户 3 个月历史数据做个性化容量调控 |

---

## 二、安全架构


```
┌─────────────────────────────────────────────────────────┐
│                    移动端 (React Native)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ 聊天页    │  │ 训练页    │  │ 我的页               │  │
│  │ (SSE流式) │  │ (本地优先) │  │ (RESTful 图表数据)   │  │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
│       │             │                   │               │
│       │   JWT Token (存 SecureStore)     │               │
└───────┼─────────────┼───────────────────┼───────────────┘
        │             │                   │
   SSE Stream    REST API            REST API
        │             │                   │
┌───────┴─────────────┴───────────────────┴───────────────┐
│                   FastAPI 后端 (服务端)                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  │
│  │ Auth     │  │ Quota    │  │ Content Safety        │  │
│  │ (JWT)    │  │ Limiter  │  │ (敏感词/合规过滤)     │  │
│  └────┬─────┘  └────┬─────┘  └───────────┬───────────┘  │
│       └──────────────┼──────────────────┘               │
│              ┌───────┴────────┐                          │
│              │  LangGraph      │                          │
│              │  StateGraph     │                          │
│              │  (PostgresSaver)│                          │
│              └───────┬────────┘                          │
│         ┌────────────┼────────────┐                      │
│    ┌────┴────┐  ┌────┴────┐  ┌───┴─────┐               │
│    │ Mem0    │  │ pgvector │  │ Redis   │               │
│    │ (记忆)  │  │ (RAG)    │  │ (缓存)  │               │
│    └─────────┘  └─────────┘  └─────────┘               │
│         ┌──────────────────────────────┐                │
│         │  PostgreSQL (Checkpoints +   │                │
│         │  用户数据 + 训练记录 + 饮食)  │                │
│         └──────────────────────────────┘                │
└─────────────────────────────────────────────────────────┘
        │
        │ API Key 仅存于服务端环境变量
        ▼
┌───────────────────┐
│ LLM Providers     │
│ (GPT-4o / Claude / │
│  Gemini / Qwen)   │
└───────────────────┘
```

### 关于延迟

1. **SSE 流式传输** — 服务端逐 token 转发，首字延迟与直连几乎一致
2. **Edge 部署** — 将 FastAPI 部署在 Cloudflare Workers / Vercel Edge，全球加速
3. **端侧轻量模型** — 简单的意图分类、信息提取用本地小模型（如 Gemini Nano 或 MediaPipe），复杂推理走云端

---

## 三、LangGraph 多 Agent 编排

### Agent 职责划分

这是五个 AI 建议的综合最优解：

```
                          ┌──────────────┐
                          │  Supervisor   │
                          │  (Router)     │
                          └──────┬───────┘
                 ┌───────────────┼───────────────┐
                 │               │               │
          ┌──────┴──────┐ ┌─────┴──────┐ ┌──────┴──────┐
          │ Memory Agent │ │ Coach Agent│ │ Diet Agent  │
          │ (静默提取+    │ │ (Plan&     │ │ (多模态+    │
          │  冲突消解+    │ │  Execute+  │ │  API校准)   │
          │  记忆压缩)    │ │  Reflection)│ │             │
          └──────────────┘ └─────┬──────┘ └──────────────┘
                                 │
                          ┌──────┴──────┐
                          │ Search Agent│
                          │ (Tavily+    │
                          │  RAG检索)   │
                          └─────────────┘
```

### LangGraph StateGraph 详细设计

```python
# State Schema
class AgentState(TypedDict):
    # 用户输入
    user_input: str
    user_id: str
    session_id: str
    
    # 意图路由
    intent: str  # "training_plan" | "diet_log" | "chat" | "profile_update"
    
    # 检索到的上下文
    user_profile: dict          # 从 Mem0 + PostgreSQL 检索
    recent_events: list[dict]   # 最近 7 天事件
    rag_context: str            # 从知识库检索的相关知识
    
    # Agent 输出
    plan_steps: list[str]       # Planner 拆解的步骤
    execution_results: dict     # Executor 执行结果
    reflection_result: dict     # Reflection 审查结果
    final_response: str         # 最终回复
    ui_components: list[dict]   # json-render 组件列表
    
    # 控制
    route: str                  # 路由决策
    error_count: int            # 重试计数
```

### 节点设计

```
User Input
    │
    ▼
[Node: Intent Classifier]  ← 轻量模型，4 类意图分类
    │
    ├─ "profile_update" → [Memory Agent] → 提取信息 → 更新 Mem0 + PG → 返回确认
    │
    ├─ "diet_log" → [Diet Agent] → VLM 识别 → USDA API 校准 → 生成食物卡片
    │
    ├─ "training_plan" → 
    │       │
    │       ▼
    │   [Node: Profile Retrieval]  ← 从 Mem0 检索用户画像 + 伤病 + 近期训练
    │       │
    │       ▼
    │   [Node: RAG Retrieval]      ← 从 pgvector 检索相关运动科学知识
    │       │
    │       ▼
    │   [Node: Planner]            ← LLM: 制定分步计划 (Plan)
    │       │
    │       ▼
    │   [Node: Executor]           ← LLM + Tool Calling: 生成具体训练方案 (Execute)
    │       │                       ← 调用 Tavily 获取动作图示
    │       │                       ← 调用 weight_history tool 获取历史重量
    │       ▼
    │   [Node: Evaluator]          ← LLM: 运动康复师视角审查 (Self-Reflection)
    │       │                       ← 检查: 肌群平衡、CNS负荷、伤病限制、ACWR
    │       │
    │       ├── score < 70 → [Node: Corrector] → 修改计划 → 回到 Executor
    │       │
    │       └── score >= 70 → [Node: Response Builder] → 组装最终回复 + UI组件
    │
    └─ "chat" → [Node: Chat] → 流式回复（注入 Profile 上下文）
```

### 一个完整的训练计划生成流程示例

```
用户: "今天想练胸肩，但左肩有点不舒服"

1. Intent Classifier → "training_plan"

2. Profile Retrieval:
   - Mem0 返回: 体重64kg, 减脂期, 肩袖肌群劳损史, 上周卧推PR 70kg×8
   - PG 查询: 最近7天训练: 周一腿, 周三背, 周五休 → 距上次上肢训练已5天

3. RAG Retrieval:
   - pgvector 检索 "肩部不适 胸部训练 安全动作" → 返回: 
     "肩袖肌群劳损时应避免颈后下拉、杠铃直立划船、
      优先选择对肩关节压力小的动作如绳索飞鸟、器械推胸"

4. Planner 输出:
   Step 1: 选择肩部友好的胸部复合动作
   Step 2: Tavily 搜索标准动作图示
   Step 3: 确定组数/次数/重量 (基于历史PR和当前状态)
   Step 4: 安排肩部孤立动作 (避开疼痛位置)

5. Executor 调用工具:
   - call_weight_history("bench_press") → 返回: 最近3次: 65kg×10, 67.5kg×8, 70kg×8
   - call_tavily_search("dumbbell chest press proper form") → 返回图片URL
   - 生成具体方案:
     1. 器械推胸 4×10-12 @ 55kg (替代杠铃卧推, 减少肩关节压力)
     2. 上斜哑铃卧推 3×10-12 @ 22.5kg
     3. 绳索飞鸟 3×12-15 @ 15kg
     4. 侧平举 4×12-15 @ 8kg (避开前束, 减少刺激)
     5. 面拉 3×15 @ 12kg (强化肩袖稳定性)

6. Evaluator 审查 (身份: 运动康复师):
   ✅ 避开了杠铃卧推(肩关节压力过大)
   ✅ 加入了面拉(肩袖强化)
   ✅ 容量适中(减脂期不需要过高容量)
   ⚠️ 建议: 每个动作前增加一组轻重量热身
   Score: 85/100 → 通过

7. Response Builder:
   - 生成包含训练表格 + 动作图示的 json-render 组件
   - 附带解释: "因为你提到左肩不适，我用器械推胸替代了杠铃卧推..."
   - 附带提醒: "如果训练中左肩疼痛加剧，立即停止并告诉我"
```

---

## 四、记忆系统设计

### 为什么不用文件存储？

你在设计里提到的"多文件记录用户信息，超过一周压缩"——这在工程上有三个致命缺陷：

1. **查询效率**：当用户说"我最近卧推涨了多少"，你需要全文检索所有文件，无法结构化查询
2. **冲突管理**：用户说"我现在64kg了"，旧文件里记录66kg——AI 读到两个值会产生幻觉
3. **上下文膨胀**：一旦使用超过一个月，压缩后的文本也会轻松突破 10K token

### 分层记忆架构

```
┌─────────────────────────────────────────────────────┐
│                   Layer 0: Prompt Cache              │
│  System Prompt: 角色 + 安全规则 + 输出格式            │
│  (每次请求固定，可被 Anthropic Prompt Cache 缓存)     │
├─────────────────────────────────────────────────────┤
│                   Layer 1: Core Profile              │
│  不变的/缓慢变化的硬指标                              │
│  {"height": 175, "gender": "male", "injuries":       │
│   ["左肩袖劳损"], "goal": "减脂", "training_years": 3}│
│  存储: PostgreSQL user_profile 表                    │
├─────────────────────────────────────────────────────┤
│                   Layer 2: Dynamic Metrics           │
│  频繁变化的数据 (体重/体脂/PR/作息)                   │
│  存储: PostgreSQL user_metrics 表 (时序) + Mem0      │
│  检索: 取最近 7 天 + Mem0 语义搜索 Top-K              │
├─────────────────────────────────────────────────────┤
│                   Layer 3: Episodic Memory           │
│  最近 7 天的完整事件日志 (训练/饮食/睡眠)              │
│  存储: PostgreSQL events 表                          │
│  压缩: 超过 7 天 → 后台 Agent 生成周摘要              │
├─────────────────────────────────────────────────────┤
│                   Layer 4: Semantic Memory           │
│  长期压缩的知识 (如 "冬天容易增重", "考试期训练中断") │
│  存储: Mem0 (向量化 + 语义检索)                       │
│  更新: 每周定时任务自动生成新的语义记忆                │
└─────────────────────────────────────────────────────┘
```

### 具体数据表设计

```sql
-- 核心画像 (Layer 1)
CREATE TABLE user_profile (
    user_id UUID PRIMARY KEY,
    height_cm DECIMAL,
    gender TEXT,
    birth_date DATE,
    goal TEXT CHECK (goal IN ('bulk', 'cut', 'maintain', 'strength', 'endurance')),
    training_years INTEGER,
    injuries TEXT[],  -- ["左肩袖劳损", "腰间盘突出史"]
    medical_conditions TEXT[],  -- ["二型糖尿病"]
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 动态指标 (Layer 2 - 时序数据，用于折线图)
CREATE TABLE user_metrics (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES user_profile(user_id),
    metric_type TEXT,  -- "weight" | "body_fat" | "muscle_mass" | "bench_press" | "squat" | "deadlift"
    value DECIMAL,
    unit TEXT,  -- "kg" | "%" | "reps"
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    source TEXT,  -- "user_input" | "agent_extracted" | "wearable"
    UNIQUE(user_id, metric_type, recorded_at)
);

-- 事件日志 (Layer 3)
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES user_profile(user_id),
    event_type TEXT,  -- "training" | "diet" | "sleep" | "supplement" | "injury" | "note"
    payload JSONB,  -- 灵活结构: {"action": "卧推", "weight_kg": 70, "reps": 8, "sets": 4}
    event_date DATE DEFAULT CURRENT_DATE,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- 训练计划
CREATE TABLE training_plans (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES user_profile(user_id),
    plan_json JSONB,  -- 完整的训练计划 JSON (含动作/组数/图片URL/说明)
    target_date DATE,
    status TEXT DEFAULT 'active',  -- active | completed | archived
    completion_data JSONB,  -- 用户完成情况 (哪些动作打勾)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 饮食记录
CREATE TABLE diet_records (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES user_profile(user_id),
    meal_type TEXT,  -- "breakfast" | "lunch" | "dinner" | "snack"
    food_items JSONB,  -- [{"name": "鸡胸肉", "weight_g": 200, "calories": 330, "protein": 62}]
    total_calories INTEGER,
    total_protein DECIMAL,
    total_carbs DECIMAL,
    total_fat DECIMAL,
    image_url TEXT,  -- 如果有拍照
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- 周摘要 (Layer 3→4 压缩产物)
CREATE TABLE weekly_summaries (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES user_profile(user_id),
    week_start DATE,
    summary_text TEXT,  -- AI 生成的摘要: "本周训练4次, 平均睡眠6.5h, 体重下降0.3kg..."
    metrics_snapshot JSONB,  -- 结构化数据快照
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, week_start)
);
```

### Memory Agent 的信息提取与冲突消解

```python
# Memory Agent 伪代码
async def memory_agent_extract(user_input: str, user_id: str):
    # Step 1: 调用轻量模型提取结构化信息
    extracted = await llm_extract(user_input, schema=MEMORY_SCHEMA)
    
    # Step 2: 检查冲突
    for item in extracted:
        current = await mem0.get(user_id, key=item.key)
        if current and current.value != item.value:
            # 发现冲突: 旧值 66kg → 新值 64kg
            await mem0.update(user_id, key=item.key, 
                            new_value=item.value, 
                            old_value=current.value)
            # 同时写 PostgreSQL 时序表 (用于折线图)
            await db.insert_metric(user_id, item.key, item.value)
        elif not current:
            await mem0.create(user_id, item.key, item.value)
    
    # Step 3: 返回简洁确认 (用户不需要看到内部过程)
    if len(extracted) == 1:
        return f"已更新: {extracted[0].key} → {extracted[0].value}"
    else:
        return f"已更新 {len(extracted)} 项信息"
```

### 纠错机制设计

用户在聊天中直接纠错时：
```
用户: "不对，我体脂不是20%，是18%"

→ Memory Agent 检测到否定词 + 修正值
→ 查询当前记录: body_fat = 20%
→ 执行更新: body_fat = 18%
→ 写入 audit_log: {"action": "correction", "field": "body_fat", "old": 20, "new": 18}
→ 回复: "已修正体脂率为 18%"
```

---

## 五、A2UI / 生成式 UI 落地策略

### A2UI vs json-render：选择 json-render

四个 AI 中 Gemini 给出了最详细的分析，我同意它的结论：

| 对比维度 | A2UI | json-render |
|---------|------|-------------|
| 设计理念 | 多智能体分布式 UI 协议 | 集中式强约束渲染 |
| 适合场景 | 多平台、多 Agent 生态 | 单体应用、React Native |
| 复杂度 | 需要宿主应用充当"微型浏览器" | 只需预定义组件目录 + Zod Schema |
| 落地成本 | 高（协议理解 + 事件回传体系） | 低（与 React Native 原生集成） |
| 你的项目 | 过度设计 | **完美匹配** |

### json-render-react-native 实施方案

```typescript
// 1. 定义组件目录 (Component Catalog)
const workoutCardSchema = z.object({
  type: z.literal("workout_card"),
  title: z.string(),
  targetMuscles: z.array(z.string()),
  exercises: z.array(z.object({
    name: z.string(),
    sets: z.number(),
    reps: z.string(),
    weight: z.string().optional(),
    imageUrl: z.string().optional(),
    notes: z.string().optional(),
  })),
  disclaimer: z.string().optional(),
});

const dietCardSchema = z.object({
  type: z.literal("diet_card"),
  mealType: z.enum(["breakfast", "lunch", "dinner", "snack"]),
  foodItems: z.array(z.object({
    name: z.string(),
    weightGrams: z.number().optional(),
    calories: z.number(),
    protein: z.number(),
    carbs: z.number(),
    fat: z.number(),
  })),
  totalCalories: z.number(),
});

// 2. 注册组件
const registry = defineRegistry({
  workout_card: {
    schema: workoutCardSchema,
    component: WorkoutCard,  // React Native 原生组件
  },
  diet_card: {
    schema: dietCardSchema,
    component: DietCard,
  },
  progress_chart: {
    schema: progressChartSchema,
    component: ProgressChart,
  },
  search_result: {
    schema: searchResultSchema,
    component: SearchResultCard,
  },
});

// 3. LLM 通过 Function Calling 输出的 JSON 直接映射为原生组件
```

### 卡片交互流程

```
1. LLM 输出: {"tool": "create_workout_card", "params": {...训练数据...}}

2. 前端接收 → Registry 匹配 → 渲染 <WorkoutCard>

3. 用户看到卡片，点击"应用"按钮:
   → 调用 REST API POST /api/plans/apply
   → 数据持久化到 PostgreSQL
   → 跳转到训练页 (React Navigation)
   → 同时向聊天流发送确认消息

4. 用户点击"修改":
   → 卡片进入编辑模式 (本地状态，不经过 LLM)
   → 用户可以滑动调整组数/次数/重量
   → 修改后再次"应用"保存
```


---

## 七、健身 APP 特有的技术亮点

### 1. ACWR 算法集成（损伤预防）

这是 Gemini 提的建议，是最具专业性的差异化亮点：

```python
def calculate_acwr(user_id: str, new_session_rpe: int, new_session_minutes: int) -> dict:
    """
    Acute-to-Chronic Workload Ratio
    急性负荷: 过去 7 天总负荷
    慢性负荷: 过去 28 天平均每周负荷
    安全区: 0.8 - 1.3
    危险区: > 1.5
    """
    # 查询历史训练数据
    acute_load = db.query("""
        SELECT SUM(rpe * duration_minutes) 
        FROM training_sessions 
        WHERE user_id = ? AND date >= DATE('now', '-7 days')
    """, user_id) + (new_session_rpe * new_session_minutes)
    
    chronic_load = db.query("""
        SELECT SUM(rpe * duration_minutes) / 4.0
        FROM training_sessions 
        WHERE user_id = ? AND date >= DATE('now', '-28 days')
    """, user_id)
    
    acwr = acute_load / chronic_load if chronic_load > 0 else 1.0
    
    if acwr > 1.5:
        risk = "high"  # Evaluator 必须驳回
    elif acwr > 1.3:
        risk = "moderate"  # Evaluator 应警告
    else:
        risk = "safe"
    
    return {"acwr": round(acwr, 2), "risk": risk}
```

### 2. 训练周报自动生成（留存利器）

这是 ChatGPT 建议的，商业化价值最高：

每周日晚，后台定时任务：
```
输入: 本周训练记录 + 饮食日志 + 睡眠数据 + 体重变化
输出: 
  - 本周训练完成率: 4/5 (80%)
  - 力量变化: 卧推 70kg→72.5kg (+3.6%)
  - 体重趋势: 65kg→64.5kg (-0.5kg, 符合减脂进度)
  - 建议: 蛋白质摄入偏低(日均1.2g/kg→建议提升至1.6g/kg)
  - 下周预测: 若保持当前节奏, 预计4周后体脂降至16%
```

### 3. 可协商计划 (Human-in-the-Loop)

ChatGPT 提出的这个特性非常加分：

```
Agent 生成计划 → 用户说"卧推我不想练" 
→ Agent: "收到, 替换为器械推胸。还有其他想调整的吗？"
→ 用户修改后确认 → Agent 更新计划并保存

```

### 4. 数据可视化设计（"我的"页面）

```
┌─────────────────────────────────────────┐
│  👤 用户卡片                             │
│  175cm | 64kg | 17%体脂 | 减脂期         │
├─────────────────────────────────────────┤
│  📊 体重变化 (折线图)                     │
│  66kg ─╲                                │
│         ╲                               │
│  64kg ───╲______                        │
│          5/1   5/15   5/31              │
├─────────────────────────────────────────┤
│  💪 力量成长 (多线折线图)                  │
│  卧推 ───/\/\/── (上升趋势)              │
│  深蹲 ────── (持平)                       │
│  硬拉 ──/\/─── (小幅上升)                 │
├─────────────────────────────────────────┤
│  🔥 训练热力图 (GitHub 贡献图样式)         │
│  一 二 三 四 五 六 日                     │
│  ██░░██░░░█  5月第1周                    │
│  █████░░███  5月第2周                    │
│  ░██░█░░░░█  5月第3周                    │
│  ███████░░█  5月第4周                    │
├─────────────────────────────────────────┤
│  🍽️ 本周饮食概览                          │
│  日均: 2100kcal | 蛋白145g | 碳水220g     │
└─────────────────────────────────────────┘
```

---

## 八、多模态饮食识别

```
用户拍照 → 前端压缩至 512px
    │
    ▼
VLM (GPT-4o / Gemini) → 识别: "200g米饭 + 150g鸡胸肉 + 50g西兰花"
    │
    ▼
计算: 200g米饭(260) + 150g鸡胸肉(248) + 50g西兰花(17) = 525kcal, 54g protein
    │
    ▼
生成 DietCard (json-render) → 显示给用户确认
    │
    ▼
用户确认/修正 → 写入 diet_records 表
```

---

## 九、技术栈终选

| 层 | 选型 | 理由 |
|----|------|------|
| **前端** | React Native + Expo | 你熟悉 JS/TS (CARdle 前端用的 Vite+React)，RN 生态成熟，json-render 原生支持 |
| **聊天 UI** | `react-native-gifted-chat` | 开箱即用的聊天界面，支持自定义消息气泡 |
| **图表** | `victory-native` | 比 react-native-chart-kit 更灵活，支持动画 |
| **本地存储** | `expo-sqlite` / `watermelondb` | 训练页离线可用，联网后同步 |
| **后端** | FastAPI + LangGraph | 直接复用 CARdle 的技术栈和代码模式 |
| **Agent 编排** | LangGraph + PostgresSaver | StateGraph + Conditional Edge + Checkpoint |
| **记忆系统** | Mem0 (自托管) | Apache 2.0 开源，Python SDK 极简接入 |
| **向量数据库** | pgvector | PostgreSQL 扩展，不引入新基础设施 |
| **数据库** | PostgreSQL | 用户数据 + 训练记录 + 饮食 + Checkpoints 全在这 |
| **缓存** | Redis | 会话状态 + 配额计数 + 热点数据 |
| **搜索** | Tavily Search API | 动作图示 + 最新健身研究 |
| **视觉模型** | GPT-4o / Gemini 1.5 Pro | 食物识别 + 体型分析 |
| **推理模型** | Claude Sonnet 4.5 / GPT-4o | 训练计划生成 + Self-Reflection |
| **轻量模型** | GPT-4o-mini / Haiku | 意图分类 + 信息提取 + 闲聊 |
| **RAG 嵌入** | BGE-M3 | Tesla 项目已验证，中英双语效果好 |
| **认证** | Supabase Auth | 开箱即用，支持 Google/Apple 登录 |
| **支付** | Stripe + 支付宝 | 会员订阅 |
| **监控** | Langfuse + Sentry | LLM 可观测性 + 错误追踪 |
| **部署** | Docker Compose → K8s | 渐进式部署 |

---

## 十、分阶段开发路线图

### Phase 1: 核心骨架（第 1-2 周）— **面试可聊**

```
功能:
  ✅ FastAPI 后端骨架 + SSE 流式
  ✅ JWT 认证 (Supabase Auth)
  ✅ React Native 聊天界面 (gifted-chat)
  ✅ 单 Agent 基础对话 (带 Profile 注入)
  ✅ PostgreSQL 数据库 + 基础表结构

目标: 一个能聊天的健身 APP，后端代理所有 LLM 请求
  
可讲点:
  - 为什么用 SSE 流式而不是客户端直连
  - JWT + API Gateway 的安全架构
  - 为什么选择 React Native (跨平台 + 生态)
```

### Phase 2: 记忆系统（第 3-4 周）— **面试核心亮点**

```
功能:
  ✅ Mem0 集成 → 用户画像自动提取与更新
  ✅ Memory Agent → 静默提取 + 冲突消解 + 纠错
  ✅ 用户信息分层存储 (Profile + Metrics + Events)
  ✅ 7天上下文窗口 + 周压缩定时任务

目标: Agent 能记住用户的身高体重、训练水平、伤病、目标
  
可讲点:
  - 为什么用 Mem0 而不是文件存储
  - 分层记忆架构设计 (4 层)
  - 时序冲突消解策略 (如何知道用户现在的体重是 64kg 而不是 66kg)
  - 记忆压缩策略 (7天事件 → 周摘要)
```

### Phase 3: Multi-Agent + Plan-and-Execute（第 5-6 周）— **面试最强点**

```
功能:
  ✅ LangGraph StateGraph 完整编排
  ✅ Supervisor Router → 4 个 Agent 路由
  ✅ Coach Agent: Plan → Execute → Evaluate → Correct
  ✅ Search Agent: Tavily 动作图示搜索
  ✅ json-render 训练卡片 (WorkoutCard)
  ✅ RAG 知识库: NCSA pdf → pgvector
  ✅ ACWR 负荷算法集成

目标: 生成一份经过 Self-Reflection 审查的专业训练计划卡片
  
可讲点:
  - 为什么用 Supervisor 路由 (不是 Peer-to-Peer)
  - Plan-and-Execute 为什么比 one-shot 好
  - Self-Reflection 的具体审查维度 (肌群平衡/CNS负荷/伤病/ACWR)
  - 运动生理学 RAG 知识库的构建与检索
  - json-render vs A2UI 的选型理由
  - ACWR 算法的运动科学依据
```

### Phase 4: 饮食 + 训练页 + 我的页（第 7-8 周）— **产品完整度**

```
功能:
  ✅ Diet Agent: VLM 食物识别 + USDA API 校准
  ✅ DietCard 交互卡片
  ✅ 训练页: 训练计划展示 + 动作打勾
  ✅ 我的页: 体重/力量折线图 + 训练热力图
  ✅ Human-in-the-Loop: 计划修改协商
  ✅ 本地优先: 训练页离线可用 (expo-sqlite)

目标: 一个完整可用的 MVP 产品
  
可讲点:
  - 多模态 + API 校准的双层架构 (为什么不用 VLM 直接估算热量)
  - Local-first 架构: 离线记录 + 联网同步
  - Human-in-the-Loop 协商模式
```

### Phase 5: 商业化 + 打磨（第 9-10 周）— **面试 + 上线**

```
功能:
  ✅ Stripe 支付集成
  ✅ 用户配额系统
  ✅ 训练周报自动生成 (定时任务)
  ✅ 主动提醒推送 (FCM)
  ✅ Docker Compose 一键部署
  ✅ 端到端测试 + LLM 输出评估
  ✅ 项目文档 + 架构图 + README

目标: 一个可以上架 + 可以面试深度讲解的完整产品
  
可讲点:
  - 商业化架构 (freemium + 会员订阅)
  - 成本控制 (轻量模型 + 缓存 + Prompt Cache)
  - LLM 输出质量的评估体系
```

### Phase 6: 杀手锏功能（第 11-12 周）— **降维打击**

```
功能 (选 1-2 个):
  □ Apple HealthKit / Google Fit 集成
  □ 体型预测 (基于当前数据预测 3 个月后体型)
```

---

## 十三、相对于四份 AI 反馈，我补充的独特内容

### 它们都没注意到或没说透的点：

1. **具体的数据表 Schema 设计** — 四个 AI 都说"用 PostgreSQL 存用户信息"，但没人给出具体的表结构。我给了 7 张核心表 + JSONB 灵活字段方案。

2. **LangGraph StateGraph 的节点级设计** — 没人画出具体的 Node 和 Edge。我给出了从 Intent Classifier → Planner → Executor → Evaluator → Corrector → Response Builder 的完整状态流转。

3. **你的 Obsidian 笔记作为 RAG 原材料** — 四个 AI 都不知道你有 20+ 篇系统化的运动生理学笔记。这是你的独有壁垒，我把它设计成了项目的核心差异化。

4. **训练计划的完整生成流程示例** — 从"左肩不舒服想练胸肩"到最终卡片输出的每一步，让面试官能直观感受到系统的智能程度。

5. **成本估算与商业化定价** — ChatGPT 提了商业化方向，但没有给具体数字。我给了月度成本 ¥450-1150 和阶梯定价方案。

6. **CARdle 技术栈复用路径** — 四个 AI 不知道你刚完成 CARdle。我设计的后端架构（FastAPI + LangGraph + Redis + PostgreSQL）直接复用 CARdle 的技术选型，开发速度翻倍。

7. **面试 10 个追问的完整回答** — 不仅准备了项目介绍，还预判了面试官会追问的 10 个技术深挖问题。

8. **分阶段路线图的具体时间规划** — 以周为单位的 12 周路线图，每周有明确的"可讲点"，确保面试时任何阶段停下来都有料可讲。

9. **四个 AI 的分歧点对比表** — 让你清楚地看到哪些建议是一致的（必须听），哪些是有分歧的（需要你判断）。

10. **80/20 判断** — 核心 20% 是 Phase 1-3（骨架+记忆+Multi-Agent），这 6 周的工作能让你在面试中讲 80% 的内容。Phase 4-6 是商业化和锦上添花。

---

## 附录：关键决策速查

| 决策 | 推荐 | 备选 |
|------|------|------|
| 前端框架 | React Native | Flutter (如果你有时间学 Dart) |
| Agent 编排 | LangGraph Supervisor | AutoGen (太重) |
| 记忆系统 | Mem0 (自托管) | 手写分层记忆 (不够工业级) |
| 生成式 UI | json-render-react-native | 自定义 JSON Schema (也行) |
| 向量库 | pgvector | Milvus (太重) |
| 视觉模型 | GPT-4o | Gemini 1.5 Pro (便宜) |
| 推理模型 | Claude Sonnet 4.5 | GPT-4o (生态更好) |
| 轻量模型 | GPT-4o-mini | Claude Haiku (更便宜) |
| 认证 | Supabase Auth | Clerk (更贵) |
| 支付 | Stripe + 支付宝 | Lemon Squeezy (更简单) |
| 是否写清楚每一个决策的 "为什么" | 是 | — |
