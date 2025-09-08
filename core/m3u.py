import json
from pathlib import Path
from .config import *


def gen_m3u_playlist(
    json_file: str, output_file: str, mode: str = "uni", sort_file: str | None = None
) -> None:
    """
    生成 M3U 播放列表，可按 sort_file 指定顺序写入
    :param json_file: JSON 数据文件
    :param output_file: 输出的 .m3u 路径
    :param mode: 'uni' 单播；'mul' 组播
    :param sort_file: 包含 tvg_name 的排序文件，一行一个；若为 None 则保持原顺序
    """
    with Path(json_file).open("r", encoding="utf-8") as fp:
        channels: list[dict] = json.load(fp)

    if sort_file:
        with Path(sort_file).open("r", encoding="utf-8") as fp:
            order_list = [
                line.strip()
                for line in fp
                if line.strip() and not line.strip().startswith("#")
            ]

        bucket: dict[str, list[dict]] = {}
        for ch in channels:
            bucket.setdefault(ch.get("tvg_name", ""), []).append(ch)

        ordered_channels: list[dict] = []
        remaining_channels: list[dict] = []

        for tid in order_list:
            ordered_channels.extend(bucket.pop(tid, []))

        for remaining in bucket.values():
            remaining_channels.extend(remaining)

        high_channels = [
            ch for ch in remaining_channels if "高清" in ch.get("channel_name", "")
        ]
        low_channels = [
            ch for ch in remaining_channels if "高清" not in ch.get("channel_name", "")
        ]

        channels = ordered_channels + high_channels + low_channels

    with Path(output_file).open("w", encoding="utf-8") as fp:
        fp.write(f'#EXTM3U url-tvg="{url_tvg}" \n')

        for ch in channels:
            channel_name = ch.get("channel_name", "")
            tvg_id = ch.get("tvg_id", "")
            tvg_name = ch.get("tvg_name", "")
            channel_name = name_map_by_name.get(channel_name, channel_name)
            channel_name = name_map_by_id.get(tvg_id, channel_name)

            group_title = ch.get("group_title", "")

            if mode == "uni":
                url = ch.get("uni_live", "")
            else:
                url = ch.get("udpxy_url", "").replace("rtp://",'rtp/')
                url = f'{udpxy_base_url}/{url}'

            if not url:
                continue

            tvg_logo = f"{logo_base}{name_map_by_name.get(channel_name, channel_name)}.png"

            extinf = (
                f"#EXTINF:-1 "
                f'tvg-name="{tvg_name}" '
                f'group-title="{group_title}" '
                f'tvg-logo="{tvg_logo}" '
            )

            catchup = ch.get("uni_playback")
            if catchup:
                extinf += f'catchup="default" catchup-source="{catchup}"'

            extinf += f", {channel_name}"
            fp.write(f"{extinf}\n{url}\n")
