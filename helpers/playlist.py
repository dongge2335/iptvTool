def replace_third_ip_byte(url: str, new_byte: int) -> str:
    """
    替换 rtp:// 或 IP 地址字符串的第三个字节

    :param url: RTP URL，例如 "rtp://239.253.240.77:8000"
    :param new_byte: 新的第三个字节值，0~255
    :return: 替换后的 URL
    """
    if not (0 <= new_byte <= 255):
        raise ValueError("new_byte 必须在 0~255 之间")

    if "://" in url:
        protocol, rest = url.split("://", 1)
    else:
        protocol, rest = "", url

    if ":" in rest:
        host, port = rest.split(":", 1)
    else:
        host, port = rest, ""

    ip_parts = host.split(".")
    if len(ip_parts) != 4:
        raise ValueError("IP 地址格式不正确")

    ip_parts[2] = str(new_byte)
    new_host = ".".join(ip_parts)

    new_url = f"{protocol}://{new_host}"
    if port:
        new_url += f":{port}"

    return new_url
