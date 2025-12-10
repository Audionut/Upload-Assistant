# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import re
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class LT(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='LT')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'LT'
        self.source_flag = 'Lat-Team "Poder Latino"'
        self.base_url = 'https://lat-team.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = ["EVO"]
        pass

    async def get_category_id(self, meta):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(meta['category'], '0')

        keywords = meta.get('keywords', '').lower()
        overview = meta.get('overview', '').lower()
        genres = meta.get('genres', '').lower()
        soap_keywords = ['telenovela', 'novela', 'soap', 'culebrón', 'culebron']
        origin_countries = meta.get('origin_country', [])

        if meta['category'] == 'TV':
            # Anime
            if meta.get('anime', False):
                category_id = '5'
            # Telenovela / Soap
            elif any(kw in keywords for kw in soap_keywords) or any(kw in overview for kw in soap_keywords):
                category_id = '8'
            # Turkish & Asian
            elif 'drama' in genres and any(c in [
                'AE', 'AF', 'AM', 'AZ', 'BD', 'BH', 'BN', 'BT', 'CN', 'CY', 'GE', 'HK', 'ID', 'IL', 'IN',
                'IQ', 'IR', 'JO', 'JP', 'KG', 'KH', 'KP', 'KR', 'KW', 'KZ', 'LA', 'LB', 'LK', 'MM', 'MN',
                'MO', 'MV', 'MY', 'NP', 'OM', 'PH', 'PK', 'PS', 'QA', 'SA', 'SG', 'SY', 'TH', 'TJ', 'TL',
                'TM', 'TR', 'TW', 'UZ', 'VN', 'YE'
            ] for c in origin_countries):
                category_id = '20'

        return {'category_id': category_id}

    async def get_name(self, meta):
        lt_name = (
            meta['name']
            .replace('Dual-Audio', '')
            .replace('Dubbed', '')
            .replace(meta['aka'], '')
        )

        if meta['type'] != 'DISC':  # DISC don't have mediainfo
            # Check if original language is "es" if true replace title for AKA if available
            if meta.get('original_language') == 'es' and meta.get('aka') != "":
                lt_name = lt_name.replace(meta.get('title'), meta.get('aka').replace('AKA', '')).strip()
            # Check if audio Spanish exists
            audios = [
                audio for audio in meta['mediainfo']['media']['track'][2:]
                if audio.get('@type') == 'Audio'
                and isinstance(audio.get('Language'), str)
                and audio.get('Language').lower() in {'es-419', 'es', 'es-mx', 'es-ar', 'es-cl', 'es-ve', 'es-bo', 'es-co',
                                                      'es-cr', 'es-do', 'es-ec', 'es-sv', 'es-gt', 'es-hn', 'es-ni', 'es-pa',
                                                      'es-py', 'es-pe', 'es-pr', 'es-uy'}
                and "commentary" not in str(audio.get('Title', '')).lower()
            ]
            if len(audios) > 0:  # If there is at least 1 audio spanish
                lt_name = lt_name
            # if not audio Spanish exists, add "[SUBS]"
            elif not meta.get('tag'):
                lt_name = lt_name + " [SUBS]"
            else:
                lt_name = lt_name.replace(meta['tag'], f" [SUBS]{meta['tag']}")

        return {"name": re.sub(r"\s{2,}", " ", lt_name)}

    async def get_additional_checks(self, meta):
        spanish_languages = ["spanish", "spanish (latin america)"]
        if not await self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=spanish_languages, check_audio=True, check_subtitle=True
        ):
            return False
        return True

    async def get_additional_data(self, meta):
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_distributor_ids(self, meta):
        return {}

    async def get_region_id(self, meta):
        return {}
