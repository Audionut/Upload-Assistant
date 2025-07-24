# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import os
import re
import platform
import cli_ui
import httpx
from src.trackers.COMMON import COMMON
from src.console import console
from src.rehostimages import check_hosts
from src.languages import parsed_mediainfo, process_desc_language


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
        self.torrent_url = 'https://hawke.uno/torrents/'
        self.id_url = 'https://hawke.uno/api/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = ["4K4U, Bearfish, BiTOR, BONE, D3FiL3R, d3g, DTR, ELiTE, EVO, eztv, EzzRips, FGT, HashMiner, HETeam, HEVCBay, HiQVE, HR-DR, iFT, ION265, iVy, JATT, Joy, LAMA, m3th, MeGusta, MRN, Musafirboy, OEPlus, Pahe.in, PHOCiS, PSA, RARBG, RMTeam, ShieldBearer, SiQ, TBD, Telly, TSP, VXT, WKS, YAWNiX, YIFY, YTS"]
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        huno_name, region_id, distributor_id = await self.get_name(meta, region_id=region_id, distributor_id=distributor_id)
        if (huno_name or region_id) == "SKIPPED":
            meta['tracker_status'][self.tracker]['status_message'] = "data error: huno_missing_data"
            return

        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "pixhost.to": "pixhost",
            "imgbox.com": "imgbox",
            "imagebam.com": "bam",
        }
        approved_image_hosts = ['ptpimg', 'imgbox', 'imgbb', 'pixhost', 'bam']
        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=approved_image_hosts)
        if 'HUNO_images_key' in meta:
            image_list = meta['HUNO_images_key']
        else:
            image_list = meta['image_list']
        await common.unit3d_edit_desc(meta, self.tracker, self.signature, image_list=image_list)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta)
        resolution_id = await self.get_res_id(meta['resolution'])
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
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[HUNO]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[HUNO].torrent", 'rb')
        files = {'torrent': open_torrent}
        data = {
            'name': huno_name,
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
            'stream': await self.is_plex_friendly(meta),
            'sd': meta['sd'],
            'keywords': meta['keywords'],
            # 'season_pack': meta.get('tv_pack', 0),
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
        if meta.get('freeleech', 0) != 0:
            data['free'] = meta.get('freeleech', 0)
        if meta.get('category') == 'TV' and meta.get('tv_pack') == 1:
            data['season_pack'] = 1

        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }
        params = {
            'api_token': tracker_config['api_key'].strip()
        }

        if meta['debug'] is False:
            try:
                response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
                meta['tracker_status'][self.tracker]['status_message'] = response.json()
            except Exception as e:
                meta['tracker_status'][self.tracker]['status_message'] = f" data error - Error uploading torrent: {e}"
                return
            try:
                # adding torrent link to comment of torrent file
                t_id = response.json()['data'].split(".")[1].split("/")[3]
                meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), "https://hawke.uno/torrents/" + t_id)
            except Exception:
                console.print("Error getting torrent ID from response.")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    async def get_audio(self, meta):
        channels = meta.get('channels', "")
        codec = meta.get('audio', "").replace("DD+", "DDP").replace("EX", "").replace("Dual-Audio", "").replace(channels, "")
        dual = "Dual-Audio" in meta.get('audio', "")
        languages = ""

        if dual:
            languages = "Dual"
        else:
            if not meta.get('audio_languages'):
                await process_desc_language(meta, desc=None, tracker=self.tracker)
            if meta.get('audio_languages'):
                languages = meta['audio_languages']
                languages = set(languages)
                if len(languages) > 1:
                    languages = "Dual"
                else:
                    languages = next(iter(languages), "SKIPPED")

        if "zxx" in languages:
            languages = "NONE"
        elif not languages:
            languages = "SKIPPED"

        return f'{codec} {channels} {languages}'

    def get_basename(self, meta):
        path = next(iter(meta['filelist']), meta['path'])
        return os.path.basename(path)

    async def get_name(self, meta, region_id=None, distributor_id=None):
        # Copied from Prep.get_name() then modified to match HUNO's naming convention.
        # It was much easier to build the name from scratch than to alter the existing name.

        region_name = None
        distributor_name = None

        if meta.get('is_disc') == "BDMV":
            common = COMMON(config=self.config)
            if not region_id:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                    region_name = cli_ui.ask_string("ULCX: Region code not found for disc. Please enter it manually (UPPERCASE): ")
                    region_id = await common.unit3d_region_ids(region_name)
                else:
                    region_id = "SKIPPED"
            if not distributor_id:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                    distributor_name = cli_ui.ask_string("ULCX: Distributor code not found for disc. Please enter it manually (UPPERCASE): ")
                    distributor_id = await common.unit3d_distributor_ids(distributor_name)

        basename = self.get_basename(meta)
        if meta.get('hardcoded-subs'):
            hc = "Hardsubbed"
        else:
            hc = ""
        type = meta.get('type', "").upper()
        title = meta.get('title', "")
        year = meta.get('year', "")
        resolution = meta.get('resolution', "")
        audio = await self.get_audio(meta)
        if "SKIPPED" in audio:
            return "SKIPPED", "SKIPPED", "SKIPPED"
        service = meta.get('service', "")
        season = meta.get('season', "")
        if meta.get('tvdb_season_number', ""):
            season_int = meta.get('tvdb_season_number')
            season = f"S{str(season_int).zfill(2)}"
        episode = meta.get('episode', "")
        if meta.get('tvdb_episode_number', ""):
            episode_int = meta.get('tvdb_episode_number')
            episode = f"E{str(episode_int).zfill(2)}"
        repack = meta.get('repack', "")
        if repack.strip():
            repack = f"[{repack}]"
        three_d = meta.get('3D', "")
        tag = meta.get('tag', "").replace("-", "- ")
        if tag == "":
            tag = "- NOGRP"
        source = meta.get('source', "").replace("Blu-ray", "BluRay")
        console.print(f"[bold cyan]Source: {source}")
        if any(x in source.lower() for x in ["pal", "ntsc"]) and type == "ENCODE":
            source = "DVD"
        hdr = meta.get('hdr', "")
        if not hdr.strip():
            hdr = "SDR"
        if distributor_name and distributor_name.upper() in ['CRITERION', 'BFI', 'SHOUT FACTORY']:
            distributor = distributor_name.title()
        else:
            if meta.get('distributor', "") and meta.get('distributor').upper() in ['CRITERION', 'BFI', 'SHOUT FACTORY']:
                distributor = meta.get('distributor').title()
            else:
                distributor = ""
        if region_name:
            region = region_name
        else:
            region = meta.get('region', "")
        video_codec = meta.get('video_codec', "")
        video_encode = meta.get('video_encode', "").replace(".", "")
        if 'x265' in basename and not meta.get('type') == "WEBDL":
            video_encode = video_encode.replace('H', 'x')
        dvd_size = meta.get('dvd_size', "")
        edition = meta.get('edition', "")
        hybrid = 'Hybrid' if meta.get('webdv', "") else ''
        scale = "DS4K" if "DS4K" in basename.upper() else "RM4K" if "RM4K" in basename.upper() else ""
        hfr = "HFR" if meta.get('hfr', '') else ""

        # YAY NAMING FUN
        if meta['category'] == "MOVIE":  # MOVIE SPECIFIC
            if type == "DISC":  # Disk
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} ({year}) {distributor} {edition} {hc} ({resolution} {region} {three_d} {source} {hybrid} {video_codec} {hfr} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'DVD':
                    name = f"{title} ({year}) {distributor} {edition} {hc} ({resolution} {source} {dvd_size} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} ({year}) {distributor} {edition} {hc} ({resolution} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source == "BluRay":  # BluRay Remux
                name = f"{title} ({year}) {edition} ({resolution} {three_d} {source} {hybrid} REMUX {video_codec} {hfr} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
                name = f"{title} ({year}) {edition} {hc} ({resolution} {source} {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "ENCODE":  # Encode
                name = f"{title} ({year}) {edition} {hc} ({resolution} {scale} {source} {hybrid} {video_encode} {hfr} {hdr} {audio} {tag}) {repack}"
            elif type in ("WEBDL", "WEBRIP"):  # WEB
                name = f"{title} ({year}) {edition} {hc} ({resolution} {scale} {service} WEB-DL {hybrid} {video_encode} {hfr} {hdr} {audio} {tag}) {repack}"
            elif type == "HDTV":  # HDTV
                name = f"{title} ({year}) {edition} {hc} ({resolution} HDTV {hybrid} {video_encode} {audio} {tag}) {repack}"
            elif type == "DVDRIP":
                name = f"{title} ({year}) {edition} {hc} ({resolution} {source} {video_encode} {hdr} {audio} {tag}) {repack}"
        elif meta['category'] == "TV":  # TV SPECIFIC
            if type == "DISC":  # Disk
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} ({year}) {season}{episode} {distributor} {edition} {hc} ({resolution} {region} {three_d} {source} {hybrid} {video_codec} {hfr} {hdr} {audio} {tag}) {repack}"
                if meta['is_disc'] == 'DVD':
                    name = f"{title} ({year}) {season}{episode} {distributor} {edition} {hc} ({resolution} {source} {dvd_size} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} ({year}) {season}{episode} {edition} ({resolution} {source} {hybrid} {video_codec} {hdr} {audio} {tag}) {repack}"
            elif type == "REMUX" and source == "BluRay":  # BluRay Remux
                name = f"{title} ({year}) {season}{episode} {edition} ({resolution} {three_d} {source} {hybrid} REMUX {video_codec} {hfr} {hdr} {audio} {tag}) {repack}"  # SOURCE
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
                name = f"{title} ({year}) {season}{episode} {edition} ({resolution} {source} {hybrid} REMUX {video_codec} {hdr} {audio} {tag}) {repack}"  # SOURCE
            elif type == "ENCODE":  # Encode
                name = f"{title} ({year}) {season}{episode} {edition} ({resolution} {scale} {source} {hybrid} {video_encode} {hfr} {hdr} {audio} {tag}) {repack}"  # SOURCE
            elif type in ("WEBDL", "WEBRIP"):  # WEB
                name = f"{title} ({year}) {season}{episode} {edition} ({resolution} {scale} {service} WEB-DL {hybrid} {video_encode} {hfr} {hdr} {audio} {tag}) {repack}"
            elif type == "HDTV":  # HDTV
                name = f"{title} ({year}) {season}{episode} {edition} ({resolution} HDTV {hybrid} {video_encode} {audio} {tag}) {repack}"

        return ' '.join(name.split()).replace(": ", " - "), region_id, distributor_id

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def get_type_id(self, meta):
        type = meta.get('type').upper()
        video_encode = meta.get('video_encode')

        if type == 'REMUX':
            return '2'
        elif type in ('WEBDL', 'WEBRIP'):
            return '15' if 'x265' in video_encode else '3'
        elif type in ('ENCODE', 'HDTV'):
            return '15'
        elif type == 'DISC':
            return '1'
        else:
            return '0'

    async def get_res_id(self, resolution):
        resolution_id = {
            'Other': '10',
            '4320p': '1',
            '2160p': '2',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '540p': '11',
            # no mapping for 540i
            '540i': '11',
            '480p': '8',
            '480i': '9'
        }.get(resolution, '10')
        return resolution_id

    async def is_plex_friendly(self, meta):
        lossy_audio_codecs = ["AAC", "DD", "DD+", "OPUS"]

        if any(l in meta["audio"] for l in lossy_audio_codecs):  # noqa E741
            return 1

        return 0

    async def search_existing(self, meta, disctype):
        if meta['video_codec'] != "HEVC" and meta['type'] in {"ENCODE", "WEBRIP", "DVDRIP", "HDTV"}:
            if not meta['unattended']:
                console.print('[bold red]Only x265/HEVC encodes are allowed at HUNO')
            meta['skipping'] = "HUNO"
            return

        if not meta['is_disc'] and meta['type'] in ['ENCODE', 'WEBRIP', 'DVDRIP', 'HDTV']:
            parsed_info = await parsed_mediainfo(meta)
            for video_track in parsed_info.get('video', []):
                encoding_settings = video_track.get('encoding_settings')
                if not encoding_settings:
                    if not meta['unattended']:
                        console.print("No encoding settings found in MEDIAINFO for HUNO")
                    meta['skipping'] = "HUNO"
                    return []
                if encoding_settings:
                    crf_match = re.search(r'crf[ =:]+([\d.]+)', encoding_settings, re.IGNORECASE)
                    if crf_match:
                        crf_value = float(crf_match.group(1))
                        if crf_value > 22:
                            if not meta['unattended']:
                                console.print(f"CRF value too high: {crf_value} for HUNO")
                            meta['skipping'] = "HUNO"
                            return []
                    else:
                        bit_rate = video_track.get('bit_rate')
                        if bit_rate and "Animation" not in meta.get('genre', ""):
                            bit_rate_num = None
                            # Match number and unit (e.g., 42.4 Mb/s, 42400 kb/s, etc.)
                            match = re.search(r'([\d.]+)\s*([kM]?b/s)', bit_rate.replace(',', ''), re.IGNORECASE)
                            if match:
                                value = float(match.group(1))
                                unit = match.group(2).lower()
                                if unit == 'mb/s':
                                    bit_rate_num = int(value * 1000)
                                elif unit == 'kb/s':
                                    bit_rate_num = int(value)
                                else:
                                    bit_rate_num = int(value)
                            if bit_rate_num is not None and bit_rate_num < 3000:
                                if not meta['unattended']:
                                    console.print(f"Video bitrate too low: {bit_rate_num} kbps for HUNO")
                                meta['skipping'] = "HUNO"
                                return []

        dupes = []

        params = {
            'api_token': self.config['TRACKERS']['HUNO']['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category']),
            'types[]': await self.get_type_id(meta),
            'resolutions[]': await self.get_res_id(meta['resolution']),
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = f"{meta.get('season', '')}"
        if meta.get('edition', "") != "":
            params['name'] + meta['edition']
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    for each in data['data']:
                        attributes = each['attributes']
                        result = {
                            'name': attributes['name'],
                            'size': attributes['size']
                        }
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
