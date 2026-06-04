# 双色球 AI V6.0

这是一个合并版双色球数据分析、历史抓取、缩水过滤和 AI 排序系统。

当前仓库主线采用：

- FastAPI 后端
- PostgreSQL / SQLite
- Vue3 管理后台
- Docker / Docker Compose
- 中彩网历史开奖分页抓取
- AI v6 确定性候选池枚举排序

本系统是“数据分析 + 缩水排序工具”，不是预测器，不承诺命中结果。

## 核心能力

- 同步中彩网双色球历史开奖分页数据
- 保留中国福彩网接口同步作为备选数据源
- 自动建表并写入 `draws`
- 最近开奖和数据统计
- 排除历史已开号码
- 支持强历史排除：排除与任意历史红球 `5+` 重合的组合
- 支持排除号码、胆码、杀尾、和值、跨度、奇偶、AC、重号、连号等规则
- AI v6 评分项：
  - 近30期热号
  - 近100期中期热号
  - 冷号回补
  - 奇偶结构
  - 三区结构
  - 和值
  - 跨度
  - 连号
  - AC值
  - 同尾
  - 上期重号
- Vue3 中文管理后台
- Docker 一键部署

## 本地 Docker 启动

```bash
docker compose up --build
```

访问：

```text
http://localhost:8000
```

首次进入后台后点击“同步历史开奖”，再点击“AI评分 Top50”。

## 本地 SQLite 开发模式

Windows PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1
```

访问：

```text
http://localhost:8000
```

停止：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\stop-local.ps1
```

## 后端开发

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
DATABASE_URL=sqlite:///../ssq.db SCHEDULER_ENABLED=false .venv/bin/uvicorn app.main:app --reload
```

## 前端开发

```bash
cd frontend
npm install
npm run dev
```

前端开发服务默认代理 `/api` 到 `http://localhost:8000`。

## API

- `GET /api/health`
- `GET /api/stats`
- `GET /api/draws?limit=30`
- `POST /api/sync?source=zhcw`
- `POST /api/sync?source=cwl&issue_count=3000`
- `POST /api/generate`

## 免费云端部署

### Render

仓库已包含 `render.yaml`。Render 当前仍提供免费 Web Service，但免费 Postgres 数据库有 30 天过期限制，请留意平台邮件提醒。

步骤：

1. 将本仓库推送到 GitHub。
2. 登录 Render。
3. 选择 New -> Blueprint。
4. 选择本仓库。
5. Render 会读取 `render.yaml` 创建：
   - `ssq-v6` Web Service
   - `ssq-v6-db` Free Postgres
6. 部署完成后打开 Web Service URL。
7. 点击“同步历史开奖”导入历史库。

### Koyeb

Koyeb 支持从 GitHub 仓库或 Dockerfile 部署，并提供免费 Web Service 和免费 Postgres 类型。创建服务时选择本仓库，使用 Dockerfile 构建，并设置环境变量：

```text
DATABASE_URL=<你的 Koyeb Postgres 连接串>
SCHEDULER_ENABLED=false
AUTO_SYNC_ON_STARTUP=false
AUTO_SYNC_SOURCE=zhcw
CORS_ORIGINS=*
```

部署完成后同样在页面点击“同步历史开奖”。

## 环境变量

```text
DATABASE_URL=postgresql+psycopg2://ssq:ssq@localhost:5432/ssq
FETCH_ISSUE_COUNT=3000
AUTO_SYNC_ON_STARTUP=false
AUTO_SYNC_SOURCE=zhcw
SCHEDULER_ENABLED=true
SCHEDULER_CRON=0 22 * * tue,thu,sun
CORS_ORIGINS=*
```

## GitHub 同步建议

本地 `ssq_ai.sqlite3`、`ssq.db`、`.venv`、`generated_numbers.csv` 都不会提交。云端使用 PostgreSQL 持久化数据。
