import requests
import asyncio
from src.console import console
import traceback
from torf import Torrent
import xml.etree.ElementTree
import os
import cli_ui
import pickle
import re
from pathlib import Path
from str2bool import str2bool
from src.trackers.COMMON import COMMON
from datetime import datetime


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

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/MTV.pkl")

        # Initiate the upload with retry logic
        await self.upload_with_retry(meta, cookiefile, common)

    async def upload_with_retry(self, meta, cookiefile, common, img_host_index=1):
        approved_image_hosts = ['ptpimg', 'imgbox']

        # Check if the images are already hosted on an approved image host
        if all(any(host in image['raw_url'] for host in approved_image_hosts) for image in meta['image_list']):
            console.print("[green]Images are already hosted on an approved image host. Skipping re-upload.")
            image_list = meta['image_list']  # Use the existing images

        else:
            # Proceed with the retry logic if images are not hosted on an approved image host
            while img_host_index <= len(approved_image_hosts):
                # Call handle_image_upload and pass the updated meta with the current image host index
                image_list, retry_mode = await self.handle_image_upload(meta, img_host_index, approved_image_hosts)

                # If retry_mode is True, switch to the next host
                if retry_mode:
                    console.print(f"[yellow]Switching to the next image host. Current index: {img_host_index}")
                    img_host_index += 1
                    continue

                # If we successfully uploaded images, break out of the loop
                if image_list is not None:
                    break

            if image_list is None:
                console.print("[red]All image hosts failed. Please check your configuration.")
                return

        # Proceed with the rest of the upload process
        torrent_filename = "BASE"
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"
        torrent = Torrent.read(torrent_path)

        if torrent.piece_size > 8388608:  # 8 MiB in bytes
            console.print("[red]Piece size is OVER 8M and does not work on MTV. Generating a new .torrent")

            # Override the max_piece_size to 8 MiB
            meta['max_piece_size'] = '8'  # 8 MiB, to ensure the new torrent adheres to this limit

            # Determine include and exclude patterns based on whether it's a disc or not
            if meta['is_disc']:
                include = []  # Adjust as needed for disc-specific inclusions, make sure it's a list
                exclude = []  # Adjust as needed for disc-specific exclusions, make sure it's a list
            else:
                include = ["*.mkv", "*.mp4", "*.ts"]
                exclude = ["*.*", "*sample.mkv", "!sample*.*"]

            # Create a new torrent with piece size explicitly set to 8 MiB
            from src.prep import Prep
            prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=self.config)
            new_torrent = prep.CustomTorrent(
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

            # Validate and write the new torrent
            new_torrent.validate_piece_size()
            new_torrent.generate(callback=prep.torf_cb, interval=5)
            new_torrent.write(f"{meta['base_dir']}/tmp/{meta['uuid']}/MTV.torrent", overwrite=True)

            torrent_filename = "MTV"

        # Validate session and re-login if necessary before proceeding with upload
        vcookie = await self.validate_cookies(meta, cookiefile)
        if not vcookie:
            console.print("[yellow]Session expired or invalid. Trying to log in.")
            await self.login(cookiefile)
            vcookie = await self.validate_cookies(meta, cookiefile)
            if not vcookie:
                console.print("[red]Re-login failed. Cannot proceed with the upload.")
                return

        await common.edit_torrent(meta, self.tracker, self.source_flag, torrent_filename=torrent_filename)

        cat_id = await self.get_cat_id(meta)
        resolution_id = await self.get_res_id(meta['resolution'])
        source_id = await self.get_source_id(meta)
        origin_id = await self.get_origin_id(meta)
        des_tags = await self.get_tags(meta)

        # Edit description and other details
        await self.edit_desc(meta)
        group_desc = await self.edit_group_desc(meta)
        mtv_name = await self.edit_name(meta)

        anon = 1 if meta['anon'] != 0 or bool(str2bool(str(self.config['TRACKERS'][self.tracker].get('anon', "False")))) else 0

        desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        desc = open(desc_path, 'r', encoding='utf-8').read()

        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"
        with open(torrent_file_path, 'rb') as f:
            tfile = f.read()

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
            with requests.Session() as session:
                with open(cookiefile, 'rb') as cf:
                    session.cookies.update(pickle.load(cf))
                response = session.post(url=self.upload_url, data=data, files=files)
                try:
                    if "torrents.php" in response.url:
                        console.print(response.url)
                    else:
                        if "authkey.php" in response.url:
                            console.print("[red]No DL link in response, It may have uploaded, check manually.")
                        else:
                            console.print("[red]Upload Failed. It doesn't look like you are logged in.")
                except Exception:
                    console.print("[red]It may have uploaded, check manually.")
                    print(traceback.print_exc())
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
        return

    async def handle_image_upload(self, meta, img_host_index=1, approved_image_hosts=None):
        if approved_image_hosts is None:
            approved_image_hosts = ['ptpimg', 'imgbox']

        current_img_host_key = f'img_host_{img_host_index}'
        current_img_host = self.config.get('DEFAULT', {}).get(current_img_host_key)

        if not current_img_host or current_img_host not in approved_image_hosts:
            console.print("[red]Your preferred image host is not supported at MTV, re-uploading to an allowed image host.")
            retry_mode = True  # Ensure retry_mode is set to True when switching hosts
            meta['imghost'] = approved_image_hosts[0]  # Switch to the first approved host
        else:
            meta['imghost'] = current_img_host
            retry_mode = False  # Start with retry_mode False unless we know we need to switch

        from src.prep import Prep
        prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=self.config)

        # Screenshot and upload process
        prep.screenshots(Path(meta['path']), meta['name'], meta['uuid'], meta['base_dir'], meta)
        return_dict = {}

        # Call upload_screens with the appropriate retry_mode
        prep.upload_screens(
            meta,
            screens=meta['screens'],
            img_host_num=img_host_index,
            i=0,
            total_screens=meta['screens'],
            custom_img_list=[],  # This remains to handle any custom logic in the original function
            return_dict=return_dict,
            retry_mode=retry_mode  # Honor the retry_mode flag passed in
        )

        # Update meta['image_list'] with uploaded images
        meta['image_list'] = return_dict.get('image_list', [])

        # Ensure images are from approved hosts
        if not all(any(x in image['raw_url'] for x in approved_image_hosts) for image in meta['image_list']):
            console.print("[red]Unsupported image host detected, please use one of the approved image hosts")
            return meta['image_list'], True  # Trigger retry_mode if switching hosts

        return meta['image_list'], False  # No need to retry, successful upload

    async def edit_desc(self, meta):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf-8').read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as desc:
            # adding bd_dump to description if it exits and adding empty string to mediainfo
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
            images = meta['image_list']
            if len(images) > 0:
                desc.write("[spoiler=Screenshots]")
                for each in range(len(images)):
                    raw_url = images[each]['raw_url']
                    img_url = images[each]['img_url']
                    desc.write(f"[url={raw_url}][img=250]{img_url}[/img][/url]")
                desc.write("[/spoiler]")
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
            mtv_name = meta['video']
        else:
            mtv_name = meta['uuid']
        # Try to use original filename if possible
        if meta['source'].lower().replace('-', '') in mtv_name.replace('-', '').lower():
            if not meta['isdir']:
                mtv_name = os.path.splitext(mtv_name)[0]
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
        # Add -NoGrp if missing tag
        if meta['tag'] == "":
            mtv_name = f"{mtv_name}-NoGrp"
        mtv_name = ' '.join(mtv_name.split())
        mtv_name = re.sub(r"[^0-9a-zA-ZÀ-ÿ. &+'\-\[\]]+", "", mtv_name)
        mtv_name = mtv_name.replace(' ', '.').replace('..', '.')
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
        tags.extend([x.strip(', ').lower().replace(' ', '.') for x in meta['genres'].split(',')])
        # Resolution
        tags.append(meta['resolution'].lower())
        if meta['sd'] == 1:
            tags.append('sd')
        elif meta['resolution'] in ['2160p', '4320p']:
            tags.append('uhd')
        else:
            tags.append('hd')
        # Streaming Service
        if str(meta['service_longname']) != "":
            tags.append(f"{meta['service_longname'].lower().replace(' ', '.')}.source")
        # Release Type/Source
        for each in ['remux', 'WEB.DL', 'WEBRip', 'HDTV', 'BluRay', 'DVD', 'HDDVD']:
            if (each.lower().replace('.', '') in meta['type'].lower()) or (each.lower().replace('-', '') in meta['source']):
                tags.append(each)
        # series tags
        if meta['category'] == "TV":
            if meta.get('tv_pack', 0) == 0:
                # Episodes
                if meta['sd'] == 1:
                    tags.extend(['episode.release', 'sd.episode'])
                else:
                    tags.extend(['episode.release', 'hd.episode'])
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
            r = requests.get(url, params=params)
            if not r.ok:
                if "unauthorized api key" in r.text.lower():
                    console.print("[red]Invalid API Key")
                return False
            return True
        except Exception:
            return False

    async def validate_cookies(self, meta, cookiefile):
        url = "https://www.morethantv.me/index.php"
        if os.path.exists(cookiefile):
            with requests.Session() as session:
                with open(cookiefile, 'rb') as cf:
                    session.cookies.update(pickle.load(cf))
                resp = session.get(url=url)
                if meta['debug']:
                    console.log('[cyan]Validate Cookies:')
                    console.log(session.cookies.get_dict())
                    console.log(resp.url)
                if resp.text.find("Logout") != -1:
                    return True
                else:
                    return False
        else:
            return False

    async def get_auth(self, cookiefile):
        url = "https://www.morethantv.me/index.php"
        if os.path.exists(cookiefile):
            with requests.Session() as session:
                with open(cookiefile, 'rb') as cf:
                    session.cookies.update(pickle.load(cf))
                resp = session.get(url=url)
                auth = resp.text.rsplit('authkey=', 1)[1][:32]
                return auth

    async def login(self, cookiefile):
        with requests.Session() as session:
            url = 'https://www.morethantv.me/login'
            payload = {
                'username': self.config['TRACKERS'][self.tracker].get('username'),
                'password': self.config['TRACKERS'][self.tracker].get('password'),
                'keeploggedin': 1,
                'cinfo': '1920|1080|24|0',
                'submit': 'login',
                'iplocked': 1,
                # 'ssl' : 'yes'
            }
            res = session.get(url="https://www.morethantv.me/login")
            token = res.text.rsplit('name="token" value="', 1)[1][:48]
            # token and CID from cookie needed for post to login
            payload["token"] = token
            resp = session.post(url=url, data=payload)

            # handle 2fa
            if resp.url.endswith('twofactor/login'):
                otp_uri = self.config['TRACKERS'][self.tracker].get('otp_uri')
                if otp_uri:
                    import pyotp
                    mfa_code = pyotp.parse_uri(otp_uri).now()
                else:
                    mfa_code = console.input('[yellow]MTV 2FA Code: ')

                two_factor_payload = {
                    'token': resp.text.rsplit('name="token" value="', 1)[1][:48],
                    'code': mfa_code,
                    'submit': 'login'
                }
                resp = session.post(url="https://www.morethantv.me/twofactor/login", data=two_factor_payload)
            # checking if logged in
            if 'authkey=' in resp.text:
                console.print('[green]Successfully logged in to MTV')
                with open(cookiefile, 'wb') as cf:
                    pickle.dump(session.cookies, cf)
            else:
                console.print('[bold red]Something went wrong while trying to log into MTV')
                await asyncio.sleep(1)
                console.print(resp.url)
        return

    async def search_existing(self, meta, disctype):
        dupes = []
        console.print("[yellow]Searching for existing torrents on site...")
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
            rr = requests.get(url=self.search_url, params=params)
            if rr is not None:
                # process search results
                response_xml = xml.etree.ElementTree.fromstring(rr.text)
                for each in response_xml.find('channel').findall('item'):
                    result = each.find('title').text
                    dupes.append(result)
            else:
                if 'status_message' in rr:
                    console.print(f"[yellow]{rr.get('status_message')}")
                    await asyncio.sleep(5)
                else:
                    console.print("[red]Site Seems to be down or not responding to API")
        except Exception:
            console.print("[red]Unable to search for existing torrents on site. Most likely the site is down.")
            dupes.append("FAILED SEARCH")
            print(traceback.print_exc())
            await asyncio.sleep(5)

        return dupes
