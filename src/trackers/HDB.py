# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import glob
import httpx
import json
import os
import re
import requests

from torf import Torrent
from unidecode import unidecode
from urllib.parse import urlparse, quote

from src.bbcode import BBCODE
from src.console import console
from data.config import config
from src.exceptions import *  # noqa F403
from src.torrentcreate import create_torrent
from src.trackers.COMMON import COMMON


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
        if meta.get('imdb_info').get('type') is not None and meta.get('imdb_info').get('genres') is not None:
            if 'concert' in meta.get('imdb_info').get('type').lower() or ('video' in meta.get('imdb_info').get('type').lower() and 'music' in meta.get('imdb_info').get('genres').lower()):
                cat_id = 4
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
            hdb_name = hdb_name.replace(meta['audio'], meta['audio'].replace(' ', '', 1).replace(' Atmos', ''))
        else:
            hdb_name = hdb_name.replace(meta['audio'], meta['audio'].replace(' Atmos', ''))
        hdb_name = hdb_name.replace(meta.get('aka', ''), '')
        if meta.get('imdb_info'):
            hdb_name = hdb_name.replace(meta['title'], meta['imdb_info']['aka'])
            if str(meta['year']) != str(meta.get('imdb_info', {}).get('year', meta['year'])) and str(meta['year']).strip() != '':
                hdb_name = hdb_name.replace(str(meta['year']), str(meta['imdb_info']['year']))
        # Remove Dubbed/Dual-Audio from title
        hdb_name = hdb_name.replace('PQ10', 'HDR')
        hdb_name = hdb_name.replace('Dubbed', '').replace('Dual-Audio', '')
        hdb_name = hdb_name.replace('REMUX', 'Remux')
        hdb_name = hdb_name.replace('BluRay Remux', 'Remux')
        hdb_name = hdb_name.replace('UHD Remux', 'Remux')
        hdb_name = ' '.join(hdb_name.split())
        hdb_name = re.sub(r"[^0-9a-zA-ZÀ-ÿ. :&+'\-\[\]]+", "", hdb_name)
        hdb_name = hdb_name.replace(' .', '.').replace('..', '.')

        return hdb_name

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await self.edit_desc(meta)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)
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
            if not (meta['anime'] or not meta['is_disc']):
                console.print("[bold red]Dual-Audio Encodes are not allowed for non-anime and non-disc content")
                return

        hdb_desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        loop = asyncio.get_running_loop()
        torrent = await loop.run_in_executor(None, Torrent.read, torrent_file_path)

        # Check if the piece size exceeds 16 MiB and regenerate the torrent if needed
        if torrent.piece_size > 16777216:  # 16 MiB in bytes
            console.print("[red]Piece size is OVER 16M and does not work on HDB. Generating a new .torrent")
            tracker_url = config['TRACKERS']['HDB'].get('announce_url', "https://fake.tracker").strip()
            piece_size = '16'
            torrent_create = f"[{self.tracker}]"

            await create_torrent(meta, meta['path'], torrent_create, tracker_url=tracker_url, piece_size=piece_size)
            await common.create_torrent_for_upload(meta, self.tracker, self.source_flag, torrent_filename=torrent_create)

        # Proceed with the upload process
        with open(torrent_file_path, 'rb') as torrentFile:
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
                    data['origin'] = 1
            # If not BDMV fill mediainfo
            if meta.get('is_disc', '') != "BDMV":
                data['techinfo'] = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8').read()
            # If tv, submit tvdb_id/season/episode
            if meta.get('tvdb_id', 0) != 0:
                data['tvdb'] = meta['tvdb_id']
            if meta.get('imdb_id') != 0:
                data['imdb'] = str(meta.get('imdb_info', {}).get('imdb_url', '')) + '/',
            else:
                data['imdb'] = 0
            if meta.get('category') == 'TV':
                data['tvdb_season'] = int(meta.get('season_int', 1))
                data['tvdb_episode'] = int(meta.get('episode_int', 1))
            # aniDB

            url = "https://hdbits.org/upload/upload"
            # Submit
            if meta['debug']:
                console.print(url)
                console.print(data)
                meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            else:
                with requests.Session() as session:
                    cookiefile = f"{meta['base_dir']}/data/cookies/HDB.txt"
                    session.cookies.update(await common.parseCookieFile(cookiefile))
                    up = session.post(url=url, data=data, files=files)
                    torrentFile.close()

                    # Match url to verify successful upload
                    match = re.match(r".*?hdbits\.org/details\.php\?id=(\d+)&uploaded=(\d+)", up.url)
                    if match:
                        meta['tracker_status'][self.tracker]['status_message'] = match.group(0)
                        id = re.search(r"(id=)(\d+)", urlparse(up.url).query).group(2)
                        await self.download_new_torrent(id, torrent_file_path)
                    else:
                        console.print(data)
                        console.print("\n\n")
                        console.print(up.text)
                        raise UploadException(f"Upload to HDB Failed: result URL {up.url} ({up.status_code}) was not expected", 'red')  # noqa F405
        return

    async def search_existing(self, meta, disctype):
        dupes = []

        url = "https://hdbits.org/api/torrents"
        data = {
            'username': self.username,
            'passkey': self.passkey,
            'category': await self.get_type_category_id(meta),
            'codec': await self.get_type_codec_id(meta),
            'medium': await self.get_type_medium_id(meta)
        }

        if int(meta.get('imdb_id')) != 0:
            data['imdb'] = {'id': meta['imdb']}
        if int(meta.get('tvdb_id')) != 0:
            data['tvdb'] = {'id': meta['tvdb_id']}

        # Build search_terms list
        search_terms = []
        has_valid_ids = ((meta.get('category') == 'TV' and meta.get('tvdb_id', 0) == 0 and meta.get('imdb_id', 0) == 0) or
                         (meta.get('category') == 'MOVIE' and meta.get('imdb_id', 0) == 0))

        if has_valid_ids:
            console.print("[yellow]No IMDb or TVDB ID found, trying other options...")
            console.print("[yellow]Double check that the upload does not already exist...")
            if meta.get('filename'):
                search_terms.append(meta['filename'])
            if meta.get('aka'):
                aka_clean = meta['aka'].replace('AKA ', '').strip()
                if aka_clean:
                    search_terms.append(aka_clean)
            if meta.get('uuid'):
                search_terms.append(meta['uuid'])

        # We have ids
        if not search_terms:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(url, json=data)
                    if response.status_code == 200:
                        response_data = response.json()
                        results = response_data.get('data', [])
                        if results:
                            for each in results:
                                result = {
                                    'name': each['name'],
                                    'size': each['size'],
                                    'files': each['filename'][:-8] if each['filename'].endswith('.torrent') else each['filename'],
                                    'filecount': each['numfiles'],
                                    'link': f"https://hdbits.org/details.php?id={each['id']}",
                                    'download': f"https://hdbits.org/download.php/{quote(each['filename'])}?id={each['id']}&passkey={self.passkey}"
                                }
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

        # Otherwise, search for each term
        for search_term in search_terms:
            console.print(f"[yellow]Searching HDB for: {search_term}")
            data['search'] = search_term

            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(url, json=data)
                    if response.status_code == 200:
                        response_data = response.json()
                        results = response_data.get('data', [])
                        if results:
                            for each in results:
                                result = {
                                    'name': each['name'],
                                    'size': each['size'],
                                    'files': each['filename'][:-8] if each['filename'].endswith('.torrent') else each['filename'],
                                    'filecount': each['numfiles'],
                                    'link': f"https://hdbits.org/details.php?id={each['id']}",
                                    'download': f"https://hdbits.org/download.php/{quote(each['filename'])}?id={each['id']}&passkey={self.passkey}"
                                }
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
        vcookie = await self.validate_cookies(meta)
        if vcookie is not True:
            console.print('[red]Failed to validate cookies. Please confirm that the site is up and your passkey is valid.')
            return False
        return True

    async def validate_cookies(self, meta):
        common = COMMON(config=self.config)
        url = "https://hdbits.org"
        cookiefile = f"{meta['base_dir']}/data/cookies/HDB.txt"
        if os.path.exists(cookiefile):
            with requests.Session() as session:
                session.cookies.update(await common.parseCookieFile(cookiefile))
                resp = session.get(url=url)
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
            # desc = bbcode.convert_code_to_quote(desc)
            desc = desc.replace("[code]", "[font=monospace]").replace("[/code]", "[/font]")
            desc = desc.replace("[user]", "").replace("[/user]", "")
            desc = desc.replace("[left]", "").replace("[/left]", "")
            desc = desc.replace("[align=left]", "").replace("[/align]", "")
            desc = desc.replace("[right]", "").replace("[/right]", "")
            desc = desc.replace("[align=right]", "").replace("[/align]", "")
            desc = desc.replace("[sup]", "").replace("[/sup]", "")
            desc = desc.replace("[sub]", "").replace("[/sub]", "")
            desc = desc.replace("[alert]", "").replace("[/alert]", "")
            desc = desc.replace("[note]", "").replace("[/note]", "")
            desc = desc.replace("[hr]", "").replace("[/hr]", "")
            desc = desc.replace("[h1]", "[u][b]").replace("[/h1]", "[/b][/u]")
            desc = desc.replace("[h2]", "[u][b]").replace("[/h2]", "[/b][/u]")
            desc = desc.replace("[h3]", "[u][b]").replace("[/h3]", "[/b][/u]")
            desc = desc.replace("[ul]", "").replace("[/ul]", "")
            desc = desc.replace("[ol]", "").replace("[/ol]", "")
            desc = desc.replace("[*]", "* ")
            desc = bbcode.convert_spoiler_to_hide(desc)
            desc = bbcode.convert_comparison_to_centered(desc, 1000)
            desc = re.sub(r"(\[img=\d+)]", "[img]", desc, flags=re.IGNORECASE)
            desc = re.sub(r"\[/size\]|\[size=\d+\]", "", desc, flags=re.IGNORECASE)
            descfile.write(desc)
            if self.rehost_images is True:
                console.print("[green]Rehosting Images...")
                hdbimg_bbcode = await self.hdbimg_upload(meta)
                if hdbimg_bbcode is not None:
                    if meta.get('comparison', False):
                        descfile.write("[center]")
                        descfile.write("[b]")
                        if meta.get('comparison_groups'):
                            group_names = []
                            sorted_group_indices = sorted(meta['comparison_groups'].keys(), key=lambda x: int(x))

                            for group_idx in sorted_group_indices:
                                group_data = meta['comparison_groups'][group_idx]
                                group_name = group_data.get('name', f'Group {group_idx}')
                                group_names.append(group_name)

                            comparison_header = " vs ".join(group_names)
                            descfile.write(f"Screenshot comparison[/b]\n\n{comparison_header}")
                        else:
                            descfile.write("Screenshot comparison")

                        descfile.write("\n\n")
                        descfile.write(f"{hdbimg_bbcode}")
                        descfile.write("[/center]")
                    else:
                        descfile.write(f"[center]{hdbimg_bbcode}[/center]")
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

        return

    async def hdbimg_upload(self, meta):
        if meta.get('comparison', False):
            comparison_path = meta.get('comparison')
            if not os.path.isdir(comparison_path):
                console.print(f"[red]Comparison path not found: {comparison_path}")
                return None

            console.print(f"[green]Uploading comparison images from {comparison_path} to HDB Image Host")

            group_images = {}
            max_images_per_group = 0

            if meta.get('comparison_groups'):
                for group_idx, group_data in meta['comparison_groups'].items():
                    files_list = group_data.get('files', [])
                    sorted_files = sorted(files_list, key=lambda f: int(re.match(r"(\d+)-", f).group(1)) if re.match(r"(\d+)-", f) else 0)

                    group_images[group_idx] = []
                    for filename in sorted_files:
                        file_path = os.path.join(comparison_path, filename)
                        if os.path.exists(file_path):
                            group_images[group_idx].append(file_path)

                    max_images_per_group = max(max_images_per_group, len(group_images[group_idx]))
            else:
                files = [f for f in os.listdir(comparison_path) if f.lower().endswith('.png')]
                pattern = re.compile(r"(\d+)-(\d+)-(.+)\.png", re.IGNORECASE)

                for f in files:
                    match = pattern.match(f)
                    if match:
                        first, second, suffix = match.groups()
                        if second not in group_images:
                            group_images[second] = []
                        file_path = os.path.join(comparison_path, f)
                        group_images[second].append((int(first), file_path))

                for group_idx in group_images:
                    group_images[group_idx].sort(key=lambda x: x[0])
                    group_images[group_idx] = [item[1] for item in group_images[group_idx]]
                    max_images_per_group = max(max_images_per_group, len(group_images[group_idx]))

            # Interleave images for correct ordering
            all_image_files = []
            sorted_group_indices = sorted(group_images.keys(), key=lambda x: int(x))
            if len(sorted_group_indices) < 3:
                thumb_size = 'w350'
            elif len(sorted_group_indices) == 3:
                thumb_size = 'w300'
            elif len(sorted_group_indices) == 4:
                thumb_size = 'w200'
            elif len(sorted_group_indices) == 5:
                thumb_size = 'w150'
            else:
                thumb_size = 'w100'

            for image_idx in range(max_images_per_group):
                for group_idx in sorted_group_indices:
                    if image_idx < len(group_images[group_idx]):
                        all_image_files.append(group_images[group_idx][image_idx])

            if meta['debug']:
                console.print("[cyan]Images will be uploaded in this order:")
                for i, path in enumerate(all_image_files):
                    console.print(f"[cyan]{i}: {os.path.basename(path)}")
        else:
            thumb_size = 'w300'
            screenshot_dir = f"{meta['base_dir']}/tmp/{meta['uuid']}"
            # similar to uploadscreens.py L546
            image_patterns = ["*.png", ".[!.]*.png"]
            image_glob = []
            for pattern in image_patterns:
                full_pattern = os.path.join(glob.escape(screenshot_dir), pattern)
                glob_results = await asyncio.to_thread(glob.glob, full_pattern)
                image_glob.extend(glob_results)
            unwanted_patterns = ["FILE*", "PLAYLIST*", "POSTER*"]
            unwanted_files = set()
            for pattern in unwanted_patterns:
                glob_results = await asyncio.to_thread(glob.glob, full_pattern)
                unwanted_files.update(glob_results)
                hidden_pattern = "." + pattern
                hidden_glob_results = await asyncio.to_thread(glob.glob, hidden_pattern)
                unwanted_files.update(hidden_glob_results)  # finished with hidden_glob_results
            image_glob = [file for file in image_glob if file not in unwanted_files]
            all_image_files = list(set(image_glob))

        # At this point, all_image_files contains paths to all images we want to upload
        if not all_image_files:
            console.print("[red]No images found for upload")
            return None

        url = "https://img.hdbits.org/upload_api.php"
        data = {
            'username': self.username,
            'passkey': self.passkey,
            'galleryoption': '1',
            'galleryname': meta['name'],
            'thumbsize': thumb_size
        }

        if meta.get('comparison', False):
            # Use everything
            upload_count = len(all_image_files)
        else:
            # Set max screenshots to 3 for TV singles, 6 otherwise
            upload_count = 3 if meta['category'] == "TV" and meta.get('tv_pack', 0) == 0 else 6
            upload_count = min(len(all_image_files), upload_count)

        if meta['debug']:
            console.print(f"[cyan]Uploading {upload_count} images to HDB Image Host")

        files = {}
        for i in range(upload_count):
            file_path = all_image_files[i]
            try:
                filename = os.path.basename(file_path)
                files[f'images_files[{i}]'] = (filename, open(file_path, 'rb'), 'image/png')
                if meta['debug']:
                    console.print(f"[cyan]Added file {filename} as images_files[{i}]")
            except Exception as e:
                console.print(f"[red]Failed to open {file_path}: {e}")
                continue

        try:
            if not files:
                console.print("[red]No files to upload")
                return None

            if meta['debug']:
                console.print(f"[green]Uploading {len(files)} images to HDB...")

            uploadSuccess = True
            if meta.get('comparison', False):
                num_groups = len(sorted_group_indices) if sorted_group_indices else 3
                max_chunk_size = 100 * 1024 * 1024  # 100 MiB in bytes
                bbcode = ""

                chunks = []
                current_chunk = []
                current_chunk_size = 0

                files_list = list(files.items())
                for i in range(0, len(files_list), num_groups):
                    row_items = files_list[i:i+num_groups]
                    row_size = sum(os.path.getsize(all_image_files[i+j]) for j in range(len(row_items)))

                    # If adding this row would exceed chunk size and we already have items, start new chunk
                    if current_chunk and current_chunk_size + row_size > max_chunk_size:
                        chunks.append(current_chunk)
                        current_chunk = []
                        current_chunk_size = 0

                    current_chunk.extend(row_items)
                    current_chunk_size += row_size

                if current_chunk:
                    chunks.append(current_chunk)

                if meta['debug']:
                    console.print(f"[cyan]Split into {len(chunks)} chunks based on 100 MiB limit")

                # Upload each chunk
                for chunk_idx, chunk in enumerate(chunks):
                    fileList = {}
                    for j, (key, value) in enumerate(chunk):
                        fileList[f'images_files[{j}]'] = value

                    if meta['debug']:
                        chunk_size_mb = sum(os.path.getsize(all_image_files[int(key.split('[')[1].split(']')[0])]) for key, _ in chunk) / (1024 * 1024)
                        console.print(f"[cyan]Uploading chunk {chunk_idx + 1}/{len(chunks)} ({len(fileList)} images, {chunk_size_mb:.2f} MiB)")

                    response = requests.post(url, data=data, files=fileList)
                    if response.status_code == 200:
                        console.print(f"[green]Chunk {chunk_idx + 1}/{len(chunks)} upload successful!")
                        bbcode += response.text
                    else:
                        console.print(f"[red]Chunk {chunk_idx + 1}/{len(chunks)} upload failed with status code {response.status_code}")
                        uploadSuccess = False
                        break
            else:
                response = requests.post(url, data=data, files=files)
                if response.status_code == 200:
                    console.print("[green]Upload successful!")
                    bbcode = response.text
                else:
                    uploadSuccess = False

            if uploadSuccess is True:
                if meta.get('comparison', False):
                    matches = re.findall(r'\[url=.*?\]\[img\].*?\[/img\]\[/url\]', bbcode)
                    formatted_bbcode = ""
                    num_groups = len(sorted_group_indices) if sorted_group_indices else 3

                    for i in range(0, len(matches), num_groups):
                        line = " ".join(matches[i:i+num_groups])
                        if i + num_groups < len(matches):
                            formatted_bbcode += line + "\n"
                        else:
                            formatted_bbcode += line

                    bbcode = formatted_bbcode

                    if meta['debug']:
                        console.print(f"[cyan]Response formatted with {num_groups} images per line")

                return bbcode
            else:
                console.print(f"[red]Upload failed with status code {response.status_code}")
                return None
        except requests.RequestException as e:
            console.print(f"[red]HTTP Request failed: {e}")
            return None
        finally:
            # Close files to prevent resource leaks
            for f in files.values():
                f[1].close()

    async def get_info_from_torrent_id(self, hdb_id):
        hdb_imdb = hdb_tvdb = hdb_name = hdb_torrenthash = hdb_description = None
        url = "https://hdbits.org/api/torrents"
        data = {
            "username": self.username,
            "passkey": self.passkey,
            "id": hdb_id
        }

        try:
            response = requests.post(url, json=data)
            if response.ok:
                response_json = response.json()

                if response_json.get('status') == 0 and response_json.get('data'):
                    first_entry = response_json['data'][0]

                    hdb_imdb = int(first_entry.get('imdb', {}).get('id') or 0)
                    hdb_tvdb = int(first_entry.get('tvdb', {}).get('id') or 0)
                    hdb_name = first_entry.get('name', None)
                    hdb_torrenthash = first_entry.get('hash', None)
                    hdb_description = first_entry.get('descr')

                else:
                    status_code = response_json.get('status', 'unknown')
                    message = response_json.get('message', 'No error message provided')
                    console.print(f"[red]API returned error status {status_code}: {message}[/red]")

        except requests.exceptions.RequestException as e:
            console.print(f"[red]Request error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Unexpected error: {e}[/red]")
            console.print_exception()

        return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash, hdb_description

    async def search_filename(self, search_term, search_file_folder, meta):
        hdb_imdb = hdb_tvdb = hdb_name = hdb_torrenthash = hdb_description = hdb_id = None
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

                if not bd_summary:
                    bd_summary = meta.get('uuid', '')

                if bd_summary:
                    data = {
                        "username": self.username,
                        "passkey": self.passkey,
                        "limit": 100,
                        "search": bd_summary  # Using the Disc Title for search with uuid fallback
                    }
                    console.print(f"[green]Searching HDB for title: [bold yellow]{bd_summary}[/bold yellow]")
                    # console.print(f"[yellow]Using this data: {data}")
                else:
                    return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash, hdb_description, hdb_id

            except FileNotFoundError:
                console.print(f"[red]Error: File not found at {bd_summary_path}[/red]")
                return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash, hdb_description, hdb_id

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
            response = requests.post(url, json=data)
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
                        hdb_description = each.get('descr')

                        console.print(f'[bold green]Matched release with HDB ID: [yellow]https://hdbits.org/details.php?id={hdb_id}[/yellow][/bold green]')

                        return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash, hdb_description, hdb_id

                    console.print('[yellow]No data found in the HDB API response[/yellow]')

                except (ValueError, KeyError, TypeError) as e:
                    console.print_exception()
                    console.print(f"[red]Failed to parse HDB API response. Error: {str(e)}[/red]")
            else:
                console.print(f"[red]Failed to get info from HDB. Status code: {response.status_code}, Reason: {response.reason}[/red]")

        except requests.exceptions.RequestException as e:
            console.print(f"[red]Request error: {str(e)}[/red]")

        console.print('[yellow]Could not find a matching release on HDB[/yellow]')
        return hdb_imdb, hdb_tvdb, hdb_name, hdb_torrenthash, hdb_description, hdb_id
