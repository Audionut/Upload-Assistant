# -*- coding: utf-8 -*-
import httpx
import os
import platform
import re
from .COMMON import COMMON
from src.console import console
from src.exportmi import exportInfo
from src.rehostimages import check_hosts


class DC(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = 'DC'
        self.source_flag = 'DigitalCore.club'
        self.base_url = 'https://digitalcore.club'
        self.torrent_url = f'{self.base_url}/torrent/'
        self.api_base_url = f'{self.base_url}/api/v1'
        self.banned_groups = ['']
        self.api_key = self.config['TRACKERS'][self.tracker].get('api_key')
        self.passkey = self.config['TRACKERS'][self.tracker].get('passkey')
        self.announce_list = [
            f'https://tracker.digitalcore.club/announce/{self.passkey}',
            f'https://trackerprxy.digitalcore.club/announce/{self.passkey}'
        ]
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Audionut's Upload Assistant ({platform.system()} {platform.release()})",
            'X-API-KEY': self.api_key
        }, timeout=30.0)
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"

    async def mediainfo(self, meta):
        mi_path = f'{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt'

        if meta.get('is_disc') == 'BDMV':
            path = meta['discs'][0]['playlists'][0]['path']
            await exportInfo(
                path,
                False,
                meta['uuid'],
                meta['base_dir'],
                export_text=True,
                is_dvd=False,
                debug=meta.get('debug', False)
            )

            with open(mi_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            lines = [
                line for line in lines
                if not line.strip().startswith('File size') and not line.strip().startswith('Overall bit rate')
            ]

            mediainfo = ''.join(lines)

        else:
            with open(mi_path, 'r', encoding='utf-8') as f:
                mediainfo = f.read()

        return mediainfo

    async def generate_description(self, meta):
        base_desc = f'{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt'
        dc_desc = f'{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt'

        description_parts = []

        # BDInfo
        tech_info = ''
        if meta.get('is_disc') == 'BDMV':
            bd_summary_file = f'{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt'
            if os.path.exists(bd_summary_file):
                with open(bd_summary_file, 'r', encoding='utf-8') as f:
                    tech_info = f.read()

        if tech_info:
            description_parts.append(f'{tech_info}')

        if os.path.exists(base_desc):
            with open(base_desc, 'r', encoding='utf-8') as f:
                manual_desc = f.read()
            description_parts.append(manual_desc)

        # Screenshots
        if f'{self.tracker}_images_key' in meta:
            images = meta[f'{self.tracker}_images_key']
        else:
            images = meta['image_list']
        if images:
            screenshots_block = '[center]\n'
            for i, image in enumerate(images, start=1):
                img_url = image['img_url']
                web_url = image['web_url']
                screenshots_block += f'[url={web_url}][img]{img_url}[/img][/url] '
                # limits to 2 screens per line, as the description box is small
                if i % 2 == 0:
                    screenshots_block += '\n'
            screenshots_block += '\n[/center]'
            description_parts.append(screenshots_block)

        custom_description_header = self.config['DEFAULT'].get('custom_description_header', '')
        if custom_description_header:
            description_parts.append(custom_description_header)

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
        desc = re.sub(r'\[center\]\[spoiler=.*? NFO:\]\[code\](.*?)\[/code\]\[/spoiler\]\[/center\]', r'[nfo]\1[/nfo]', desc, flags=re.DOTALL)
        desc = re.sub(r'(\[img=\d+)]', '[img]', desc, flags=re.IGNORECASE)
        desc = re.sub(r'(\[spoiler=[^]]+])', '[spoiler]', desc, flags=re.IGNORECASE)
        desc = bbcode.convert_comparison_to_centered(desc, 1000)
        desc = re.sub(r'\n{3,}', '\n\n', desc)

        with open(dc_desc, 'w', encoding='utf-8') as f:
            f.write(desc)

        return desc

    async def get_category_id(self, meta):
        resolution = meta.get('resolution')
        category = meta.get('category')
        is_disc = meta.get('is_disc')
        tv_pack = meta.get('tv_pack')
        sd = meta.get('sd')

        if is_disc == 'BDMV':
            if resolution == '1080p' and category == 'MOVIE':
                return 3
            elif resolution == '2160p' and category == 'MOVIE':
                return 38
            elif category == 'TV':
                return 14
        if is_disc == 'DVD':
            if category == 'MOVIE':
                return 1
            elif category == 'TV':
                return 11
        if category == 'TV' and tv_pack == 1:
            return 12
        if sd == 1:
            if category == 'MOVIE':
                return 2
            elif category == 'TV':
                return 10
        category_map = {
            'MOVIE': {'2160p': 4, '1080p': 6, '1080i': 6, '720p': 5},
            'TV': {'2160p': 13, '1080p': 9, '1080i': 9, '720p': 8},
        }
        if category in category_map:
            return category_map[category].get(resolution)
        return None

    async def login(self):
        if not self.api_key:
            console.print(f'[bold red]API key for {self.tracker} is not configured.[/bold red]')
            return False

        url = f'{self.api_base_url}/torrents'

        try:
            response = await self.session.get(url, headers=self.session.headers, timeout=15)
            if response.status_code == 200:
                return True
            else:
                console.print(f'[bold red]Authentication failed for {self.tracker}. Status: {response.status_code}[/bold red]')
                return False
        except httpx.RequestError as e:
            console.print(f'[bold red]Error during {self.tracker} authentication: {e}[/bold red]')
            return False

    async def search_existing(self, meta, results):
        imdb_id = meta.get('imdb_info', {}).get('imdbID')
        if not imdb_id:
            console.print(f'[bold yellow]Cannot perform search on {self.tracker}: IMDb ID not found in metadata.[/bold yellow]')
            return []

        search_url = f'{self.api_base_url}/torrents'
        search_params = {'searchText': imdb_id}
        self.search_results = []
        try:
            response = await self.session.get(search_url, params=search_params, headers=self.session.headers, timeout=15)
            response.raise_for_status()

            if response.text and response.text != '[]':
                self.search_results = response.json()
                results = self.search_results
                if self.search_results and isinstance(self.search_results, list):
                    should_continue = await self.get_title(meta, results)
                    if not should_continue:
                        print('An UNRAR duplicate of this specific release already exists on site.')
                        meta['skipping'] = f'{self.tracker}'
                        return
                    return self.search_results

        except Exception as e:
            console.print(f'[bold red]Error searching for IMDb ID {imdb_id} on {self.tracker}: {e}[/bold red]')

        return []

    async def get_title(self, meta, results):
        results = results
        is_scene = bool(meta.get('scene_name'))
        base_name = meta['scene_name'] if is_scene else meta['uuid']

        needs_unrar_tag = False

        if results:
            upload_title = {meta['uuid']}
            if is_scene:
                upload_title.add(meta['scene_name'])

            matching_titles = [
                t for t in results
                if t.get('name') in upload_title
            ]

            if matching_titles:
                unrar_version_exists = any(t.get('unrar', 0) != 0 for t in matching_titles)

                if unrar_version_exists:
                    return False
                else:
                    console.print(f'[bold yellow]Found a RAR version of this release on {self.tracker}. Appending [UNRAR] to filename.[/bold yellow]')
                    needs_unrar_tag = True

        if needs_unrar_tag:
            upload_base_name = meta['scene_name'] if is_scene else meta['uuid']
            title = f'{upload_base_name} [UNRAR].torrent'
        else:
            title = f'{base_name}.torrent'

        title = title.replace('.mkv', '').replace('.mp4', '')

        return title

    async def fetch_data(self, meta):
        approved_image_hosts = ['imgbox', 'imgbb', 'bhd', 'imgur', 'postimg', 'digitalcore']
        url_host_mapping = {
            'ibb.co': 'imgbb',
            'imgbox.com': 'imgbox',
            'beyondhd.co': 'bhd',
            'imgur.com': 'imgur',
            'postimg.cc': 'postimg',
            'digitalcore.club': 'digitalcore'
        }
        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=approved_image_hosts)

        anon = '1' if meta['anon'] or self.config['TRACKERS'][self.tracker].get('anon', False) else '0'

        data = {
            'category': await self.get_category_id(meta),
            'imdbId': meta.get('imdb_info', {}).get('imdbID', ''),
            'nfo': await self.generate_description(meta),
            'mediainfo': await self.mediainfo(meta),
            'reqid': '0',
            'section': 'new',
            'frileech': '1',
            'anonymousUpload': anon,
            'p2p': '0',
            'unrar': '1',
        }

        return data

    async def upload(self, meta, results):
        await self.edit_torrent(meta, self.tracker, self.source_flag)
        data = await self.fetch_data(meta)
        title = await self.get_title(meta, results)
        status_message = ''
        torrent_id = ''

        if not meta.get('debug', False):
            upload_url = f'{self.api_base_url}/torrents/upload'
            torrent_path = f'{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent'

            with open(torrent_path, 'rb') as torrent_file:
                files = {'file': (title, torrent_file, 'application/x-bittorrent')}

                response = await self.session.post(upload_url, data=data, files=files, headers=self.session.headers, timeout=90)
                response.raise_for_status()
                status_message = response.json()

                if response.status_code == 200 and status_message.get('id'):
                    torrent_id = status_message.get('id', '')
                    if torrent_id:
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                else:
                    console.print(f'{status_message.get('message', 'Unknown API error.')}')
                    meta['skipping'] = f'{self.tracker}'
                    return

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading'

        await self.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce_list, self.torrent_url + str(torrent_id) + '/')

        meta['tracker_status'][self.tracker]['status_message'] = status_message
