# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
from difflib import SequenceMatcher
from str2bool import str2bool
import os
import platform
import hashlib
import bencodepy
import glob
from urllib.parse import urlparse

from src.trackers.COMMON import COMMON
from src.console import console
from src.takescreens import disc_screenshots, dvd_screenshots, screenshots
from src.uploadscreens import upload_screens


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
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = ['Sicario', 'TOMMY', 'x0r', 'nikt0', 'FGT', 'd3g', 'MeGusta', 'YIFY', 'tigole', 'TEKNO3D', 'C4K', 'RARBG', '4K4U', 'EASports', 'ReaLHD', 'Telly', 'AOC', 'WKS', 'SasukeducK']
        pass

    def match_host(self, hostname, approved_hosts):
        for approved_host in approved_hosts:
            if hostname == approved_host or hostname.endswith(f".{approved_host}"):
                return approved_host
        return hostname

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await self.upload_with_retry(meta, common)

    async def upload_with_retry(self, meta, common, img_host_index=1):
        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "pixhost.to": "pixhost",
            "imgbox.com": "imgbox",
            "beyondhd.co": "bhd",
            "imagebam.com": "bam",
        }

        approved_image_hosts = ['ptpimg', 'imgbox', 'imgbb', 'pixhost', 'bhd', 'bam']

        for image in meta['image_list']:
            raw_url = image['raw_url']
            parsed_url = urlparse(raw_url)
            hostname = parsed_url.netloc
            mapped_host = self.match_host(hostname, url_host_mapping.keys())
            mapped_host = url_host_mapping.get(mapped_host, mapped_host)
            if meta['debug']:
                if mapped_host in approved_image_hosts:
                    console.print(f"[green]URL '{raw_url}' is correctly matched to approved host '{mapped_host}'.")
                else:
                    console.print(f"[red]URL '{raw_url}' is not recognized as part of an approved host.")

        if all(
            url_host_mapping.get(
                self.match_host(urlparse(image['raw_url']).netloc, url_host_mapping.keys()),
                self.match_host(urlparse(image['raw_url']).netloc, url_host_mapping.keys()),
            ) in approved_image_hosts
            for image in meta['image_list']
        ):
            console.print("[green]Images are already hosted on an approved image host. Skipping re-upload.")
            image_list = meta['image_list']
        else:
            images_reuploaded = False
            while img_host_index <= len(approved_image_hosts):
                image_list, retry_mode, images_reuploaded = await self.handle_image_upload(meta, img_host_index, approved_image_hosts)

                if retry_mode:
                    console.print(f"[yellow]Switching to the next image host. Current index: {img_host_index}")
                    img_host_index += 1
                    continue

                new_images_key = 'bhd_images_key'
                if image_list is not None:
                    image_list = meta[new_images_key]
                    break

            if image_list is None:
                console.print("[red]All image hosts failed. Please check your configuration.")
                return

        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        source_id = await self.get_source(meta['source'])
        type_id = await self.get_type(meta)
        draft = await self.get_live(meta)
        await self.edit_desc(meta)
        tags = await self.get_tags(meta)
        custom, edition = await self.get_edition(meta, tags)
        bhd_name = await self.edit_name(meta)
        if meta['anon'] == 0 and bool(str2bool(str(self.config['TRACKERS'][self.tracker].get('anon', "False")))) is False:
            anon = 0
        else:
            anon = 1

        if meta['bdinfo'] is not None:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8')
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8')

        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        torrent_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"
        files = {
            'mediainfo': mi_dump,
        }
        if os.path.exists(torrent_file):
            open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent", 'rb')
            files['file'] = open_torrent.read()
            open_torrent.close()

        data = {
            'name': bhd_name,
            'category_id': cat_id,
            'type': type_id,
            'source': source_id,
            'imdb_id': meta['imdb_id'].replace('tt', ''),
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
        if meta.get('region', "") != "":
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
                console.print(response)
            except Exception:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)

    async def handle_image_upload(self, meta, img_host_index=1, approved_image_hosts=None, file=None):
        if approved_image_hosts is None:
            approved_image_hosts = ['ptpimg', 'imgbox', 'imgbb', 'pixhost']

        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "pixhost.to": "pixhost",
            "imgbox.com": "imgbox",
        }

        retry_mode = False
        images_reuploaded = False
        new_images_key = 'bhd_images_key'
        discs = meta.get('discs', [])  # noqa F841
        filelist = meta.get('video', [])
        filename = meta['filename']
        path = meta['path']
        if isinstance(filelist, str):
            filelist = [filelist]

        multi_screens = int(self.config['DEFAULT'].get('screens', 6))
        base_dir = meta['base_dir']
        folder_id = meta['uuid']
        meta[new_images_key] = []

        screenshots_dir = os.path.join(base_dir, 'tmp', folder_id)
        all_screenshots = []

        for i, file in enumerate(filelist):
            filename_pattern = f"{filename}*.png"

            if meta['is_disc'] == "DVD":
                existing_screens = glob.glob(f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['discs'][0]['name']}-*.png")
            else:
                existing_screens = glob.glob(os.path.join(screenshots_dir, filename_pattern))

            if len(existing_screens) < multi_screens:
                if meta.get('debug'):
                    console.print("[yellow]The image host of existing images is not supported.")
                    console.print(f"[yellow]Insufficient screenshots found: generating {multi_screens} screenshots.")
                if meta['is_disc'] == "BDMV":
                    try:
                        disc_screenshots(meta, filename, meta['bdinfo'], folder_id, base_dir, meta.get('vapoursynth', False), [], meta.get('ffdebug', False), multi_screens, True)
                    except Exception as e:
                        print(f"Error during BDMV screenshot capture: {e}")
                elif meta['is_disc'] == "DVD":
                    try:
                        dvd_screenshots(
                            meta, 0, None, True
                        )
                    except Exception as e:
                        print(f"Error during DVD screenshot capture: {e}")
                else:
                    try:
                        screenshots(
                            path, filename, meta['uuid'], base_dir, meta, multi_screens, True, None)
                    except Exception as e:
                        print(f"Error during generic screenshot capture: {e}")

                if meta['is_disc'] == "DVD":
                    existing_screens = glob.glob(f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['discs'][0]['name']}-*.png")
                else:
                    existing_screens = glob.glob(os.path.join(screenshots_dir, filename_pattern))

            all_screenshots.extend(existing_screens)

        if not all_screenshots:
            console.print("[red]No screenshots were generated or found. Please check the screenshot generation process.")
            return [], True, images_reuploaded

        if not meta.get('skip_imghost_upload', False):
            uploaded_images = []
            while True:
                current_img_host_key = f'img_host_{img_host_index}'
                current_img_host = self.config.get('DEFAULT', {}).get(current_img_host_key)

                if not current_img_host:
                    console.print("[red]No more image hosts left to try.")
                    return

                if current_img_host not in approved_image_hosts:
                    console.print(f"[red]Your preferred image host '{current_img_host}' is not supported at BHD, trying next host.")
                    retry_mode = True
                    images_reuploaded = True
                    img_host_index += 1
                    continue
                else:
                    meta['imghost'] = current_img_host
                    console.print(f"[green]Uploading to approved host '{current_img_host}'.")
                    break

            uploaded_images, _ = upload_screens(
                meta, multi_screens, img_host_index, 0, multi_screens,
                all_screenshots, {new_images_key: meta[new_images_key]}, retry_mode
            )

            if uploaded_images:
                meta[new_images_key] = uploaded_images

            if meta['debug']:
                for image in uploaded_images:
                    console.print(f"[debug] Response in upload_image_task: {image['img_url']}, {image['raw_url']}, {image['web_url']}")

            for image in meta.get(new_images_key, []):
                raw_url = image['raw_url']
                parsed_url = urlparse(raw_url)
                hostname = parsed_url.netloc
                mapped_host = self.match_host(hostname, url_host_mapping.keys())
                mapped_host = url_host_mapping.get(mapped_host, mapped_host)

                if mapped_host not in approved_image_hosts:
                    console.print(f"[red]Unsupported image host detected in URL '{raw_url}'. Please use one of the approved image hosts.")
                    return meta[new_images_key], True, images_reuploaded  # Trigger retry_mode if switching hosts

            if all(
                url_host_mapping.get(
                    self.match_host(urlparse(image['raw_url']).netloc, url_host_mapping.keys()),
                    self.match_host(urlparse(image['raw_url']).netloc, url_host_mapping.keys()),
                ) in approved_image_hosts
                for image in meta[new_images_key]
            ):

                return meta[new_images_key], False, images_reuploaded
        else:
            return meta[new_images_key], False, images_reuploaded

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
            if 'bhd_images_key' in meta:
                images = meta['bhd_images_key']
            else:
                images = meta['image_list']
            if len(images) > 0:
                desc.write("[align=center]")
                for each in range(len(images[:int(meta['screens'])])):
                    web_url = images[each]['web_url']
                    img_url = images[each]['img_url']
                    if (each == len(images) - 1):
                        desc.write(f"[url={web_url}][img width=350]{img_url}[/img][/url]")
                    elif (each + 1) % 2 == 0:
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
        if any(phrase in bhd_name.lower() for phrase in ("-framestor", "-bhdstudio", "-bmf", "-decibel", "-d-zone", "-hifi", "-ncmt", "-tdd", "-flux", "-crfw", "-sonny", "-zr-", "-mkvultra", "-rpg", "-w4nk3r", "-irobot", "-beyondhd")):
            console.print("[bold red]This is an internal BHD release, skipping upload[/bold red]")
            meta['skipping'] = "BHD"
            return
        if meta['type'] == "DVDRIP":
            console.print("[bold red]No DVDRIP at BHD, skipping upload[/bold red]")
            meta['skipping'] = "BHD"
            return
        dupes = []
        console.print("[yellow]Searching for existing torrents on BHD...")
        category = meta['category']
        if category == 'MOVIE':
            tmdbID = "movie"
            category = "Movies"
        if category == "TV":
            tmdbID = "tv"
        data = {
            'action': 'search',
            'tmdb_id': f"{tmdbID}/{meta['tmdb']}",
            'categories': category,
            'types': await self.get_type(meta),
        }
        # Search all releases if SD
        if meta['sd'] == 1:
            data['categories'] = None
            data['types'] = None
        if meta['category'] == 'TV':
            if meta.get('tv_pack', 0) == 1:
                data['pack'] = 1
            data['search'] = f"{meta.get('season', '')}{meta.get('episode', '')}"
        url = f"https://beyond-hd.me/api/torrents/{self.config['TRACKERS']['BHD']['api_key'].strip()}"
        try:
            response = requests.post(url=url, data=data)
            response = response.json()
            if response.get('status_code') == 1:
                for each in response['results']:
                    result = each['name']
                    difference = SequenceMatcher(None, meta['clean_name'].replace('DD+', 'DDP'), result).ratio()
                    if difference >= 0.05:
                        dupes.append(result)
            else:
                console.print(f"[yellow]{response.get('status_message')}")
                await asyncio.sleep(5)
        except Exception:
            console.print('[bold red]Unable to search for existing torrents on site. Most likely the site is down.')
            await asyncio.sleep(5)

        return dupes

    async def get_live(self, meta):
        draft = self.config['TRACKERS'][self.tracker]['draft_default'].strip()
        draft = bool(str2bool(str(draft)))  # 0 for send to draft, 1 for live
        if draft:
            draft_int = 0
        else:
            draft_int = 1
        if meta['draft']:
            draft_int = 0
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
        # if meta['type'] == 'WEBDL' and meta.get('has_encode_settings', False) == True:
        #     name = name.replace('H.264', 'x264')
        if meta['category'] == "TV" and meta.get('tv_pack', 0) == 0 and meta.get('episode_title_storage', '').strip() != '' and meta['episode'].strip() != '':
            name = name.replace(meta['episode'], f"{meta['episode']} {meta['episode_title_storage']}", 1)
        return name

    async def search_torrent_page(self, meta, disctype):
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"
        with open(torrent_file_path, 'rb') as open_torrent:
            torrent_data = open_torrent.read()
        torrent = bencodepy.decode(torrent_data)
        info_dict = torrent[b'info']
        bencoded_info = bencodepy.encode(info_dict)
        info_hash = hashlib.sha1(bencoded_info).hexdigest()
        # console.print(f"Info Hash: {info_hash}")

        params = {
            'action': 'search',
            'info_hash': info_hash
        }
        url = f"https://beyond-hd.me/api/torrents/{self.config['TRACKERS']['BHD']['api_key'].strip()}"
        try:
            response = requests.post(url=url, json=params)
            response_data = response.json()
            # console.print(f"[yellow]Response Data: {response_data}")

            if response_data.get('total_results') == 1:
                for each in response_data['results']:
                    details_link = f"https://beyond-hd.me/details/{each['id']}"

                if details_link:
                    with open(torrent_file_path, 'rb') as open_torrent:
                        torrent_data = open_torrent.read()

                    torrent = bencodepy.decode(torrent_data)
                    torrent[b'comment'] = details_link.encode('utf-8')
                    updated_torrent_data = bencodepy.encode(torrent)

                    with open(torrent_file_path, 'wb') as updated_torrent_file:
                        updated_torrent_file.write(updated_torrent_data)

                    return details_link
                else:
                    return None
            else:
                return None

        except requests.exceptions.RequestException as e:
            print(f"An error occurred during the request: {e}")
            return None
