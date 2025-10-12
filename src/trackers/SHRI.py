# -*- coding: utf-8 -*-
import cli_ui
import os
import pycountry
import re
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

        # Build audio language tag: original → ITALIAN → ENGLISH → others/Multi (4+)
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

            # Handle remaining: show individually if ≤3 total, else add Multi
            if len(result) + len(remaining) > 3:
                result.append("Multi")
            else:
                result.extend(remaining)

            audio_lang_str = " - ".join(result)

        effective_type = self._get_effective_type(meta)

        # Detect Hybrid from filename if not in title
        hybrid = ""
        basename_upper = self.get_basename(meta).upper()
        if "HYBRID" in basename_upper and "HYBRID" not in title.upper():
            hybrid = "Hybrid"

        repack = meta.get("repack", "").strip()

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

        # Add [SUBS] for Italian subtitles without Italian audio
        if not self._has_italian_audio(meta) and self._has_italian_subtitles(meta):
            name = f"{name} [SUBS]"

        # Extract and clean release group tag
        tag = meta.get("tag", "").strip()
        if not tag:
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

            # Extract tag after last hyphen
            if "-" in name_no_ext:
                potential_tag = name_no_ext.split("-")[-1]
                if (
                    potential_tag
                    and len(potential_tag) <= 30
                    and potential_tag.replace("_", "").replace(".", "").isalnum()
                ):
                    tag = potential_tag

        # Clean and validate tag
        tag = tag.lstrip("-").strip()
        tag = re.sub(r"^[A-Z]{2,3}\s+", "", tag)

        if not tag or self.INVALID_TAG_PATTERN.search(tag):
            tag = "NoGroup"

        name = f"{name}-{tag}"
        name = self.WHITESPACE_PATTERN.sub(" ", name).strip()

        return {"name": name}

    async def get_type_id(self, meta):
        """Map release type to ShareIsland type IDs"""
        effective_type = self._get_effective_type(meta)
        type_id = {
            "CINEMA_NEWS": "42",
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

    async def get_additional_checks(self, meta):
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
                return False

            # Validate region code with API
            region_id = await self.common.unit3d_region_ids(region_name)
            if not region_id:
                cli_ui.error(f"Invalid region code '{region_name}'; skipping SHRI.")
                return False

            # Handle optional distributor
            distributor_name = meta.get("distributor")
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
        """Distinguish REMUX/WEBDL/WEBRIP/ENCODE via MediaInfo"""
        try:
            mi = meta.get("mediainfo", {})
            video_track = mi.get("media", {}).get("track", [{}])[1]
            source = meta.get("source", "").upper()
            # Has encode settings = definitely encoded
            if video_track.get("Encoded_Library_Settings"):
                return "WEBRIP" if "WEB" in source else "ENCODE"
            # Profile 8 = streaming-only
            if "dvhe.08" in video_track.get("HDR_Format_Profile", ""):
                return "WEBDL"
            # No encode settings + WEB source = WEB-DL
            if "WEB" in source:
                return "WEBDL"
            # No encode settings + disc source = REMUX
            if source in ("BLURAY", "HDDVD"):
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

        return self._detect_type_from_technical_analysis(meta)

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
        """Select best quality Italian audio track and format as string"""
        # fmt: off
        AUDIO = {
            "DTS": "DTS", "AAC": "AAC", "AAC LC": "AAC", "AC-3": "DD", 
            "E-AC-3": "DD+", "Enhanced AC-3": "DD+", "MLP FBA": "TrueHD",
            "FLAC": "FLAC", "Opus": "Opus", "PCM": "LPCM",
            "Dolby Digital Audio": "DD", "Dolby Digital Plus Audio": "DD+",
            "Dolby TrueHD Audio": "TrueHD", "DTS Audio": "DTS",
            "DTS-HD Master Audio": "DTS-HD MA", "DTS-HD High-Res Audio": "DTS-HD HRA"
        }
        COMMERCIAL_NAMES = {
            "Dolby Digital": "DD", "Dolby Digital Plus": "DD+",
            "Dolby TrueHD": "TrueHD", "DTS-ES": "DTS-ES",
            "DTS-HD Master Audio": "DTS-HD MA"
        }
        AUDIO_EXTRA = {"XLL": "-HD MA", "XLL X": ":X", "ES": "-ES"}
        FORMAT_EXTRA = {"JOC": " Atmos", "16-ch": " Atmos", "Atmos Audio": " Atmos"}
        FORMAT_SETTINGS_EXTRA = {"Dolby Surround EX": "EX"}
        def clean(s):
            return re.sub(r"\s*-[A-Z]{3}(-[A-Z]{3})*$", "", s.replace("Dual-Audio", "")).strip()
        def has_object_audio(t):
            return any(x in t["additional"] + t["codec"] for x in ["JOC", "Atmos", "16-ch", "DTS:X", "DTS-X"])
        def normalize_track(lang, codec, additional, channels, chan_str, bitrate, lossless, profile, settings):
            """Create unified track structure"""
            return {
                "lang": str(lang).lower(), "codec": str(codec), "additional": str(additional),
                "channels": channels, "chan_str": chan_str, "bitrate": bitrate,
                "lossless": lossless, "profile": str(profile), "settings": str(settings)
            }
        tracks = []
        bdinfo = meta.get("bdinfo") or {}
        try:
            if bdinfo.get("audio"):
                for t in bdinfo["audio"]:
                    channels = int(float(t.get("channels", "2.0").split(".")[0]))
                    bitrate_match = re.search(r'(\d+)', t.get("bitrate", "0"))
                    tracks.append(normalize_track(
                        lang=t.get("language", ""), codec=t.get("codec", ""), additional=t.get("atmos_why_you_be_like_this", ""),
                        channels=channels, chan_str=t.get("channels", "2.0"), bitrate=int(bitrate_match.group(1)) * 1000 if bitrate_match else 0,
                        lossless=any(x in t.get("codec", "").lower() for x in ["truehd", "dts-hd ma", "flac", "pcm"]), profile="", settings=""
                    ))
            else:
                for t in meta.get("mediainfo", {}).get("media", {}).get("track", []):
                    if t.get("@type") != "Audio":
                        continue
                    channels = int(t.get("Channels", 2))
                    layout = t.get("ChannelLayout") or t.get("ChannelPositions", "")
                    tracks.append(normalize_track(
                        lang=str(t.get("Language", "")), codec=t.get("Format_Commercial") or t.get("Format", ""), additional=t.get("Format_AdditionalFeatures", ""),
                        channels=channels, chan_str=f"{channels - 1}.1" if "LFE" in layout else f"{channels}.0", bitrate=int(t.get("BitRate", 0)),
                        lossless=t.get("Compression_Mode") == "Lossless", profile=t.get("Format_Profile", ""), settings=t.get("Format_Settings", "")
                    ))
            italian = [t for t in tracks if t["lang"] in {"it", "it-it", "italian", "italiano"}]
            if not italian:
                return clean(meta.get("audio", ""))
            
            best = max(italian, key=lambda t: (t["lossless"], t["channels"], has_object_audio(t), t["bitrate"]))
            
            format_name = COMMERCIAL_NAMES.get(best["codec"]) or AUDIO.get(best["codec"]) or best["codec"]
            # Apply audio_extra (profile suffixes like -HD MA)
            for key, suffix in AUDIO_EXTRA.items():
                if key in best["profile"]:
                    format_name += suffix
            result = f"{format_name} {best['chan_str']}"
            # Apply format_extra (Atmos, etc)
            for key, suffix in FORMAT_EXTRA.items():
                if key in best["additional"] or key in best["codec"]:
                    result += suffix
                    break
            # Apply format_settings_extra (EX, etc)
            for key, suffix in FORMAT_SETTINGS_EXTRA.items():
                if key in best["settings"]:
                    result += f" {suffix}"
                    break
        except Exception as e:
                cli_ui.warning(f"Audio format detection failed: {e}[/yellow]")
                return clean(meta.get("audio", ""))
        return clean(result)
