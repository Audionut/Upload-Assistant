# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
from difflib import SequenceMatcher
from str2bool import str2bool
import os
import re
import platform

from src.trackers.COMMON import COMMON
from src.console import console

class HUNO():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'HUNO'
        self.source_flag = 'HUNO'
        self.search_url = 'https://hawke.uno/api/torrents/filter'
        self.upload_url = 'https://hawke.uno/api/torrents/upload'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by L4G's Upload Assistant[/url][/center]"
        self.banned_groups = ["4K4U, Bearfish, BiTOR, BONE, D3FiL3R, d3g, DTR, ELiTE, EVO, eztv, EzzRips, FGT, HashMiner, HETeam, HEVCBay, HiQVE, HR-DR, iFT, ION265, iVy, JATT, Joy, LAMA, m3th, MeGusta, MRN, Musafirboy, OEPlus, Pahe.in, PHOCiS, PSA, RARBG, RMTeam, ShieldBearer, SiQ, TBD, Telly, TSP, VXT, WKS, YAWNiX, YIFY, YTS"]
        pass


    async def upload(self, meta):
        common = COMMON(config=self.config)
        await common.unit3d_edit_desc(meta, self.tracker, self.signature)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta)
        resolution_id = await self.get_res_id(meta['resolution'])
        if meta['anon'] == 0 and bool(str2bool(self.config['TRACKERS']['HUNO'].get('anon', "False"))) == False:
            anon = 0
        else:
            anon = 1

        # adding logic to check if its an encode or webrip and not HEVC as only HEVC encodes and webrips are allowed
        if meta['video_codec'] != "HEVC" and (meta['type'] == "ENCODE" or meta['type'] == "WEBRIP"):
            console.print(f'[bold red]Only x265/HEVC encodes are allowed')
            return

        if meta['bdinfo'] != None:
            mi_dump = None
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
            bd_dump = None
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[HUNO]DESCRIPTION.txt", 'r').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[HUNO]{meta['clean_name']}.torrent", 'rb')
        files = {'torrent': open_torrent}
        data = {
            'name' : await self.get_name(meta),
            'description' : desc,
            'mediainfo' : mi_dump,
            'bdinfo' : bd_dump,
            'category_id' : cat_id,
            'type_id' : type_id,
            'resolution_id' : resolution_id,
            'tmdb' : meta['tmdb'],
            'imdb' : meta['imdb_id'].replace('tt', ''),
            'tvdb' : meta['tvdb_id'],
            'mal' : meta['mal_id'],
            'igdb' : 0,
            'anonymous' : anon,
            'stream' : await self.is_plex_friendly(meta),
            'sd' : meta['sd'],
            'keywords' : meta['keywords'],
            'season_pack': meta.get('tv_pack', 0),
            # 'featured' : 0,
            # 'free' : 0,
            # 'double_up' : 0,
            # 'sticky' : 0,
        }

        tracker_config = self.config['TRACKERS'][self.tracker]

        if 'internal' in tracker_config:
            if tracker_config['internal'] and meta['tag'] and meta['tag'][1:] in tracker_config.get('internal_groups', []):
                data['internal'] = 1
            else:
                data['internal'] = 0

        headers = {
            'User-Agent': f'Upload Assistant/2.1 ({platform.system()} {platform.release()})'
        }
        params = {
            'api_token': tracker_config['api_key'].strip()
        }

        if meta['debug'] == False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
            try:
                console.print(response.json())
                # adding torrent link to comment of torrent file
                t_id = response.json()['data'].split(".")[1].split("/")[3]
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), "https://hawke.uno/torrents/" + t_id)
            except:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print(f"[cyan]Request Data:")
            console.print(data)
        open_torrent.close()

    def get_audio(self, meta):
        channels = meta.get('channels', "")
        codec = meta.get('audio', "").replace("DD+", "DDP").replace("EX", "").replace("Dual-Audio", "").replace(channels, "")
        dual = "Dual-Audio" in meta.get('audio', "")
        language = ""

        if dual:
            language = "DUAL"
        elif 'mediainfo' in meta:
            language = next(x for x in meta["mediainfo"]["media"]["track"] if x["@type"] == "Audio").get('Language_String', "English")
            language = re.sub(r'\(.+\)', '', language)

        return f'{codec} {channels} {language}'
    
    def get_basename(self, meta):
        path = next(iter(meta['filelist']), meta['path'])
        return os.path.basename(path)

    async def get_name(self, meta):
        # Copied from Prep.get_name() then modified to match HUNO's naming convention.
        # It was much easier to build the name from scratch than to alter the existing name.

        basename = self.get_basename(meta)
        type = meta.get('type', "")
        title = meta.get('title',"")
        alt_title = meta.get('aka', "")
        year = meta.get('year', "")
        resolution = meta.get('resolution', "")
        audio = self.get_audio(meta)
        service = meta.get('service', "")
        season = meta.get('season', "")
        episode = meta.get('episode', "")
        repack = meta.get('repack', "")
        if repack.strip():
            repack = f"[{repack}]"
        three_d = meta.get('3D', "")
        tag = meta.get('tag', "").replace("-", "- ")
        if tag == "":
            tag = "- NOGRP"
        source = meta.get('source', "")
        uhd = meta.get('uhd', "")
        hdr = meta.get('hdr', "")
        if not hdr.strip():
            hdr = "SDR"
        distributor = meta.get('distributor', "")
        video_codec = meta.get('video_codec', "")
        video_encode = meta.get('video_encode', "").replace(".", "")
        if 'x265' in basename:
            video_encode = video_encode.replace('H', 'x')
        region = meta.get('region', "")
        dvd_size = meta.get('dvd_size', "")
        edition = meta.get('edition', "")
        hybrid = "Hybrid" if "HYBRID" in basename.upper() else ""
        search_year = meta.get('search_year', "")
        if not str(search_year).strip():
            search_year = year
        scale = "DS4K" if "DS4K" in basename.upper() else "RM4K" if "RM4K" in basename.upper() else ""

        #YAY NAMING FUN
        if meta['category'] == "MOVIE": #MOVIE SPECIFIC
            if type == "DISC": #Disk
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} ({year}) {three_d} {edition} ({resolution} {region} {uhd} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'DVD':
                    name = f"{title} ({year}) {edition} ({resolution} {dvd_size} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} ({year}) {edition} ({resolution} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source == "BluRay": #BluRay Remux
                name = f"{title} ({year}) {three_d} {edition} ({resolution} {uhd} {source} {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD"): #DVD Remux
                name = f"{title} ({year}) {edition} (DVD {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "ENCODE": #Encode
                name = f"{title} ({year}) {edition} ({resolution} {scale} {uhd} {source} {hybrid} {video_encode} {hdr} {audio} {tag}) {repack}"
            elif type in ("WEBDL", "WEBRIP"): #WEB
                name = f"{title} ({year}) {edition} ({resolution} {scale} {uhd} {service} WEB-DL {hybrid} {video_encode} {hdr} {audio} {tag}) {repack}"
            elif type == "HDTV": #HDTV
                name = f"{title} ({year}) {edition} ({resolution} HDTV {hybrid} {video_encode} {audio} {tag}) {repack}"
        elif meta['category'] == "TV": #TV SPECIFIC
            if type == "DISC": #Disk
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} ({search_year}) {season}{episode} {three_d} {edition} ({resolution} {region} {uhd} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                if meta['is_disc'] == 'DVD':
                    name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} {dvd_size} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source == "BluRay": #BluRay Remux
                name = f"{title} ({search_year}) {season}{episode} {three_d} {edition} ({resolution} {uhd} {source} {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}" #SOURCE
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD"): #DVD Remux
                name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} DVD {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}" #SOURCE
            elif type == "ENCODE": #Encode
                name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} {scale} {uhd} {source} {hybrid} {video_encode} {hdr} {audio} {tag}) {repack}" #SOURCE
            elif type in ("WEBDL", "WEBRIP"): #WEB
                name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} {scale} {uhd} {service} WEB-DL {hybrid} {video_encode} {hdr} {audio} {tag}) {repack}"
            elif type == "HDTV": #HDTV
                name = f"{title} ({search_year}) {season}{episode} {edition} ({resolution} HDTV {hybrid} {video_encode} {audio} {tag}) {repack}"

        return ' '.join(name.split()).replace(": ", " - ")


    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            }.get(category_name, '0')
        return category_id


    async def get_type_id(self, meta):
        basename = self.get_basename(meta)
        type = meta['type']

        if type == 'REMUX':
            return '2'
        elif type in ('WEBDL', 'WEBRIP'):
            return '15' if 'x265' in basename else '3'
        elif type in ('ENCODE', 'HDTV'):
            return '15'
        elif type == 'DISC':
            return '1'
        else:
            return '0'


    async def get_res_id(self, resolution):
        resolution_id = {
            'Other':'10',
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i':'4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
            }.get(resolution, '10')
        return resolution_id


    async def is_plex_friendly(self, meta):
        lossy_audio_codecs = ["AAC", "DD", "DD+", "OPUS"]

        if any(l in meta["audio"] for l in lossy_audio_codecs):
            return 1

        return 0


    async def search_existing(self, meta):
        dupes = []
        console.print("[yellow]Searching for existing torrents on site...")

        params = {
            'api_token' : self.config['TRACKERS']['HUNO']['api_key'].strip(),
            'tmdbId' : meta['tmdb'],
            'categories[]' : await self.get_cat_id(meta['category']),
            'types[]' : await self.get_type_id(meta),
            'resolutions[]' : await self.get_res_id(meta['resolution']),
            'name' : ""
        }
        if meta['category'] == 'TV':
            params['name'] = f"{meta.get('season', '')}{meta.get('episode', '')}"
        if meta.get('edition', "") != "":
            params['name'] + meta['edition']
        try:
            response = requests.get(url=self.search_url, params=params)
            response = response.json()
            for each in response['data']:
                result = [each][0]['attributes']['name']
                # difference = SequenceMatcher(None, meta['clean_name'], result).ratio()
                # if difference >= 0.05:
                dupes.append(result)
        except:
            console.print('[bold red]Unable to search for existing torrents on site. Either the site is down or your API key is incorrect')
            await asyncio.sleep(5)

        return dupes
