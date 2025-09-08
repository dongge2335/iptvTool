import json
import re
from .ffmpeg import *
from .config import *


def gen_iptv_json():
    with open("raw.json", "r", encoding="utf-8") as file:
        json_data = json.load(file)

    filename = "iptv.json"

    with open(filename, "w", encoding="utf-8") as f:
        f.write("[]")

    for channel in json_data:
        if "ChannelURL" in channel and channel["ChannelURL"].startswith("igmp://"):
            udpxy_url = f"{channel['ChannelURL'].replace('igmp://', 'rtp://')}"
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
        else:
            print(f"频道 {channel.get('ChannelName', '?')} 没有 ChannelURL,跳过")
            continue

        uni_live = "Not Found"
        uni_playback = "Not Found"
        
        if "ChannelSDP" in channel:
            print(f"Processing: {tvg_name}")
            match = re.search(r"rtsp://\S+", channel["ChannelSDP"])
            if match:
                uni_live = match.group(0)
                redirected = get_redirected_rtsp_with_retry(uni_live, retries=2, delay=1)

                if redirected is not None:
                    uni_live = redirected
                    pattern = r"(rtsp://\S+:\d+).*?(ch\d*)"
                    match2 = re.search(pattern, uni_live)
                    if match2:
                        url = match2.group(1)
                        cid = match2.group(2)
                        uni_playback = f"{url}/iptv/Tvod/iptv/001/001/{cid}.rsc?tvdr={timeshift}"
                else:
                    print(f"未找到单播地址: {tvg_name}")

        record = {
            "tvg_id": tvg_id,
            "tvg_name": tvg_name,
            "group_title": group_title,
            "channel_name": channel_name,
            "udpxy_url": udpxy_url,
            "uni_live": uni_live,
            "uni_playback": uni_playback,
        }

        with open(filename, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                data = []

        data.append(record)

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


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
            print("现有 channels.txt 与 JSON 中的 ChannelName 完全一致 ✅")
        else:
            print("现有 channels.txt 与 JSON 中的 ChannelName 不一致 ❌")
            added = [c for c in json_channel_names if c not in existing_channels]
            removed = [c for c in existing_channels if c not in json_channel_names]
            if added:
                print(f"JSON 新增频道: {added}")
            if removed:
                print(f"channel.txt 移除频道: {removed}")

        with open(output_file, "w", encoding="utf-8") as f:
            for name in json_channel_names:
                f.write(name + "\n")

    except Exception as e:
        print(f"发生错误: {e}")


def generate_unused_multicast_m3u(
    json_file="raw.json", output_file="multicast.unused.m3u"
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
        user_id = channel.get('UserChannelID')
        if user_id in ChannelName_map_by_id:
            channel['ChannelName'] = ChannelName_map_by_id[user_id]

    with open(json_file, "w", encoding="utf-8") as file:
        json.dump(json_data, file, ensure_ascii=False, indent=2)

    print(f"已根据 name_map_by_id 更新 {json_file} 中的 ChannelName")
            