# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any, cast

from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class SAM(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name="SAM")
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = "SAM"
        self.base_url = "https://samaritano.cc"
        self.id_url = f"{self.base_url}/api/torrents/"
        self.upload_url = f"{self.base_url}/api/torrents/upload"
        self.search_url = f"{self.base_url}/api/torrents/filter"
        self.torrent_url = f"{self.base_url}/torrents/"
        self.requests_url = f"{self.base_url}/api/requests/filter"
        self.banned_groups = []

    def get_name(self, meta: Meta) -> dict[str, str]:
        name = (
            str(meta.get("name", ""))
            .replace("DD+ ", "DDP")
            .replace("DD ", "DD")
            .replace("AAC ", "AAC")
            .replace("FLAC ", "FLAC")
            .replace("Dubbed", "")
            .replace("Dual-Audio", "")
        )

        # If it is a Series or Anime, remove the year from the title.
        if meta.get("category") in ["TV", "ANIMES"]:
            year = str(meta.get("year", ""))
            if year and year in name:
                name = name.replace(f"({year})", "").replace(year, "").strip()

        # Remove the AKA title, unless it is Brazilian
        if meta.get("original_language") != "pt":
            name = name.replace(str(meta.get("aka", "")), "")

        # If it is Brazilian, use only the AKA title, deleting the foreign title
        if meta.get("original_language") == "pt" and meta.get("aka"):
            aka_value = str(meta.get("aka", ""))
            aka_clean = aka_value.replace("AKA", "").strip()
            title = str(meta.get("title", ""))
            name = name.replace(aka_value, "").replace(title, aka_clean).strip()

        sam_name = name
        tag_value = str(meta.get("tag", ""))
        tag_lower = tag_value.lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        if not meta.get('is_disc'):
            audio_tag = ""
            if meta.get("audio_languages"):
                audio_languages_value = meta.get("audio_languages", [])
                audio_languages_list = [str(lang) for lang in cast(list[Any], audio_languages_value)] if isinstance(audio_languages_value, list) else []
                audio_languages = set(audio_languages_list)

                if "Portuguese" in audio_languages:
                    if len(audio_languages) >= 3:
                        audio_tag = " MULTI"
                    elif len(audio_languages) == 2:
                        audio_tag = " DUAL"
                    else:
                        audio_tag = ""

                if audio_tag:
                    if "-" in sam_name:
                        parts = sam_name.rsplit("-", 1)

                        custom_tag = str(self.config.get("TRACKERS", {}).get(self.tracker, {}).get("tag_for_custom_release", ""))
                        if custom_tag and custom_tag in name:
                            match = re.search(r"-([^.-]+)\.(?:DUAL|MULTI)", meta["uuid"])
                            if match and match.group(1) != tag_value:
                                original_group_tag = match.group(1)
                                sam_name = f"{parts[0]}-{original_group_tag}{audio_tag}-{parts[1]}"
                            else:
                                sam_name = f"{parts[0]}{audio_tag}-{parts[1]}"
                        else:
                            sam_name = f"{parts[0]}{audio_tag}-{parts[1]}"
                    else:
                        sam_name += audio_tag

        if tag_value == "" or any(
            invalid_tag in tag_lower for invalid_tag in invalid_tags
        ):
            for invalid_tag in invalid_tags:
                sam_name = re.sub(f"-{invalid_tag}", "", sam_name, flags=re.IGNORECASE)
            sam_name = f"{sam_name}-NoGroup"

        return {"name": re.sub(r"\s{2,}", " ", sam_name)}

    def get_additional_data(self, meta: Meta) -> dict[str, Any]:
        data: dict[str, Any] = {
            "mod_queue_opt_in": self.get_flag(meta, "modq"),
        }

        return data

    def get_additional_checks(self, meta: Meta) -> bool:
        return self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=["portuguese", "português"], check_audio=True, check_subtitle=True
        )
