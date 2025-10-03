# -*- coding: utf-8 -*-
# import discord
import re
import os
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

    async def get_additional_data(self, meta):
        data = {
            'mod_queue_opt_in': await self.get_flag(meta, 'modq'),
        }
        return data

    def get_basename(self, meta):
        path = next(iter(meta['filelist']), meta['path'])
        return os.path.basename(path)

    async def get_name(self, meta):
        """
        Generate ShareIsland release name with REMUX detection for UNTOUCHED/VU files,
        audio language tags, Italian title support, and [SUBS] tagging.
        """
        basename = self.get_basename(meta)
        shareisland_name = meta['name']
        resolution = meta.get('resolution')
        video_codec = meta.get('video_codec')
        video_encode = meta.get('video_encode')
        name_type = meta.get('type', "")
        source = meta.get('source', "")
        imdb_info = meta.get('imdb_info') or {}
        type = meta.get('type', "")
        akas = imdb_info.get('akas', [])
        italian_title = None

        remove_list = ['Dubbed']
        for each in remove_list:
            shareisland_name = shareisland_name.replace(each, '')

        # Extract Italian title from IMDb AKAs
        for aka in akas:
            if isinstance(aka, dict) and aka.get("country") == "Italy":
                italian_title = aka.get("title")
                break

        use_italian_title = self.config['TRACKERS'][self.tracker].get('use_italian_title', False)

        # Process audio languages if not already done
        audio_lang_str = ""
        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        # Build audio language string (e.g., "ITALIAN - ENGLISH")
        if meta.get('audio_languages'):
            audio_languages = []
            for lang in meta['audio_languages']:
                lang_up = lang.upper()
                if lang_up not in audio_languages:
                    audio_languages.append(lang_up)
            audio_lang_str = " - ".join(audio_languages)

        # Clean audio string locally without modifying meta
        meta.get('audio', '').replace('Dual-Audio', '').strip()

        # Remove Dual-Audio from shareisland_name if present
        if meta.get('dual_audio'):
            shareisland_name = shareisland_name.replace("Dual-Audio", "", 1)

        # Detect UNTOUCHED/VU files and classify as REMUX
        if not meta.get('is_disc') and ('untouched' in basename.lower() or 'vu' in basename.lower()):
            type = "REMUX"
            name_type = "REMUX"
            meta['type'] = "REMUX"
            
            if meta['type'] in shareisland_name:
                shareisland_name = shareisland_name.replace(f"{meta['type']}", type, 1)
            else:
                shareisland_name = shareisland_name.replace(source, f"{source} REMUX", 1)
            
            shareisland_name = re.sub(r'\bUNTOUCHED\b', '', shareisland_name, flags=re.IGNORECASE)
            shareisland_name = re.sub(r'\bVU\b', '', shareisland_name, flags=re.IGNORECASE)

        # Normalize REMUX naming per tracker rules
        if name_type == "REMUX":
            shareisland_name = shareisland_name.replace('x264', video_codec).replace('x265', video_codec)
            
            if video_codec in shareisland_name:
                shareisland_name = re.sub(rf'[\s\-]{re.escape(video_codec)}', '', shareisland_name, count=1)
                shareisland_name = shareisland_name.replace('REMUX', f'REMUX {video_codec}', 1)

        # Apply Italian title if configured
        if italian_title and use_italian_title:
            shareisland_name = shareisland_name.replace(meta.get('aka', ''), '')
            shareisland_name = shareisland_name.replace(meta.get('title', ''), italian_title)

        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        # Check for Italian audio (excluding commentary)
        audios = []
        if 'mediainfo' in meta and 'media' in meta['mediainfo'] and 'track' in meta['mediainfo']['media']:
            audios = [
                audio for audio in meta['mediainfo']['media']['track'][2:]
                if audio.get('@type') == 'Audio'
                and isinstance(audio.get('Language'), str)
                and audio.get('Language').lower() in {'it', 'it-it'}
                and "commentary" not in str(audio.get('Title', '')).lower()
            ]

        # Check for Italian subtitles
        subs = []
        if 'mediainfo' in meta and 'media' in meta['mediainfo'] and 'track' in meta['mediainfo']['media']:
            subs = [
                sub for sub in meta['mediainfo']['media']['track']
                if sub.get('@type') == 'Text'
                and isinstance(sub.get('Language'), str)
                and sub['Language'].lower() in {'it', 'it-it'}
            ]

        # Add [SUBS] tag for Italian subs without Italian audio
        if len(audios) > 0:
            shareisland_name = shareisland_name
        elif len(subs) > 0:
            if not meta.get('tag'):
                shareisland_name = shareisland_name + " [SUBS]"
            else:
                shareisland_name = shareisland_name.replace(meta['tag'], f" [SUBS]{meta['tag']}")

        # Insert audio language string per tracker rules
        if audio_lang_str:
            if name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):
                shareisland_name = shareisland_name.replace(str(meta['year']), f"{meta['year']} {audio_lang_str}", 1)
            elif not meta.get('is_disc') == "BDMV":
                shareisland_name = shareisland_name.replace(meta['resolution'], f"{audio_lang_str} {meta['resolution']}", 1)

        # DVD rip formatting
        if name_type == "DVDRIP":
            source = "DVDRip"
            shareisland_name = shareisland_name.replace(f"{meta['source']} ", "", 1)
            shareisland_name = shareisland_name.replace(f"{meta['video_encode']}", "", 1)
            shareisland_name = shareisland_name.replace(f"{source}", f"{resolution} {source}", 1)
            shareisland_name = shareisland_name.replace((meta['audio']), f"{meta['audio']}{video_encode}", 1)

        # DVD disc and DVD REMUX formatting
        elif meta['is_disc'] == "DVD" or (name_type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD")):
            shareisland_name = shareisland_name.replace((meta['source']), f"{resolution} {meta['source']}", 1)
            shareisland_name = shareisland_name.replace((meta['audio']), f"{video_codec} {meta['audio']}", 1)

        # Replace invalid tags with NoGroup
        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                shareisland_name = re.sub(f"-{invalid_tag}", "", shareisland_name, flags=re.IGNORECASE)
            shareisland_name = f"{shareisland_name}-NoGroup"

        shareisland_name = re.sub(r'\s{2,}', ' ', shareisland_name)

        return {'name': shareisland_name}

    async def get_type_id(self, meta):
        """Map release type to ShareIsland type IDs"""
        type_id = {
            'DISC': '26',
            'REMUX': '7',
            'WEBDL': '27',
            'WEBRIP': '15',
            'HDTV': '6',
            'ENCODE': '15',
        }.get(meta['type'], '0')
        return {'type_id': type_id}
