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
udpxy_base_url = "http://192.168.0.1:4022"
logo_base = "https://raw.githubusercontent.com/plsy1/iptv/main/logo/"
url_tvg = "https://raw.githubusercontent.com/plsy1/epg/main/e/seven-days.xml.gz"

# 关键词匹配
group_keywords = {"": ""}
# 映射
tvg_name_map_by_tvg_id = {"": ""}
# 映射
tvg_name_map_by_tvg_name = {"": ""}
# 关键词匹配
exclude_channel_list = [""]
# 关键词匹配
playback_targets = [""]
# 精确匹配
exclude_playback_targets = [""]
