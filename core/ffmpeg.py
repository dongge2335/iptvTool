import json
import re
import time
import subprocess


def get_redirected_rtsp_with_retry(url, retries=3, delay=1):
    """
    尝试获取 RTSP 重定向地址，失败时重试
    :param url: 原始 RTSP 地址
    :param retries: 最大重试次数
    :param delay: 每次重试间隔秒数
    :return: 重定向地址或者 None
    """
    for attempt in range(1, retries + 1):
        redirected = get_redirected_rtsp(url)
        if redirected is not None:
            return redirected
        else:
            if attempt < retries:
                print(f"第 {attempt} 次未获取到重定向地址，等待 {delay}s 后重试...")
                time.sleep(delay)
    return None

def get_redirected_rtsp(rtsp_url):
    command = ["ffprobe", "-print_format", "json", "-i", rtsp_url]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=True, timeout=5
        )
        output = result.stderr

        redirect_match = re.search(r"Redirecting to (rtsp://[^\s]+Uni\.sdp)", output)
        if redirect_match:
            return redirect_match.group(1)
    except Exception as e:
        print(f"Error occurred while running ffprobe: {e}")
        return None

    return None

def get_rtsp_resolution_level(rtsp_url):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        rtsp_url,
    ]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=True, timeout=5
        )
        info = json.loads(result.stdout)

        if "streams" in info and len(info["streams"]) > 0:
            width = info["streams"][0].get("width")
            height = info["streams"][0].get("height")

            if not width or not height:
                return None

            if width <= 720 and height <= 480:
                level = "SD"
            elif width <= 1280 and height <= 720:
                level = "HD"
            elif width <= 1920 and height <= 1080:
                level = "FHD"
            else:
                level = "UHD"

            return {"width": width, "height": height, "level": level}

    except Exception as e:
        print(f"Error occurred while running ffprobe: {e}")
        return None

    return None
