# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import cli_ui

from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class BLU(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='BLU')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'BLU'
        self.source_flag = 'BLU'
        self.base_url = 'https://blutopia.cc'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            '[Oj]', '3LTON', '4yEo', 'ADE', 'AFG', 'AniHLS', 'AnimeRG', 'AniURL', 'AOC', 'AROMA', 'aXXo', 'B3LLUM',
            'BHDStudio', 'Brrip', 'CHD', 'CM8', 'CrEwSaDe', 'd3g', 'DeadFish', 'DNL', 'DTLegacy', 'ELiTE',
            'eSc', 'EZTV', 'EZTV.RE', 'F13', 'FaNGDiNG0', 'FGT', 'Flights', 'FRDS', 'FUM', 'HAiKU', 'hallowed',
            'HD2DVD', 'HDS', 'HDTime', 'Hi10', 'ION10', 'iPlanet', 'JIVE', 'KiNGDOM', 'LAMA', 'Leffe', 'LEGi0N',
            'LOAD', 'MeGusta', 'mHD', 'mSD', 'NhaNc3', 'nHD', 'nikt0', 'NOIVTC', 'nSD', 'PiRaTeS', 'playBD',
            'PlaySD', 'playXD', 'PRODJi', 'RAPiDCOWS', 'RARBG', 'RetroPeeps', 'RDN', 'REsuRRecTioN', 'RMTeam', 'SANTi', 'SasukeducK',
            'SicFoI', 'SPASM', 'SPDVD', 'STUTTERSHIT', 'Telly', 'TheFarm', 'TM', 'TRiToN', 'UPiNSMOKE', 'URANiME', 'WAF',
            'WKS', 'x0r', 'xRed', 'XS', 'YIFY', 'ZKBL', 'ZmN', 'ZMNT',
        ]
        pass

    async def get_additional_checks(self, meta):
        should_continue = True
        if meta['type'] in ['ENCODE', 'REMUX']:
            if 'HDR' in meta.get('hdr', '') and 'DV' in meta.get('hdr', ''):
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    console.print('[bold red]Releases using a Dolby Vision layer from a different source have specific description requirements.[/bold red]')
                    console.print('[bold red]See rule 12.5. You must have a correct pre-formatted description if this release has a derived layer[/bold red]')
                    if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                        pass
                    else:
                        return False
                    if cli_ui.ask_yes_no("Is this a derived layer release?", default=False):
                        meta['tracker_status'][self.tracker]['other'] = True

        if meta['type'] not in ['WEBDL'] and not meta['is_disc']:
            if meta.get('tag', "") in ['CMRG', 'EVO', 'TERMiNAL', 'ViSION']:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    console.print(f'[bold red]Group {meta["tag"]} is only allowed for raw type content[/bold red]')
                    if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                        pass
                    else:
                        return False
                else:
                    return False

        if not meta['valid_mi_settings']:
            console.print(f"[bold red]No encoding settings in mediainfo, skipping {self.tracker} upload.[/bold red]")
            return False

        return should_continue

    async def get_name(self, meta):
        blu_name = meta['name']
        if meta['category'] == 'TV' and meta.get('episode_title', "") != "":
            blu_name = blu_name.replace(f"{meta['episode_title']} {meta['resolution']}", f"{meta['resolution']}", 1)
        imdb_name = meta.get('imdb_info', {}).get('title', "")
        imdb_year = str(meta.get('imdb_info', {}).get('year', ""))
        imdb_aka = meta.get('imdb_info', {}).get('aka', "")
        year = str(meta.get('year', ""))
        aka = meta.get('aka', "")
        webdv = meta.get('webdv', "")
        if imdb_name and imdb_name.strip():
            if aka:
                blu_name = blu_name.replace(f"{aka} ", "", 1)
            blu_name = blu_name.replace(f"{meta['title']}", imdb_name, 1)

            if imdb_aka and imdb_aka.strip() and imdb_aka != imdb_name and not meta.get('no_aka', False):
                blu_name = blu_name.replace(f"{imdb_name}", f"{imdb_name} AKA {imdb_aka}", 1)

        if not meta.get('category') == "TV" and imdb_year and imdb_year.strip() and year and year.strip() and imdb_year != year:
            blu_name = blu_name.replace(f"{year}", imdb_year, 1)

        if webdv:
            blu_name = blu_name.replace("HYBRID ", "", 1)

        if meta['tracker_status'][self.tracker].get('other', False):
            blu_name = blu_name.replace(f"{meta['resolution']}", f"{meta['resolution']} DVP5/DVP8", 1)

        return {'name': blu_name}

    async def get_additional_data(self, meta):
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_category_id(self, meta, category=None, reverse=False, mapping_only=False):
        edition = meta.get('edition', '')
        category_name = meta['category']
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'FANRES': '3'
        }

        is_fanres = False

        if category_name == 'MOVIE' and 'FANRES' in edition:
            is_fanres = True

        if meta['tracker_status'][self.tracker].get('other', False):
            is_fanres = True

        if is_fanres:
            return {'category_id': '3'}

        if mapping_only:
            return category_id
        elif reverse:
            return {v: k for k, v in category_id.items()}
        elif category is not None:
            return {'category_id': category_id.get(category, '0')}
        else:
            meta_category = meta.get('category', '')
            resolved_id = category_id.get(meta_category, '0')
            return {'category_id': resolved_id}

    async def get_type_id(self, meta, type=None, reverse=False, mapping_only=False):
        type_id = {
            'DISC': '1',
            'REMUX': '3',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '12'
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

    async def get_resolution_id(self, meta, mapping_only=False, reverse=False, resolution=None):
        resolution_id = {
            '8640p': '10',
            '4320p': '11',
            '2160p': '1',
            '1440p': '2',
            '1080p': '2',
            '1080i': '3',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }
        if mapping_only:
            return resolution_id
        elif reverse:
            return {v: k for k, v in resolution_id.items()}
        elif resolution is not None:
            return {'resolution_id': resolution_id.get(resolution, '10')}
        else:
            meta_resolution = meta.get('resolution', '')
            resolved_id = resolution_id.get(meta_resolution, '10')
            return {'resolution_id': resolved_id}
