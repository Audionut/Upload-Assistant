import requests
import asyncio
import re
import os
from pathlib import Path
import json
import glob
import httpx
from unidecode import unidecode
from urllib.parse import urlparse, quote
from src.trackers.COMMON import COMMON
from src.exceptions import *  # noqa F403
from src.console import console
from datetime import datetime
from torf import Torrent
from src.torrentcreate import CustomTorrent, torf_cb, create_torrent


class HDB():

    def __init__(self, config):
        self.config = config
        self.tracker = 'HDB'
        self.source_flag = 'HDBits'
        self.username = config['TRACKERS']['HDB'].get('username', '').strip()
        self.passkey = config['TRACKERS']['HDB'].get('passkey', '').strip()
        self.rehost_images = config['TRACKERS']['HDB'].get('img_rehost', True)
        self.signature = None
        self.banned_groups = [""]

    async def get_type_category_id(self, meta):
        cat_id = "EXIT"
        # 6 = Audio Track
        # 8 = Misc/Demo
        # 4 = Music
        # 5 = Sport
        # 7 = PORN
        # 1 = Movie
        if meta['category'] == 'MOVIE':
            cat_id = 1
        # 2 = TV
        if meta['category'] == 'TV':
            cat_id = 2
        # 3 = Documentary
        if 'documentary' in meta.get("genres", "").lower() or 'documentary' in meta.get("keywords", "").lower():
            cat_id = 3
        return cat_id

    async def get_type_codec_id(self, meta):
        codecmap = {
            "AVC": 1, "H.264": 1,
            "HEVC": 5, "H.265": 5,
            "MPEG-2": 2,
            "VC-1": 3,
            "XviD": 4,
            "VP9": 6
        }
        searchcodec = meta.get('video_codec', meta.get('video_encode'))
        codec_id = codecmap.get(searchcodec, "EXIT")
        return codec_id

    async def get_type_medium_id(self, meta):
        medium_id = "EXIT"
        # 1 = Blu-ray / HD DVD
        if meta.get('is_disc', '') in ("BDMV", "HD DVD"):
            medium_id = 1
        # 4 = Capture
        if meta.get('type', '') == "HDTV":
            medium_id = 4
            if meta.get('has_encode_settings', False) is True:
                medium_id = 3
        # 3 = Encode
        if meta.get('type', '') in ("ENCODE", "WEBRIP"):
            medium_id = 3
        # 5 = Remux
        if meta.get('type', '') == "REMUX":
            medium_id = 5
        # 6 = WEB-DL
        if meta.get('type', '') == "WEBDL":
            medium_id = 6
        return medium_id

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

    async def get_tags(self, meta):
        tags = []

        # Web Services:
        service_dict = {
            "AMZN": 28,
            "NF": 29,
            "HULU": 34,
            "DSNP": 33,
            "HMAX": 30,
            "ATVP": 27,
            "iT": 38,
            "iP": 56,
            "STAN": 32,
            "PCOK": 31,
            "CR": 72,
            "PMTP": 69,
            "MA": 77,
            "SHO": 76,
            "BCORE": 66, "CORE": 66,
            "CRKL": 73,
            "FUNI": 74,
            "HLMK": 71,
            "HTSR": 79,
            "CRAV": 80,
            'MAX': 88
        }
        if meta.get('service') in service_dict.keys():
            tags.append(service_dict.get(meta['service']))

        # Collections
        # Masters of Cinema, The Criterion Collection, Warner Archive Collection
        distributor_dict = {
            "WARNER ARCHIVE": 68, "WARNER ARCHIVE COLLECTION": 68, "WAC": 68,
            "CRITERION": 18, "CRITERION COLLECTION": 18, "CC": 18,
            "MASTERS OF CINEMA": 19, "MOC": 19,
            "KINO LORBER": 55, "KINO": 55,
            "BFI VIDEO": 63, "BFI": 63, "BRITISH FILM INSTITUTE": 63,
            "STUDIO CANAL": 65,
            "ARROW": 64
        }
        if meta.get('distributor') in distributor_dict.keys():
            tags.append(distributor_dict.get(meta['distributor']))

        # 4K Remaster,
        if "IMAX" in meta.get('edition', ''):
            tags.append(14)
        if "OPEN MATTE" in meta.get('edition', '').upper():
            tags.append(58)

        # Audio
        # DTS:X, Dolby Atmos, Auro-3D, Silent
        if "DTS:X" in meta['audio']:
            tags.append(7)
        if "Atmos" in meta['audio']:
            tags.append(5)
        if meta.get('silent', False) is True:
            console.print('[yellow]zxx audio track found, suggesting you tag as silent')  # 57

        # Video Metadata
        # HDR10, HDR10+, Dolby Vision, 10-bit,
        if "HDR" in meta.get('hdr', ''):
            if "HDR10+" in meta['hdr']:
                tags.append(25)  # HDR10+
            else:
                tags.append(9)  # HDR10
        if "DV" in meta.get('hdr', ''):
            tags.append(6)  # DV
        if "HLG" in meta.get('hdr', ''):
            tags.append(10)  # HLG

        return tags

    async def edit_name(self, meta):
        hdb_name = meta['name']
        hdb_name = hdb_name.replace('H.265', 'HEVC')
        if meta.get('source', '').upper() == 'WEB' and meta.get('service', '').strip() != '':
            hdb_name = hdb_name.replace(f"{meta.get('service', '')} ", '', 1)
        if 'DV' in meta.get('hdr', ''):
            hdb_name = hdb_name.replace(' DV ', ' DoVi ')
        if 'HDR' in meta.get('hdr', ''):
            if 'HDR10+' not in meta['hdr']:
                hdb_name = hdb_name.replace('HDR', 'HDR10')
        if meta.get('type') in ('WEBDL', 'WEBRIP', 'ENCODE'):
            hdb_name = hdb_name.replace(meta['audio'], meta['audio'].replace(' ', '', 1).replace('Atmos', ''))
        else:
            hdb_name = hdb_name.replace(meta['audio'], meta['audio'].replace('Atmos', ''))
        hdb_name = hdb_name.replace(meta.get('aka', ''), '')
        if meta.get('imdb_info'):
            hdb_name = hdb_name.replace(meta['title'], meta['imdb_info']['aka'])
            if str(meta['year']) != str(meta.get('imdb_info', {}).get('year', meta['year'])) and str(meta['year']).strip() != '':
                hdb_name = hdb_name.replace(str(meta['year']), str(meta['imdb_info']['year']))
        # Remove Dubbed/Dual-Audio from title
        hdb_name = hdb_name.replace('PQ10', 'HDR')
        hdb_name = hdb_name.replace('Dubbed', '').replace('Dual-Audio', '')
        hdb_name = hdb_name.replace('REMUX', 'Remux')
        hdb_name = ' '.join(hdb_name.split())
        hdb_name = re.sub(r"[^0-9a-zA-ZÀ-ÿ. :&+'\-\[\]]+", "", hdb_name)
        hdb_name = hdb_name.replace(' .', '.').replace('..', '.')

        return hdb_name

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await self.edit_desc(meta)
        hdb_name = await self.edit_name(meta)
        cat_id = await self.get_type_category_id(meta)
        codec_id = await self.get_type_codec_id(meta)
        medium_id = await self.get_type_medium_id(meta)
        hdb_tags = await self.get_tags(meta)

        for each in (cat_id, codec_id, medium_id):
            if each == "EXIT":
                console.print("[bold red]Something didn't map correctly, or this content is not allowed on HDB")
                return
        if "Dual-Audio" in meta['audio']:
            if not (meta['anime'] or meta['is_disc']):
                console.print("[bold red]Dual-Audio Encodes are not allowed for non-anime and non-disc content")
            return

        # Download new .torrent from site
        hdb_desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        torrent = Torrent.read(torrent_path)

        # Check if the piece size exceeds 16 MiB and regenerate the torrent if needed
        if torrent.piece_size > 16777216:  # 16 MiB in bytes
            console.print("[red]Piece size is OVER 16M and does not work on HDB. Generating a new .torrent")
            if meta.get('mkbrr', False):
                from data.config import config
                tracker_url = config['TRACKERS']['HDB'].get('announce_url', "https://fake.tracker").strip()

                # Create the torrent with the tracker URL
                torrent_create = f"[{self.tracker}]"
                create_torrent(meta, meta['path'], torrent_create, tracker_url=tracker_url)
                torrent_filename = "[HDB]"

                await common.edit_torrent(meta, self.tracker, self.source_flag, torrent_filename=torrent_filename)
            else:
                if meta['is_disc']:
                    include = []
                    exclude = []
                else:
                    include = ["*.mkv", "*.mp4", "*.ts"]
                    exclude = ["*.*", "*sample.mkv", "!sample*.*"]

                # Create a new torrent with piece size explicitly set to 16 MiB
                new_torrent = CustomTorrent(
                    meta=meta,
                    path=Path(meta['path']),
                    trackers=["https://fake.tracker"],
                    source="Audionut",
                    private=True,
                    exclude_globs=exclude,  # Ensure this is always a list
                    include_globs=include,  # Ensure this is always a list
                    creation_date=datetime.now(),
                    comment="Created by Audionut's Upload Assistant",
                    created_by="Audionut's Upload Assistant"
                )

                # Explicitly set the piece size and update metainfo
                new_torrent.piece_size = 16777216  # 16 MiB in bytes
                new_torrent.metainfo['info']['piece length'] = 16777216  # Ensure 'piece length' is set

                # Validate and write the new torrent
                new_torrent.validate_piece_size()
                new_torrent.generate(callback=torf_cb, interval=5)
                new_torrent.write(torrent_path, overwrite=True)
                torrent_filename = "[HDB]"
                await common.edit_torrent(meta, self.tracker, self.source_flag, torrent_filename=torrent_filename)
        else:
            await common.edit_torrent(meta, self.tracker, self.source_flag, torrent_filename="BASE")

        # Proceed with the upload process
        with open(torrent_path, 'rb') as torrentFile:
            if len(meta['filelist']) == 1:
                torrentFileName = unidecode(os.path.basename(meta['video']).replace(' ', '.'))
            else:
                torrentFileName = unidecode(os.path.basename(meta['path']).replace(' ', '.'))
            files = {
                'file': (f"{torrentFileName}.torrent", torrentFile, "application/x-bittorrent")
            }
            data = {
                'name': hdb_name,
                'category': cat_id,
                'codec': codec_id,
                'medium': medium_id,
                'origin': 0,
                'descr': hdb_desc.rstrip(),
                'techinfo': '',
                'tags[]': hdb_tags,
            }

            # If internal, set 1
            if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
                if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                    data['internal'] = 1
            # If not BDMV fill mediainfo
            if meta.get('is_disc', '') != "BDMV":
                data['techinfo'] = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8').read()
            # If tv, submit tvdb_id/season/episode
            if meta.get('tvdb_id', 0) != 0:
                data['tvdb'] = meta['tvdb_id']
            if int(meta.get('imdb_id')) != 0:
                imdbID = f"tt{meta.get('imdb_id'):07d}"
                data['imdb'] = f"https://www.imdb.com/title/{imdbID}/",
            if meta.get('category') == 'TV':
                data['tvdb_season'] = int(meta.get('season_int', 1))
                data['tvdb_episode'] = int(meta.get('episode_int', 1))
            # aniDB

            url = "https://hdbits.org/upload/upload"
            # Submit
            if meta['debug']:
                console.print(url)
                console.print(data)
            else:
                with requests.Session() as session:
                    cookiefile = f"{meta['base_dir']}/data/cookies/HDB.txt"
                    session.cookies.update(await common.parseCookieFile(cookiefile))
                    up = session.post(url=url, data=data, files=files)
                    torrentFile.close()

                    # Match url to verify successful upload
                    match = re.match(r".*?hdbits\.org/details\.php\?id=(\d+)&uploaded=(\d+)", up.url)
                    if match:
                        id = re.search(r"(id=)(\d+)", urlparse(up.url).query).group(2)
                        await self.download_new_torrent(id, torrent_path)
                    else:
                        console.print(data)
                        console.print("\n\n")
                        console.print(up.text)
                        raise UploadException(f"Upload to HDB Failed: result URL {up.url} ({up.status_code}) was not expected", 'red')  # noqa F405
        return

    async def search_existing(self, meta, disctype):
        dupes = []
        console.print("[yellow]Searching for existing torrents on HDB...")

        url = "https://hdbits.org/api/torrents"
        data = {
            'username': self.username,
            'passkey': self.passkey,
            'category': await self.get_type_category_id(meta),
            'codec': await self.get_type_codec_id(meta),
            'medium': await self.get_type_medium_id(meta),
            'search': meta['resolution']
        }

        # Add IMDb and TVDB IDs if available
        if int(meta.get('imdb_id')) != 0:
            data['imdb'] = {'id': meta['imdb']}
        if int(meta.get('tvdb_id')) != 0:
            data['tvdb'] = {'id': meta['tvdb_id']}

        try:
            # Send POST request with JSON body
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=data)

                if response.status_code == 200:
                    response_data = response.json()
                    for each in response_data.get('data', []):
                        result = each['name']
                        dupes.append(result)
                else:
                    console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")

        except httpx.TimeoutException:
            console.print("[bold red]Request timed out while searching for existing torrents.")
        except httpx.RequestError as e:
            console.print(f"[bold red]An error occurred while making the request: {e}")
        except Exception as e:
            console.print("[bold red]Unexpected error occurred while searching torrents.")
            console.print(str(e))
            await asyncio.sleep(5)

        return dupes

    async def validate_credentials(self, meta):
        vapi = await self.validate_api()
        vcookie = await self.validate_cookies(meta)
        if vapi is not True:
            console.print('[red]Failed to validate API. Please confirm that the site is up and your passkey is valid.')
            return False
        if vcookie is not True:
            console.print('[red]Failed to validate cookies. Please confirm that the site is up and your passkey is valid.')
            return False
        return True

    async def validate_api(self):
        url = "https://hdbits.org/api/test"
        data = {
            'username': self.username,
            'passkey': self.passkey
        }
        try:
            r = requests.post(url, data=json.dumps(data)).json()
            if r.get('status', 5) == 0:
                return True
            return False
        except Exception:
            return False

    async def validate_cookies(self, meta):
        common = COMMON(config=self.config)
        url = "https://hdbits.org"
        cookiefile = f"{meta['base_dir']}/data/cookies/HDB.txt"
        if os.path.exists(cookiefile):
            with requests.Session() as session:
                session.cookies.update(await common.parseCookieFile(cookiefile))
                resp = session.get(url=url)
                if meta['debug']:
                    console.print('[cyan]Cookies:')
                    console.print(session.cookies.get_dict())
                    console.print("\n\n")
                    console.print(resp.text)
                if resp.text.find("""<a href="/logout.php">Logout</a>""") != -1:
                    return True
                else:
                    return False
        else:
            console.print("[bold red]Missing Cookie File. (data/cookies/HDB.txt)")
            return False

    async def download_new_torrent(self, id, torrent_path):
        # Get HDB .torrent filename
        api_url = "https://hdbits.org/api/torrents"
        data = {
            'username': self.username,
            'passkey': self.passkey,
            'id': id
        }
        r = requests.get(url=api_url, data=json.dumps(data))
        filename = r.json()['data'][0]['filename']

        # Download new .torrent
        download_url = f"https://hdbits.org/download.php/{quote(filename)}"
        params = {
            'passkey': self.passkey,
            'id': id
        }

        r = requests.get(url=download_url, params=params)
        with open(torrent_path, "wb") as tor:
            tor.write(r.content)
        return

    async def edit_desc(self, meta):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf-8').read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as descfile:
            from src.bbcode import BBCODE
            # Add This line for all web-dls
            if meta['type'] == 'WEBDL' and meta.get('service_longname', '') != '' and meta.get('description', None) is None:
                descfile.write(f"[center][quote]This release is sourced from {meta['service_longname']}[/quote][/center]")
            bbcode = BBCODE()
            if meta.get('discs', []) != []:
                discs = meta['discs']
                if discs[0]['type'] == "DVD":
                    descfile.write(f"[quote=VOB MediaInfo]{discs[0]['vob_mi']}[/quote]\n")
                    descfile.write("\n")
                if discs[0]['type'] == "BDMV":
                    descfile.write(f"[quote]{discs[0]['summary'].strip()}[/quote]\n")
                    descfile.write("\n")
                if len(discs) >= 2:
                    for each in discs[1:]:
                        if each['type'] == "BDMV":
                            descfile.write(f"[quote={each.get('name', 'BDINFO')}]{each['summary']}[/quote]\n")
                            descfile.write("\n")
                            pass
                        if each['type'] == "DVD":
                            descfile.write(f"{each['name']}:\n")
                            descfile.write(f"[quote={os.path.basename(each['vob'])}][{each['vob_mi']}[/quote] [quote={os.path.basename(each['ifo'])}][{each['ifo_mi']}[/quote]\n")
                            descfile.write("\n")
            desc = base
            desc = bbcode.convert_code_to_quote(desc)
            desc = bbcode.convert_spoiler_to_hide(desc)
            desc = bbcode.convert_comparison_to_centered(desc, 1000)
            desc = re.sub(r"(\[img=\d+)]", "[img]", desc, flags=re.IGNORECASE)
            descfile.write(desc)
            if self.rehost_images is True:
                console.print("[green]Rehosting Images...")
                hdbimg_bbcode = await self.hdbimg_upload(meta)
                descfile.write(f"{hdbimg_bbcode}")
            else:
                images = meta['image_list']
                if len(images) > 0:
                    descfile.write("[center]")
                    for each in range(len(images[:int(meta['screens'])])):
                        img_url = images[each]['img_url']
                        web_url = images[each]['web_url']
                        descfile.write(f"[url={web_url}][img]{img_url}[/img][/url]")
                    descfile.write("[/center]")
            if self.signature is not None:
                descfile.write(self.signature)
            descfile.close()

    async def hdbimg_upload(self, meta):
        image_path = os.path.join(meta['base_dir'], "tmp", os.path.basename(meta['path']), "*.png")
        image_glob = glob.glob(image_path)
        unwanted_patterns = ["FILE*", "PLAYLIST*", "POSTER*"]
        unwanted_files = set()
        for pattern in unwanted_patterns:
            unwanted_files.update(glob.glob(pattern))

        image_glob = [file for file in image_glob if file not in unwanted_files]
        images = list(set(image_glob))
        url = "https://img.hdbits.org/upload_api.php"

        data = {
            'username': self.username,
            'passkey': self.passkey,
            'galleryoption': '1',
            'galleryname': meta['name'],
            'thumbsize': 'w300'
        }
        if meta['debug']:
            print(f"[DEBUG] Uploading to: {url}")
            print(f"[DEBUG] Metadata: {data}")
            print(f"[DEBUG] Found {len(images)} images")

        # Set max screenshots to 3 for TV singles, 6 otherwise
        hdbimg_screen_count = 3 if meta['category'] == "TV" and meta.get('tv_pack', 0) == 0 else 6
        hdbimg_screen_count = min(len(images), hdbimg_screen_count)
        if meta['debug']:
            print(f"[DEBUG] Using {hdbimg_screen_count} images for upload")

        files = {}
        for i in range(hdbimg_screen_count):
            file_path = images[i]
            try:
                files[f'images_files[{i}]'] = (f'image_{i}.png', open(file_path, 'rb'), 'image/png')
                if meta['debug']:
                    print(f"[DEBUG] Added file {file_path} as images_files[{i}]")
            except Exception as e:
                print(f"[ERROR] Failed to open {file_path}: {e}")
                return None

        try:
            response = requests.post(url, data=data, files=files)
            if meta['debug']:
                print(f"[DEBUG] HTTP Response Code: {response.status_code}")
                print(f"[DEBUG] Response Text: {response.text[:500]}")  # Limit output for readability
            return response.text
        except requests.RequestException as e:
            print(f"[ERROR] HTTP Request failed: {e}")
            return None
        finally:
            # Close files to prevent resource leaks
            for f in files.values():
                f[1].close()
                if meta['debug']:
                    print(f"[DEBUG] Closed file {f[0]}")

    async def get_info_from_torrent_id(self, hdb_id):
        hdb_imdb = hdb_tvdb = hdb_name = hdb_torrenthash = None
        url = "https://hdbits.org/api/torrents"
        data = {
            "username": self.username,
            "passkey": self.passkey,
            "id": hdb_id
        }

        try:
            response = requests.get(url, json=data)
            if response.ok:
                response = response.json()
                if response.get('data'):
                    first_entry = response['data'][0]

                    hdb_imdb = int(first_entry.get('imdb', {}).get('id') or 0)
                    hdb_tvdb = int(first_entry.get('tvdb', {}).get('id') or 0)
                    hdb_name = first_entry.get('name', None)
                    hdb_torrenthash = first_entry.get('hash', None)

        except requests.exceptions.RequestException as e:
            console.print(f"Request error: {e}")
        except Exception:
            console.print_exception()

        return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash

    async def search_filename(self, search_term, search_file_folder, meta):
        hdb_imdb = hdb_tvdb = hdb_name = hdb_torrenthash = hdb_id = None
        url = "https://hdbits.org/api/torrents"

        # Handle disc case
        if search_file_folder == 'folder' and meta.get('is_disc'):
            bd_summary_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], 'BD_SUMMARY_00.txt')
            bd_summary = None

            # Parse the BD_SUMMARY_00.txt file to extract the Disc Title
            try:
                with open(bd_summary_path, 'r', encoding='utf-8') as file:
                    for line in file:
                        if "Disc Title:" in line:
                            bd_summary = line.split("Disc Title:")[1].strip()
                            break

                if bd_summary:
                    data = {
                        "username": self.username,
                        "passkey": self.passkey,
                        "limit": 100,
                        "search": bd_summary  # Using the Disc Title for search
                    }
                    console.print(f"[green]Searching HDB for disc title: [bold yellow]{bd_summary}[/bold yellow]")
                    # console.print(f"[yellow]Using this data: {data}")
                else:
                    console.print(f"[red]Error: 'Disc Title' not found in {bd_summary_path}[/red]")
                    return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash, hdb_id

            except FileNotFoundError:
                console.print(f"[red]Error: File not found at {bd_summary_path}[/red]")
                return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash, hdb_id

        else:  # Handling non-disc case
            data = {
                "username": self.username,
                "passkey": self.passkey,
                "limit": 100,
                "file_in_torrent": os.path.basename(search_term)
            }
            console.print(f"[green]Searching HDB for file: [bold yellow]{os.path.basename(search_term)}[/bold yellow]")
            # console.print(f"[yellow]Using this data: {data}")

        try:
            response = requests.get(url, json=data)
            if response.ok:
                try:
                    response_json = response.json()
                    # console.print(f"[green]HDB API response: {response_json}[/green]")

                    if 'data' not in response_json:
                        console.print(f"[red]Error: 'data' key not found or empty in HDB API response. Full response: {response_json}[/red]")
                        return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash, hdb_id

                    for each in response_json['data']:
                        hdb_imdb = int(each.get('imdb', {}).get('id') or 0)
                        hdb_tvdb = int(each.get('tvdb', {}).get('id') or 0)
                        hdb_name = each.get('name', None)
                        hdb_torrenthash = each.get('hash', None)
                        hdb_id = each.get('id', None)

                        console.print(f'[bold green]Matched release with HDB ID: [yellow]https://hdbits.org/details.php?id={hdb_id}[/yellow][/bold green]')

                        return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash, hdb_id

                    console.print('[yellow]No data found in the HDB API response[/yellow]')

                except (ValueError, KeyError, TypeError) as e:
                    console.print_exception()
                    console.print(f"[red]Failed to parse HDB API response. Error: {str(e)}[/red]")
            else:
                console.print(f"[red]Failed to get info from HDB. Status code: {response.status_code}, Reason: {response.reason}[/red]")

        except requests.exceptions.RequestException as e:
            console.print(f"[red]Request error: {str(e)}[/red]")

        console.print('[yellow]Could not find a matching release on HDB[/yellow]')
        return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash, hdb_id
