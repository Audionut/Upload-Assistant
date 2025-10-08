# -*- coding: utf-8 -*-
import pycountry
import re
import os
from src.console import console
from src.languages import process_desc_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

_shri_session_data = {}


class SHRI(UNIT3D):
    """ShareIsland tracker implementation with Italian localization support"""

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
        - BDMV region injection
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
        audio = meta.get("audio", "").replace("Dual-Audio", "").strip()
        audio = re.sub(r"\s*-[A-Z]{3}(-[A-Z]{3})*$", "", audio).strip()

        # Build audio language tag: original → ITALIAN → others (Multi for 4+)
        audio_lang_str = ""
        if meta.get("audio_languages"):
            audio_langs = [lang.upper() for lang in meta["audio_languages"]]
            audio_langs = list(dict.fromkeys(audio_langs))

            orig_lang_iso = meta.get("original_language", "").upper()
            orig_lang_full = self._get_language_name(orig_lang_iso)

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
            name = meta["name"]

            # Apply Italian title if enabled
            if italian_title and use_italian_title:
                name = name.replace(meta.get("title", ""), italian_title, 1)

            # Remove tag
            tag = meta.get("tag", "").strip()
            if tag:
                name = name.replace(tag, "")

            # Remove AKA
            aka = meta.get("aka", "")
            if aka:
                name = name.replace(f"{aka}", "")

            # DVD: add resolution before source, codec before audio
            if meta.get("is_disc") == "DVD":
                if resolution and source:
                    name = name.replace(source, f"{resolution} {source}", 1)
                if video_codec and audio:
                    name = name.replace(audio, f"{video_codec} {audio}", 1)

            # BDMV: inject resolution and region
            elif meta.get("is_disc") == "BDMV":
                if resolution and f" {resolution} " not in name:
                    parts = name.split()
                    if year in parts:
                        idx = parts.index(year) + 1
                        parts.insert(idx, resolution)
                        name = " ".join(parts)

                name = await self.finalize_disc_name(meta, name)

        elif effective_type == "REMUX":
            # REMUX: Title Year Edition 3D LANG Hybrid REPACK Resolution UHD Source REMUX HDR VideoCodec Audio
            name = f"{title} {year} {season}{episode} {episode_title} {part} {edition} {three_d} {audio_lang_str} {hybrid} {repack} {resolution} {uhd} {source} REMUX {hdr} {video_codec} {audio}"

        elif effective_type in ("DVDRIP", "BRRIP"):
            type_str = "DVDRip" if effective_type == "DVDRIP" else "BRRip"
            # DVDRip/BRRip: Title Year Edition LANG Hybrid REPACK Resolution Type Audio HDR VideoCodec
            name = f"{title} {year} {season} {edition} {audio_lang_str} {hybrid} {repack} {resolution} {type_str} {audio} {hdr} {video_encode}"

        elif effective_type in ("ENCODE", "HDTV"):
            # Encode/HDTV: Title Year Edition LANG Hybrid REPACK Resolution UHD Source Audio HDR VideoCodec
            name = f"{title} {year} {season}{episode} {episode_title} {part} {edition} {audio_lang_str} {hybrid} {repack} {resolution} {uhd} {source} {audio} {hdr} {video_encode}"

        elif effective_type in ("WEBDL", "WEBRIP"):
            service = meta.get("service", "")
            type_str = "WEB-DL" if effective_type == "WEBDL" else "WEBRip"
            # WEB: Title Year Edition LANG Hybrid REPACK Resolution UHD Service Type Audio HDR VideoCodec
            name = f"{title} {year} {season}{episode} {episode_title} {part} {edition} {audio_lang_str} {hybrid} {repack} {resolution} {uhd} {service} {type_str} {audio} {hdr} {video_encode}"

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

    async def get_additional_checks(self, meta):
        """
        Validate and prompt for BDMV region/distributor before upload.
        Stores validated IDs in module-level dict keyed by UUID for use during upload.
        """
        if meta.get("is_disc") == "BDMV":
            region_name = meta.get("region")

            # Prompt for region if not in meta
            if not region_name:
                if not meta.get("unattended") or meta.get("unattended_confirm"):
                    while True:
                        region_name = (
                            input(
                                "SHRI: Region code not found for disc. Please enter it manually (mandatory): "
                            )
                            .strip()
                            .upper()
                        )
                        if region_name:
                            break
                        print("Region code is required.")

            # Validate region name was provided
            if not region_name:
                console.print("[bold red]Region required; skipping SHRI.[/bold red]")
                return False

            # Validate region code with API
            region_id = await self.common.unit3d_region_ids(region_name)
            if not region_id:
                console.print(
                    f"[bold red]Invalid region code '{region_name}'; skipping SHRI.[/bold red]"
                )
                return False

            # Handle optional distributor
            distributor_name = meta.get("distributor")
            if not distributor_name and not meta.get("unattended"):
                distributor_name = (
                    input("SHRI: Distributor (optional, Enter to skip): ")
                    .strip()
                    .upper()
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

    async def finalize_disc_name(self, meta, name):
        """
        Inject region code into BDMV release name after resolution/edition.
        Uses region name stored during validation phase.
        """
        data = _shri_session_data.get(meta["uuid"], {})
        region_name = data.get("_shri_region_name")

        # Only inject if region was validated and not already in name
        if region_name and f" {region_name} " not in name:
            resolution = meta.get("resolution", "")
            edition = meta.get("edition", "")

            if edition:
                name = name.replace(
                    f"{resolution} {edition}",
                    f"{resolution} {edition} {region_name}",
                    1,
                )
            elif resolution:
                name = name.replace(resolution, f"{resolution} {region_name}", 1)

        return name

    def get_basename(self, meta):
        """Extract basename from first file in filelist or path"""
        path = next(iter(meta["filelist"]), meta["path"])
        return os.path.basename(path)

    def _is_remux(self, meta):
        """
        Detect REMUX releases via filename markers or mediainfo analysis.

        Methods:
        - Filename markers: remux, vu, untouched (excludes group tags at end)
        - Mediainfo: no encoding settings + BluRay/HDDVD source
        """
        basename = self.get_basename(meta)
        # Remove extension to check markers properly
        name_no_ext = os.path.splitext(basename)[0].lower()

        if "remux" in name_no_ext:
            return True

        # Check for VU/UNTOUCHED markers (not at end as group tag)
        for marker in ["vu", "untouched", "vu1080", "vu720"]:
            if marker in name_no_ext and not name_no_ext.endswith(f"-{marker}"):
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
