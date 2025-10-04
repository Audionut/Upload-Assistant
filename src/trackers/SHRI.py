# -*- coding: utf-8 -*-
# import discord
import re
import os
from src.languages import process_desc_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class SHRI(UNIT3D):
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
        Generate ShareIsland release name with REMUX detection for UNTOUCHED/VU files,
        audio language tags, Italian title support, and [SUBS] tagging.
        """
        shareisland_name = meta["name"]
        resolution = meta.get("resolution")
        video_codec = meta.get("video_codec")
        video_encode = meta.get("video_encode")
        name_type = self._get_effective_type(meta)
        source = meta.get("source", "")
        imdb_info = meta.get("imdb_info") or {}

        # Extract Italian title from IMDb AKAs
        italian_title = self._get_italian_title(imdb_info)
        use_italian_title = self.config["TRACKERS"][self.tracker].get(
            "use_italian_title", False
        )

        # Remove unwanted tags
        remove_list = ["Dubbed"]
        for each in remove_list:
            shareisland_name = shareisland_name.replace(each, "")

        # Process audio languages if not already done
        audio_lang_str = ""
        if not meta.get("language_checked", False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        # Build audio language string (e.g., "ITALIAN - ENGLISH")
        if meta.get("audio_languages"):
            audio_languages = []
            for lang in meta["audio_languages"]:
                lang_up = lang.upper()
                if lang_up not in audio_languages:
                    audio_languages.append(lang_up)
            audio_lang_str = " - ".join(audio_languages)

        # Remove Dual-Audio from shareisland_name if present
        if meta.get("dual_audio"):
            shareisland_name = shareisland_name.replace("Dual-Audio", "", 1)

        # Handle REMUX detection and naming
        if self._is_remux(meta):
            if "ENCODE" in shareisland_name:
                shareisland_name = shareisland_name.replace("ENCODE", "REMUX", 1)
            elif "REMUX" not in shareisland_name and source:
                # Insert REMUX after source when ENCODE not present
                shareisland_name = shareisland_name.replace(
                    source, f"{source} REMUX", 1
                )

            # Remove VU/UNTOUCHED markers
            shareisland_name = self.MARKER_PATTERN.sub("", shareisland_name)

        # Normalize REMUX naming per tracker rules
        if name_type == "REMUX":
            shareisland_name = shareisland_name.replace("x264", video_codec).replace(
                "x265", video_codec
            )

            if video_codec in shareisland_name:
                shareisland_name = re.sub(
                    rf"[\s\-]{re.escape(video_codec)}", "", shareisland_name, count=1
                )
                shareisland_name = shareisland_name.replace(
                    "REMUX", f"REMUX {video_codec}", 1
                )

        # Apply Italian title if configured
        if italian_title and use_italian_title:
            shareisland_name = shareisland_name.replace(meta.get("aka", ""), "")
            shareisland_name = shareisland_name.replace(
                meta.get("title", ""), italian_title
            )

        # Add [SUBS] tag for Italian subs without Italian audio
        if not self._has_italian_audio(meta) and self._has_italian_subtitles(meta):
            if not meta.get("tag"):
                shareisland_name = shareisland_name + " [SUBS]"
            else:
                shareisland_name = shareisland_name.replace(
                    meta["tag"], f" [SUBS]{meta['tag']}"
                )

        # Insert audio language string per tracker rules
        if audio_lang_str:
            if name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):
                shareisland_name = shareisland_name.replace(
                    str(meta["year"]), f"{meta['year']} {audio_lang_str}", 1
                )
            elif not meta.get("is_disc") == "BDMV":
                shareisland_name = shareisland_name.replace(
                    meta["resolution"], f"{audio_lang_str} {meta['resolution']}", 1
                )

        # DVD rip formatting
        if name_type == "DVDRIP":
            source = "DVDRip"
            shareisland_name = shareisland_name.replace(f"{meta['source']} ", "", 1)
            shareisland_name = shareisland_name.replace(
                f"{meta['video_encode']}", "", 1
            )
            shareisland_name = shareisland_name.replace(
                f"{source}", f"{resolution} {source}", 1
            )
            shareisland_name = shareisland_name.replace(
                (meta["audio"]), f"{meta['audio']}{video_encode}", 1
            )

        # DVD disc and DVD REMUX formatting
        elif meta["is_disc"] == "DVD" or (
            name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")
        ):
            shareisland_name = shareisland_name.replace(
                (meta["source"]), f"{resolution} {meta['source']}", 1
            )
            shareisland_name = shareisland_name.replace(
                (meta["audio"]), f"{video_codec} {meta['audio']}", 1
            )

        # Replace invalid tags with NoGroup
        tag_lower = meta["tag"].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        if meta["tag"] == "" or any(
            invalid_tag in tag_lower for invalid_tag in invalid_tags
        ):
            shareisland_name = self.INVALID_TAG_PATTERN.sub("", shareisland_name)
            shareisland_name = f"{shareisland_name}-NoGroup"

        shareisland_name = self.WHITESPACE_PATTERN.sub(" ", shareisland_name)

        return {"name": shareisland_name}

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
        }.get(effective_type, "0")
        return {"type_id": type_id}

    # Private helper methods

    def get_basename(self, meta):
        """Extract basename from first file in filelist or path"""
        path = next(iter(meta["filelist"]), meta["path"])
        return os.path.basename(path)

    def _is_remux(self, meta):
        """Detect REMUX by checking basename markers and mediainfo"""
        basename = self.get_basename(meta).lower()

        # Explicit markers
        if "remux" in basename:
            return True
        if any(marker in basename for marker in ["vu", "untouched", "vu1080", "vu720"]):
            return True

        # Mediainfo check: no encoding settings = likely REMUX
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
        """Determine effective type for SHRI, detecting REMUX from various indicators"""
        return "REMUX" if self._is_remux(meta) else meta.get("type", "ENCODE")

    def _get_italian_title(self, imdb_info):
        """Extract Italian title from IMDb AKAs"""
        akas = imdb_info.get("akas", [])
        for aka in akas:
            if isinstance(aka, dict) and aka.get("country") == "Italy":
                return aka.get("title")
        return None

    def _has_italian_audio(self, meta):
        """Check for Italian audio tracks (excluding commentary)"""
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
