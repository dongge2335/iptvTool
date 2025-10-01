import json
from pathlib import Path


class Config:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.area_codes = self._load_json("area_codes.json")
        self.generator_config = self._load_json("generator_config.json")
        self.scraper_config = self._load_json("scraper_config.json")
        self.formatter = self._load_json("formatter_config.json")
        self.post_processor_config = self._load_json("postprocessor_config.json")
        self.common_config = self._load_json("common_config.json")

    def get_area_codes(self):
        return self.area_codes

    def get_generator_config(self):
        return self.generator_config

    def get_scraper_config(self):
        return self.scraper_config

    def get_formatter_config(self):
        return self.formatter

    def get_post_processor_config(self):
        return self.post_processor_config
    
    def get_common_config(self):
        return self.common_config

    def _load_json(self, filename: str):
        path = self.config_dir / filename
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[Config] File {filename} not found!")
            return {}
        except json.JSONDecodeError:
            print(f"[Config] Error decoding {filename}!")
            return {}
