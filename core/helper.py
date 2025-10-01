import json, re, time, subprocess
from .config import *
import subprocess
from urllib.parse import urlparse
from datetime import datetime, timedelta


def get_redirected_rtsp_url(url, retries=5, delay=1, timeout=5):
    """
    获取 RTSP 重定向地址（带重试）
    :param url: 原始 RTSP 地址
    :param retries: 最大重试次数
    :param delay: 每次重试间隔秒数
    :param timeout: ffprobe 命令超时时间（秒）
    :return: 重定向地址或 None
    """
    command = ["ffprobe", "-print_format", "json", "-i", url]

    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=True, timeout=timeout
            )
            output = result.stderr
            match = re.search(r"Redirecting to (rtsp://[^\s]+Uni\.sdp)", output)
            if match:
                return match.group(1)
        except subprocess.TimeoutExpired:
            pass
        except subprocess.CalledProcessError:
            pass
        except Exception as e:
            pass

        if attempt < retries:
            time.sleep(delay)

    return None


def probe_info_by_url(url, timeout=5):
    """
    获取媒体信息，返回 dict 包含 programs、video/audio streams 等。
    """
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        "-show_programs",
        url,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=timeout
        )
        info = json.loads(proc.stdout)
        if "programs" in info and len(info["programs"]) > 0:
            program_tags = info["programs"][0].get("tags", {})
            info["service_name"] = program_tags.get("service_name")
            info["service_provider"] = program_tags.get("service_provider")
        else:
            info["service_name"] = None
            info["service_provider"] = None

        return info
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}


def process_channel(channel):
    if "ChannelURL" not in channel or not channel["ChannelURL"].startswith("igmp://"):
        return None, f"频道 {channel.get('ChannelName', '?')} 没有 ChannelURL, 跳过"

    ChannelName = channel["ChannelName"]
    ChannelID = channel["ChannelID"]

    tvg_id = channel["UserChannelID"]

    tvg_name = (
        channel["ChannelName"]
        .replace("超高清", "")
        .replace("高清", "")
        .replace("标清", "")
        .replace(" ", "")
    )
    tvg_name = tvg_name_map_by_tvg_id.get(tvg_id, tvg_name)
    tvg_name = tvg_name_map_by_tvg_name.get(tvg_name, tvg_name)

    group_title = "其他频道"

    for keyword, title in group_keywords.items():
        if keyword in ChannelName:
            group_title = title
            break

    mul_live = channel["ChannelURL"].replace("igmp://", "rtp://")
    uni_live = ""
    uni_playback = ""
    warnings = None

    if "ChannelSDP" in channel:
        match = re.search(r"rtsp://\S+", channel["ChannelSDP"])
        if match:
            tmp = match.group(0)
            redirected = get_redirected_rtsp_url(tmp, retries=5, delay=1)
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
                warnings = f"未找到单播地址: {ChannelName}"

    record = {
        "ChannelID": ChannelID,
        "ChannelName": ChannelName,
        "tvg_id": tvg_id,
        "tvg_name": tvg_name,
        "group_title": group_title,
        "mul_live": mul_live,
        "uni_live": uni_live,
        "uni_playback": uni_playback,
    }

    return record, warnings


def test_ffmpeg_rtsp(url, timeout=3):
    """
    用 FFmpeg 尝试拉 RTSP 流，返回 True 表示能拉通，False 表示失败
    """
    cmd = [
        "ffmpeg",
        "-rtsp_transport",
        "udp",
        "-i",
        url,
        "-t",
        "1",
        "-f",
        "null",
        "-",
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=True,
        )
        return True
    except Exception:
        return False


def get_yyyyMMddHHmmss_time(days=0, hours=0, minutes=0):
    """
    返回偏移后的时间，格式: yyyyMMddHHmmss
    days: 偏移天数，可正可负
    hours: 偏移小时
    minutes: 偏移分钟
    """
    target_time = datetime.now() + timedelta(days=days, hours=hours, minutes=minutes)
    return target_time.strftime("%Y%m%d%H%M%S")


def test_ip_connectivity(url, start=1, end=254):
    """
    测试 RTSP URL 中 IP 最后一段从 start 到 end 哪个可连通。
    只修改 IP，tvdr 保持原样。
    返回第一个可连通的 URL 或 None
    """
    parsed = urlparse(url)
    ip_parts = parsed.hostname.split(".")

    for last_octet in range(start, end + 1):
        ip_parts[-1] = str(last_octet)
        ip_candidate = ".".join(ip_parts)
        test_url = url.replace(parsed.hostname, ip_candidate)

        if test_ffmpeg_rtsp(test_url):
            return last_octet

    return None


def find_playback(channel, offset: int):
    """处理单个频道，返回处理后的 channel dict"""
    uni_playback = channel.get("uni_playback")
    channel_name = channel.get("ChannelName")

    if not uni_playback or not channel_name:
        return channel

    if not any(ch in channel_name for ch in playback_targets):
        return channel

    if any(channel_name == ch for ch in exclude_playback_targets):
        return channel

    begin_time = get_yyyyMMddHHmmss_time(days=-offset, minutes=-30)
    end_time = get_yyyyMMddHHmmss_time(offset)

    uni_playback_filled = uni_playback.replace("{utc:YmdHMS}", begin_time).replace(
        "{utcend:YmdHMS}", end_time
    )

    if test_ffmpeg_rtsp(uni_playback_filled):
        print(f"获取回看地址 offset = {offset}: {channel_name}, 原地址可用，跳过")
        return channel

    success = test_ip_connectivity(uni_playback_filled, 36, 48) or test_ip_connectivity(
        uni_playback_filled, 68, 74
    )

    if success:
        print(f"获取回看地址 offset = {offset}: {channel_name}, 获取成功")
        parsed = urlparse(uni_playback)
        ip_parts = parsed.hostname.split(".")
        ip_parts[-1] = str(success)
        new_ip = ".".join(ip_parts)
        new_url = uni_playback.replace(parsed.hostname, new_ip)
        channel["uni_playback"] = new_url

    else:
        print(f"{channel_name} 无可用7天回看地址")

    return channel
