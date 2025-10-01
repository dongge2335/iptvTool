import subprocess
from urllib.parse import urlparse


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
