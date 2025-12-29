# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import aiofiles
import asyncio
import glob
import httpx
import os
import platform
import re
from src.console import console
from src.get_desc import DescriptionBuilder
from src.trackers.COMMON import COMMON


class UNIT3D:
    def __init__(self, config, tracker_name):
        self.config = config
        self.tracker = tracker_name
        self.common = COMMON(config)
        tracker_config = self.config['TRACKERS'].get(self.tracker, {})
        self.announce_url = tracker_config.get('announce_url', '')
        self.api_key = tracker_config.get('api_key', '')
        pass

    async def get_additional_checks(self, meta):
        should_continue = True
        return should_continue

    async def search_existing(self, meta, disctype):
        if not self.api_key:
            if not meta['debug']:
                console.print(f'[bold red]{self.tracker}: Missing API key in config file. Skipping upload...[/bold red]')
                meta['skipping'] = f'{self.tracker}'
                return

        should_continue = await self.get_additional_checks(meta)
        if not should_continue:
            meta['skipping'] = f'{self.tracker}'
            return

        dupes = []
        params = {
            'api_token': self.api_key,
            'tmdbId': meta['tmdb'],
            'categories[]': (await self.get_category_id(meta))['category_id'],
            'name': '',
            'perPage': '100'
        }
        resolutions = await self.get_resolution_id(meta)
        if resolutions['resolution_id'] in ['3', '4']:
            # Convert params to list of tuples to support duplicate keys
            params_list = [(k, v) for k, v in params.items()]
            params_list.append(('resolutions[]', '3'))
            params_list.append(('resolutions[]', '4'))
            params = params_list
        else:
            params['resolutions[]'] = resolutions['resolution_id']

        if self.tracker not in ['SP']:
            type_id = (await self.get_type_id(meta))['type_id']
            if isinstance(params, list):
                params.append(('types[]', type_id))
            else:
                params['types[]'] = type_id

        if meta['category'] == 'TV':
            season_value = f" {meta.get('season', '')}"
            if isinstance(params, list):
                # Update the 'name' parameter in the list
                params = [(k, v + season_value if k == 'name' else v) for k, v in params]
            else:
                params['name'] = params['name'] + season_value

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url=self.search_url, params=params)
                response.raise_for_status()
                if response.status_code == 200:
                    data = response.json()
                    for each in data['data']:
                        attributes = each.get('attributes', {})
                        if not meta['is_disc']:
                            result = {
                                'name': attributes['name'],
                                'size': attributes['size'],
                                'files': [file['name'] for file in attributes.get('files', []) if isinstance(file, dict) and 'name' in file],
                                'file_count': len(attributes.get('files', [])) if isinstance(attributes.get('files'), list) else 0,
                                'trumpable': attributes.get('trumpable', False),
                                'link': attributes.get('details_link', None),
                                'download': attributes.get('download_link', None)
                            }
                        else:
                            result = {
                                'name': attributes['name'],
                                'size': attributes['size'],
                                'files': [],
                                'file_count': len(attributes.get('files', [])) if isinstance(attributes.get('files'), list) else 0,
                                'trumpable': attributes.get('trumpable', False),
                                'link': attributes.get('details_link', None),
                                'download': attributes.get('download_link', None)
                            }
                        dupes.append(result)
                else:
                    console.print(f'[bold red]Failed to search torrents. HTTP Status: {response.status_code}')
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 302:
                meta['tracker_status'][self.tracker]['status_message'] = (
                    "data error: Redirect (302). This may indicate a problem with authentication. Please verify that your API key is valid."
                )
            else:
                meta['tracker_status'][self.tracker]['status_message'] = f'data error: HTTP {e.response.status_code} - {e.response.text}'
        except httpx.TimeoutException:
            console.print('[bold red]Request timed out after 10 seconds')
        except httpx.RequestError as e:
            console.print(f'[bold red]Unable to search for existing torrents: {e}')
        except Exception as e:
            console.print(f'[bold red]Unexpected error: {e}')
            await asyncio.sleep(5)

        return dupes

    async def get_name(self, meta):
        return {'name': meta['name']}

    async def get_description(self, meta):
        return {'description': await DescriptionBuilder(self.config).unit3d_edit_desc(meta, self.tracker, comparison=True)}

    async def get_mediainfo(self, meta):
        if meta['bdinfo'] is not None:
            mediainfo = None
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8') as f:
                mediainfo = await f.read()
        return {'mediainfo': mediainfo}

    async def get_bdinfo(self, meta):
        if meta['bdinfo'] is not None:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8') as f:
                bdinfo = await f.read()
        else:
            bdinfo = None
        return {'bdinfo': bdinfo}

    async def get_category_id(self, meta, category=None, reverse=False, mapping_only=False):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }
        if mapping_only:
            return category_id
        elif reverse:
            return {v: k for k, v in category_id.items()}
        elif category is not None:
            return {'category_id': category_id.get(category, '0')}
        else:
            meta_category = meta.get('category', '')
            resolved_id = category_id.get(meta_category, '0')
            return {'category_id': resolved_id}

    async def get_type_id(self, meta, type=None, reverse=False, mapping_only=False):
        type_id = {
            'DISC': '1',
            'REMUX': '2',
            'WEBDL': '4',
            'WEBRIP': '5',
            'HDTV': '6',
            'ENCODE': '3',
            'DVDRIP': '3',
        }
        if mapping_only:
            return type_id
        elif reverse:
            return {v: k for k, v in type_id.items()}
        elif type is not None:
            return {'type_id': type_id.get(type, '0')}
        else:
            meta_type = meta.get('type', '')
            resolved_id = type_id.get(meta_type, '0')
            return {'type_id': resolved_id}

    async def get_resolution_id(self, meta, resolution=None, reverse=False, mapping_only=False):
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
        }
        if mapping_only:
            return resolution_id
        elif reverse:
            return {v: k for k, v in resolution_id.items()}
        elif resolution is not None:
            return {'resolution_id': resolution_id.get(resolution, '10')}
        else:
            meta_resolution = meta.get('resolution', '')
            resolved_id = resolution_id.get(meta_resolution, '10')
            return {'resolution_id': resolved_id}

    async def get_anonymous(self, meta):
        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anonymous = 0
        else:
            anonymous = 1
        return {'anonymous': anonymous}

    async def get_additional_data(self, meta):
        # Used to add additional data if needed
        '''
        data = {
            'modq': await self.get_flag(meta, 'modq'),
            'draft': await self.get_flag(meta, 'draft'),
        }
        '''
        data = {}

        return data

    async def get_flag(self, meta, flag_name):
        config_flag = self.config['TRACKERS'][self.tracker].get(flag_name)
        if meta.get(flag_name, False):
            return 1
        else:
            if config_flag is not None:
                return 1 if config_flag else 0
            else:
                return 0

    async def get_distributor_id(self, meta):
        distributor_id = await self.common.unit3d_distributor_ids(meta.get('distributor'))
        if distributor_id != 0:
            return {'distributor_id': distributor_id}

        return {}

    async def get_region_id(self, meta):
        region_id = await self.common.unit3d_region_ids(meta.get('region'))
        if region_id != 0:
            return {'region_id': region_id}

        return {}

    async def get_tmdb(self, meta):
        return {'tmdb': meta['tmdb']}

    async def get_imdb(self, meta):
        return {'imdb': meta['imdb']}

    async def get_tvdb(self, meta):
        tvdb = meta.get('tvdb_id', 0) if meta['category'] == 'TV' else 0
        return {'tvdb': tvdb}

    async def get_mal(self, meta):
        return {'mal': meta['mal_id']}

    async def get_igdb(self, meta):
        return {'igdb': 0}

    async def get_stream(self, meta):
        return {'stream': meta['stream']}

    async def get_sd(self, meta):
        return {'sd': meta['sd']}

    async def get_keywords(self, meta):
        return {'keywords': meta.get('keywords', '')}

    async def get_personal_release(self, meta):
        personal_release = int(meta.get('personalrelease', False))
        return {'personal_release': personal_release}

    async def get_internal(self, meta):
        internal = 0
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != '' and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                internal = 1

        return {'internal': internal}

    async def get_season_number(self, meta):
        data = {}
        if meta.get('category') == 'TV':
            data = {'season_number': meta.get('season_int', '0')}

        return data

    async def get_episode_number(self, meta):
        data = {}
        if meta.get('category') == 'TV':
            data = {'episode_number': meta.get('episode_int', '0')}

        return data

    async def get_featured(self, meta):
        return {'featured': 0}

    async def get_free(self, meta):
        free = 0
        if meta.get('freeleech', 0) != 0:
            free = meta.get('freeleech', 0)

        return {'free': free}

    async def get_doubleup(self, meta):
        return {'doubleup': 0}

    async def get_sticky(self, meta):
        return {'sticky': 0}

    async def get_data(self, meta):
        results = await asyncio.gather(
            self.get_name(meta),
            self.get_description(meta),
            self.get_mediainfo(meta),
            self.get_bdinfo(meta),
            self.get_category_id(meta),
            self.get_type_id(meta),
            self.get_resolution_id(meta),
            self.get_tmdb(meta),
            self.get_imdb(meta),
            self.get_tvdb(meta),
            self.get_mal(meta),
            self.get_igdb(meta),
            self.get_anonymous(meta),
            self.get_stream(meta),
            self.get_sd(meta),
            self.get_keywords(meta),
            self.get_personal_release(meta),
            self.get_internal(meta),
            self.get_season_number(meta),
            self.get_episode_number(meta),
            self.get_featured(meta),
            self.get_free(meta),
            self.get_doubleup(meta),
            self.get_sticky(meta),
            self.get_additional_data(meta),
            self.get_region_id(meta),
            self.get_distributor_id(meta),
        )

        merged = {}
        for r in results:
            if not isinstance(r, dict):
                raise TypeError(f'Expected dict, got {type(r)}: {r}')
            merged.update(r)

        return merged

    async def get_additional_files(self, meta):
        files = {}
        base_dir = meta['base_dir']
        uuid = meta['uuid']
        specified_dir_path = os.path.join(base_dir, 'tmp', uuid, '*.nfo')
        nfo_files = glob.glob(specified_dir_path)

        if nfo_files:
            async with aiofiles.open(nfo_files[0], 'rb') as f:
                nfo_bytes = await f.read()
            files['nfo'] = ("nfo_file.nfo", nfo_bytes, "text/plain")

        return files

    async def upload(self, meta, disctype):
        data = await self.get_data(meta)
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"
        async with aiofiles.open(torrent_file_path, 'rb') as f:
            torrent_bytes = await f.read()
        files = {'torrent': ('torrent.torrent', torrent_bytes, 'application/x-bittorrent')}
        files.update(await self.get_additional_files(meta))
        headers = {'User-Agent': f'{meta["ua_name"]} {meta.get("current_version", "")} ({platform.system()} {platform.release()})'}
        params = {'api_token': self.api_key}

        if meta['debug'] is False:
            response_data = {}
            max_retries = 2
            retry_delay = 5
            timeout = 10.0

            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                        response = await client.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
                        response.raise_for_status()

                        response_data = response.json()
                        meta['tracker_status'][self.tracker]['status_message'] = await self.process_response_data(response_data)
                        torrent_id = await self.get_torrent_id(response_data)

                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id
                        await self.common.download_tracker_torrent(
                            meta,
                            self.tracker,
                            headers=headers,
                            params=params,
                            downurl=response_data['data']
                        )
                        break  # Success, exit retry loop

                except httpx.HTTPStatusError as e:
                    # Check if upload already exists (can happen after timeout)
                    if "The name has already been taken" in e.response.text or "The info hash has already been taken" in e.response.text:
                        try:
                            error_data = e.response.json()
                            existing_torrent = error_data.get('data', {}).get('existing_torrent', {})
                            torrent_id = str(existing_torrent.get('existing_id', ''))
                            download_url = existing_torrent.get('download_url', '')

                            if torrent_id and download_url:
                                meta['tracker_status'][self.tracker]['status_message'] = (
                                    "Found the uploaded torrent (it was already uploaded successfully)."
                                )
                                meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id
                                await self.common.download_tracker_torrent(
                                    meta,
                                    self.tracker,
                                    headers=headers,
                                    params=params,
                                    downurl=download_url
                                )
                                break  # Success, exit retry loop
                            else:
                                console.print(f'[yellow]{self.tracker}: Could not extract existing torrent info from error response[/yellow]')
                        except Exception as parse_error:
                            console.print(f'[yellow]{self.tracker}: Error parsing existing torrent response: {parse_error}[/yellow]')

                    if e.response.status_code in [403, 302]:
                        # Don't retry auth/permission errors
                        if e.response.status_code == 403:
                            meta['tracker_status'][self.tracker]['status_message'] = (
                                "data error: Forbidden (403). This may indicate that you do not have upload permission."
                            )
                        else:
                            meta['tracker_status'][self.tracker]['status_message'] = (
                                "data error: Redirect (302). This may indicate a problem with authentication. Please verify that your API key is valid."
                            )
                        break  # Don't retry
                    else:
                        # Retry other HTTP errors
                        if attempt < max_retries - 1:
                            console.print(f'[yellow]{self.tracker}: HTTP {e.response.status_code} error, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})[/yellow]')
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            # Final attempt failed
                            if e.response.status_code == 520:
                                meta['tracker_status'][self.tracker]['status_message'] = (
                                    "data error: Error (520). This is probably a cloudflare issue on the tracker side."
                                )
                            else:
                                meta['tracker_status'][self.tracker]['status_message'] = f'data error: HTTP {e.response.status_code} - {e.response.text}'
                except httpx.TimeoutException:
                    if attempt < max_retries - 1:
                        timeout = timeout * 2.00  # Increase timeout by 100% for next retry
                        console.print(f'[yellow]{self.tracker}: Request timed out, retrying in {retry_delay} seconds with {timeout}s timeout... (attempt {attempt + 1}/{max_retries})[/yellow]')
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        meta['tracker_status'][self.tracker]['status_message'] = 'data error: Request timed out after multiple attempts'
                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        console.print(f'[yellow]{self.tracker}: Request error, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})[/yellow]')
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        meta['tracker_status'][self.tracker]['status_message'] = f'data error: Unable to upload. Error: {e}.\nResponse: {response_data}'
                except Exception as e:
                    meta['tracker_status'][self.tracker]['status_message'] = f'data error: It may have uploaded, go check. Error: {e}.\nResponse: {response_data}'
                    return
        else:
            console.print(f'[cyan]{self.tracker} Request Data:')
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = f'Debug mode enabled, not uploading: {self.tracker}.'

    async def get_torrent_id(self, response_data):
        """Matches /12345.abcde and returns 12345"""
        torrent_id = ''
        try:
            match = re.search(r'/(\d+)\.', response_data['data'])
            if match:
                torrent_id = match.group(1)
        except (IndexError, KeyError):
            print('Could not parse torrent_id from response data.')
        return torrent_id

    async def process_response_data(self, response_data):
        """Returns only the success message from the response data if the upload is successful; otherwise, returns the complete response data."""
        status_message = ''
        try:
            if response_data['success'] is True:
                status_message = response_data['message']
            else:
                status_message = response_data
        except Exception:
            pass

        return status_message
