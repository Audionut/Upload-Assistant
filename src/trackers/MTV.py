# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
import aiofiles
import aiofiles.os
import asyncio
import cli_ui
import httpx
import os
import pickle
import pyotp
import re
import traceback
import xml.etree.ElementTree as ET

from torf import Torrent

from data.config import config
from src.console import console
from src.rehostimages import check_hosts
from src.torrentcreate import create_torrent
from src.trackers.COMMON import COMMON


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
            '3LTON', '[Oj]', 'aXXo', 'BDP', 'BRrip', 'CM8', 'CrEwSaDe', 'CMCT',
            'DeadFish', 'DNL', 'ELiTE', 'AFG', 'ZMNT',
            'FaNGDiNG0', 'FRDS', 'FUM', 'h65', 'HD2DVD', 'HDTime', 'ION10', 'iPlanet', 'JIVE',
            'KiNGDOM', 'LAMA', 'Leffe', 'LOAD', 'mHD', 'mRS', 'mSD', 'NhaNc3', 'nHD', 'nikt0', 'nSD',
            'PandaRG', 'PRODJi', 'QxR', 'RARBG', 'RDN', 'SANTi', 'STUTTERSHIT',
            'TERMiNAL',  # TERMiNAL: low bitrate UHD
            'TM', 'ViSiON',  # ViSiON: Xvid releases -- re-encoded
            'WAF', 'x0r', 'XS', 'YIFY', 'ZKBL', 'ZmN'
        ]
        pass

    # For loading
    async def async_pickle_loads(self, data):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, pickle.loads, data)

    # For dumping
    async def async_pickle_dumps(self, obj):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, pickle.dumps, obj)

    async def check_image_hosts(self, meta):
        approved_image_hosts = ['ptpimg', 'imgbox', 'imgbb']
        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "imgbox.com": "imgbox",
        }

        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=approved_image_hosts)
        return

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/MTV.pkl")
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        if not await aiofiles.os.path.exists(torrent_file_path):
            await common.edit_torrent(meta, self.tracker, self.source_flag, torrent_filename="BASE")

        loop = asyncio.get_running_loop()
        torrent = await loop.run_in_executor(None, Torrent.read, torrent_file_path)

        if torrent.piece_size > 8388608:
            tracker_config = self.config['TRACKERS'].get(self.tracker, {})
            if str(tracker_config.get('skip_if_rehash', 'false')).lower() == "false":
                console.print("[red]Piece size is OVER 8M and does not work on MTV. Generating a new .torrent")
                meta['max_piece_size'] = '8'
                tracker_url = config['TRACKERS']['MTV'].get('announce_url', "https://fake.tracker").strip()
                torrent_create = f"[{self.tracker}]"

                create_torrent(meta, meta['path'], torrent_create, tracker_url=tracker_url)
                await common.edit_torrent(meta, self.tracker, self.source_flag, torrent_filename=torrent_create)

            else:
                console.print("[red]Piece size is OVER 8M and skip_if_rehash enabled. Skipping upload.")
                return

        cat_id = await self.get_cat_id(meta)
        resolution_id = await self.get_res_id(meta['resolution'])
        source_id = await self.get_source_id(meta)
        origin_id = await self.get_origin_id(meta)
        des_tags = await self.get_tags(meta)
        await self.edit_desc(meta)
        group_desc = await self.edit_group_desc(meta)
        mtv_name = await self.edit_name(meta)

        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anon = 0
        else:
            anon = 1

        desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        async with aiofiles.open(desc_path, 'r', encoding='utf-8') as f:
            desc = await f.read()

        async with aiofiles.open(torrent_file_path, 'rb') as f:
            tfile = await f.read()

        files = {
            'file_input': (f"[{self.tracker}].torrent", tfile)
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
            try:
                async with aiofiles.open(cookiefile, 'rb') as cf:
                    cookie_data = await cf.read()
                    cookies = await self.async_pickle_loads(cookie_data)

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }

                async with httpx.AsyncClient(
                    cookies=cookies,
                    timeout=10.0,
                    follow_redirects=True,
                    headers=headers
                ) as client:

                    response = await client.post(url=self.upload_url, data=data, files=files)

                    try:
                        if "torrents.php" in str(response.url):
                            meta['tracker_status'][self.tracker]['status_message'] = response.url
                            await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), str(response.url))
                        elif 'https://www.morethantv.me/upload.php' in str(response.url):
                            meta['tracker_status'][self.tracker]['status_message'] = "data error - Still on upload page - upload may have failed"
                            if "error" in response.text.lower() or "failed" in response.text.lower():
                                meta['tracker_status'][self.tracker]['status_message'] = "data error - Upload failed - check form data"
                        elif str(response.url) == "https://www.morethantv.me/" or str(response.url) == "https://www.morethantv.me/index.php":
                            if "Project Luminance" in response.text:
                                meta['tracker_status'][self.tracker]['status_message'] = "data error - Not logged in - session may have expired"
                            if "'GroupID' cannot be null" in response.text:
                                meta['tracker_status'][self.tracker]['status_message'] = "data error - You are hitting this site bug: https://www.morethantv.me/forum/thread/3338?"
                            elif "Integrity constraint violation" in response.text:
                                meta['tracker_status'][self.tracker]['status_message'] = "data error - Proper site bug"
                        else:
                            if "authkey.php" in str(response.url):
                                meta['tracker_status'][self.tracker]['status_message'] = "data error - No DL link in response, It may have uploaded, check manually."
                            else:
                                console.print(f"response URL: {response.url}")
                                console.print(f"response status: {response.status_code}")
                    except Exception:
                        meta['tracker_status'][self.tracker]['status_message'] = "data error -It may have uploaded, check manually."
                        print(traceback.print_exc())
            except (httpx.RequestError, Exception) as e:
                meta['tracker_status'][self.tracker]['status_message'] = f"data error: {e}"
                return
        else:
            console.print("[cyan]MTV Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        return

    async def edit_desc(self, meta):
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf-8') as f:
            base = await f.read()

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as desc:
            if meta['bdinfo'] is not None:
                mi_dump = None
                async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8') as f:
                    bd_dump = await f.read()
            else:
                async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8') as f:
                    mi_dump = (await f.read()).strip()
                bd_dump = None

            if bd_dump:
                await desc.write("[mediainfo]" + bd_dump + "[/mediainfo]\n\n")
            elif mi_dump:
                await desc.write("[mediainfo]" + mi_dump + "[/mediainfo]\n\n")

            if (
                meta.get('is_disc') == "DVD" and
                isinstance(meta.get('discs'), list) and
                len(meta['discs']) > 0 and
                'vob_mi' in meta['discs'][0]
            ):
                await desc.write("[mediainfo]" + meta['discs'][0]['vob_mi'] + "[/mediainfo]\n\n")
            try:
                if meta.get('tonemapped', False) and self.config['DEFAULT'].get('tonemapped_header', None):
                    console.print("[green]Adding tonemapped header to description")
                    tonemapped_header = self.config['DEFAULT'].get('tonemapped_header')
                    await desc.write(tonemapped_header)
                    await desc.write("\n\n")
            except Exception as e:
                console.print(f"[yellow]Warning: Error setting tonemapped header: {str(e)}[/yellow]")
            if f'{self.tracker}_images_key' in meta:
                images = meta[f'{self.tracker}_images_key']
            else:
                images = meta['image_list']
            if len(images) > 0:
                for image in images:
                    raw_url = image['raw_url']
                    img_url = image['img_url']
                    await desc.write(f"[url={raw_url}][img=250]{img_url}[/img][/url]")

            base = re.sub(r'\[/?quote\]', '', base, flags=re.IGNORECASE).strip()
            if base != "":
                await desc.write(f"\n\n[spoiler=Notes]{base}[/spoiler]")

        return

    async def edit_group_desc(self, meta):
        description = ""
        if meta['imdb_id'] != 0:
            description += str(meta.get('imdb_info', {}).get('imdb_url', ''))
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
        KNOWN_EXTENSIONS = {".mkv", ".mp4", ".avi", ".ts"}
        if meta['scene'] is True:
            if meta.get('scene_name') != "":
                mtv_name = meta.get('scene_name')
            else:
                mtv_name = meta['uuid']
                base, ext = os.path.splitext(mtv_name)
                if ext.lower() in KNOWN_EXTENSIONS:
                    mtv_name = base
        else:
            mtv_name = meta['name']
            prefix_removed = False
            replacement_prefix = ""

            # Check for Dual-Audio or Dubbed prefix
            if "Dual-Audio " in mtv_name:
                prefix_removed = True
                prefix_index = mtv_name.find("Dual-Audio ")
                replacement_prefix = "DUAL "
                mtv_name = mtv_name[:prefix_index] + mtv_name[prefix_index + len("Dual-Audio "):]
            elif "Dubbed " in mtv_name:
                prefix_removed = True
                prefix_index = mtv_name.find("Dubbed ")
                replacement_prefix = "DUBBED "
                mtv_name = mtv_name[:prefix_index] + mtv_name[prefix_index + len("Dubbed "):]

            audio_str = meta['audio']
            if prefix_removed:
                audio_str = audio_str.replace("Dual-Audio ", "").replace("Dubbed ", "")

            if prefix_removed and prefix_index != -1:
                mtv_name = f"{mtv_name[:prefix_index]}{replacement_prefix}{mtv_name[prefix_index:].lstrip()}"

            if meta.get('type') in ('WEBDL', 'WEBRIP', 'ENCODE') and "DD" in audio_str:
                mtv_name = mtv_name.replace(audio_str, audio_str.replace(' ', '', 1))
            if 'DD+' in meta.get('audio', '') and 'DDP' in meta['uuid']:
                mtv_name = mtv_name.replace('DD+', 'DDP')

        if meta['source'].lower().replace('-', '') in mtv_name.replace('-', '').lower():
            if not meta['isdir']:
                # Check if there is a valid file extension, otherwise, skip the split
                if '.' in mtv_name and mtv_name.split('.')[-1].isalpha() and len(mtv_name.split('.')[-1]) <= 4:
                    mtv_name = os.path.splitext(mtv_name)[0]

        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                mtv_name = re.sub(f"-{invalid_tag}", "", mtv_name, flags=re.IGNORECASE)
            mtv_name = f"{mtv_name}-NOGRP"

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
        # MTV takes issue with some of the pulled TMDB tags, and I'm not hand checking and attempting
        # to regex however many tags need changing, so they're just getting skipped
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
        if not await aiofiles.os.path.exists(cookiefile):
            await self.login(cookiefile)
        vcookie = await self.validate_cookies(meta, cookiefile)
        if vcookie is not True:
            console.print('[red]Failed to validate cookies. Please confirm that the site is up and your username and password is valid.')
            if 'mtv_timeout' in meta and meta['mtv_timeout']:
                meta['skipping'] = "MTV"
                return False
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                recreate = cli_ui.ask_yes_no("Log in again and create new session?")
            else:
                recreate = True
            if recreate is True:
                if await aiofiles.os.path.exists(cookiefile):
                    await aiofiles.os.remove(cookiefile)  # Using async file removal
                await self.login(cookiefile)
                vcookie = await self.validate_cookies(meta, cookiefile)
                return vcookie
            else:
                return False

        return True

    async def validate_cookies(self, meta, cookiefile):
        url = "https://www.morethantv.me/index.php"
        if await aiofiles.os.path.exists(cookiefile):
            try:

                async with aiofiles.open(cookiefile, 'rb') as cf:
                    data = await cf.read()
                    cookies_dict = await self.async_pickle_loads(data)

                async with httpx.AsyncClient(cookies=cookies_dict, timeout=10) as client:
                    try:
                        resp = await client.get(url=url)
                        if meta['debug']:
                            console.print('[cyan]Validating MTV Cookies:')

                        if "Logout" in resp.text:
                            return True
                        else:
                            console.print("[yellow]Valid session not found in cookies")
                            return False

                    except httpx.TimeoutException:
                        console.print(f"[red]Connection to {url} timed out. The site may be down or unreachable.")
                        meta['mtv_timeout'] = True
                        return False
                    except httpx.ConnectError:
                        console.print(f"[red]Failed to connect to {url}. The site may be down or your connection is blocked.")
                        meta['mtv_timeout'] = True
                        return False
                    except Exception as e:
                        console.print(f"[red]Error connecting to MTV: {str(e)}")
                        return False
            except Exception as e:
                console.print(f"[red]Error loading cookies: {str(e)}")
                return False
        else:
            console.print("[yellow]Cookie file not found")
            return False

    async def get_auth(self, cookiefile):
        url = "https://www.morethantv.me/index.php"
        try:
            if await aiofiles.os.path.exists(cookiefile):
                async with aiofiles.open(cookiefile, 'rb') as cf:
                    data = await cf.read()
                    cookies = await self.async_pickle_loads(data)

                async with httpx.AsyncClient(cookies=cookies, timeout=10) as client:
                    try:
                        resp = await client.get(url=url)
                        if "authkey=" in resp.text:
                            auth = resp.text.rsplit('authkey=', 1)[1][:32]
                            return auth
                        else:
                            console.print("[yellow]Auth key not found in response")
                            return ""
                    except httpx.RequestError as e:
                        console.print(f"[red]Error getting auth key: {str(e)}")
                        return ""
            else:
                console.print("[yellow]Cookie file not found for auth key retrieval")
                return ""
        except Exception as e:
            console.print(f"[red]Unexpected error retrieving auth key: {str(e)}")
            return ""

    async def login(self, cookiefile):
        try:
            async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                url = 'https://www.morethantv.me/login'
                payload = {
                    'username': self.config['TRACKERS'][self.tracker].get('username'),
                    'password': self.config['TRACKERS'][self.tracker].get('password'),
                    'keeploggedin': 1,
                    'cinfo': '1920|1080|24|0',
                    'submit': 'login',
                    'iplocked': 1,
                }

                try:
                    res = await client.get(url="https://www.morethantv.me/login")

                    if 'name="token" value="' not in res.text:
                        console.print("[red]Unable to find token in login page")
                        return False

                    token = res.text.rsplit('name="token" value="', 1)[1][:48]

                    payload["token"] = token
                    resp = await client.post(url=url, data=payload)

                    if str(resp.url).endswith('twofactor/login'):

                        otp_uri = self.config['TRACKERS'][self.tracker].get('otp_uri')
                        if otp_uri:
                            mfa_code = pyotp.parse_uri(otp_uri).now()
                        else:
                            mfa_code = console.input('[yellow]MTV 2FA Code: ')

                        two_factor_token = resp.text.rsplit('name="token" value="', 1)[1][:48]
                        two_factor_payload = {
                            'token': two_factor_token,
                            'code': mfa_code,
                            'submit': 'login'
                        }
                        resp = await client.post(url="https://www.morethantv.me/twofactor/login", data=two_factor_payload)

                    await asyncio.sleep(1)
                    if 'authkey=' in resp.text:
                        console.print('[green]Successfully logged in to MTV')
                        cookies_dict = dict(client.cookies)
                        cookies_data = await self.async_pickle_dumps(cookies_dict)
                        async with aiofiles.open(cookiefile, 'wb') as cf:
                            await cf.write(cookies_data)
                        console.print(f"[green]Cookies saved to {cookiefile}")
                        return True
                    else:
                        console.print('[bold red]Something went wrong while trying to log into MTV')
                        console.print(f"[red]Final URL: {resp.url}")
                        return False

                except httpx.TimeoutException:
                    console.print("[red]Connection to MTV timed out. The site may be down or unreachable.")
                    return False
                except httpx.ConnectError:
                    console.print("[red]Failed to connect to MTV. The site may be down or your connection is blocked.")
                    return False
                except Exception as e:
                    console.print(f"[red]Error during MTV login: {str(e)}")
                    console.print(f"[dim red]{traceback.format_exc()}[/dim red]")
                    return False
        except Exception as e:
            console.print(f"[red]Unexpected error during login: {str(e)}")
            console.print(f"[dim red]{traceback.format_exc()}[/dim red]")
        return False

    async def search_existing(self, meta, disctype):
        if meta.get('bloated', False):
            console.print(f'[bold red]Bloated releases are not allowed at {self.tracker}[/bold red]')
            meta['skipping'] = "MTV"
            return []
        if meta['type'] not in ['WEBDL']:
            if meta.get('tag', "") and any(x in meta['tag'] for x in ['EVO']):
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    console.print(f'[bold red]Group {meta["tag"]} is only allowed for raw type content at {self.tracker}[/bold red]')
                    if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                        pass
                    else:
                        meta['skipping'] = "MTV"
                        return []
                else:
                    meta['skipping'] = "MTV"
                    return []

        allowed_anime = ['Thighs', 'sam', 'Vanilla', 'OZR', 'Netaro', 'Datte13', 'UDF', 'Baws', 'ARC', 'Dae', 'MTBB',
                         'Okay-Subs', 'hchcsen', 'Noyr', 'TTGA', 'GJM', 'Kaleido-Subs', 'GJM-Kaleido', 'LostYears',
                         'Reza', 'Aergia', 'Drag', 'Crow', 'Arid', 'JySzE', 'iKaos', 'Spirale', 'CsS', 'FLE', 'WSE',
                         'Legion', 'AC', 'UQW', 'Commie', 'Chihiro']
        if meta['resolution'] not in ['2160p'] and meta['video_codec'] in ['HEVC']:
            if meta['anime'] and meta.get('tag', "") and not any(x in meta['tag'] for x in allowed_anime):
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    console.print(f'[bold red]Only 4K HEVC anime releases from {meta["tag"]} are allowed at {self.tracker}[/bold red]')
                    if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                        pass
                    else:
                        meta['skipping'] = "MTV"
                        return []
            else:
                console.print(f'[bold red]Only 4K HEVC releases are allowed at {self.tracker}[/bold red]')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    meta['skipping'] = "MTV"
                    return []

        disallowed_keywords = {'XXX', 'Erotic', 'Porn'}
        disallowed_genres = {'Adult', 'Erotica'}
        if any(keyword.lower() in disallowed_keywords for keyword in map(str.lower, meta['keywords'])) or any(genre.lower() in disallowed_genres for genre in map(str.lower, meta.get('combined_genres', []))):
            if (not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False))):
                console.print(f'[bold red]Porn/xxx is not allowed at {self.tracker}.[/bold red]')
                if cli_ui.ask_yes_no("Do you want to upload anyway?", default=False):
                    pass
                else:
                    meta['skipping'] = "MTV"
                    return []
            else:
                meta['skipping'] = "MTV"
                return []

        dupes = []

        # Build request parameters
        params = {
            't': 'search',
            'apikey': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'q': "",
            'limit': "100"
        }

        if meta['imdb_id'] != 0:
            params['imdbid'] = "tt" + str(meta['imdb'])
        elif meta['tmdb'] != 0:
            params['tmdbid'] = str(meta['tmdb'])
        elif meta['tvdb_id'] != 0:
            params['tvdbid'] = str(meta['tvdb_id'])
        else:
            params['q'] = meta['title'].replace(': ', ' ').replace('’', '').replace("'", '')

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)

                if response.status_code == 200 and response.text:
                    # Parse XML response
                    try:
                        loop = asyncio.get_running_loop()
                        response_xml = await loop.run_in_executor(None, ET.fromstring, response.text)
                        for each in response_xml.find('channel').findall('item'):
                            result = {
                                'name': each.find('title').text,
                                'files': each.find('title').text,
                                'file_count': each.find('files').text,
                                'size': each.find('size').text,
                                'link': each.find('guid').text
                            }
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
