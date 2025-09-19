# -*- coding: utf-8 -*-
import cli_ui
from src.trackers.COMMON import COMMON
from src.console import console
from src.trackers.UNIT3D import UNIT3D


class OTW(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='OTW')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'OTW'
        self.source_flag = 'OTW'
        self.base_url = 'https://oldtoons.world'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            '[Oj]', '3LTON', '4yEo', 'ADE', 'AFG', 'AniHLS', 'AnimeRG', 'AniURL',
            'AROMA', 'aXXo', 'CM8', 'CrEwSaDe', 'd3g', 'DeadFish', 'DNL', 'ELiTE',
            'eSc', 'FaNGDiNG0', 'FGT', 'Flights', 'FRDS', 'FUM', 'GalaxyRG', 'HAiKU',
            'HD2DVD', 'HDS', 'HDTime', 'Hi10', 'ION10', 'iPlanet', 'JIVE', 'KiNGDOM',
            'Lama', 'Leffe', 'LOAD', 'mHD', 'NhaNc3', 'nHD', 'NOIVTC', 'nSD', 'PiRaTeS',
            'PRODJi', 'RAPiDCOWS', 'RARBG', 'RDN', 'REsuRRecTioN', 'RMTeam', 'SANTi',
            'SicFoI', 'SPASM', 'STUTTERSHIT', 'Telly', 'TM', 'UPiNSMOKE', 'WAF', 'xRed',
            'XS', 'YELLO', 'YIFY', 'YTS', 'ZKBL', 'ZmN', '4f8c4100292', 'Azkars', 'Sync0rdi',
            ['EVO', 'Raw Content Only'], ['TERMiNAL', 'Raw Content Only'],
            ['ViSION', 'Note the capitalization and characters used'], ['CMRG', 'Raw Content Only']
        ]
        pass

    async def get_additional_checks(self, meta):
        should_continue = True

        if not any(genre in meta['genres'] for genre in ['Animation', 'Family']):
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print('[bold red]Genre does not match Animation or Family for OTW.')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    should_continue = False
            else:
                should_continue = False
        disallowed_keywords = {'XXX', 'Erotic', 'Porn', 'Hentai', 'Adult Animation', 'Orgy', 'softcore'}
        if any(keyword.lower() in disallowed_keywords for keyword in map(str.lower, meta['keywords'])):
            if not meta['unattended']:
                console.print('[bold red]Adult animation not allowed at OTW.')
            should_continue = False
        if meta['sd'] and 'BluRay' in meta['source']:
            if not meta['unattended']:
                console.print("[bold red]SD content from HD source not allowed")
            should_continue = False

        return should_continue

    async def get_type_id(self, meta):
        type = meta['type']
        if meta.get('is_disc') == 'BDMV':
            return {'type_id': '1'}
        elif meta.get('is_disc') and meta.get('is_disc') != 'BDMV':
            return {'type_id': '7'}
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(type, '0')
        return {'type_id': type_id}

    async def get_name(self, meta):
        otw_name = meta['name']
        source = meta['source']
        resolution = meta['resolution']
        aka = meta.get('aka', '')
        type = meta['type']
        if aka:
            otw_name = otw_name.replace(meta["aka"], '')
        if meta['is_disc'] == "DVD":
            otw_name = otw_name.replace(source, f"{source} {resolution}")
        if meta['is_disc'] == "DVD" or type == "REMUX":
            otw_name = otw_name.replace(meta['audio'], f"{meta.get('video_codec', '')} {meta['audio']}", 1)
        elif meta['is_disc'] == "DVD" or (type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")):
            otw_name = otw_name.replace((meta['source']), f"{resolution} {meta['source']}", 1)
        if meta['category'] == "TV":
            years = []

            tmdb_year = meta.get('year')
            if tmdb_year and str(tmdb_year).isdigit():
                years.append(int(tmdb_year))

            imdb_year = meta.get('imdb_info', {}).get('year')
            if imdb_year and str(imdb_year).isdigit():
                years.append(int(imdb_year))

            series_year = meta.get('tvdb_episode_data', {}).get('series_year')
            if series_year and str(series_year).isdigit():
                years.append(int(series_year))
            # Use the oldest year if any found, else empty string
            year = str(min(years)) if years else ""
            if not meta.get('no_year', False) and not meta.get('search_year', ''):
                otw_name = otw_name.replace(meta['title'], f"{meta['title']} {year}", 1)

        return {'name': meta['name']}

    async def get_additional_data(self, meta):
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data
