# -*- coding: utf-8 -*-
# import discord
import re
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

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if config_flag is not None:
            return 1 if config_flag else 0

        return 1 if meta.get(flag_name, False) else 0

    async def edit_name(self, meta):
        shareisland_name = meta['name']
        resolution = meta.get('resolution')
        video_codec = meta.get('video_codec')
        video_encode = meta.get('video_encode')
        name_type = meta.get('type', "")
        source = meta.get('source', "")

        audio_lang_str = ""

        if meta.get('audio_languages'):
            audio_languages = []
            for lang in meta['audio_languages']:
                lang_up = lang.upper()
                if lang_up not in audio_languages:
                    audio_languages.append(lang_up)
            audio_lang_str = " - ".join(audio_languages)

        if not audio_lang_str:
            try:
                media_info_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
                with open(media_info_path, 'r', encoding='utf-8') as f:
                    media_info_text = f.read()

                audio_section = re.findall(r'Audio[\s\S]+?Language\s+:\s+(\w+)', media_info_text)
                audio_languages = []
                for lang in audio_section:
                    lang_up = lang.upper()
                    if lang_up not in audio_languages:
                        audio_languages.append(lang_up)
                audio_lang_str = " - ".join(audio_languages) if audio_languages else ""
            except (FileNotFoundError, KeyError):
                pass

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

        return shareisland_name

    async def get_type_id(self, type=None, reverse=False):
        type_mapping = {
            'DISC': '26',
            'REMUX': '7',
            'WEBDL': '27',
            'WEBRIP': '15',
            'HDTV': '6',
            'ENCODE': '15',
        }

        if reverse:
            # Return a reverse mapping of type IDs to type names
            return {v: k for k, v in type_mapping.items()}
        elif type is not None:
            # Return the specific type ID
            return type_mapping.get(type, '0')
        else:
            # Return the full mapping
            return type_mapping
