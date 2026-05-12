# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any

from src.trackers.NEXUSPHP import NEXUSPHP

Meta = dict[str, Any]
Config = dict[str, Any]


class PTFANS(NEXUSPHP):
    def __init__(self, config: Config) -> None:
        super().__init__(config, "PTFANS")
        self.banned_groups = []
        self.base_url = "https://ptfans.cc"
        self.source_flag = "[ptfans.cc] PTFans"
        self.torrent_url = f"{self.base_url}/details.php?id="

    def get_category(self, meta: Meta) -> int:
        animations = 414
        documentaries = 406
        movies = 401
        tv_series = 404
        tv_shows = 405

        category = str(meta.get("category", "")).upper()
        genres = str(meta.get("genres", "")).lower()
        keywords = str(meta.get("keywords", "")).lower()

        if "documentary" in genres or "documentary" in keywords:
            return documentaries
        if meta.get("anime") or "animation" in genres or "animation" in keywords:
            return animations

        if category == "MOVIE":
            return movies
        if category == "TV":
            game_show_keywords = [
                "award show",
                "competition",
                "game show",
                "music show",
                "performance",
                "reality television",
                "reality tv",
                "reality",
                "stand-up",
                "talk show",
                "tv show",
                "variety",
            ]
            if any(re.search(rf"(^|,\s*){re.escape(keyword)}(\s*,|$)", genres, re.IGNORECASE) for keyword in game_show_keywords):
                return tv_shows
            else:
                return tv_series

        return movies

    def get_type(self, meta: Meta) -> int:
        blu_ray = 6
        dvd = 2
        encode = 8
        other = 9
        remux = 3
        web_dl = 5

        is_disc = str(meta.get("is_disc", "")).lower()
        mtype = str(meta.get("type", "")).lower()

        if is_disc == "bdmv":
            return blu_ray
        if "dvd" in is_disc:
            return dvd

        if mtype == "remux":
            return remux
        if mtype in ("webdl", "webrip"):
            return web_dl
        if mtype == "encode":
            return encode

        return other

    def get_codec(self, meta: Meta) -> int:
        av1 = 8
        bluray_avc = 4
        bluray_hevc = 5
        bluray_vc1 = 3
        mpeg2 = 6
        not_bluray_h264 = 1
        not_bluray_h265 = 2
        other = 9
        xvid = 7

        codec = str(meta.get("video_codec", "")).lower()
        source = meta.get("source", "").lower()
        is_bluray_source = "bluray" in source or "blu-ray" in source

        if "av1" in codec:
            return av1
        if "h265" in codec or "x265" in codec or "hevc" in codec:
            if is_bluray_source:
                return bluray_hevc
            return not_bluray_h265
        if "h264" in codec or "x264" in codec or "avc" in codec:
            if is_bluray_source:
                return bluray_avc
            return not_bluray_h264
        if "mpeg2" in codec or "mpeg-2" in codec:
            return mpeg2
        if "vc1" in codec or "vc-1" in codec:
            if is_bluray_source:
                return bluray_vc1
            return other
        if "xvid" in codec:
            return xvid

        return other

    def get_resolution(self, meta: Meta) -> int:
        resolution = str(meta.get("resolution", "")).lower()

        if resolution == "1080p":
            return 1
        if resolution == "1080i":
            return 2
        if resolution == "720p":
            return 3
        if meta.get("sd", False):
            return 4
        if resolution == "2160p":
            return 5
        if resolution == "4320p":
            return 6

        return 1

    def get_group_tag(self, meta: Meta) -> int:
        group_tag = {
            "-chd": 2,
            "-hds": 1,
            "-mysilu": 3,
            "-wiki": 4,
        }

        group = str(meta.get("tag", "")).lower()
        return group_tag.get(group, 5)
