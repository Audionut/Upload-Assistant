# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any

from src.trackers.NEXUSPHP import NEXUSPHP

Meta = dict[str, Any]
Config = dict[str, Any]


class LAJIDUI(NEXUSPHP):
    def __init__(self, config: Config) -> None:
        super().__init__(config, "LAJIDUI")
        self.banned_groups = []
        self.base_url = "https://pt.lajidui.top"
        self.source_flag = "[pt.lajidui.top] lajidui"
        self.torrent_url = f"{self.base_url}/details.php?id="

    def get_category(self, meta: Meta) -> int:
        animations = 405
        documentaries = 404
        movies = 401
        tv_series = 402
        tv_shows = 403

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

    def get_container(self, meta: Meta) -> int:
        iso = 16
        mkv = 10
        mp4 = 11
        other = 17

        if meta.get("is_disc", ""):
            return iso

        container = str(meta.get("container", "")).lower()

        if "mp4" in container:
            return mp4
        if "mkv" in container:
            return mkv

        return other

    def get_region(self, meta: Meta) -> int:
        america = [
            'AG', 'AI', 'AR', 'AW', 'BB', 'BL', 'BM', 'BO', 'BQ', 'BR', 'BS', 'BV', 'BZ', 'CA', 'CL',
            'CO', 'CR', 'CU', 'CW', 'DM', 'DO', 'EC', 'FK', 'GD', 'GF', 'GL', 'GP', 'GS', 'GT', 'GY',
            'HN', 'HT', 'JM', 'KN', 'KY', 'LC', 'MF', 'MQ', 'MS', 'MX', 'NI', 'PA', 'PE', 'PM', 'PR',
            'PY', 'SR', 'SV', 'SX', 'TC', 'TT', 'US', 'UY', 'VC', 'VE', 'VG', 'VI'
        ]  # fmt: off

        europe = [
            'AD', 'AL', 'AT', 'AX', 'BA', 'BE', 'BG', 'BY', 'CH', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
            'FO', 'FR', 'GB', 'GG', 'GI', 'GR', 'HR', 'HU', 'IE', 'IM', 'IS', 'IT', 'JE', 'LI', 'LT',
            'LU', 'LV', 'MC', 'MD', 'ME', 'MK', 'MT', 'NL', 'NO', 'PL', 'PT', 'RO', 'RS', 'RU', 'SE',
            'SI', 'SJ', 'SK', 'SM', 'SU', 'UA', 'VA', 'XC'
        ]  # fmt: off

        country = meta.get("origin_country", [])[0].upper()
        if country in america or country in europe:
            return 1
        if country == "CN":
            return 7
        if country == "TW":
            return 2
        if country == "HK":
            return 8
        if country == "JP":
            return 10
        if country == "KR":
            return 11
        if country == "IN":
            return 3

        return 6

    def get_type(self, meta: Meta) -> int:
        blu_ray = 1
        dvdr = 6
        encode = 7
        hd_dvd = 2
        hdtv = 5
        other = 11
        remux = 3
        web_dl = 10

        is_disc = str(meta.get("is_disc", "")).lower()
        mtype = str(meta.get("type", "")).lower()

        if is_disc == "bdmv":
            return blu_ray
        if is_disc == "dvd":
            return dvdr
        if is_disc == "hddvd":
            return hd_dvd

        if mtype == "remux":
            return remux
        if mtype in ("webdl", "webrip"):
            return web_dl
        if mtype == "hdtv":
            return hdtv
        if mtype == "encode":
            return encode

        return other

    def get_codec(self, meta: Meta) -> int:
        av1 = 6
        h264 = 1
        h265 = 7
        mpeg2 = 4
        other = 5
        vc1 = 2
        xvid = 3

        codec = str(meta.get("video_codec", "")).lower()

        if "h265" in codec or "x265" in codec or "hevc" in codec:
            return h265
        if "h264" in codec or "x264" in codec or "avc" in codec:
            return h264
        if "vc1" in codec or "vc-1" in codec:
            return vc1
        if "mpeg2" in codec or "mpeg-2" in codec:
            return mpeg2
        if "av1" in codec:
            return av1
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
            return 6
        if resolution == "4320p":
            return 7

        return 8

    def get_audio_codec(self, meta: Meta) -> int:
        audio_codec = str(meta.get("audio", "")).lower()

        if "flac" in audio_codec:
            return 1
        if "ape" in audio_codec:
            return 2
        if "dts-hd" in audio_codec:
            return 9
        if "dts" in audio_codec:
            return 3
        if "mp3" in audio_codec:
            return 4
        if "ogg" in audio_codec:
            return 5
        if "aac" in audio_codec:
            return 6
        if "wav" in audio_codec:
            return 8
        if "true" in audio_codec:
            return 10
        if "lpcm" in audio_codec:
            return 11
        if "ddp" in audio_codec:
            return 12
        if "dd" in audio_codec:
            return 13

        return 7

    def get_group_tag(self, meta: Meta) -> int:
        group_tag = {
            "-ade": 7,
            "-agsvweb": 15,
            "-beast": 18,
            "-beitai": 21,
            "-bmdru": 20,
            "-catedu": 17,
            "-chd": 2,
            "-cmct": 8,
            "-frds": 9,
            "-godramas": 22,
            "-hdhome": 14,
            "-hdsky": 1,
            "-hhweb": 6,
            "-lhd": 19,
            "-other": 5,
            "-ourbits": 12,
            "-pter": 16,
            "-qhstudIo": 13,
            "-tjupt": 10,
            "-ubits": 11,
            "-wiki": 4,
            "-原创": 3,
        }

        group = str(meta.get("tag", "")).lower()
        return group_tag.get(group, 5)

    def get_checkboxes(self, meta: Meta) -> list[str]:
        cantonese_audio = 11
        chinese_and_english_audio = 15
        chinese_and_english_subtitle = 16
        chinese_audio = 5
        chinese_subtitle = 6
        diy = 4
        english_audio = 14
        hdr = 7
        multi_track = 17
        reposting_prohibited = 1
        single_episode = 12

        audio_tracks = meta.get("audio_languages", [])
        subtitle_tracks = meta.get("subtitle_languages", [])
        mhdr = meta.get("hdr", "")

        checkboxes = []

        if meta.get("exclusive", False):
            checkboxes.append(str(reposting_prohibited))

        if "Chinese" in audio_tracks or "Mandarin" in audio_tracks:
            checkboxes.append(str(chinese_audio))

        if "Chinese" in audio_tracks and "English" in audio_tracks:
            checkboxes.append(str(chinese_and_english_audio))

        if "English" in audio_tracks:
            checkboxes.append(str(english_audio))

        if "Chinese" in subtitle_tracks and "English" in subtitle_tracks:
            checkboxes.append(str(chinese_and_english_subtitle))

        if len(meta.get("audio_languages", [])) > 1:
            checkboxes.append(str(multi_track))

        if "Cantonese" in audio_tracks:
            checkboxes.append(str(cantonese_audio))

        if "Chinese" in subtitle_tracks or "Mandarin" in subtitle_tracks:
            checkboxes.append(str(chinese_subtitle))

        if "HDR" in mhdr.upper():
            checkboxes.append(str(hdr))

        if meta.get("diy_disc", False):
            checkboxes.append(str(diy))

        if meta["category"] == "TV" and not meta.get("tv_pack", False):
            checkboxes.append(str(single_episode))

        return checkboxes
