# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
from typing import Literal
import asyncio
import aiofiles
import certifi
import cli_ui
import os
import pycountry
import random
import re
import requests
from babel import Locale
from src.audio import get_audio_v2
from src.languages import process_desc_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

_shri_session_data = {}


class SHRI(UNIT3D):
    """ShareIsland tracker implementation with Italian localization support"""

    # Pre-compile regex patterns for performance
    INVALID_TAG_PATTERN = re.compile(r"-(nogrp|nogroup|unknown|unk)", re.IGNORECASE)
    WHITESPACE_PATTERN = re.compile(r"\s{2,}")
    MARKER_PATTERN = re.compile(r"\b(UNTOUCHED|VU1080|VU720|VU)\b", re.IGNORECASE)
    CINEMA_NEWS_PATTERN = re.compile(
        r"\b(HDTS|TS|MD|LD|CAM|HDCAM|TC|HDTC)\b", re.IGNORECASE
    )
    CINEMA_VIDEO_PATTERN = re.compile(r"\b(HDTS|TS|CAM|HDCAM|TC|HDTC)\b", re.IGNORECASE)
    CINEMA_AUDIO_PATTERN = re.compile(r"\b(MD|LD)\b", re.IGNORECASE)

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
        self.requests_url = f"{self.base_url}/api/requests/filter"
        self.torrent_url = f"{self.base_url}/torrents/"
        self.banned_groups = []

    def _get_language_code(self, track_or_string):
        """Extract and normalize language to ISO alpha-2 code"""
        if isinstance(track_or_string, dict):
            lang = track_or_string.get("Language", "")
            if isinstance(lang, dict):
                lang = lang.get("String", "")
        else:
            lang = track_or_string
        if not lang:
            return ""
        lang_str = str(lang).lower()

        # Strip country code if present (e.g., "en-US" → "en")
        if "-" in lang_str:
            lang_str = lang_str.split("-")[0]

        if len(lang_str) == 2:
            return lang_str
        try:
            lang_obj = (
                pycountry.languages.get(name=lang_str.title())
                or pycountry.languages.get(alpha_2=lang_str)
                or pycountry.languages.get(alpha_3=lang_str)
            )
            return lang_obj.alpha_2.lower() if lang_obj else lang_str
        except (AttributeError, KeyError, LookupError):
            return lang_str

    async def get_additional_data(self, meta):
        """Get additional tracker-specific upload data"""
        return {"mod_queue_opt_in": await self.get_flag(meta, "modq")}

    async def get_name(self, meta):
        """
        Rebuild release name from meta components following ShareIsland naming rules.

        Handles:
        - REMUX detection from filename markers (VU/UNTOUCHED)
        - Italian title substitution from IMDb AKAs
        - Multi-language audio tags (ITALIAN - ENGLISH format)
        - Italian subtitle [SUBS] tag when no Italian audio present
        - Release group tag cleaning and validation
        - DISC region injection
        """
        if not meta.get("language_checked", False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        # Title and basic info
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
        if isinstance(source, list):
            source = source[0] if source else ""
        video_codec = meta.get("video_codec", "")
        video_encode = meta.get("video_encode", "")

        # TV specific
        season = meta.get("season") or ""
        episode = meta.get("episode") or ""
        episode_title = meta.get("episode_title") or ""
        part = meta.get("part") or ""

        # Optional fields
        edition = meta.get("edition") or ""
        hdr = meta.get("hdr") or ""
        uhd = meta.get("uhd") or ""
        three_d = meta.get("3D") or ""

        # Clean audio: remove Dual-Audio and trailing language codes
        audio = await self._get_best_italian_audio_format(meta)

        # Build audio language tag: original -> ITALIAN -> ENGLISH -> others/Multi (4+)
        audio_lang_str = ""
        if meta.get("audio_languages"):
            # Normalize all to full names
            audio_langs = [
                self._get_language_name(lang.upper())
                for lang in meta["audio_languages"]
            ]
            audio_langs = [lang for lang in audio_langs if lang]  # Remove empty
            audio_langs = list(dict.fromkeys(audio_langs))  # Dedupe preserving order

            orig_lang_iso = meta.get("original_language", "").upper()
            orig_lang_full = self._get_language_name(orig_lang_iso)

            result = []
            remaining = audio_langs.copy()

            # Priority 1: Original language
            if orig_lang_full and orig_lang_full in remaining:
                result.append(orig_lang_full)
                remaining.remove(orig_lang_full)

            # Priority 2: Italian (if not already added)
            if "ITALIAN" in remaining:
                result.append("ITALIAN")
                remaining.remove("ITALIAN")

            # Priority 3: English (if not already added)
            if "ENGLISH" in remaining:
                result.append("ENGLISH")
                remaining.remove("ENGLISH")

            # Handle remaining: show individually if <=3 total, else add Multi
            if len(result) + len(remaining) > 3:
                result.append("Multi")
            else:
                result.extend(remaining)

            audio_lang_str = " - ".join(result)

        effective_type = self.get_effective_type(meta)

        if effective_type != "DISC":
            source = source.replace("Blu-ray", "BluRay")

        # Detect Hybrid from filename if not in title
        hybrid = ""
        if (
            not edition
            and (meta.get("webdv", False) or isinstance(meta.get("source", ""), list))
            and "HYBRID" not in title.upper()
        ):
            hybrid = "Hybrid"

        repack = meta.get("repack", "").strip()

        name = None
        # Build name per ShareIsland type-specific format
        if effective_type == "DISC":
            # Inject region from validated session data if available
            region = _shri_session_data.get(meta["uuid"], {}).get(
                "_shri_region_name"
            ) or meta.get("region", "")
            if meta["is_disc"] == "BDMV":
                # BDMV: Title Year 3D Edition Hybrid REPACK Resolution Region UHD Source HDR VideoCodec Audio
                name = f"{title} {year} {season}{episode} {three_d} {edition} {hybrid} {repack} {resolution} {region} {uhd} {source} {hdr} {video_codec} {audio}"
            elif meta["is_disc"] == "DVD":
                dvd_size = meta.get("dvd_size", "")
                # DVD: Title Year 3D Edition REPACK Resolution Region Source DVDSize Audio
                name = f"{title} {year} {season}{episode} {three_d} {edition} {repack} {resolution} {region} {source} {dvd_size} {audio}"
            elif meta["is_disc"] == "HDDVD":
                # HDDVD: Title Year Edition REPACK Resolution Region Source VideoCodec Audio
                name = f"{title} {year} {edition} {repack} {resolution} {region} {source} {video_codec} {audio}"

        elif effective_type == "REMUX":
            # REMUX: Title Year 3D LANG Edition Hybrid REPACK Resolution UHD Source REMUX HDR VideoCodec Audio
            name = f"{title} {year} {season}{episode} {episode_title} {part} {three_d} {audio_lang_str} {edition} {hybrid} {repack} {resolution} {uhd} {source} REMUX {hdr} {video_codec} {audio}"

        elif effective_type in ("DVDRIP", "BRRIP"):
            type_str = "DVDRip" if effective_type == "DVDRIP" else "BRRip"
            # DVDRip/BRRip: Title Year LANG Edition Hybrid REPACK Resolution Type Audio HDR VideoCodec
            name = f"{title} {year} {season} {audio_lang_str} {edition} {hybrid} {repack} {resolution} {type_str} {audio} {hdr} {video_encode}"

        elif effective_type in ("ENCODE", "HDTV"):
            # Encode/HDTV: Title Year LANG Edition Hybrid REPACK Resolution UHD Source Audio HDR VideoCodec
            name = f"{title} {year} {season}{episode} {episode_title} {part} {audio_lang_str} {edition} {hybrid} {repack} {resolution} {uhd} {source} {audio} {hdr} {video_encode}"

        elif effective_type in ("WEBDL", "WEBRIP"):
            service = meta.get("service", "")
            type_str = "WEB-DL" if effective_type == "WEBDL" else "WEBRip"
            # WEB: Title Year LANG Edition Hybrid REPACK Resolution UHD Service Type Audio HDR VideoCodec
            name = f"{title} {year} {season}{episode} {episode_title} {part} {audio_lang_str} {edition} {hybrid} {repack} {resolution} {uhd} {service} {type_str} {audio} {hdr} {video_encode}"

        elif effective_type == "CINEMA_NEWS":
            basename_upper = self.get_basename(meta).upper()
            markers = []

            video_match = self.CINEMA_VIDEO_PATTERN.search(basename_upper)
            if video_match:
                markers.append(video_match.group(0))

            audio_match = self.CINEMA_AUDIO_PATTERN.search(basename_upper)
            if audio_match:
                markers.append(audio_match.group(0))

            source_marker = " ".join(markers)

            # Cinema News: Title Year LANG Edition REPACK Resolution Source Audio VideoCodec
            name = f"{title} {year} {audio_lang_str} {edition} {repack} {resolution} {source_marker} {audio} {video_encode}"

        else:
            # Fallback: use original name with cleaned audio
            name = meta["name"].replace("Dual-Audio", "").strip()

        # Ensure name is always a string
        if not name:
            name = meta.get("name", "UNKNOWN")

        # Add [SUBS] for Italian subtitles without Italian audio
        if not self._has_italian_audio(meta) and self._has_italian_subtitles(meta):
            name = f"{name} [SUBS]"

        # Cleanup whitespace
        name = self.WHITESPACE_PATTERN.sub(" ", name).strip()

        # Extract tag and append if valid
        tag = self._extract_clean_release_group(meta, name)
        if tag:
            name = f"{name}-{tag}"

        return {"name": name}

    def _extract_clean_release_group(self, meta, current_name):
        """Extract release group - only accepts VU/UNTOUCHED markers from filename"""
        tag = meta.get("tag", "").strip().lstrip("-")
        if tag and " " not in tag and not self.INVALID_TAG_PATTERN.search(tag):
            return tag

        basename = self.get_basename(meta)
        # Get extension from mediainfo and remove it
        ext = (
            meta.get("mediainfo", {})
            .get("media", {})
            .get("track", [{}])[0]
            .get("FileExtension", "")
        )
        name_no_ext = (
            basename[: -len(ext) - 1]
            if ext and basename.endswith(f".{ext}")
            else basename
        )
        parts = re.split(r"[-.]", name_no_ext)
        if not parts:
            return "NoGroup"

        potential_tag = parts[-1].strip()
        # Handle space-separated components
        if " " in potential_tag:
            potential_tag = potential_tag.split()[-1]

        if (
            not potential_tag
            or len(potential_tag) > 30
            or not potential_tag.replace("_", "").isalnum()
        ):
            return "NoGroup"

        # ONLY accept if it's a VU/UNTOUCHED marker
        if not self.MARKER_PATTERN.search(potential_tag):
            return "NoGroup"

        return potential_tag

    async def get_type_id(self, meta, type=None, reverse=False, mapping_only=False):
        """Map release type to ShareIsland type IDs"""
        type_mapping = {
            "CINEMA_NEWS": "42",
            "DISC": "26",
            "REMUX": "7",
            "WEBDL": "27",
            "WEBRIP": "15",
            "HDTV": "33",
            "ENCODE": "15",
            "DVDRIP": "15",
            "BRRIP": "15",
        }

        if mapping_only:
            return type_mapping

        elif reverse:
            return {v: k for k, v in type_mapping.items()}
        elif type is not None:
            return {"type_id": type_mapping.get(type, "0")}
        else:
            effective_type = self.get_effective_type(meta)
            type_id = type_mapping.get(effective_type, "0")
            return {"type_id": type_id}

    async def get_additional_checks(self, meta) -> Literal[True]:
        """
        Validate and prompt for DVD/HDDVD region/distributor before upload.
        Stores validated IDs in module-level dict keyed by UUID for use during upload.
        """
        if meta.get("is_disc") in ["DVD", "HDDVD"]:
            region_name = meta.get("region")

            # Prompt for region if not in meta
            if not region_name:
                if not meta.get("unattended") or meta.get("unattended_confirm"):
                    while True:
                        region_name = cli_ui.ask_string(
                            "SHRI: Region code not found for disc. Please enter it manually (mandatory): "
                        )
                        region_name = (
                            region_name.strip().upper() if region_name else None
                        )
                        if region_name:
                            break
                        print("Region code is required.")

            # Validate region name was provided
            if not region_name:
                cli_ui.error("Region required; skipping SHRI.")
                raise ValueError("Region required for disc upload")

            # Validate region code with API
            region_id = await self.common.unit3d_region_ids(region_name)
            if not region_id:
                cli_ui.error(f"Invalid region code '{region_name}'; skipping SHRI.")
                raise ValueError(f"Invalid region code: {region_name}")

            # Handle optional distributor
            distributor_name = meta.get("distributor")
            distributor_id = None
            if not distributor_name and not meta.get("unattended"):
                distributor_name = cli_ui.ask_string(
                    "SHRI: Distributor (optional, Enter to skip): "
                )
                distributor_name = (
                    distributor_name.strip().upper() if distributor_name else None
                )

            if distributor_name:
                distributor_id = await self.common.unit3d_distributor_ids(
                    distributor_name
                )

            # Store in module-level dict keyed by UUID (survives instance recreation)
            _shri_session_data[meta["uuid"]] = {
                "_shri_region_id": region_id,
                "_shri_region_name": region_name,
                "_shri_distributor_id": distributor_id if distributor_name else None,
            }

        return await super().get_additional_checks(meta)

    async def get_region_id(self, meta):
        """Override to use validated region ID stored in meta"""
        data = _shri_session_data.get(meta["uuid"], {})
        region_id = data.get("_shri_region_id")
        if region_id:
            return {"region_id": region_id}
        return await super().get_region_id(meta)

    async def get_distributor_id(self, meta):
        """Override to use validated distributor ID stored in meta"""
        data = _shri_session_data.get(meta["uuid"], {})
        distributor_id = data.get("_shri_distributor_id")
        if distributor_id:
            return {"distributor_id": distributor_id}
        return await super().get_distributor_id(meta)

    def get_basename(self, meta):
        """Extract basename from first file in filelist or path"""
        path = next(iter(meta["filelist"]), meta["path"])
        return os.path.basename(path)

    def _detect_type_from_technical_analysis(self, meta):
        """Unified type detection: filename markers + MediaInfo analysis"""
        # Priority 1: Explicit REMUX markers (filename check FIRST)
        if self._has_remux_marker(meta):
            return "REMUX"
        # Priority 2: Base type from upstream
        base_type = meta.get("type", "ENCODE")
        if base_type in ("DISC", "DVDRIP", "BRRIP"):
            return base_type
        # Priority 3: Technical mediainfo analysis
        return self._analyze_encode_type(meta)

    def _has_remux_marker(self, meta):
        name_no_ext = os.path.splitext(self.get_basename(meta))[0].lower()
        if "remux" in name_no_ext:
            return True
        if self.MARKER_PATTERN.search(name_no_ext):
            return True

        # Check for MakeMKV + no encoding
        mi = meta.get("mediainfo", {}).get("media", {}).get("track", [])
        if mi:
            general = mi[0]
            encoded_app = str(general.get("Encoded_Application", "")).lower()
            encoded_lib = str(general.get("Encoded_Library", "")).lower()

            if "makemkv" in encoded_app or "makemkv" in encoded_lib:
                video = next((t for t in mi if t.get("@type") == "Video"), {})
                settings = video.get("Encoded_Library_Settings")
                if not settings or isinstance(settings, dict):
                    return True

        return False

    def _analyze_encode_type(self, meta):
        """
        Detect release type from MediaInfo technical analysis.

        Priority order:
        1. DV profile (05/07/08) + no encoding -> WEB-DL (overrides source field)
        2. CRF in settings -> WEBRIP/ENCODE
        3. Service fingerprints -> WEB-DL (CR/Netflix patterns)
        4. BluRay encoding detection -> ENCODE (settings, library, or GPU stripped metadata)
        5. Encoding tools (source-aware) -> WEBRIP/ENCODE (Handbrake/Staxrip/etc in general track)
        6. No encoding + WEB -> WEB-DL
        7. Service override -> WEB-DL (handles misdetected sources)
        8. No encoding + disc -> REMUX
        """

        def has_encoding_tools(general_track, tools):
            """Check if general track contains specified encoding tools."""
            encoded_app = str(general_track.get("Encoded_Application", "")).lower()
            extra = general_track.get("extra", {})
            writing_frontend = str(extra.get("Writing_frontend", "")).lower()
            tool_string = f"{encoded_app} {writing_frontend}"
            return any(tool in tool_string for tool in tools)

        try:
            mi = meta.get("mediainfo", {})
            tracks = mi.get("media", {}).get("track", [])
            general_track = tracks[0]
            video_track = tracks[1]

            # Normalize source list
            source = meta.get("source", "")
            if isinstance(source, list):
                source = [s.upper() for s in source]
            else:
                source = [source.upper()] if source else []

            service = str(meta.get("service", "")).upper()

            # Extract encoding metadata
            raw_settings = video_track.get("Encoded_Library_Settings", "")
            raw_library = video_track.get("Encoded_Library", "")
            has_settings = raw_settings and not isinstance(raw_settings, dict)
            has_library = raw_library and not isinstance(raw_library, dict)
            encoding_settings = str(raw_settings).lower() if has_settings else ""
            encoded_library = str(raw_library).lower() if has_library else ""

            # ===== Priority 1: DV streaming profiles =====
            # DV profiles 5/7/8 indicate streaming sources (overrides source field)
            hdr_profile = video_track.get("HDR_Format_Profile", "")
            has_streaming_dv = any(
                prof in hdr_profile for prof in ["dvhe.05", "dvhe.07", "dvhe.08"]
            )

            if has_streaming_dv and not encoding_settings:
                # Ensure not re-encoded by user tools
                if not has_encoding_tools(
                    general_track, ["handbrake", "staxrip", "megatagger"]
                ):
                    return "WEBDL"

            # ===== Priority 2: CRF detection =====
            # CRF (Constant Rate Factor) indicates user re-encode
            if "crf=" in encoding_settings:
                return "WEBRIP" if any("WEB" in s for s in source) else "ENCODE"

            # ===== Priority 3: Service fingerprints =====
            # Crunchyroll detection
            if service == "CR":
                if "core 142" in encoded_library:
                    return "WEBDL"
                if has_library:
                    core_match = re.search(r"core (\d+)", encoded_library)
                    if core_match and int(core_match.group(1)) >= 152:
                        return "WEBRIP"
                if encoding_settings and "bitrate=" in encoding_settings:
                    return "WEBDL"

            # Netflix fingerprint detection
            format_profile = video_track.get("Format_Profile", "")
            if "Main@L4.0" in format_profile and "rc=2pass" in encoding_settings:
                if "core 118" in encoded_library or "core 148" in encoded_library:
                    return "WEBDL"

            # ===== Priority 4: BluRay encoding detection =====
            if any(s in ("BLURAY", "BLU-RAY") for s in source):
                # GPU encode detection: empty BitDepth/Chroma metadata (dict type)
                if isinstance(video_track.get("BitDepth"), dict):
                    return "ENCODE"
                # Any encoding settings or library info = encode (not remux)
                # Catches x264/x265 in Encoded_Library or settings in Encoded_Library_Settings
                if has_settings or has_library:
                    return "ENCODE"

            # ===== Priority 5: Encoding tools (source-aware) =====
            # Check general track for encoding tools (Handbrake, Staxrip, etc)
            if any(s in ("BLURAY", "BLU-RAY") for s in source):
                if has_encoding_tools(
                    general_track,
                    ["x264", "x265", "handbrake", "staxrip", "megatagger"],
                ):
                    return "ENCODE"

            # WEB sources: only explicit user tools indicate re-encode
            if any("WEB" in s for s in source):
                if has_encoding_tools(
                    general_track, ["handbrake", "staxrip", "megatagger"]
                ):
                    return "WEBRIP"

            # ===== Priority 6: No encoding + WEB = WEB-DL =====
            if any("WEB" in s for s in source):
                return "WEBDL"

            # ===== Priority 7: Service override =====
            # If streaming service is set but source wasn't detected as Web,
            # override to WEB-DL (handles upstream get_source.py misdetection)
            if service and service not in ("", "NONE"):
                return "WEBDL"

            # ===== Priority 8: No encoding + disc = REMUX =====
            if any(s in ("BLURAY", "BLU-RAY", "HDDVD") for s in source):
                return "REMUX"

            # DVD REMUX detection
            if any(s in ("NTSC", "PAL", "NTSC DVD", "PAL DVD", "DVD") for s in source):
                if not has_settings and not has_library:
                    return "REMUX"

        except (IndexError, KeyError):
            # Fallback on mediainfo parsing errors
            pass

        # Final fallback: use meta type or default to ENCODE
        return meta.get("type", "ENCODE")

    def get_effective_type(self, meta):
        """
        Determine effective type with priority hierarchy:
        1. Cinema News (CAM/HDCAM/TC/HDTC/TS/HDTS/MD/LD keywords)
        2. Technical analysis (REMUX/ENCODE/WEB-DL/WEBRip detection)
        3. Base type from meta
        """
        basename = self.get_basename(meta)
        if self.CINEMA_NEWS_PATTERN.search(basename):
            return "CINEMA_NEWS"

        detected_type = self._detect_type_from_technical_analysis(meta)
        return detected_type

    def _get_italian_title(self, imdb_info):
        """Extract Italian title from IMDb AKAs with priority"""
        country_match = None
        language_match = None

        for aka in imdb_info.get("akas", []):
            if isinstance(aka, dict):
                if aka.get("country") == "Italy" and not aka.get("attributes"):
                    country_match = aka.get("title")
                    break  # Country match takes priority
                elif aka.get("language") == "Italy" and not language_match and not aka.get("attributes"):
                    language_match = aka.get("title")

        return country_match or language_match

    def _has_italian_audio(self, meta):
        """Check for Italian audio tracks, excluding commentary"""
        if "mediainfo" not in meta:
            return False

        tracks = meta["mediainfo"].get("media", {}).get("track", [])
        return any(
            track.get("@type") == "Audio"
            and self._get_language_code(track) in {"it"}
            and "commentary" not in str(track.get("Title", "")).lower()
            for track in tracks[2:]
        )

    def _has_italian_subtitles(self, meta):
        """Check for Italian subtitle tracks"""
        if "mediainfo" not in meta:
            return False

        tracks = meta["mediainfo"].get("media", {}).get("track", [])
        return any(
            track.get("@type") == "Text" and self._get_language_code(track) in {"it"}
            for track in tracks
        )

    def _get_language_name(self, iso_code):
        """Convert ISO language code to full language name"""
        if not iso_code:
            return ""

        # Try alpha_2 (IT, EN, etc)
        lang = pycountry.languages.get(alpha_2=iso_code.lower())
        if lang:
            return lang.name.upper()

        # Try alpha_3 (ITA, ENG, etc)
        lang = pycountry.languages.get(alpha_3=iso_code.lower())
        if lang:
            return lang.name.upper()

        return iso_code

    def _get_italian_language_name(self, iso_code):
        """Convert ISO language code to Italian language name using Babel"""
        if not iso_code:
            return ""

        try:
            locale = Locale.parse(iso_code.lower())
            italian_name = locale.get_display_name("it")
            return (
                italian_name.title()
                if italian_name
                else self._get_language_name(iso_code).title()
            )
        except (ValueError, AttributeError, KeyError):
            return self._get_language_name(iso_code).title()

    async def _get_best_italian_audio_format(self, meta):
        """Filter Italian tracks, select best, format via get_audio_v2"""
        # fmt: off
        ITALIAN_LANGS = {"it", "italian", "italiano"}

        def extract_quality(track, is_bdinfo):
            if is_bdinfo:
                bitrate_match = re.search(r'(\d+)', track.get("bitrate", "0"))
                return (
                    any(x in track.get("codec", "").lower() for x in ["truehd", "dts-hd ma", "flac", "pcm"]),
                    int(float(track.get("channels", "2.0").split(".")[0])),
                    "atmos" in track.get("atmos_why_you_be_like_this", "").lower(),
                    int(bitrate_match.group(1)) if bitrate_match else 0
                )
            else:
                try:
                    bitrate_int = int(track.get("BitRate", 0)) if track.get("BitRate", 0) else 0
                except (ValueError, TypeError) as e:
                    cli_ui.warning(f"Invalid BitRate value in audio track: {track.get('BitRate')}\n"
                                   f"Using 0 as default. Error: {e}.")
                    bitrate_int = 0
                return (
                    track.get("Compression_Mode") == "Lossless",
                    int(track.get("Channels", 2)),
                    "JOC" in track.get("Format_AdditionalFeatures", "") or "Atmos" in track.get("Format_Commercial", ""),
                    bitrate_int
                )

        def clean(audio_str):
            return re.sub(r"\s*-[A-Z]{3}(-[A-Z]{3})*$", "", audio_str.replace("Dual-Audio", "").replace("Dubbed", "")).strip()

        bdinfo = meta.get("bdinfo")

        if bdinfo and bdinfo.get("audio"):
            italian = [t for t in bdinfo["audio"] if t.get("language", "").lower() in ITALIAN_LANGS]
            if not italian:
                return clean(meta.get("audio", ""))
            best = max(italian, key=lambda t: extract_quality(t, True))
            audio_str, _, _ = await get_audio_v2(None, meta, {"audio": [best]})
        else:
            tracks = meta.get("mediainfo", {}).get("media", {}).get("track", [])
            italian = [
                t for t in tracks[1:]
                if t.get("@type") == "Audio"
                and self._get_language_code(t) in ITALIAN_LANGS
                and "commentary" not in str(t.get("Title", "")).lower()
            ]
            if not italian:
                return clean(meta.get("audio", ""))
            best = max(italian, key=lambda t: extract_quality(t, False))
            audio_str, _, _ = await get_audio_v2({"media": {"track": [tracks[0], best]}}, meta, None)

        return clean(audio_str)

    async def get_description(self, meta, is_test=False):
        """Generate Italian BBCode description for ShareIsland"""
        title = meta.get("title", "Unknown")
        italian_title = self._get_italian_title(meta.get("imdb_info", {}))
        if italian_title:
            title = italian_title

        category = meta.get("category", "MOVIE")

        # Build info line: resolution, source, codec, audio, language
        info_parts = []
        if meta.get("resolution"):
            info_parts.append(meta["resolution"])

        source = meta.get("source", "")
        if isinstance(source, list):
            source = source[0] if source else ""
        if source:
            info_parts.append(
                source.replace("Blu-ray", "BluRay").replace("Web", "WEB-DL")
            )

        video_codec = meta.get("video_codec", "")
        if "HEVC" in video_codec or "H.265" in video_codec:
            info_parts.append("x265")
        elif "AVC" in video_codec or "H.264" in video_codec:
            info_parts.append("x264")
        elif video_codec:
            info_parts.append(video_codec)

        if meta.get("hdr") and meta["hdr"] != "SDR":
            info_parts.append(meta["hdr"])

        audio = await self._get_best_italian_audio_format(meta)
        if audio:
            info_parts.append(audio)

        if meta.get("audio_languages"):
            langs = [
                self._get_italian_language_name(self._get_language_code(lang))
                for lang in meta["audio_languages"]
            ]
            langs = [lang for lang in langs if lang]
            if "Italiano" in langs:
                info_parts.append("Italiano")
            elif "Inglese" in langs:
                info_parts.append("Inglese")
            elif langs:
                info_parts.append(langs[0].title())

        info_line = " ".join(info_parts)

        # Fetch TMDb data and format components
        summary, logo_url = await self._fetch_tmdb_italian(meta)
        screens = await self._format_screens_italian(meta)
        synthetic_mi = await self._get_synthetic_mediainfo(meta)

        bbcode = self._build_bbcode(
            title, info_line, logo_url, summary, screens, synthetic_mi, category, meta
        )

        custom_description_header = self.config.get("DEFAULT", {}).get(
            "custom_description_header", ""
        )
        if custom_description_header:
            bbcode = bbcode.replace(
                "[code]\n", f"[code]\n{custom_description_header}\n\n"
            )

        if not is_test:
            desc_file = (
                f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
            )
            async with aiofiles.open(desc_file, "w", encoding="utf-8") as f:
                await f.write(bbcode)

        return {"description": bbcode}

    async def _fetch_tmdb_italian(self, meta):
        """Fetch Italian overview and logo from TMDb API"""
        api_key = self.config.get("DEFAULT", {}).get("tmdb_api", "N/A")
        tmdb_id = meta.get("tmdb", "")

        summary = "Riassunto non disponibile."
        logo_url = ""

        if not tmdb_id:
            return summary, logo_url

        # Use /tv/ endpoint for series, /movie/ for films
        category = meta.get("category", "MOVIE")
        media_type = "tv" if category == "TV" else "movie"

        try:
            url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
            params = {"api_key": api_key, "language": "it-IT"}
            resp = await asyncio.to_thread(
                requests.get, url, params=params, timeout=5, verify=certifi.where()
            )
            resp.encoding = "utf-8"

            if resp.status_code == 200:
                data = resp.json()
                raw_summary = data.get("overview", "Riassunto non disponibile.")
                summary = " ".join(raw_summary.split())

                # Try meta logo first, then fetch from TMDb
                logo_path = meta.get("tmdb_logo", "")
                if logo_path:
                    logo_url = f"https://image.tmdb.org/t/p/w300/{logo_path}"
                else:
                    img_url = (
                        f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images"
                    )
                    img_resp = await asyncio.to_thread(
                        requests.get,
                        img_url,
                        params={"api_key": api_key},
                        timeout=5,
                        verify=certifi.where(),
                    )
                    if img_resp.status_code == 200:
                        img_data = img_resp.json()
                        logos = img_data.get("logos", [])
                        # Priority: Italian > English > any other > first available
                        logo_url = ""
                        fallback_logo = None
                        for logo in logos:
                            lang = logo.get("iso_639_1")
                            path = logo.get("file_path")
                            if lang == "it":
                                logo_url = f"https://image.tmdb.org/t/p/w300{path}"
                                break
                            elif lang == "en" and not logo_url:
                                logo_url = f"https://image.tmdb.org/t/p/w300{path}"
                            elif not fallback_logo:
                                fallback_logo = path
                        # Use fallback if no Italian/English found
                        if not logo_url and fallback_logo:
                            logo_url = f"https://image.tmdb.org/t/p/w300{fallback_logo}"
        except Exception as e:
            print(f"[DEBUG] TMDb fetch error: {e}")

        return summary, logo_url

    async def _format_screens_italian(self, meta):
        """Format up to 6 screenshots in 2-column grid with [img=350]"""
        images = meta.get("image_list", [])
        if not images:
            return "[center]Nessuno screenshot disponibile[/center]"

        screens = []
        for img in images[:6]:
            raw_url = img.get("raw_url", "")
            web_url = img.get("web_url", raw_url)
            if raw_url:
                screens.append(f"[url={web_url}][img=350]{raw_url}[/img][/url]")

        if not screens:
            return "[center]Nessuno screenshot disponibile[/center]"

        # 2 screenshots per row
        row1 = (
            " ".join(screens[:2]) + " \n"
            if len(screens) >= 2
            else " ".join(screens) + " \n"
        )
        row2 = " ".join(screens[2:4]) + " \n" if len(screens) > 2 else ""
        row3 = " ".join(screens[4:6]) + " \n" if len(screens) > 4 else ""
        return f"[center]{row1}{row2}{row3}[/center]"

    async def _get_synthetic_mediainfo(self, meta):
        """Extract formatted mediainfo from meta.json structure"""

        def safe_int(val, default=0):
            """Convert to int, handling dict/None cases"""
            try:
                return default if isinstance(val, dict) else int(val)
            except (ValueError, TypeError):
                return default

        def get_audio_format_details(audio_track):
            """Map raw audio formats to commercial names"""
            fmt_map = {
                "E-AC-3": ("DDP", "Dolby Digital Plus"),
                "AC-3": ("DD", "Dolby Digital"),
                "TrueHD": ("TrueHD", "Dolby TrueHD"),
                "MLP FBA": ("TrueHD", "Dolby TrueHD"),
                "DTS-HD MA": ("DTS-HD MA", "DTS-HD Master Audio"),
                "AAC": ("AAC", "Advanced Audio Codec"),
            }

            if not audio_track:
                return "AAC", "AAC"

            fmt_raw = audio_track.get("Format", "AAC")

            # Detect Atmos in MLP FBA streams
            if fmt_raw == "MLP FBA":
                commercial = audio_track.get("Format_Commercial_IfAny", "")
                if isinstance(commercial, str) and "atmos" in commercial.lower():
                    return "TrueHD Atmos", "Dolby TrueHD with Atmos"

            return fmt_map.get(fmt_raw, (fmt_raw, fmt_raw))

        try:
            mi = meta.get("mediainfo", {}).get("media", {})
            tracks = mi.get("track", [])

            # Parse track types
            general = next((t for t in tracks if t.get("@type") == "General"), {})
            video = next((t for t in tracks if t.get("@type") == "Video"), {})
            audio_tracks = [t for t in tracks if t.get("@type") == "Audio"]
            text_tracks = [t for t in tracks if t.get("@type") == "Text"]

            # Prefer Italian audio, fallback to first track
            ita_audio = next(
                (t for t in audio_tracks if self._get_language_code(t) == "it"), None
            )
            if not ita_audio and audio_tracks:
                ita_audio = audio_tracks[0]

            # General info
            filelist = meta.get("filelist", [])
            fn = (
                os.path.basename(filelist[0])
                if filelist
                else general.get("FileName", "file.mkv")
            )
            size = f"{safe_int(general.get('FileSize', 0)) / (1024**3):.1f} GiB"

            dur_sec = float(general.get("Duration", 0))
            hours = safe_int(dur_sec // 3600)
            minutes = safe_int((dur_sec % 3600) // 60)
            dur = f"{hours} h {minutes} min" if hours > 0 else f"{minutes} min"

            total_br = (
                f"{safe_int(general.get('OverallBitRate', 0)) / 1000000:.1f} Mb/s"
            )
            chap = "Si" if safe_int(general.get("MenuCount", 0)) > 0 else "No"

            # Video info
            vid_format = video.get("Format", "N/A")
            vid_format_upper = vid_format.upper()
            if "HEVC" in vid_format_upper:
                codec = "x265"
            elif "AVC" in vid_format_upper or "H.264" in vid_format_upper:
                codec = "x264"
            elif "MPEG VIDEO" in vid_format_upper or "MPEG-2" in vid_format_upper:
                codec = "MPEG-2"
            elif "VC-1" in vid_format_upper or "VC1" in vid_format_upper:
                codec = "VC-1"
            else:
                codec = vid_format  # Fallback to format name
            depth = f"{video.get('BitDepth', 10)} bits"
            vid_br = f"{safe_int(video.get('BitRate', 0)) / 1000000:.1f} Mb/s"
            res = meta.get("resolution", "N/A")
            asp_decimal = video.get("DisplayAspectRatio")
            asp_float = float(asp_decimal) if asp_decimal else 0.0
            if 1.77 <= asp_float <= 1.79:
                asp = "16:9"
            elif 1.32 <= asp_float <= 1.34:
                asp = "4:3"
            elif 2.35 <= asp_float <= 2.45:
                asp = "2.39:1"
            else:
                asp = f"{asp_float:.2f}:1" if asp_float != 0.0 else "N/A"

            # Audio info
            afmt = ita_audio.get("Format", "N/A") if ita_audio else "N/A"

            # Try commercial name from mediainfo, fallback to mapping
            afmt_name = (
                ita_audio.get("Format_Commercial_IfAny", "") if ita_audio else ""
            )
            if isinstance(afmt_name, dict) or not afmt_name:
                afmt_name = ita_audio.get("Title", "") if ita_audio else ""
            if isinstance(afmt_name, dict) or not afmt_name:
                _, afmt_name = (
                    get_audio_format_details(ita_audio) if ita_audio else ("", afmt)
                )

            # Map channel count to standard format
            ch = ita_audio.get("Channels", "2") if ita_audio else "2"
            if ch == "6":
                ch = "5.1"
            elif ch == "8":
                ch = "7.1"
            elif ch == "2":
                ch = "2.0"

            aud_br = (
                f"{safe_int(ita_audio.get('BitRate', 0)) / 1000:.0f} kb/s"
                if ita_audio
                else "0 kb/s"
            )
            if ita_audio:
                audio_lang_code = self._get_language_code(ita_audio)
                lang = (
                    self._get_italian_language_name(audio_lang_code)
                    if audio_lang_code
                    else "Inglese"
                )
            else:
                lang = "Inglese"

            # Subtitle languages
            if text_tracks:
                sub_langs = set()
                for t in text_tracks:
                    lang_code = self._get_language_code(t)
                    if lang_code:
                        lang_name = self._get_italian_language_name(lang_code)
                        if lang_name:
                            sub_langs.add(lang_name.title())
                subs = ", ".join(sorted(sub_langs)) if sub_langs else "Assenti"
            else:
                subs = "Assenti"

            return {
                "fn": fn,
                "size": size,
                "dur": dur,
                "total_br": total_br,
                "chap": chap,
                "vid_format": vid_format,
                "codec": codec,
                "depth": depth,
                "vid_br": vid_br,
                "res": res,
                "asp": asp,
                "aud_format": afmt,
                "aud_name": afmt_name,
                "ch": ch,
                "aud_br": aud_br,
                "lang": lang,
                "subs": subs,
            }
        except Exception as e:
            print(f"[DEBUG] Mediainfo extraction error: {e}")
            import traceback

            traceback.print_exc()
            return None

    def _strip_bbcode(self, text):
        """Remove BBCode tags from text, keeping only plain content"""
        pattern = re.compile(r"\[/?[^\]]+\]")
        return pattern.sub("", text).strip()

    def _build_bbcode(
        self, title, info_line, logo_url, summary, screens, synthetic_mi, category, meta
    ):
        """Build ShareIsland BBCode template"""
        if category == "TV":
            is_pack = meta.get("tv_pack", 0) == 1
            category_header = (
                "--- SERIE TV (STAGIONE) ---"
                if is_pack
                else "--- SERIE TV (EPISODIO) ---"
            )
        else:
            category_header = "--- FILM ---"
        release_group = meta.get("tag", "").lstrip("-").strip()

        tonemapped_text = ""
        if meta.get("tonemapped", False):
            tonemapped_header = self.config.get("DEFAULT", {}).get(
                "tonemapped_header", ""
            )
            if tonemapped_header:
                tonemapped_text = self._strip_bbcode(tonemapped_header)

        if release_group.lower() == "island":
            base_notes = "Questa è una release interna pubblicata in esclusiva su Shareisland.\nSi prega di non ricaricare questa release su tracker pubblici o privati. Si prega di mantenerla in seed il più a lungo possibile. Grazie!"
            if tonemapped_text:
                release_notes_section = f"""[size=13][b][color=#e8024b]--- RELEASE NOTES ---[/color][/b][/size]
[size=11][color=#FFFFFF]{base_notes}
{tonemapped_text}[/color][/size]"""
            else:
                release_notes_section = f"""[size=13][b][color=#e8024b]--- RELEASE NOTES ---[/color][/b][/size]
[size=11][color=#FFFFFF]{base_notes}[/color][/size]"""
        else:
            base_notes = "Nulla da aggiungere."
            if tonemapped_text:
                release_notes_section = f"""[size=13][b][color=#e8024b]--- RELEASE NOTES ---[/color][/b][/size]
[size=11][color=#FFFFFF]{tonemapped_text}[/color][/size]"""
            else:
                release_notes_section = f"""[size=13][b][color=#e8024b]--- RELEASE NOTES ---[/color][/b][/size]
[size=11][color=#FFFFFF]{base_notes}[/color][/size]"""

        pirate_shouts = [
            "The Scene never dies",
            "Arrr! Powered by Rum & Bandwidth",
            "Seed or walk the plank!",
            "Released by Nobody — claimed by Everybody",
            "From the depths of the digital seas",
            "Where bits are free and rum flows endlessly",
            "Pirates don't ask, they share",
            "For the glory of the Scene!",
            "Scene is the paradise",
        ]
        if not release_group or release_group.lower() in [
            "nogroup",
            "nogrp",
            "unknown",
            "unk",
        ]:
            shoutouts = f"SHOUTOUTS : {random.choice(pirate_shouts)}"
        else:
            shoutouts = f"SHOUTOUTS : {release_group}"
        logo_section = (
            f"[center][img=250]{logo_url}[/img][/center]\n" if logo_url else ""
        )

        # Build LINKS section
        imdb_id = meta.get("imdb", "")
        tmdb_id = meta.get("tmdb", "")
        media_type = "tv" if category == "TV" else "movie"

        links_section = ""
        if imdb_id or tmdb_id:
            links_section = (
                "\n[size=13][b][color=#e8024b]--- LINKS ---[/color][/b][/size]\n"
            )
            if imdb_id:
                links_section += f"[size=11][color=#FFFFFF]IMDb: https://www.imdb.com/title/tt{imdb_id}/[/color][/size]\n"
            if tmdb_id:
                links_section += f"[size=11][color=#FFFFFF]TMDb: https://www.themoviedb.org/{media_type}/{tmdb_id}[/color][/size]\n"
            links_section += "\n"

        ua_sig = meta.get("ua_signature", "Generated by Upload Assistant")

        # Mediainfo section
        mediainfo_section = ""
        if synthetic_mi:
            mediainfo_section = f"""[size=13][b][color=#da8d49]INFO GENERALI[/color][/b][/size]
[size=11][color=#FFFFFF]Nome File       : {synthetic_mi['fn']}[/color][/size]
[size=11][color=#FFFFFF]Dimensioni File : {synthetic_mi['size']}[/color][/size]
[size=11][color=#FFFFFF]Durata          : {synthetic_mi['dur']}[/color][/size]
[size=11][color=#FFFFFF]Bitrate Totale  : {synthetic_mi['total_br']}[/color][/size]
[size=11][color=#FFFFFF]Capitoli        : {synthetic_mi['chap']}[/color][/size]

[size=13][b][color=#da8d49]VIDEO[/color][/b][/size]
[size=11][color=#FFFFFF]Formato         : {synthetic_mi['vid_format']}[/color][/size]
[size=11][color=#FFFFFF]Compressore     : {synthetic_mi['codec']}[/color][/size]
[size=11][color=#FFFFFF]Profondità Bit  : {synthetic_mi['depth']}[/color][/size]
[size=11][color=#FFFFFF]Bitrate         : {synthetic_mi['vid_br']}[/color][/size]
[size=11][color=#FFFFFF]Risoluzione     : {synthetic_mi['res']}[/color][/size]
[size=11][color=#FFFFFF]Rapporto        : {synthetic_mi['asp']}[/color][/size]

[size=13][b][color=#da8d49]AUDIO[/color][/b][/size]
[size=11][color=#FFFFFF]Formato         : {synthetic_mi['aud_format']}[/color][/size]
[size=11][color=#FFFFFF]Nome            : {synthetic_mi['aud_name']}[/color][/size]
[size=11][color=#FFFFFF]Canali          : {synthetic_mi['ch']}[/color][/size]
[size=11][color=#FFFFFF]Bitrate         : {synthetic_mi['aud_br']}[/color][/size]
[size=11][color=#FFFFFF]Lingua          : {synthetic_mi['lang']}[/color][/size]

[size=13][b][color=#da8d49]SOTTOTITOLI[/color][/b][/size]
[size=11][color=#FFFFFF]{synthetic_mi['subs']}[/color][/size]

"""

        bbcode = f"""[code]
{logo_section}[center][size=13][b][color=#e8024b]{category_header}[/color][/b][/size][/center]
[center][size=13][b][color=#ffffff]{title}[/color][/b][/size][/center]
[center][size=13][color=#ffffff]{info_line}[/color][/size][/center]

[center][size=13][b][color=#e8024b]--- RIASSUNTO ---[/color][/b][/size][/center]
{summary}

[center][size=13][b][color=#e8024b]--- SCREENS ---[/color][/b][/size][/center]
{screens}
{links_section}{mediainfo_section}{release_notes_section}

[size=13][b][color=#e8024b]--- SHOUTOUTS ---[/color][/b][/size]
[size=11][color=#FFFFFF]{shoutouts}[/color][/size]

[size=13][color=#0592a3][size=16][b]BUON DOWNLOAD![/b][/size][/color][/size]

[right][size=8]{ua_sig}[/size][/right]
[/code]"""

        return bbcode
