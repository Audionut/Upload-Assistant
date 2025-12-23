# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import cli_ui
import re
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
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            '[Oj]', '3LTON', '4yEo', 'ADE', 'AFG', 'AniHLS', 'AnimeRG', 'AniURL',
            'AROMA', 'aXXo', 'CM8', 'CrEwSaDe', 'DeadFish', 'DNL', 'ELiTE',
            'eSc', 'FaNGDiNG0', 'FGT', 'Flights', 'FRDS', 'FUM', 'GalaxyRG', 'HAiKU',
            'HD2DVD', 'HDS', 'HDTime', 'Hi10', 'INFINITY', 'ION10', 'iPlanet', 'JIVE', 'KiNGDOM',
            'LAMA', 'Leffe', 'LOAD', 'mHD', 'NhaNc3', 'nHD', 'NOIVTC', 'nSD', 'PiRaTeS',
            'PRODJi', 'RAPiDCOWS', 'RARBG', 'RDN', 'REsuRRecTioN', 'RMTeam', 'SANTi',
            'SicFoI', 'SPASM', 'STUTTERSHIT', 'Telly', 'TM', 'UPiNSMOKE', 'WAF', 'xRed',
            'XS', 'YELLO', 'YIFY', 'YTS', 'ZKBL', 'ZmN', '4f8c4100292', 'Azkars', 'Sync0rdi'
        ]
        pass

    async def get_additional_checks(self, meta):
        should_continue = True

        if not any(genre in meta['combined_genres'] for genre in ['Animation', 'Family']):
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print('[bold red]Genre does not match Animation or Family for OTW.')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    return False
            else:
                return False

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy', 'hentai', 'adult animation', 'softcore']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print('[bold red]Adult animation not allowed at OTW.')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    return False
            else:
                return False

        if meta['type'] not in ['WEBDL'] and not meta['is_disc']:
            if meta.get('tag', "") in ['CMRG', 'EVO', 'TERMiNAL', 'ViSION']:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    console.print(f'[bold red]Group {meta["tag"]} is only allowed for raw type content at OTW[/bold red]')
                    if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                        pass
                    else:
                        return False
                else:
                    return False

        return should_continue

    async def get_type_id(self, meta, type=None, reverse=False, mapping_only=False):
        type = meta['type']
        if meta.get('is_disc') == 'BDMV':
            return {'type_id': '1'}
        elif meta.get('is_disc') and meta.get('is_disc') != 'BDMV':
            return {'type_id': '7'}
        if type == "DVDRIP":
            return {'type_id': '8'}
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }
        if mapping_only:
            return type_id
        elif reverse:
            return {v: k for k, v in type_id.items()}
        elif type is not None:
            return {'type_id': type_id.get(type, '0')}
        else:
            meta_type = meta.get('type', '')
            resolved_id = type_id.get(meta_type, '0')
            return {'type_id': resolved_id}

    async def get_name(self, meta):
        otw_name = meta['name']
        source = meta['source']
        resolution = meta['resolution']
        aka = meta.get('aka', '')
        type = meta['type']
        video_codec = meta.get('video_codec', '')
        if aka:
            otw_name = otw_name.replace(f"{aka} ", '')
        if meta['is_disc'] == "DVD" or (type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")):
            otw_name = otw_name.replace((meta['source']), f"{resolution} {meta['source']}", 1)
            otw_name = otw_name.replace((meta['audio']), f"{video_codec} {meta['audio']}", 1)
        if meta['category'] == "TV":
            years = []

            tmdb_year = meta.get('year')
            if tmdb_year and str(tmdb_year).isdigit():
                year = str(tmdb_year)
            else:
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

        return {'name': otw_name}

    async def get_additional_data(self, meta):
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data
