"""网页服务：提供折扣商品 API 与前端页面，内置每日定时抓取。

用法：
    python web_server.py            # 默认 0.0.0.0:8000
    python web_server.py -c config.yaml
"""
import argparse
import datetime
import logging
import os
import sys
import threading
import time
from contextlib import asynccontextmanager

# Windows 控制台默认 GBK，强制 UTF-8 输出避免中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from uniqlo_bot import pipeline
from uniqlo_bot.config import load_config
from uniqlo_bot.storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("web_server")

cfg = load_config()
store = Storage(cfg["storage"]["db_path"])

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
IMAGE_DIR = os.path.abspath(cfg["image_cache"]["dir"])
os.makedirs(IMAGE_DIR, exist_ok=True)

_crawl_lock = threading.Lock()


def _run_crawl_job():
    """后台执行一次抓取（加锁防止并发）。"""
    if not _crawl_lock.acquire(blocking=False):
        log.info("已有抓取任务在运行，跳过本次")
        return
    try:
        log.info("开始抓取…")
        pipeline.run_pipeline(load_config(), logger=log)
        log.info("抓取完成")
    except Exception as exc:  # noqa: BLE001
        log.exception("抓取失败：%s", exc)
    finally:
        _crawl_lock.release()


def _next_run_delay(times):
    """返回距下一个抓取时间点的秒数与时间。"""
    now = datetime.datetime.now()
    candidates = []
    for t in times:
        hh, mm = (int(x) for x in str(t).split(":"))
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        candidates.append(target)
    nxt = min(candidates)
    return (nxt - now).total_seconds(), nxt


def _scheduler_loop(times):
    """定时循环：到点触发抓取。"""
    while True:
        delay, nxt = _next_run_delay(times)
        log.info("下次定时抓取：%s", nxt.strftime("%Y-%m-%d %H:%M:%S"))
        time.sleep(delay)
        _run_crawl_job()


def _data_is_stale(stale_hours):
    """数据为空或超过 stale_hours 未更新时返回 True。"""
    updated = store.summary().get("updated_at")
    if not updated:
        log.info("数据库为空，启动时执行首次抓取")
        return True
    try:
        last = datetime.datetime.strptime(updated, "%Y-%m-%d %H:%M:%S")
        if (datetime.datetime.now() - last).total_seconds() > stale_hours * 3600:
            log.info("数据已过期（%s），启动时补抓", updated)
            return True
    except ValueError:
        return True
    return False


@asynccontextmanager
async def lifespan(_app):
    """服务启动：拉起定时器，必要时补抓一次。"""
    sc = cfg["schedule"]
    if sc.get("enabled", True):
        threading.Thread(target=_scheduler_loop, args=(sc["times"],), daemon=True).start()
        if _data_is_stale(sc.get("stale_hours", 24)):
            threading.Thread(target=_run_crawl_job, daemon=True).start()
    yield


app = FastAPI(title="优衣库折扣机器人", lifespan=lifespan)
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")


@app.get("/api/products")
def get_products(
    sex: str = Query("", description="按品类过滤，如 男装/女装/童装/婴幼儿装"),
    page: str = Query("", description="按来源页过滤，如 限时特优/超值精选"),
    q: str = Query("", description="按名称/货号搜索"),
    min_discount: float = Query(0, description="最小折扣率(%)"),
):
    items = store.get_active(sort="discount")

    def match(p):
        if sex and sex not in p["sex"]:
            return False
        if page and page not in p["source_pages"]:
            return False
        if min_discount and p["discount_rate"] < min_discount:
            return False
        if q:
            needle = q.lower()
            if (
                needle not in p["name"].lower()
                and needle not in p["item_code"].lower()
                and needle not in p["product_code"].lower()
            ):
                return False
        return True

    return [p for p in items if match(p)]


@app.get("/api/summary")
def get_summary():
    return store.summary()


@app.get("/api/options")
def get_options():
    items = store.get_active(sort="discount")
    sexes = sorted({p["sex"] for p in items if p["sex"]})
    pages = sorted({pg for p in items for pg in p["source_pages"]})
    return {"sexes": sexes, "pages": pages}


@app.post("/api/crawl")
def trigger_crawl():
    """手动触发一次抓取（后台执行）。"""
    if _crawl_lock.locked():
        return {"status": "running"}
    threading.Thread(target=_run_crawl_job, daemon=True).start()
    return {"status": "started"}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="优衣库折扣网页服务")
    parser.add_argument("-c", "--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    host = args.host or cfg["web"]["host"]
    port = args.port or cfg["web"]["port"]
    uvicorn.run(app, host=host, port=port)
