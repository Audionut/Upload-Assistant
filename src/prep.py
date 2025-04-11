# -*- coding: utf-8 -*-
from src.console import console
from src.exceptions import *  # noqa: F403
from src.clients import Clients
from data.config import config
from src.trackersetup import tracker_class_map
from src.tvmaze import search_tvmaze, get_tvmaze_episode_data
from src.imdb import get_imdb_info_api, search_imdb
from src.trackermeta import update_metadata_from_tracker
from src.tmdb import tmdb_other_meta, get_tmdb_imdb_from_mediainfo, get_tmdb_from_imdb, get_tmdb_id, get_episode_details
from src.region import get_region, get_distributor, get_service
from src.exportmi import exportInfo, mi_resolution
from src.getseasonep import get_season_episode
from src.btnid import get_btn_torrents, get_bhd_torrents
from src.tvdb import get_tvdb_episode_data, get_tvdb_series_episodes

try:
    import traceback
    from src.discparse import DiscParse
    import os
    import re
    from guessit import guessit
    import ntpath
    from pathlib import Path
    import urllib
    import urllib.parse
    import json
    import glob
    import requests
    from pymediainfo import MediaInfo
    import tmdbsimple as tmdb
    import time
    import itertools
    import aiohttp
    import asyncio
    from difflib import SequenceMatcher
except ModuleNotFoundError:
    console.print(traceback.print_exc())
    console.print('[bold red]Missing Module Found. Please reinstall required dependancies.')
    console.print('[yellow]pip3 install --user -U -r requirements.txt')
    exit()
except KeyboardInterrupt:
    exit()


