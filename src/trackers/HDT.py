# -*- coding: utf-8 -*-
import aiofiles
import http.cookiejar
import httpx
import os
import re
from bs4 import BeautifulSoup
from src.bbcode import BBCODE
from src.console import console
from src.get_desc import DescriptionBuilder
from src.trackers.COMMON import COMMON
from urllib.parse import urlparse


class HDT:
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'HDT'
        self.source_flag = 'hd-torrents.org'

        url_from_config = self.config['TRACKERS'][self.tracker].get('url')
        parsed_url = urlparse(url_from_config)
        self.config_url = parsed_url.netloc
        self.base_url = f'https://{self.config_url}'

        self.torrent_url = f'{self.base_url}/details.php?id='
        self.announce_url = self.config['TRACKERS'][self.tracker]['announce_url']
        self.banned_groups = []
        self.ua_name = f'Upload Assistant {self.common.get_version()}'.strip()
        self.signature = f'\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by {self.ua_name}[/url][/center]'
        self.session = httpx.AsyncClient(headers={
            'User-Agent': self.ua_name
        }, timeout=60.0)

    async def load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        self.cookie_jar = http.cookiejar.MozillaCookieJar(cookie_file)

        try:
            self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
        except FileNotFoundError:
            console.print(f'{self.tracker}: [bold red]Cookie file for {self.tracker} not found: {cookie_file}[/bold red]')

        self.session.cookies = self.cookie_jar

    async def save_cookies(self):
        if self.cookie_jar is None:
            console.print(f'{self.tracker}: Cookie jar not initialized, cannot save cookies.')
            return

        try:
            self.cookie_jar.save(ignore_discard=True, ignore_expires=True)
        except Exception as e:
            console.print(f'{self.tracker}: Failed to update the cookie file: {e}')

    async def validate_credentials(self, meta):
        await self.load_cookies(meta)
        try:
            upload_page_url = f'{self.base_url}/upload.php'
            response = await self.session.get(upload_page_url)
            response.raise_for_status()

            if 'Create account' in response.text:
                console.print(f'{self.tracker}: Validation failed. The cookie appears to be expired or invalid.')
                return False

            auth_match = re.search(r'name="csrfToken" value="([^"]+)"', response.text)

            if not auth_match:
                console.print(f"{self.tracker}: Validation failed. Could not find 'auth' token on upload page.")
                console.print('This can happen if the site HTML has changed or if the login failed silently..')

                failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                os.makedirs(os.path.dirname(failure_path), exist_ok=True)
                with open(failure_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                console.print(f'The server response was saved to {failure_path} for analysis.')
                return False

            await self.save_cookies()
            return str(auth_match.group(1))

        except httpx.TimeoutException:
            console.print(f'{self.tracker}: Error in {self.tracker}: Timeout while trying to validate credentials.')
            return False
        except httpx.HTTPStatusError as e:
            console.print(f'{self.tracker}: HTTP error validating credentials for {self.tracker}: Status {e.response.status_code}.')
            return False
        except httpx.RequestError as e:
            console.print(f'{self.tracker}: Network error while validating credentials for {self.tracker}: {e.__class__.__name__}.')
            return False
        except Exception as e:
            console.print(f'{self.tracker}: Unexpected error validating credentials: {e}')
            return False

    async def get_category_id(self, meta):
        if meta['category'] == 'MOVIE':
            # BDMV
            if meta.get('is_disc', '') == "BDMV" or meta.get('type', '') == "DISC":
                if meta['resolution'] == '2160p':
                    # 70 = Movie/UHD/Blu-Ray
                    cat_id = 70
                if meta['resolution'] in ('1080p', '1080i'):
                    # 1 = Movie/Blu-Ray
                    cat_id = 1

            # REMUX
            if meta.get('type', '') == 'REMUX':
                if meta.get('uhd', '') == 'UHD' and meta['resolution'] == '2160p':
                    # 71 = Movie/UHD/Remux
                    cat_id = 71
                else:
                    # 2 = Movie/Remux
                    cat_id = 2

            # REST OF THE STUFF
            if meta.get('type', '') not in ("DISC", "REMUX"):
                if meta['resolution'] == '2160p':
                    # 64 = Movie/2160p
                    cat_id = 64
                elif meta['resolution'] in ('1080p', '1080i'):
                    # 5 = Movie/1080p/i
                    cat_id = 5
                elif meta['resolution'] == '720p':
                    # 3 = Movie/720p
                    cat_id = 3

        if meta['category'] == 'TV':
            # BDMV
            if meta.get('is_disc', '') == "BDMV" or meta.get('type', '') == "DISC":
                if meta['resolution'] == '2160p':
                    # 72 = TV Show/UHD/Blu-ray
                    cat_id = 72
                if meta['resolution'] in ('1080p', '1080i'):
                    # 59 = TV Show/Blu-ray
                    cat_id = 59

            # REMUX
            if meta.get('type', '') == 'REMUX':
                if meta.get('uhd', '') == 'UHD' and meta['resolution'] == '2160p':
                    # 73 = TV Show/UHD/Remux
                    cat_id = 73
                else:
                    # 60 = TV Show/Remux
                    cat_id = 60

            # REST OF THE STUFF
            if meta.get('type', '') not in ("DISC", "REMUX"):
                if meta['resolution'] == '2160p':
                    # 65 = TV Show/2160p
                    cat_id = 65
                elif meta['resolution'] in ('1080p', '1080i'):
                    # 30 = TV Show/1080p/i
                    cat_id = 30
                elif meta['resolution'] == '720p':
                    # 38 = TV Show/720p
                    cat_id = 38

        return cat_id

    async def edit_name(self, meta):
        hdt_name = meta['name']
        if meta.get('type') in ('WEBDL', 'WEBRIP', 'ENCODE'):
            hdt_name = hdt_name.replace(meta['audio'], meta['audio'].replace(' ', '', 1))
        if 'DV' in meta.get('hdr', ''):
            hdt_name = hdt_name.replace(' DV ', ' DoVi ')
        if 'BluRay REMUX' in hdt_name:
            hdt_name = hdt_name.replace('BluRay REMUX', 'Blu-ray Remux')

        hdt_name = ' '.join(hdt_name.split())
        hdt_name = re.sub(r"[^0-9a-zA-ZÀ-ÿ. &+'\-\[\]]+", "", hdt_name)
        hdt_name = hdt_name.replace(':', '').replace('..', ' ').replace('  ', ' ')
        return hdt_name

    async def edit_desc(self, meta):
        builder = DescriptionBuilder(self.config)
        desc_parts = []

        # Custom Header
        desc_parts.append(await builder.get_custom_header(self.tracker))

        # Logo
        logo_resize_url = meta.get('tmdb_logo', '')
        if logo_resize_url:
            desc_parts.append(f"[center][img]https://image.tmdb.org/t/p/w300{logo_resize_url}[/img][/center]")

        # TV
        title, episode_image, episode_overview = await builder.get_tv_info(meta, self.tracker, resize=True)
        if episode_overview:
            desc_parts.append(f'[center]{title}[/center]')

            if episode_image:
                desc_parts.append(f"[center][img]{episode_image}[/img][/center]")

            desc_parts.append(f'[center]{episode_overview}[/center]')

        # File information
        mediainfo = await builder.get_mediainfo_section(meta, self.tracker)
        if mediainfo:
            desc_parts.append(f'[left][font=consolas]{mediainfo}[/font][/left]')

        bdinfo = await builder.get_bdinfo_section(meta)
        if bdinfo:
            desc_parts.append(f'[left][font=consolas]{bdinfo}[/font][/left]')

        # User description
        desc_parts.append(await builder.get_user_description(meta))

        # Screenshot Header
        desc_parts.append(await builder.screenshot_header(self.tracker))

        # Screenshots
        images = meta.get('image_list', [])
        if images:
            screenshots_block = ''
            for image in images:
                screenshots_block += f"<a href='{image['raw_url']}'><img src='{image['img_url']}' height=137></a> "
            desc_parts.append('[center]\n' + screenshots_block + '[/center]')

        # Signature
        desc_parts.append(f"[center][url=https://github.com/Audionut/Upload-Assistant]Created by {meta.get('ua_name')} {meta.get('current_version', '')}[/url][/center]")

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = description.replace('[user]', '').replace('[/user]', '')
        description = description.replace('[align=left]', '').replace('[/align]', '')
        description = description.replace('[align=right]', '').replace('[/align]', '')
        description = bbcode.remove_sub(description)
        description = bbcode.remove_sup(description)
        description = description.replace('[alert]', '').replace('[/alert]', '')
        description = description.replace('[note]', '').replace('[/note]', '')
        description = description.replace('[hr]', '').replace('[/hr]', '')
        description = description.replace('[h1]', '[u][b]').replace('[/h1]', '[/b][/u]')
        description = description.replace('[h2]', '[u][b]').replace('[/h2]', '[/b][/u]')
        description = description.replace('[h3]', '[u][b]').replace('[/h3]', '[/b][/u]')
        description = description.replace('[ul]', '').replace('[/ul]', '')
        description = description.replace('[ol]', '').replace('[/ol]', '')
        description = bbcode.convert_spoiler_to_hide(description)
        description = bbcode.remove_img_resize(description)
        description = bbcode.convert_comparison_to_centered(description, 1000)
        description = bbcode.remove_spoiler(description)
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    async def search_existing(self, meta, disctype):
        if meta['resolution'] not in ['2160p', '1080p', '1080i', '720p']:
            console.print('[bold red]Resolution must be at least 720p resolution for HDT.')
            meta['skipping'] = f'{self.tracker}'
            return []

        # Ensure we have valid credentials and auth_token before searching
        if not hasattr(self, 'auth_token') or not self.auth_token:
            credentials_valid = await self.validate_credentials(meta)
            if not credentials_valid:
                console.print(f'[bold red]{self.tracker}: Failed to validate credentials for search.')
                return []

        search_url = f'{self.base_url}/torrents.php?'
        if int(meta.get('imdb_id', 0)) != 0:
            imdbID = f"tt{meta['imdb']}"
            params = {
                'csrfToken': meta[f'{self.tracker}_secret_token'],
                'search': imdbID,
                'active': '0',
                'options': '2',
                'category[]': await self.get_category_id(meta)
            }
        else:
            params = {
                'csrfToken': meta[f'{self.tracker}_secret_token'],
                'search': meta['title'],
                'category[]': await self.get_category_id(meta),
                'options': '3'
            }

        results = []

        try:
            response = await self.session.get(search_url, params=params)
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.find_all('tr')

            for row in rows:
                if row.find('td', class_='mainblockcontent', string='Filename') is not None:
                    continue

                name_tag = row.find('a', href=lambda href: href and href.startswith('details.php?id='))

                name = name_tag.text.strip() if name_tag else None
                link = f'{self.base_url}/{name_tag["href"]}' if name_tag else None
                size = None

                cells = row.find_all('td', class_='mainblockcontent')
                for cell in cells:
                    cell_text = cell.text.strip()
                    if 'GiB' in cell_text or 'MiB' in cell_text:
                        size = cell_text
                        break

                if name:
                    results.append({
                        'name': name,
                        'size': size,
                        'link': link
                    })

        except httpx.TimeoutException:
            console.print(f'{self.tracker}: Timeout while searching for existing torrents.')
            return []
        except httpx.HTTPStatusError as e:
            console.print(f'{self.tracker}: HTTP error while searching: Status {e.response.status_code}.')
            return []
        except httpx.RequestError as e:
            console.print(f'{self.tracker}: Network error while searching: {e.__class__.__name__}.')
            return []
        except Exception as e:
            console.print(f'{self.tracker}: Unexpected error while searching: {e}')
            return []

        return results

    async def get_data(self, meta):
        await self.load_cookies(meta)
        data = {
            'filename': await self.edit_name(meta),
            'category': await self.get_category_id(meta),
            'info': await self.edit_desc(meta),
            'csrfToken': meta[f'{self.tracker}_secret_token'],
        }

        # 3D
        if "3D" in meta.get('3d', ''):
            data['3d'] = 'true'

        # HDR
        if "HDR" in meta.get('hdr', ''):
            if "HDR10+" in meta['hdr']:
                data['HDR10'] = 'true'
                data['HDR10Plus'] = 'true'
            else:
                data['HDR10'] = 'true'
        if "DV" in meta.get('hdr', ''):
            data['DolbyVision'] = 'true'

        # IMDB
        if int(meta.get('imdb_id')) != 0:
            data['infosite'] = meta.get('imdb_info', {}).get('imdb_url', '')

        # Full Season Pack
        if int(meta.get('tv_pack', '0')) != 0:
            data['season'] = 'true'
        else:
            data['season'] = 'false'

        # Anonymous check
        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            data['anonymous'] = 'false'
        else:
            data['anonymous'] = 'true'

        return data

    async def upload(self, meta, disctype):
        await self.common.edit_torrent(meta, self.tracker, self.source_flag, announce_url='https://hdts-announce.ru/announce.php')
        data = await self.get_data(meta)
        status_message = ''

        if not meta.get('debug', False):
            torrent_id = ''
            upload_url = f"{self.base_url}/upload.php"
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

            with open(torrent_path, 'rb') as torrent_file:
                files = {'torrent': ('torrent.torrent', torrent_file, 'application/x-bittorrent')}

                response = await self.session.post(url=upload_url, data=data, files=files)

                if 'Upload successful!' in response.text:
                    status_message = "Torrent uploaded successfully."

                    # Find the torrent id
                    match = re.search(r'download\.php\?id=([^&]+)', response.text)
                    if match:
                        torrent_id = match.group(1)
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                else:
                    status_message = 'data error - The upload appears to have failed. It may have uploaded, go check.'

                    response_save_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                    with open(response_save_path, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    console.print(f'Upload failed, HTML response was saved to: {response_save_path}')

            await self.common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce_url, self.torrent_url + torrent_id)

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message
