# -*- coding: utf-8 -*-
import re
import os
from src.languages import process_desc_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class SHRI(UNIT3D):
    LANG_MAP = {
        "AR": "ARABIC", "PT-BR": "BRAZILIAN PORTUGUESE", "BG": "BULGARIAN", 
        "ZH": "CHINESE", "HR": "CROATIAN", "CS": "CZECH", "DA": "DANISH", 
        "NL": "DUTCH", "EN": "ENGLISH", "ET": "ESTONIAN", "FI": "FINNISH", 
        "FR": "FRENCH", "DE": "GERMAN", "EL": "GREEK", "HE": "HEBREW", 
        "HI": "HINDI", "HU": "HUNGARIAN", "IS": "ICELANDIC", "ID": "INDONESIAN",
        "IT": "ITALIAN", "JA": "JAPANESE", "KO": "KOREAN", "LV": "LATVIAN", 
        "LT": "LITHUANIAN", "NO": "NORWEGIAN", "FA": "PERSIAN", "PL": "POLISH", 
        "PT": "PORTUGUESE", "RO": "ROMANIAN", "RU": "RUSSIAN", "SR": "SERBIAN", 
        "SK": "SLOVAK", "SL": "SLOVENIAN", "ES": "SPANISH", "SV": "SWEDISH", 
        "TH": "THAI", "TR": "TURKISH", "UK": "UKRAINIAN", "VI": "VIETNAMESE"
    }
    # Pre-compile regex patterns for performance
    INVALID_TAG_PATTERN = re.compile(r"-(nogrp|nogroup|unknown|unk)", re.IGNORECASE)
    WHITESPACE_PATTERN = re.compile(r"\s{2,}")
    MARKER_PATTERN = re.compile(r"\b(UNTOUCHED|VU)\b", re.IGNORECASE)

    def __init__(self, config):
        super().__init__(config, tracker_name="SHRI")
        self.config = config
        self.common = COMMON(config)
        self.tracker = "SHRI"
        self.source_flag = "ShareIsland"
        self.base_url = "https://shareisland.org"
        self.id_url = f"{self.base_url}/api/torrents/"
        self.upload_url = f"{self.base_url}/api/torrents/upload"
        self.search_url = f"{self.base_url}/api/torrents/filter"
        self.torrent_url = f"{self.base_url}/torrents/"
        self.banned_groups = []

    async def get_additional_data(self, meta):
        """Get additional tracker-specific upload data"""
        data = {
            "mod_queue_opt_in": await self.get_flag(meta, "modq"),
        }
        return data

    async def get_name(self, meta):
        """
        Rebuild release name from meta components following ShareIsland naming rules.

        Handles:
        - REMUX detection for VU/UNTOUCHED releases
        - Italian title substitution from IMDb AKAs
        - Multi-language audio tags (ITALIAN - ENGLISH format)
        - Italian subtitle [SUBS] tag when no Italian audio present
        - Release group tag cleaning and validation
        """
        if not meta.get("language_checked", False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        # Extract components
        title = meta.get("title", "")
        italian_title = self._get_italian_title(meta.get("imdb_info", {}))
        use_italian_title = self.config["TRACKERS"][self.tracker].get(
            "use_italian_title", False
        )

        if italian_title and use_italian_title:
            title = italian_title

        year = str(meta.get("year", ""))
        resolution = meta.get("resolution", "")
        source = meta.get("source", "")
        video_codec = meta.get("video_codec", "")
        video_encode = meta.get("video_encode", "")

        # Clean audio: remove Dual-Audio and trailing language codes
        audio = meta.get("audio", "").replace("Dual-Audio", "").strip()
        audio = re.sub(r"\s*-[A-Z]{3}(-[A-Z]{3})*$", "", audio).strip()

        # Build audio language string with priority: original → ITALIAN → Multi
        audio_lang_str = ""
        if meta.get("audio_languages"):
            audio_langs = [lang.upper() for lang in meta["audio_languages"]]
            audio_langs = list(dict.fromkeys(audio_langs))

            # Convert original language from ISO code to full name
            orig_lang_iso = meta.get("original_language", "").upper()
            orig_lang_full = self.LANG_MAP.get(orig_lang_iso, "")

            result = []
            remaining = audio_langs.copy()

            # Priority 1: Original language always first
            if orig_lang_full and orig_lang_full in remaining:
                result.append(orig_lang_full)
                remaining.remove(orig_lang_full)

            # Priority 2: Italian always second (if present and not already added)
            italian_variants = ["ITALIAN", "ITA", "IT"]
            italian_lang = next(
                (lang for lang in remaining if lang in italian_variants), None
            )
            if italian_lang:
                result.append("ITALIAN")
                remaining.remove(italian_lang)

            # 4+ languages: add Multi after first two
            if len(audio_langs) >= 4:
                result.append("Multi")
            else:
                # 3 or fewer: show all languages
                result.extend(remaining)

            audio_lang_str = " - ".join(result)

        effective_type = self._get_effective_type(meta)

        hybrid = ""
        basename_upper = self.get_basename(meta).upper()
        title_upper = title.upper()
        if all([x in meta.get("hdr", "") for x in ["HDR", "DV"]]) or (
            "HYBRID" in basename_upper and "HYBRID" not in title_upper
        ):
            hybrid = "Hybrid"

        repack = meta.get("repack", "").strip()

        # Build name per ShareIsland type-specific format
        if effective_type == "DISC":
            if meta.get("is_disc") == "DVD":
                name = f"{title} {year} {audio_lang_str} {hybrid} {repack} {source} {audio}"
            else:  # BDMV or other disc types
                name = f"{title} {year} {audio_lang_str} {hybrid} {repack} {resolution} {source} {video_codec} {audio}"

        elif effective_type == "REMUX":
            # REMUX: Title Year LANG Resolution Source REMUX Codec Audio
            name = f"{title} {year} {audio_lang_str} {hybrid} {repack} {resolution} {source} REMUX {video_codec} {audio}"

        elif effective_type in ("DVDRIP", "BRRIP"):
            # DVDRip/BRRIP: Title Year LANG Resolution DVDRip Audio Encode
            type_str = "DVDRip" if effective_type == "DVDRIP" else "BRRip"
            name = f"{title} {year} {audio_lang_str} {hybrid} {repack} {resolution} {type_str} {audio} {video_encode}"

        elif effective_type in ("ENCODE", "HDTV"):
            # Encode/HDTV: Title Year LANG Resolution Source Audio Encode
            name = f"{title} {year} {audio_lang_str} {hybrid} {repack} {resolution} {source} {audio} {video_encode}"

        elif effective_type in ("WEBDL", "WEBRIP"):
            # WEB: Title Year LANG Resolution Service Type Audio Encode
            service = meta.get("service", "")
            type_str = "WEB-DL" if effective_type == "WEBDL" else "WEBRip"
            name = f"{title} {year} {audio_lang_str} {hybrid} {repack} {resolution} {service} {type_str} {audio} {video_encode}"

        else:
            # Fallback: use original name with cleaned audio
            name = meta["name"].replace("Dual-Audio", "").strip()

        # Add [SUBS] tag for Italian subtitles without Italian audio
        if not self._has_italian_audio(meta) and self._has_italian_subtitles(meta):
            name = f"{name} [SUBS]"

        # Clean and validate release group tag
        tag = meta.get("tag", "").strip()
        tag = tag.lstrip("-")
        tag = re.sub(r"^[A-Z]{2,3}\s+", "", tag).strip()

        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        if not tag or any(inv in tag.lower() for inv in invalid_tags):
            tag = "NoGroup"

        name = f"{name}-{tag}"
        name = self.WHITESPACE_PATTERN.sub(" ", name).strip()

        return {"name": name}

    async def get_type_id(self, meta):
        """Map release type to ShareIsland type IDs"""
        effective_type = self._get_effective_type(meta)
        type_id = {
            "DISC": "26",
            "REMUX": "7",
            "WEBDL": "27",
            "WEBRIP": "15",
            "HDTV": "6",
            "ENCODE": "15",
            "DVDRIP": "15",
            "BRRIP": "15",
        }.get(effective_type, "0")
        return {"type_id": type_id}

    def get_basename(self, meta):
        """Extract basename from first file in filelist or path"""
        path = next(iter(meta["filelist"]), meta["path"])
        return os.path.basename(path)

    def _is_remux(self, meta):
        """
        Detect REMUX releases via:
        - Filename markers (remux, vu, untouched)
        - Mediainfo analysis (no encoding settings + BluRay/HDDVD source)
        """
        basename = self.get_basename(meta).lower()

        if "remux" in basename:
            return True
        if any(marker in basename for marker in ["vu", "untouched", "vu1080", "vu720"]):
            return True

        try:
            mi = meta.get("mediainfo", {})
            video_track = mi.get("media", {}).get("track", [{}])[1]

            if (
                not video_track.get("Encoded_Library_Settings")
                and meta.get("source") in ("BluRay", "HDDVD")
                and meta.get("type") not in ("DISC", "WEBDL", "WEBRIP")
            ):
                return True
        except (IndexError, KeyError):
            pass

        return False

    def _get_effective_type(self, meta):
        """Determine effective type, overriding ENCODE with REMUX when detected"""
        return "REMUX" if self._is_remux(meta) else meta.get("type", "ENCODE")

    def _get_italian_title(self, imdb_info):
        """Extract Italian title from IMDb AKAs"""
        akas = imdb_info.get("akas", [])
        for aka in akas:
            if isinstance(aka, dict) and aka.get("country") == "Italy":
                return aka.get("title")
        return None

    def _has_italian_audio(self, meta):
        """Check for Italian audio tracks, excluding commentary"""
        if "mediainfo" not in meta:
            return False

        tracks = meta["mediainfo"].get("media", {}).get("track", [])
        return any(
            track.get("@type") == "Audio"
            and isinstance(track.get("Language"), str)
            and track.get("Language").lower() in {"it", "it-it"}
            and "commentary" not in str(track.get("Title", "")).lower()
            for track in tracks[2:]
        )

    def _has_italian_subtitles(self, meta):
        """Check for Italian subtitle tracks"""
        if "mediainfo" not in meta:
            return False

        tracks = meta["mediainfo"].get("media", {}).get("track", [])
        return any(
            track.get("@type") == "Text"
            and isinstance(track.get("Language"), str)
            and track.get("Language").lower() in {"it", "it-it"}
            for track in tracks
        )
