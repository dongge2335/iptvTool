# !/usr/bin/env python3
import argparse
from core.process import *


def main():
    parser = argparse.ArgumentParser(description="IPTV 工具 - 获取、处理、生成播放列表")

    parser.add_argument("--all", action="store_true")

    parser.add_argument("--fetch", action="store_true", help="抓取 IPTV 原始数据")
    parser.add_argument(
        "--process", action="store_true", help="处理 raw.json 并生成 iptv.json"
    )
    parser.add_argument("--m3u", action="store_true", help="生成 M3U 播放列表")
    parser.add_argument(
        "--diff", action="store_true", help="生成频道名称列表并与现有文件对比"
    )
    parser.add_argument(
        "--unused", action="store_true", help="生成未使用的组播地址列表"
    )
    parser.add_argument(
        "--test", action="store_true", help="测试是否存在需要鉴权的单播地址"
    )

    parser.add_argument(
        "--probe",
        choices=["unicast", "unused"],
        help="探测地址类型并生成 JSON（unicast 或 unused）",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="生成频道列表 Markdown 文件"
    )

    parser.add_argument("--mode", choices=["uni", "mul", "all"], default="all")
    parser.add_argument("--sort-file", default="data/sort.txt")
    parser.add_argument(
        "--timeout", type=int, default=10, help="ffprobe 超时时间（秒）"
    )
    parser.add_argument("--max-workers", type=int, default=8, help="ffprobe 并发线程数")

    args = parser.parse_args()

    if args.all:
        args.fetch = True
        args.process = True
        args.m3u = True
        args.diff = True

    if args.fetch:
        get_iptv_raw()
    if args.process:
        gen_iptv_json()
    if args.m3u:
        if args.mode in ["uni", "all"]:
            gen_m3u_playlist(
                mode="uni",
                sort_file=args.sort_file,
            )
        if args.mode in ["mul", "all"]:
            gen_m3u_playlist(
                mode="mul",
                sort_file=args.sort_file,
            )
        json_to_md_table()

    if args.diff:
        diff_channel_lists()
    if args.unused:
        generate_unused_multicast_m3u()
    if args.test:
        test_auth()

    if args.probe:
        if args.probe == "unicast":
            probe_unicast(timeout=args.timeout, max_workers=args.max_workers)
        elif args.probe == "unused":
            probe_unused_multicast(timeout=args.timeout, max_workers=args.max_workers)

    if args.list:
        json_to_md_table()

if __name__ == "__main__":
    main()
