# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import platform
import httpx
import re
from src.trackers.COMMON import COMMON
from src.console import console
from src.languages import process_desc_language


class CBR():
    def __init__(self, config):
        self.config = config
        self.tracker = 'CBR'
        self.source_flag = 'CapybaraBR'
        self.upload_url = 'https://capybarabr.com/api/torrents/upload'
        self.search_url = 'https://capybarabr.com/api/torrents/filter'
        self.torrent_url = 'https://capybarabr.com/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = [
            '3LTON', '4yEo', 'ADE', 'AFG', 'AROMA', 'AniHLS', 'AniURL', 'AnimeRG', 'BLUDV', 'CHD', 'CM8', 'Comando', 'CrEwSaDe', 'DNL', 'DeadFish',
            'ELiTE', 'FGT', 'FRDS', 'FUM', 'FaNGDiNG0', 'Flights', 'HAiKU', 'HD2DVD', 'HDS', 'HDTime', 'Hi10', 'Hiro360', 'ION10', 'JIVE', 'KiNGDOM',
            'LEGi0N', 'LOAD', 'Lapumia', 'Leffe', 'MACCAULAY', 'MeGusta', 'NOIVTC', 'NhaNc3', 'OFT', 'Oj', 'PRODJi', 'PiRaTeS', 'PlaySD', 'RAPiDCOWS',
            'RARBG', 'RDN', 'REsuRRecTioN', 'RMTeam', 'RetroPeeps', 'SANTi', 'SILVEIRATeam', 'SPASM', 'SPDVD', 'STUTTERSHIT', 'SicFoI', 'TGx', 'TM',
            'TRiToN', 'Telly', 'UPiNSMOKE', 'URANiME', 'WAF', 'XS', 'YIFY', 'ZKBL', 'ZMNT', 'ZmN', 'aXXo', 'd3g', 'eSc', 'iPlanet', 'mHD', 'mSD', 'nHD',
            'nSD', 'nikt0', 'playXD', 'x0r', 'xRed'
        ]
        pass

    async def get_cat_id(self, category_name, meta):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'ANIMES': '4'
        }.get(category_name, '0')
        if meta['anime'] is True and category_id == '2':
            category_id = '4'
        return category_id

    async def get_type_id(self, type):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'ENCODE': '3',
            'DVDRIP': '3',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6'
        }.get(type, '0')
        return type_id

    async def get_res_id(self, resolution):
        resolution_id = {
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9',
            'Other': '10',
        }.get(resolution, '10')
        return resolution_id

    async def edit_name(self, meta):
        name = meta['name'].replace('DD+ ', 'DDP').replace('DD ', 'DD').replace('AAC ', 'AAC').replace('FLAC ', 'FLAC')

        # Se for Series ou Anime, remove o ano do título
        if meta.get('category') in ['TV', 'ANIMES']:
            year = str(meta.get('year', ''))
            if year and year in name:
                name = name.replace(year, '').replace(f"({year})", '').strip()
                name = re.sub(r'\s{2,}', ' ', name)

        # Remove o título AKA, exceto se for nacional
        if meta.get('original_language') != 'pt':
            name = name.replace(meta["aka"], '')

        # Se for nacional, usa apenas o título de AKA, apagando o título estrangeiro
        if meta.get('original_language') == 'pt' and meta.get('aka'):
            aka_clean = meta['aka'].replace('AKA', '').strip()
            title = meta.get('title')
            name = name.replace(meta["aka"], '').replace(title, aka_clean).strip()

        cbr_name = name
        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        if meta.get('no_dual', False):
            if meta.get('dual_audio', False):
                cbr_name = cbr_name.replace("Dual-Audio ", '')
        else:
            if meta.get('audio_languages') and not meta.get('is_disc') == "BDMV":
                audio_languages = set(meta['audio_languages'])
                if len(audio_languages) >= 3:
                    audio_tag = ' MULTI'
                elif len(audio_languages) == 2:
                    audio_tag = ' DUAL'
                else:
                    audio_tag = ''
            if audio_tag:
                if meta.get('dual_audio', False):
                    cbr_name = cbr_name.replace("Dual-Audio ", '')
                if '-' in cbr_name:
                    parts = cbr_name.rsplit('-', 1)
                    cbr_name = f"{parts[0]}{audio_tag}-{parts[1]}"
                else:
                    cbr_name += audio_tag

        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                cbr_name = re.sub(f"-{invalid_tag}", "", cbr_name, flags=re.IGNORECASE)
            cbr_name = f"{cbr_name}-NoGroup"

        return cbr_name

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        modq = await self.get_flag(meta, 'modq')
        cat_id = await self.get_cat_id(meta['category'], meta)
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        cbr_name = await self.edit_name(meta)
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
        data = {
            'name': cbr_name,
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
            'mod_queue_opt_in': modq,
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
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    async def search_existing(self, meta, disctype):
        if not meta['is_disc'] == "BDMV":
            if not meta.get('audio_languages') or not meta.get('subtitle_languages'):
                await process_desc_language(meta, desc=None, tracker=self.tracker)
            portuguese_languages = ['Portuguese', 'Português']
            if not any(lang in meta.get('audio_languages', []) for lang in portuguese_languages) and not any(lang in meta.get('subtitle_languages', []) for lang in portuguese_languages):
                if not meta['unattended']:
                    console.print('[bold red]CBR requires at least one Portuguese audio or subtitle track.')
                meta['skipping'] = "CBR"
                return

        dupes = []

        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category'], meta),
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

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if config_flag is not None:
            return 1 if config_flag else 0

        return 1 if meta.get(flag_name, False) else 0
