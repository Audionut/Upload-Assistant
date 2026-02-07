# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any, Optional, cast

import cli_ui

from src.console import console
from src.languages import languages_manager
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D

Meta = dict[str, Any]
Config = dict[str, Any]


class TTR(UNIT3D):

    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='TTR')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'TTR'
        self.base_url = 'https://torrenteros.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        self.ttr_name = ''  # Initialize instance variable

    async def get_name(self, meta: Meta) -> dict[str, str]:
        name = self.ttr_name or self.build_name(meta)

        return {'name': name}

    def build_name(self, meta: Meta) -> str:
        name = str(meta.get('name_notag', ''))

        def ask_spanish_type(kind: str) -> str:
            console.print(f"{self.tracker}: [green]Found Spanish {kind} track.[/green] [yellow]Is it Castellano or Latino?[/yellow]")
            console.print("1 = Castellano")
            console.print("2 = Latino")
            console.print("3 = Castellano Latino")
            return str(cli_ui.ask_string("Enter choice (1-3): "))

        def get_spanish_type(lang_code: str) -> Optional[str]:
            if not lang_code:
                return None
            lang_code = lang_code.lower()
            if lang_code in ('es-es', 'es', 'spa'):
                return 'Castellano'
            if lang_code.startswith('es-'):
                return 'Latino'
            return None

        if meta.get('is_disc') == 'BDMV':
            spanish_audio = "Spanish" in meta.get('audio_languages', [])
            spanish_subtitle = "Spanish" in meta.get('subtitle_languages', [])
            unattended = meta.get('unattended', False)
            confirm = meta.get('unattended_confirm', False)

            if spanish_audio:
                if unattended or confirm:
                    suffix = 'Castellano'
                else:
                    user_choice = ask_spanish_type("audio")
                    suffix = {'1': 'Castellano', '2': 'Latino', '3': 'Castellano Latino'}.get(user_choice, 'Castellano')
                name += f" {suffix}"

            elif spanish_subtitle:
                if unattended or confirm:
                    suffix = 'Castellano Subs'
                else:
                    user_choice = ask_spanish_type("subtitle")
                    suffix = {'1': 'Castellano Subs', '2': 'Latino Subs', '3': 'Castellano Latino Subs'}.get(user_choice, 'Castellano Subs')

                name += f" {suffix}"

        else:
            tracks = cast(
                list[dict[str, Any]],
                cast(dict[str, Any], meta.get('mediainfo', {})).get('media', {}).get('track', []),
            )
            spanish_audio_type = None
            spanish_subs_type = None

            for track in tracks:
                if track.get('@type') == 'Audio':
                    lang = track.get('Language', '')
                    if isinstance(lang, dict):
                        lang = ''
                    spanish_audio_type = get_spanish_type(str(lang).strip())
                    if spanish_audio_type:
                        break

            for track in tracks:
                if track.get('@type') == 'Text':
                    lang = track.get('Language', '')
                    if isinstance(lang, dict):
                        lang = ''
                    spanish_subs_type = get_spanish_type(str(lang).strip())
                    if spanish_subs_type:
                        break

            if spanish_audio_type:
                name += f" {spanish_audio_type}"
            elif spanish_subs_type:
                name += f" {spanish_subs_type} Subs"

        tag = str(meta.get('tag', ""))
        if tag:
            name += tag

        self.ttr_name = name

        return name

    async def get_additional_data(self, meta: Meta) -> dict[str, Any]:
        data: dict[str, Any] = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_additional_checks(self, meta: Meta) -> bool:
        if not meta.get("language_checked", False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)

        if "Spanish" not in meta.get('audio_languages', []):
            if "Spanish" not in meta.get('subtitle_languages', []):
                console.print(
                    "[bold red]TTR requires at least one Spanish audio or subtitle track."
                )
                return False
            else:
                if meta.get('unattended'):
                    if not meta.get('unattended_confirm', False):
                        return False
                else:
                    console.print(f"{self.tracker}: [yellow]No Spanish audio track found, but Spanish subtitles are present.[/yellow]")
                    if not cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                        return False

        return True
