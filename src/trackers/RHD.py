# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any, Optional, cast

import cli_ui
import pycountry

from src.console import console
from src.languages import languages_manager
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class RHD(UNIT3D):
    WHITESPACE_PATTERN = re.compile(r"\s{2,}")

    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='RHD')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'RHD'
        self.base_url = 'https://rocket-hd.cc'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'  # If the site supports requests via API, otherwise remove this line
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = ["1XBET", "MEGA", "MTZ", "Whistler", "WOTT", "Taylor.D", "HELD", "FSX", "FuN", "MagicX", "w00t", "PaTroL", "BB",
                              "266ers", "GTF", "JellyfinPlex", "2BA", "FritzBox"]
        pass

    # The section below can be deleted if no changes are needed, as everything else is handled in UNIT3D.py
    # If advanced changes are required, copy the necessary functions from UNIT3D.py here
    # For example, if you need to modify the description, copy and paste the 'get_description' function and adjust it accordingly

    async def get_resolution_id(
        self,
        meta: Meta,
        resolution: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        _ = (resolution, reverse, mapping_only)
        resolution_id = {
            '8640p': '10',
            '4320p': '1',
            '2160p': '2',
            '1440p': '3',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '12',
            '576i': '13',
            '540p': '16',
            '480p': '11',
            '480i': '18',
            '384p': '14',
        }.get(meta['resolution'], '10')
        return {'resolution_id': resolution_id}

    def _get_language_code(self, track_or_string: Any) -> str:
        """Extract and normalize language to ISO alpha-2 code"""
        if isinstance(track_or_string, dict):
            track_dict = cast(dict[str, Any], track_or_string)
            lang = track_dict.get("Language", "")
            if isinstance(lang, dict):
                lang = cast(dict[str, Any], lang).get("String", "")
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

    def _get_german_title(self, imdb_info: dict[str, Any]) -> Optional[str]:
        """Extract German title from IMDb AKAs with priority"""
        country_match: Optional[str] = None
        language_match: Optional[str] = None

        akas_value = imdb_info.get("akas", [])
        akas = cast(list[dict[str, Any]], akas_value) if isinstance(akas_value, list) else []
        for aka in akas:
            if aka.get("country") == "Germany" and not aka.get("attributes"):
                title = aka.get("title")
                if isinstance(title, str):
                    country_match = title
                break  # Country match takes priority
            elif aka.get("language") == "German" and not language_match and not aka.get("attributes"):
                title = aka.get("title")
                if isinstance(title, str):
                    language_match = title

        return country_match or language_match

    def _has_german_audio(self, meta: dict[str, Any]) -> bool:
        """Check for German audio tracks, excluding commentary"""
        if "mediainfo" not in meta:
            return False

        tracks = meta["mediainfo"].get("media", {}).get("track", [])
        return any(
            track.get("@type") == "Audio"
            and self._get_language_code(track) in {"de"}
            and "commentary" not in str(track.get("Title", "")).lower()
            for track in tracks[2:]
        )

    def _has_german_subtitles(self, meta: dict[str, Any]) -> bool:
        """Check for German subtitle tracks"""
        if "mediainfo" not in meta:
            return False

        tracks = meta["mediainfo"].get("media", {}).get("track", [])
        return any(
            track.get("@type") == "Text" and self._get_language_code(track) in {"de"}
            for track in tracks
        )

    def _get_language_name(self, iso_code: str) -> str:
        """Convert ISO language code to full name (e.g. GERMAN, ENGLISH)"""
        if not iso_code:
            return ""

        iso_lower = iso_code.lower()

        # Try full language name (Italian, English, etc)
        lang = pycountry.languages.get(name=iso_code.title())
        if lang and hasattr(lang, 'name'):
            return str(lang.name).upper()

        # Try alpha_2 (IT, EN, etc)
        lang = pycountry.languages.get(alpha_2=iso_lower)
        if lang and hasattr(lang, 'name'):
            return str(lang.name).upper()

        # Try alpha_3 (ITA, ENG, etc)
        lang = pycountry.languages.get(alpha_3=iso_lower)
        if lang and hasattr(lang, 'name'):
            return str(lang.name).upper()

        return iso_code.upper()


    async def get_name(self, meta: dict[str, Any]) -> dict[str, str]:
        """
        Rebuild release name from meta components following RocketHD naming rules.

        Handles:
        - REMUX detection from filename markers (VU/UNTOUCHED)
        - German title substitution from IMDb AKAs
        - audio-language tags (ENGLISH, GERMAN, GERMAN DL, MULTI, etc.)
        - GERMAN SUBBED tag when no German audio present, but German subtitles are
        - Release group tag cleaning and validation
        - DISC region injection
        """
        if not meta.get("language_checked", False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)

        # Title and basic info
        title = meta.get("title", "")
        german_title = self._get_german_title(meta.get("imdb_info", {}))
        use_german_title = self.config["TRACKERS"][self.tracker].get(
            "use_german_title", False
        )
        if german_title and use_german_title:
            title = german_title

        year_value: Any = meta.get("year", "")
        resolution_value: Any = meta.get("resolution", "")
        source_value: Any = meta.get("source", "")
        year = str(year_value)
        resolution = str(resolution_value)
        source = (
            str(cast(Any, source_value[0])) if source_value else ""
        ) if isinstance(source_value, list) else str(source_value)
        video_codec = str(meta.get("video_codec", ""))
        video_encode = str(meta.get("video_encode", ""))

        # TV specific
        season = str(meta.get("season") or "")
        episode = str(meta.get("episode") or "")
        episode_title = str(meta.get("episode_title") or "")
        part = str(meta.get("part") or "")

        # Optional fields
        edition = str(meta.get("edition") or "")
        hdr = str(meta.get("hdr") or "")
        uhd = str(meta.get("uhd") or "")
        three_d = str(meta.get("3D") or "")

        # Clean audio: remove Dual-Audio and trailing language codes
        audio = meta.get("audio", "") #TODO: replace with get_best_german_audio function that handles Dual-Audio and other cases more robustly
        if "DD+" in audio:
            audio = audio.replace("DD+", "DDP")

        # Build audio language tag
        audio_lang_str = ""
        if meta.get("audio_languages"):
            # Normalize all to abbreviated ISO 639-3 codes
            audio_langs_value = meta.get("audio_languages", [])
            audio_langs_raw = cast(list[Any], audio_langs_value) if isinstance(audio_langs_value, list) else []
            audio_langs = [self._get_language_name(str(lang)) for lang in audio_langs_raw]
            audio_langs = [lang for lang in audio_langs if lang]  # Remove empty
            audio_langs = list(dict.fromkeys(audio_langs))  # Dedupe preserving order

            num_langs = len(audio_langs)

            if num_langs == 1:
                # One language (GERMAN or non-GERMAN)
                audio_lang_str = audio_langs[0]

            elif num_langs == 2:
                # Two languages ("GERMAN DL" if GERMAN is present, "[lang] DL" if not)
                if "GERMAN" in audio_langs:
                    audio_lang_str = "GERMAN DL"
                elif "ENGLISH" in audio_langs:
                    audio_lang_str = "ENGLISH DL"
                else:
                    audio_lang_str = f"{audio_langs[0]} DL"

            elif num_langs >= 3:
                # Three or more languages, "GERMAN ML" if GERMAN is present, "MULTI" only if not)
                audio_lang_str = "GERMAN ML" if "GERMAN" in audio_langs else "MULTI"

        # Add [GERMAN SUBBED] for German subtitles without German audio
        if not self._has_german_audio(meta) and self._has_german_subtitles(meta):
            audio_lang_str = "GERMAN SUBBED"

        effective_type = meta.get("type", "") #TODO: replace with get_effective_type function

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
        # Build name per RocketHD type-specific format
        if effective_type == "DISC":
            # Inject region from validated session data if available
            region = meta.get("region", "")
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

        else:
            # Fallback: use original name
            name = str(meta["name"])


        # Ensure name is always a string
        if not name:
            name = str(meta.get("name", "UNKNOWN"))

        # Remove any leftover "Dual-Audio" markers
        if "Dual-Audio" in name:
            name = name.replace("Dual-Audio", "").strip()

        # Cleanup whitespace
        name = self.WHITESPACE_PATTERN.sub(" ", name).strip()

        # Extract tag and append if valid
        tag = meta.get("tag", "").strip() #todo: replace with more robust _extract_clean_release_group function
        if tag:
            name = f"{name}{tag}"

        return {"name": name}

    async def get_additional_checks(self, meta: Meta) -> bool:
        should_continue = True

        # Uploading MIC, CAM, TS, LD, as well as upscale releases, is prohibited.
        raw_uuid = meta.get("uuid", "")
        # Split on delimiters (dot, hyphen, underscore) or whitespace so tags like "LD" only match as separate tokens
        dir_up = [tok for tok in re.split(r'[\.\s_-]+', str(raw_uuid).upper()) if tok]
        print(dir_up)
        if any(x in dir_up for x in ["MIC", "CAM", "TS", "TELESYNC", "LD", "LINE", "UPSCALE" ]):
            console.print(f"[bold red]Uploading MIC, CAM, TS, LD, as well as upscale releases, is prohibited, skipping {self.tracker} upload.")
            if not cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                return False

        # Uploading SD content is not allowed. Exception: No HD version exists. Check release databases beforehand to ensure an HD version doesn't exist
        if meta.get("resolution") in ["384p", "480p", "480i", "540p","576p", "576i"]:
            console.print(f"[bold red]Uploading SD releases is not allowed on {self.tracker}, unless no HD version exists.")
            console.print("[bold red]Please check release databases beforehand to be sure.")
            if not cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                return False

        # Uploads must contain a German audio track. Exception: The release was requested in its original language.
        if not self._has_german_audio(meta) and not meta.get("requested_release", False):
            console.print("[bold red]Uploads must contain a German audio track, unless the release was requested in its original language.")
            if not cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                return False

        # check for samples, proofs, and images in the upload directory
        filelist = meta.get("filelist", [])
        if any(
            str(file).lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff", ".pdf"))
            or "sample" in str(file).lower()
            or "proof" in str(file).lower()
            for file in filelist
        ):
            console.print("[bold red]Uploads containing samples, proofs, and images are prohibited.[/bold red]")
            if not cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                return False
        return should_continue
