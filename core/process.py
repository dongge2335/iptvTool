import json
import re
from .ffmpeg import *
from .config import *
from concurrent.futures import ThreadPoolExecutor, as_completed


def process_channel(channel):
    if "ChannelURL" not in channel or not channel["ChannelURL"].startswith("igmp://"):
        return None, f"频道 {channel.get('ChannelName', '?')} 没有 ChannelURL, 跳过"

    udpxy_url = channel["ChannelURL"].replace("igmp://", "rtp://")
    tvg_id = channel["UserChannelID"]
    tvg_name = channel["ChannelName"]
    channel_name = (
        tvg_name.replace("超高清", "")
        .replace("高清", "")
        .replace("标清", "")
        .replace(" ", "")
    )

    group_title = "其他频道"
    for keyword, group in group_keywords.items():
        if keyword in tvg_name:
            group_title = group
            break

    uni_live = ""
    uni_playback = ""
    warnings = None

    if "ChannelSDP" in channel:
        print(f"Processing: {tvg_name}")
        match = re.search(r"rtsp://\S+", channel["ChannelSDP"])
        if match:
            tmp = match.group(0)
            redirected = get_redirected_rtsp_with_retry(tmp, retries=2, delay=1)

            if redirected is not None:
                uni_live = redirected
                pattern = r"(rtsp://\S+:\d+).*?(ch\d*)"
                match2 = re.search(pattern, uni_live)
                if match2:
                    url = match2.group(1)
                    cid = match2.group(2)
                    uni_playback = (
                        f"{url}/iptv/Tvod/iptv/001/001/{cid}.rsc?tvdr={timeshift}"
                    )
            else:
                warnings = f"未找到单播地址: {tvg_name}"

    record = {
        "tvg_id": tvg_id,
        "tvg_name": tvg_name,
        "group_title": group_title,
        "channel_name": channel_name,
        "udpxy_url": udpxy_url,
        "uni_live": uni_live,
        "uni_playback": uni_playback,
    }

    return record, warnings


def gen_iptv_json():
    with open("raw.json", "r", encoding="utf-8") as file:
        json_data = json.load(file)

    results = []
    not_found = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_channel, ch): ch for ch in json_data}
        for future in as_completed(futures):
            record, warning = future.result()
            if record:
                results.append(record)
            if warning:
                not_found.append(warning)

    try:
        results.sort(key=lambda x: int(x["tvg_id"]))
    except ValueError:
        results.sort(key=lambda x: x["tvg_id"])

    with open("iptv.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    if not_found:
        print("=== 未找到单播地址的频道 ===")
        for msg in not_found:
            print(msg)


def extract_channel_names(json_file="raw.json", output_file="channels.txt"):
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

        if existing_channels == json_channel_names:
            print("未发现频道变动")
        else:
            print("发现频道变动")
            added = [c for c in json_channel_names if c not in existing_channels]
            removed = [c for c in existing_channels if c not in json_channel_names]
            if added:
                print(f"新增频道: {added}")
            if removed:
                print(f"移除频道: {removed}")

        with open(output_file, "w", encoding="utf-8") as f:
            for name in json_channel_names:
                f.write(name + "\n")

    except Exception as e:
        print(f"发生错误: {e}")


def generate_unused_multicast_m3u(
    json_file="raw.json", output_file="unused.m3u"
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
    print(f"未使用的组播地址已保存到 {output_file}")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in noUse:
            extinf = f"#EXTINF:-1 "
            extinf += f",{ch}"
            f.write(
                f"{extinf}\n{f'http://192.168.0.1:4022/rtp/239.253.240.{ch}:8000'}\n"
            )


def process_raw(json_file="raw.json"):
    """
    根据 UserChannelID 更新 ChannelName
    """
    with open(json_file, "r", encoding="utf-8") as file:
        json_data = json.load(file)

    for channel in json_data:
        user_id = channel.get("UserChannelID")
        if user_id in ChannelName_map_by_id:
            channel["ChannelName"] = ChannelName_map_by_id[user_id]

    with open(json_file, "w", encoding="utf-8") as file:
        json.dump(json_data, file, ensure_ascii=False, indent=2)

