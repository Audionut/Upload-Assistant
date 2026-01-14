# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import re
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D
from typing import Any


class CBR(UNIT3D):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config, tracker_name='CBR')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'CBR'
        self.base_url = 'https://capybarabr.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            "4K4U", "afm72", "Alcaide_Kira", "AROMA", "ASM", "Bandi", "BiTOR", "BLUDV", "Bluespots",
            "BOLS", "CaNNIBal", "Comando", "d3g", "DepraveD", "EMBER", "FGT", "FreetheFish", "Garshasp",
            "Ghost", "Grym", "HDS", "Hi10", "HiQVE", "Hiro360", "ImE", "ION10", "iVy", "Judas", "LAMA",
            "Langbard", "Lapumia", "LION", "MeGusta", "MONOLITH", "MRCS", "NaNi", "Natty", "nikt0",
            "OEPlus", "OFT", "OsC", "Panda", "PANDEMONiUM", "PHOCiS", "PiRaTeS", "PYC", "QxR", "r00t",
            "Ralphy", "RARBG", "RetroPeeps", "RZeroX", "S74Ll10n", "SAMPA", "Sicario", "SiCFoI", "Silence",
            "SkipTT", "SM737", "SPDVD", "STUTTERSHIT", "SWTYBLZ", "t3nzin", "TAoE", "TEKNO3D", "Telly", "TGx",
            "Tigole", "TSP", "TSPxL", "TWA", "UnKn0wn", "VXT", "Vyndros", "W32", "Will1869", "x0r", "YIFY", "YTS.MX", "YTS"
        ]

    async def get_category_id(
        self, meta: dict[str, Any], category: str = "", reverse: bool = False, mapping_only: bool = False
    ) -> dict[str, str]:
        category_id: dict[str, str] = {
            "MOVIE": "1",
            "TV": "2",
            "ANIMES": "4"
        }

        if mapping_only:
            return category_id
        elif reverse:
            return {v: k for k, v in category_id.items()}

        resolved_category = category if category else meta.get("category", "")
        if meta.get("anime", False) is True and resolved_category == "TV":
            resolved_category = "ANIMES"

        if resolved_category:
            return {"category_id": category_id.get(resolved_category, "0")}

        return {"category_id": "0"}

    async def get_type_id(
        self, meta: dict[str, Any], type: str = "", reverse: bool = False, mapping_only: bool = False
    ) -> dict[str, str]:
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'ENCODE': '3',
            'DVDRIP': '3',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6'
        }

        if mapping_only:
            return type_id
        elif reverse:
            return {v: k for k, v in type_id.items()}
        elif type:
            return {"type_id": type_id.get(type, "0")}
        else:
            meta_type = meta.get("type", "")
            resolved_id = type_id.get(meta_type, "0")
            return {"type_id": resolved_id}

    async def get_resolution_id(
        self, meta: dict[str, Any], resolution: str = "", reverse: bool = False, mapping_only: bool = False
    ) -> dict[str, str]:
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9',
            'Other': '10',
        }

        if mapping_only:
            return resolution_id
        elif reverse:
            return {v: k for k, v in resolution_id.items()}
        elif resolution:
            return {"resolution_id": resolution_id.get(resolution, "10")}
        else:
            meta_resolution = meta.get("resolution", "")
            resolved_id = resolution_id.get(meta_resolution, "10")
            return {"resolution_id": resolved_id}

    async def get_name(self, meta: dict[str, Any]) -> dict[str, str]:
        name = (
            str(meta["name"])
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
            name = name.replace(meta.get("aka", ""), "")

        # If it is Brazilian, use only the AKA title, deleting the foreign title
        if meta.get("original_language") == "pt" and meta.get("aka"):
            aka_clean = str(meta.get("aka", "")).replace("AKA", "").strip()
            title = meta.get("title", "")
            name = name.replace(meta.get("aka", ""), "").replace(title, aka_clean).strip()

        cbr_name = name
        tag_lower = str(meta.get("tag", "")).lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        if not meta.get('is_disc'):
            audio_tag = ""
            if meta.get("audio_languages"):
                audio_languages: set[str] = set(meta["audio_languages"])

                if any(lang.lower() == "portuguese" or lang == "português" for lang in audio_languages):
                    if len(audio_languages) >= 3:
                        audio_tag = " MULTI"
                    elif len(audio_languages) == 2:
                        audio_tag = " DUAL"
                    else:
                        audio_tag = ""

                if audio_tag:
                    if "-" in cbr_name:
                        parts = cbr_name.rsplit("-", 1)

                        custom_tag = dict(dict(self.config.get("TRACKERS", {})).get(self.tracker, {})).get(
                            "tag_for_custom_release", ""
                        )
                        if custom_tag and custom_tag in name:
                            match = re.search(r"-([^.-]+)\.(?:DUAL|MULTI)", meta["uuid"])
                            if match and match.group(1) != meta["tag"]:
                                original_group_tag = match.group(1)
                                cbr_name = f"{parts[0]}-{original_group_tag}{audio_tag}-{parts[1]}"
                            else:
                                cbr_name = f"{parts[0]}{audio_tag}-{parts[1]}"
                        else:
                            cbr_name = f"{parts[0]}{audio_tag}-{parts[1]}"
                    else:
                        cbr_name += audio_tag

        if meta["tag"] == "" or any(
            invalid_tag in tag_lower for invalid_tag in invalid_tags
        ):
            for invalid_tag in invalid_tags:
                cbr_name = re.sub(f"-{invalid_tag}", "", cbr_name, flags=re.IGNORECASE)
            cbr_name = f"{cbr_name}-NoGroup"

        return {"name": re.sub(r"\s{2,}", " ", cbr_name)}

    async def get_additional_data(self, meta: dict[str, Any]) -> dict[str, str]:
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_additional_checks(self, meta: dict[str, Any]) -> bool:
        return await self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=["portuguese", "português"], check_audio=True, check_subtitle=True
        )
