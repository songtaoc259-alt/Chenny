# Render 部署（最简步骤）

## 1) 准备 GitHub 仓库
- 把以下文件推到 GitHub：
  - `single_file_takeout_app.py`
  - `requirements.txt`
  - `.gitignore`
  - `DEPLOY_RENDER.md`

## 2) 在 Render 创建 Web Service
- 打开 Render 控制台，选择 `New +` -> `Web Service`
- 连接你的 GitHub 仓库
- 关键配置：
  - `Runtime`: `Python 3`
  - `Build Command`: `pip install -r requirements.txt`
  - `Start Command`: `python single_file_takeout_app.py --prod --host 0.0.0.0 --port $PORT`

## 3) 配置环境变量（Environment）
- `APP_SECRET_KEY`：请设置一个长随机字符串
- 可选（推荐持久化）：
  - `APP_DB_PATH=/var/data/single_file_takeout_app.db`
  - `APP_UPLOAD_DIR=/var/data/uploads`

## 4) 持久化磁盘（推荐）
- 在 Render 服务里添加 Persistent Disk
- 挂载路径设置为：`/var/data`
- 这样数据库和上传图片在重启后不会丢失

## 5) 验证上线
- 打开服务 URL
- 检查健康接口：`/healthz`
  - 示例：`https://你的域名/healthz`

---

## 常见问题
- 问：别人能直接访问吗？
  - 答：可以。Render 提供公网 URL，任何用户都可访问。

- 问：为什么我重启后数据没了？
  - 答：通常是没有挂载 Persistent Disk，或未设置 `APP_DB_PATH` / `APP_UPLOAD_DIR` 到 `/var/data`。

- 问：上传图片打不开？
  - 答：确认 `APP_UPLOAD_DIR` 指向可写目录，并已挂载持久化磁盘。
