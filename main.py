import argparse
from pathlib import Path
from modules.config import Config
from modules.generator import M3UPlaylistGenerator
from modules.scraper import Scraper
from modules.formatter import Formatter
from modules.postprocessor import PostProcessor

CONFIG_PATH = "config"

cfg = Config(CONFIG_PATH)
common_config = cfg.get_common_config()

Path(common_config.get("data_dir")).parent.mkdir(parents=True, exist_ok=True)
Path(common_config.get("playlist_dir")).parent.mkdir(parents=True, exist_ok=True)


def fetch():
    scraper_config = cfg.get_scraper_config()
    client = Scraper(cfg=scraper_config, common_config=common_config)
    client.run()


def format():
    formatter_config = cfg.formatter
    formatter = Formatter(cfg=formatter_config, common_config=common_config)
    formatter.run()


def generate(mode, area, filter):
    generator_config = cfg.get_generator_config()
    area_codes = cfg.get_area_codes()
    generator = M3UPlaylistGenerator(
        cfg=generator_config, common_config=common_config, area_codes=area_codes
    )
    generator.generate_playlist(mode=mode, area=area, filter=filter)


def generate_table():
    generator_config = cfg.get_generator_config()
    area_codes = cfg.get_area_codes()
    generator = M3UPlaylistGenerator(
        cfg=generator_config, common_config=common_config, area_codes=area_codes
    )
    generator.generate_channel_table()


def generate_unused(area):
    generator_config = cfg.get_generator_config()
    area_codes = cfg.get_area_codes()
    generator = M3UPlaylistGenerator(
        cfg=generator_config, common_config=common_config, area_codes=area_codes
    )
    generator.generate_unused_multicast_m3u(area=area)


def process():
    post_processor_config = cfg.get_post_processor_config()
    post_processor = PostProcessor(
        cfg=post_processor_config, common_config=common_config
    )
    post_processor.process_playback()


def diff():
    post_processor_config = cfg.get_post_processor_config()
    post_processor = PostProcessor(
        cfg=post_processor_config, common_config=common_config
    )
    post_processor.diff()


def auth():
    post_processor_config = cfg.get_post_processor_config()
    post_processor = PostProcessor(
        cfg=post_processor_config, common_config=common_config
    )
    post_processor.if_auth()


def process_all():
    fetch()
    format()
    generate("private", "taian", True)


def main():
    parser = argparse.ArgumentParser(description="IPTV processing CLI")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("fetch", help="Fetch raw data")
    subparsers.add_parser("format", help="Format raw data")

    generate_parser = subparsers.add_parser("generate", help="Generate M3U playlist")
    generate_parser.add_argument("--mode", type=str, default="private")
    generate_parser.add_argument("--area", type=str, required=True)
    generate_parser.add_argument("--filter", type=bool, default=True)

    subparsers.add_parser("generate_table", help="Generate channel table")

    unused_parser = subparsers.add_parser(
        "generate_unused", help="Generate unused multicast M3U"
    )
    unused_parser.add_argument("--area", type=str, required=True)

    subparsers.add_parser("playback", help="Process playback data")
    subparsers.add_parser("diff", help="Perform diff operation")
    subparsers.add_parser("check", help="Check if auth is required")

    subparsers.add_parser("all", help="Run fetch, format and generate in sequence")

    args = parser.parse_args()

    if args.command == "fetch":
        fetch()
    elif args.command == "format":
        format()
    elif args.command == "generate":
        generate(args.mode, args.area, args.filter)
    elif args.command == "generate_table":
        generate_table()
    elif args.command == "generate_unused":
        generate_unused(args.area)
    elif args.command == "playback":
        process()
    elif args.command == "diff":
        diff()
    elif args.command == "check":
        auth()

    elif args.command == "all":
        process_all()
    else:
        print("Invalid command")


if __name__ == "__main__":
    main()
