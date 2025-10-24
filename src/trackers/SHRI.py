# -*- coding: utf-8 -*-
from typing import Literal
import cli_ui
import os
import pycountry
import re
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

        effective_type = self._get_effective_type(meta)

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
        """Extract release group if not already in the calculated name"""
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
            or self.INVALID_TAG_PATTERN.search(potential_tag)
        ):
            return "NoGroup"

        # Special case: UNTOUCHED/VU at end is valid tag, don't reject
        if self.MARKER_PATTERN.search(potential_tag):
            return potential_tag

        # Check against calculated name
        name_normalized = (
            current_name.lower()
            .replace("-", "")
            .replace(".", "")
            .replace(" ", "")
            .replace("_", "")
        )
        tag_normalized = potential_tag.lower().replace("_", "")

        if tag_normalized in name_normalized:
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
            "HDTV": "6",
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
            effective_type = self._get_effective_type(meta)
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
        base_type = meta.get("type", "ENCODE")
        if base_type in ("DISC", "DVDRIP", "BRRIP"):
            return base_type
        # Priority 1: Explicit REMUX markers
        if self._has_remux_marker(meta):
            return "REMUX"
        # Priority 2: Technical analysis
        return self._analyze_encode_type(meta)

    def _has_remux_marker(self, meta):
        """Check filename for REMUX indicators"""
        name_no_ext = os.path.splitext(self.get_basename(meta))[0].lower()
        if "remux" in name_no_ext:
            return True
        match = self.MARKER_PATTERN.search(name_no_ext)
        if match and not name_no_ext.endswith(f"-{match.group(0).lower()}"):
            return True
        return False

    def _analyze_encode_type(self, meta):
        """
        Detect release type from MediaInfo technical analysis.

        Priority order:
        1. DV profile (05/07/08) + no encoding -> WEB-DL (overrides source field)
        2. CRF in settings -> WEBRIP/ENCODE
        3. Service fingerprints -> WEB-DL (CR/Netflix patterns)
        4. BluRay empty metadata -> ENCODE (GPU stripped)
        5. Encoding tools (source-aware) -> WEBRIP/ENCODE
        6. No encoding + WEB -> WEB-DL
        7. No encoding + disc -> REMUX
        """

        def has_encoding_tools(general_track, tools):
            """Check if general track contains specified encoding tools"""
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

            # Priority 1: DV profiles 5/7/8 indicate streaming (overrides source field)
            hdr_profile = video_track.get("HDR_Format_Profile", "")
            has_streaming_dv = any(
                prof in hdr_profile for prof in ["dvhe.05", "dvhe.07", "dvhe.08"]
            )

            if has_streaming_dv and not encoding_settings:
                if not has_encoding_tools(
                    general_track, ["handbrake", "staxrip", "megatagger"]
                ):
                    return "WEBDL"

            # Priority 2: CRF indicates user re-encode
            if "crf=" in encoding_settings:
                return "WEBRIP" if any("WEB" in s for s in source) else "ENCODE"

            # Priority 3: Service fingerprints
            if service == "CR":
                if "core 142" in encoded_library:
                    return "WEBDL"
                if has_library:
                    core_match = re.search(r"core (\d+)", encoded_library)
                    if core_match and int(core_match.group(1)) >= 152:
                        return "WEBRIP"
                if encoding_settings and "bitrate=" in encoding_settings:
                    return "WEBDL"

            # Netflix fingerprint
            format_profile = video_track.get("Format_Profile", "")
            if "Main@L4.0" in format_profile and "rc=2pass" in encoding_settings:
                if "core 118" in encoded_library or "core 148" in encoded_library:
                    return "WEBDL"

            # Priority 4: BluRay empty metadata indicates GPU encode
            if any(s in ("BLURAY", "BLU-RAY") for s in source):
                bit_depth = video_track.get("BitDepth")
                chroma = video_track.get("ChromaSubsampling")
                if isinstance(bit_depth, dict) and isinstance(chroma, dict):
                    return "ENCODE"

            # Priority 5: Encoding tools (source-aware)
            # BluRay: x264/x265 indicates re-encode
            if any(s in ("BLURAY", "BLU-RAY") for s in source):
                if has_encoding_tools(
                    general_track,
                    ["x264", "x265", "handbrake", "staxrip", "megatagger"],
                ):
                    return "ENCODE"

            # WEB: only explicit user tools indicate re-encode
            if any("WEB" in s for s in source):
                if has_encoding_tools(
                    general_track, ["handbrake", "staxrip", "megatagger"]
                ):
                    return "WEBRIP"

            # Priority 6: No encoding + WEB = WEB-DL
            if any("WEB" in s for s in source):
                return "WEBDL"

            # Priority 7: No encoding + disc = REMUX
            if any(s in ("BLURAY", "BLU-RAY", "HDDVD") for s in source):
                return "REMUX"

        except (IndexError, KeyError):
            pass

        return meta.get("type", "ENCODE")

    def _get_effective_type(self, meta):
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
        cli_ui.info(f"{self.tracker} Detected type: {detected_type}")
        return detected_type

    def _get_italian_title(self, imdb_info):
        """Extract Italian title from IMDb AKAs with priority"""
        country_match = None
        language_match = None

        for aka in imdb_info.get("akas", []):
            if isinstance(aka, dict):
                if aka.get("country") == "Italy":
                    country_match = aka.get("title")
                    break  # Country match takes priority
                elif aka.get("language") == "Italy" and not language_match:
                    language_match = aka.get("title")

        return country_match or language_match

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

    async def _get_best_italian_audio_format(self, meta):
        """Filter Italian tracks, select best, format via get_audio_v2"""
        # fmt: off
        ITALIAN_LANGS = {"it", "it-it", "italian", "italiano"}

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
                and isinstance(t.get("Language"), str)
                and t.get("Language", "").lower() in ITALIAN_LANGS
                and "commentary" not in str(t.get("Title", "")).lower()
            ]
            if not italian:
                return clean(meta.get("audio", ""))
            best = max(italian, key=lambda t: extract_quality(t, False))
            audio_str, _, _ = await get_audio_v2({"media": {"track": [tracks[0], best]}}, meta, None)

        return clean(audio_str)
