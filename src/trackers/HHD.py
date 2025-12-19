# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class HHD(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='HHD')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'HHD'
        self.source_flag = 'HHD'
        self.base_url = 'https://homiehelpdesk.net'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            'aXXo', 'BONE', 'BRrip', 'CM8', 'CrEwSaDe', 'CTFOH', 'dAV1nci', 'd3g',
            'DNL', 'FaNGDiNG0', 'GalaxyTV', 'HD2DVD', 'HDTime', 'iHYTECH', 'ION10',
            'iPlanet', 'KiNGDOM', 'LAMA', 'MeGusta', 'mHD', 'mSD', 'NaNi', 'NhaNc3',
            'nHD', 'nikt0', 'nSD', 'OFT', 'PRODJi', 'RARBG', 'Rifftrax', 'SANTi',
            'SasukeducK', 'ShAaNiG', 'Sicario', 'STUTTERSHIT', 'TGALAXY', 'TORRENTGALAXY',
            'TSP', 'TSPxL', 'ViSION', 'VXT', 'WAF', 'WKS', 'x0r', 'YAWNiX', 'YIFY', 'YTS', 'PSA', ['EVO', 'WEB-DL only']
        ]
        pass

    async def get_additional_checks(self, meta):
        should_continue = True
        if meta['type'] == "DVDRIP":
            console.print("[bold red]DVDRIP uploads are not allowed on HHD.[/bold red]")
            return False

        return should_continue

    async def get_resolution_id(self, meta, mapping_only=False, reverse=False, resolution=None):
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1440p': '3',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9',
            'Other': '10'
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
