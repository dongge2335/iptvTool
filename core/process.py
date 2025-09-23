import json, re
from pathlib import Path
from .helper import *
from .config import *
from .STB import IPTVClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from datetime import datetime, timedelta, timezone


def get_iptv_raw():
    print("获取 IPTV 原始数据...")
    client = IPTVClient()
    client.login()
    client.auth()
    client.portal_auth()
    channels = client.get_channels()
    with open("data/raw.json", "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=4)


def gen_iptv_json():
    with open("data/raw.json", "r", encoding="utf-8") as file:
        json_data = json.load(file)

    results = []
    not_found = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_channel, ch): ch for ch in json_data}
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="格式化 IPTV 原始数据..."
        ):
            record, warning = future.result()
            if record:
                results.append(record)
            if warning:
                not_found.append(warning)

    try:
        results.sort(key=lambda x: int(x["tvg_id"]))
    except ValueError:
        results.sort(key=lambda x: x["tvg_id"])

    with open("data/iptv.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    if not_found:
        print("=== 未找到单播地址的频道 ===")
        for msg in not_found:
            print(msg)


def gen_m3u_playlist(
    output_path="playlist",
    json_file="data/iptv.json",
    mode: str = "uni",
    sort_file: str | None = None,
) -> None:
    """
    生成 M3U 播放列表，可按 sort_file 指定顺序写入
    :param json_file: JSON 数据文件
    :param output_file: 输出的 .m3u 路径
    :param mode: 'uni' 单播；'mul' 组播
    :param sort_file: 包含 ChannelName 的排序文件，一行一个；若为 None 则保持原顺序
    """
    from pathlib import Path

    Path(output_path).mkdir(parents=True, exist_ok=True)

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

        channels = ordered_channels + high_channels + low_channels

    if mode == "uni":
        output_file = f"{output_path}/unicast.m3u"
    elif mode == "mul":
        output_file = f"{output_path}/multicast.m3u"

    with Path(output_file).open("w", encoding="utf-8") as fp:
        fp.write(f'#EXTM3U url-tvg="{url_tvg}" \n')

        for ch in channels:
            catchup = ch.get("uni_playback")
            if catchup.startswith("rtsp://222") and mode == "uni":
                continue

            tvg_name = ch.get("tvg_name", "")

            tvg_logo = f"{logo_base}{tvg_name}.png"
            group_title = ch.get("group_title", "")

            if mode == "uni":
                url = ch.get("uni_live", "")
            elif mode == "mul":
                url = ch.get("udpxy_url", "").replace("rtp://", "rtp/")
                url = f"{udpxy_base_url}/{url}"
            if not url:
                continue

            extinf = (
                f"#EXTINF:-1 "
                f'tvg-name="{tvg_name}" '
                # f'tvg-id="{tvg_id}" '
                f'group-title="{group_title}" '
                f'tvg-logo="{tvg_logo}" '
            )

            if catchup:
                extinf += f'catchup="default" catchup-source="{catchup}"'

            extinf += f", {tvg_name}"
            fp.write(f"{extinf}\n{url}\n")

    print(f"播放列表已保存到 {output_file}")


def diff_channel_lists(json_file="data/raw.json", output_file="data/channels.txt"):
    """
    从 JSON 文件读取 ChannelName 并写入文本文件，同时与已有 channel.txt 对比是否一致
    :param json_file: 输入的 JSON 文件路径
    :param output_file: 输出的 TXT 文件路径
    """
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        json_channel_names = [
            item["ChannelName"] for item in data if "ChannelName" in item
        ]

        try:
            with open(output_file, "r", encoding="utf-8") as f:
                existing_channels = [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            existing_channels = []
            print(f"{output_file} 不存在，将创建新的文件")

        final_message = ""
        ifWrite = False

        if existing_channels == json_channel_names:
            final_message = "频道列表未变动"
        else:
            ifWrite = True
            added = [c for c in json_channel_names if c not in existing_channels]
            removed = [c for c in existing_channels if c not in json_channel_names]

            parts = []
            if added:
                parts.append("上线频道: " + ", ".join(added))
            if removed:
                parts.append("下线频道: " + ", ".join(removed))

            final_message = "\n".join(parts)

        print(final_message)

        if ifWrite == True:
            now_str = datetime.now().strftime("%Y-%m-%d")
            with open("data/channel-change.md", "a", encoding="utf-8") as f:
                f.write(f"#### 时间: {now_str}\n")
                f.write(final_message + "\n\n")

        with open(output_file, "w", encoding="utf-8") as f:
            for name in json_channel_names:
                f.write(name + "\n")

    except Exception as e:
        print(f"发生错误: {e}")


def generate_unused_multicast_m3u(
    json_file="data/raw.json", output_file="data/unused.m3u"
):
    used = []
    noUse = []
    with open(json_file, "r", encoding="utf-8") as file:
        json_data = json.load(file)
        for channel in json_data:

            if "ChannelURL" in channel and channel["ChannelURL"].startswith("igmp://"):
                url = channel["ChannelURL"].replace("igmp://", "")
                matches = re.findall(r"\b(?:\d{1,3}\.){3}(\d{1,3})\b", url)
                used.append(int(matches[0]))
        for i in range(0, 256):
            if i not in used:
                noUse.append(i)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in noUse:
            extinf = f"#EXTINF:-1 "
            extinf += f",{ch}"
            f.write(
                f"{extinf}\n{f'http://192.168.0.1:4022/rtp/239.253.240.{ch}:8000'}\n"
            )

    print(f"未使用的组播地址已保存到 {output_file}")


def probe_unused_multicast(
    json_file="data/raw.json",
    timeout=10,
    output_file="data/probe-unused.json",
    max_workers=1,
):
    """
    多线程调用 probe_info 获取未使用组播的 ffprobe JSON。
    返回列表，每项为 {"addr": int, "info": dict}
    """
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    used = {
        int(m.group(1))
        for ch in data
        if (m := re.search(r"\b(?:\d{1,3}\.){3}(\d{1,3})\b", ch.get("ChannelURL", "")))
    }

    unused = [i for i in range(1, 256) if i not in used]

    def worker(ch):
        url = f"{udpxy_base_url}/rtp/239.253.240.{ch}:8000"
        print("Probing:", url)
        info = probe_info_by_url(url, timeout=timeout)
        return {"addr": ch, "info": info}

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for res in executor.map(worker, unused):
            results.append(res)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    return results


def probe_unicast(
    json_file="data/raw.json",
    timeout=10,
    output_file="data/probe-unicast.json",
    max_workers=8,
):
    """
    多线程调用 probe_info 获取单播的 ffprobe JSON。
    返回列表，每项为 {"name": str, "info": dict}
    """
    channels = []
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    for channel in data:
        if "ChannelSDP" in channel:
            match = re.search(r"rtsp://\S+", channel["ChannelSDP"])
            if match:
                url = match.group(0)
                channels.append({"name": channel["ChannelName"], "url": url})

    def worker(ch):
        print("Probing:", ch["name"])
        info = probe_info_by_url(ch["url"], timeout=timeout)
        return {"name": ch["name"], "info": info}

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for res in executor.map(worker, channels):
            results.append(res)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)


def test_auth():
    with open("data/raw.json", "r", encoding="utf-8") as file:
        json_data = json.load(file)
        for channel in json_data:
            if channel.get("ChannelName") == "环球旅游标清":
                match = re.search(r"rtsp://\S+", channel["ChannelSDP"])
                if match:
                    tmp = match.group(0)
                    redirected = get_redirected_rtsp_url(tmp)
                    if redirected.startswith("rtsp://222"):
                        print("需要鉴权")
                    else:
                        print("无需鉴权")


def json_to_md_table(json_file="data/iptv.json", md_file="data/channels.md"):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_channels = len(data)

    tz_utc8 = timezone(timedelta(hours=8))
    now_str = datetime.now(tz=tz_utc8).strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "## 📺 频道列表\n",
        f"**更新时间**: {now_str} UTC+8\n\n"
        f"**频道总数**: {total_channels}\n\n"
        "| 频道名称 | 频道号 | 组播号 |",
        "|----------|--------|--------|",
    ]

    for ch in data:
        name = ch.get("ChannelName", "")
        tvg_id = ch.get("tvg_id", "")

        channel_url = ch.get("udpxy_url", "")
        mcast_number = ""
        if channel_url.startswith("rtp://"):
            match = re.search(r"\.(\d+):\d+$", channel_url)
            if match:
                mcast_number = match.group(1)

        lines.append(f"| {name} | {tvg_id} | {mcast_number} |")

    with open(md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("频道列表 Markdown 文件 已生成")
