# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import platform
import httpx
import json

from src.trackers.COMMON import COMMON
from src.console import console


class AL():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config):
        self.config = config
        self.tracker = 'AL'
        self.source_flag = 'al'
        self.upload_url = 'https://animelovers.club/api/torrents/upload'
        self.search_url = 'https://animelovers.club/api/torrents/filter'
        self.torrent_url = 'https://animelovers.club/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant][color=#9400FF]AnimeLovers[/color][/url][/center]"
        self.banned_groups = [""]
        pass

    async def get_cat_id(self, category_name, meta):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')

        if 'HENTAI' in meta.get('mal_rating', "") or 'HENTAI' in str(meta.get('keywords', '')).upper():
            category_id = 7

        return category_id

    async def get_type_id(self, type):
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
        }.get(type, '1')
        return type_id

    async def get_res_id(self, resolution, bit_depth):
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
        return resolution_id

    async def edit_name(self, meta, mal_title=None):
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

        if tag == '':
            tag = '-NoGroup'
        if 'AVC' in video_codec and '264' in video_encode:
            name += f"{tag.strip()}"
        else:
            name += f" {video_codec}{tag.strip()}"

        console.print(f"[yellow]Corrected title : [green]{name}")
        return name

    async def get_mal_data(self, anime_id, meta):
        response = requests.get(f"https://api.jikan.moe/v4/anime/{anime_id}")
        content = response.json()
        title = content['data']['title'] if content['data']['title'] else None
        meta['mal_rating'] = content['data']['rating'].upper() if content['data']['rating'] else None
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

    async def upload(self, meta, disctype):
        title = await self.get_mal_data(meta['mal'], meta)
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'], meta)
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'], meta.get('bit_depth', ''))
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        name = await self.edit_name(meta, mal_title=title)
        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anon = 0
        else:
            anon = 1

        if meta['bdinfo'] is not None:
            mi_dump = None
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
            bd_dump = None
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb')
        files = {'torrent': open_torrent}
        data = {
            'name': name,
            'description': desc,
            'mediainfo': mi_dump,
            'bdinfo': bd_dump,
            'category_id': cat_id,
            'type_id': type_id,
            'resolution_id': resolution_id,
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb'],
            'tvdb': meta['tvdb_id'],
            'mal': meta['mal_id'],
            'igdb': 0,
            'anonymous': anon,
            'stream': meta['stream'],
            'sd': meta['sd'],
            'keywords': meta['keywords'],
            'personal_release': int(meta.get('personalrelease', False)),
            'internal': 0,
            'featured': 0,
            'free': 0,
            'doubleup': 0,
            'sticky': 0,
        }
        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1

        if region_id != 0:
            data['region_id'] = region_id
        if distributor_id != 0:
            data['distributor_id'] = distributor_id
        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }

        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
            try:
                meta['tracker_status'][self.tracker]['status_message'] = response.json()
                # adding torrent link to comment of torrent file
                t_id = response.json()['data'].split(".")[1].split("/")[3]
                meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), self.torrent_url + t_id)
            except Exception:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            json_formatted_str = json.dumps(data, indent=4)
            console.print(json_formatted_str)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    async def search_existing(self, meta, disctype):
        dupes = []
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category'], meta),
            'types[]': await self.get_type_id(meta['type']),
            'resolutions[]': await self.get_res_id(meta['resolution'], meta.get('bit_depth', '')),
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = params['name'] + f" {meta.get('season', '')}"
        if meta.get('edition', "") != "":
            params['name'] = params['name'] + f" {meta['edition']}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    for each in data['data']:
                        result = [each][0]['attributes']['name']
                        dupes.append(result)
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 5 seconds")
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            await asyncio.sleep(5)

        return dupes
