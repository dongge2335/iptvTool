import json, re
from pathlib import Path
from tqdm import tqdm
from datetime import datetime, timedelta, timezone


class M3UPlaylistGenerator:
    def __init__(self, cfg: dict, common_config: dict, area_codes: dict):
        self.area_codes = area_codes
        self.data_dir = common_config.get("data_dir")
        self.playlist_dir = common_config.get("playlist_dir")
        self.raw_file_name = common_config.get("raw_file_name")
        self.raw_file_path = Path(self.data_dir) / self.raw_file_name
        self.formatted_file_name = common_config.get("formatted_file_name")
        self.formatted_file_path = Path(self.data_dir) / self.formatted_file_name
        self.sort_file_name = common_config.get("sort_file_name")
        self.url_tvg = cfg.get("url_tvg", False)
        self.logo_base = cfg.get("logo_base", "")
        self.udpxy_base_url = cfg.get("udpxy_base_url", "")
        self.exclude_channel_list_public = cfg.get("exclude_channel_list_public", [])
        self.exclude_channel_list_private = cfg.get("exclude_channel_list_private", [])
        self.channel_list_markdown_file_name = common_config.get(
            "channel_list_markdown_file_name"
        )

    def generate_unused_multicast_m3u(self, area: str):
        used = []
        noUse = []
        area_code = self.area_codes.get(area, "")
        if not area_code:
            raise ValueError("[Generator] 'area' not valid.")

        with open(self.raw_file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            for channel in data:
                url = channel["ChannelURL"].replace("igmp://", "")
                matches = re.findall(r"\b(?:\d{1,3}\.){3}(\d{1,3})\b", url)
                used.append(int(matches[0]))
            for i in range(0, 256):
                if i not in used:
                    noUse.append(i)

        unused_multicast_file_path = (
            Path(self.playlist_dir) / f"multicast-unused-{area}.m3u"
        )

        with open(unused_multicast_file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in noUse:
                extinf = f"#EXTINF:-1 "
                extinf += f",{ch}"
                f.write(
                    f"{extinf}\n{self.udpxy_base_url.format(f'rtp/239.253.{area_code}.{ch}:8000')}\n"
                )

        print(
            f"Unused multicast addresses have been saved to {unused_multicast_file_path}"
        )

    def generate_channel_table(self):
        with open(self.formatted_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        excluded_count = sum(
            1
            for channel_info in data
            if any(
                channel_info.get("tvg_name", "") == channel
                for channel in self.exclude_channel_list_public
            )
        )

        total_channels = len(data) - excluded_count

        tz_utc8 = timezone(timedelta(hours=8))
        now_str = datetime.now(tz=tz_utc8).strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "## 频道列表\n",
            f"**更新时间**: {now_str} UTC+8\n\n"
            f"**频道总数**: {total_channels}\n\n"
            "| 频道名称 | 频道号 | 组播号 |",
            "|----------|--------|--------|",
        ]

        for ch in data:
            name = ch.get("ChannelName", "")
            tvg_id = ch.get("tvg_id", "")
            tvg_name = ch.get("tvg_name", "")

            if any(
                tvg_name.startswith(local) for local in self.exclude_channel_list_public
            ):
                continue

            channel_url = ch.get("mul_live", "")
            mcast_number = ""
            if channel_url.startswith("rtp://"):
                import re

                match = re.search(r"\.(\d+):\d+$", channel_url)
                if match:
                    mcast_number = match.group(1)

            lines.append(f"| {name} | {tvg_id} | {mcast_number} |")

        with open(
            Path(self.data_dir) / self.channel_list_markdown_file_name,
            "w",
            encoding="utf-8",
        ) as f:
            f.write("\n".join(lines))

        print("[Generator] Channel list Markdown file has been generated.")

    def generate_playlist(
        self, area: str = "", mode: str = "", filter: bool = False
    ) -> None:
        if not area or not mode:
            raise ValueError(
                "[Generator] 'area' and 'mode' must be provided and valid."
            )
        channels = self.load_channels()
        channels = self.sort_channels(channels)

        area_code = self.area_codes.get(area, "")
        if not area_code:
            raise ValueError("[Generator] 'area' not valid.")

        for playlist_type in ["uni", "mul"]:
            prefix = {"uni": "unicast", "mul": "multicast"}[playlist_type]
            infix = "-private" if mode == "private" else "-public"
            suffix = "-filtered" if filter else ""
            output_file = f"{self.playlist_dir}/{prefix}{infix}{suffix}-{area}.m3u"

            with Path(output_file).open("w", encoding="utf-8") as fp:
                fp.write(f'#EXTM3U url-tvg="{self.url_tvg}" \n')

                for ch in tqdm(
                    channels,
                    desc=f"[Generator] Processing {playlist_type} playlist",
                    unit="channel",
                ):
                    if not self.filter_channel(ch, mode, filter):
                        continue

                    tvg_name = ch.get("tvg_name", "")
                    tvg_logo = f"{self.logo_base}{tvg_name}.png"
                    group_title = ch.get("group_title", "")
                    catchup = ch.get("uni_playback")

                    if playlist_type == "uni":
                        url = ch.get("uni_live", "")
                    else:
                        from helpers.playlist import replace_third_ip_byte

                        url = f"{self.udpxy_base_url.format(replace_third_ip_byte(ch.get('mul_live', ''), area_code).replace('rtp://', 'rtp/'))}"

                    if not url:
                        continue

                    extinf = (
                        f"#EXTINF:-1 "
                        f'tvg-name="{tvg_name}" '
                        f'group-title="{group_title}" '
                        f'tvg-logo="{tvg_logo}" '
                    )

                    if catchup:
                        extinf += f'catchup="default" catchup-source="{catchup}"'

                    extinf += f", {tvg_name}"
                    fp.write(f"{extinf}\n{url}\n")

            print(
                f"[Generator] The {playlist_type} playlist has been saved to {output_file}."
            )

    def load_channels(self) -> list[dict]:
        with Path(self.formatted_file_path).open("r", encoding="utf-8") as fp:
            return json.load(fp)

    def sort_channels(self, channels: list[dict]) -> list[dict]:
        if not self.sort_file_name:
            return channels

        with Path(self.sort_file_name).open("r", encoding="utf-8") as fp:
            order_list = [
                line.strip()
                for line in fp
                if line.strip() and not line.strip().startswith("#")
            ]

        bucket: dict[str, list[dict]] = {}
        for ch in channels:
            bucket.setdefault(ch.get("ChannelName", ""), []).append(ch)

        ordered_channels: list[dict] = []
        remaining_channels: list[dict] = []

        for tid in order_list:
            ordered_channels.extend(bucket.pop(tid, []))

        for remaining in bucket.values():
            remaining_channels.extend(remaining)

        high_channels = [
            ch for ch in remaining_channels if "高清" in ch.get("ChannelName", "")
        ]
        low_channels = [
            ch for ch in remaining_channels if "高清" not in ch.get("ChannelName", "")
        ]

        return ordered_channels + high_channels + low_channels

    def filter_channel(self, ch: dict, mode: str, filter: bool) -> bool:

        ChannelName = ch.get("ChannelName", "")

        if (
            filter == True
            and mode == "private"
            and any(
                exclude_channel == ChannelName
                for exclude_channel in self.exclude_channel_list_private
            )
        ):
            return False

        if (
            filter == True
            and mode == "public"
            and any(
                exclude_channel == ChannelName
                for exclude_channel in self.exclude_channel_list_public
            )
        ):
            return False

        return True
