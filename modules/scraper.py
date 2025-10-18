import re, random, json, requests
from pathlib import Path


class Scraper:
    def __init__(self, cfg: dict, common_config: dict):
        self.eas_ip = cfg["eas_ip"]
        self.eas_port = cfg["eas_port"]
        self.user_id = cfg["user_id"]
        self.stb_id = cfg["stb_id"]
        self.mac = cfg["mac"]
        self.custom_str = cfg["custom_str"]
        self.encrypt_key = cfg["encrypt_key"]

        self.data_dir = common_config.get("data_dir")
        self.raw_file_name = common_config.get("raw_file_name")

        self.output_path = Path(self.data_dir) / self.raw_file_name

        self.stbIP = None
        self.encrypt_token = None
        self.jsession_id = None
        self.epg_ip = None
        self.epg_port = None
        self.session = requests.Session()

    def run(self):
        self.login()
        self.auth()
        self.portal_auth()
        self.get_channels()

    def login(self):
        url = (
            f"http://{self.eas_ip}:{self.eas_port}/iptvepg/platform/getencrypttoken.jsp"
        )
        params = {
            "UserID": self.user_id,
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
            raise RuntimeError(
                "[Scraper] Login failed: encryptToken could not be retrieved."
            )

        match = re.search(r'<form[^>]+action="([^"]+)"', r.text)
        if match:
            self.auth_jsp_url = match.group(1)

        html = r.text

        stbip_match = re.search(r'<input[^>]+name="StbIP"[^>]+value="([^"]+)"', html)
        self.stbIP = stbip_match.group(1) if stbip_match else None

        action_match = re.search(r'<form[^>]+action="([^"]+)"', html)
        action_url = action_match.group(1) if action_match else ""

        host_match = re.search(r"://([^:/]+):(\d+)", action_url)
        if host_match:
            self.epg_ip = host_match.group(1)
            self.epg_port = host_match.group(2)

        self.encrypt_token = m.group(1)

    def auth(self):
        rand = random.randint(10_000_000, 99_999_999)
        src = f"{rand}${self.encrypt_token}"
        src2 = f"{src}${self.user_id}${self.stb_id}${self.stbIP}${self.mac}${self.custom_str}"
        from helpers.scraper import UnionDesEncrypt

        self.authenticator = UnionDesEncrypt(src2, self.encrypt_key)
        data = {
            "easip": self.eas_ip,
            "ipVersion": "4",
            "networkid": "1",
            "serterminalno": "311",
            "UserID": self.user_id,
            "Authenticator": self.authenticator,
            "StbIP": self.stbIP,
        }
        r = self.session.post(self.auth_jsp_url, data=data, timeout=5)
        r.raise_for_status()
        self.jsession_id = r.cookies.get("JSESSIONID")

        m = re.search(r"window\.location\s*=\s*'(http[^']+)'", r.content.decode("gbk"))
        if not m:
            raise RuntimeError(
                "[Scraper] Authentication failed: Redirect URL not found."
            )

        redirect_url = m.group(1)
        r2 = self.session.post(
            redirect_url,
            headers={"Cookie": f"JSESSIONID={self.jsession_id}"},
            timeout=5,
        )
        r2.raise_for_status()
        m2 = re.search(r"UserToken=([A-Za-z0-9_\-\.]+)", redirect_url)
        if not m2:
            raise RuntimeError(
                "[Scraper] Authentication failed: user_token not retrieved."
            )
        self.user_token = m2.group(1)

    def portal_auth(self):
        url = (
            f"http://{self.epg_ip}:{self.epg_port}/iptvepg/function/funcportalauth.jsp"
        )
        headers = {"Cookie": f"JSESSIONID={self.jsession_id}"}
        data = {
            "UserToken": self.user_token,
            "UserID": self.user_id,
            "STBID": self.stb_id,
            "stbinfo": "",
            "prmid": "",
            "easip": self.eas_ip,
            "networkid": 1,
            "stbtype": "E900V21C",
            "drmsupplier": "",
            "stbversion": "2.00.07",
        }
        try:
            r = self.session.post(url, headers=headers, data=data, timeout=5)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[Scraper] Authentication failed: {e}")
            return None

    def get_channels(self):
        url = f"http://{self.epg_ip}:{self.epg_port}/iptvepg/function/frameset_builder.jsp"
        headers = {"Cookie": f"JSESSIONID={self.jsession_id}"}
        data = {
            "MAIN_WIN_SRC": "/iptvepg/frame205/channel_start.jsp?tempno=-1",
            "NEED_UPDATE_STB": "1",
            "BUILD_ACTION": "FRAMESET_BUILDER",
            "hdmistatus": "undefined",
        }

        try:
            r = self.session.post(url, headers=headers, data=data, timeout=5)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[Scraper] Failed to fetch data: {e}")
            return

        text = r.content.decode("gbk")
        channels = []

        for line in text.splitlines():
            match = re.search(r"jsSetConfig\('Channel',\s*'([^']+)'\)", line)
            if match:
                cfg = dict(re.findall(r"(\w+)=\"([^\"]+)\"", match.group(1)))
                channels.append(cfg)

        if channels:
            try:
                with open(self.output_path, "w", encoding="utf-8") as f:
                    json.dump(channels, f, ensure_ascii=False, indent=4)
                print("[Scraper] Raw data fetched and saved successfully.")
            except IOError as e:
                print(f"[Scraper] Failed to write to file: {e}")
        else:
            print("[Scraper] No channels found in the fetched data.")
