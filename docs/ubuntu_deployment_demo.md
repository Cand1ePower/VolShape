# VolShape Ubuntu Demo Deployment

目标：把 VolShape 部署到 Ubuntu 服务器，使用 Docker Compose 提供后端 API、PostgreSQL、Redis、静态演示页、API 文档入口，以及可下载的 Android APK。

## 当前结论

当前项目不建议直接“无准备无损上云”，但已经具备低风险上云条件。上云前必须处理：

- 使用 PostgreSQL/Redis 生产实例，不能依赖本地 SQLite。
- 后端 `.env` 必须换成生产密钥，尤其是 `AUTH_JWT_SECRET`、`TOKEN_ENCRYPTION_SECRET`、New API、Langfuse、FatSecret、视觉模型 Key。
- 前端必须通过 `EXPO_PUBLIC_API_BASE_URL` 指向公网 HTTPS API。
- Nginx 需要关闭 `/api/chat/stream` 这类 SSE 接口的 buffering。
- APK 下载需要静态目录托管。

## 推荐域名

建议使用：

- `https://volshape.candlepower.cool`：VolShape 后端 API + 演示页 + APK 下载
- `https://api.candlepower.cool`：继续保留给 New API 网关

如果暂时没有 DNS，可以先用服务器 IP 调试后端，但 APK/网页正式演示建议使用 HTTPS 域名。

## 服务器准备

```bash
sudo apt update
sudo apt install -y git nginx certbot python3-certbot-nginx python3.12-venv docker.io docker-compose-plugin
sudo systemctl enable --now docker nginx
```

创建目录：

```bash
sudo mkdir -p /opt/volshape /var/www/volshape /var/www/volshape-downloads /var/www/certbot
sudo chown -R ubuntu:ubuntu /opt/volshape /var/www/volshape /var/www/volshape-downloads
```

## 部署代码

```bash
cd /opt/volshape
git clone <your-repo-url> .
```

如果用手动上传代码，也保持最终目录结构为：

```text
/opt/volshape/backend
/opt/volshape/frontend
/opt/volshape/deploy
```

## Docker Compose 一键部署

生产部署优先使用 Docker Compose：

```bash
cd /opt/volshape/deploy
docker compose -f docker-compose.prod.yml --env-file ../backend/.env up -d --build
```

服务包括：

- `db`: PostgreSQL 16 + pgvector
- `redis`: Redis 7
- `backend`: FastAPI + Alembic 自动迁移
- `nginx`: 静态演示页、APK 下载、API 反代、SSE 透传

## 后端环境变量

```bash
cd /opt/volshape/backend
cp .env.example .env
nano .env
```

生产关键项：

```bash
ENV=production
DATABASE_URL=postgresql+asyncpg://postgres:<strong-password>@localhost:5432/volshape
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=https://volshape.candlepower.cool
AUTH_JWT_SECRET=<long-random-secret>
TOKEN_ENCRYPTION_SECRET=<another-long-random-secret>
NEWAPI_BASE_URL=https://api.candlepower.cool
NEWAPI_ACCESS_TOKEN=<new-api-admin-token>
NEWAPI_USER_ID=1
LANGFUSE_PUBLIC_KEY=<pk-lf-...>
LANGFUSE_SECRET_KEY=<sk-lf-...>
LANGFUSE_HOST=https://cloud.langfuse.com
```

生成随机密钥：

```bash
openssl rand -hex 32
```

## 手动安装后端依赖

仅当不使用 Docker 时才需要手动安装 Python 依赖。

Docker 后端容器启动时会执行：

```bash
alembic upgrade head
```

如果迁移失败，可查看后端容器日志：

```bash
cd /opt/volshape/deploy
docker compose -f docker-compose.prod.yml logs -f backend
```

## systemd 后端服务

仅当不使用 Docker 后端容器时使用：

```bash
sudo cp /opt/volshape/deploy/systemd/volshape-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now volshape-backend
sudo systemctl status volshape-backend
```

查看日志：

```bash
journalctl -u volshape-backend -f
```

## Nginx 与 HTTPS

先确保 DNS 已经把 `volshape.candlepower.cool` 指到服务器 IP。

```bash
sudo cp /opt/volshape/deploy/nginx/volshape.conf /etc/nginx/sites-available/volshape.conf
sudo ln -sf /etc/nginx/sites-available/volshape.conf /etc/nginx/sites-enabled/volshape.conf
sudo nginx -t
sudo systemctl reload nginx
```

申请证书：

```bash
sudo certbot --nginx -d volshape.candlepower.cool
```

## 静态演示页

```bash
cp /opt/volshape/deploy/site/index.html /var/www/volshape/index.html
```

访问：

```text
https://volshape.candlepower.cool
```

## 构建 Android APK

本地或服务器都可以构建。推荐用 EAS 云构建：

```bash
cd frontend
npm install
npx eas-cli@latest login
npx eas-cli@latest init
EXPO_PUBLIC_API_BASE_URL=https://volshape.candlepower.cool npx eas-cli@latest build -p android --profile preview
```

构建完成后下载 APK，并上传到服务器：

```bash
scp VolShape-preview.apk ubuntu@101.43.140.191:/var/www/volshape-downloads/VolShape-preview.apk
```

下载地址：

```text
https://volshape.candlepower.cool/downloads/VolShape-preview.apk
```

## 本地验证命令

后端：

```bash
curl https://volshape.candlepower.cool/health
```

评测：

```bash
cd /opt/volshape/backend
. .venv/bin/activate
python evals/run_evals.py --strict
pytest tests/test_prompt_versions.py tests/test_evals.py tests/test_media_analysis.py -q
```

## 回滚

```bash
cd /opt/volshape
git log --oneline -5
git checkout <previous-commit>
cd backend
. .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart volshape-backend
```

## 面试演示顺序

1. 打开演示页，说明这是线上部署入口。
2. 展示 APK 下载。
3. 登录 App，演示快速/专家模式。
4. 展示用户记忆、训练历史、多会话。
5. 上传饮食图片，展示营养卡片与持久化。
6. 打开 Langfuse，展示 trace。
7. 运行 eval，说明 prompt 版本管理和回归测试。
