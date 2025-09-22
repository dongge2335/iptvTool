#!/usr/bin/env python3
import argparse
from core.STB import get_iptv_raw
from core.process import (
    gen_iptv_json,
    extract_channel_names,
    generate_unused_multicast_m3u,
    process_raw,
    test_auth,
)
from core.m3u import gen_m3u_playlist


def main():
    parser = argparse.ArgumentParser(description="IPTV 工具 - 获取、处理、生成播放列表")

    parser.add_argument("--fetch", action="store_true", help="抓取 IPTV 原始数据")
    parser.add_argument("--process", action="store_true", help="生成 iptv.json")
    parser.add_argument("--m3u", choices=["uni", "mul", "all"], help="生成m3u播放列表")
    parser.add_argument("--list", action="store_true", help="生成频道名称列表")
    parser.add_argument("--unused", action="store_true", help="生成未使用组播地址列表")
    parser.add_argument(
        "--all", action="store_true", help="执行 fetch + process + m3u all 全流程"
    )
    parser.add_argument(
        "--sort-file", default="sort.txt", help="排序文件路径（默认：sort.txt）"
    )
    parser.add_argument(
        "--output-dir", default="playlist", help="输出目录（默认：playlist）"
    )
    parser.add_argument(
        "--input-json",
        default="iptv.json",
        help="IPTV JSON 数据文件路径（默认：iptv.json）",
    )

    parser.add_argument(
        "--test", action="store_true", help="测试是否存在需要鉴权的单播地址"
    )

    args = parser.parse_args()

    if args.all:
        args.fetch = True
        args.process = True
        args.m3u = "all"

    if args.fetch:
        print("📡 获取 IPTV 原始数据...")
        get_iptv_raw()
        process_raw()
    if args.process:
        print("🛠 生成 iptv.json...")
        gen_iptv_json()

    if args.m3u:
        if args.m3u in ["all", "uni"]:
            print("🎯 生成单播播放列表...")
            gen_m3u_playlist(
                args.input_json,
                f"{args.output_dir}/unicast.m3u",
                mode="uni",
                sort_file=args.sort_file,
            )

        if args.m3u in ["all", "mul"]:
            print("🌐 生成组播播放列表...")
            gen_m3u_playlist(
                args.input_json,
                f"{args.output_dir}/multicast.m3u",
                mode="mul",
                sort_file=args.sort_file,
            )

    if args.list:
        extract_channel_names()
    if args.unused:
        generate_unused_multicast_m3u()

    if args.test:
        test_auth()

    if not (
        args.fetch or args.process or args.m3u or args.list or args.unused or args.test
    ):
        parser.print_help()


if __name__ == "__main__":
    main()
