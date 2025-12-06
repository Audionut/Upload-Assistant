# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D
import re


class CBR(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='CBR')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'CBR'
        self.source_flag = 'CapybaraBR'
        self.base_url = 'https://capybarabr.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            '3LTON', '4yEo', 'ADE', 'ASM', 'AFG', 'AROMA', 'AniHLS', 'AniURL', 'AnimeRG', 'BLUDV', 'CHD', 'CM8', 'Comando', 'CrEwSaDe', 'DNL', 'DeadFish',
            'DragsterPS', 'DRENAN', 'ELiTE', 'FGT', 'FRDS', 'FUM', 'FaNGDiNG0', 'Flights', 'HAiKU', 'HD2DVD', 'HDS', 'HDTime', 'Hi10', 'Hiro360', 'ION10', 'JIVE', 'KiNGDOM',
            'LEGi0N', 'LOAD', 'Lapumia', 'Leffe', 'MACCAULAY', 'MeGusta', 'NOIVTC', 'NhaNc3', 'OFT', 'Oj', 'PRODJi', 'PiRaTeS', 'PlaySD', 'RAPiDCOWS',
            'RARBG', 'RDN', 'REsuRRecTioN', 'RMTeam', 'RetroPeeps', 'S74Ll10n', 'SANTi', 'SILVEIRATeam', 'SPASM', 'SPDVD', 'STUTTERSHIT', 'SicFoI', 'TGx', 'TM',
            'TRiToN', 'Telly', 'UPiNSMOKE', 'URANiME', 'WAF', 'XS', 'YIFY', 'ZKBL', 'ZMNT', 'ZmN', 'aXXo', 'd3g', 'eSc', 'iPlanet', 'mHD', 'mSD', 'nHD',
            'nSD', 'nikt0', 'playXD', 'x0r', 'xRed'
        ]
        pass

    async def get_category_id(self, meta):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'ANIMES': '4'
        }.get(meta['category'], '0')
        if meta['anime'] is True and category_id == '2':
            category_id = '4'
        return {'category_id': category_id}

    async def get_type_id(self, meta):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'ENCODE': '3',
            'DVDRIP': '3',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6'
        }.get(meta['type'], '0')
        return {'type_id': type_id}

    async def get_resolution_id(self, meta):
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9',
            'Other': '10',
        }.get(meta['resolution'], '10')
        return {'resolution_id': resolution_id}

    async def get_name(self, meta):
        name = meta['name'].replace('DD+ ', 'DDP').replace('DD ', 'DD').replace('AAC ', 'AAC').replace('FLAC ', 'FLAC')

        # If it is a Series or Anime, remove the year from the title.
        if meta.get('category') in ['TV', 'ANIMES']:
            year = str(meta.get('year', ''))
            if year and year in name:
                name = name.replace(year, '').replace(f"({year})", '').strip()
                name = re.sub(r'\s{2,}', ' ', name)

        # Remove the AKA title, unless it is Brazilian
        if meta.get('original_language') != 'pt':
            name = name.replace(meta["aka"], '')

        # If it is Brazilian, use only the AKA title, deleting the foreign title
        if meta.get('original_language') == 'pt' and meta.get('aka'):
            aka_clean = meta['aka'].replace('AKA', '').strip()
            title = meta.get('title')
            name = name.replace(meta["aka"], '').replace(title, aka_clean).strip()

        cbr_name = name
        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        if meta.get('no_dual', False):
            if meta.get('dual_audio', False):
                cbr_name = cbr_name.replace("Dual-Audio ", '')
        else:
            if meta.get('audio_languages') and not meta.get('is_disc') == "BDMV":
                audio_languages = set(meta['audio_languages'])
                if len(audio_languages) >= 3:
                    audio_tag = ' MULTI'
                elif len(audio_languages) == 2:
                    audio_tag = ' DUAL'
                else:
                    audio_tag = ''

                if audio_tag:
                    if meta.get('dual_audio', False):
                        cbr_name = cbr_name.replace("Dual-Audio ", '')
                    if '-' in cbr_name:
                        parts = cbr_name.rsplit('-', 1)
                        cbr_name = f"{parts[0]}{audio_tag}-{parts[1]}"
                    else:
                        cbr_name += audio_tag

        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                cbr_name = re.sub(f"-{invalid_tag}", "", cbr_name, flags=re.IGNORECASE)
            cbr_name = f"{cbr_name}-NoGroup"

        return {'name': cbr_name}

    async def get_additional_data(self, meta):
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_additional_checks(self, meta):
        return await self.common.check_language_requirements(
            meta, self.tracker, languages_to_check=["portuguese", "português"], check_audio=True, check_subtitle=True
        )
