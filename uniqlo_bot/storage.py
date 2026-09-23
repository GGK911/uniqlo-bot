"""SQLite 存储：商品入库、新增/降价检测。"""
import json
import os
import sqlite3
from datetime import datetime


class Storage:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_code  TEXT PRIMARY KEY,
                    item_code     TEXT,
                    name          TEXT,
                    full_name     TEXT,
                    sex           TEXT,
                    origin_price  REAL,
                    price         REAL,
                    discount_rate REAL,
                    label         TEXT,
                    time_begin    INTEGER,
                    time_end      INTEGER,
                    colors        TEXT,
                    image         TEXT,
                    image_local   TEXT,
                    url           TEXT,
                    source_pages  TEXT,
                    stock         INTEGER,
                    active        INTEGER DEFAULT 1,
                    first_seen    TEXT,
                    last_seen     TEXT
                )
                """
            )
            # 兼容旧库：补充 image_local 列（列已存在时忽略）
            try:
                conn.execute("ALTER TABLE products ADD COLUMN image_local TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass

    def _row_to_dict(self, row):
        d = dict(row)
        d["colors"] = json.loads(d["colors"]) if d.get("colors") else []
        d["source_pages"] = json.loads(d["source_pages"]) if d.get("source_pages") else []
        d["stock"] = bool(d["stock"])
        d["active"] = bool(d["active"])
        return d

    def apply_run(self, products):
        """把一次抓取结果入库，返回 {new, drops, removed, total}。"""
        today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new = []
        drops = []

        with self._connect() as conn:
            conn.execute("UPDATE products SET active = 0")
            for p in products:
                old = conn.execute(
                    "SELECT price FROM products WHERE product_code = ?",
                    (p["product_code"],),
                ).fetchone()

                if old is None:
                    new.append(p)
                elif old["price"] is not None and p["price"] < old["price"] - 1e-9:
                    drops.append({"product": p, "old_price": old["price"]})

                conn.execute(
                    """
                    INSERT INTO products (
                        product_code, item_code, name, full_name, sex,
                        origin_price, price, discount_rate, label,
                        time_begin, time_end, colors, image, image_local, url,
                        source_pages, stock, active, first_seen, last_seen
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(product_code) DO UPDATE SET
                        item_code=excluded.item_code,
                        name=excluded.name,
                        full_name=excluded.full_name,
                        sex=excluded.sex,
                        origin_price=excluded.origin_price,
                        price=excluded.price,
                        discount_rate=excluded.discount_rate,
                        label=excluded.label,
                        time_begin=excluded.time_begin,
                        time_end=excluded.time_end,
                        colors=excluded.colors,
                        image=excluded.image,
                        image_local=excluded.image_local,
                        url=excluded.url,
                        source_pages=excluded.source_pages,
                        stock=excluded.stock,
                        active=1,
                        last_seen=excluded.last_seen
                    """,
                    (
                        p["product_code"],
                        p["item_code"],
                        p["name"],
                        p["full_name"],
                        p["sex"],
                        p["origin_price"],
                        p["price"],
                        p["discount_rate"],
                        p["label"],
                        p["time_begin"],
                        p["time_end"],
                        json.dumps(p["colors"], ensure_ascii=False),
                        p["image"],
                        p["image_local"],
                        p["url"],
                        json.dumps(p["source_pages"], ensure_ascii=False),
                        1 if p["stock"] else 0,
                        today,
                        today,
                    ),
                )

            removed = conn.execute(
                "SELECT COUNT(*) FROM products WHERE active = 0"
            ).fetchone()[0]

        return {"new": new, "drops": drops, "removed": removed, "total": len(products)}

    def get_active(self, sort="discount"):
        """返回当前在售的商品列表。"""
        order = {"discount": "discount_rate DESC, price ASC", "price": "price ASC"}
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM products WHERE active = 1 ORDER BY {order.get(sort, order['discount'])}"
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def summary(self):
        """返回概览统计。"""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM products WHERE active = 1").fetchone()[0]
            avg = conn.execute(
                "SELECT AVG(discount_rate) FROM products WHERE active = 1 AND discount_rate > 0"
            ).fetchone()[0]
            best = conn.execute(
                "SELECT MAX(discount_rate) FROM products WHERE active = 1"
            ).fetchone()[0]
            last = conn.execute("SELECT MAX(last_seen) FROM products").fetchone()[0]
        return {
            "total": total,
            "avg_discount_rate": round(avg or 0, 1),
            "max_discount_rate": round(best or 0, 1),
            "updated_at": last,
        }
