"""企业微信群机器人推送。"""
import requests


def send_markdown(webhook_url, content):
    """向企业微信群机器人发送 markdown 消息。返回响应的 errcode。"""
    payload = {"msgtype": "markdown", "markdown": {"content": content}}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"errcode": -1, "errmsg": str(exc)}


def _fmt_price(p):
    return f"{p['price']:.0f}" if float(p["price"]).is_integer() else f"{p['price']:.1f}"


def build_summary_markdown(diff, top_products):
    """构造推送消息。"""
    total = diff["total"]
    new_n = len(diff["new"])
    drop_n = len(diff["drops"])
    removed_n = diff["removed"]

    lines = ["## 🛍️ 优衣库每日折扣", ""]
    lines.append(f"**在售折扣商品：{total}**｜新增 {new_n}｜降价 {drop_n}｜下架 {removed_n}")
    lines.append("")

    if drop_n:
        lines.append("### 🔻 今日降价")
        for d in diff["drops"][:10]:
            p = d["product"]
            lines.append(
                f"- [{p['name']}]({p['url']}) "
                f"{_fmt_price({'price': d['old_price']})} → **{_fmt_price(p)}** "
                f"（{p['discount_rate']}% off）"
            )
        lines.append("")

    if new_n:
        lines.append("### 🆕 今日新增")
        for p in diff["new"][:10]:
            lines.append(f"- [{p['name']}]({p['url']}) **{_fmt_price(p)}**（{p['discount_rate']}% off）")
        lines.append("")

    lines.append("### 🏆 最划算 TOP")
    for p in top_products[:10]:
        lines.append(
            f"- [{p['name']}]({p['url']}) "
            f"~~{_fmt_price({'price': p['origin_price']})}~~ → **{_fmt_price(p)}** "
            f"（{p['discount_rate']}% off）"
        )

    return "\n".join(lines)
