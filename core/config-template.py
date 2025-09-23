# STB.py

eas_ip = ""
eas_port = ""
epgIP = ""
epgPort = ""
userID = ""
stbID = ""
ip = ""
MAC = ""
CustomStr = "$CTC"
encryptKey = ""

# process.py

timeshift = "{utc:YmdHMS}GMT-{utcend:YmdHMS}GMT"

group_keywords = {
    "CCTV": "央视频道",
    "山东": "山东频道",
}

tvg_name_map_by_tvg_id = {
    "8": "CCTV5+",
}

tvg_name_map_by_tvg_name = {
    "CCTV少儿": "CCTV14",
    "CCTV4中文国际欧洲": "CCTV4欧洲",
    "CCTV4中文国际美洲": "CCTV4美洲",
    "CCTV17农业": "CCTV17",
    "CGTN英语": "CGTN",
    "CGTN英文纪录": "CGTN纪录",
    "CGTN西班牙语": "CGTN西语",
    "CGTN阿拉伯语": "CGTN阿语",
    "山东教育卫视": "山东教育",
    "山东广播电视台经济广播": "山东经济广播",
    "海洋频道": "山东海洋频道",
    "KAKU少儿": "卡酷少儿",
    "汽摩频道": "汽摩",
    "齐鲁":"山东齐鲁",
    "居家购物":"山东居家购物"
}


# m3u.py

udpxy_base_url = "http://192.168.0.1:4022"
logo_base = "https://raw.githubusercontent.com/plsy1/iptv/main/logo/"
url_tvg = "https://raw.githubusercontent.com/plsy1/epg/main/e/seven-days.xml.gz,https://e.erw.cc/all.xml.gz"
