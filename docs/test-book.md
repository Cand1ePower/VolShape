# VolShape 测试说明书

## 测试目标

本测试体系面向 AI 应用工程师面试展示，重点证明项目不是“只能跑 demo”，而是具备：

- 账号系统正确性
- 多用户额度治理
- New API 网关失败可观测性
- LLM 显式错误链路
- 分层记忆写入与压缩
- LangGraph workflow 可测性
- 支付/订阅入口基本契约

## 测试环境

测试入口：

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

测试环境变量：

```python
TESTING=1
```

测试数据库：

- 使用 SQLite 内存数据库。
- `tests/conftest.py` 在测试 session 开始时创建全部 SQLAlchemy 表。
- 测试结束后 drop 全部表。

注意：测试环境不会通过 New API 创建真实 token。

## 当前测试文件

### `tests/test_auth_quota.py`

覆盖账号系统和额度系统。

用例：

- `test_register_login_refresh_and_me`
  - 注册用户
  - 登录获取 access token 和 refresh token
  - 调用 `/api/auth/me`
  - 验证默认 free quota
  - 刷新 access token

- `test_duplicate_register_returns_conflict`
  - 相同 email 重复注册应返回 409。

- `test_free_user_cannot_use_detailed_mode`
  - free 用户使用专家模式应被拒绝。

- `test_daily_message_limit_is_enforced`
  - 连续累加 10 次消息后，free 用户第 11 次请求应返回 429。

工程价值：

- 证明账号系统不再依赖 MVP 测试 user。
- 证明 quota policy 真正参与业务判断。

### `tests/test_error_handling.py`

覆盖显式错误链路。

用例：

- `test_llm_empty_response_is_explicit_error`
  - mock LLM 返回空内容。
  - 断言抛出 `LLMEmptyResponseError`。
  - 避免空内容被当成成功回复。

- `test_newapi_token_provision_error_is_typed`
  - mock 无共享 token 且无法自动创建 New API token。
  - 断言抛出 `NewApiProvisionError`。

- `test_live_agent_stream_emits_structured_error`
  - mock LangGraph workflow 中途失败。
  - 断言 SSE 返回 `event: error`。
  - 断言错误 payload 包含 `code/message/retryable`。
  - 断言流最终发送 `done`，前端可以收尾 UI 状态。

工程价值：

- 解决之前 `"已为您准备好！"` 这种假成功问题。
- 证明模型网关错误会显式暴露，而不是被 fallback 静默吞掉。

### `tests/test_chat.py`

覆盖基础服务和聊天鉴权。

用例：

- 根路径健康检查。
- 未授权访问 `/api/chat/stream` 返回 401。
- development bypass token 可以进入 SSE。

工程价值：

- 验证 chat stream 基础契约。
- 验证本地开发调试路径。

### `tests/test_memory.py`

覆盖分层记忆。

用例：

- LLM 抽取后的画像/指标写入。
- 体重冲突以时序指标追加。
- episodic events 压缩为 weekly summary。
- 伤病新增与恢复删除。

工程价值：

- 保持“LLM 总结提取”为核心，不走硬编码规则抽取。
- 验证 Layer 1/2/3/4 的写入和读取闭环。

### `tests/test_workflow.py`

覆盖 LangGraph workflow。

当前策略：

- workflow 测试使用 deterministic mock LLM。
- 不依赖真实模型输出稳定性。
- 真实模型质量应进入 evals，而不是单元测试。

用例：

- workflow 可编译。
- 普通训练需求可走完整图。
- 带伤病画像时，workflow 可完成安全链路。

工程价值：

- 区分“业务图逻辑测试”和“模型质量评估”。
- 避免真实 LLM 返回截断 JSON 导致测试不稳定。

### `tests/test_payment.py`

覆盖支付和周报。

用例：

- free/vip quota 查询。
- checkout session mock URL 生成。
- weekly report HTML 渲染。

工程价值：

- 验证订阅入口契约。
- 验证用户报告展示链路。

### `tests/test_diet.py`

覆盖饮食记录相关功能。

工程价值：

- 确保饮食业务和用户鉴权/记忆体系并行可用。

## 新增错误链路测试设计

### 结构化错误格式

后端错误 payload：

```json
{
  "code": "llm_gateway_failed",
  "message": "模型服务暂时不可用，我已停止本次处理以避免生成不可靠结果。",
  "retryable": true,
  "details": {
    "error_type": "InternalServerError"
  }
}
```

前端处理：

- SSE `error` event 解析 JSON。
- bot 气泡显示用户可读 message。
- 附带错误码，方便调试和截图展示。

## 推荐继续补的测试

### P0 后续

- `test_chat_stream_llm_failure_does_not_save_fake_success`
  - 确认数据库不会保存 `"已为您准备好！"`。

- `test_memory_extraction_failure_is_observable`
  - LLM 记忆抽取失败时，至少记录 warning/error metadata。

- `test_newapi_token_provision_success_with_mocked_api`
  - mock `/api/token/`、`/api/token/?p=...`、`/api/token/{id}/key`。
  - 验证本地保存 encrypted token。

### P1 Eval 体系

单元测试不应该评价模型“答得好不好”。建议单独建立 `evals/`：

- 记忆抽取准确率
- 意图分类准确率
- 训练计划安全性
- 多轮记忆一致性
- 危险建议拒绝率

## 面试讲法

可以这样解释：

> 我把 LLM 应用测试分成三层：第一层是传统工程测试，覆盖 auth、quota、DB、SSE、错误链路；第二层是 deterministic mock workflow 测试，验证 LangGraph 编排逻辑；第三层是 evals，用真实模型跑数据集和 rubric，评估语义质量。这样既保证 CI 稳定，也能持续评估 AI 能力。
