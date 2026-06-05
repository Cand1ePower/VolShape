# VolShape Progress Log

最后更新：2026-06-04

## 项目总体状态

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 账号体系 | 已完成核心闭环 | 注册、登录、刷新令牌、鉴权、用户态恢复可用 |
| 套餐与额度 | 已完成核心闭环 | Free / Pro / Premium 与 New API 额度控制已打通 |
| 聊天工作流 | 已完成核心闭环 | 快速 / 专家双模式、SSE、显式错误链路可用 |
| 多层记忆 | 已完成核心闭环 | profile / metrics / events / mem0 已接入 |
| 训练上下文 | 已完成核心闭环 | 能注入计划组数与实际完成组数 |
| 多会话系统 | 已完成核心闭环 | 历史加载、列表、置顶、删除、最后会话恢复已完成 |
| Langfuse | 基础可用 | 已有 trace，仍需补 provider / prompt / fallback 维度 |
| 数据库迁移 | 基础可用 | Alembic baseline 已就位，后续要继续收口 |
| MCP 多模态层 | 规划完成，开始实现 | 当前进入 Gateway / Factory 骨架阶段 |

## 本阶段新增结论

### 成本策略

当前阶段不采用“月订阅优先”，而采用：

- 免费额度优先
- 按次计费优先
- 本地零边际成本优先
- 试用型供应商仅作备用 / demo 通道

### 当前选型结论

| 场景 | 主方案 | 备用方案 | 备注 |
| --- | --- | --- | --- |
| 饮食文字 | LLM 解析 + FatSecret | Edamam | 以 FatSecret 免费计划为主 |
| 食物照片 | New API 多模态 + FatSecret | LogMeal / YMove | 优先按次计费，不先订阅 |
| 训练视频 | MediaPipe 本地分析 + LLM | QuickPose / YMove | 零边际成本最适合当前阶段 |

## 已完成的重要里程碑

### 2026-06-03

- 完成正式账号体系替换 MVP 测试账号
- 打通 Free / Pro / Premium 套餐与额度逻辑
- 修复聊天历史加载与多会话恢复
- 完成会话列表、置顶、删除与最后会话恢复
- 修复键盘动画与输入栏抖动问题
- 补强训练上下文：计划组数与实际完成组数可回灌
- 补齐一批 auth / chat / memory / workflow / migration 测试

### 2026-06-04

- 明确 MCP 扩展不走“多供应商直连模型”的路线
- 确定采用 `MCP Gateway + Factory` 方案
- 把多模态能力收敛为 3 个稳定能力接口
- 将成本策略正式调整为 `credit-first`

## 当前进行中

1. 重写执行版路线图
2. 新增进度日志文档
3. 搭建 MCP 工厂层基础骨架

## 下一步

1. 落地 `backend/app/services/mcp/`
2. 先做 provider catalog 与 factory
3. 接入 `nutrition_text.analyze`
4. 再接 `nutrition_photo.analyze`
5. 为 provider selection 补 Langfuse 埋点和测试

## 当前风险

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 外部营养 API 免费资格申请存在时间差 | 可能影响主链路上线速度 | 先用 LLM + 本地结构化结果演示，再补正式 nutrition adapter |
| 视频姿态分析如果直接上商用 SaaS 成本高 | 不利于低频面试项目 | 先用 MediaPipe 本地链路 |
| 多供应商接入容易让 workflow 变复杂 | 可维护性下降 | 统一收口到 Gateway / Factory |
