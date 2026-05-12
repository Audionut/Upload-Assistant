# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any

from src.trackers.NEXUSPHP import NEXUSPHP

Meta = dict[str, Any]
Config = dict[str, Any]


class PTCAFE(NEXUSPHP):
    def __init__(self, config: Config) -> None:
        super().__init__(config, "PTCAFE")
        self.banned_groups = []
        self.base_url = "https://ptcafe.club"
        self.source_flag = "[ptcafe.club] 咖啡"
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
            return 3
        if country == "CN":
            return 1
        if country == "TW" or country == "HK":
            return 2
        if country == "JP":
            return 4
        if country == "KR":
            return 5
        if country == "IN":
            return 6

        return 7

    def get_type(self, meta: Meta) -> int:
        blu_ray = 4
        blu_ray_diy = 5
        dvd = 10
        encode = 7
        remux = 6
        tv = 9
        uhd_diy = 2
        uhd_master_disc = 1
        uhd_remux = 3
        web_dl = 8

        is_disc = str(meta.get("is_disc", "")).lower()
        is_diy = meta.get("diy_disc", False)
        mtype = str(meta.get("type", "")).lower()
        resolution = str(meta.get("resolution", "")).lower()

        if is_disc == "bdmv":
            if resolution == "2160p":
                if is_diy:
                    return uhd_diy
                return uhd_master_disc
            else:
                if is_diy:
                    return blu_ray_diy
                return blu_ray

        if "dvd" in is_disc:
            return dvd

        if mtype == "remux":
            if resolution == "2160p":
                return uhd_remux
            return remux

        if mtype in ("webdl", "webrip"):
            return web_dl

        if "tv" in mtype:
            return tv

        if mtype == "encode":
            return encode

        return encode

    def get_codec(self, meta: Meta) -> int:
        divx = 10
        h264 = 2
        h265 = 1
        mpeg2 = 6
        mpeg4 = 7
        other = 11
        vc1 = 5
        vp9 = 9
        x264 = 4
        x265 = 3
        xvid = 8

        codec = str(meta.get("video_codec", "")).lower()

        if "h265" in codec or "x265" in codec or "hevc" in codec:
            return h265
        if "h264" in codec or "x264" in codec or "avc" in codec:
            return h264
        if "vc1" in codec or "vc-1" in codec:
            return vc1
        if "mpeg2" in codec or "mpeg-2" in codec:
            return mpeg2
        if "mpeg4" in codec or "mpeg-4" in codec:
            return mpeg4
        if "xvid" in codec:
            return xvid
        if "vp9" in codec:
            return vp9
        if "divx" in codec:
            return divx
        if "x265" in codec:
            return x265
        if "x264" in codec:
            return x264

        return other

    def get_resolution(self, meta: Meta) -> int:
        resolution = str(meta.get("resolution", "")).lower()

        if "1080" in resolution:
            return 3
        if "720" in resolution:
            return 4
        if meta.get("sd", False):
            return 5
        if "2160" in resolution:
            return 2
        if "4320" in resolution:
            return 1

        return 6

    def get_audio_codec(self, meta: Meta) -> int:
        audio_codec = str(meta.get("audio", "")).lower()

        if "dts:x 7.1" in audio_codec:
            return 1
        if "hd ma" in audio_codec:
            return 2
        if "hd hr" in audio_codec:
            return 3
        if "dts-hd" in audio_codec:
            return 4
        if "dts:x" in audio_codec:
            return 5
        if "lpcm" in audio_codec:
            return 6
        if "dd" in audio_codec:
            return 7
        if "atmos" in audio_codec:
            return 8
        if "aac" in audio_codec:
            return 9
        if "true" in audio_codec:
            return 10
        if "dts" in audio_codec:
            return 11
        if "flac" in audio_codec:
            return 12
        if "ape" in audio_codec:
            return 13
        if "mp3" in audio_codec:
            return 14
        if "wav" in audio_codec:
            return 15
        if "opus" in audio_codec:
            return 16
        if "ogg" in audio_codec:
            return 17

        return 18

    def get_group_tag(self, meta: Meta) -> int:
        group_tag = {
            "-ade": 1,
            "-adweb": 2,
            "-audies": 3,
            "-beast": 4,
            "-beitai": 5,
            "-beyondhd": 6,
            "-btstv": 7,
            "-cafetv": 8,
            "-cafeweb": 9,
            "-chd": 10,
            "-chdweb": 11,
            "-cmct": 12,
            "-djweb": 13,
            "-frds": 14,
            "-hdctv": 15,
            "-hdh": 16,
            "-hdhome": 17,
            "-hdsky": 18,
            "-hdsweb": 19,
            "-hhweb": 20,
            "-mteam": 21,
            "-mweb": 22,
            "-ourbits": 23,
            "-ourtv": 24,
            "-ptcafe": 25,
            "-pterweb": 26,
            "-qhstudio": 27,
            "-ttg": 28,
            "-wiki": 29,
        }

        group = str(meta.get("tag", "")).lower()
        return group_tag.get(group, 30)

    def get_checkboxes(self, meta: Meta) -> list[str]:
        cantonese_audio = 8
        chinese_audio = 7
        chinese_subtitle = 9
        diy = 13
        dv = 11
        hdr = 12
        reposting_prohibited = 5

        audio_tracks = meta.get("audio_languages", [])
        mhdr = meta.get("hdr", "")
        subtitle_tracks = meta.get("subtitle_languages", [])

        checkboxes = []

        if meta.get("exclusive", False):
            checkboxes.append(str(reposting_prohibited))

        if "Chinese" in audio_tracks or "Mandarin" in audio_tracks:
            checkboxes.append(str(chinese_audio))

        if "Cantonese" in audio_tracks:
            checkboxes.append(str(cantonese_audio))

        if "Chinese" in subtitle_tracks or "Mandarin" in subtitle_tracks:
            checkboxes.append(str(chinese_subtitle))

        if "HDR" in mhdr.upper():
            checkboxes.append(str(hdr))

        if "DV" in mhdr.upper():
            checkboxes.append(str(dv))

        if meta.get("diy_disc", False):
            checkboxes.append(str(diy))

        return checkboxes

    def get_douban_url(self, meta: Meta) -> str:
        _ = meta
        return ""

    def get_imdb_url(self, meta: Meta) -> str:
        _ = meta
        return ""
