# -*- coding: utf-8 -*-
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
            '[Oj]', '3LTON', '4yEo', 'ADE', 'AFG', 'AniHLS', 'AnimeRG', 'AniURL', 'AOC', 'AROMA',
            'aXXo', 'Brrip', 'CHD', 'CM8', 'CrEwSaDe', 'd3g', 'DeadFish', 'DNL', 'ELiTE', 'eSc',
            'FaNGDiNG0', 'FGT', 'Flights', 'FRDS', 'FUM', 'HAiKU', 'HD2DVD', 'HDS', 'HDTime',
            'Hi10', 'ION10', 'iPlanet', 'JIVE', 'KiNGDOM', 'Leffe', 'LEGi0N', 'LOAD', 'MeGusta',
            'mHD', 'mSD', 'NhaNc3', 'nHD', 'nikt0', 'NOIVTC', 'nSD', 'OFT', 'PiRaTeS', 'playBD',
            'PlaySD', 'playXD', 'PRODJi', 'RAPiDCOWS', 'RARBG', 'RDN', 'REsuRRecTioN', 'RetroPeeps',
            'RMTeam', 'SANTi', 'SicFoI', 'SPASM', 'SPDVD', 'STUTTERSHIT', 'Telly', 'TM', 'TRiToN',
            'UPiNSMOKE', 'URANiME', 'WAF', 'x0r', 'xRed', 'XS', 'YIFY', 'ZKBL', 'ZmN', 'ZMNT',
            ['CMRG', 'Raw Content Only'], ['EVO', 'Raw Content Only'], ['TERMiNAL', 'Raw Content Only'],
            ['ViSION', 'Note the capitalization and characters used'],
        ]
        pass

    async def get_name(self, meta):
        blu_name = meta['name']
        if meta['category'] == 'TV' and meta.get('episode_title', "") != "":
            blu_name = blu_name.replace(f"{meta['episode_title']} {meta['resolution']}", f"{meta['resolution']}", 1)
        imdb_name = meta.get('imdb_info', {}).get('title', "")
        imdb_year = str(meta.get('imdb_info', {}).get('year', ""))
        year = str(meta.get('year', ""))
        blu_name = blu_name.replace(f"{meta['title']}", imdb_name, 1)
        if not meta.get('category') == "TV":
            blu_name = blu_name.replace(f"{year}", imdb_year, 1)

        if all([x in meta['hdr'] for x in ['HDR', 'DV']]):
            if "hybrid" not in blu_name.lower():
                if "REPACK" in blu_name:
                    blu_name = blu_name.replace('REPACK', 'Hybrid REPACK')
                else:
                    blu_name = blu_name.replace(meta['resolution'], f"Hybrid {meta['resolution']}")

        return {'name': blu_name}

    async def get_description(self, meta):
        desc_header = ''
        if meta.get('webdv', False):
            desc_header = await self.derived_dv_layer(meta)
        await self.common.unit3d_edit_desc(meta, self.tracker, self.signature, comparison=True, desc_header=desc_header)
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        return {'description': desc}

    async def derived_dv_layer(self, meta):
        desc_header = ''
        # Exit if not DV + HDR
        if not all([x in meta['hdr'] for x in ['HDR', 'DV']]):
            return desc_header
        import cli_ui
        console.print("[bold yellow]Generating the required description addition for Derived DV Layers. Please respond appropriately.")
        ask_comp = True
        if meta['type'] == 'WEBDL':
            if cli_ui.ask_yes_no("Is the DV Layer sourced from the same service as the video?"):
                ask_comp = False
                desc_header = "[code]This release contains a derived Dolby Vision profile 8 layer. Comparisons not required as DV and HDR are from same provider.[/code]"

        if ask_comp:
            while desc_header == "":
                desc_input = cli_ui.ask_string("Please provide comparisons between HDR masters. (link or bbcode)", default="")
                desc_header = f"[code]This release contains a derived Dolby Vision profile 8 layer. Comparisons between HDR masters: {desc_input}[/code]"

        return desc_header

    async def get_additional_data(self, meta):
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_category_id(self, meta, mapping_only=False, reverse=False, category=None):
        edition = meta.get('edition', '')
        category_name = meta['category']
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'FANRES': '3'
        }
        if category_name == 'MOVIE' and 'FANRES' in edition:
            category_id = '3'
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
