# -*- coding: utf-8 -*-
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
        self.banned_groups = []
        pass

    async def get_category_id(self, meta):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'ANIME': '5',
            'TELENOVELAS': '8',
            'Asiáticas & Turcas': '20',
        }.get(meta['category'], '0')
        # if is anime
        if meta['anime'] is True and category_id == '2':
            category_id = '5'
        # elif is telenovela
        elif category_id == '2' and ("telenovela" in meta['keywords'] or "telenovela" in meta['overview']):
            category_id = '8'
        # if is  TURCAS o Asiáticas
        elif meta["original_language"] in ['ja', 'ko', 'tr'] and category_id == '2' and 'Drama' in meta['genres']:
            category_id = '20'
        return {'category_id': category_id}

    async def get_name(self, meta):
        lt_name = meta['name'].replace('Dual-Audio', '').replace('Dubbed', '').replace(meta['aka'], '').replace('  ', ' ').strip()
        if meta['type'] != 'DISC':  # DISC don't have mediainfo
            # Check if is HYBRID (Copied from BLU.py)
            if 'hybrid' in meta.get('uuid').lower():
                if "repack" in meta.get('uuid').lower():
                    lt_name = lt_name.replace('REPACK', 'Hybrid REPACK')
                else:
                    lt_name = lt_name.replace(meta['resolution'], f"Hybrid {meta['resolution']}")
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

        return {'name': lt_name}

    async def get_distributor_ids(self, meta):
        return {}

    async def get_region_id(self, meta):
        return {}
