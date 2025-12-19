# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import glob
import httpx
import os
import platform
import re
from bs4 import BeautifulSoup
from src.bbcode import BBCODE
from src.console import console
from src.cookie_auth import CookieValidator, CookieAuthUploader
from src.get_desc import DescriptionBuilder
from urllib.parse import urlparse


class HDT:
    def __init__(self, config):
        self.config = config
        self.cookie_validator = CookieValidator(config)
        self.cookie_auth_uploader = CookieAuthUploader(config)
        self.tracker = 'HDT'
        self.source_flag = 'hd-torrents.org'

        url_from_config = self.config['TRACKERS'][self.tracker].get('url')
        parsed_url = urlparse(url_from_config)
        self.config_url = parsed_url.netloc
        self.base_url = f'https://{self.config_url}'

        self.torrent_url = f'{self.base_url}/details.php?id='
        self.announce_url = self.config['TRACKERS'][self.tracker]['announce_url']
        self.banned_groups = []
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f'Upload Assistant ({platform.system()} {platform.release()})'
        }, timeout=60.0)

    async def validate_credentials(self, meta):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        return await self.cookie_validator.cookie_validation(
            meta=meta,
            tracker=self.tracker,
            test_url=f'{self.base_url}/upload.php',
            success_text='usercp.php',
            token_pattern=r'name="csrfToken" value="([^"]+)"'
        )

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
            desc_parts.append(f"[center][img]https://image.tmdb.org/t/p/w300/{logo_resize_url}[/img][/center]")

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

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta, self.tracker))

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
        desc_parts.append(f"[right][url=https://github.com/Audionut/Upload-Assistant][size=1]{meta['ua_signature']}[/size][/url][/right]")

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
        description = bbcode.remove_list(description)
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
                'csrfToken': HDT.secret_token,
                'search': imdbID,
                'active': '0',
                'options': '2',
                'category[]': await self.get_category_id(meta)
            }
        else:
            params = {
                'csrfToken': HDT.secret_token,
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
        data = {
            'filename': await self.edit_name(meta),
            'category': await self.get_category_id(meta),
            'info': await self.edit_desc(meta),
            'csrfToken': HDT.secret_token,
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
            data['infosite'] = str(meta.get('imdb_info', {}).get('imdb_url', '') + '/')

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

    async def get_nfo(self, meta):
        nfo_dir = os.path.join(meta['base_dir'], "tmp", meta['uuid'])
        nfo_files = glob.glob(os.path.join(nfo_dir, "*.nfo"))

        if nfo_files:
            nfo_path = nfo_files[0]
            return {'nfos': (os.path.basename(nfo_path), open(nfo_path, "rb"), "application/octet-stream")}
        return {}

    async def upload(self, meta, disctype):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        data = await self.get_data(meta)
        files = await self.get_nfo(meta)

        await self.cookie_auth_uploader.handle_upload(
            meta=meta,
            tracker=self.tracker,
            source_flag=self.source_flag,
            torrent_url=self.torrent_url,
            data=data,
            torrent_field_name='torrent',
            upload_cookies=self.session.cookies,
            upload_url=f"{self.base_url}/upload.php",
            hash_is_id=True,
            success_text="Upload successful!",
            default_announce='https://hdts-announce.ru/announce.php',
            additional_files=files,
        )

        return