class Prep():
    """
    Prepare for upload:
        Mediainfo/BDInfo
        Screenshots
        Database Identifiers (TMDB/IMDB/MAL/etc)
        Create Name
    """
    def __init__(self, screens, img_host, config):
        self.screens = screens
        self.config = config
        self.img_host = img_host.lower()
        tmdb.API_KEY = config['DEFAULT']['tmdb_api']

    def _is_true(self, value):
        return str(value).strip().lower() == "true"

    async def gather_prep(self, meta, mode):
        meta['cutoff'] = int(self.config['DEFAULT'].get('cutoff_screens', 1))
        tvdb_api = str(self.config['DEFAULT'].get('tvdb_api', None))
        tvdb_token = str(self.config['DEFAULT'].get('tvdb_token', None))
        meta['mode'] = mode
        meta['isdir'] = os.path.isdir(meta['path'])
        base_dir = meta['base_dir']
        meta['saved_description'] = False

        folder_id = os.path.basename(meta['path'])
        if meta.get('uuid', None) is None:
            meta['uuid'] = folder_id
        if not os.path.exists(f"{base_dir}/tmp/{meta['uuid']}"):
            Path(f"{base_dir}/tmp/{meta['uuid']}").mkdir(parents=True, exist_ok=True)

        if meta['debug']:
            console.print(f"[cyan]ID: {meta['uuid']}")

        meta['is_disc'], videoloc, bdinfo, meta['discs'] = await self.get_disc(meta)

        # Debugging information
        # console.print(f"Debug: meta['filelist'] before population: {meta.get('filelist', 'Not Set')}")

        if meta['is_disc'] == "BDMV":
            video, meta['scene'], meta['imdb_id'] = await self.is_scene(meta['path'], meta, meta.get('imdb_id', 0))
            meta['filelist'] = []  # No filelist for discs, use path
            search_term = os.path.basename(meta['path'])
            search_file_folder = 'folder'
            try:
                guess_name = bdinfo['title'].replace('-', ' ')
                filename = guessit(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]})['title']
                untouched_filename = bdinfo['title']
                try:
                    meta['search_year'] = guessit(bdinfo['title'])['year']
                except Exception:
                    meta['search_year'] = ""
            except Exception:
                guess_name = bdinfo['label'].replace('-', ' ')
                filename = guessit(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]})['title']
                untouched_filename = bdinfo['label']
                try:
                    meta['search_year'] = guessit(bdinfo['label'])['year']
                except Exception:
                    meta['search_year'] = ""

            if meta.get('resolution', None) is None:
                meta['resolution'] = await mi_resolution(bdinfo['video'][0]['res'], guessit(video), width="OTHER", scan="p", height="OTHER", actual_height=0)
            meta['sd'] = await self.is_sd(meta['resolution'])

            mi = None

        elif meta['is_disc'] == "DVD":
            video, meta['scene'], meta['imdb_id'] = await self.is_scene(meta['path'], meta, meta.get('imdb_id', 0))
            meta['filelist'] = []
            search_term = os.path.basename(meta['path'])
            search_file_folder = 'folder'
            guess_name = meta['discs'][0]['path'].replace('-', ' ')
            filename = guessit(guess_name, {"excludes": ["country", "language"]})['title']
            untouched_filename = os.path.basename(os.path.dirname(meta['discs'][0]['path']))
            try:
                meta['search_year'] = guessit(meta['discs'][0]['path'])['year']
            except Exception:
                meta['search_year'] = ""
            if not meta.get('edit', False):
                mi = await exportInfo(f"{meta['discs'][0]['path']}/VTS_{meta['discs'][0]['main_set'][0][:2]}_1.VOB", False, meta['uuid'], meta['base_dir'], export_text=False)
                meta['mediainfo'] = mi
            else:
                mi = meta['mediainfo']

            meta['dvd_size'] = await self.get_dvd_size(meta['discs'], meta.get('manual_dvds'))
            meta['resolution'] = await self.get_resolution(guessit(video), meta['uuid'], base_dir)
            meta['sd'] = await self.is_sd(meta['resolution'])

        elif meta['is_disc'] == "HDDVD":
            video, meta['scene'], meta['imdb_id'] = await self.is_scene(meta['path'], meta, meta.get('imdb_id', 0))
            meta['filelist'] = []
            search_term = os.path.basename(meta['path'])
            search_file_folder = 'folder'
            guess_name = meta['discs'][0]['path'].replace('-', '')
            filename = guessit(guess_name, {"excludes": ["country", "language"]})['title']
            untouched_filename = os.path.basename(meta['discs'][0]['path'])
            videopath = meta['discs'][0]['largest_evo']
            try:
                meta['search_year'] = guessit(meta['discs'][0]['path'])['year']
            except Exception:
                meta['search_year'] = ""
            if not meta.get('edit', False):
                mi = await exportInfo(meta['discs'][0]['largest_evo'], False, meta['uuid'], meta['base_dir'], export_text=False)
                meta['mediainfo'] = mi
            else:
                mi = meta['mediainfo']
            meta['resolution'] = await self.get_resolution(guessit(video), meta['uuid'], base_dir)
            meta['sd'] = await self.is_sd(meta['resolution'])

        else:
            def extract_title_and_year(filename):
                basename = os.path.basename(filename)
                basename = os.path.splitext(basename)[0]

                secondary_title = None
                year = None

                # Check for AKA patterns first
                aka_patterns = [' AKA ', '.aka.', ' aka ', '.AKA.']
                for pattern in aka_patterns:
                    if pattern in basename:
                        aka_parts = basename.split(pattern, 1)
                        if len(aka_parts) > 1:
                            primary_title = aka_parts[0].strip()
                            secondary_part = aka_parts[1].strip()

                            # Look for a year in the primary title
                            year_match_primary = re.search(r'\b(19|20)\d{2}\b', primary_title)
                            if year_match_primary:
                                year = year_match_primary.group(0)

                            # Process secondary title
                            secondary_match = re.match(r"^(\d+)", secondary_part)
                            if secondary_match:
                                secondary_title = secondary_match.group(1)
                            else:
                                # Catch everything after AKA until it hits a year or release info
                                year_or_release_match = re.search(r'\b(19|20)\d{2}\b|\bBluRay\b|\bREMUX\b|\b\d+p\b|\bDTS-HD\b|\bAVC\b', secondary_part)
                                if year_or_release_match:
                                    # Check if we found a year in the secondary part
                                    if re.match(r'\b(19|20)\d{2}\b', year_or_release_match.group(0)):
                                        # If no year was found in primary title, or we want to override
                                        if not year:
                                            year = year_or_release_match.group(0)

                                    secondary_title = secondary_part[:year_or_release_match.start()].strip()
                                else:
                                    secondary_title = secondary_part

                            primary_title = primary_title.replace('.', ' ')
                            secondary_title = secondary_title.replace('.', ' ')
                            return primary_title, secondary_title, year

                # if not AKA, catch titles that begin with a year
                match = re.match(r"^(\d+)", basename)
                if match:
                    potential_title = match.group(1)
                    # Check if this title could also be a year (1900-2099)
                    could_be_year = re.match(r'^(19|20)\d{2}$', potential_title) is not None

                    # Search for a different year elsewhere in the filename
                    year_match = re.search(r'\b(19|20)\d{2}\b', basename)

                    # Only accept the year_match if it's different from the potential_title
                    if year_match and (not could_be_year or year_match.group(0) != potential_title):
                        year = year_match.group(0)
                    else:
                        year = None

                    return potential_title, None, year

                # If no pattern match works but there's still a year in the filename, extract it
                year_match = re.search(r'\b(19|20)\d{2}\b', basename)
                if year_match:
                    year = year_match.group(0)
                    return None, None, year

                return None, None, None

            videopath, meta['filelist'] = await self.get_video(videoloc, meta.get('mode', 'discord'))
            search_term = os.path.basename(meta['filelist'][0]) if meta['filelist'] else None
            search_file_folder = 'file'

            video, meta['scene'], meta['imdb_id'] = await self.is_scene(videopath, meta, meta.get('imdb_id', 0))

            title, secondary_title, extracted_year = extract_title_and_year(video)
            if meta['debug']:
                console.print(f"Title: {title}, Secondary Title: {secondary_title}, Year: {extracted_year}")
            if secondary_title:
                meta['secondary_title'] = secondary_title
            if extracted_year and not meta.get('year'):
                meta['year'] = extracted_year

            guess_name = ntpath.basename(video).replace('-', ' ')

            if title:
                filename = title
            else:
                filename = guessit(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]}).get("title", guessit(re.sub("[^0-9a-zA-Z]+", " ", guess_name), {"excludes": ["country", "language"]})["title"])
            untouched_filename = os.path.basename(video)

            # rely only on guessit for search_year for tv matching
            try:
                meta['search_year'] = guessit(video)['year']
            except Exception:
                meta['search_year'] = ""

            if not meta.get('edit', False):
                mi = await exportInfo(videopath, meta['isdir'], meta['uuid'], base_dir, export_text=True)
                meta['mediainfo'] = mi
            else:
                mi = meta['mediainfo']

            if meta.get('resolution', None) is None:
                meta['resolution'] = await self.get_resolution(guessit(video), meta['uuid'], base_dir)
            meta['sd'] = await self.is_sd(meta['resolution'])

        if " AKA " in filename.replace('.', ' '):
            filename = filename.split('AKA')[0]
        meta['filename'] = filename
        meta['bdinfo'] = bdinfo

        # Check if there's a language restriction
        if meta['has_languages'] is not None:
            audio_languages = await self.get_audio_languages(mi, meta)
            any_of_languages = meta['has_languages'].lower().split(",")
            # We need to have user input languages and file must have audio tracks.
            if len(any_of_languages) > 0 and len(audio_languages) > 0 and not set(any_of_languages).intersection(set(audio_languages)):
                console.print(f"[red] None of the required languages ({meta['has_languages']}) is available on the file {audio_languages}")
                raise Exception("No matching languages")

        # Debugging information after population
        # console.print(f"Debug: meta['filelist'] after population: {meta.get('filelist', 'Not Set')}")

        if 'description' not in meta or meta.get('description') is None:
            meta['description'] = ""

        description_text = meta.get('description', '')
        if description_text is None:
            description_text = ""
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
            if len(description_text):
                description.write(description_text)

        client = Clients(config=config)
        only_id = config['DEFAULT'].get('only_id', False) if not meta.get('only_id') else False

        meta['skip_auto_torrent'] = config['DEFAULT'].get('skip_auto_torrent', False)
        hash_ids = ['infohash', 'torrent_hash', 'skip_auto_torrent']
        tracker_ids = ['ptp', 'bhd', 'hdb', 'blu', 'btn', 'oe', 'aither', 'lst']

        if not any(meta.get(id_type) for id_type in hash_ids + tracker_ids):
            await client.get_pathed_torrents(meta['path'], meta)

        # Ensure all manual IDs have proper default values
        meta['tmdb_manual'] = meta.get('tmdb_manual') or 0
        meta['imdb_manual'] = meta.get('imdb_manual') or 0
        meta['mal_manual'] = meta.get('mal_manual') or 0
        meta['tvdb_manual'] = meta.get('tvdb_manual') or 0
        meta['tvmaze_manual'] = meta.get('tvmaze_manual') or 0

        # Set tmdb_id
        try:
            meta['tmdb_id'] = int(meta['tmdb_manual'])
        except (ValueError, TypeError):
            meta['tmdb_id'] = 0

        # Set imdb_id with proper handling for 'tt' prefix
        try:
            if not meta.get('imdb_id'):
                imdb_value = meta['imdb_manual']
                if imdb_value:
                    if str(imdb_value).startswith('tt'):
                        meta['imdb_id'] = int(str(imdb_value)[2:])
                    else:
                        meta['imdb_id'] = int(imdb_value)
                else:
                    meta['imdb_id'] = 0
        except (ValueError, TypeError):
            meta['imdb_id'] = 0

        # Set mal_id
        try:
            meta['mal_id'] = int(meta['mal_manual'])
        except (ValueError, TypeError):
            meta['mal_id'] = 0

        # Set tvdb_id
        try:
            meta['tvdb_id'] = int(meta['tvdb_manual'])
        except (ValueError, TypeError):
            meta['tvdb_id'] = 0

        try:
            meta['tvmaze_id'] = int(meta['tvmaze_manual'])
        except (ValueError, TypeError):
            meta['tvmaze_id'] = 0

        if meta.get('category', None) is not None:
            meta['category'] = meta['category'].upper()

        if meta.get('infohash') is not None and 'base_torrent_created' in meta and not meta['base_torrent_created']:
            meta = await client.get_ptp_from_hash(meta)
        if not meta.get('image_list') and not meta.get('edit', False):
            # Reuse information from trackers with fallback
            found_match = False

            if search_term:
                # Check if a specific tracker is already set in meta
                tracker_keys = {
                    'ptp': 'PTP',
                    'hdb': 'HDB',
                    'blu': 'BLU',
                    'aither': 'AITHER',
                    'lst': 'LST',
                    'oe': 'OE',
                    'tik': 'TIK',
                    'btn': 'BTN',
                    'bhd': 'BHD',
                }

                specific_tracker = next((tracker_keys[key] for key in tracker_keys if meta.get(key) is not None), None)

                async def process_tracker(tracker_name, meta, only_id):
                    nonlocal found_match
                    if tracker_class_map is None:
                        print(f"Tracker class for {tracker_name} not found.")
                        return meta

                    tracker_instance = tracker_class_map[tracker_name](config=config)
                    try:
                        updated_meta, match = await update_metadata_from_tracker(
                            tracker_name, tracker_instance, meta, search_term, search_file_folder, only_id
                        )
                        if match:
                            found_match = True
                            console.print(f"[green]Match found on tracker: {tracker_name}[/green]")
                        return updated_meta
                    except aiohttp.ClientSSLError:
                        print(f"{tracker_name} tracker request failed due to SSL error.")
                    except requests.exceptions.ConnectionError as conn_err:
                        print(f"{tracker_name} tracker request failed due to connection error: {conn_err}")
                    return meta

                # If a specific tracker is found, process only that tracker
                if specific_tracker:
                    if specific_tracker == "BTN":
                        btn_id = meta.get('btn')
                        btn_api = config['DEFAULT'].get('btn_api')
                        await get_btn_torrents(btn_api, btn_id, meta)
                        if meta.get('imdb_id') != 0:
                            found_match = True
                    elif specific_tracker == "BHD":
                        bhd_api = config['DEFAULT'].get('bhd_api')
                        bhd_rss_key = config['DEFAULT'].get('bhd_rss_key')
                        if meta.get('bhd'):
                            if len(str(meta['bhd'])) > 8:
                                if not meta.get('infohash'):
                                    meta['infohash'] = meta['bhd']
                                await get_bhd_torrents(bhd_api, bhd_rss_key, meta, only_id, info_hash=meta['infohash'])
                                if meta.get('imdb_id') != 0 or meta.get('tmdb_id') != 0:
                                    found_match = True
                            else:
                                await get_bhd_torrents(bhd_api, bhd_rss_key, meta, only_id, torrent_id=meta['bhd'])
                                if meta.get('imdb_id') != 0 or meta.get('tmdb_id') != 0:
                                    found_match = True
                        else:
                            console.print("[yellow]No BHD ID found, skipping BHD tracker update.[/yellow]")
                    else:
                        meta = await process_tracker(specific_tracker, meta, only_id)
                else:
                    # Process all trackers with API = true if no specific tracker is set in meta
                    tracker_order = ["PTP", "BHD", "BLU", "AITHER", "LST", "OE", "TIK", "HDB"]

                    for tracker_name in tracker_order:
                        if not found_match:  # Stop checking once a match is found
                            tracker_config = self.config['TRACKERS'].get(tracker_name, {})
                            if str(tracker_config.get('useAPI', 'false')).lower() == "true":
                                meta = await process_tracker(tracker_name, meta, only_id)

                if not found_match:
                    console.print("[yellow]No matches found on any trackers.[/yellow]")

                if (not meta.get('region') or not meta.get('distributor')) and meta['is_disc'] == "BDMV":
                    from src.trackers.COMMON import COMMON
                    common = COMMON(config)

                    # Prioritize trackers in this order
                    tracker_order = ["BLU", "AITHER", "LST", "OE", "TIK"]

                    # Check if we have stored torrent comments
                    if meta.get('torrent_comments'):
                        # Try to extract tracker IDs from stored comments
                        for tracker_name in tracker_order:
                            # Skip if we already have region and distributor
                            if meta.get('region') and meta.get('distributor'):
                                break

                            tracker_id = None
                            tracker_key = tracker_name.lower()
                            # Check each stored comment for matching tracker URL
                            for comment_data in meta.get('torrent_comments', []):
                                comment = comment_data.get('comment', '')

                                if "blutopia.cc" in comment and tracker_name == "BLU":
                                    match = re.search(r'/(\d+)$', comment)
                                    if match:
                                        tracker_id = match.group(1)
                                        meta[tracker_key] = tracker_id
                                        break
                                elif "aither.cc" in comment and tracker_name == "AITHER":
                                    match = re.search(r'/(\d+)$', comment)
                                    if match:
                                        tracker_id = match.group(1)
                                        meta[tracker_key] = tracker_id
                                        break
                                elif "lst.gg" in comment and tracker_name == "LST":
                                    match = re.search(r'/(\d+)$', comment)
                                    if match:
                                        tracker_id = match.group(1)
                                        meta[tracker_key] = tracker_id
                                        break
                                elif "onlyencodes.cc" in comment and tracker_name == "OE":
                                    match = re.search(r'/(\d+)$', comment)
                                    if match:
                                        tracker_id = match.group(1)
                                        meta[tracker_key] = tracker_id
                                        break
                                elif "cinematik.net" in comment and tracker_name == "TIK":
                                    match = re.search(r'/(\d+)$', comment)
                                    if match:
                                        tracker_id = match.group(1)
                                        meta[tracker_key] = tracker_id
                                        break

                            # If we found a tracker ID, try to get region/distributor data
                            if tracker_id:
                                if meta.get('debug', False):
                                    console.print(f"[cyan]Using {tracker_name} ID {tracker_id} to get region/distributor info[/cyan]")
                                # Get the tracker instance
                                tracker_instance = tracker_class_map[tracker_name](config=config)
                                # Try to get region/distributor data
                                await common.unit3d_region_distributor(meta, tracker_name, tracker_instance.torrent_url, tracker_id)
                                # Stop if we found both region and distributor
                                if meta.get('region') and meta.get('distributor'):
                                    if meta.get('debug', False):
                                        console.print(f"[green]Successfully found region and distributor from {tracker_name}[/green]")
                                    break

            else:
                console.print("[yellow]Warning: No valid search term available, skipping tracker updates.[/yellow]")
        else:
            console.print("Skipping existing search as meta already populated")

        user_overrides = config['DEFAULT'].get('user_overrides', False)
        if user_overrides and (meta.get('imdb_id') != 0 or meta.get('tvdb_id') != 0):
            meta = await self.get_source_override(meta, other_id=True)
            meta['no_override'] = True

        if meta['debug']:
            console.print("ID inputs into prep")
            console.print("category:", meta.get("category"))
            console.print(f"Raw TVDB ID: {meta['tvdb_id']} (type: {type(meta['tvdb_id']).__name__})")
            console.print(f"Raw IMDb ID: {meta['imdb_id']} (type: {type(meta['imdb_id']).__name__})")
            console.print(f"Raw TMDb ID: {meta['tmdb_id']} (type: {type(meta['tmdb_id']).__name__})")
            console.print(f"Raw TVMAZE ID: {meta['tvmaze_id']} (type: {type(meta['tvmaze_id']).__name__})")
            console.print(f"Raw MAL ID: {meta['mal_id']} (type: {type(meta['mal_id']).__name__})")
        console.print("[yellow]Building meta data.....")
        if meta['debug']:
            meta_start_time = time.time()
        if meta.get('manual_language'):
            meta['original_langauge'] = meta.get('manual_language').lower()
        meta['type'] = await self.get_type(video, meta['scene'], meta['is_disc'], meta)
        if meta.get('category', None) is None:
            meta['category'] = await self.get_cat(video)
        else:
            meta['category'] = meta['category'].upper()

        if meta.get("not_anime", False) and meta.get("category") == "TV":
            meta = await get_season_episode(video, meta)

        meta['we_checked_tvdb'] = False
        meta['we_checked_tmdb'] = False
        meta['we_asked_tvmaze'] = False

        # if we have all of the ids, search everything all at once
        if int(meta['imdb_id']) != 0 and int(meta['tvdb_id']) != 0 and int(meta['tmdb_id']) != 0 and int(meta['tvmaze_id']) != 0:
            # Create a list of all tasks to run in parallel
            all_tasks = [
                # Core metadata tasks
                tmdb_other_meta(
                    tmdb_id=meta['tmdb_id'],
                    path=meta.get('path'),
                    search_year=meta.get('search_year'),
                    category=meta.get('category'),
                    imdb_id=meta.get('imdb_id', 0),
                    manual_language=meta.get('manual_language'),
                    anime=meta.get('anime', False),
                    mal_manual=meta.get('mal_manual'),
                    aka=meta.get('aka', ''),
                    original_language=meta.get('original_language'),
                    poster=meta.get('poster'),
                    debug=meta.get('debug', False),
                    mode=meta.get('mode', 'cli'),
                    tvdb_id=meta.get('tvdb_id', 0)
                ),
                get_imdb_info_api(
                    meta['imdb_id'],
                    manual_language=meta.get('manual_language'),
                    debug=meta.get('debug', False)
                )
            ]

            # Add episode-specific tasks if this is a TV show with episodes
            if (meta['category'] == 'TV' and not meta.get('tv_pack', False) and
                    'season_int' in meta and 'episode_int' in meta and meta.get('episode_int') != 0):

                # Add TVDb task if we have credentials
                if tvdb_api and tvdb_token:
                    all_tasks.append(
                        get_tvdb_episode_data(
                            meta['base_dir'],
                            tvdb_token,
                            meta.get('tvdb_id'),
                            meta.get('season_int'),
                            meta.get('episode_int'),
                            api_key=tvdb_api,
                            debug=meta.get('debug', False)
                        )
                    )

                # Add TMDb episode details task
                all_tasks.append(
                    get_episode_details(
                        meta.get('tmdb_id'),
                        meta.get('season_int'),
                        meta.get('episode_int'),
                        debug=meta.get('debug', False)
                    )
                )

                # Add TVMaze episode data task
                all_tasks.append(
                    get_tvmaze_episode_data(
                        meta.get('tvmaze_id'),
                        meta.get('season_int'),
                        meta.get('episode_int')
                    )
                )

            # Execute all tasks in parallel
            results = await asyncio.gather(*all_tasks, return_exceptions=True)

            # Process core metadata results
            tmdb_metadata, imdb_info = results[0:2]
            result_index = 2  # Start processing episode data from this index

            # Process TMDB metadata
            if not isinstance(tmdb_metadata, Exception) and tmdb_metadata:
                meta.update(tmdb_metadata)
            else:
                console.print("[yellow]Warning: Could not get TMDB metadata")

            # Process IMDB info
            if isinstance(imdb_info, dict):
                meta['imdb_info'] = imdb_info
                meta['tv_year'] = imdb_info.get('tv_year', None)
            elif isinstance(imdb_info, Exception):
                console.print(f"[red]IMDb API call failed: {imdb_info}[/red]")
                meta['imdb_info'] = meta.get('imdb_info', {})  # Keep previous IMDb info if it exists
            else:
                console.print("[red]Unexpected IMDb response, setting imdb_info to empty.[/red]")
                meta['imdb_info'] = {}

            # Process episode data if this is a TV show
            if meta['category'] == 'TV' and not meta.get('tv_pack', False) and meta.get('episode_int', 0) != 0:
                # Process TVDb episode data (if included)
                if tvdb_api and tvdb_token:
                    tvdb_episode_data = results[result_index]
                    result_index += 1

                    if tvdb_episode_data and not isinstance(tvdb_episode_data, Exception):
                        console.print("[green]TVDB episode data retrieved successfully.[/green]")
                        meta['tvdb_episode_data'] = tvdb_episode_data
                        meta['we_checked_tvdb'] = True

                        # Process episode name
                        if meta['tvdb_episode_data'].get('episode_name'):
                            episode_name = meta['tvdb_episode_data'].get('episode_name')
                            if episode_name and isinstance(episode_name, str) and episode_name.strip():
                                if 'episode' in episode_name.lower():
                                    meta['auto_episode_title'] = None
                                    meta['tvdb_episode_title'] = None
                                else:
                                    meta['tvdb_episode_title'] = episode_name.strip()
                                    meta['auto_episode_title'] = episode_name.strip()
                            else:
                                meta['auto_episode_title'] = None

                        # Process overview
                        if meta['tvdb_episode_data'].get('overview') and meta.get('original_language') == "en":
                            overview = meta['tvdb_episode_data'].get('overview')
                            if overview and isinstance(overview, str) and overview.strip():
                                meta['overview_meta'] = overview.strip()
                            else:
                                meta['overview_meta'] = None
                        else:
                            meta['overview_meta'] = None

                        # Process season and episode numbers
                        if meta['tvdb_episode_data'].get('season_name'):
                            meta['tvdb_season_name'] = meta['tvdb_episode_data'].get('season_name')

                        if meta['tvdb_episode_data'].get('season_number'):
                            meta['tvdb_season_number'] = meta['tvdb_episode_data'].get('season_number')

                        if meta['tvdb_episode_data'].get('episode_number'):
                            meta['tvdb_episode_number'] = meta['tvdb_episode_data'].get('episode_number')

                        if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('series_name'):
                            year = meta['tvdb_episode_data'].get('series_name')
                            year_match = re.search(r'\b(19\d\d|20[0-3]\d)\b', year)
                            if year_match:
                                meta['search_year'] = year_match.group(0)
                            else:
                                meta['search_year'] = ""

                    elif isinstance(tvdb_episode_data, Exception):
                        console.print(f"[yellow]TVDb episode data retrieval failed: {tvdb_episode_data}")

                # Process TMDb episode data
                tmdb_episode_data = results[result_index]
                result_index += 1

                if not isinstance(tmdb_episode_data, Exception) and tmdb_episode_data:
                    meta['tmdb_episode_data'] = tmdb_episode_data
                    meta['we_checked_tmdb'] = True

                    # Only set title if not already set
                    if meta.get('auto_episode_title') is None and tmdb_episode_data.get('name') is not None:
                        if 'episode' in tmdb_episode_data.get('name', '').lower():
                            meta['auto_episode_title'] = None
                        else:
                            meta['auto_episode_title'] = tmdb_episode_data['name']

                    # Only set overview if not already set
                    if meta.get('overview_meta') is None and tmdb_episode_data.get('overview') is not None:
                        meta['overview_meta'] = tmdb_episode_data.get('overview', None)
                elif isinstance(tmdb_episode_data, Exception):
                    console.print(f"[yellow]TMDb episode data retrieval failed: {tmdb_episode_data}")

                # Process TVMaze episode data
                if result_index < len(results):
                    tvmaze_episode_data = results[result_index]

                    if not isinstance(tvmaze_episode_data, Exception) and tvmaze_episode_data:
                        meta['tvmaze_episode_data'] = tvmaze_episode_data

                        # Only set title if not already set
                        if meta.get('auto_episode_title') is None and tvmaze_episode_data.get('name') is not None:
                            if 'episode' in tvmaze_episode_data.get('name', '').lower():
                                meta['auto_episode_title'] = None
                            else:
                                meta['auto_episode_title'] = tvmaze_episode_data['name']

                        # Only set overview if not already set
                        if meta.get('overview_meta') is None and tvmaze_episode_data.get('summary') is not None:
                            meta['overview_meta'] = tvmaze_episode_data.get('summary', None)
                        meta['we_asked_tvmaze'] = True
                    elif isinstance(tvmaze_episode_data, Exception):
                        console.print(f"[yellow]TVMaze episode data retrieval failed: {tvmaze_episode_data}")

        # Check if both IMDb and TVDB IDs are present first
        elif int(meta['imdb_id']) != 0 and int(meta['tvdb_id']) != 0:
            tasks = [
                get_tmdb_from_imdb(
                    meta['imdb_id'],
                    meta.get('tvdb_id'),
                    meta.get('search_year'),
                    filename,
                    debug=meta.get('debug', False),
                    mode=meta.get('mode', 'discord')
                ),
                search_tvmaze(
                    filename, meta['search_year'], meta.get('imdb_id', 0), meta.get('tvdb_id', 0),
                    manual_date=meta.get('manual_date'),
                    tvmaze_manual=meta.get('tvmaze_manual'),
                    debug=meta.get('debug', False),
                    return_full_tuple=False
                ),
                get_imdb_info_api(
                    meta['imdb_id'],
                    manual_language=meta.get('manual_language'),
                    debug=meta.get('debug', False)
                )
            ]

            # Add TVDb tasks if we have credentials and it's a TV show with episodes
            add_tvdb_tasks = (
                tvdb_api and tvdb_token and
                'season_int' in meta and 'episode_int' in meta and
                meta.get('category') == 'TV' and
                not meta.get('tv_pack', False) and
                meta.get('episode_int') != 0
            )

            if add_tvdb_tasks:
                tvdb_episode_data = await get_tvdb_episode_data(
                    meta['base_dir'],
                    tvdb_token,
                    meta.get('tvdb_id'),
                    meta.get('season_int'),
                    meta.get('episode_int'),
                    api_key=tvdb_api,
                    debug=meta.get('debug', False)
                )

                if tvdb_episode_data:
                    meta['tvdb_episode_data'] = tvdb_episode_data
                    meta['we_checked_tvdb'] = True

                    # Process episode name
                    if meta['tvdb_episode_data'].get('episode_name'):
                        episode_name = meta['tvdb_episode_data'].get('episode_name')
                        if episode_name and isinstance(episode_name, str) and episode_name.strip():
                            if 'episode' in episode_name.lower():
                                meta['auto_episode_title'] = None
                                meta['tvdb_episode_title'] = None
                            else:
                                meta['tvdb_episode_title'] = episode_name.strip()
                                meta['auto_episode_title'] = episode_name.strip()
                        else:
                            meta['auto_episode_title'] = None

                    # Process overview
                    if meta['tvdb_episode_data'].get('overview') and meta.get('original_language') == "en":
                        overview = meta['tvdb_episode_data'].get('overview')
                        if overview and isinstance(overview, str) and overview.strip():
                            meta['overview_meta'] = overview.strip()
                        else:
                            meta['overview_meta'] = None
                    else:
                        meta['overview_meta'] = None

                    if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('series_name'):
                        year = meta['tvdb_episode_data'].get('series_name')
                        year_match = re.search(r'\b(19\d\d|20[0-3]\d)\b', year)
                        if year_match:
                            meta['search_year'] = year_match.group(0)
                        else:
                            meta['search_year'] = ""

            results = await asyncio.gather(*tasks, return_exceptions=True)
            tmdb_result, tvmaze_id, imdb_info_result = results[:3]
            if isinstance(tmdb_result, tuple) and len(tmdb_result) == 3:
                meta['category'], meta['tmdb_id'], meta['original_language'] = tmdb_result

            meta['tvmaze_id'] = tvmaze_id if isinstance(tvmaze_id, int) else 0

            if isinstance(imdb_info_result, dict):
                meta['imdb_info'] = imdb_info_result
                meta['tv_year'] = imdb_info_result.get('tv_year', None)
            elif isinstance(imdb_info_result, Exception):
                console.print(f"[red]IMDb API call failed: {imdb_info_result}[/red]")
                meta['imdb_info'] = meta.get('imdb_info', {})  # Keep previous IMDb info if it exists
            else:
                console.print("[red]Unexpected IMDb response, setting imdb_info to empty.[/red]")
                meta['imdb_info'] = {}

        # Check if both IMDb and TMDb IDs are present next
        elif int(meta['imdb_id']) != 0 and int(meta['tmdb_id']) != 0:
            # Create a list of coroutines to run concurrently
            coroutines = [
                tmdb_other_meta(
                    tmdb_id=meta['tmdb_id'],
                    path=meta.get('path'),
                    search_year=meta.get('search_year'),
                    category=meta.get('category'),
                    imdb_id=meta.get('imdb_id', 0),
                    manual_language=meta.get('manual_language'),
                    anime=meta.get('anime', False),
                    mal_manual=meta.get('mal_manual'),
                    aka=meta.get('aka', ''),
                    original_language=meta.get('original_language'),
                    poster=meta.get('poster'),
                    debug=meta.get('debug', False),
                    mode=meta.get('mode', 'cli'),
                    tvdb_id=meta.get('tvdb_id', 0)
                ),
                get_imdb_info_api(
                    meta['imdb_id'],
                    manual_language=meta.get('manual_language'),
                    debug=meta.get('debug', False)
                )
            ]

            # Add TVMaze search if it's a TV category
            if meta['category'] == 'TV':
                coroutines.append(
                    search_tvmaze(
                        filename, meta['search_year'], meta.get('imdb_id', 0), meta.get('tvdb_id', 0),
                        manual_date=meta.get('manual_date'),
                        tvmaze_manual=meta.get('tvmaze_manual'),
                        debug=meta.get('debug', False),
                        return_full_tuple=False
                    )
                )

                # Add TMDb episode details if it's a TV show with episodes
                if ('season_int' in meta and 'episode_int' in meta and
                        not meta.get('tv_pack', False) and
                        meta.get('episode_int') != 0):
                    coroutines.append(
                        get_episode_details(
                            meta.get('tmdb_id'),
                            meta.get('season_int'),
                            meta.get('episode_int'),
                            debug=meta.get('debug', False)
                        )
                    )

            # Gather results
            results = await asyncio.gather(*coroutines, return_exceptions=True)

            # Process the results
            if isinstance(results[0], Exception):
                error_msg = f"TMDB metadata retrieval failed: {str(results[0])}"
                console.print(f"[bold red]{error_msg}[/bold red]")
                raise RuntimeError(error_msg)
            elif not results[0]:  # Check if the result is empty (empty dict)
                error_msg = f"Failed to retrieve essential metadata from TMDB ID: {meta['tmdb_id']}"
                console.print(f"[bold red]{error_msg}[/bold red]")
                raise ValueError(error_msg)
            else:
                tmdb_metadata = results[0]

            # Update meta with TMDB metadata
            if tmdb_metadata:
                meta.update(tmdb_metadata)

            imdb_info_result = results[1]

            # Process IMDb info
            if isinstance(imdb_info_result, dict):
                meta['imdb_info'] = imdb_info_result
                meta['tv_year'] = imdb_info_result.get('tv_year', None)
            elif isinstance(imdb_info_result, Exception):
                console.print(f"[red]IMDb API call failed: {imdb_info_result}[/red]")
                meta['imdb_info'] = meta.get('imdb_info', {})  # Keep previous IMDb info if it exists
            else:
                console.print("[red]Unexpected IMDb response, setting imdb_info to empty.[/red]")
                meta['imdb_info'] = {}

            # Process TVMaze results if it was included
            if meta['category'] == 'TV':
                if len(results) > 2:
                    tvmaze_result = results[2]
                    if isinstance(tvmaze_result, int):
                        meta['tvmaze_id'] = tvmaze_result
                    elif isinstance(tvmaze_result, Exception):
                        console.print(f"[red]TVMaze API call failed: {tvmaze_result}[/red]")
                        meta['tvmaze_id'] = 0  # Set default value if an exception occurred

                # Process TMDb episode details if they were included
                if len(results) > 3:
                    episode_details_result = results[3]
                    if isinstance(episode_details_result, dict):
                        meta['tmdb_episode_data'] = episode_details_result
                        meta['we_checked_tmdb'] = True

                        # Only set episode title if not already set and if the title doesn't just contain "Episode"
                        if meta.get('auto_episode_title') is None and episode_details_result.get('name') is not None:
                            if 'episode' in episode_details_result.get('name', '').lower():
                                meta['auto_episode_title'] = None
                            else:
                                meta['auto_episode_title'] = episode_details_result['name']

                        # Only set overview if not already set
                        if meta.get('overview_meta') is None and episode_details_result.get('overview') is not None:
                            meta['overview_meta'] = episode_details_result.get('overview', None)

                    elif isinstance(episode_details_result, Exception):
                        console.print(f"[red]TMDb episode details API call failed: {episode_details_result}[/red]")

        # Get TMDB and IMDb metadata only if IDs are still missing
        if meta.get('tmdb_id') == 0 and meta.get('imdb_id') == 0:
            console.print("Fetching TMDB ID...")
            meta['category'], meta['tmdb_id'], meta['imdb_id'] = await get_tmdb_imdb_from_mediainfo(
                mi, meta['category'], meta['is_disc'], meta['tmdb_id'], meta['imdb_id']
            )
        if meta.get('tmdb_id') == 0 and meta.get('imdb_id') == 0:
            console.print("Fetching TMDB ID from filename...")
            meta = await get_tmdb_id(filename, meta['search_year'], meta, meta['category'], untouched_filename)
        elif meta.get('imdb_id') != 0 and meta.get('tmdb_id') == 0:
            category, tmdb_id, original_language = await get_tmdb_from_imdb(
                meta['imdb_id'],
                meta.get('tvdb_id'),
                meta.get('search_year'),
                filename,
                debug=meta.get('debug', False),
                mode=meta.get('mode', 'discord')
            )

            meta['category'] = category
            meta['tmdb_id'] = int(tmdb_id)
            meta['original_language'] = original_language
        # Fetch TMDB metadata if available
        if int(meta['tmdb_id']) != 0:
            # Check if essential TMDB metadata is already populated
            if not meta.get('edit', False):
                essential_fields = ['title', 'year', 'genres', 'overview']
                tmdb_metadata_populated = all(meta.get(field) is not None for field in essential_fields)
            else:
                tmdb_metadata_populated = False

            if not tmdb_metadata_populated:
                console.print("Fetching TMDB metadata...")
                try:
                    # Extract only the needed parameters
                    tmdb_metadata = await tmdb_other_meta(
                        tmdb_id=meta['tmdb_id'],
                        path=meta.get('path'),
                        search_year=meta.get('search_year'),
                        category=meta.get('category'),
                        imdb_id=meta.get('imdb_id', 0),
                        manual_language=meta.get('manual_language'),
                        anime=meta.get('anime', False),
                        mal_manual=meta.get('mal_manual'),
                        aka=meta.get('aka', ''),
                        original_language=meta.get('original_language'),
                        poster=meta.get('poster'),
                        debug=meta.get('debug', False),
                        mode=meta.get('mode', 'cli'),
                        tvdb_id=meta.get('tvdb_id', 0)
                    )

                    # Check if the metadata is empty or missing essential fields
                    if not tmdb_metadata or not all(tmdb_metadata.get(field) for field in ['title', 'year']):
                        error_msg = f"Failed to retrieve essential metadata from TMDB ID: {meta['tmdb_id']}"
                        console.print(f"[bold red]{error_msg}[/bold red]")
                        raise ValueError(error_msg)

                    # Update meta with return values from tmdb_other_meta
                    meta.update(tmdb_metadata)

                except Exception as e:
                    error_msg = f"TMDB metadata retrieval failed for ID {meta['tmdb_id']}: {str(e)}"
                    console.print(f"[bold red]{error_msg}[/bold red]")
                    raise RuntimeError(error_msg) from e
        # Search TVMaze only if it's a TV category and tvmaze_id is still missing
        if meta['category'] == "TV":
            if meta.get('tvmaze_id', 0) == 0:
                meta['tvmaze_id'], meta['imdb_id'], meta['tvdb_id'] = await search_tvmaze(
                    filename, meta['search_year'], meta.get('imdb_id', 0), meta.get('tvdb_id', 0),
                    manual_date=meta.get('manual_date'),
                    tvmaze_manual=meta.get('tvmaze_manual'),
                    debug=meta.get('debug', False),
                    return_full_tuple=True
                )
        else:
            meta.setdefault('tvmaze_id', 0)

        meta['tvmaze'] = meta.get('tvmaze_id', 0)
        # If no IMDb ID, search for it
        if meta.get('imdb_id') == 0:
            meta['imdb_id'] = await search_imdb(filename, meta['search_year'])
        # Ensure IMDb info is retrieved if it wasn't already fetched
        if meta.get('imdb_info', None) is None and int(meta['imdb_id']) != 0:
            imdb_info = await get_imdb_info_api(meta['imdb_id'], manual_language=meta.get('manual_language'), debug=meta.get('debug', False))
            meta['imdb_info'] = imdb_info
            meta['tv_year'] = imdb_info.get('tv_year', None)

            aka = meta.get('imdb_info', {}).get('aka', "").strip()
            title = meta.get('imdb_info', {}).get('title', "").strip().lower()
            year = str(meta.get('imdb_info', {}).get('year', ""))

            if aka and not meta.get('aka'):
                aka_trimmed = aka[5:].strip().lower() if len(aka) > 5 else aka.lower()
                difference = SequenceMatcher(None, title, aka_trimmed).ratio()
                if difference >= 0.9 or not aka_trimmed or aka_trimmed in title:
                    aka = None

                if aka is not None:
                    if f"({year})" in aka:
                        aka = aka.replace(f"({year})", "").strip()

                    meta['aka'] = f"AKA {aka}"
        if meta.get('tag', None) is None:
            meta['tag'] = await self.get_tag(video, meta)
        else:
            if not meta['tag'].startswith('-') and meta['tag'] != "":
                meta['tag'] = f"-{meta['tag']}"

        if meta['category'] == "TV":
            if not meta.get('not_anime', False):
                meta = await get_season_episode(video, meta)
            if not meta.get('tv_pack', False) and meta.get('episode_int') != 0:
                if not meta.get('auto_episode_title') or not meta.get('overview_meta'):
                    # prioritze tvdb metadata if available
                    if tvdb_api and tvdb_token and not meta.get('we_checked_tvdb', False):
                        console.print("[yellow]Fetching TVDb metadata...")
                        meta['tvdb_season_int'], meta['tvdb_episode_int'] = await get_tvdb_series_episodes(base_dir, tvdb_token, meta.get('tvdb_id'), meta.get('season_int'), meta.get('episode_int'), tvdb_api, debug=meta.get('debug', False))
                        tvdb_episode_data = await get_tvdb_episode_data(base_dir, tvdb_token, meta['tvdb_id'], meta.get('tvdb_season_int'), meta.get('tvdb_episode_int'), api_key=tvdb_api, debug=meta.get('debug', False))
                        if tvdb_episode_data:
                            meta['tvdb_episode_data'] = tvdb_episode_data

                            if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('episode_name') and meta.get('auto_episode_title') is None:
                                episode_name = meta['tvdb_episode_data'].get('episode_name')
                                if episode_name and isinstance(episode_name, str) and episode_name.strip():
                                    if 'episode' in episode_name.lower():
                                        meta['auto_episode_title'] = None
                                        meta['tvdb_episode_title'] = None
                                    else:
                                        meta['tvdb_episode_title'] = episode_name.strip()
                                        meta['auto_episode_title'] = episode_name.strip()
                                else:
                                    meta['auto_episode_title'] = None

                            if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('overview') and meta.get('original_language') == "en":
                                overview = meta['tvdb_episode_data'].get('overview')
                                if overview and isinstance(overview, str) and overview.strip():
                                    meta['overview_meta'] = overview.strip()
                                else:
                                    meta['overview_meta'] = None
                            else:
                                meta['overview_meta'] = None

                            if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('season_name'):
                                meta['tvdb_season_name'] = meta['tvdb_episode_data'].get('season_name')

                            if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('season_number'):
                                meta['tvdb_season_number'] = meta['tvdb_episode_data'].get('season_number')

                            if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('episode_number'):
                                meta['tvdb_episode_number'] = meta['tvdb_episode_data'].get('episode_number')

                            if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('series_name'):
                                year = meta['tvdb_episode_data'].get('series_name')
                                year_match = re.search(r'\b(19\d\d|20[0-3]\d)\b', year)
                                if year_match:
                                    meta['search_year'] = year_match.group(0)
                                else:
                                    meta['search_year'] = ""

                    # fallback to tmdb data if tvdb data is not available
                    if (meta.get('auto_episode_title') is None or meta.get('overview_meta') is None) and not meta.get('we_checked_tmdb', False):
                        if meta.get('tvdb_episode_int') != meta.get('episode_int'):
                            episode = meta.get('episode_int')
                            season = meta.get('tvdb_season_int')
                            if meta['debug']:
                                console.print(f"[yellow]Using absolute episode number from TVDb: {episode}[/yellow]")
                                console.print(f"[yellow]Using matching season number from TVDb: {season}[/yellow]")
                        else:
                            episode = meta.get('episode_int')
                            season = meta.get('season_int')
                        console.print("[yellow]Fetching TMDb episode metadata...")
                        episode_details = await get_episode_details(meta.get('tmdb_id'), season, episode, debug=meta.get('debug', False))
                        if meta.get('auto_episode_title') is None and episode_details.get('name') is not None:
                            if 'episode' in episode_details.get("name").lower():
                                meta['auto_episode_title'] = None
                            else:
                                meta['auto_episode_title'] = episode_details['name']
                        if meta.get('overview_meta') is None and episode_details.get('overview') is not None:
                            meta['overview_meta'] = episode_details.get('overview', None)

                    # fallback to tvmaze data if no other data is available
                    if meta.get('auto_episode_title') is None or meta.get('overview_meta') is None and not meta.get('we_asked_tvmaze', False):
                        if meta.get('tvdb_episode_int') == meta.get('episode_int'):
                            console.print("[yellow]Fetching TVMaze episode metadata...")
                            tvmaze_episode_data = await get_tvmaze_episode_data(meta.get('tvmaze_id'), meta.get('season_int'), meta.get('episode_int'))
                            if tvmaze_episode_data:
                                meta['tvmaze_episode_data'] = tvmaze_episode_data
                                if meta.get('auto_episode_title') is None and tvmaze_episode_data.get('name') is not None:
                                    if 'episode' in tvmaze_episode_data.get("name").lower():
                                        meta['auto_episode_title'] = None
                                    else:
                                        meta['auto_episode_title'] = tvmaze_episode_data['name']
                                if meta.get('overview_meta') is None and tvmaze_episode_data.get('summary') is not None:
                                    meta['overview_meta'] = tvmaze_episode_data.get('summary', None)
                        else:
                            if meta['debug']:
                                console.print("[yellow]Skipping TVMAZE episode retrieval due to mismatched episode numbers.[/yellow]")

                    if 'tvdb_season_int' in meta and meta['tvdb_season_int'] and meta['tvdb_episode_int'] != 0:
                        meta['episode_int'] = meta['tvdb_episode_int']
                        meta['season_int'] = meta['tvdb_season_int']
                        meta['season'] = "S" + str(meta['season_int']).zfill(2)
                        meta['episode'] = "E" + str(meta['episode_int']).zfill(2)

        meta = await self.tag_override(meta)

        if user_overrides and not meta.get('no_override', False):
            meta = await self.get_source_override(meta)
        if meta.get('tag') == "-SubsPlease":  # SubsPlease-specific
            tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])  # Get all tracks
            bitrate = tracks[1].get('BitRate', '') if len(tracks) > 1 and not isinstance(tracks[1].get('BitRate', ''), dict) else ''  # Check that bitrate is not a dict
            bitrate_oldMediaInfo = tracks[0].get('OverallBitRate', '') if len(tracks) > 0 and not isinstance(tracks[0].get('OverallBitRate', ''), dict) else ''  # Check for old MediaInfo
            meta['episode_title'] = ""
            if (bitrate.isdigit() and int(bitrate) >= 8000000) or (bitrate_oldMediaInfo.isdigit() and int(bitrate_oldMediaInfo) >= 8000000) and meta.get('resolution') == "1080p":  # 8Mbps for 1080p
                meta['service'] = "CR"
            elif (bitrate.isdigit() or bitrate_oldMediaInfo.isdigit()) and meta.get('resolution') == "1080p":  # Only assign if at least one bitrate is present, otherwise leave it to user
                meta['service'] = "HIDI"
            elif (bitrate.isdigit() and int(bitrate) >= 4000000) or (bitrate_oldMediaInfo.isdigit() and int(bitrate_oldMediaInfo) >= 4000000) and meta.get('resolution') == "720p":  # 4Mbps for 720p
                meta['service'] = "CR"
            elif (bitrate.isdigit() or bitrate_oldMediaInfo.isdigit()) and meta.get('resolution') == "720p":
                meta['service'] = "HIDI"
        meta['video'] = video
        meta['audio'], meta['channels'], meta['has_commentary'] = await self.get_audio_v2(mi, meta, bdinfo)
        if meta['tag'][1:].startswith(meta['channels']):
            meta['tag'] = meta['tag'].replace(f"-{meta['channels']}", '')
        if meta.get('no_tag', False):
            meta['tag'] = ""
        meta['3D'] = await self.is_3d(mi, bdinfo)
        if meta.get('manual_source', None):
            meta['source'] = meta['manual_source']
            _, meta['type'] = await self.get_source(meta['type'], video, meta['path'], meta['is_disc'], meta, folder_id, base_dir)
        else:
            meta['source'], meta['type'] = await self.get_source(meta['type'], video, meta['path'], meta['is_disc'], meta, folder_id, base_dir)
        if meta.get('service', None) in (None, ''):
            meta['service'], meta['service_longname'] = await get_service(video, meta.get('tag', ''), meta['audio'], meta['filename'])
        elif meta.get('service'):
            services = await get_service(get_services_only=True)
            meta['service_longname'] = max((k for k, v in services.items() if v == meta['service']), key=len, default=meta['service'])
        meta['uhd'] = await self.get_uhd(meta['type'], guessit(meta['path']), meta['resolution'], meta['path'])
        meta['hdr'] = await self.get_hdr(mi, bdinfo)
        meta['distributor'] = await get_distributor(meta['distributor'])
        if meta.get('is_disc', None) == "BDMV":  # Blu-ray Specific
            meta['region'] = await get_region(bdinfo, meta.get('region', None))
            meta['video_codec'] = await self.get_video_codec(bdinfo)
        else:
            meta['video_encode'], meta['video_codec'], meta['has_encode_settings'], meta['bit_depth'] = await self.get_video_encode(mi, meta['type'], bdinfo)
        if meta.get('no_edition') is False:
            meta['edition'], meta['repack'] = await self.get_edition(meta['path'], bdinfo, meta['filelist'], meta.get('manual_edition'), meta)
            if "REPACK" in meta.get('edition', ""):
                meta['repack'] = re.search(r"REPACK[\d]?", meta['edition'])[0]
                meta['edition'] = re.sub(r"REPACK[\d]?", "", meta['edition']).strip().replace('  ', ' ')
        else:
            meta['edition'] = ""

        meta.get('stream', False)
        meta['stream'] = await self.stream_optimized(meta['stream'])
        meta.get('anon', False)
        meta['anon'] = self.is_anon(meta['anon'])

        # return duplicate ids so I don't have to catch every site file
        meta['tmdb'] = meta.get('tmdb_id')
        if int(meta.get('imdb_id')) != 0:
            imdb_str = str(meta['imdb_id']).zfill(7)
            meta['imdb'] = imdb_str
        else:
            meta['imdb'] = '0'
        meta['mal'] = meta.get('mal_id')
        meta['tvdb'] = meta.get('tvdb_id')

        if meta['debug']:
            meta_finish_time = time.time()
            console.print(f"Metadata processed in {meta_finish_time - meta_start_time:.2f} seconds")

        return meta

    """
    Determine if disc and if so, get bdinfo
    """
    async def get_disc(self, meta):
        is_disc = None
        videoloc = meta['path']
        bdinfo = None
        bd_summary = None  # noqa: F841
        discs = []
        parse = DiscParse()
        for path, directories, files in sorted(os.walk(meta['path'])):
            for each in directories:
                if each.upper() == "BDMV":  # BDMVs
                    is_disc = "BDMV"
                    disc = {
                        'path': f"{path}/{each}",
                        'name': os.path.basename(path),
                        'type': 'BDMV',
                        'summary': "",
                        'bdinfo': ""
                    }
                    discs.append(disc)
                elif each == "VIDEO_TS":  # DVDs
                    is_disc = "DVD"
                    disc = {
                        'path': f"{path}/{each}",
                        'name': os.path.basename(path),
                        'type': 'DVD',
                        'vob_mi': '',
                        'ifo_mi': '',
                        'main_set': [],
                        'size': ""
                    }
                    discs.append(disc)
                elif each == "HVDVD_TS":
                    is_disc = "HDDVD"
                    disc = {
                        'path': f"{path}/{each}",
                        'name': os.path.basename(path),
                        'type': 'HDDVD',
                        'evo_mi': '',
                        'largest_evo': ""
                    }
                    discs.append(disc)
        if is_disc == "BDMV":
            if meta.get('edit', False) is False:
                discs, bdinfo = await parse.get_bdinfo(meta, discs, meta['uuid'], meta['base_dir'], meta.get('discs', []))
            else:
                discs, bdinfo = await parse.get_bdinfo(meta, meta['discs'], meta['uuid'], meta['base_dir'], meta['discs'])
        elif is_disc == "DVD":
            discs = await parse.get_dvdinfo(discs)
            export = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'w', newline="", encoding='utf-8')
            export.write(discs[0]['ifo_mi'])
            export.close()
            export_clean = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'w', newline="", encoding='utf-8')
            export_clean.write(discs[0]['ifo_mi'])
            export_clean.close()
        elif is_disc == "HDDVD":
            discs = await parse.get_hddvd_info(discs, meta)
            export = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'w', newline="", encoding='utf-8')
            export.write(discs[0]['evo_mi'])
            export.close()
        discs = sorted(discs, key=lambda d: d['name'])
        return is_disc, videoloc, bdinfo, discs

    """
    Get video files

    """
    async def get_video(self, videoloc, mode):
        filelist = []
        videoloc = os.path.abspath(videoloc)
        if os.path.isdir(videoloc):
            globlist = glob.glob1(videoloc, "*.mkv") + glob.glob1(videoloc, "*.mp4") + glob.glob1(videoloc, "*.ts")
            for file in globlist:
                if not file.lower().endswith('sample.mkv') or "!sample" in file.lower():
                    filelist.append(os.path.abspath(f"{videoloc}{os.sep}{file}"))
            try:
                video = sorted(filelist)[0]
            except IndexError:
                console.print("[bold red]No Video files found")
                if mode == 'cli':
                    exit()
        else:
            video = videoloc
            filelist.append(videoloc)
        filelist = sorted(filelist)
        return video, filelist

    """
    Get Resolution
    """

    async def get_resolution(self, guess, folder_id, base_dir):
        with open(f'{base_dir}/tmp/{folder_id}/MediaInfo.json', 'r', encoding='utf-8') as f:
            mi = json.load(f)
            try:
                width = mi['media']['track'][1]['Width']
                height = mi['media']['track'][1]['Height']
            except Exception:
                width = 0
                height = 0
            framerate = mi['media']['track'][1].get('FrameRate', '')
            try:
                scan = mi['media']['track'][1]['ScanType']
            except Exception:
                scan = "Progressive"
            if scan == "Progressive":
                scan = "p"
            elif scan == "Interlaced":
                scan = 'i'
            elif framerate == "25.000":
                scan = "p"
            else:
                # Fallback using regex on meta['uuid'] - mainly for HUNO fun and games.
                match = re.search(r'\b(1080p|720p|2160p)\b', folder_id, re.IGNORECASE)
                if match:
                    scan = "p"  # Assume progressive based on common resolution markers
                else:
                    scan = "i"  # Default to interlaced if no indicators are found
            width_list = [3840, 2560, 1920, 1280, 1024, 960, 854, 720, 15360, 7680, 0]
            height_list = [2160, 1440, 1080, 720, 576, 540, 480, 8640, 4320, 0]
            width = await self.closest(width_list, int(width))
            actual_height = int(height)
            height = await self.closest(height_list, int(height))
            res = f"{width}x{height}{scan}"
            resolution = await mi_resolution(res, guess, width, scan, height, actual_height)
        return resolution

    async def closest(self, lst, K):
        # Get closest, but not over
        lst = sorted(lst)
        mi_input = K
        res = 0
        for each in lst:
            if mi_input > each:
                pass
            else:
                res = each
                break
        return res

        # return lst[min(range(len(lst)), key = lambda i: abs(lst[i]-K))]

    async def is_sd(self, resolution):
        if resolution in ("480i", "480p", "576i", "576p", "540p"):
            sd = 1
        else:
            sd = 0
        return sd

    """
    Is a scene release?
    """
    async def is_scene(self, video, meta, imdb=None):
        scene = False
        base = os.path.basename(video)
        match = re.match(r"^(.+)\.[a-zA-Z0-9]{3}$", os.path.basename(video))

        if match and (not meta['is_disc'] or meta['keep_folder']):
            base = match.group(1)
        base = urllib.parse.quote(base)
        url = f"https://api.srrdb.com/v1/search/r:{base}"
        if meta['debug']:
            console.print("Using SRRDB url", url)
        if 'scene' not in meta:
            try:
                response = requests.get(url, timeout=30)
                response_json = response.json()
                if meta['debug']:
                    console.print(response_json)

                if int(response_json.get('resultsCount', 0)) > 0:
                    first_result = response_json['results'][0]
                    meta['scene_name'] = first_result['release']
                    video = f"{first_result['release']}.mkv"
                    scene = True
                    if scene and meta.get('isdir', False) and meta.get('queue') is not None:
                        meta['keep_folder'] = True

                    # NFO Download Handling
                    if not meta.get('nfo'):
                        if first_result.get("hasNFO") == "yes":
                            try:
                                release = first_result['release']
                                release_lower = release.lower()
                                nfo_url = f"https://www.srrdb.com/download/file/{release}/{release_lower}.nfo"

                                # Define path and create directory
                                save_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
                                os.makedirs(save_path, exist_ok=True)
                                nfo_file_path = os.path.join(save_path, f"{release_lower}.nfo")

                                # Download the NFO file
                                nfo_response = requests.get(nfo_url, timeout=30)
                                if nfo_response.status_code == 200:
                                    with open(nfo_file_path, 'wb') as f:
                                        f.write(nfo_response.content)
                                        meta['nfo'] = True
                                        meta['auto_nfo'] = True
                                    console.print(f"[green]NFO downloaded to {nfo_file_path}")
                                else:
                                    console.print("[yellow]NFO file not available for download.")
                            except Exception as e:
                                console.print("[yellow]Failed to download NFO file:", e)

                    # IMDb Handling
                    try:
                        imdb_response = requests.get(f"https://api.srrdb.com/v1/imdb/{base}", timeout=10)

                        if imdb_response.status_code == 200:
                            imdb_json = imdb_response.json()
                            if meta['debug']:
                                console.print(f"imdb_json: {imdb_json}")

                            if imdb_json.get('releases') and len(imdb_json['releases']) > 0 and imdb == 0:
                                imdb_str = None
                                first_release = imdb_json['releases'][0]

                                if 'imdb' in first_release:
                                    imdb_str = first_release['imdb']
                                elif 'imdbId' in first_release:
                                    imdb_str = first_release['imdbId']
                                elif 'imdbid' in first_release:
                                    imdb_str = first_release['imdbid']

                                if imdb_str:
                                    imdb_str = str(imdb_str).lstrip('tT')  # Strip 'tt' or 'TT'
                                    imdb = int(imdb_str) if imdb_str.isdigit() else 0

                                first_release_name = imdb_json['releases'][0].get('title', imdb_json.get('query', ['Unknown release'])[0] if isinstance(imdb_json.get('query'), list) else 'Unknown release')
                                console.print(f"[green]SRRDB: Matched to {first_release_name}")
                        else:
                            console.print(f"[yellow]SRRDB API request failed with status: {imdb_response.status_code}")

                    except requests.RequestException as e:
                        console.print(f"[yellow]Failed to fetch IMDb information: {e}")
                    except (KeyError, IndexError, ValueError) as e:
                        console.print(f"[yellow]Error processing IMDb data: {e}")
                    except Exception as e:
                        console.print(f"[yellow]Unexpected error during IMDb lookup: {e}")

                else:
                    console.print("[yellow]SRRDB: No match found")

            except Exception as e:
                console.print(f"[yellow]SRRDB: No match found, or request has timed out: {e}")

        return video, scene, imdb

    """
    Get type and category
    """

    async def get_type(self, video, scene, is_disc, meta):
        if meta.get('manual_type'):
            type = meta.get('manual_type')
        else:
            filename = os.path.basename(video).lower()
            if "remux" in filename:
                type = "REMUX"
            elif any(word in filename for word in [" web ", ".web.", "web-dl", "webdl"]):
                type = "WEBDL"
            elif "webrip" in filename:
                type = "WEBRIP"
            # elif scene == True:
                # type = "ENCODE"
            elif "hdtv" in filename:
                type = "HDTV"
            elif is_disc is not None:
                type = "DISC"
            elif "dvdrip" in filename:
                type = "DVDRIP"
                # exit()
            else:
                type = "ENCODE"
        return type

    async def get_cat(self, video):
        # if category is None:
        category = guessit(video.replace('1.0', ''))['type']
        if category.lower() == "movie":
            category = "MOVIE"  # 1
        elif category.lower() in ("tv", "episode"):
            category = "TV"  # 2
        else:
            category = "MOVIE"
        return category

    """
    Mediainfo/Bdinfo > meta
    """
    async def get_audio_v2(self, mi, meta, bdinfo):
        extra = dual = ""
        has_commentary = False

        # Get formats
        if bdinfo is not None:  # Disks
            format_settings = ""
            format = bdinfo.get('audio', [{}])[0].get('codec', '')
            commercial = format
            additional = bdinfo.get('audio', [{}])[0].get('atmos_why_you_be_like_this', '')

            # Channels
            chan = bdinfo.get('audio', [{}])[0].get('channels', '')
        else:
            track_num = 2
            tracks = mi.get('media', {}).get('track', [])

            # Handle HD-DVD case
            if meta.get('is_disc') == "HDDVD":
                # Look for the first audio track
                for i, t in enumerate(tracks):
                    if t.get('@type') == "Audio":
                        track_num = i
                        break
            else:
                for i, t in enumerate(tracks):
                    if t.get('@type') != "Audio":
                        continue
                    if t.get('Language', '') == meta.get('original_language', '') and "commentary" not in (t.get('Title') or '').lower():
                        track_num = i
                        break

            track = tracks[track_num] if len(tracks) > track_num else {}
            format = track.get('Format', '')
            commercial = track.get('Format_Commercial', '') or track.get('Format_Commercial_IfAny', '')

            if track.get('Language', '') == "zxx":
                meta['silent'] = True

            additional = track.get('Format_AdditionalFeatures', '')

            format_settings = track.get('Format_Settings', '')
            if not isinstance(format_settings, str):
                format_settings = ""
            if format_settings in ['Explicit']:
                format_settings = ""
            format_profile = track.get('Format_Profile', '')
            # Channels
            channels = track.get('Channels_Original', track.get('Channels'))
            if not str(channels).isnumeric():
                channels = track.get('Channels')
            try:
                channel_layout = track.get('ChannelLayout', '') or track.get('ChannelLayout_Original', '') or track.get('ChannelPositions', '')
            except Exception:
                channel_layout = ''

            if channel_layout and "LFE" in channel_layout:
                chan = f"{int(channels) - 1}.1"
            elif channel_layout == "":
                if int(channels) <= 2:
                    chan = f"{int(channels)}.0"
                else:
                    chan = f"{int(channels) - 1}.1"
            else:
                chan = f"{channels}.0"

            if meta.get('dual_audio', False):
                dual = "Dual-Audio"
            else:
                if not meta.get('original_language', '').startswith('en'):
                    eng, orig = False, False
                    try:
                        for t in mi['media']['track']:
                            if t.get('@type') != "Audio":
                                continue

                            audio_language = t.get('Language', '')

                            if isinstance(audio_language, str):
                                if audio_language.startswith("en") and "commentary" not in (t.get('Title') or '').lower():
                                    eng = True

                                if not audio_language.startswith("en") and audio_language.startswith(meta.get('original_language')) and "commentary" not in (t.get('Title') or '').lower():
                                    orig = True

                                variants = ['zh', 'cn', 'cmn', 'no', 'nb']
                                if any(audio_language.startswith(var) for var in variants) and any(meta.get('original_language').startswith(var) for var in variants):
                                    orig = True

                            if isinstance(audio_language, str) and audio_language and audio_language != meta.get('original_language') and not audio_language.startswith("en"):
                                audio_language = "und" if audio_language == "" else audio_language
                                console.print(f"[bold red]This release has a(n) {audio_language} audio track, and may be considered bloated")
                                time.sleep(5)

                        if eng and orig:
                            dual = "Dual-Audio"
                        elif eng and not orig and meta.get('original_language') not in ['zxx', 'xx', None] and not meta.get('no_dub', False):
                            dual = "Dubbed"
                    except Exception:
                        console.print(traceback.format_exc())
                        pass

            for t in tracks:
                if t.get('@type') != "Audio":
                    continue

                if "commentary" in (t.get('Title') or '').lower():
                    has_commentary = True

        # Convert commercial name to naming conventions
        audio = {
            "DTS": "DTS",
            "AAC": "AAC",
            "AAC LC": "AAC",
            "AC-3": "DD",
            "E-AC-3": "DD+",
            "A_EAC3": "DD+",
            "Enhanced AC-3": "DD+",
            "MLP FBA": "TrueHD",
            "FLAC": "FLAC",
            "Opus": "Opus",
            "Vorbis": "VORBIS",
            "PCM": "LPCM",
            "LPCM Audio": "LPCM",
            "Dolby Digital Audio": "DD",
            "Dolby Digital Plus Audio": "DD+",
            "Dolby Digital Plus": "DD+",
            "Dolby TrueHD Audio": "TrueHD",
            "DTS Audio": "DTS",
            "DTS-HD Master Audio": "DTS-HD MA",
            "DTS-HD High-Res Audio": "DTS-HD HRA",
            "DTS:X Master Audio": "DTS:X"
        }
        audio_extra = {
            "XLL": "-HD MA",
            "XLL X": ":X",
            "ES": "-ES",
        }
        format_extra = {
            "JOC": " Atmos",
            "16-ch": " Atmos",
            "Atmos Audio": " Atmos",
        }
        format_settings_extra = {
            "Dolby Surround EX": "EX"
        }

        commercial_names = {
            "Dolby Digital": "DD",
            "Dolby Digital Plus": "DD+",
            "Dolby TrueHD": "TrueHD",
            "DTS-ES": "DTS-ES",
            "DTS-HD High": "DTS-HD HRA",
            "Free Lossless Audio Codec": "FLAC",
            "DTS-HD Master Audio": "DTS-HD MA"
        }

        search_format = True

        if isinstance(additional, dict):
            additional = ""  # Set empty string if additional is a dictionary

        if commercial:
            for key, value in commercial_names.items():
                if key in commercial:
                    codec = value
                    search_format = False
                if "Atmos" in commercial or format_extra.get(additional, "") == " Atmos":
                    extra = " Atmos"

        if search_format:
            codec = audio.get(format, "") + audio_extra.get(additional, "")
            extra = format_extra.get(additional, "")

        format_settings = format_settings_extra.get(format_settings, "")
        if format_settings == "EX" and chan == "5.1":
            format_settings = "EX"
        else:
            format_settings = ""

        if codec == "":
            codec = format

        if format.startswith("DTS"):
            if additional and additional.endswith("X"):
                codec = "DTS:X"
                chan = f"{int(channels) - 1}.1"

        if format == "MPEG Audio":
            if format_profile == "Layer 2":
                codec = "MP2"
            else:
                codec = track.get('CodecID_Hint', '')

        if codec == "DD" and chan == "7.1":
            console.print("[warning] Detected codec is DD but channel count is 7.1, correcting to DD+")
            codec = "DD+"

        audio = f"{dual} {codec or ''} {format_settings or ''} {chan or ''}{extra or ''}"
        audio = ' '.join(audio.split())
        return audio, chan, has_commentary

    async def is_3d(self, mi, bdinfo):
        if bdinfo is not None:
            if bdinfo['video'][0]['3d'] != "":
                return "3D"
            else:
                return ""
        else:
            return ""

    async def get_tag(self, video, meta):
        # Using regex from cross-seed (https://github.com/cross-seed/cross-seed/tree/master?tab=Apache-2.0-1-ov-file)
        release_group = None
        basename = os.path.basename(video)

        # Try specialized regex patterns first
        if meta.get('anime', False):
            # Anime pattern: [Group] at the beginning
            basename_stripped = os.path.splitext(basename)[0]
            anime_match = re.search(r'^\s*\[(.+?)\]', basename_stripped)
            if anime_match:
                release_group = anime_match.group(1)
                if meta['debug']:
                    console.print(f"Anime regex match: {release_group}")
        else:
            if not meta.get('is_disc') == "BDMV":
                # Non-anime pattern: group at the end after last hyphen, avoiding resolutions and numbers
                basename_stripped = os.path.splitext(basename)[0]
                non_anime_match = re.search(r'(?<=-)((?:\W|\b)(?!(?:\d{3,4}[ip]))(?!\d+\b)(?:\W|\b)([\w .]+?))(?:\[.+\])?(?:\))?(?:\s\[.+\])?$', basename_stripped)
                if non_anime_match:
                    release_group = non_anime_match.group(1).strip()
                    if meta['debug']:
                        console.print(f"Non-anime regex match: {release_group}")

        # If regex patterns didn't work, fall back to guessit
        if not release_group:
            try:
                parsed = guessit(video)
                release_group = parsed.get('release_group')
                if meta['debug']:
                    console.print(f"Guessit match: {release_group}")

            except Exception as e:
                console.print(f"Error while parsing group tag: {e}")
                release_group = None

        # BDMV validation
        if meta['is_disc'] == "BDMV" and release_group:
            if f"-{release_group}" not in video:
                release_group = None

        # Format the tag
        tag = f"-{release_group}" if release_group else ""

        # Clean up any tags that are just a hyphen
        if tag == "-":
            tag = ""

        # Remove generic "no group" tags
        if tag and tag[1:].lower() in ["nogroup", "nogrp"]:
            tag = ""

        return tag

    async def get_source(self, type, video, path, is_disc, meta, folder_id, base_dir):
        try:
            with open(f'{base_dir}/tmp/{folder_id}/MediaInfo.json', 'r', encoding='utf-8') as f:
                mi = json.load(f)
        except Exception:
            if meta['debug']:
                console.print("No mediainfo.json")
        try:
            try:
                source = guessit(video)['source']
            except Exception:
                try:
                    source = guessit(path)['source']
                except Exception:
                    source = "BluRay"
            if source in ("Blu-ray", "Ultra HD Blu-ray", "BluRay", "BR") or is_disc == "BDMV":
                if type == "DISC":
                    source = "Blu-ray"
                elif type in ('ENCODE', 'REMUX'):
                    source = "BluRay"
            if is_disc == "DVD" or source in ("DVD", "dvd"):
                try:
                    if is_disc == "DVD":
                        mediainfo = MediaInfo.parse(f"{meta['discs'][0]['path']}/VTS_{meta['discs'][0]['main_set'][0][:2]}_0.IFO")
                    else:
                        mediainfo = MediaInfo.parse(video)
                    for track in mediainfo.tracks:
                        if track.track_type == "Video":
                            system = track.standard
                    if system not in ("PAL", "NTSC"):
                        raise WeirdSystem  # noqa: F405
                except Exception:
                    try:
                        other = guessit(video)['other']
                        if "PAL" in other:
                            system = "PAL"
                        elif "NTSC" in other:
                            system = "NTSC"
                    except Exception:
                        system = ""
                    if system == "" or system is None:
                        try:
                            framerate = mi['media']['track'][1].get('FrameRate', '')
                            if '25' in framerate or '50' in framerate:
                                system = "PAL"
                            elif framerate:
                                system = "NTSC"
                            else:
                                system = ""
                        except Exception:
                            system = ""
                finally:
                    if system is None:
                        system = ""
                    if type == "REMUX":
                        system = f"{system} DVD".strip()
                    source = system
            if source in ("Web", "WEB"):
                if type == "ENCODE":
                    type = "WEBRIP"
            if source in ("HD-DVD", "HD DVD", "HDDVD"):
                if is_disc == "HDDVD":
                    source = "HD DVD"
                if type in ("ENCODE", "REMUX"):
                    source = "HDDVD"
            if type in ("WEBDL", 'WEBRIP'):
                source = "Web"
            if source == "Ultra HDTV":
                source = "UHDTV"
        except Exception:
            console.print(traceback.format_exc())
            source = "BluRay"

        return source, type

    async def get_uhd(self, type, guess, resolution, path):
        try:
            source = guess['Source']
            other = guess['Other']
        except Exception:
            source = ""
            other = ""
        uhd = ""
        if source == 'Blu-ray' and other == "Ultra HD" or source == "Ultra HD Blu-ray":
            uhd = "UHD"
        elif "UHD" in path:
            uhd = "UHD"
        elif type in ("DISC", "REMUX", "ENCODE", "WEBRIP"):
            uhd = ""

        if type in ("DISC", "REMUX", "ENCODE") and resolution == "2160p":
            uhd = "UHD"

        return uhd

    async def get_hdr(self, mi, bdinfo):
        hdr = ""
        dv = ""
        if bdinfo is not None:  # Disks
            hdr_mi = bdinfo['video'][0]['hdr_dv']
            if "HDR10+" in hdr_mi:
                hdr = "HDR10+"
            elif hdr_mi == "HDR10":
                hdr = "HDR"
            try:
                if bdinfo['video'][1]['hdr_dv'] == "Dolby Vision":
                    dv = "DV"
            except Exception:
                pass
        else:
            video_track = mi['media']['track'][1]
            try:
                hdr_mi = video_track['colour_primaries']
                if hdr_mi in ("BT.2020", "REC.2020"):
                    hdr = ""
                    hdr_format_string = video_track.get('HDR_Format_Compatibility', video_track.get('HDR_Format_String', video_track.get('HDR_Format', "")))
                    if "HDR10" in hdr_format_string:
                        hdr = "HDR"
                    if "HDR10+" in hdr_format_string:
                        hdr = "HDR10+"
                    if hdr_format_string == "" and "PQ" in (video_track.get('transfer_characteristics'), video_track.get('transfer_characteristics_Original', None)):
                        hdr = "PQ10"
                    transfer_characteristics = video_track.get('transfer_characteristics_Original', None)
                    if "HLG" in transfer_characteristics:
                        hdr = "HLG"
                    if hdr != "HLG" and "BT.2020 (10-bit)" in transfer_characteristics:
                        hdr = "WCG"
            except Exception:
                pass

            try:
                if "Dolby Vision" in video_track.get('HDR_Format', '') or "Dolby Vision" in video_track.get('HDR_Format_String', ''):
                    dv = "DV"
            except Exception:
                pass

        hdr = f"{dv} {hdr}".strip()
        return hdr

    async def get_video_codec(self, bdinfo):
        codecs = {
            "MPEG-2 Video": "MPEG-2",
            "MPEG-4 AVC Video": "AVC",
            "MPEG-H HEVC Video": "HEVC",
            "VC-1 Video": "VC-1"
        }
        codec = codecs.get(bdinfo['video'][0]['codec'], "")
        return codec

    async def get_video_encode(self, mi, type, bdinfo):
        video_encode = ""
        codec = ""
        bit_depth = '0'
        has_encode_settings = False
        try:
            format = mi['media']['track'][1]['Format']
            format_profile = mi['media']['track'][1].get('Format_Profile', format)
            if mi['media']['track'][1].get('Encoded_Library_Settings', None):
                has_encode_settings = True
            bit_depth = mi['media']['track'][1].get('BitDepth', '0')
        except Exception:
            format = bdinfo['video'][0]['codec']
            format_profile = bdinfo['video'][0]['profile']
        if type in ("ENCODE", "WEBRIP", "DVDRIP"):  # ENCODE or WEBRIP or DVDRIP
            if format == 'AVC':
                codec = 'x264'
            elif format == 'HEVC':
                codec = 'x265'
            elif format == 'AV1':
                codec = 'AV1'
        elif type in ('WEBDL', 'HDTV'):  # WEB-DL
            if format == 'AVC':
                codec = 'H.264'
            elif format == 'HEVC':
                codec = 'H.265'
            elif format == 'AV1':
                codec = 'AV1'

            if type == 'HDTV' and has_encode_settings is True:
                codec = codec.replace('H.', 'x')
        elif format == "VP9":
            codec = "VP9"
        elif format == "VC-1":
            codec = "VC-1"
        if format_profile == 'High 10':
            profile = "Hi10P"
        else:
            profile = ""
        video_encode = f"{profile} {codec}"
        video_codec = format
        if video_codec == "MPEG Video":
            video_codec = f"MPEG-{mi['media']['track'][1].get('Format_Version')}"
        return video_encode, video_codec, has_encode_settings, bit_depth

    async def get_edition(self, video, bdinfo, filelist, manual_edition, meta):
        if video.lower().startswith('dc'):
            video = video.replace('dc', '', 1)

        guess = guessit(video)
        tag = guess.get('release_group', 'NOGROUP')
        repack = ""
        edition = ""

        if bdinfo is not None:
            try:
                edition = guessit(bdinfo['label'])['edition']
            except Exception as e:
                print(f"BDInfo Edition Guess Error: {e}")
                edition = ""
        else:
            try:
                edition = guess.get('edition', "")
            except Exception as e:
                print(f"Video Edition Guess Error: {e}")
                edition = ""

        if isinstance(edition, list):
            edition = " ".join(edition)

        if len(filelist) == 1:
            video = os.path.basename(video)

        video = video.upper().replace('.', ' ').replace(tag.upper(), '').replace('-', '')

        if "OPEN MATTE" in video:
            edition = edition + " Open Matte"

        if manual_edition:
            if isinstance(manual_edition, list):
                manual_edition = " ".join(manual_edition)
            edition = str(manual_edition)
        edition = edition.replace(",", " ")

        # print(f"Edition After Manual Edition: {edition}")

        if "REPACK" in (video or edition.upper()) or "V2" in video:
            repack = "REPACK"
        if "REPACK2" in (video or edition.upper()) or "V3" in video:
            repack = "REPACK2"
        if "REPACK3" in (video or edition.upper()) or "V4" in video:
            repack = "REPACK3"
        if "PROPER" in (video or edition.upper()):
            repack = "PROPER"
        if "PROPER2" in (video or edition.upper()):
            repack = "PROPER2"
        if "PROPER3" in (video or edition.upper()):
            repack = "PROPER3"
        if "RERIP" in (video or edition.upper()):
            repack = "RERIP"

        # print(f"Repack after Checks: {repack}")

        # Only remove REPACK, RERIP, or PROPER from edition if they're not part of manual_edition
        if not manual_edition or all(tag.lower() not in ['repack', 'repack2', 'repack3', 'proper', 'proper2', 'proper3', 'rerip'] for tag in manual_edition.strip().lower().split()):
            edition = re.sub(r"(\bREPACK\d?\b|\bRERIP\b|\bPROPER\b)", "", edition, flags=re.IGNORECASE).strip()

        if edition:
            from src.region import get_distributor
            distributors = await get_distributor(edition)

            bad = ['internal', 'limited', 'retail']

            if distributors:
                bad.append(distributors.lower())
                meta['distributor'] = distributors

            if any(term.lower() in edition.lower() for term in bad):
                edition = re.sub(r'\b(?:' + '|'.join(bad) + r')\b', '', edition, flags=re.IGNORECASE).strip()
                # Clean up extra spaces
                while '  ' in edition:
                    edition = edition.replace('  ', ' ')
            console.print(f"Final Edition: {edition}")
        return edition, repack

    async def get_name(self, meta):
        type = meta.get('type', "").upper()
        title = meta.get('title', "")
        alt_title = meta.get('aka', "")
        year = meta.get('year', "")
        if int(meta.get('manual_year')) > 0:
            year = meta.get('manual_year')
        resolution = meta.get('resolution', "")
        if resolution == "OTHER":
            resolution = ""
        audio = meta.get('audio', "")
        service = meta.get('service', "")
        season = meta.get('season', "")
        episode = meta.get('episode', "")
        part = meta.get('part', "")
        repack = meta.get('repack', "")
        three_d = meta.get('3D', "")
        tag = meta.get('tag', "")
        source = meta.get('source', "")
        uhd = meta.get('uhd', "")
        hdr = meta.get('hdr', "")
        if meta.get('manual_episode_title'):
            episode_title = meta.get('manual_episode_title')
        elif meta.get('daily_episode_title'):
            episode_title = meta.get('daily_episode_title')
        else:
            episode_title = ""
        if meta.get('is_disc', "") == "BDMV":  # Disk
            video_codec = meta.get('video_codec', "")
            region = meta.get('region', "")
        elif meta.get('is_disc', "") == "DVD":
            region = meta.get('region', "")
            dvd_size = meta.get('dvd_size', "")
        else:
            video_codec = meta.get('video_codec', "")
            video_encode = meta.get('video_encode', "")
        edition = meta.get('edition', "")

        if meta['category'] == "TV":
            if meta['search_year'] != "":
                year = meta['year']
            else:
                year = ""
            if meta.get('manual_date'):
                # Ignore season and year for --daily flagged shows, just use manual date stored in episode_name
                season = ''
                episode = ''
        if meta.get('no_season', False) is True:
            season = ''
        if meta.get('no_year', False) is True:
            year = ''
        if meta.get('no_aka', False) is True:
            alt_title = ''
        if meta['debug']:
            console.log("[cyan]get_name cat/type")
            console.log(f"CATEGORY: {meta['category']}")
            console.log(f"TYPE: {meta['type']}")
            console.log("[cyan]get_name meta:")
            # console.log(meta)

        # YAY NAMING FUN
        if meta['category'] == "MOVIE":  # MOVIE SPECIFIC
            if type == "DISC":  # Disk
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} {alt_title} {year} {three_d} {edition} {repack} {resolution} {region} {uhd} {source} {hdr} {video_codec} {audio}"
                    potential_missing = ['edition', 'region', 'distributor']
                elif meta['is_disc'] == 'DVD':
                    name = f"{title} {alt_title} {year} {edition} {repack} {source} {dvd_size} {audio}"
                    potential_missing = ['edition', 'distributor']
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {source} {video_codec} {audio}"
                    potential_missing = ['edition', 'region', 'distributor']
            elif type == "REMUX" and source in ("BluRay", "HDDVD"):  # BluRay/HDDVD Remux
                name = f"{title} {alt_title} {year} {three_d} {edition} {repack} {resolution} {uhd} {source} REMUX {hdr} {video_codec} {audio}"
                potential_missing = ['edition', 'description']
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
                name = f"{title} {alt_title} {year} {edition} {repack} {source} REMUX  {audio}"
                potential_missing = ['edition', 'description']
            elif type == "ENCODE":  # Encode
                name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {uhd} {source} {audio} {hdr} {video_encode}"
                potential_missing = ['edition', 'description']
            elif type == "WEBDL":  # WEB-DL
                name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {uhd} {service} WEB-DL {audio} {hdr} {video_encode}"
                potential_missing = ['edition', 'service']
            elif type == "WEBRIP":  # WEBRip
                name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {uhd} {service} WEBRip {audio} {hdr} {video_encode}"
                potential_missing = ['edition', 'service']
            elif type == "HDTV":  # HDTV
                name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {source} {audio} {video_encode}"
                potential_missing = []
            elif type == "DVDRIP":
                name = f"{title} {alt_title} {year} {source} {video_encode} DVDRip {audio}"
                potential_missing = []
        elif meta['category'] == "TV":  # TV SPECIFIC
            if type == "DISC":  # Disk
                if meta['is_disc'] == 'BDMV':
                    name = f"{title} {year} {alt_title} {season}{episode} {three_d} {edition} {repack} {resolution} {region} {uhd} {source} {hdr} {video_codec} {audio}"
                    potential_missing = ['edition', 'region', 'distributor']
                if meta['is_disc'] == 'DVD':
                    name = f"{title} {alt_title} {season}{episode}{three_d} {edition} {repack} {source} {dvd_size} {audio}"
                    potential_missing = ['edition', 'distributor']
                elif meta['is_disc'] == 'HDDVD':
                    name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {source} {video_codec} {audio}"
                    potential_missing = ['edition', 'region', 'distributor']
            elif type == "REMUX" and source in ("BluRay", "HDDVD"):  # BluRay Remux
                name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {three_d} {edition} {repack} {resolution} {uhd} {source} REMUX {hdr} {video_codec} {audio}"  # SOURCE
                potential_missing = ['edition', 'description']
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
                name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {source} REMUX {audio}"  # SOURCE
                potential_missing = ['edition', 'description']
            elif type == "ENCODE":  # Encode
                name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {resolution} {uhd} {source} {audio} {hdr} {video_encode}"  # SOURCE
                potential_missing = ['edition', 'description']
            elif type == "WEBDL":  # WEB-DL
                name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {resolution} {uhd} {service} WEB-DL {audio} {hdr} {video_encode}"
                potential_missing = ['edition', 'service']
            elif type == "WEBRIP":  # WEBRip
                name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {resolution} {uhd} {service} WEBRip {audio} {hdr} {video_encode}"
                potential_missing = ['edition', 'service']
            elif type == "HDTV":  # HDTV
                name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {resolution} {source} {audio} {video_encode}"
                potential_missing = []
            elif type == "DVDRIP":
                name = f"{title} {alt_title} {season} {source} DVDRip {video_encode}"
                potential_missing = []

        try:
            name = ' '.join(name.split())
        except Exception:
            console.print("[bold red]Unable to generate name. Please re-run and correct any of the following args if needed.")
            console.print(f"--category [yellow]{meta['category']}")
            console.print(f"--type [yellow]{meta['type']}")
            console.print(f"--source [yellow]{meta['source']}")
            console.print("[bold green]If you specified type, try also specifying source")

            exit()
        name_notag = name
        name = name_notag + tag
        clean_name = await self.clean_filename(name)
        return name_notag, name, clean_name, potential_missing

    async def stream_optimized(self, stream_opt):
        if stream_opt is True:
            stream = 1
        else:
            stream = 0
        return stream

    def is_anon(self, anon_in):
        anon = self.config['DEFAULT'].get("Anon", "False")
        if anon.lower() == "true":
            console.print("[bold red]Global ANON has been removed in favor of per-tracker settings. Please update your config accordingly.")
            time.sleep(10)
        if anon_in is True:
            anon_out = 1
        else:
            anon_out = 0
        return anon_out

    async def upload_image(self, session, url, data, headers, files):
        if headers is None and files is None:
            async with session.post(url=url, data=data) as resp:
                response = await resp.json()
                return response
        elif headers is None and files is not None:
            async with session.post(url=url, data=data, files=files) as resp:
                response = await resp.json()
                return response
        elif headers is not None and files is None:
            async with session.post(url=url, data=data, headers=headers) as resp:
                response = await resp.json()
                return response
        else:
            async with session.post(url=url, data=data, headers=headers, files=files) as resp:
                response = await resp.json()
                return response

    async def clean_filename(self, name):
        invalid = '<>:"/\\|?*'
        for char in invalid:
            name = name.replace(char, '-')
        return name

    async def gen_desc(self, meta):
        def clean_text(text):
            return text.replace('\r\n', '').replace('\n', '').strip()

        desclink = meta.get('desclink')
        descfile = meta.get('descfile')
        scene_nfo = False
        bhd_nfo = False

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
            description.seek(0)
            content_written = False

            if meta.get('desc_template'):
                from jinja2 import Template
                try:
                    with open(f"{meta['base_dir']}/data/templates/{meta['desc_template']}.txt", 'r') as f:
                        template = Template(f.read())
                        template_desc = template.render(meta)
                        if clean_text(template_desc):
                            if len(template_desc) > 0:
                                description.write(template_desc + "\n")
                            content_written = True
                except FileNotFoundError:
                    console.print(f"[ERROR] Template '{meta['desc_template']}' not found.")

            base_dir = meta['base_dir']
            uuid = meta['uuid']
            path = meta['path']
            specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
            source_dir_path = os.path.join(path, "*.nfo")
            if meta['debug']:
                console.print(f"specified_dir_path: {specified_dir_path}")
                console.print(f"sourcedir_path: {source_dir_path}")
            if meta.get('nfo') and not content_written:
                if 'auto_nfo' in meta and meta['auto_nfo'] is True:
                    nfo_files = glob.glob(specified_dir_path)
                    scene_nfo = True
                elif 'bhd_nfo' in meta and meta['bhd_nfo'] is True:
                    nfo_files = glob.glob(specified_dir_path)
                    bhd_nfo = True
                else:
                    nfo_files = glob.glob(source_dir_path)
                if not nfo_files:
                    console.print("NFO was set but no nfo file was found")
                    description.write("\n")
                    return meta

                if nfo_files:
                    nfo = nfo_files[0]
                    try:
                        with open(nfo, 'r', encoding="utf-8") as nfo_file:
                            nfo_content = nfo_file.read()
                        if meta['debug']:
                            console.print("NFO content read with utf-8 encoding.")
                    except UnicodeDecodeError:
                        if meta['debug']:
                            console.print("utf-8 decoding failed, trying latin1.")
                        with open(nfo, 'r', encoding="latin1") as nfo_file:
                            nfo_content = nfo_file.read()

                    if scene_nfo is True:
                        description.write(f"[center][spoiler=Scene NFO:][code]{nfo_content}[/code][/spoiler][/center]\n")
                    elif bhd_nfo is True:
                        description.write(f"[center][spoiler=FraMeSToR NFO:][code]{nfo_content}[/code][/spoiler][/center]\n")
                    else:
                        description.write(f"[code]{nfo_content}[/code]\n")
                    meta['description'] = "CUSTOM"
                    content_written = True

            if desclink and not content_written:
                try:
                    parsed = urllib.parse.urlparse(desclink.replace('/raw/', '/'))
                    split = os.path.split(parsed.path)
                    raw = parsed._replace(path=f"{split[0]}/raw/{split[1]}" if split[0] != '/' else f"/raw{parsed.path}")
                    raw_url = urllib.parse.urlunparse(raw)
                    desclink_content = requests.get(raw_url).text
                    if clean_text(desclink_content):
                        description.write(desclink_content + "\n")
                        meta['description'] = "CUSTOM"
                        content_written = True
                except Exception as e:
                    console.print(f"[ERROR] Failed to fetch description from link: {e}")

            if descfile and os.path.isfile(descfile) and not content_written:
                with open(descfile, 'r') as f:
                    file_content = f.read()
                if clean_text(file_content):
                    description.write(file_content)
                    meta['description'] = "CUSTOM"
                    content_written = True

            if not content_written:
                if meta.get('description'):
                    description_text = meta.get('description', '').strip()
                else:
                    description_text = ""
                if description_text:
                    description.write(description_text + "\n")

            if description.tell() != 0:
                description.write("\n")
            return meta

        # Fallback if no description is provided
        if not meta.get('skip_gen_desc', False):
            description_text = meta['description'] if meta['description'] else ""
            with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
                if len(description_text) > 0:
                    description.write(description_text + "\n")

            return meta

    async def tag_override(self, meta):
        with open(f"{meta['base_dir']}/data/tags.json", 'r', encoding="utf-8") as f:
            tags = json.load(f)
            f.close()

        for tag in tags:
            value = tags.get(tag)
            if value.get('in_name', "") == tag and tag in meta['path']:
                meta['tag'] = f"-{tag}"
            if meta['tag'][1:] == tag:
                for key in value:
                    if key == 'type':
                        if meta[key] == "ENCODE":
                            meta[key] = value.get(key)
                        else:
                            pass
                    elif key == 'personalrelease':
                        meta[key] = self._is_true(value.get(key, "False"))
                    elif key == 'template':
                        meta['desc_template'] = value.get(key)
                    else:
                        meta[key] = value.get(key)
        return meta

    async def get_dvd_size(self, discs, manual_dvds):
        sizes = []
        dvd_sizes = []
        for each in discs:
            sizes.append(each['size'])
        grouped_sizes = [list(i) for j, i in itertools.groupby(sorted(sizes))]
        for each in grouped_sizes:
            if len(each) > 1:
                dvd_sizes.append(f"{len(each)}x{each[0]}")
            else:
                dvd_sizes.append(each[0])
        dvd_sizes.sort()
        compact = " ".join(dvd_sizes)

        if manual_dvds:
            compact = str(manual_dvds)

        return compact

    async def get_audio_languages(self, mi, meta):
        tracks = mi.get('media', {}).get('track', [])

        languages = []

        for i, t in enumerate(tracks):
            if t.get('@type') != "Audio":
                continue

            language = t.get('Language', '')
            if meta['debug']:
                console.print(f"DEBUG: Track {i} Language = {language} ({type(language)})")

            if isinstance(language, str):  # Normal case
                languages.append(language.lower())
            elif isinstance(language, dict):  # Handle unexpected dict case
                if 'value' in language:  # Check if a known key exists
                    extracted = language['value']
                    if isinstance(extracted, str):
                        languages.append(extracted.lower())

        return languages

    async def get_source_override(self, meta, other_id=False):
        try:
            with open(f"{meta['base_dir']}/data/templates/user-args.json", 'r', encoding="utf-8") as f:
                console.print("[green]Found user-args.json")
                user_args = json.load(f)

            current_tmdb_id = meta.get('tmdb_id', 0)
            current_imdb_id = meta.get('imdb_id', 0)
            current_tvdb_id = meta.get('tvdb_id', 0)

            # Convert to int for comparison if it's a string
            if isinstance(current_tmdb_id, str) and current_tmdb_id.isdigit():
                current_tmdb_id = int(current_tmdb_id)

            if isinstance(current_imdb_id, str) and current_imdb_id.isdigit():
                current_imdb_id = int(current_imdb_id)

            if isinstance(current_tvdb_id, str) and current_tvdb_id.isdigit():
                current_tvdb_id = int(current_tvdb_id)

            if not other_id:
                for entry in user_args.get('entries', []):
                    entry_tmdb_id = entry.get('tmdb_id')
                    args = entry.get('args', [])

                    if not entry_tmdb_id:
                        continue

                    # Parse the entry's TMDB ID from the user-args.json file
                    entry_category, entry_normalized_id = await self.parse_tmdb_id(entry_tmdb_id)
                    if entry_category != meta['category']:
                        if meta['debug']:
                            console.print(f"Skipping user entry because override category {entry_category} does not match UA category {meta['category']}:")
                        continue

                    # Check if IDs match
                    if entry_normalized_id == current_tmdb_id:
                        console.print(f"[green]Found matching override for TMDb ID: {entry_normalized_id}")
                        console.print(f"[yellow]Applying arguments: {' '.join(args)}")

                        meta = await self.apply_args_to_meta(meta, args)
                        break

            else:
                for entry in user_args.get('other_ids', []):
                    # Check for TVDB ID match
                    if 'tvdb_id' in entry and str(entry['tvdb_id']) == str(current_tvdb_id) and current_tvdb_id != 0:
                        args = entry.get('args', [])
                        console.print(f"[green]Found matching override for TVDb ID: {current_tvdb_id}")
                        console.print(f"[yellow]Applying arguments: {' '.join(args)}")
                        meta = await self.apply_args_to_meta(meta, args)
                        break

                    # Check for IMDB ID match (without tt prefix)
                    if 'imdb_id' in entry:
                        entry_imdb = entry['imdb_id']
                        if str(entry_imdb).startswith('tt'):
                            entry_imdb = entry_imdb[2:]

                        if str(entry_imdb) == str(current_imdb_id) and current_imdb_id != 0:
                            args = entry.get('args', [])
                            console.print(f"[green]Found matching override for IMDb ID: {current_imdb_id}")
                            console.print(f"[yellow]Applying arguments: {' '.join(args)}")
                            meta = await self.apply_args_to_meta(meta, args)
                            break

        except (FileNotFoundError, json.JSONDecodeError) as e:
            console.print(f"[red]Error loading user-args.json: {e}")

        return meta

    async def parse_tmdb_id(self, tmdb_id, category=None):
        if tmdb_id is None:
            return category, 0

        tmdb_id = str(tmdb_id).strip().lower()
        if not tmdb_id or tmdb_id == 0:
            return category, 0

        if '/' in tmdb_id:
            parts = tmdb_id.split('/')
            if len(parts) >= 2:
                prefix = parts[0]
                id_part = parts[1]

                if prefix == 'tv':
                    category = 'TV'
                elif prefix == 'movie':
                    category = 'MOVIE'

                try:
                    normalized_id = int(id_part)
                    return category, normalized_id
                except ValueError:
                    return category, 0

        try:
            normalized_id = int(tmdb_id)
            return category, normalized_id
        except ValueError:
            return category, 0

    async def apply_args_to_meta(self, meta, args):
        from src.args import Args

        try:
            arg_keys_to_track = set()
            arg_values = {}

            i = 0
            while i < len(args):
                arg = args[i]
                if arg.startswith('--'):
                    # Remove '--' prefix and convert dashes to underscores
                    key = arg[2:].replace('-', '_')
                    arg_keys_to_track.add(key)

                    # Store the value if it exists
                    if i + 1 < len(args) and not args[i + 1].startswith('--'):
                        arg_values[key] = args[i + 1]  # Store the value with its key
                        i += 1
                i += 1

            if meta['debug']:
                console.print(f"[Debug] Tracking changes for keys: {', '.join(arg_keys_to_track)}")

            # Create a new Args instance and process the arguments
            arg_processor = Args(self.config)
            full_args = ['upload.py'] + args
            updated_meta, _, _ = arg_processor.parse(full_args, meta.copy())
            updated_meta['path'] = meta.get('path')
            modified_keys = []

            # Handle ID arguments specifically
            id_mappings = {
                'tmdb': ['tmdb_id', 'tmdb', 'tmdb_manual'],
                'tvmaze': ['tvmaze_id', 'tvmaze', 'tvmaze_manual'],
                'imdb': ['imdb_id', 'imdb', 'imdb_manual'],
                'tvdb': ['tvdb_id', 'tvdb', 'tvdb_manual'],
            }

            for key in arg_keys_to_track:
                # Special handling for ID fields
                if key in id_mappings:
                    if key in arg_values:  # Check if we have a value for this key
                        value = arg_values[key]
                        # Convert to int if possible
                        try:
                            if isinstance(value, str) and value.isdigit():
                                value = int(value)
                            elif isinstance(value, str) and key == 'imdb' and value.startswith('tt'):
                                value = int(value[2:])  # Remove 'tt' prefix and convert to int
                        except ValueError:
                            pass

                        # Update all related keys
                        for related_key in id_mappings[key]:
                            meta[related_key] = value
                            modified_keys.append(related_key)
                            if meta['debug']:
                                console.print(f"[Debug] Override: {related_key} changed from {meta.get(related_key)} to {value}")
                # Handle regular fields
                elif key in updated_meta and key in meta:
                    # Skip path to preserve original
                    if key == 'path':
                        continue

                    new_value = updated_meta[key]
                    old_value = meta[key]
                    # Only update if the value actually changed
                    if new_value != old_value:
                        meta[key] = new_value
                        modified_keys.append(key)
                        if meta['debug']:
                            console.print(f"[Debug] Override: {key} changed from {old_value} to {new_value}")
            if meta['debug'] and modified_keys:
                console.print(f"[Debug] Applied overrides for: {', '.join(modified_keys)}")

        except Exception as e:
            console.print(f"[red]Error processing arguments: {e}")
            if meta['debug']:
                import traceback
                console.print(traceback.format_exc())

        return meta
