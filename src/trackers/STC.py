# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import cli_ui
import re
from src.console import console
from src.get_desc import DescriptionBuilder
from src.rehostimages import check_hosts
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class STC(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='STC')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'STC'
        self.base_url = 'https://skipthecommercials.xyz'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [""]
        self.approved_image_hosts = ['imgbox', 'imgbb']
        pass

    async def get_type_id(self, meta, type=None, reverse=False, mapping_only=False):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(meta.get('type'), '0')
        if meta.get('tv_pack'):
            if meta.get('sd'):
                # Season SD
                if meta.get('type') not in ["WEBDL", "WEBRIP"]:
                    type_id = '17'
                else:
                    type_id = '14'
            else:
                if meta.get('type') not in ["WEBDL", "WEBRIP"]:
                    type_id = '18'
                else:
                    type_id = '13'

        return {'type_id': type_id}

    async def get_additional_checks(self, meta):
        should_continue = True
        if meta['category'] != 'TV':
            if not meta['unattended']:
                console.print(f'[bold red]Only TV uploads allowed at {self.tracker}.[/bold red]')
            return False

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy', 'hentai', 'adult animation', 'softcore']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print(f'[bold red]Porn is not allowed at {self.tracker}.[/bold red]')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    return False
            else:
                return False

        return should_continue

    async def check_image_hosts(self, meta):
        url_host_mapping = {
            "ibb.co": "imgbb",
            "imgbox.com": "imgbox",
        }
        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=self.approved_image_hosts)

    async def get_description(self, meta):
        if 'STC_images_key' in meta:
            image_list = meta['STC_images_key']
        else:
            image_list = meta['image_list']

        return {'description': await DescriptionBuilder(self.tracker, self.config).unit3d_edit_desc(meta, image_list=image_list, approved_image_hosts=self.approved_image_hosts)}
