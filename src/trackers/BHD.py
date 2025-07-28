# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
from difflib import SequenceMatcher
import os
import platform
import bencodepy
import httpx
import re
import cli_ui
import glob
from src.trackers.COMMON import COMMON
from src.console import console
from src.rehostimages import check_hosts


class BHD():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'BHD'
        self.source_flag = 'BHD'
        self.upload_url = 'https://beyond-hd.me/api/upload/'
        self.torrent_url = 'https://beyond-hd.me/details/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = ['Sicario', 'TOMMY', 'x0r', 'nikt0', 'FGT', 'd3g', 'MeGusta', 'YIFY', 'tigole', 'TEKNO3D', 'C4K', 'RARBG', '4K4U', 'EASports', 'ReaLHD', 'Telly', 'AOC', 'WKS', 'SasukeducK']
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "pixhost.to": "pixhost",
            "imgbox.com": "imgbox",
            "beyondhd.co": "bhd",
            "imagebam.com": "bam",
        }

        approved_image_hosts = ['ptpimg', 'imgbox', 'imgbb', 'pixhost', 'bhd', 'bam']
        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=approved_image_hosts)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        source_id = await self.get_source(meta['source'])
        type_id = await self.get_type(meta)
        draft = await self.get_live(meta)
        await self.edit_desc(meta)
        tags = await self.get_tags(meta)
        custom, edition = await self.get_edition(meta, tags)
        bhd_name = await self.edit_name(meta)
        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anon = 0
        else:
            anon = 1

        if meta['bdinfo'] is not None:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8')
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8')

        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        torrent_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        files = {
            'mediainfo': mi_dump,
        }
        open_torrent = None
        if os.path.exists(torrent_file):
            open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb')
            files['file'] = open_torrent.read()
        base_dir = meta['base_dir']
        uuid = meta['uuid']
        specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
        nfo_files = glob.glob(specified_dir_path)
        nfo_file = None
        if nfo_files:
            nfo_file = open(nfo_files[0], 'rb')
        if nfo_file:
            files['nfo_file'] = ("nfo_file.nfo", nfo_file, "text/plain")

        data = {
            'name': bhd_name,
            'category_id': cat_id,
            'type': type_id,
            'source': source_id,
            'imdb_id': meta['imdb'],
            'tmdb_id': meta['tmdb'],
            'description': desc,
            'anon': anon,
            'sd': meta.get('sd', 0),
            'live': draft
            # 'internal' : 0,
            # 'featured' : 0,
            # 'free' : 0,
            # 'double_up' : 0,
            # 'sticky' : 0,
        }
        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1

        if meta.get('tv_pack', 0) == 1:
            data['pack'] = 1
        if meta.get('season', None) == "S00":
            data['special'] = 1
        allowed_regions = ['AUS', 'CAN', 'CEE', 'CHN', 'ESP', 'EUR', 'FRA', 'GBR', 'GER', 'HKG', 'ITA', 'JPN', 'KOR', 'NOR', 'NLD', 'RUS', 'TWN', 'USA']
        if meta.get('region', "") in allowed_regions:
            data['region'] = meta['region']
        if custom is True:
            data['custom_edition'] = edition
        elif edition != "":
            data['edition'] = edition
        if len(tags) > 0:
            data['tags'] = ','.join(tags)
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }

        url = self.upload_url + self.config['TRACKERS'][self.tracker]['api_key'].strip()
        details_link = {}
        if meta['debug'] is False:
            response = requests.post(url=url, files=files, data=data, headers=headers)
            try:
                response = response.json()
                if int(response['status_code']) == 0:
                    console.print(f"[red]{response['status_message']}")
                    if response['status_message'].startswith('Invalid imdb_id'):
                        console.print('[yellow]RETRYING UPLOAD')
                        data['imdb_id'] = 1
                        response = requests.post(url=url, files=files, data=data, headers=headers)
                        response = response.json()
                    elif response['status_message'].startswith('Invalid name value'):
                        console.print(f"[bold yellow]Submitted Name: {bhd_name}")

                if 'status_message' in response:
                    match = re.search(r"https://beyond-hd\.me/torrent/download/.*\.(\d+)\.", response['status_message'])
                    if match:
                        torrent_id = match.group(1)
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id
                        details_link = f"https://beyond-hd.me/details/{torrent_id}"
                    else:
                        console.print("[yellow]No valid details link found in status_message.")

                meta['tracker_status'][self.tracker]['status_message'] = response
            except Exception as e:
                console.print("It may have uploaded, go check")
                console.print(f"Error: {e}")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."

        if details_link:
            try:
                open_torrent.seek(0)
                torrent_data = open_torrent.read()
                torrent = bencodepy.decode(torrent_data)
                torrent[b'comment'] = details_link.encode('utf-8')
                with open(torrent_file, 'wb') as updated_torrent_file:
                    updated_torrent_file.write(bencodepy.encode(torrent))

                console.print(f"Torrent file updated with comment: {details_link}")
            except Exception as e:
                console.print(f"Error while editing the torrent file: {e}")

        if open_torrent is not None:
            open_torrent.close()

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '1')
        return category_id

    async def get_source(self, source):
        sources = {
            "Blu-ray": "Blu-ray",
            "BluRay": "Blu-ray",
            "HDDVD": "HD-DVD",
            "HD DVD": "HD-DVD",
            "WEB": "WEB",
            "Web": "WEB",
            "HDTV": "HDTV",
            "UHDTV": "HDTV",
            "NTSC": "DVD", "NTSC DVD": "DVD",
            "PAL": "DVD", "PAL DVD": "DVD",
        }

        source_id = sources.get(source)
        return source_id

    async def get_type(self, meta):
        if meta['is_disc'] == "BDMV":
            bdinfo = meta['bdinfo']
            bd_sizes = [25, 50, 66, 100]
            for each in bd_sizes:
                if bdinfo['size'] < each:
                    bd_size = each
                    break
            if meta['uhd'] == "UHD" and bd_size != 25:
                type_id = f"UHD {bd_size}"
            else:
                type_id = f"BD {bd_size}"
            if type_id not in ['UHD 100', 'UHD 66', 'UHD 50', 'BD 50', 'BD 25']:
                type_id = "Other"
        elif meta['is_disc'] == "DVD":
            if "DVD5" in meta['dvd_size']:
                type_id = "DVD 5"
            elif "DVD9" in meta['dvd_size']:
                type_id = "DVD 9"
        else:
            if meta['type'] == "REMUX":
                if meta['source'] == "BluRay":
                    type_id = "BD Remux"
                if meta['source'] in ("PAL DVD", "NTSC DVD"):
                    type_id = "DVD Remux"
                if meta['uhd'] == "UHD":
                    type_id = "UHD Remux"
                if meta['source'] == "HDDVD":
                    type_id = "Other"
            else:
                acceptable_res = ["2160p", "1080p", "1080i", "720p", "576p", "576i", "540p", "480p", "Other"]
                if meta['resolution'] in acceptable_res:
                    type_id = meta['resolution']
                else:
                    type_id = "Other"
        return type_id

    async def edit_desc(self, meta):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf-8').read()
        base = base.replace("[user]", "").replace("[/user]", "")
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as desc:
            if meta.get('discs', []) != []:
                discs = meta['discs']
                if discs[0]['type'] == "DVD":
                    desc.write(f"[spoiler=VOB MediaInfo][code]{discs[0]['vob_mi']}[/code][/spoiler]")
                    desc.write("\n")
                if len(discs) >= 2:
                    for each in discs[1:]:
                        if each['type'] == "BDMV":
                            desc.write(f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]")
                            desc.write("\n")
                        elif each['type'] == "DVD":
                            desc.write(f"{each['name']}:\n")
                            desc.write(f"[spoiler={os.path.basename(each['vob'])}][code][{each['vob_mi']}[/code][/spoiler] [spoiler={os.path.basename(each['ifo'])}][code][{each['ifo_mi']}[/code][/spoiler]")
                            desc.write("\n")
                        elif each['type'] == "HDDVD":
                            desc.write(f"{each['name']}:\n")
                            desc.write(f"[spoiler={os.path.basename(each['largest_evo'])}][code][{each['evo_mi']}[/code][/spoiler]\n")
                            desc.write("\n")
            desc.write(base.replace("[img]", "[img width=300]"))
            try:
                # If screensPerRow is set, use that to determine how many screenshots should be on each row. Otherwise, use 2 as default
                screensPerRow = int(self.config['DEFAULT'].get('screens_per_row', 2))
            except Exception:
                screensPerRow = 2
            if meta.get('comparison') and meta.get('comparison_groups'):
                desc.write("[center]")
                comparison_groups = meta.get('comparison_groups', {})
                sorted_group_indices = sorted(comparison_groups.keys(), key=lambda x: int(x))

                comp_sources = []
                for group_idx in sorted_group_indices:
                    group_data = comparison_groups[group_idx]
                    group_name = group_data.get('name', f'Group {group_idx}')
                    comp_sources.append(group_name)

                sources_string = ", ".join(comp_sources)
                desc.write(f"[comparison={sources_string}]\n")

                images_per_group = min([
                    len(comparison_groups[idx].get('urls', []))
                    for idx in sorted_group_indices
                ])

                for img_idx in range(images_per_group):
                    for group_idx in sorted_group_indices:
                        group_data = comparison_groups[group_idx]
                        urls = group_data.get('urls', [])
                        if img_idx < len(urls):
                            img_url = urls[img_idx].get('raw_url', '')
                            if img_url:
                                desc.write(f"{img_url}\n")

                desc.write("[/comparison][/center]\n\n")
            if f'{self.tracker}_images_key' in meta:
                images = meta[f'{self.tracker}_images_key']
            else:
                images = meta['image_list']
            if len(images) > 0:
                desc.write("[align=center]")
                for each in range(len(images[:int(meta['screens'])])):
                    web_url = images[each]['web_url']
                    img_url = images[each]['img_url']
                    if (each == len(images) - 1):
                        desc.write(f"[url={web_url}][img width=350]{img_url}[/img][/url]")
                    elif (each + 1) % screensPerRow == 0:
                        desc.write(f"[url={web_url}][img width=350]{img_url}[/img][/url]\n")
                        desc.write("\n")
                    else:
                        desc.write(f"[url={web_url}][img width=350]{img_url}[/img][/url] ")
                desc.write("[/align]")
            desc.write(self.signature)
            desc.close()
        return

    async def search_existing(self, meta, disctype):
        bhd_name = await self.edit_name(meta)
        if any(phrase in bhd_name.lower() for phrase in (
            "-framestor", "-bhdstudio", "-bmf", "-decibel", "-d-zone", "-hifi",
            "-ncmt", "-tdd", "-flux", "-crfw", "-sonny", "-zr-", "-mkvultra",
            "-rpg", "-w4nk3r", "-irobot", "-beyondhd"
        )):
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                console.print("[bold red]This is an internal BHD release, skipping upload[/bold red]")
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    meta['skipping'] = "BHD"
                    return []
            else:
                meta['skipping'] = "BHD"
                return []
        if meta['sd'] and not (meta['is_disc'] or "REMUX" in meta['type'] or "WEBDL" in meta['type']):
            if not meta['unattended']:
                console.print("[bold red]Modified SD content not allowed at BHD[/bold red]")
            meta['skipping'] = "BHD"
            return []
        if meta['bloated'] is True:
            console.print("[bold red]Non-English dub not allowed at BHD[/bold red]")
            meta['skipping'] = "BHD"
            return []

        dupes = []
        category = meta['category']
        tmdbID = "movie" if category == 'MOVIE' else "tv"
        if category == 'MOVIE':
            category = "Movies"
        elif category == "TV":
            category = "TV"
        if meta['is_disc'] == "DVD":
            type = None
        else:
            type = await self.get_type(meta)

        data = {
            'action': 'search',
            'tmdb_id': f"{tmdbID}/{meta['tmdb']}",
            'categories': category,
            'types': type
        }
        if meta['sd'] == 1:
            data['categories'] = None
            data['types'] = None
        if meta['category'] == 'TV':
            data['search'] = f"{meta.get('season', '')}"

        url = f"https://beyond-hd.me/api/torrents/{self.config['TRACKERS']['BHD']['api_key'].strip()}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, params=data)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status_code') == 1:
                        for each in data['results']:
                            result = {
                                'name': each['name'],
                                'size': each['size']
                            }
                            difference = SequenceMatcher(
                                None,
                                meta['clean_name'].replace('DD+', 'DDP'),
                                result['name']
                            ).ratio()
                            if difference >= 0.05:
                                dupes.append(result)
                    else:
                        console.print(f"[bold red]Failed to search torrents. API Error: {data.get('message', 'Unknown Error')}")
                else:
                    console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 5 seconds")
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            await asyncio.sleep(5)

        return dupes

    def _is_true(self, value):
        """
        Converts a value to a boolean. Returns True for "true", "1", "yes" (case-insensitive), and False otherwise.
        """
        return str(value).strip().lower() in {"true", "1", "yes"}

    async def get_live(self, meta):
        draft_value = self.config['TRACKERS'][self.tracker].get('draft_default', False)
        if isinstance(draft_value, bool):
            draft_bool = draft_value
        else:
            draft_bool = self._is_true(str(draft_value).strip())

        draft_int = 0 if draft_bool or meta.get('draft') else 1

        return draft_int

    async def get_edition(self, meta, tags):
        custom = False
        edition = meta.get('edition', "")
        if "Hybrid" in tags:
            edition = edition.replace('Hybrid', '').strip()
        editions = ['collector', 'cirector', 'extended', 'limited', 'special', 'theatrical', 'uncut', 'unrated']
        for each in editions:
            if each in meta.get('edition'):
                edition = each
            elif edition == "":
                edition = ""
            else:
                custom = True
        return custom, edition

    async def get_tags(self, meta):
        tags = []
        if meta['type'] == "WEBRIP":
            tags.append("WEBRip")
        if meta['type'] == "WEBDL":
            tags.append("WEBDL")
        if meta.get('3D') == "3D":
            tags.append('3D')
        if "Dual-Audio" in meta.get('audio', ""):
            tags.append('DualAudio')
        if "Dubbed" in meta.get('audio', ""):
            tags.append('EnglishDub')
        if "Open Matte" in meta.get('edition', ""):
            tags.append("OpenMatte")
        if meta.get('scene', False) is True:
            tags.append("Scene")
        if meta.get('personalrelease', False) is True:
            tags.append('Personal')
        if "hybrid" in meta.get('edition', "").lower():
            tags.append('Hybrid')
        if meta.get('has_commentary', False) is True:
            tags.append('Commentary')
        if "DV" in meta.get('hdr', ''):
            tags.append('DV')
        if "HDR" in meta.get('hdr', ''):
            if "HDR10+" in meta['hdr']:
                tags.append('HDR10+')
            else:
                tags.append('HDR10')
        if "HLG" in meta.get('hdr', ''):
            tags.append('HLG')
        return tags

    async def edit_name(self, meta):
        name = meta.get('name')
        if meta.get('source', '') in ('PAL DVD', 'NTSC DVD', 'DVD', 'NTSC', 'PAL'):
            audio = meta.get('audio', '')
            audio = ' '.join(audio.split())
            name = name.replace(audio, f"{meta.get('video_codec')} {audio}")
        name = name.replace("DD+", "DDP")
        return name
