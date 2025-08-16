# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import platform
import os
import glob
import httpx

from src.trackers.COMMON import COMMON
from src.console import console


class BLU():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'BLU'
        self.source_flag = 'BLU'
        self.search_url = 'https://blutopia.cc/api/torrents/filter'
        self.torrent_url = 'https://blutopia.cc/torrents/'
        self.id_url = 'https://blutopia.cc/api/torrents/'
        self.upload_url = 'https://blutopia.cc/api/torrents/upload'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionuts Upload Assistant[/url][/center]"
        self.banned_groups = [
            '[Oj]', '3LTON', '4yEo', 'ADE', 'AFG', 'AniHLS', 'AnimeRG', 'AniURL', 'AROMA', 'aXXo', 'Brrip', 'CHD', 'CM8', 'CrEwSaDe', 'd3g', 'DeadFish', 'DNL', 'ELiTE', 'eSc', 'FaNGDiNG0', 'FGT', 'Flights',
            'FRDS', 'FUM', 'HAiKU', 'HD2DVD', 'HDS', 'HDTime', 'Hi10', 'ION10', 'iPlanet', 'JIVE', 'KiNGDOM', 'Leffe', 'LEGi0N', 'LOAD', 'MeGusta', 'mHD', 'mSD', 'NhaNc3', 'nHD', 'nikt0', 'NOIVTC', 'OFT',
            'nSD', 'PiRaTeS', 'playBD', 'PlaySD', 'playXD', 'PRODJi', 'RAPiDCOWS', 'RARBG', 'RetroPeeps', 'RDN', 'REsuRRecTioN', 'RMTeam', 'SANTi', 'SicFoI', 'SPASM', 'SPDVD', 'STUTTERSHIT', 'Telly', 'TM',
            'TRiToN', 'UPiNSMOKE', 'URANiME', 'WAF', 'x0r', 'xRed', 'XS', 'YIFY', 'ZKBL', 'ZmN', 'ZMNT', 'AOC',
            ['EVO', 'Raw Content Only'], ['TERMiNAL', 'Raw Content Only'], ['ViSION', 'Note the capitalization and characters used'], ['CMRG', 'Raw Content Only']
        ]

        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        blu_name = await self.edit_name(meta)
        desc_header = ""
        if meta.get('webdv', False):
            blu_name, desc_header = await self.derived_dv_layer(meta)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await common.unit3d_edit_desc(meta, self.tracker, self.signature, comparison=True, desc_header=desc_header)
        cat_id = await self.get_cat_id(meta['category'], meta.get('edition', ''))
        type_id = await self.get_type_id(meta['type'])
        resolution_id = await self.get_res_id(meta['resolution'])
        modq = await self.get_flag(meta, 'modq')
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
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[BLU]DESCRIPTION.txt", 'r', encoding='utf-8').read()

        base_dir = meta['base_dir']
        uuid = meta['uuid']
        specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
        nfo_files = glob.glob(specified_dir_path)
        nfo_file = None
        if nfo_files:
            nfo_file = open(nfo_files[0], 'rb')

        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[BLU].torrent", 'rb')
        files = {'torrent': ("placeholder.torrent", open_torrent, "application/x-bittorrent")}

        if nfo_file:
            files['nfo'] = ("nfo_file.nfo", nfo_file, "text/plain")

        data = {
            'name': blu_name,
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
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), "https://blutopia.cc/torrents/" + t_id)
            except Exception:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    async def edit_name(self, meta):
        blu_name = meta['name']
        if meta['category'] == 'TV' and meta.get('episode_title', "") != "":
            blu_name = blu_name.replace(f"{meta['episode_title']} {meta['resolution']}", f"{meta['resolution']}", 1)
        imdb_name = meta.get('imdb_info', {}).get('title', "")
        imdb_year = str(meta.get('imdb_info', {}).get('year', ""))
        year = str(meta.get('year', ""))
        blu_name = blu_name.replace(f"{meta['title']}", imdb_name, 1)
        if not meta.get('category') == "TV":
            blu_name = blu_name.replace(f"{year}", imdb_year, 1)
        return blu_name

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if config_flag is not None:
            return 1 if config_flag else 0

        return 1 if meta.get(flag_name, False) else 0

    async def get_cat_id(self, category_name, edition):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'FANRES': '3'
        }.get(category_name, '0')
        if category_name == 'MOVIE' and 'FANRES' in edition:
            category_id = '3'
        return category_id

    async def get_type_id(self, type):
        type_id = {
            'DISC': '1',
            'REMUX': '3',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '12'
        }.get(type, '0')
        return type_id

    async def get_res_id(self, resolution):
        resolution_id = {
            '8640p': '10',
            '4320p': '11',
            '2160p': '1',
            '1440p': '2',
            '1080p': '2',
            '1080i': '3',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(resolution, '10')
        return resolution_id

    async def derived_dv_layer(self, meta):
        name = meta['name']
        desc_header = ""
        # Exit if not DV + HDR
        if not all([x in meta['hdr'] for x in ['HDR', 'DV']]):
            return name, desc_header
        import cli_ui
        console.print("[bold yellow]Generating the required description addition for Derived DV Layers. Please respond appropriately.")
        ask_comp = True
        if meta['type'] == "WEBDL":
            if cli_ui.ask_yes_no("Is the DV Layer sourced from the same service as the video?"):
                ask_comp = False
                desc_header = "[code]This release contains a derived Dolby Vision profile 8 layer. Comparisons not required as DV and HDR are from same provider.[/code]"

        if ask_comp:
            while desc_header == "":
                desc_input = cli_ui.ask_string("Please provide comparisons between HDR masters. (link or bbcode)", default="")
                desc_header = f"[code]This release contains a derived Dolby Vision profile 8 layer. Comparisons between HDR masters: {desc_input}[/code]"

        if "hybrid" not in name.lower():
            if "REPACK" in name:
                name = name.replace('REPACK', 'Hybrid REPACK')
            else:
                name = name.replace(meta['resolution'], f"Hybrid {meta['resolution']}")
        return name, desc_header

    async def search_existing(self, meta, disctype):
        dupes = []
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category'], meta.get('edition', '')),
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
