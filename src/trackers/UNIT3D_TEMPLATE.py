# -*- coding: utf-8 -*-
# import discord
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class UNIT3D_TEMPLATE(UNIT3D):
    ###############################################################
    ########                    EDIT ME                    ######## noqa E266
    ###############################################################

    # ALSO EDIT CLASS NAME ABOVE AS ABBREVIATED TRACKER NAME

    def __init__(self, config):
        super().__init__(config, tracker_name='UNIT3D_TEMPLATE')  # EDIT ME AS ABBREVIATED TRACKER NAME
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'Abbreviated Tracker Name'
        self.source_flag = 'Source flag for .torrent'
        self.base_url = 'https://domain.tld'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [""]
        pass

    # If default UNIT3D categories, remove this function
    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    # If default UNIT3D types, remove this function
    async def get_type_id(self, type):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(type, '0')
        return type_id

    # If default UNIT3D resolutions, remove this function
    async def get_res_id(self, resolution):
        resolution_id = {
            '8640p': '10',
            '4320p': '1',
            '2160p': '2',
            '1440p': '3',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(resolution, '10')
        return resolution_id

    # If there are tracker specific checks to be done before upload, add them here
    # Is it a movie only tracker? Are concerts banned? Etc.
    async def get_additional_checks(self, meta):
        should_continue = True
        return should_continue

    # If the tracker has modq in the api, otherwise remove this function
    async def get_additional_data(self, meta):
        data = {
            'modq': await self.get_flag(meta, 'modq'),
        }

        return data

    # If the tracker has specific naming conventions, add them here
    async def edit_name(self, meta):
        UNIT3D_TEMPLATE_name = meta['name']
        return {'name': UNIT3D_TEMPLATE_name}
