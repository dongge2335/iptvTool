import json, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from typing import Optional


class Formatter:
    def __init__(self, cfg: dict, common_config: dict, workers: Optional[int] = None):

        self.data_dir = common_config.get("data_dir")
        self.raw_file_name = common_config.get("raw_file_name")
        self.formatted_file_name = common_config.get("formatted_file_name")
        self.input_file_path = Path(self.data_dir) / self.raw_file_name
        self.output_file_path = Path(self.data_dir) / self.formatted_file_name
        
        self.timeshift = cfg.get("timeshift")
        self.group_title_map_by_channel_name_keywords = cfg.get(
            "group_title_map_by_channel_name_keywords", {}
        )
        self.tvg_name_map_by_tvg_id = cfg.get("tvg_name_map_by_tvg_id", {})
        self.tvg_name_map_by_tvg_name = cfg.get("tvg_name_map_by_tvg_name", {})
        self.channel_name_map_by_tvg_id = cfg.get("channel_name_map_by_tvg_id", {})
        self.workers = workers or cfg.get("workers", 10)
        self.results = []
        self.not_found = []


    def run(self):
        raw_data = self.load_raw()
        self.process_all(raw_data)
        self.sort_results()
        self.save_results()
        self.report_not_found()

    def _process_channel(self, channel):
        if "ChannelURL" not in channel or not channel["ChannelURL"].startswith(
            "igmp://"
        ):
            return (
                None,
                f"[Formatter] Channel '{channel.get('ChannelName', '?')}' does not have a ChannelURL. Skipping.",
            )

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
        tvg_name = self.tvg_name_map_by_tvg_id.get(tvg_id, tvg_name)
        tvg_name = self.tvg_name_map_by_tvg_name.get(tvg_name, tvg_name)

        ChannelName = self.channel_name_map_by_tvg_id.get(tvg_id, ChannelName)

        group_title = "其他频道"
        for keyword, title in self.group_title_map_by_channel_name_keywords.items():
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
                from utils.ffmpeg import get_redirected_rtsp_url

                redirected = get_redirected_rtsp_url(tmp, retries=5, delay=1)
                if redirected is not None:
                    uni_live = redirected
                    pattern = r"(rtsp://\S+:\d+).*?(ch\d*)"
                    match2 = re.search(pattern, uni_live)
                    if match2:
                        url = match2.group(1)
                        cid = match2.group(2)
                        uni_playback = f"{url}/iptv/Tvod/iptv/001/001/{cid}.rsc?tvdr={self.timeshift}"
                else:
                    warnings = f"[Formatter] no accessible unicast address for channel: {ChannelName}"

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

    def load_raw(self):
        with open(self.input_file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def process_all(self, json_data):
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(self._process_channel, ch): ch for ch in json_data
            }
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="[Formatter] Formatting raw data",
            ):
                record, warning = future.result()
                if record:
                    self.results.append(record)
                if warning:
                    self.not_found.append(warning)

    def sort_results(self):
        try:
            self.results.sort(key=lambda x: int(x["tvg_id"]))
        except ValueError:
            self.results.sort(key=lambda x: x["tvg_id"])

    def save_results(self):
        with open(self.output_file_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

    def report_not_found(self):
        if self.not_found:
            print("[Formatter] Encountered some issues:")
            for msg in self.not_found:
                print(f"- {msg}")
        else:
            print("[Formatter] All good.")
