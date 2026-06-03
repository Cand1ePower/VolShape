# 数据库 Schema 与迁移说明

## 当前数据库结构

VolShape 当前使用 SQLAlchemy ORM 定义 schema，核心模型在 `backend/app/database/models.py`。开发环境优先尝试 PostgreSQL，连接失败时会 fallback 到本地 SQLite 文件；测试环境使用 SQLite 内存库。

当前表可以按领域分为 5 组：

### 账号与认证

- `app_users`：正式用户账号。保存 email、username、password_hash、role、status、登录时间等。
- `auth_identities`：第三方身份预留表。通过 `provider + provider_subject` 唯一约束支持 OAuth/外部身份绑定。
- `auth_sessions`：刷新令牌会话表。保存 refresh token hash、设备信息、过期时间、吊销时间。

设计意图：把“账号系统”从原 MVP 的测试 user_id 中拆出来，后续所有业务表通过 `user_id` 关联真实用户。

### 订阅、额度与审计

- `subscriptions`：用户订阅状态。字段包括 tier、status、provider、当前周期、是否周期结束取消。
- `user_quota_policies`：不同 tier 的额度策略。包含每日消息数、月度 quota、允许模型、上下文限制、功能开关。
- `user_usage_daily`：用户每日使用聚合。记录消息数、prompt tokens、completion tokens、quota_used。
- `llm_requests`：每次模型调用明细。记录模型、状态、token 用量、延迟、错误码、request_id。
- `audit_logs`：管理/安全审计预留。

设计意图：面向多用户 AI 产品，需要把“是否能用”“用了多少”“为什么失败”都持久化，支撑计费、限流和监控。

### New API 网关

- `newapi_tokens`：VolShape 用户与 New API token 的绑定。真实 token 加密保存为 `token_ciphertext`，同时缓存 New API token id、group、模型限制和额度。

设计意图：每个 App 用户拥有可单独监控和限制的 New API token，避免所有请求共用一个不可追踪的系统 key。

### 分层记忆系统

- `user_profile`：Layer 1，慢变化核心画像。身高、性别、目标、训练年限、伤病、医疗情况。
- `user_metrics`：Layer 2，动态时序指标。体重、体脂、PR 等按时间追加。
- `events`：Layer 3，事件流水。训练、饮食、睡眠、伤病、note 等近期事件。
- `weekly_summaries`：Layer 4，压缩后的周摘要。用于长期语义记忆和减少上下文膨胀。

设计意图：保留 LLM 总结式记忆抽取，但存储层分清“长期画像”“时序指标”“短期事件”“压缩摘要”，方便检索和冲突处理。

### 训练与饮食业务

- `training_plans`：训练计划卡片和完成状态。
- `diet_records`：饮食记录、宏量营养和图片 URL。
- `conversation_messages`：聊天历史，支持保存普通文本和带 UI card 的 assistant 消息。

## 当前 schema 演进方式

现在项目在启动时调用：

```python
Base.metadata.create_all
```

这适合 MVP 和测试环境，但不适合生产演进。原因：

1. `create_all` 只会创建不存在的表，不会可靠地修改已有表结构。
2. 删除字段、改字段类型、加索引、改约束，都需要显式迁移。
3. 多人协作和部署时，需要知道“数据库现在处于哪个版本”。
4. 面试时，schema 演进是后端工程成熟度的关键问题。

## 什么是 Alembic

Alembic 是 SQLAlchemy 官方生态里的数据库迁移工具。它做三件事：

1. 记录数据库 schema 版本。
2. 把 ORM 模型变化生成 migration 脚本。
3. 在不同环境执行 `upgrade` / `downgrade`，让数据库结构可重复演进。

典型命令：

```bash
alembic init migrations
alembic revision --autogenerate -m "add auth and quota tables"
alembic upgrade head
alembic downgrade -1
```

## 为什么本项目需要迁移

VolShape 已经从 MVP 进入“真实 AI 应用工程”阶段，数据库包含：

- 账号系统
- 订阅与额度
- LLM 请求审计
- New API token 绑定
- 分层记忆
- 训练/饮食业务

这些表后续一定会继续变化，例如：

- 给 `llm_requests` 增加 `prompt_version`
- 给 `events` 增加索引
- 给 `subscriptions` 增加支付订单 id
- 给 `newapi_tokens` 增加 token 轮换字段
- 给 `conversation_messages` 增加 error metadata

没有 Alembic 时，每次上线都只能靠 `create_all` 或人工改库，风险很高。

## 推荐落地方案

短期保留测试环境 `create_all`，生产和开发主库引入 Alembic：

1. 初始化 Alembic。
2. 生成当前全量 schema 的 baseline migration。
3. 新增 CI 检查 migration 是否可执行。
4. 后续所有模型变更都先写 migration，再改代码。

推荐目录：

```text
backend/
  alembic.ini
  migrations/
    env.py
    versions/
```

推荐规则：

- SQLite 只作为本地开发 fallback。
- PostgreSQL 作为生产标准数据库。
- 测试继续使用 SQLite 内存库，但重要查询需要覆盖 PostgreSQL 兼容性。
