# -*- coding: utf-8 -*-
# import discord
import os
import glob
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class FNP(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='FNP')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'FNP'
        self.source_flag = 'FnP'
        self.base_url = 'https://fearnopeer.com'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            "4K4U", "BiTOR", "d3g", "FGT", "FRDS", "FTUApps", "GalaxyRG", "LAMA",
            "MeGusta", "NeoNoir", "PSA", "RARBG", "YAWNiX", "YTS", "YIFY", "x0r"
        ]
        pass

    async def get_res_id(self, resolution):
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(resolution, '10')
        return resolution_id

    async def get_additional_data(self, meta):
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data

    async def get_additional_files(self, meta):
        files = {}
        base_dir = meta['base_dir']
        uuid = meta['uuid']
        specified_dir_path = os.path.join(base_dir, 'tmp', uuid, '*.nfo')
        nfo_files = glob.glob(specified_dir_path)

        if nfo_files:
            nfo_path = nfo_files[0]
            with open(nfo_path, 'rb') as f:
                content = f.read()
            files['nfo'] = (os.path.basename(nfo_path), content, 'text/plain')

        return files
