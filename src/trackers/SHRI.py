# -*- coding: utf-8 -*-
# import discord
import re
from src.languages import process_desc_language
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class SHRI(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='SHRI')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'SHRI'
        self.source_flag = 'ShareIsland'
        self.base_url = 'https://shareisland.org'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_name(self, meta):
        shareisland_name = meta['name']
        resolution = meta.get('resolution')
        video_codec = meta.get('video_codec')
        video_encode = meta.get('video_encode')
        name_type = meta.get('type', "")
        source = meta.get('source', "")
        imdb_info = meta.get('imdb_info') or {}

        akas = imdb_info.get('akas', [])
        italian_title = None

        for aka in akas:
            if isinstance(aka, dict) and aka.get("country") == "Italy":
                italian_title = aka.get("title")
                break

        use_italian_title = self.config['TRACKERS'][self.tracker].get('use_italian_title', False)
        if italian_title and use_italian_title:
            shareisland_name = shareisland_name.replace(meta.get('aka', ''), '')
            shareisland_name = shareisland_name.replace(meta.get('title', ''), italian_title)

        audio_lang_str = ""

        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        if meta.get('audio_languages'):
            audio_languages = []
            for lang in meta['audio_languages']:
                lang_up = lang.upper()
                if lang_up not in audio_languages:
                    audio_languages.append(lang_up)
            audio_lang_str = " - ".join(audio_languages)

        if meta.get('dual_audio'):
            shareisland_name = shareisland_name.replace("Dual-Audio ", "", 1)

        if audio_lang_str:
            if name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):
                shareisland_name = shareisland_name.replace(str(meta['year']), f"{meta['year']} {audio_lang_str}", 1)
            elif not meta.get('is_disc') == "BDMV":
                shareisland_name = shareisland_name.replace(meta['resolution'], f"{audio_lang_str} {meta['resolution']}", 1)

        if name_type == "DVDRIP":
            source = "DVDRip"
            shareisland_name = shareisland_name.replace(f"{meta['source']} ", "", 1)
            shareisland_name = shareisland_name.replace(f"{meta['video_encode']}", "", 1)
            shareisland_name = shareisland_name.replace(f"{source}", f"{resolution} {source}", 1)
            shareisland_name = shareisland_name.replace((meta['audio']), f"{meta['audio']}{video_encode}", 1)

        elif meta['is_disc'] == "DVD" or (name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")):
            shareisland_name = shareisland_name.replace((meta['source']), f"{resolution} {meta['source']}", 1)
            shareisland_name = shareisland_name.replace((meta['audio']), f"{video_codec} {meta['audio']}", 1)

        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                shareisland_name = re.sub(f"-{invalid_tag}", "", shareisland_name, flags=re.IGNORECASE)
            shareisland_name = f"{shareisland_name}-NoGroup"

        return {'name': shareisland_name}

    async def get_type_id(self, meta):
        type_id = {
            'DISC': '26',
            'REMUX': '7',
            'WEBDL': '27',
            'WEBRIP': '15',
            'HDTV': '6',
            'ENCODE': '15',
        }.get(meta['type'], '0')
        return {'type_id': type_id}
