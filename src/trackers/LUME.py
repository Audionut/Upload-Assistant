# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any

from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class LUME(UNIT3D):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config, tracker_name="LUME")
        self.config = config
        self.common = COMMON(config)
        self.tracker = "LUME"
        self.base_url = "https://luminarr.me"
        self.id_url = f"{self.base_url}/api/torrents/"
        self.upload_url = f"{self.base_url}/api/torrents/upload"
        self.requests_url = f"{self.base_url}/api/requests/filter"
        self.search_url = f"{self.base_url}/api/torrents/filter"
        self.torrent_url = f"{self.base_url}/torrents/"
        self.banned_groups: list[str] = [""]
