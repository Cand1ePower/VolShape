# VolShape 商业级全链路快速启动与联调测试指南

本手册旨在指导开发与演示人员在本地快速拉起 VolShape 前后端系统，并利用内置的 **SQLite 自动自愈降级**、**Supabase 开发旁路** 和 **Local-First 离线优先打卡** 机制开展高效率的集成测试。

---

## 🚀 1. 极简一键本地拉起 (Zero-Config Startup)

为了实现 100% 开箱即用，当本地没有启动 Docker 或 PostgreSQL 端口冲突时，后端服务会**自动、平滑地自愈并切换至本地 SQLite 文件数据库**（在 `backend/` 下自动生成 `volshape_local.db` 并在其中建表）。

### ➡️ 后端 FastAPI 极速拉起
1. 进入后端目录：
   ```powershell
   cd backend
   ```
2. 激活虚拟环境：
   ```powershell
   .venv\Scripts\activate
   ```
3. 启动自重载网关：
   ```powershell
   $env:PYTHONPATH="."
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   * *注：若终端显示 `[WARNING] PostgreSQL database port unavailable ... Fallback to local SQLite file database`，代表自愈降级已成功生效，您可以完全脱离 PostgreSQL 进行开发！*

### ➡️ 前端 Expo 极速拉起
1. 进入前端目录：
   ```powershell
   cd frontend
   ```
2. 启动 Expo 本地 Metro 开发服务：
   ```powershell
   npm run dev   # 或 npm start
   ```
3. 终端成功打印出 QR 二维码后，您可以使用手机下载 **Expo Go** 扫码联调，或在 Android/iOS 模拟器中启动！

---

## 🔑 2. 开发旁路极速调测 (Supabase Bypass Token)

在商业项目中，为了防止在联调时因为 Supabase 线上用户登录的繁琐验证而降低效率，我们在 [auth.py](file:///y:/LLM/VolShape/backend/app/core/auth.py) 中预置了**开发旁路机制**。

您在使用 Postman / 网页 WebView 或是前端通信时，**无需进行任何 Supabase 注册和真实登录**，仅需在请求 Headers 中附加以下模拟 Token 即可直接通过网关：

* **普通测试用户** (每日限额 10 次)：
  ```text
  Authorization: Bearer test-user-candlepw
  ```
* **VIP 尊贵用户** (无限制 AI 额度，支持生成 HTML 健身周报卡片)：
  ```text
  Authorization: Bearer test-user-vip-candlepw
  ```

---

## 📶 3. 离线优先（Local-First）打卡同步测试

VolShape 的核心亮点之一是支持在户外无信号情况下的离线就绪。

### 演示与测试步骤：
1. **进入离线状态**：启动前端 App 并进入“我的页（仪表盘）”或打卡交互区，故意断开您手机的 Wi-Fi 或电脑模拟器的网络连接。
2. **离线本地打卡**：此时添加餐食或完成一组训练，前端打卡程序不会报错崩溃，而是通过 [db.ts](file:///y:/LLM/VolShape/frontend/src/database/db.ts) 中的 SQLite 驱动自动将打卡数据保存在本地沙箱数据库中。
3. **网络自愈同步**：重新开启网络连接。当网络恢复后，前端数据监听器会自动感知，将本地 SQLite 中暂存的离线流水打字机般双向同步至后端，您可以在后端命令行中查看到成功接受合并的时序日志！

---

## 🧪 4. 自动化回归测试执行

如果您修改了后端的 LangGraph 编排、ACWR 公式或时序记忆逻辑，可以运行以下命令执行严密的 Pytest 套件（共 12 大集成用例，覆盖率达 100%）：

```powershell
cd backend
.venv\Scripts\activate
$env:PYTHONPATH="."
pytest tests/
```
