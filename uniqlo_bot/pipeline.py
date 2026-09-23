"""抓取流水线：抓取 -> 图片缓存 -> 入库 -> 微信推送。

run_daily.py（手动）与 web_server.py（定时）共用此入口。
"""
import logging

from . import crawler, notify
from .api import UniqloApi
from .storage import Storage

log = logging.getLogger("pipeline")


def run_pipeline(cfg, logger=None):
    """执行一次完整抓取，返回 diff 概览 {new, drops, removed, total}。"""
    log_ = logger or log
    u = cfg["uniqlo"]
    f = cfg["filter"]
    w = cfg["wechat"]
    ic = cfg["image_cache"]

    api = UniqloApi(
        u["base_url"],
        u["image_base"],
        timeout=u["request"]["timeout"],
        retries=u["request"]["retries"],
        delay=u["request"]["delay"],
    )

    log_.info("开始抓取 %d 个促销页", len(u["pages"]))
    products = crawler.crawl(
        api,
        u["pages"],
        u["index_path"],
        min_discount_rate=f["min_discount_rate"],
        only_in_stock=f["only_in_stock"],
        logger=log_,
    )
    log_.info("抓取完成，共 %d 件折扣商品", len(products))

    if products:
        products = crawler.cache_images(
            products, api, ic["dir"], ic["concurrency"], logger=log_
        )

    store = Storage(cfg["storage"]["db_path"])
    diff = store.apply_run(products)
    log_.info(
        "入库完成：总数 %d，新增 %d，降价 %d，下架 %d",
        diff["total"],
        len(diff["new"]),
        len(diff["drops"]),
        diff["removed"],
    )

    if w["enabled"] and w["webhook_url"]:
        top = sorted(products, key=lambda p: (-p["discount_rate"], p["price"]))[: w["top_n"]]
        content = notify.build_summary_markdown(diff, top)
        resp = notify.send_markdown(w["webhook_url"], content)
        if resp.get("errcode") == 0:
            log_.info("微信推送成功")
        else:
            log_.warning("微信推送失败：%s", resp)

    return diff
