# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import re
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class SAM(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name="SAM")
        self.config = config
        self.common = COMMON(config)
        self.tracker = "SAM"
        self.source_flag = "SAMARITANO"
        self.base_url = "https://samaritano.cc"
        self.id_url = f"{self.base_url}/api/torrents/"
        self.upload_url = f"{self.base_url}/api/torrents/upload"
        self.search_url = f"{self.base_url}/api/torrents/filter"
        self.torrent_url = f"{self.base_url}/torrents/"
        self.requests_url = f"{self.base_url}/api/requests/filter"
        self.banned_groups = []
        pass

    async def get_name(self, meta):
        name = (
            meta["name"]
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
                name = name.replace(year, "").replace(f"({year})", "").strip()

        # Remove the AKA title, unless it is Brazilian
        if meta.get("original_language") != "pt":
            name = name.replace(meta["aka"], "")

        # If it is Brazilian, use only the AKA title, deleting the foreign title
        if meta.get("original_language") == "pt" and meta.get("aka"):
            aka_clean = meta["aka"].replace("AKA", "").strip()
            title = meta.get("title")
            name = name.replace(meta["aka"], "").replace(title, aka_clean).strip()

        sam_name = name
        tag_lower = meta["tag"].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        audio_tag = ""
        if meta.get("audio_languages"):
            audio_languages = set(meta["audio_languages"])

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
                    sam_name = f"{parts[0]}{audio_tag}-{parts[1]}"
                else:
                    sam_name += audio_tag

        if meta["tag"] == "" or any(
            invalid_tag in tag_lower for invalid_tag in invalid_tags
        ):
            for invalid_tag in invalid_tags:
                sam_name = re.sub(f"-{invalid_tag}", "", sam_name, flags=re.IGNORECASE)
            sam_name = f"{sam_name}-NoGroup"

        return {"name": re.sub(r"\s{2,}", " ", sam_name)}

    async def get_additional_data(self, meta):
        data = {
            "mod_queue_opt_in": await self.get_flag(meta, "modq"),
        }

        return data

    async def get_additional_checks(self, meta):
        return await self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=["portuguese", "português"], check_audio=True, check_subtitle=True
        )
