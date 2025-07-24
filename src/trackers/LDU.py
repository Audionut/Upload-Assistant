# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import platform
import httpx
import glob
import os
import langcodes
from src.trackers.COMMON import COMMON
from src.console import console
from src.languages import has_english_language


class LDU():
    def __init__(self, config):
        self.config = config
        self.tracker = 'LDU'
        self.source_flag = 'LDU'
        self.upload_url = 'https://theldu.to/api/torrents/upload'
        self.search_url = 'https://theldu.to/api/torrents/filter'
        self.torrent_url = 'https://theldu.to/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = []
        pass

    async def get_cat_id(self, meta):
        genres = f"{meta.get('keywords', '')} {meta.get('genres', '')}"
        sound_mixes = meta.get('imdb_info', {}).get('sound_mixes', [])

        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'Anime': '8',
            'FANRES': '12',
            'MUSIC': '3',
        }.get(meta['category'], '0')

        if 'hentai' in genres.lower():
            category_id = '10'
        elif any(x in genres.lower() for x in ['xxx', 'erotic', 'porn', 'adult', 'orgy']):
            if not await has_english_language(meta.get('subtitle_languages', [])):
                category_id = '45'
            else:
                category_id = '6'
        if meta['category'] == "MOVIE":
            if meta.get('3d') or "3D" in meta.get('edition', ''):
                category_id = '21'
            elif any(x in meta.get('edition', '').lower() for x in ["fanedit", "fanres"]):
                category_id = '12'
            elif meta.get('anime', False) or meta.get('mal_id', 0) != 0:
                category_id = '8'
            elif (any('silent film' in mix.lower() for mix in sound_mixes if isinstance(mix, str)) or meta.get('silent', False)):
                category_id = '18'
            elif "musical" in genres.lower():
                category_id = '25'
            elif any(x in genres.lower() for x in ['holiday', 'easter', 'christmas', 'halloween', 'thanksgiving']):
                category_id = '24'
            elif "documentary" in genres.lower():
                category_id = '17'
            elif any(x in genres.lower() for x in ['stand-up', 'standup']):
                category_id = '20'
            elif "short film" in genres.lower() or int(meta.get('imdb_info', {}).get('runtime', 0)) < 5:
                category_id = '19'
            elif not await has_english_language(meta.get('audio_languages', [])) and not await has_english_language(meta.get('subtitle_languages', [])):
                category_id = '22'
            elif "dubbed" in meta.get('audio', '').lower():
                category_id = '27'
            else:
                category_id = '1'
        elif meta['category'] == "TV":
            if meta.get('anime', False) or meta.get('mal_id', 0) != 0:
                category_id = '9'
            elif "documentary" in genres.lower():
                category_id = '40'
            elif not await has_english_language(meta.get('audio_languages', [])) and not await has_english_language(meta.get('subtitle_languages', [])):
                category_id = '29'
            elif meta.get('tv_pack', False):
                category_id = '2'
            elif "dubbed" in meta.get('audio', '').lower():
                category_id = '31'
            else:
                category_id = '41'

        return category_id

    async def get_type_id(self, type, meta):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3'
        }.get(type, '0')
        if any(x in meta.get('edition', '').lower() for x in ["fanedit", "fanres"]):
            type_id = '16'
        return type_id

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

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta)
        name = await self.edit_name(meta, cat_id)
        type_id = await self.get_type_id(meta['type'], meta)
        resolution_id = await self.get_res_id(meta['resolution'])
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
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
        base_dir = meta['base_dir']
        uuid = meta['uuid']
        specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
        nfo_files = glob.glob(specified_dir_path)
        nfo_file = None
        if nfo_files:
            nfo_file = open(nfo_files[0], 'rb')
        if nfo_file:
            files['nfo'] = ("nfo_file.nfo", nfo_file, "text/plain")
        data = {
            'name': name,
            'description': desc,
            'mediainfo': mi_dump,
            'bdinfo': bd_dump,
            'category_id': cat_id,
            'type_id': type_id,
            'resolution_id': resolution_id,
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb_id'],
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
            if response.status_code == 500:
                meta['tracker_status'][self.tracker]['status_message'] = "500 Internal Server Error. It probably uploaded through"
            else:
                try:
                    meta['tracker_status'][self.tracker]['status_message'] = response.json()
                    # adding torrent link to comment of torrent file
                    try:
                        t_id = response.json()['data'].split(".")[1].split("/")[3]
                        meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                        await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), self.torrent_url + t_id)
                    except Exception as e:
                        console.print(f"[bold red]Error extracting torrent ID: {e}[/bold red]")
                except Exception:
                    console.print("It may have uploaded, go check")
                    open_torrent.close()
                    return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    async def edit_name(self, meta, cat_id):
        ldu_name = meta['name']
        non_eng = False
        non_eng_audio = False
        iso_audio = None
        iso_subtitle = None
        if meta.get('original_language') != "en":
            non_eng = True
        if meta.get('audio_languages'):
            audio_language = meta['audio_languages'][0]
            if audio_language:
                try:
                    lang = langcodes.find(audio_language).to_alpha3()
                    iso_audio = lang.upper()
                    if not await has_english_language(audio_language):
                        non_eng_audio = True
                except Exception as e:
                    console.print(f"[bold red]Error extracting audio language: {e}[/bold red]")

        if meta.get('no_subs', False):
            iso_subtitle = "NoSubs"
        else:
            if meta.get('subtitle_languages'):
                subtitle_language = meta['subtitle_languages'][0]
                if subtitle_language:
                    try:
                        lang = langcodes.find(subtitle_language).to_alpha3()
                        iso_subtitle = f"Subs {lang.upper()}"
                    except Exception as e:
                        console.print(f"[bold red]Error extracting subtitle language: {e}[/bold red]")

        if cat_id == '18' and iso_subtitle:
            ldu_name = f"{ldu_name} [{iso_subtitle}]"

        elif non_eng or non_eng_audio:
            language_parts = []
            if iso_audio:
                language_parts.append(f"[{iso_audio}]")
            if iso_subtitle:
                language_parts.append(f"[{iso_subtitle}]")

            if language_parts:
                ldu_name = f"{ldu_name} {' '.join(language_parts)}"

        return ldu_name

    async def search_existing(self, meta, disctype):
        dupes = []
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb_id'],
            'types[]': await self.get_type_id(meta['type'], meta),
            'resolutions[]': await self.get_res_id(meta['resolution']),
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = params['name'] + f" {meta.get('season', '')}"
        if meta.get('edition', "") != "":
            params['name'] = params['name'] + f" {meta['edition']}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
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
