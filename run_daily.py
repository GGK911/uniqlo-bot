"""每日抓取入口（手动执行用；定时任务由 web_server.py 内置调度器负责）。

用法：
    python run_daily.py              # 用默认 config.yaml
    python run_daily.py -c 自定义.yaml
"""
import argparse
import logging
import sys

# Windows 控制台默认 GBK，强制 UTF-8 输出避免中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from uniqlo_bot import pipeline  # noqa: E402
from uniqlo_bot.config import load_config  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_daily")


def main():
    parser = argparse.ArgumentParser(description="优衣库每日折扣抓取")
    parser.add_argument("-c", "--config", default="config.yaml", help="配置文件路径")
    args = parser.parse_args()

    cfg = load_config(args.config)
    pipeline.run_pipeline(cfg, logger=log)


if __name__ == "__main__":
    main()
