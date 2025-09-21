# -*- coding: utf-8 -*-
import cli_ui
import glob
import httpx
import os
import platform
import re
from src.trackers.COMMON import COMMON
from bs4 import BeautifulSoup
from pymediainfo import MediaInfo
from src.console import console
from src.exceptions import UploadException


class HDS():
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'HDS'
        self.source_flag = 'HD-Space'
        self.banned_groups = ['']
        self.base_url = 'https://hd-space.org'
        self.torrent_url = 'https://hd-space.org/index.php?page=torrent-details&id='
        self.announce = self.config['TRACKERS'][self.tracker]['announce_url']
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Upload Assistant/2.3 ({platform.system()} {platform.release()})"
        }, timeout=30)
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Created by Upload Assistant[/url][/center]"

    async def load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/HDS.txt")
        if not os.path.exists(cookie_file):
            console.print(f'[bold red]Cookie file for {self.tracker} not found: {cookie_file}[/bold red]')
            return False

        self.session.cookies = await self.common.parseCookieFile(cookie_file)

    async def validate_credentials(self, meta):
        await self.load_cookies(meta)
        try:
            test_url = f'{self.base_url}/index.php?'

            params = {
                'page': 'upload'
            }

            response = await self.session.get(test_url, params=params)

            if response.status_code == 200 and 'index.php?page=upload' in str(response.url):
                return True
            else:
                console.print(f'[bold red]Failed to validate {self.tracker} credentials. The cookie may be expired.[/bold red]')
                return False
        except Exception as e:
            console.print(f'[bold red]Error validating {self.tracker} credentials: {e}[/bold red]')
            return False

    async def generate_description(self, meta):
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        description_parts = []

        # MediaInfo/BDInfo
        tech_info = ''
        if meta.get('is_disc') == 'BDMV':
            bd_summary_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(bd_summary_file):
                with open(bd_summary_file, 'r', encoding='utf-8') as f:
                    tech_info = f.read()

        if not meta.get('is_disc'):
            video_file = meta['filelist'][0]
            mi_template = os.path.abspath(f"{meta['base_dir']}/data/templates/MEDIAINFO.txt")
            if os.path.exists(mi_template):
                try:
                    media_info = MediaInfo.parse(video_file, output='STRING', full=False, mediainfo_options={'inform': f'file://{mi_template}'})
                    tech_info = str(media_info)
                except Exception:
                    console.print('[bold red]Could not find the MediaInfo template[/bold red]')
                    mi_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
                    if os.path.exists(mi_file_path):
                        with open(mi_file_path, 'r', encoding='utf-8') as f:
                            tech_info = f.read()
            else:
                console.print('[bold yellow]Using normal MediaInfo for the description.[/bold yellow]')
                mi_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
                if os.path.exists(mi_file_path):
                    with open(mi_file_path, 'r', encoding='utf-8') as f:
                        tech_info = f.read()

        if tech_info:
            description_parts.append(tech_info)

        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                manual_desc = f.read()
            description_parts.append(manual_desc)

        # Screenshots
        images = meta.get('image_list', [])
        if not images or len(images) < 3:
            raise UploadException('[red]HDS requires at least 3 screenshots.[/red]')

        screenshots_block = '[center]\n'
        for image in images:
            img_url = image['img_url']
            web_url = image['web_url']
            screenshots_block += f'[url={web_url}][img]{img_url}[/img][/url]'
        screenshots_block += '\n[/center]'
        description_parts.append(screenshots_block)

        if self.signature:
            description_parts.append(self.signature)

        final_description = '\n\n'.join(filter(None, description_parts))
        from src.bbcode import BBCODE
        bbcode = BBCODE()
        desc = final_description
        desc = desc.replace('[user]', '').replace('[/user]', '')
        desc = desc.replace('[align=left]', '').replace('[/align]', '')
        desc = desc.replace('[right]', '').replace('[/right]', '')
        desc = desc.replace('[align=right]', '').replace('[/align]', '')
        desc = desc.replace('[sup]', '').replace('[/sup]', '')
        desc = desc.replace('[sub]', '').replace('[/sub]', '')
        desc = desc.replace('[alert]', '').replace('[/alert]', '')
        desc = desc.replace('[note]', '').replace('[/note]', '')
        desc = desc.replace('[hr]', '').replace('[/hr]', '')
        desc = desc.replace('[h1]', '[u][b]').replace('[/h1]', '[/b][/u]')
        desc = desc.replace('[h2]', '[u][b]').replace('[/h2]', '[/b][/u]')
        desc = desc.replace('[h3]', '[u][b]').replace('[/h3]', '[/b][/u]')
        desc = desc.replace('[ul]', '').replace('[/ul]', '')
        desc = desc.replace('[ol]', '').replace('[/ol]', '')
        desc = desc.replace('[hide]', '').replace('[/hide]', '')
        desc = re.sub(r'\[center\]\[spoiler=.*? NFO:\]\[code\](.*?)\[/code\]\[/spoiler\]\[/center\]', r'', desc, flags=re.DOTALL)
        desc = re.sub(r'\[img(?:[^\]]*)\]', '[img]', desc, flags=re.IGNORECASE)
        desc = bbcode.convert_comparison_to_centered(desc, 1000)
        desc = bbcode.remove_spoiler(desc)
        desc = re.sub(r'\n{3,}', '\n\n', desc)

        with open(final_desc_path, 'w', encoding='utf-8') as f:
            f.write(desc)

        return desc

    async def search_existing(self, meta, disctype):
        dupes = []
        imdb_id = meta.get('imdb', '')
        if imdb_id == '0':
            cli_ui.info(f'IMDb ID not found, cannot search for duplicates on {self.tracker}.')
            return dupes

        search_url = f'{self.base_url}/index.php?'

        params = {
            'page': 'torrents',
            'search': imdb_id,
            'active': '0',
            'options': '2'
        }

        try:
            response = await self.session.get(search_url, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            torrent_links = soup.find_all('a', href=lambda href: href and 'page=torrent-details&id=' in href)

            if torrent_links:
                for link in torrent_links:
                    dupes.append(link.get_text(strip=True))

        except Exception as e:
            console.print(f'[bold red]Error searching for duplicates on {self.tracker}: {e}[/bold red]')

        return dupes

    async def get_category_id(self, meta):
        resolution = meta.get('resolution')
        category = meta.get('category')
        type_ = meta.get('type')
        is_disc = meta.get('is_disc')
        genres = meta.get('genres', '').lower()
        keywords = meta.get('keywords', '').lower()
        is_anime = meta.get('anime')

        if is_disc == 'BDMV':
            return 15  # Blu-Ray
        if type_ == 'REMUX':
            return 40  # Remux

        category_map = {
            'MOVIE': {
                '2160p': 46,
                '1080p': 19, '1080i': 19,
                '720p': 18
            },
            'TV': {
                '2160p': 45,
                '1080p': 22, '1080i': 22,
                '720p': 21
            },
            'DOCUMENTARY': {
                '2160p': 47,
                '1080p': 25, '1080i': 25,
                '720p': 24
            },
            'ANIME': {
                '2160p': 48,
                '1080p': 28, '1080i': 28,
                '720p': 27
            }
        }

        if 'documentary' in genres or 'documentary' in keywords:
            return category_map['DOCUMENTARY'].get(resolution, 38)
        if is_anime:
            return category_map['ANIME'].get(resolution, 38)

        if category in category_map:
            return category_map[category].get(resolution, 38)

        return 38

    async def get_requests(self, meta):
        if not self.config['DEFAULT'].get('search_requests', False) and not meta.get('search_requests', False):
            return False
        else:
            try:
                query = meta['title']
                search_url = f'{self.base_url}/index.php?'

                params = {
                    'page': 'viewrequests',
                    'search': query,
                    'filter': 'true'
                }

                response = await self.session.get(search_url, params=params, cookies=self.session.cookies)
                response.raise_for_status()
                response_results_text = response.text

                soup = BeautifulSoup(response_results_text, 'html.parser')
                request_rows = soup.select('form[action="index.php?page=takedelreq"] table.lista tr')

                results = []
                for row in request_rows:
                    if row.find('td', class_='header'):
                        continue

                    name_element = row.select_one('td.lista a b')
                    if not name_element:
                        continue

                    name = name_element.text.strip()
                    link_element = name_element.find_parent('a')
                    link = link_element['href'] if link_element else None

                    results.append({
                        'Name': name,
                        'Link': link,
                    })

                if results:
                    message = f"\n{self.tracker}: [bold yellow]Your upload may fulfill the following request(s), check it out:[/bold yellow]\n\n"
                    for r in results:
                        message += f"[bold green]Name:[/bold green] {r['Name']}\n"
                        message += f"[bold green]Link:[/bold green] {self.base_url}/{r['Link']}\n\n"
                    console.print(message)

                return results

            except Exception as e:
                print(f'An error occurred while fetching requests: {e}')
                return []

    async def get_nfo(self, meta):
        nfo_dir = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
        nfo_files = glob.glob(os.path.join(nfo_dir, '*.nfo'))

        if nfo_files:
            nfo_path = nfo_files[0]

            return {
                'nfo': (
                    os.path.basename(nfo_path),
                    open(nfo_path, 'rb'),
                    'application/octet-stream'
                )
            }
        return {}

    async def fetch_data(self, meta):
        data = {
            'category': await self.get_category_id(meta),
            'filename': meta['name'],
            'genre': meta.get('genres', ''),
            'imdb': meta.get('imdb', ''),
            'info': await self.generate_description(meta),
            'nuk_rea': '',
            'nuk': 'false',
            'req': 'false',
            'submit': 'Send',
            't3d': 'true' if '3D' in meta.get('3d', '') else 'false',
            'user_id': '',
            'youtube_video': meta.get('youtube', ''),
        }

        # Anon
        anon = not (meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data.update({
                'anonymous': 'true'
            })
        else:
            data.update({
                'anonymous': 'false'
            })

        return data

    async def upload(self, meta, disctype):
        await self.load_cookies(meta)
        await self.common.edit_torrent(meta, self.tracker, self.source_flag)
        data = await self.fetch_data(meta)
        requests = await self.get_requests(meta)
        status_message = ''

        if not meta.get('debug', False):
            torrent_id = ''
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
            upload_url = f"{self.base_url}/index.php?"
            params = {
                'page': 'upload'
            }

            with open(torrent_path, 'rb') as torrent_file:
                files = {
                    'torrent': (f'[{self.tracker}].torrent', torrent_file, 'application/x-bittorrent'),
                }
                nfo = await self.get_nfo(meta)
                if nfo:
                    files['nfo'] = nfo['nfo']

                response = await self.session.post(upload_url, data=data, params=params, files=files)

                if 'download.php?id=' in response.text:
                    status_message = 'Torrent uploaded successfully.'

                    # Find the torrent id
                    match = re.search(r'download\.php\?id=([^&]+)', response.text)
                    if match:
                        torrent_id = match.group(1)
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                    if requests:
                        status_message += ' Your upload may fulfill existing requests, check prior console logs.'

                else:
                    status_message = 'The upload appears to have failed. It may have uploaded, go check.'

                    response_save_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                    with open(response_save_path, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    console.print(f'Upload failed, HTML response was saved to: {response_save_path}')

                    meta['skipping'] = f"{self.tracker}"
                    return

            await self.common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce, self.torrent_url + torrent_id)

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading'

        meta['tracker_status'][self.tracker]['status_message'] = status_message
