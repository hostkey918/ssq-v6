# 双色球 V6.0 系统

基于 FastAPI、PostgreSQL、Vue3、APScheduler 的双色球历史开奖同步、过滤、AI评分和 Web 管理后台。

## 功能

- 自动抓取双色球历史开奖并入库
- PostgreSQL 持久化存储
- 排除历史已开奖号码
- 支持 3 连号、4 连号、和值、AC 值、重号过滤
- 启发式 AI 评分系统，输出 Top50 号码
- Vue3 Web 管理后台
- Docker 与 Docker Compose 一键启动

## 一键启动

```bash
docker compose up --build
```

启动后访问：

- 管理后台：http://localhost:8000
- API 文档：http://localhost:8000/docs
- PostgreSQL：localhost:5432，库名/用户/密码均为 `ssq`

首次进入后台后点击“同步历史开奖”，再点击“AI评分 Top50”。

## 本地开发

本机没有 PostgreSQL 或暂时不想用 Docker 时，可以用项目自带脚本启动 SQLite 开发模式：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1
```

访问：http://localhost:8000

停止服务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\stop-local.ps1
```

该模式会使用项目根目录的 `ssq.db`，适合本地体验和调试。生产或正式部署仍建议使用 PostgreSQL。

后端：

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

前端开发服务默认代理 `/api` 到 `http://localhost:8000`。

默认调度为每周二、周四、周日 22:00 自动同步开奖数据，可通过 `SCHEDULER_CRON` 调整。

## 关键接口

- `GET /api/health` 健康检查
- `GET /api/stats` 历史开奖统计
- `GET /api/draws` 最近开奖列表
- `POST /api/sync` 抓取并同步历史开奖
- `POST /api/generate` 根据过滤规则生成评分 TopN

## 评分说明

AI评分为可解释启发式模型，综合红蓝球历史频率、奇偶比、三区分布、和值、AC 值、重号和连号情况。它用于辅助筛选和排序，不代表任何中奖保证。
