# -*- coding: utf-8 -*-
# import discord
import requests
import platform

from src.trackers.COMMON import COMMON
from src.console import console
from pathlib import Path


class TL():
    CATEGORIES = {
        'Anime': 34,
        'Movie4K': 47,
        'MovieBluray': 13,
        'MovieBlurayRip': 14,
        'MovieCam': 8,
        'MovieTS': 9,
        'MovieDocumentary': 29,
        'MovieDvd': 12,
        'MovieDvdRip': 11,
        'MovieForeign': 36,
        'MovieHdRip': 43,
        'MovieWebrip': 37,
        'TvBoxsets': 27,
        'TvEpisodes': 26,
        'TvEpisodesHd': 32,
        'TvForeign': 44
    }

    def __init__(self, config):
        self.config = config
        self.tracker = 'TL'
        self.source_flag = 'TorrentLeech.org'
        self.upload_url = 'https://www.torrentleech.org/torrents/upload/apiupload'
        self.signature = None
        self.banned_groups = [""]

        self.announce_key = self.config['TRACKERS'][self.tracker]['announce_key']
        self.config['TRACKERS'][self.tracker]['announce_url'] = f"https://tracker.torrentleech.org/a/{self.announce_key}/announce"
        pass

    async def get_cat_id(self, common, meta):
        if meta.get('anime', 0):
            return self.CATEGORIES['Anime']

        if meta['category'] == 'MOVIE':
            if meta['original_language'] != 'en':
                return self.CATEGORIES['MovieForeign']
            elif 'Documentary' in meta['genres']:
                return self.CATEGORIES['MovieDocumentary']
            elif meta['uhd']:
                return self.CATEGORIES['Movie4K']
            elif meta['is_disc'] in ('BDMV', 'HDDVD') or (meta['type'] == 'REMUX' and meta['source'] in ('BluRay', 'HDDVD')):
                return self.CATEGORIES['MovieBluray']
            elif meta['type'] == 'ENCODE' and meta['source'] in ('BluRay', 'HDDVD'):
                return self.CATEGORIES['MovieBlurayRip']
            elif meta['is_disc'] == 'DVD' or (meta['type'] == 'REMUX' and 'DVD' in meta['source']):
                return self.CATEGORIES['MovieDvd']
            elif meta['type'] == 'ENCODE' and 'DVD' in meta['source']:
                return self.CATEGORIES['MovieDvdRip']
            elif 'WEB' in meta['type']:
                return self.CATEGORIES['MovieWebrip']
            elif meta['type'] == 'HDTV':
                return self.CATEGORIES['MovieHdRip']
        elif meta['category'] == 'TV':
            if meta['original_language'] != 'en':
                return self.CATEGORIES['TvForeign']
            elif meta.get('tv_pack', 0):
                return self.CATEGORIES['TvBoxsets']
            elif meta['sd']:
                return self.CATEGORIES['TvEpisodes']
            else:
                return self.CATEGORIES['TvEpisodesHd']

        raise NotImplementedError('Failed to determine TL category!')

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(common, meta)
        # await common.unit3d_edit_desc(meta, self.tracker, self.signature)

        open_desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'a+', encoding='utf-8')

        info_filename = 'BD_SUMMARY_00' if meta['bdinfo'] is not None else 'MEDIAINFO_CLEANPATH'
        open_info = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/{info_filename}.txt", 'r', encoding='utf-8')
        open_desc.write('\n\n')
        open_desc.write(open_info.read())
        open_info.close()

        open_desc.seek(0)
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb')
        files = {
            'nfo': open_desc,
            'torrent': (self.get_name(meta) + '.torrent', open_torrent)
        }
        data = {
            'announcekey': self.announce_key,
            'category': cat_id
        }
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }

        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers)
            if not response.text.isnumeric():
                meta['tracker_status'][self.tracker]['status_message'] = response.text
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()
        open_desc.close()

    def get_name(self, meta):
        path = Path(meta['path'])
        return path.stem if path.is_file() else path.name
