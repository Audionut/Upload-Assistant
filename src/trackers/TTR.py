# -*- coding: utf-8 -*-
from src.console import console
from src.languages import process_desc_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class TTR(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='TTR')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'TTR'
        self.source_flag = 'TTR'
        self.base_url = 'https://torrenteros.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_name(self, meta):
        try:
            name = TTR.ttr_name
        except AttributeError:
            name = await self.build_name(meta)

        return {'name': name}

    async def build_name(self, meta):
        name = meta['name_notag']

        async def ask_spanish_type(kind):
            console.print(f"{self.tracker}: [green]Found Spanish {kind} track.[/green] [yellow]Is it Castellano or Latino?[/yellow]")
            console.print("1 = Castellano")
            console.print("2 = Latino")
            console.print("3 = Castellano Latino")
            return await self.common.async_input()

        def get_spanish_type(lang_code):
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
                    user_choice = await ask_spanish_type("audio")
                    suffix = {'1': 'Castellano', '2': 'Latino', '3': 'Castellano Latino'}.get(user_choice, 'Castellano')
                name += f" {suffix}"

            elif spanish_subtitle:
                if unattended or confirm:
                    suffix = 'Castellano'
                else:
                    user_choice = await ask_spanish_type("subtitle")
                    suffix = {'1': 'Castellano Subs', '2': 'Latino Subs', '3': 'Castellano Latino Subs'}.get(user_choice, 'Castellano')

                name += f" {suffix}"

        else:
            tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
            spanish_audio_type = None
            spanish_subs_type = None

            for track in tracks:
                if track.get('@type') == 'Audio':
                    spanish_audio_type = get_spanish_type(track.get('Language', '').strip())
                    if spanish_audio_type:
                        break

            for track in tracks:
                if track.get('@type') == 'Text':
                    spanish_subs_type = get_spanish_type(track.get('Language', '').strip())
                    if spanish_subs_type:
                        break

            if spanish_audio_type:
                name += f" {spanish_audio_type}"
            elif spanish_subs_type:
                name += f" {spanish_subs_type} Subs"

        tag = meta.get('tag', "")
        if tag:
            name += tag

        TTR.ttr_name = name

        return name

    async def get_additional_data(self, meta):
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_additional_checks(self, meta):
        if not meta.get("language_checked", False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        if "Spanish" not in meta.get('audio_languages', []):
            if "Spanish" not in meta.get('subtitle_languages', []):
                console.print(
                    "[bold red]TTR requires at least one Spanish audio or subtitle track."
                )
                return False
            else:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    console.print(f"{self.tracker}: [yellow]No Spanish audio track found, but Spanish subtitles are present.[/yellow]")
                    console.print(f"{self.tracker}: [yellow]Do you want to upload anyway? y/N[/yellow]")
                    user_choice = await self.common.async_input()
                    if user_choice.lower() != 'y':
                        return False
                else:
                    return False

        return True
