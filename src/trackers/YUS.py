# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import cli_ui
import re
from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class YUS(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='YUS')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'YUS'
        self.base_url = 'https://yu-scene.net'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            'ADDICTION', 'B3LLUM', 'BANDOLEROS', 'BigEasy', 'CINEMAXIS', 'D3US', 'd3g', 'DUMMESCHWEDEN', 'FGT', 'GRANiTEN',
            'KiNGDOM', 'Lama', 'MeGusta', 'MezRips', 'mHD', 'mRS', 'msd', 'NeXus', 'NhaNc3', 'nHD',
            'NorTekst', 'NORViNE', 'PANDEMONiUM', 'PiTBULL', 'RAPiDCOWS', 'RARBG', 'Radarr', 'RCDiVX', 'RDN', 'ROCKETRACCOON',
            'SANTi', 'SHOWTiME', 'SOOSi', 'SUXWIC', 'TOXVIO', 'TWA', 'VXT', 'Will1869', 'x0r', 'XS',
            'YIFY', 'YOLAND', 'YTS', 'ZKBL', 'ZmN', 'ZMNT']
        pass

    async def get_additional_checks(self, meta):
        should_continue = True

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if (not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False))):
                console.print('[bold red]Porn/xxx is not allowed at YUS.')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    return False
            else:
                return False

        return should_continue

    async def get_type_id(self, meta, type=None, reverse=False, mapping_only=False):
        type_id = {
            'DISC': '17',
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
