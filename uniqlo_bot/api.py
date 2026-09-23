"""优衣库接口客户端。

所有数据接口均为静态 JSON、无需鉴权，直接 GET 即可。
注意：图片 CDN（/hmall/ 路径）会被腾讯 EdgeOne 的 TLS 指纹识别拦截，
requests 会得到 567，需用 curl_cffi 模拟浏览器指纹；JSON 接口用 requests 即可。
"""
import os
import time

import requests
from curl_cffi import requests as cffi_requests


class UniqloApi:
    def __init__(self, base_url, image_base, timeout=20, retries=3, delay=0.3):
        self.base_url = base_url.rstrip("/")
        self.image_base = image_base.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                ),
                "Referer": f"{self.base_url}/",
                "Accept": "*/*",
            }
        )

    def get_json(self, path, params=None):
        """GET 一个 JSON 接口，带重试与限速。"""
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        last_err = None
        for i in range(self.retries):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 200:
                    return resp.json()
                last_err = f"HTTP {resp.status_code}"
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
            time.sleep(self.delay * (i + 1))
        raise RuntimeError(f"GET {url} 失败: {last_err}")

    def product_image_url(self, product_code, color_no=None):
        """商品主图 / 色卡图 URL。"""
        if color_no:
            return f"{self.image_base}/{product_code}/chip/22/{color_no}.jpg"
        return f"{self.image_base}/{product_code}/main/first/1000/1.jpg"

    def product_page_url(self, product_code):
        """商品详情页链接。"""
        return f"{self.base_url}/product-detail.html?productCode={product_code}"

    def download_image(self, product_code, dest_path):
        """下载商品主图到本地，成功返回 True。

        用 curl_cffi 模拟 Chrome 指纹，绕过图片 CDN 的 TLS 指纹拦截。
        """
        url = self.product_image_url(product_code)
        try:
            resp = cffi_requests.get(url, timeout=self.timeout, impersonate="chrome")
            if resp.status_code == 200 and resp.content:
                os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
                return True
        except Exception:  # noqa: BLE001
            pass
        return False
