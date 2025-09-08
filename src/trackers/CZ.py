# -*- coding: utf-8 -*-
import re
from src.trackers.COMMON import COMMON
from src.trackers.AVISTAZ_NETWORK import AZTrackerBase


class CZ(AZTrackerBase):
    def __init__(self, config):
        super().__init__(config, tracker_name='CZ')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'CZ'
        self.source_flag = 'CinemaZ'
        self.banned_groups = ['']
        self.base_url = 'https://cinemaz.to'
        self.torrent_url = f'{self.base_url}/torrent/'

    async def rules(self, meta):
        return True

    def edit_name(self, meta):
        upload_name = meta.get('name').replace(meta['aka'], '').replace('Dubbed', '').replace('Dual-Audio', '')

        tag_lower = meta['tag'].lower()
        invalid_tags = ['nogrp', 'nogroup', 'unknown', '-unk-']

        if meta['tag'] == '' or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                upload_name = re.sub(f'-{invalid_tag}', '', upload_name, flags=re.IGNORECASE)
            upload_name = f'{upload_name}-NoGroup'

        return upload_name
