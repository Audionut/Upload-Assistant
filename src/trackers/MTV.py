import asyncio
from src.console import console
import traceback
from torf import Torrent
import httpx
import xml.etree.ElementTree as ET
import os
import cli_ui
import pickle
import re
import pyotp
from pathlib import Path
from str2bool import str2bool
from src.trackers.COMMON import COMMON
from datetime import datetime
import glob
import aiofiles
from urllib.parse import urlparse
from src.torrentcreate import CustomTorrent, torf_cb
from src.takescreens import disc_screenshots, dvd_screenshots, screenshots
from src.uploadscreens import upload_screens


class MTV():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config):
        self.config = config
        self.tracker = 'MTV'
        self.source_flag = 'MTV'
        self.upload_url = 'https://www.morethantv.me/upload.php'
        self.forum_link = 'https://www.morethantv.me/wiki.php?action=article&id=73'
        self.search_url = 'https://www.morethantv.me/api/torznab'
        self.banned_groups = [
            'aXXo', 'BRrip', 'CM8', 'CrEwSaDe', 'DNL', 'FaNGDiNG0', 'FRDS', 'HD2DVD', 'HDTime', 'iPlanet',
            'KiNGDOM', 'Leffe', 'mHD', 'mSD', 'nHD', 'nikt0', 'nSD', 'NhaNc3', 'PRODJi', 'RDN', 'SANTi',
            'STUTTERSHIT', 'TERMiNAL', 'ViSION', 'WAF', 'x0r', 'YIFY', ['EVO', 'WEB-DL Only']
        ]
        pass

    async def file_exists_async(self, file_path):
        try:
            async with aiofiles.open(file_path, 'r'):
                return True
        except FileNotFoundError:
            return False

    def match_host(self, hostname, approved_hosts):
        for approved_host in approved_hosts:
            if hostname == approved_host or hostname.endswith(f".{approved_host}"):
                return approved_host
        return hostname

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/MTV.pkl")
        await self.upload_with_retry(meta, cookiefile, common)

    async def upload_with_retry(self, meta, cookiefile, common, img_host_index=1):
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"
        file_exists = await self.file_exists_async(torrent_file_path)
        if not file_exists:
            meta['not_uploading'] = True
            return

        torrent_filename = "BASE"
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"

        async with aiofiles.open(torrent_path, 'rb') as torrent_file:
            torrent_content = await torrent_file.read()
        # Assuming Torrent.read is a function, you need to call it with the content
        torrent = Torrent.read(torrent_content)

        if torrent.piece_size > 8388608:
            tracker_config = self.config['TRACKERS'].get(self.tracker, {})
            if str(tracker_config.get('skip_if_rehash', 'false')).lower() == "false":
                console.print("[red]Piece size is OVER 8M and does not work on MTV. Generating a new .torrent")

                meta['max_piece_size'] = '8'
                if meta['is_disc']:
                    include = []
                    exclude = []
                else:
                    include = ["*.mkv", "*.mp4", "*.ts"]
                    exclude = ["*.*", "*sample.mkv", "!sample*.*"]

                new_torrent = CustomTorrent(
                    meta=meta,
                    path=Path(meta['path']),
                    trackers=["https://fake.tracker"],
                    source="L4G",
                    private=True,
                    exclude_globs=exclude,  # Ensure this is always a list
                    include_globs=include,  # Ensure this is always a list
                    creation_date=datetime.now(),
                    comment="Created by L4G's Upload Assistant",
                    created_by="L4G's Upload Assistant"
                )

                new_torrent.piece_size = 8 * 1024 * 1024
                new_torrent.validate_piece_size()
                new_torrent.generate(callback=torf_cb, interval=5)
                new_torrent.write(f"{meta['base_dir']}/tmp/{meta['uuid']}/MTV.torrent", overwrite=True)

                torrent_filename = "MTV"

            else:
                console.print("[red]Piece size is OVER 8M and skip_if_rehash enabled. Skipping upload.")
                return
        await common.edit_torrent(meta, self.tracker, self.source_flag, torrent_filename=torrent_filename)

        approved_image_hosts = ['ptpimg', 'imgbox', 'imgbb']
        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "imgbox.com": "imgbox",
        }

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
            image_list = meta['image_list']

        else:
            images_reuploaded = False
            while img_host_index <= len(approved_image_hosts):
                image_list, retry_mode, images_reuploaded = await self.handle_image_upload(meta, img_host_index, approved_image_hosts)

                if retry_mode:
                    console.print(f"[yellow]Switching to the next image host. Current index: {img_host_index}")
                    img_host_index += 1
                    continue

                new_images_key = 'mtv_images_key'
                if image_list is not None:
                    image_list = meta[new_images_key]
                    break

            if image_list is None:
                console.print("[red]All image hosts failed. Please check your configuration.")
                return

        cat_id = await self.get_cat_id(meta)
        resolution_id = await self.get_res_id(meta['resolution'])
        source_id = await self.get_source_id(meta)
        origin_id = await self.get_origin_id(meta)
        des_tags = await self.get_tags(meta)
        await self.edit_desc(meta)
        group_desc = await self.edit_group_desc(meta)
        mtv_name = await self.edit_name(meta)

        anon = 1 if meta['anon'] != 0 or bool(str2bool(str(self.config['TRACKERS'][self.tracker].get('anon', "False")))) else 0

        desc = None
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8') as file:
            desc = await file.read()
        tfile = await aiofiles.open(torrent_file_path, 'rb')

        files = {
            'file_input': (f"{meta['name']}.torrent", tfile)
        }

        data = {
            'image': '',
            'title': mtv_name,
            'category': cat_id,
            'Resolution': resolution_id,
            'source': source_id,
            'origin': origin_id,
            'taglist': des_tags,
            'desc': desc,
            'groupDesc': group_desc,
            'ignoredupes': '1',
            'genre_tags': '---',
            'autocomplete_toggle': 'on',
            'fontfont': '-1',
            'fontsize': '-1',
            'auth': await self.get_auth(cookiefile),
            'anonymous': anon,
            'submit': 'true',
        }

        if not meta['debug']:
            async with httpx.AsyncClient() as client:
                try:
                    # Load cookies from the cookie file
                    with open(cookiefile, 'rb') as cf:
                        client.cookies = pickle.load(cf)
                    response = await client.post(url=self.upload_url, data=data, files=files)
                    if "torrents.php" in response.url:
                        console.print(response.url)
                    elif "authkey.php" in response.url:
                        meta['not_uploading'] = True
                        console.print("[red]No DL link in response, it may have uploaded. Check manually.")
                    else:
                        meta['not_uploading'] = True
                        console.print("[red]Upload Failed. Either you are not logged in...")
                        console.print("[red]You are hitting this site bug: https://www.morethantv.me/forum/thread/3338?")
                        console.print("[red]Or you hit some other error with the torrent upload.")
                except Exception as exc:
                    meta['not_uploading'] = True
                    console.print("[red]It may have uploaded, check manually.")
                    console.print(f"[red]Error: {exc}")
                    traceback.print_exc()
        else:
            # Debug mode: Print the request data
            console.print("[cyan]Request Data:")
            console.print(data)
        return

    async def handle_image_upload(self, meta, img_host_index=1, approved_image_hosts=None, file=None):
        if approved_image_hosts is None:
            approved_image_hosts = ['ptpimg', 'imgbox', 'imgbb']

        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "imgbox.com": "imgbox",
        }

        retry_mode = False
        images_reuploaded = False
        new_images_key = 'mtv_images_key'
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
                    raise Exception("No valid image host found in the config.")

                if current_img_host not in approved_image_hosts:
                    console.print(f"[red]Your preferred image host '{current_img_host}' is not supported at MTV, trying next host.")
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

    async def edit_desc(self, meta):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf-8').read()

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as desc:
            if meta['bdinfo'] is not None:
                mi_dump = None
                bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
            else:
                mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8').read()[:-65].strip()
                bd_dump = None

            if bd_dump:
                desc.write("[mediainfo]" + bd_dump + "[/mediainfo]\n\n")
            elif mi_dump:
                desc.write("[mediainfo]" + mi_dump + "[/mediainfo]\n\n")

            if 'mtv_images_key' in meta:
                images = meta['mtv_images_key']
            else:
                images = meta['image_list']
            if len(images) > 0:
                for image in images:
                    raw_url = image['raw_url']
                    img_url = image['img_url']
                    desc.write(f"[url={raw_url}][img=250]{img_url}[/img][/url]")

            desc.write(f"\n\n{base}")
            desc.close()
        return

    async def edit_group_desc(self, meta):
        description = ""
        if meta['imdb_id'] not in ("0", "", None):
            description += f"https://www.imdb.com/title/tt{meta['imdb_id']}"
        if meta['tmdb'] != 0:
            description += f"\nhttps://www.themoviedb.org/{str(meta['category'].lower())}/{str(meta['tmdb'])}"
        if meta['tvdb_id'] != 0:
            description += f"\nhttps://www.thetvdb.com/?id={str(meta['tvdb_id'])}"
        if meta['tvmaze_id'] != 0:
            description += f"\nhttps://www.tvmaze.com/shows/{str(meta['tvmaze_id'])}"
        if meta['mal_id'] != 0:
            description += f"\nhttps://myanimelist.net/anime/{str(meta['mal_id'])}"

        return description

    async def edit_name(self, meta):
        if meta['scene'] is True:
            if meta.get('scene_name') != "":
                mtv_name = meta.get('scene_name')
            else:
                mtv_name = meta['uuid']
        else:
            mtv_name = meta['name']
            if meta.get('type') in ('WEBDL', 'WEBRIP', 'ENCODE') and "DD" in meta['audio']:
                mtv_name = mtv_name.replace(meta['audio'], meta['audio'].replace(' ', '', 1))
            mtv_name = mtv_name.replace(meta.get('aka', ''), '')
            if meta['category'] == "TV" and meta.get('tv_pack', 0) == 0 and meta.get('episode_title_storage', '').strip() != '' and meta['episode'].strip() != '':
                mtv_name = mtv_name.replace(meta['episode'], f"{meta['episode']} {meta['episode_title_storage']}")
            if 'DD+' in meta.get('audio', '') and 'DDP' in meta['uuid']:
                mtv_name = mtv_name.replace('DD+', 'DDP')
            mtv_name = mtv_name.replace('Dubbed', '').replace('Dual-Audio', 'DUAL')
        if meta['source'].lower().replace('-', '') in mtv_name.replace('-', '').lower():
            if not meta['isdir']:
                # Check if there is a valid file extension, otherwise, skip the split
                if '.' in mtv_name and mtv_name.split('.')[-1].isalpha() and len(mtv_name.split('.')[-1]) <= 4:
                    mtv_name = os.path.splitext(mtv_name)[0]
        # Add -NoGrp if missing tag
        if meta['tag'] == "":
            mtv_name = f"{mtv_name}-NoGrp"
        mtv_name = ' '.join(mtv_name.split())
        mtv_name = re.sub(r"[^0-9a-zA-ZÀ-ÿ. &+'\-\[\]]+", "", mtv_name)
        mtv_name = mtv_name.replace(' ', '.').replace('..', '.')
        console.print(f"[yellow]Sent this name: {mtv_name}[/yellow]")
        return mtv_name

    async def get_res_id(self, resolution):
        resolution_id = {
            '8640p': '0',
            '4320p': '4000',
            '2160p': '2160',
            '1440p': '1440',
            '1080p': '1080',
            '1080i': '1080',
            '720p': '720',
            '576p': '0',
            '576i': '0',
            '480p': '480',
            '480i': '480'
        }.get(resolution, '10')
        return resolution_id

    async def get_cat_id(self, meta):
        if meta['category'] == "MOVIE":
            if meta['sd'] == 1:
                return 2
            else:
                return 1
        if meta['category'] == "TV":
            if meta['tv_pack'] == 1:
                if meta['sd'] == 1:
                    return 6
                else:
                    return 5
            else:
                if meta['sd'] == 1:
                    return 4
                else:
                    return 3

    async def get_source_id(self, meta):
        if meta['is_disc'] == 'DVD':
            return '1'
        elif meta['is_disc'] == 'BDMV' or meta['type'] == "REMUX":
            return '7'
        else:
            type_id = {
                'DISC': '1',
                'WEBDL': '9',
                'WEBRIP': '10',
                'HDTV': '1',
                'SDTV': '2',
                'TVRIP': '3',
                'DVD': '4',
                'DVDRIP': '5',
                'BDRIP': '8',
                'VHS': '6',
                'MIXED': '11',
                'Unknown': '12',
                'ENCODE': '7'
            }.get(meta['type'], '0')
        return type_id

    async def get_origin_id(self, meta):
        if meta['personalrelease']:
            return '4'
        elif meta['scene']:
            return '2'
        # returning P2P
        else:
            return '3'

    async def get_tags(self, meta):
        tags = []
        # Genres
        # MTV takes issue with some of the pulled TMDB tags, and I'm not hand checking and attempting
        # to regex however many tags need changing, so they're just geting skipped
        # tags.extend([x.strip(', ').lower().replace(' ', '.') for x in meta['genres'].split(',')])
        # Resolution
        tags.append(meta['resolution'].lower())
        if meta['sd'] == 1:
            tags.append('sd')
        elif meta['resolution'] in ['2160p', '4320p']:
            tags.append('uhd')
        else:
            tags.append('hd')
        # Streaming Service
        # disney+ should be disneyplus, assume every other service is same.
        # If I'm wrong, then they can either allowing editing tags or service will just get skipped also
        if str(meta['service_longname']) != "":
            service_name = meta['service_longname'].lower().replace(' ', '.')
            service_name = service_name.replace('+', 'plus')  # Replace '+' with 'plus'
            tags.append(f"{service_name}.source")
        # Release Type/Source
        for each in ['remux', 'WEB.DL', 'WEBRip', 'HDTV', 'BluRay', 'DVD', 'HDDVD']:
            if (each.lower().replace('.', '') in meta['type'].lower()) or (each.lower().replace('-', '') in meta['source']):
                tags.append(each)
        # series tags
        if meta['category'] == "TV":
            if meta.get('tv_pack', 0) == 0:
                # Episodes
                if meta['sd'] == 1:
                    tags.extend(['sd.episode'])
                else:
                    tags.extend(['hd.episode'])
            else:
                # Seasons
                if meta['sd'] == 1:
                    tags.append('sd.season')
                else:
                    tags.append('hd.season')

        # movie tags
        if meta['category'] == 'MOVIE':
            if meta['sd'] == 1:
                tags.append('sd.movie')
            else:
                tags.append('hd.movie')

        # Audio tags
        audio_tag = ""
        for each in ['dd', 'ddp', 'aac', 'truehd', 'mp3', 'mp2', 'dts', 'dts.hd', 'dts.x']:
            if each in meta['audio'].replace('+', 'p').replace('-', '.').replace(':', '.').replace(' ', '.').lower():
                audio_tag = f'{each}.audio'
        tags.append(audio_tag)
        if 'atmos' in meta['audio'].lower():
            tags.append('atmos.audio')

        # Video tags
        tags.append(meta.get('video_codec').replace('AVC', 'h264').replace('HEVC', 'h265').replace('-', ''))

        # Group Tags
        if meta['tag'] != "":
            tags.append(f"{meta['tag'][1:].replace(' ', '.')}.release")
        else:
            tags.append('NOGRP.release')

        # Scene/P2P
        if meta['scene']:
            tags.append('scene.group.release')
        else:
            tags.append('p2p.group.release')

        # Has subtitles
        if meta.get('is_disc', '') != "BDMV":
            if any(track.get('@type', '') == "Text" for track in meta['mediainfo']['media']['track']):
                tags.append('subtitles')
        else:
            if len(meta['bdinfo']['subtitles']) >= 1:
                tags.append('subtitles')

        tags = ' '.join(tags)
        return tags

    async def validate_credentials(self, meta):
        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/MTV.pkl")
        if not os.path.exists(cookiefile):
            await self.login(cookiefile)
        vcookie = await self.validate_cookies(meta, cookiefile)
        if vcookie is not True:
            console.print('[red]Failed to validate cookies. Please confirm that the site is up and your username and password is valid.')
            recreate = cli_ui.ask_yes_no("Log in again and create new session?")
            if recreate is True:
                if os.path.exists(cookiefile):
                    os.remove(cookiefile)
                await self.login(cookiefile)
                vcookie = await self.validate_cookies(meta, cookiefile)
                return vcookie
            else:
                return False
        vapi = await self.validate_api()
        if vapi is not True:
            console.print('[red]Failed to validate API. Please confirm that the site is up and your API key is valid.')
        return True

    async def validate_api(self):
        url = self.search_url
        params = {
            'apikey': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                if not response.is_success:
                    if "unauthorized api key" in response.text.lower():
                        console.print("[red]Invalid API Key")
                    return False
                return True
        except Exception as e:
            console.print(f"[red]An error occurred: {e}")
            return False

    async def validate_cookies(self, meta, cookiefile):
        url = "https://www.morethantv.me/index.php"
        if os.path.exists(cookiefile):
            async with httpx.AsyncClient() as client:
                # Load cookies from the file
                with open(cookiefile, 'rb') as cf:
                    cookies = pickle.load(cf)
                client.cookies.update(cookies)

                # Perform the GET request
                response = await client.get(url)

                if meta['debug']:
                    console.log('[cyan]Validate Cookies:')
                    console.log(client.cookies.jar)  # For inspecting cookies in httpx
                    console.log(response.url)

                # Check for "Logout" in the response text
                if "Logout" in response.text:
                    return True
                else:
                    return False
        else:
            return False

    async def get_auth(self, cookiefile):
        url = "https://www.morethantv.me/index.php"
        if os.path.exists(cookiefile):
            async with httpx.AsyncClient() as client:
                # Load cookies from the file
                with open(cookiefile, 'rb') as cf:
                    cookies = pickle.load(cf)
                client.cookies.update(cookies)

                # Perform the GET request
                response = await client.get(url)

                # Extract `authkey` from the response text
                auth = response.text.rsplit('authkey=', 1)[1][:32]
                return auth

    async def login(self, cookiefile):
        async with httpx.AsyncClient() as client:
            login_url = 'https://www.morethantv.me/login'
            twofactor_url = 'https://www.morethantv.me/twofactor/login'

            # Initial payload
            payload = {
                'username': self.config['TRACKERS'][self.tracker].get('username'),
                'password': self.config['TRACKERS'][self.tracker].get('password'),
                'keeploggedin': 1,
                'cinfo': '1920|1080|24|0',
                'submit': 'login',
                'iplocked': 1,
            }

            # Fetch login page to get the token
            res = await client.get(login_url)
            token = res.text.rsplit('name="token" value="', 1)[1][:48]
            payload['token'] = token

            # Submit login form
            resp = await client.post(login_url, data=payload)

            # Handle 2FA
            if resp.url.endswith('twofactor/login'):
                otp_uri = self.config['TRACKERS'][self.tracker].get('otp_uri')
                if otp_uri:
                    mfa_code = pyotp.parse_uri(otp_uri).now()
                else:
                    mfa_code = console.input('[yellow]MTV 2FA Code: ')

                two_factor_payload = {
                    'token': resp.text.rsplit('name="token" value="', 1)[1][:48],
                    'code': mfa_code,
                    'submit': 'login',
                }
                resp = await client.post(twofactor_url, data=two_factor_payload)

            # Check if logged in
            if 'authkey=' in resp.text:
                console.print('[green]Successfully logged in to MTV')
                # Save cookies to file
                with open(cookiefile, 'wb') as cf:
                    pickle.dump(client.cookies.jar, cf)
            else:
                console.print('[bold red]Something went wrong while trying to log into MTV')
                await asyncio.sleep(1)
                console.print(resp.url)
        return

    async def search_existing(self, meta, disctype):
        dupes = []
        console.print("[yellow]Searching for existing torrents on MTV...")

        # Build request parameters
        params = {
            't': 'search',
            'apikey': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'q': ""
        }

        if meta['imdb_id'] not in ("0", "", None):
            params['imdbid'] = "tt" + meta['imdb_id']
        elif meta['tmdb'] != "0":
            params['tmdbid'] = meta['tmdb']
        elif meta['tvdb_id'] != 0:
            params['tvdbid'] = meta['tvdb_id']
        else:
            params['q'] = meta['title'].replace(': ', ' ').replace('’', '').replace("'", '')

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)

                if response.status_code == 200 and response.text:
                    # Parse XML response
                    try:
                        response_xml = ET.fromstring(response.text)
                        for each in response_xml.find('channel').findall('item'):
                            result = each.find('title').text
                            dupes.append(result)
                    except ET.ParseError:
                        console.print("[red]Failed to parse XML response from MTV API")
                else:
                    # Handle potential error messages
                    if response.status_code != 200:
                        console.print(f"[red]HTTP request failed. Status: {response.status_code}")
                    elif 'status_message' in response.json():
                        console.print(f"[yellow]{response.json().get('status_message')}")
                        await asyncio.sleep(5)
                    else:
                        console.print("[red]Site Seems to be down or not responding to API")
        except httpx.TimeoutException:
            console.print("[red]Request timed out after 5 seconds")
        except httpx.RequestError as e:
            console.print(f"[red]Unable to search for existing torrents: {e}")
        except Exception:
            console.print("[red]Unable to search for existing torrents on site. Most likely the site is down.")
            dupes.append("FAILED SEARCH")
            print(traceback.print_exc())
            await asyncio.sleep(5)

        return dupes
