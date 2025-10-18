import json
from pathlib import Path
from urllib.parse import urlparse
from helpers.postprocessor import *
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from datetime import datetime


class PostProcessor:
    def __init__(self, cfg: dict, common_config: dict, workers: Optional[int] = None):

        self.data_dir = common_config.get("data_dir")
        self.formatted_file_name = common_config.get("formatted_file_name")
        self.formatted_file_path = Path(self.data_dir) / self.formatted_file_name
        self.raw_file_path = cfg.get("raw_file_path")
        self.channel_list_file_path = cfg.get("channel_list_file_path")
        self.process_channel_keywords = cfg.get("process_channel_keywords")
        self.channel_list_change_file_path = cfg.get("channel_list_change_file_path")
        self.workers = workers or cfg.get("workers", 10)
        self.playback_offset = cfg.get("playback_offset", 7)
        self.auth_test_channel_name = cfg.get("auth_test_channel_name", "")

    def if_auth(self):
        with open(self.raw_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for channel in data:
                if channel.get("ChannelName") == self.auth_test_channel_name:
                    import re

                    match = re.search(r"rtsp://\S+", channel["ChannelSDP"])
                    if match:
                        tmp = match.group(0)
                        from utils.ffmpeg import get_redirected_rtsp_url

                        redirected = get_redirected_rtsp_url(tmp)
                        if not redirected or redirected.startswith("rtsp://222"):
                            print("[PostProcessor] Authentication required.")
                        else:
                            print("[PostProcessor] No Authentication required.")

    def diff(self):
        try:
            with open(self.raw_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            json_channel_names = [
                item["ChannelName"] for item in data if "ChannelName" in item
            ]



            try:
                with open(self.channel_list_file_path, "r", encoding="utf-8") as f:
                    existing_channels = [line.strip() for line in f.readlines()]
            except FileNotFoundError:
                existing_channels = []

            final_message = ""
            ifWrite = False

            if existing_channels == json_channel_names:
                print("[PostProcessor] Channel list has not changed")
            else:
                ifWrite = True
                added = [c for c in json_channel_names if c not in existing_channels]
                removed = [c for c in existing_channels if c not in json_channel_names]

                parts = []
                if added:
                    parts.append("New channel added: " + ", ".join(added))
                if removed:
                    parts.append("Channel removed: " + ", ".join(removed))

                final_message = "\n".join(parts)

                print(f"[PostProcessor] {final_message}")

            if ifWrite == True:
                now_str = datetime.now().strftime("%Y-%m-%d")
                with open(
                    self.channel_list_change_file_path, "a", encoding="utf-8"
                ) as f:
                    f.write(f"#### 时间: {now_str}\n\n")
                    if added:
                        f.write("上线频道: " + ", ".join(added) + "\n\n")
                    if removed:
                        f.write("下线频道: " + ", ".join(removed) + "\n\n")

            with open(self.channel_list_file_path, "w", encoding="utf-8") as f:
                for name in json_channel_names:
                    f.write(name + "\n")

        except Exception as e:
            print(f"[PostProcessor]: {e}")

    def process_playback(self, offset: Optional[int] = None):
        offset = offset or self.playback_offset
        results = []
        print("[PostProcessor] Starting to find playback URLs.")
        with open(self.formatted_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = [executor.submit(self.find_playback, ch, offset) for ch in data]
            for fut in as_completed(futures):
                results.append(fut.result())

        results = self.sort_results(results)
        self.save_results(self.formatted_file_path, results)

    def find_playback(self, channel, offset):
        uni_playback = channel.get("uni_playback")
        channel_name = channel.get("ChannelName")

        if not uni_playback or not channel_name:
            return channel

        if not any(ch in channel_name for ch in self.process_channel_keywords):
            return channel
        from utils.convert import get_yyyyMMddHHmmss_with_offset

        begin_time = get_yyyyMMddHHmmss_with_offset(days=-offset, minutes=-30)
        end_time = get_yyyyMMddHHmmss_with_offset(offset)

        uni_playback_filled = uni_playback.replace("{utc:YmdHMS}", begin_time).replace(
            "{utcend:YmdHMS}", end_time
        )

        if test_ffmpeg_rtsp(uni_playback_filled):
            print(
                f"- [PostProcessor] Offset = {offset}: {channel_name}, Original URL is available, skipping."
            )
            return channel

        success = test_ip_connectivity(
            uni_playback_filled, 36, 48
        ) or test_ip_connectivity(uni_playback_filled, 68, 74)

        if success:
            print(
                f"- [PostProcessor] Offset = {offset}: {channel_name}, Playback URL fetched successfully."
            )
            parsed = urlparse(uni_playback)
            ip_parts = parsed.hostname.split(".")
            ip_parts[-1] = str(success)
            new_ip = ".".join(ip_parts)
            new_url = uni_playback.replace(parsed.hostname, new_ip)
            channel["uni_playback"] = new_url
        else:
            print(f"- [PostProcessor] {channel_name} has no available playback URL.")

        return channel

    def sort_results(self, results):
        try:
            results.sort(key=lambda x: int(x["tvg_id"]))
        except ValueError:
            results.sort(key=lambda x: x["tvg_id"])
        return results

    def save_results(self, filename: str, results):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
