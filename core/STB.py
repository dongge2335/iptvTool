import re, random, requests, binascii
from Crypto.Cipher import DES
from Crypto.Util.Padding import pad
from .config import (
    eas_ip,
    eas_port,
    epgIP,
    epgPort,
    userID,
    stbID,
    ip,
    MAC,
    CustomStr,
    encryptKey,
)


def UnionDesEncrypt(strMsg, strKey):
    try:
        keyappend = 8 - len(strKey)
        if keyappend > 0:
            strKey = strKey + "0" * keyappend

        key_bytes = strKey.encode("utf-8")
        msg_bytes = strMsg.encode("utf-8")

        padded_msg = pad(msg_bytes, DES.block_size)

        cipher = DES.new(key_bytes, DES.MODE_ECB)
        encrypted = cipher.encrypt(padded_msg)

        return binascii.hexlify(encrypted).decode("utf-8").upper()

    except Exception as e:
        print(f"UnionDesEncrypt: {e}")


class IPTVClient:
    def __init__(self):
        self.session = requests.Session()
        self.encrypt_token = None
        self.jsessionid = None
        self.user_token = None

    def login(self):
        url = f"http://{eas_ip}:{eas_port}/iptvepg/platform/getencrypttoken.jsp"
        params = {
            "UserID": userID,
            "Action": "Login",
            "TerminalFlag": "1",
            "TerminalOsType": "0",
            "STBID": "",
            "stbtype": "",
        }
        r = self.session.get(url, params=params, timeout=5)
        r.raise_for_status()
        m = re.search(r"GetAuthInfo\('(.*?)'\)", r.text)
        if not m:
            raise RuntimeError("登录失败: encryptToken 未获取")
        self.encrypt_token = m.group(1)

    def auth(self):
        rand = random.randint(10_000_000, 99_999_999)
        src = f"{rand}${self.encrypt_token}"
        src2 = f"{src}${userID}${stbID}${ip}${MAC}${CustomStr}"
        authenticator = UnionDesEncrypt(src2, encryptKey)
        url = f"http://{epgIP}:{epgPort}/iptvepg/platform/auth.jsp"
        data = {
            "easip": eas_ip,
            "ipVersion": "4",
            "networkid": "1",
            "serterminalno": "311",
            "UserID": userID,
            "Authenticator": authenticator,
            "StbIP": ip,
        }
        r = self.session.post(url, data=data, timeout=5)
        r.raise_for_status()
        self.jsessionid = r.cookies.get("JSESSIONID")

        m = re.search(r"window\.location\s*=\s*'(http[^']+)'", r.content.decode("gbk"))
        if not m:
            raise RuntimeError("鉴权失败: 跳转地址未找到")

        redirect_url = m.group(1)
        r2 = self.session.post(
            redirect_url, headers={"Cookie": f"JSESSIONID={self.jsessionid}"}, timeout=5
        )
        r2.raise_for_status()
        m2 = re.search(r"UserToken=([A-Za-z0-9_\-\.]+)", redirect_url)
        if not m2:
            raise RuntimeError("鉴权失败: user_token 未获取")
        self.user_token = m2.group(1)

    def portal_auth(self):
        url = f"http://{epgIP}:{epgPort}/iptvepg/function/funcportalauth.jsp"
        headers = {"Cookie": f"JSESSIONID={self.jsessionid}"}
        data = {
            "UserToken": self.user_token,
            "UserID": userID,
            "STBID": stbID,
            "stbinfo": "",
            "prmid": "",
            "easip": eas_ip,
            "networkid": 1,
            "stbtype": "",
            "drmsupplier": "",
            "stbversion": "",
        }
        r = self.session.post(url, headers=headers, data=data, timeout=5)
        r.raise_for_status()

    def get_channels(self):
        url = f"http://{epgIP}:{epgPort}/iptvepg/function/frameset_builder.jsp"
        headers = {"Cookie": f"JSESSIONID={self.jsessionid}"}
        data = {
            "MAIN_WIN_SRC": "/iptvepg/frame205/channel_start.jsp?tempno=-1",
            "NEED_UPDATE_STB": "1",
            "BUILD_ACTION": "FRAMESET_BUILDER",
            "hdmistatus": "undefined",
        }
        r = self.session.post(url, headers=headers, data=data, timeout=5)
        r.raise_for_status()
        text = r.content.decode("gbk")
        channels = []
        for line in text.splitlines():
            m = re.search(r"jsSetConfig\('Channel',\s*'([^']+)'\)", line)
            if m:
                cfg = dict(re.findall(r"(\w+)=\"([^\"]+)\"", m.group(1)))
                channels.append(cfg)
        return channels
