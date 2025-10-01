import subprocess, re, time


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
