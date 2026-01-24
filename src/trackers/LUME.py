# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
from typing import Any

import cli_ui

from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]


class LUME(UNIT3D):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config, tracker_name="LUME")
        self.config = config
        self.common = COMMON(config)
        self.tracker = "LUME"
        self.base_url = "https://luminarr.me"
        self.id_url = f"{self.base_url}/api/torrents/"
        self.upload_url = f"{self.base_url}/api/torrents/upload"
        self.requests_url = f"{self.base_url}/api/requests/filter"
        self.search_url = f"{self.base_url}/api/torrents/filter"
        self.torrent_url = f"{self.base_url}/torrents/"
        self.banned_groups: list[str] = []

    async def get_additional_data(self, meta: Meta) -> dict[str, Any]:
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_additional_checks(self, meta: Meta) -> bool:
        should_continue = True

        if meta['is_disc'] not in ["BDMV", "DVD"] and not await self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=["english"], check_audio=True, check_subtitle=True, original_language=True
        ):
            return False

        if meta['is_disc'] not in ["BDMV", "DVD"] and meta['resolution'] not in ['8640p', '4320p', '2160p', '1440p', '1080p', '1080i', '720p']:
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print(f"[bold red]{self.tracker} only allows SD releases when the content does not have a higher resolution release.[/bold red]")
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    return False
            else:
                return False

        if not meta['valid_mi_settings']:
            console.print(f"[bold red]No encoding settings in mediainfo, skipping {self.tracker} upload.[/bold red]")
            return False

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print(f"[bold red]Pornography is not allowed at {self.tracker}.[/bold red]")
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    return False
            else:
                return False

        return should_continue
