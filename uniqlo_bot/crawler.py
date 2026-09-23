"""抓取编排：页面发现 -> 商品编码 -> 商品详情 -> 折扣计算 -> 图片缓存。"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)


def discover_page_files(api, index_path):
    """从页面索引里解析各促销页当前生效的配置文件。

    返回 {route: {"title": str, "paths": [componentsPath, ...]}}。
    只关注以 /wechat/ 开头的路由。
    """
    index = api.get_json(index_path)
    # 促销页路由位于索引的 pages 字段下
    routes = index.get("pages", {}) if isinstance(index, dict) else {}
    result = {}
    for route, node in routes.items():
        if not isinstance(route, str) or not route.startswith("/wechat/"):
            continue
        if not isinstance(node, dict):
            continue
        paths = []
        for prop in node.get("props") or []:
            cp = prop.get("componentsPath")
            if cp:
                paths.append(cp)
        if paths:
            result[route] = {
                "title": node.get("title") or node.get("code") or route,
                "paths": paths,
            }
    return result


def extract_product_codes(page_json):
    """从页面配置里提取所有 productCode（去重、保序）。"""
    codes = []
    seen = set()
    for section in page_json.values():
        if not isinstance(section, dict):
            continue
        if section.get("componentType") != "productRecommed":
            continue
        for group in section.get("props") or []:
            if not isinstance(group, dict):
                continue
            for item in group.get("props") or []:
                code = item.get("productCode")
                if code and code not in seen:
                    seen.add(code)
                    codes.append(code)
    return codes


def parse_product(data, product_code, api):
    """把商品详情 JSON 解析成标准字典。"""
    origin = data.get("originPrice") or 0
    price = data.get("minPrice") or 0
    discount_rate = 0.0
    if origin and price and origin > 0:
        discount_rate = round((origin - price) / origin * 100, 1)

    colors = [
        {"styleText": c.get("styleText", ""), "colorNo": c.get("colorNo", "")}
        for c in (data.get("colorList") or [])
    ]

    has_stock = str(data.get("hasStock", "")).upper() == "Y" or str(
        data.get("stock", "")
    ).upper() == "Y"

    return {
        "product_code": product_code,
        "item_code": data.get("code", ""),
        "name": data.get("name", ""),
        "full_name": data.get("fullName", data.get("name", "")),
        "sex": data.get("sex") or data.get("gDeptValue") or "",
        "origin_price": origin,
        "price": price,
        "discount_rate": discount_rate,
        "label": data.get("label", ""),
        "time_begin": data.get("timeLimitedBegin"),
        "time_end": data.get("timeLimitedEnd"),
        "colors": colors,
        "image": api.product_image_url(product_code),
        "image_local": "",  # 本地缓存路径，由 cache_images 填充
        "url": api.product_page_url(product_code),
        "stock": 1 if has_stock else 0,
        "source_pages": [],  # 由上层填充
    }


def crawl(api, pages, index_path, min_discount_rate=0, only_in_stock=True, logger=None):
    """抓取所有促销页，返回去重后的商品列表（按折扣率降序）。"""
    log_ = logger or log
    page_files = discover_page_files(api, index_path)

    # 组装 route -> 页面名
    wanted = {p["route"]: p["name"] for p in pages}

    # products: code -> 商品字典（合并多页来源）
    products = {}
    for route, name in wanted.items():
        info = page_files.get(route)
        if not info:
            log_.warning("未在索引中找到促销页 %s (%s)，跳过", route, name)
            continue
        for components_path in info["paths"]:
            log_.info("抓取 %s -> %s", name, components_path)
            page_json = api.get_json(f"/wechat/config_1/zh_CN/{components_path}")
            codes = extract_product_codes(page_json)
            for code in codes:
                if code in products:
                    if name not in products[code]["source_pages"]:
                        products[code]["source_pages"].append(name)
                    continue
                detail = api.get_json(f"/data/products/prodInfo/zh_CN/{code}.json")
                item = parse_product(detail, code, api)
                item["source_pages"] = [name]
                products[code] = item

    result = list(products.values())

    # 过滤：折扣率、库存
    def keep(p):
        if p["discount_rate"] < min_discount_rate:
            return False
        if only_in_stock and not p["stock"]:
            return False
        return True

    result = [p for p in result if keep(p)]
    # 按折扣率降序（最划算在前）
    result.sort(key=lambda p: (-p["discount_rate"], p["price"]))
    return result


def cache_images(products, api, cache_dir, concurrency=4, logger=None):
    """下载商品主图到本地缓存，并把成功者写入 image_local。

    已存在的缓存文件跳过，不会重复下载。
    """
    log_ = logger or log
    os.makedirs(cache_dir, exist_ok=True)

    def work(p):
        code = p["product_code"]
        local_name = f"{code}.jpg"
        local_path = os.path.join(cache_dir, local_name)
        if not (os.path.exists(local_path) and os.path.getsize(local_path) > 0):
            api.download_image(code, local_path)
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            p["image_local"] = f"/images/{local_name}"

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        list(ex.map(work, products))

    # 清理已不在本次结果中的旧图片，避免缓存无限膨胀
    valid = {p["product_code"] for p in products}
    removed = 0
    for fname in os.listdir(cache_dir):
        if fname.endswith(".jpg") and fname[:-4] not in valid:
            try:
                os.remove(os.path.join(cache_dir, fname))
                removed += 1
            except OSError:
                pass

    cached = sum(1 for p in products if p["image_local"])
    log_.info(
        "图片缓存完成：%d/%d 张已本地化，清理 %d 张旧图",
        cached,
        len(products),
        removed,
    )
    return products
