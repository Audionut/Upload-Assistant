# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import langcodes
import re
from src.languages import has_english_language
from src.trackers.COMMON import COMMON
from src.console import console
from src.trackers.UNIT3D import UNIT3D


class LDU(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='LDU')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'LDU'
        self.source_flag = 'LDU'
        self.base_url = 'https://theldu.to'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_category_id(self, meta):
        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        sound_mixes = meta.get('imdb_info', {}).get('sound_mixes', [])

        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'Anime': '8',
            'FANRES': '12',
            'MUSIC': '3',
        }.get(meta['category'], '0')

        if 'hentai' in genres.lower():
            category_id = '10'
        elif any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if not await has_english_language(meta.get('subtitle_languages', [])):
                category_id = '45'
            else:
                category_id = '6'
        if meta['category'] == "MOVIE":
            if meta.get('3d') or "3D" in meta.get('edition', ''):
                category_id = '21'
            elif any(x in meta.get('edition', '').lower() for x in ["fanedit", "fanres"]):
                category_id = '12'
            elif meta.get('anime', False) or meta.get('mal_id', 0) != 0:
                category_id = '8'
            elif (any('silent film' in mix.lower() for mix in sound_mixes if isinstance(mix, str)) or meta.get('silent', False)):
                category_id = '18'
            elif "musical" in genres.lower():
                category_id = '25'
            elif any(x in genres.lower() for x in ['holiday', 'easter', 'christmas', 'halloween', 'thanksgiving']):
                category_id = '24'
            elif "documentary" in genres.lower():
                category_id = '17'
            elif any(x in genres.lower() for x in ['stand-up', 'standup']):
                category_id = '20'
            elif "short film" in genres.lower() or int(meta.get('imdb_info', {}).get('runtime', 0)) < 5:
                category_id = '19'
            elif not await has_english_language(meta.get('audio_languages', [])) and not await has_english_language(meta.get('subtitle_languages', [])):
                category_id = '22'
            elif "dubbed" in meta.get('audio', '').lower():
                category_id = '27'
            else:
                category_id = '1'
        elif meta['category'] == "TV":
            if meta.get('anime', False) or meta.get('mal_id', 0) != 0:
                category_id = '9'
            elif "documentary" in genres.lower():
                category_id = '40'
            elif not await has_english_language(meta.get('audio_languages', [])) and not await has_english_language(meta.get('subtitle_languages', [])):
                category_id = '29'
            elif meta.get('tv_pack', False):
                category_id = '2'
            elif "dubbed" in meta.get('audio', '').lower():
                category_id = '31'
            else:
                category_id = '41'

        return {'category_id': category_id}

    async def get_type_id(self, meta):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(meta.get('type'), '0')
        if any(x in meta.get('edition', '').lower() for x in ["fanedit", "fanres"]):
            type_id = '16'
        return {'type_id': type_id}

    async def get_name(self, meta):
        ldu_name = meta['name']
        cat_id = (await self.get_category_id(meta))['category_id']
        non_eng = False
        non_eng_audio = False
        iso_audio = None
        iso_subtitle = None
        if meta.get('original_language') != "en":
            non_eng = True
        if meta.get('audio_languages'):
            audio_language = meta['audio_languages'][0]
            if audio_language:
                try:
                    lang = langcodes.find(audio_language).to_alpha3()
                    iso_audio = lang.upper()
                    if not await has_english_language(audio_language):
                        non_eng_audio = True
                except Exception as e:
                    console.print(f"[bold red]Error extracting audio language: {e}[/bold red]")

        if meta.get('no_subs', False):
            iso_subtitle = "NoSubs"
        else:
            if meta.get('subtitle_languages'):
                subtitle_language = meta['subtitle_languages'][0]
                if subtitle_language:
                    try:
                        lang = langcodes.find(subtitle_language).to_alpha3()
                        iso_subtitle = f"Subs {lang.upper()}"
                    except Exception as e:
                        console.print(f"[bold red]Error extracting subtitle language: {e}[/bold red]")

        if cat_id == '18' and iso_subtitle:
            ldu_name = f"{ldu_name} [{iso_subtitle}]"

        elif non_eng or non_eng_audio:
            language_parts = []
            if iso_audio:
                language_parts.append(f"[{iso_audio}]")
            if iso_subtitle:
                language_parts.append(f"[{iso_subtitle}]")

            if language_parts:
                ldu_name = f"{ldu_name} {' '.join(language_parts)}"

        return {'name': ldu_name}
