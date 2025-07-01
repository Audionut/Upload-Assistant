# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import platform
import httpx
import re
import glob
import os
from src.trackers.COMMON import COMMON
from src.console import console
from src.rehostimages import check_hosts
from data.config import config


class DP():
    def __init__(self, config):
        self.config = config
        self.tracker = 'DP'
        self.source_flag = 'DarkPeers'
        self.upload_url = 'https://darkpeers.org/api/torrents/upload'
        self.search_url = 'https://darkpeers.org/api/torrents/filter'
        self.torrent_url = 'https://darkpeers.org/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = [""]
        pass

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

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
        name = await self.edit_name(meta)
        if meta.get('dp_skipping', False):
            console.print("[red]Skipping DP upload as language conditions were not met.")
            return
        url_host_mapping = {
            "ibb.co": "imgbb",
            "pixhost.to": "pixhost",
            "imgbox.com": "imgbox",
            "imagebam.com": "bam",
        }
        approved_image_hosts = ['imgbox', 'imgbb', 'pixhost', 'bam']
        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=approved_image_hosts)
        if 'DP_images_key' in meta:
            image_list = meta['DP_images_key']
        else:
            image_list = meta['image_list']
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        modq = await self.get_flag(meta, 'modq')
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        if meta.get('logo', "") == "":
            from src.tmdb import get_logo
            TMDB_API_KEY = config['DEFAULT'].get('tmdb_api', False)
            TMDB_BASE_URL = "https://api.themoviedb.org/3"
            tmdb_id = meta.get('tmdb')
            category = meta.get('category')
            debug = meta.get('debug')
            logo_languages = ['da', 'sv', 'no', 'fi', 'is', 'en']
            logo_path = await get_logo(tmdb_id, category, debug, logo_languages=logo_languages, TMDB_API_KEY=TMDB_API_KEY, TMDB_BASE_URL=TMDB_BASE_URL)
            if logo_path:
                meta['logo'] = logo_path
        await common.unit3d_edit_desc(meta, self.tracker, self.signature, image_list=image_list)
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
            'mod_queue_opt_in': modq,
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
            console.print(data)
        open_torrent.close()

    async def edit_name(self, meta):
        dp_name = meta.get('name')
        nordic_languages = ['danish', 'swedish', 'norwegian', 'icelandic', 'finnish']
        english_languages = ['english']
        meta['dp_skipping'] = False

        if meta['is_disc'] == "BDMV" and 'bdinfo' in meta:
            has_english_audio = False
            has_nordic_audio = False

            if 'audio' in meta['bdinfo']:
                for audio_track in meta['bdinfo']['audio']:
                    if 'language' in audio_track:
                        audio_lang = audio_track['language'].lower()
                        if audio_lang in nordic_languages:
                            has_nordic_audio = True
                            break
                        elif audio_lang in english_languages:
                            has_english_audio = True

            if not has_english_audio and not has_nordic_audio:
                has_nordic_subtitle = False
                if 'subtitles' in meta['bdinfo']:
                    for subtitle in meta['bdinfo']['subtitles']:
                        if subtitle.lower() in (nordic_languages + english_languages):
                            has_nordic_subtitle = True
                            break

                    if not has_nordic_subtitle:
                        meta['dp_skipping'] = True
                        return dp_name

        elif not meta['is_disc'] == "BDMV":
            media_info_text = None
            try:
                media_info_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
                with open(media_info_path, 'r', encoding='utf-8') as f:
                    media_info_text = f.read()
            except (FileNotFoundError, KeyError) as e:
                print(f"Error processing MEDIAINFO.txt: {e}")

            if media_info_text:
                audio_section = re.findall(r'Audio[\s\S]+?Language\s+:\s+(\w+)', media_info_text)
                subtitle_section = re.findall(r'Text[\s\S]+?Language\s+:\s+(\w+)', media_info_text)

                has_nordic_audio = False
                has_english_audio = False
                for language in audio_section:
                    language = language.lower().strip()
                    if language in nordic_languages:
                        has_nordic_audio = True
                        break
                    elif language in english_languages:
                        has_english_audio = True
                        break

                if not has_english_audio and not has_nordic_audio:
                    has_nordic_sub = False
                    for language in subtitle_section:
                        language = language.lower().strip()
                        if language in (nordic_languages + english_languages):
                            has_nordic_sub = True
                            break

                    if not has_nordic_sub:
                        meta['dp_skipping'] = True
                        return dp_name

        return dp_name

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if config_flag is not None:
            return 1 if config_flag else 0

        return 1 if meta.get(flag_name, False) else 0

    async def search_existing(self, meta, disctype):
        dupes = []
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category']),
            'types[]': await self.get_type_id(meta['type']),
            'resolutions[]': await self.get_res_id(meta['resolution']),
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
