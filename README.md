# 优衣库每日折扣机器人

每天抓取优衣库小程序（uniqlo.cn）的「限时特优」「超值精选」等折扣信息，本地网页展示 + 企业微信群机器人推送。

数据来源是优衣库小程序的静态 JSON 接口，**无需登录、无需 token**。

## 目录结构

```
uniqlo/
├── config.yaml          配置
├── requirements.txt     依赖
├── run_daily.py         手动抓取入口
├── web_server.py        网页服务（内置每日定时抓取）
├── Dockerfile           Docker 镜像
├── docker-compose.yml   一键启动编排
├── .dockerignore        镜像构建排除项
├── uniqlo_bot/          核心包（接口/抓取/存储/推送/流水线）
├── static/index.html    前端展示页
└── data/                运行时生成
    ├── uniqlo.db        商品数据库
    └── images/          商品图片本地缓存
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务（网页 + 每日定时抓取，一条命令）

```bash
python web_server.py
```

浏览器打开 http://localhost:8000 即可查看，支持按品类/来源/折扣率筛选和搜索，右上角有「立即刷新」按钮。

服务启动时会**自动**：
- 按 `config.yaml` 里 `schedule.times` 的时间点每天定时抓取（默认 09:00 / 15:00）；
- 若数据库为空或数据已过期（`stale_hours`），启动时补抓一次；
- 抓取时把商品图缓存到本地 `data/images/`，网页加载不再回源优衣库 CDN。

### 3. 手动抓取一次（可选）

```bash
python run_daily.py
```

成功后打印「总数 / 新增 / 降价 / 下架」统计。

### 4. 开启微信推送

1. 在企业微信里建一个群，添加「群机器人」，复制 Webhook 地址；
2. 编辑 `config.yaml`：

```yaml
wechat:
  enabled: true
  webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的KEY"
```

### 5. 开机自启（可选）

让 `python web_server.py` 随 Windows 开机运行即可持续定时抓取：把快捷方式放进启动文件夹（`Win+R` → `shell:startup`），目标填 `pythonw.exe D:\IdeaProjects\uniqlo\web_server.py`（用 `pythonw` 无窗口静默运行）。

> 抓取时间建议设在优衣库上新/调价之后（限时特优通常周二、周五更新），`config.yaml` 里 `schedule.times` 可配多个时间点。

## Docker 部署

无需本地 Python 环境，用容器跑更省心（网页 + 每日定时抓取 + 数据持久化一条龙）。

```bash
docker compose up -d --build   # 构建并后台启动
docker compose logs -f          # 查看日志
docker compose down             # 停止（加 -v 连同数据卷一起删）
```

启动后浏览器打开 http://localhost:8000 。

- **数据持久化**：数据库和图片缓存放在命名卷 `uniqlo_uniqlo_data`，删容器重建数据仍在。
- **改配置免重建**：`config.yaml` 只读挂载进容器，改完（如微信 webhook）执行 `docker compose restart` 即可生效。
- **时区**：镜像内置 `TZ=Asia/Shanghai`，定时抓取按中国时间触发，可用环境变量 `TZ` 覆盖。
- **镜像源提示**：若 `docker compose up -d --build` 报 `502` 或拉取基础镜像失败，多为 Docker Hub 镜像加速源（如 `dockerproxy.net`）临时故障，等其恢复或换源后重试即可。

## 配置说明

| 配置 | 说明 |
|---|---|
| `uniqlo.pages` | 要抓取的促销页，route 对应 `cms-wechat-config.json` 里的 `/wechat/xxx` 路由 |
| `filter.min_discount_rate` | 只保留折扣率 ≥ 该值(%)的商品，0 = 全部 |
| `filter.only_in_stock` | 只保留有货商品 |
| `wechat.top_n` | 推送 TOP N 最划算商品 |

## 数据接口（供参考）

| 用途 | 接口 |
|---|---|
| 页面索引（自愈式发现配置文件名） | `GET /wechat/config_1/zh_CN/cms-wechat-config.json` |
| 促销页商品列表 | `GET /wechat/config_1/zh_CN/{componentsPath}` |
| 商品详情 | `GET /data/products/prodInfo/zh_CN/{productCode}.json` |
| 商品主图 | `https://www.uniqlo.cn/hmall/test/{productCode}/main/first/1000/1.jpg` |

## 免责声明

本项目仅供个人学习研究使用，请控制抓取频率，勿用于商业用途或对优衣库服务器造成压力。
