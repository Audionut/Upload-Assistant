# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import httpx
import os
from src.console import console
from src.get_desc import DescriptionBuilder
from src.rehostimages import check_hosts
from src.trackers.COMMON import COMMON


class DC:
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'DC'
        self.base_url = 'https://digitalcore.club'
        self.api_base_url = f'{self.base_url}/api/v1/torrents'
        self.torrent_url = f'{self.base_url}/torrent/'
        self.banned_groups = ['']
        self.api_key = self.config['TRACKERS'][self.tracker].get('api_key')
        self.session = httpx.AsyncClient(headers={
            'X-API-KEY': self.api_key
        }, timeout=30.0)

    async def mediainfo(self, meta):
        if meta.get('is_disc') == 'BDMV':
            mediainfo = await self.common.get_bdmv_mediainfo(meta, remove=['File size', 'Overall bit rate'])
        else:
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
            with open(mi_path, 'r', encoding='utf-8') as f:
                mediainfo = f.read()

        return mediainfo

    async def generate_description(self, meta):
        builder = DescriptionBuilder(self.config)
        desc_parts = []

        # Custom Header
        desc_parts.append(await builder.get_custom_header(self.tracker))

        # TV
        title, episode_image, episode_overview = await builder.get_tv_info(meta, self.tracker)
        if episode_overview:
            desc_parts.append(f'[center]{title}[/center]')
            desc_parts.append(f'[center]{episode_overview}[/center]')

        # File information
        desc_parts.append(await builder.get_bdinfo_section(meta))

        # NFO
        if meta.get('description_nfo_content', ''):
            desc_parts.append(f"[nfo]{meta.get('description_nfo_content')}[/nfo]")

        # User description
        desc_parts.append(await builder.get_user_description(meta))

        # Screenshots
        if f'{self.tracker}_images_key' in meta:
            images = meta[f'{self.tracker}_images_key']
        else:
            images = meta['image_list']
        if images:
            screenshots_block = '[center]\n'
            for i, image in enumerate(images, start=1):
                screenshots_block += (
                    f"[url={image['web_url']}][img=350]{image['raw_url']}[/img][/url] "
                )
                # limits to 2 screens per line, as the description box is small
                if i % 2 == 0:
                    screenshots_block += '\n'
            screenshots_block += '\n[/center]'
            desc_parts.append(screenshots_block)

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta, self.tracker))

        # Signature
        desc_parts.append(f"[center][url=https://github.com/Audionut/Upload-Assistant]{meta['ua_signature']}[/url][/center]")

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        from src.bbcode import BBCODE
        bbcode = BBCODE()
        description = description.replace('[user]', '').replace('[/user]', '')
        description = description.replace('[align=left]', '').replace('[/align]', '')
        description = description.replace('[right]', '').replace('[/right]', '')
        description = description.replace('[align=right]', '').replace('[/align]', '')
        description = bbcode.remove_sup(description)
        description = bbcode.remove_sub(description)
        description = description.replace('[alert]', '').replace('[/alert]', '')
        description = description.replace('[note]', '').replace('[/note]', '')
        description = description.replace('[hr]', '').replace('[/hr]', '')
        description = description.replace('[h1]', '[u][b]').replace('[/h1]', '[/b][/u]')
        description = description.replace('[h2]', '[u][b]').replace('[/h2]', '[/b][/u]')
        description = description.replace('[h3]', '[u][b]').replace('[/h3]', '[/b][/u]')
        description = description.replace('[ul]', '').replace('[/ul]', '')
        description = description.replace('[ol]', '').replace('[/ol]', '')
        description = description.replace('[*] ', '• ').replace('[*]', '• ')
        description = bbcode.convert_named_spoiler_to_normal_spoiler(description)
        description = bbcode.convert_comparison_to_centered(description, 1000)
        description = bbcode.remove_list(description)
        description = description.strip()
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    async def get_category_id(self, meta):
        resolution = meta.get('resolution', '')
        category = meta.get('category', '')
        is_disc = meta.get('is_disc', '')
        tv_pack = meta.get('tv_pack', '')
        sd = meta.get('sd', '')

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

    async def search_existing(self, meta, disctype):
        imdb_id = meta.get('imdb_info', {}).get('imdbID')
        if not imdb_id:
            console.print(f'[bold yellow]Cannot perform search on {self.tracker}: IMDb ID not found in metadata.[/bold yellow]')
            return []

        search_params = {'searchText': imdb_id}
        search_results = []
        dupes = []
        try:
            response = await self.session.get(self.api_base_url, params=search_params, headers=self.session.headers, timeout=15)
            response.raise_for_status()

            if response.text and response.text != '[]':
                search_results = response.json()
                if search_results and isinstance(search_results, list):
                    for each in search_results:
                        name = each.get('name')
                        torrent_id = each.get('id')
                        size = each.get('size')
                        torrent_link = f'{self.torrent_url}{torrent_id}/' if torrent_id else None
                        dupe_entry = {
                            'name': name,
                            'size': size,
                            'link': torrent_link
                        }
                        dupes.append(dupe_entry)

                    return dupes

        except Exception as e:
            console.print(f'[bold red]Error searching for IMDb ID {imdb_id} on {self.tracker}: {e}[/bold red]')

        return []

    async def edit_name(self, meta):
        """
        Edits the name according to DC's naming conventions.
        Scene uploads should use the scene name.
        Scene uploads should also have "[UNRAR]" in the name, as the UA only uploads unzipped files, which are considered "altered".
        https://digitalcore.club/forum/17/topic/1051/uploading-for-beginners
        """
        if meta.get("scene_name", ""):
            dc_name = f"{meta.get('scene_name')} [UNRAR]"
        else:
            dc_name = meta["uuid"]
            base, ext = os.path.splitext(dc_name)
            if ext.lower() in {".mkv", ".mp4", ".avi", ".ts"}:
                dc_name = base

        return dc_name

    async def check_image_hosts(self, meta):
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
        return

    async def fetch_data(self, meta):
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

    async def upload(self, meta, disctype):
        data = await self.fetch_data(meta)
        torrent_title = await self.edit_name(meta)
        status_message = ''
        response = None

        if not meta.get('debug', False):
            try:
                upload_url = f'{self.api_base_url}/upload'
                torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"

                with open(torrent_path, 'rb') as torrent_file:
                    files = {'file': (torrent_title + '.torrent', torrent_file, 'application/x-bittorrent')}

                    response = await self.session.post(upload_url, data=data, files=files, headers=self.session.headers, timeout=90)
                    response.raise_for_status()
                    response_data = response.json()

                    if response.status_code == 200 and response_data.get('id'):
                        torrent_id = str(response_data['id'])
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id + '/'
                        status_message = response_data.get('message')

                        await self.common.add_tracker_torrent(
                            meta,
                            tracker=self.tracker,
                            source_flag=None,
                            new_tracker=None,
                            comment=None,
                            headers=self.session.headers,
                            downurl=f'{self.api_base_url}/download/{torrent_id}'
                        )

                    else:
                        status_message = f"data error: {response_data.get('message', 'Unknown API error.')}"

            except httpx.HTTPStatusError as e:
                status_message = f'data error: HTTP {e.response.status_code} - {e.response.text}'
            except httpx.TimeoutException:
                status_message = f'data error: Request timed out after {self.session.timeout.write} seconds'
            except httpx.RequestError as e:
                resp_text = getattr(getattr(e, 'response', None), 'text', 'No response received')
                status_message = f'data error: Unable to upload. Error: {e}.\nResponse: {resp_text}'
            except Exception as e:
                resp_text = response.text if response is not None else 'No response received'
                status_message = f'data error: It may have uploaded, go check. Error: {e}.\nResponse: {resp_text}'
                return

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading'

        meta['tracker_status'][self.tracker]['status_message'] = status_message
