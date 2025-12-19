# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import re
import requests
from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class AL(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='AL')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'AL'
        self.source_flag = 'al'
        self.base_url = 'https://animelovers.club'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_additional_checks(self, meta):
        should_continue = True

        if not meta["mal"]:
            console.print("[bold red]MAL ID is missing, cannot upload to AL.[/bold red]")
            meta["skipping"] = f'{self.tracker}'
            return False

        return should_continue

    async def get_category_id(self, meta):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(meta['category'], '0')

        if 'HENTAI' in meta.get('mal_rating', "") or 'HENTAI' in str(meta.get('keywords', '')).upper():
            category_id = '7'

        return {'category_id': category_id}

    async def get_type_id(self, meta):
        type_id = {
            'BDMV': '1',
            'DISC': '1',
            'REMUX': '2',
            'ENCODE': '3',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'DVDISO': '7',
            'DVDRIP': '8',
            'RAW': '9',
            'BDRIP': '10',
            'COLOR': '11',
            'MONO': '12'
        }.get(meta['type'], '1')
        return {'type_id': type_id}

    async def get_resolution_id(self, meta):
        resolution = meta['resolution']
        bit_depth = meta.get('bit_depth', '')
        resolution_to_compare = resolution
        if bit_depth == "10":
            resolution_to_compare = f"{resolution} 10bit"
        resolution_id = {
            '4320p 10bit': '1',
            '4320p': '14',
            '2160p 10bit': '2',
            '2160p': '13',
            '1080p 10bit': '3',
            '1080p': '12',
            '1080i': '4',
            '816p 10bit': '11',
            '816p': '16',
            '720p 10bit': '5',
            '720p': '15',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(resolution_to_compare, '10')
        return {'resolution_id': resolution_id}

    async def get_name(self, meta):
        mal_title = await self.get_mal_data(meta)
        category = meta['category']
        title = ''
        try:
            title = meta['imdb_info']['title']
        except Exception as e:
            console.log(e)
            title = meta['title']
        year = ''
        service = meta.get('service', '')
        try:
            year = meta['imdb_info']['year']
        except Exception as e:
            console.log(e)
            year = meta['year']
        season = meta['season']
        episode = meta.get('episode', '')
        resolution = meta['resolution'].replace('i', 'p')
        bit_depth = meta.get('bit_depth', '')
        service = meta['service']
        source = meta['source']
        region = meta.get('region', '')
        if meta['is_disc'] is None:
            video_type = meta['type']
            audios = await self.format_audios(meta['mediainfo']['media']['track'])
            subtitles = await self.format_subtitles(meta['mediainfo']['media']['track'])
        else:
            video_type = meta['is_disc']
            audios = await self.format_audios_disc(meta['bdinfo']['audio'])
            subtitles = await self.format_subtitles_disc(meta['bdinfo']['subtitles'])
        tag = meta['tag']
        video_encode = meta.get('video_encode', '')
        video_codec = meta['video_codec']

        name = f"{title}"
        if mal_title and title.upper() != mal_title.upper():
            name += f" ({mal_title})"
        if category == 'MOVIE':
            name += f" {year}"
        else:
            name += f" {season}{episode}"

        name += f" {resolution}"

        if bit_depth == "10":
            name += f" {bit_depth}Bit"

        if service != '':
            name += f" {service}"

        if region not in ['', None]:
            name += f" {region}"

        if meta['is_disc'] is None:
            if source in ['BluRay', 'Blu-ray', 'LaserDisc', 'DCP']:
                if source == 'Blu-ray':
                    source = 'BluRay'
                name += f" {source}"

            if video_type != 'ENCODE':
                name += f" {video_type}"
        else:
            name += f" {video_type}"

        name += f" {audios}"

        if len(subtitles.strip()) > 0:
            name += f" {subtitles}Subs"

        if len(video_encode.strip()) > 0:
            name += f" {video_encode.strip()}"

        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                tag = re.sub(f"-{invalid_tag}", "", tag, flags=re.IGNORECASE)
            tag = '-NoGroup'

        if 'AVC' in video_codec and '264' in video_encode:
            name += f"{tag.strip()}"
        else:
            name += f" {video_codec}{tag.strip()}"

        console.print(f"[yellow]Corrected title : [green]{name}")
        return {'name': name}

    async def get_mal_data(self, meta):
        anime_id = meta['mal']
        response = requests.get(f"https://api.jikan.moe/v4/anime/{anime_id}")
        content = response.json()
        title = content['data']['title'] if content['data']['title'] else None
        meta['mal_rating'] = content['data']['rating'].upper() if content['data']['rating'] else ""
        return title

    async def format_audios(self, tracks):
        formats = {}
        audio_tracks = [track for track in tracks if track['@type'] == "Audio"]
        for audio_track in audio_tracks:
            channels_str = await self.get_correct_channels_str(audio_track['Channels'])
            audio_codec = await self.get_correct_audio_codec_str(audio_track['Format'])
            audio_format = f"{audio_codec} {channels_str}"
            audio_language = await self.get_correct_language_str(audio_track['Language'])
            if (formats.get(audio_format, False)):
                if audio_language not in formats[audio_format]:
                    formats[audio_format] += f"-{audio_language}"
            else:
                formats[audio_format] = audio_language

        audios = ""
        for audio_format in formats.keys():
            audios_languages = formats[audio_format]
            audios += f"{audios_languages} {audio_format} "
        return audios.strip()

    async def format_audios_disc(self, tracks):
        formats = {}
        for audio_track in tracks:
            channels_str = await self.get_correct_channels_str(audio_track['channels'])
            audio_codec = await self.get_correct_audio_codec_str(audio_track['codec'])
            audio_format = f"{audio_codec} {channels_str}"
            audio_language = await self.get_correct_language_str(audio_track['language'])
            if (formats.get(audio_format, False)):
                if audio_language not in formats[audio_format]:
                    formats[audio_format] += f"-{audio_language}"
            else:
                formats[audio_format] = audio_language

        audios = ""
        for audio_format in formats.keys():
            audios_languages = formats[audio_format]
            audios += f"{audios_languages} {audio_format} "
        return audios.strip()

    async def format_subtitles(self, tracks):
        subtitles = []
        subtitle_tracks = [track for track in tracks if track['@type'] == "Text"]
        for subtitle_track in subtitle_tracks:
            subtitle_language = await self.get_correct_language_str(subtitle_track['Language'])
            if subtitle_language not in subtitles:
                subtitles.append(subtitle_language)
        if len(subtitles) > 3:
            return 'Multi-'
        return "-".join(subtitles)

    async def format_subtitles_disc(self, tracks):
        subtitles = []
        for subtitle_track in tracks:
            subtitle_language = await self.get_correct_language_str(subtitle_track)
            if subtitle_language not in subtitles:
                subtitles.append(subtitle_language)
        if len(subtitles) > 3:
            return 'Multi-'
        return "-".join(subtitles)

    async def get_correct_language_str(self, language):
        try:
            language_upper = language.upper()
            if language_upper.startswith('JA'):
                return 'Jap'
            elif language_upper.startswith('EN'):
                return 'Eng'
            elif language_upper.startswith('ES'):
                return 'Spa'
            elif language_upper.startswith('PT'):
                return 'Por'
            elif language_upper.startswith('FR'):
                return 'Fre'
            elif language_upper.startswith('AR'):
                return 'Ara'
            elif language_upper.startswith('IT'):
                return 'Ita'
            elif language_upper.startswith('RU'):
                return 'Rus'
            elif language_upper.startswith('ZH') or language_upper.startswith('CHI'):
                return 'Chi'
            elif language_upper.startswith('DE') or language_upper.startswith('GER'):
                return 'Ger'
            else:
                if len(language) >= 3:
                    return language[0:3]
                else:
                    return language
        except Exception as e:
            console.log(e)
            return 'UNKOWN'

    async def get_correct_channels_str(self, channels_str):
        if channels_str == '6':
            return '5.1'
        elif channels_str == '5':
            return '5.0'
        elif channels_str == '2':
            return '2.0'
        elif channels_str == '1':
            return '1.0'
        else:
            return channels_str

    async def get_correct_audio_codec_str(self, audio_codec_str):
        if audio_codec_str == 'AC-3':
            return 'AC3'
        if audio_codec_str == 'E-AC-3':
            return 'DD+'
        if audio_codec_str == 'MLP FBA':
            return 'TrueHD'
        if audio_codec_str == 'DTS-HD Master Audio':
            return 'DTS'
        if audio_codec_str == 'Dolby Digital Audio':
            return 'DD'
        else:
            return audio_codec_str
