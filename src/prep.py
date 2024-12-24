# -*- coding: utf-8 -*-
from src.args import Args
from src.console import console
from src.exceptions import *  # noqa: F403
from src.trackers.PTP import PTP
from src.trackers.COMMON import COMMON
from src.clients import Clients
from data.config import config
from src.uphelper import UploadHelper
from src.trackersetup import TRACKER_SETUP, tracker_class_map
from src.takescreens import disc_screenshots, dvd_screenshots, screenshots
from src.tvmaze import search_tvmaze
from src.imdb import get_imdb_info_api, search_imdb, imdb_other_meta
from src.trackermeta import update_metadata_from_tracker
from src.tmdb import tmdb_other_meta, get_tmdb_imdb_from_mediainfo, get_tmdb_from_imdb, get_tmdb_id
from src.region import get_region, get_distributor, get_service
from src.exportmi import exportInfo, mi_resolution
from src.getseasonep import get_season_episode

try:
    import traceback
    from src.discparse import DiscParse
    import os
    import re
    import math
    from str2bool import str2bool
    from guessit import guessit
    import ntpath
    from pathlib import Path
    import urllib
    import urllib.parse
    import random
    import json
    import glob
    import requests
    from pymediainfo import MediaInfo
    import tmdbsimple as tmdb
    from datetime import datetime
    import torf
    from torf import Torrent
    import time
    import itertools
    import cli_ui
    import aiohttp
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

    async def gather_prep(self, meta, mode):
        meta['cutoff'] = int(self.config['DEFAULT'].get('cutoff_screens', 3))
        task_limit = self.config['DEFAULT'].get('task_limit', "0")
        if int(task_limit) > 0:
            meta['task_limit'] = task_limit
        meta['tone_map'] = self.config['DEFAULT'].get('tone_map', False)
        tone_task_limit = self.config['DEFAULT'].get('tone_task_limit', "0")
        if int(tone_task_limit) > 0:
            meta['tone_task_limit'] = tone_task_limit
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
            video, meta['scene'], meta['imdb'] = await self.is_scene(meta['path'], meta, meta.get('imdb', None))
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
            video, meta['scene'], meta['imdb'] = await self.is_scene(meta['path'], meta, meta.get('imdb', None))
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
            video, meta['scene'], meta['imdb'] = await self.is_scene(meta['path'], meta, meta.get('imdb', None))
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
            meta['sd'] = self.is_sd(meta['resolution'])

        else:
            videopath, meta['filelist'] = await self.get_video(videoloc, meta.get('mode', 'discord'))
            search_term = os.path.basename(meta['filelist'][0]) if meta['filelist'] else None
            search_file_folder = 'file'
            video, meta['scene'], meta['imdb'] = await self.is_scene(videopath, meta, meta.get('imdb', None))
            guess_name = ntpath.basename(video).replace('-', ' ')
            filename = guessit(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]}).get("title", guessit(re.sub("[^0-9a-zA-Z]+", " ", guess_name), {"excludes": ["country", "language"]})["title"])
            untouched_filename = os.path.basename(video)
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

        # Debugging information after population
        # console.print(f"Debug: meta['filelist'] after population: {meta.get('filelist', 'Not Set')}")

        if 'description' not in meta:
            meta['description'] = ""

        description_text = meta.get('description', '')
        if description_text is None:
            description_text = ""
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
            description.write(description_text)

        client = Clients(config=config)
        if meta.get('infohash') is not None:
            meta = await client.get_ptp_from_hash(meta)
        common = COMMON(config=config)
        tracker_setup = TRACKER_SETUP(config=config)
        if not meta.get('image_list'):
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
                }
                specific_tracker = next((tracker_keys[key] for key in tracker_keys if meta.get(key)), None)

                async def process_tracker(tracker_name, meta):
                    nonlocal found_match
                    if tracker_class_map is None:
                        print(f"Tracker class for {tracker_name} not found.")
                        return meta

                    tracker_instance = tracker_class_map[tracker_name](config=config)
                    try:
                        updated_meta, match = await update_metadata_from_tracker(
                            tracker_name, tracker_instance, meta, search_term, search_file_folder
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
                    meta = await process_tracker(specific_tracker, meta)
                else:
                    # Process all trackers with API = true if no specific tracker is set in meta
                    tracker_order = ["PTP", "BLU", "AITHER", "LST", "OE", "TIK", "HDB"]

                    for tracker_name in tracker_order:
                        if not found_match:  # Stop checking once a match is found
                            tracker_config = self.config['TRACKERS'].get(tracker_name, {})
                            if str(tracker_config.get('useAPI', 'false')).lower() == "true":
                                meta = await process_tracker(tracker_name, meta)

                if not found_match:
                    console.print("[yellow]No matches found on any trackers.[/yellow]")
            else:
                console.print("[yellow]Warning: No valid search term available, skipping tracker updates.[/yellow]")
        else:
            console.print("Skipping existing search as meta already populated")

        console.print("[yellow]Building meta data.....")
        if meta['debug']:
            meta_start_time = time.time()
        if meta.get('manual_language'):
            meta['original_langauge'] = meta.get('manual_language').lower()
        meta['tmdb'] = meta.get('tmdb_manual', None)
        meta['type'] = await self.get_type(video, meta['scene'], meta['is_disc'], meta)
        if meta.get('category', None) is None:
            meta['category'] = await self.get_cat(video)
        else:
            meta['category'] = meta['category'].upper()
        if meta.get('tmdb', None) is None and meta.get('imdb', None) is None:
            meta['category'], meta['tmdb'], meta['imdb'] = await get_tmdb_imdb_from_mediainfo(mi, meta['category'], meta['is_disc'], meta['tmdb'], meta['imdb'])
        if meta.get('tmdb', None) is None and meta.get('imdb', None) is None:
            meta = await get_tmdb_id(filename, meta['search_year'], meta, meta['category'], untouched_filename)
        elif meta.get('imdb', None) is not None and meta.get('tmdb_manual', None) is None:
            meta['imdb_id'] = str(meta['imdb']).replace('tt', '')
            meta = await get_tmdb_from_imdb(meta, filename)
        else:
            meta['tmdb_manual'] = meta.get('tmdb', None)

        # If no tmdb, use imdb for meta
        if int(meta['tmdb']) == 0:
            meta = await imdb_other_meta(meta)
        else:
            meta = await tmdb_other_meta(meta)
        # Search tvmaze
        if meta['category'] == "TV":
            meta['tvmaze_id'], meta['imdb_id'], meta['tvdb_id'] = await search_tvmaze(filename, meta['search_year'], meta.get('imdb_id', '0'), meta.get('tvdb_id', 0), meta)
        else:
            meta.setdefault('tvmaze_id', '0')
        # If no imdb, search for it
        if meta.get('imdb_id', None) is None:
            meta['imdb_id'] = await search_imdb(filename, meta['search_year'])
        if meta.get('imdb_info', None) is None and int(meta['imdb_id']) != 0:
            meta['imdb_info'] = await get_imdb_info_api(meta['imdb_id'], meta)
        if meta.get('tag', None) is None:
            meta['tag'] = await self.get_tag(video, meta)
        else:
            if not meta['tag'].startswith('-') and meta['tag'] != "":
                meta['tag'] = f"-{meta['tag']}"
        if meta['category'] == "TV":
            meta = await get_season_episode(video, meta)
        meta = await self.tag_override(meta)
        if meta.get('tag') == "-SubsPlease":  # SubsPlease-specific
            tracks = meta.get('mediainfo').get('media', {}).get('track', [])  # Get all tracks
            bitrate = tracks[1].get('BitRate', '') if len(tracks) > 1 else ''  # Get video bitrate if available
            bitrate_oldMediaInfo = tracks[0].get('OverallBitRate', '') if len(tracks) > 0 else ''  # For old MediaInfo (< 24.x where video bitrate is empty, use 'OverallBitRate' instead)
            meta['episode_title'] = ""
            if (bitrate.isdigit() and int(bitrate) >= 8000000) or (bitrate_oldMediaInfo.isdigit() and int(bitrate_oldMediaInfo) >= 8000000):
                meta['service'] = "CR"
            elif (bitrate.isdigit() or bitrate_oldMediaInfo.isdigit()):  # Only assign if at least one bitrate is present, otherwise leave it to user
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
            meta['edition'], meta['repack'] = await self.get_edition(meta['path'], bdinfo, meta['filelist'], meta.get('manual_edition'))
            if "REPACK" in meta.get('edition', ""):
                meta['repack'] = re.search(r"REPACK[\d]?", meta['edition'])[0]
                meta['edition'] = re.sub(r"REPACK[\d]?", "", meta['edition']).strip().replace('  ', ' ')
        else:
            meta['edition'] = ""
        meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await self.get_name(meta)
        if meta['debug']:
            meta_finish_time = time.time()
            console.print(f"Metadata processed in {meta_finish_time - meta_start_time:.2f} seconds")
        parser = Args(config)
        helper = UploadHelper()
        enabled_trackers = tracker_setup.trackers_enabled(meta)
        if "saved_trackers" not in meta:
            meta['trackers'] = enabled_trackers
        else:
            meta['trackers'] = meta['saved_trackers']
        confirm = helper.get_confirmation(meta)
        while confirm is False:
            with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
                json.dump(meta, f, indent=4)
            meta['saved_trackers'] = meta['trackers']
            editargs = cli_ui.ask_string("Input args that need correction e.g. (--tag NTb --category tv --tmdb 12345)")
            editargs = (meta['path'],) + tuple(editargs.split())
            if meta.get('debug', False):
                editargs += ("--debug",)
            meta, help, before_args = parser.parse(editargs, meta)
            meta['edit'] = True
            meta = await self.gather_prep(meta=meta, mode='cli')
            meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await self.get_name(meta)
            confirm = helper.get_confirmation(meta)

        tracker_status = {}
        successful_trackers = 0

        for tracker_name in meta['trackers']:
            disctype = meta.get('disctype', None)
            tracker_name = tracker_name.replace(" ", "").upper().strip()

            if meta['name'].endswith('DUPE?'):
                meta['name'] = meta['name'].replace(' DUPE?', '')

            if tracker_name in tracker_class_map:
                tracker_class = tracker_class_map[tracker_name](config=config)
                tracker_status[tracker_name] = {'banned': False, 'skipped': False, 'dupe': False, 'upload': False}

                if tracker_name in {"THR", "PTP"}:
                    if meta.get('imdb_id', '0') == '0':
                        imdb_id = cli_ui.ask_string("Unable to find IMDB id, please enter e.g.(tt1234567)")
                        meta['imdb_id'] = imdb_id.replace('tt', '').zfill(7)
                if tracker_name == "PTP":
                    console.print("[yellow]Searching for Group ID")
                    ptp = PTP(config=config)
                    groupID = await ptp.get_group_by_imdb(meta['imdb_id'])
                    if groupID is None:
                        console.print("[yellow]No Existing Group found")
                        if meta.get('youtube', None) is None or "youtube" not in str(meta.get('youtube', '')):
                            youtube = cli_ui.ask_string("Unable to find youtube trailer, please link one e.g.(https://www.youtube.com/watch?v=dQw4w9WgXcQ)", default="")
                            meta['youtube'] = youtube
                    meta['ptp_groupID'] = groupID

                if tracker_name == "THR":
                    youtube = cli_ui.ask_string("Unable to find youtube trailer, please link one e.g.(https://www.youtube.com/watch?v=dQw4w9WgXcQ)")
                    meta['youtube'] = youtube

                if tracker_setup.check_banned_group(tracker_class.tracker, tracker_class.banned_groups, meta):
                    console.print(f"[red]Tracker '{tracker_name}' is banned. Skipping.[/red]")
                    tracker_status[tracker_name]['banned'] = True

                if tracker_name not in {"THR", "PTP", "TL"}:
                    dupes = await tracker_class.search_existing(meta, disctype)
                elif tracker_name == "PTP":
                    dupes = await ptp.search_existing(groupID, meta, disctype)
                if 'skipping' not in meta or meta['skipping'] is None:
                    dupes = await common.filter_dupes(dupes, meta)
                    meta, is_dupe = helper.dupe_check(dupes, meta, tracker_name)
                    if is_dupe:
                        console.print(f"[red]Skipping upload on {tracker_name}[/red]")
                        print()
                        tracker_status[tracker_name]['dupe'] = True
                elif meta['skipping']:
                    tracker_status[tracker_name]['skipped'] = True
                if tracker_name == "MTV":
                    if not tracker_status[tracker_name]['banned'] and not tracker_status[tracker_name]['skipped'] and not tracker_status[tracker_name]['dupe']:
                        tracker_config = self.config['TRACKERS'].get(tracker_name, {})
                        if str(tracker_config.get('prefer_mtv_torrent', 'false')).lower() == "true":
                            meta['prefer_small_pieces'] = True
                        else:
                            meta['prefer_small_pieces'] = False
                        if str(tracker_config.get('skip_if_rehash', 'false')).lower() == "true":
                            torrent_path = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")
                            if not os.path.exists(torrent_path):
                                check_torrent = await client.find_existing_torrent(meta)
                                if check_torrent:
                                    console.print(f"[yellow]Existing torrent found on {check_torrent}[/yellow]")
                                    await self.create_base_from_existing_torrent(check_torrent, meta['base_dir'], meta['uuid'])
                                    torrent = Torrent.read(torrent_path)
                                    if torrent.piece_size > 8388608:
                                        console.print("[yellow]No existing torrent found with piece size lesser than 8MB[/yellow]")
                                        tracker_status[tracker_name]['skipped'] = True
                            elif os.path.exists(torrent_path):
                                torrent = Torrent.read(torrent_path)
                                if torrent.piece_size > 8388608:
                                    console.print("[yellow]Existing torrent found with piece size greater than 8MB[/yellow]")
                                    tracker_status[tracker_name]['skipped'] = True
                if meta.get('skipping') is None and not is_dupe and tracker_name == "PTP":
                    if meta.get('imdb_info', {}) == {}:
                        meta['imdb_info'] = get_imdb_info_api(meta['imdb_id'], meta)
                if not meta['debug']:
                    if not tracker_status[tracker_name]['banned'] and not tracker_status[tracker_name]['skipped'] and not tracker_status[tracker_name]['dupe']:
                        console.print(f"[bold yellow]Tracker '{tracker_name}' passed all checks.")
                        if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                            edit_choice = input("Enter 'y' to upload, or press enter to skip uploading:")
                            if edit_choice.lower() == 'y':
                                tracker_status[tracker_name]['upload'] = True
                                successful_trackers += 1
                            else:
                                tracker_status[tracker_name]['upload'] = False
                        else:
                            tracker_status[tracker_name]['upload'] = True
                            successful_trackers += 1
                else:
                    tracker_status[tracker_name]['upload'] = True
                    successful_trackers += 1
                meta['skipping'] = None
        else:
            if tracker_name == "MANUAL":
                successful_trackers += 1

        meta['tracker_status'] = tracker_status

        if meta['debug']:
            console.print("\n[bold]Tracker Processing Summary:[/bold]")
        for t_name, status in tracker_status.items():
            banned_status = 'Yes' if status['banned'] else 'No'
            skipped_status = 'Yes' if status['skipped'] else 'No'
            dupe_status = 'Yes' if status['dupe'] else 'No'
            upload_status = 'Yes' if status['upload'] else 'No'
            if meta['debug']:
                console.print(f"Tracker: {t_name} | Banned: {banned_status} | Skipped: {skipped_status} | Dupe: {dupe_status} | [yellow]Upload:[/yellow] {upload_status}")
        if meta['debug']:
            console.print(f"\n[bold]Trackers Passed all Checks:[/bold] {successful_trackers}")

        meta['skip_uploading'] = int(self.config['DEFAULT'].get('tracker_pass_checks', 1))
        if not meta['debug']:
            if successful_trackers < meta['skip_uploading']:
                console.print(f"[red]Not enough successful trackers ({successful_trackers}/{meta['skip_uploading']}). EXITING........[/red]")
                return

        meta['we_are_uploading'] = True

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
            json.dump(meta, f, indent=4)

        if 'manual_frames' not in meta:
            meta['manual_frames'] = {}
        manual_frames = meta['manual_frames']
        # Take Screenshots
        if meta['is_disc'] == "BDMV":
            if not meta.get('edit', False):
                use_vs = meta.get('vapoursynth', False)
                try:
                    disc_screenshots(
                        meta, filename, bdinfo, meta['uuid'], base_dir, use_vs,
                        meta.get('image_list', []), meta.get('ffdebug', False), None
                    )
                except Exception as e:
                    print(f"Error during BDMV screenshot capture: {e}")

        elif meta['is_disc'] == "DVD":
            if not meta.get('edit', False):
                try:
                    dvd_screenshots(
                        meta, 0, None, None
                    )
                except Exception as e:
                    print(f"Error during DVD screenshot capture: {e}")

        else:
            if not meta.get('edit', False):
                try:
                    screenshots(
                        videopath, filename, meta['uuid'], base_dir, meta,
                        manual_frames=manual_frames  # Pass additional kwargs directly
                    )
                except Exception as e:
                    print(f"Error during generic screenshot capture: {e}")

        # WORK ON THIS
        meta.get('stream', False)
        meta['stream'] = await self.stream_optimized(meta['stream'])
        meta.get('anon', False)
        meta['anon'] = self.is_anon(meta['anon'])
        if meta['saved_description'] is False:
            meta = await self.gen_desc(meta)
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
        for path, directories, files in os. walk(meta['path']):
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
                discs, bdinfo = await parse.get_bdinfo(discs, meta['uuid'], meta['base_dir'], meta.get('discs', []))
            else:
                discs, bdinfo = await parse.get_bdinfo(meta['discs'], meta['uuid'], meta['base_dir'], meta['discs'])
        elif is_disc == "DVD":
            discs = await parse.get_dvdinfo(discs)
            export = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'w', newline="", encoding='utf-8')
            export.write(discs[0]['ifo_mi'])
            export.close()
            export_clean = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'w', newline="", encoding='utf-8')
            export_clean.write(discs[0]['ifo_mi'])
            export_clean.close()
        elif is_disc == "HDDVD":
            discs = await parse.get_hddvd_info(discs)
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
            width_list = [3840, 2560, 1920, 1280, 1024, 854, 720, 15360, 7680, 0]
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
        base = os.path.splitext(base)[0]
        base = urllib.parse.quote(base)
        url = f"https://api.srrdb.com/v1/search/r:{base}"
        if 'scene' not in meta:
            try:
                response = requests.get(url, timeout=30)
                response_json = response.json()

                if int(response_json.get('resultsCount', 0)) > 0:
                    first_result = response_json['results'][0]
                    meta['scene_name'] = first_result['release']
                    video = f"{first_result['release']}.mkv"
                    scene = True
                    if scene and meta.get('isdir', False) and meta.get('queue') is not None:
                        meta['keep_folder'] = True

                    # NFO Download Handling
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
                        r = requests.get(f"https://api.srrdb.com/v1/imdb/{base}")
                        r = r.json()

                        if r['releases'] != [] and imdb is None:
                            imdb = r['releases'][0].get('imdb', imdb) if r['releases'][0].get('imdb') is not None else imdb
                        console.print(f"[green]SRRDB: Matched to {first_result['release']}")
                    except Exception as e:
                        console.print("[yellow]Failed to fetch IMDb information:", e)

                else:
                    console.print("[yellow]SRRDB: No match found")

            except Exception as e:
                console.print("[yellow]SRRDB: No match found, or request has timed out", e)

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
                channel_layout = track.get('ChannelLayout', '')
            except Exception:
                channel_layout = track.get('ChannelLayout_Original', '')

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
                        for t in tracks:
                            if t.get('@type') != "Audio":
                                continue

                            audio_language = t.get('Language', '')

                            if isinstance(audio_language, str):
                                if audio_language.startswith("en") and "commentary" not in (t.get('Title') or '').lower():
                                    eng = True

                                if not audio_language.startswith("en") and audio_language.startswith(meta['original_language']) and "commentary" not in (t.get('Title') or '').lower():
                                    orig = True

                                variants = ['zh', 'cn', 'cmn', 'no', 'nb']
                                if any(audio_language.startswith(var) for var in variants) and any(meta['original_language'].startswith(var) for var in variants):
                                    orig = True

                            if isinstance(audio_language, str) and audio_language and audio_language != meta['original_language'] and not audio_language.startswith("en"):
                                audio_language = "und" if audio_language == "" else audio_language
                                console.print(f"[bold red]This release has a(n) {audio_language} audio track, and may be considered bloated")
                                time.sleep(5)

                        if eng and orig:
                            dual = "Dual-Audio"
                        elif eng and not orig and meta['original_language'] not in ['zxx', 'xx', None] and not meta.get('no_dub', False):
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
            "MLP FBA": "TrueHD",
            "FLAC": "FLAC",
            "Opus": "Opus",
            "Vorbis": "VORBIS",
            "PCM": "LPCM",
            "LPCM Audio": "LPCM",
            "Dolby Digital Audio": "DD",
            "Dolby Digital Plus Audio": "DD+",
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
        try:
            parsed = guessit(video)
            release_group = parsed.get('release_group')
            if meta['is_disc'] == "BDMV":
                if release_group:
                    if f"-{release_group}" not in video:
                        if meta['debug']:
                            console.print(f"[warning] Invalid release group format: {release_group}")
                        release_group = None

            tag = f"-{release_group}" if release_group else ""
        except Exception as e:
            console.print(f"Error while parsing: {e}")
            tag = ""

        if tag == "-":
            tag = ""
        if tag[1:].lower() in ["nogroup", "nogrp"]:
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

    async def get_edition(self, video, bdinfo, filelist, manual_edition):
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
        if "RERIP" in (video or edition.upper()):
            repack = "RERIP"

        # print(f"Repack after Checks: {repack}")

        # Only remove REPACK, RERIP, or PROPER from edition if they're not part of manual_edition
        if not manual_edition or all(tag.lower() not in ['repack', 'repack2', 'repack3', 'proper', 'rerip'] for tag in manual_edition.strip().lower().split()):
            edition = re.sub(r"(\bREPACK\d?\b|\bRERIP\b|\bPROPER\b)", "", edition, flags=re.IGNORECASE).strip()
        print(f"Final Edition: {edition}")
        bad = ['internal', 'limited', 'retail']

        if edition.lower() in bad:
            edition = re.sub(r'\b(?:' + '|'.join(bad) + r')\b', '', edition, flags=re.IGNORECASE).strip()

        return edition, repack

    """
    Create Torrent
    """
    class CustomTorrent(torf.Torrent):
        # Default piece size limits
        torf.Torrent.piece_size_min = 16384  # 16 KiB
        torf.Torrent.piece_size_max = 268435456  # 256 MiB

        def __init__(self, meta, *args, **kwargs):
            super().__init__(*args, **kwargs)

            # Override piece_size_max if meta['max_piece_size'] is specified
            if 'max_piece_size' in meta and meta['max_piece_size']:
                try:
                    max_piece_size_mib = int(meta['max_piece_size']) * 1024 * 1024  # Convert MiB to bytes
                    self.piece_size_max = min(max_piece_size_mib, torf.Torrent.piece_size_max)
                except ValueError:
                    self.piece_size_max = torf.Torrent.piece_size_max  # Fallback to default if conversion fails
            else:
                self.piece_size_max = torf.Torrent.piece_size_max

            # Calculate and set the piece size
            # total_size = self._calculate_total_size()
            # piece_size = self.calculate_piece_size(total_size, self.piece_size_min, self.piece_size_max, self.files)
            self.metainfo['info']['piece length'] = self._piece_size

        @property
        def piece_size(self):
            return self._piece_size

        @piece_size.setter
        def piece_size(self, value):
            if value is None:
                total_size = self._calculate_total_size()
                value = self.calculate_piece_size(total_size, self.piece_size_min, self.piece_size_max, self.files)
            self._piece_size = value
            self.metainfo['info']['piece length'] = value  # Ensure 'piece length' is set

        @classmethod
        def calculate_piece_size(cls, total_size, min_size, max_size, files):
            file_count = len(files)
            # console.print(f"[red]Calculating piece size for {file_count} files")

            our_min_size = 16384
            our_max_size = max_size if max_size else 268435456  # Default to 256 MiB if max_size is None
            piece_size = 4194304  # Start with 4 MiB

            num_pieces = math.ceil(total_size / piece_size)

            # Initial torrent_file_size calculation based on file_count
            # More paths = greater error in pathname_bytes, roughly recalibrate
            if file_count > 1000:
                torrent_file_size = 20 + (num_pieces * 20) + int(cls._calculate_pathname_bytes(files) * 71 / 100)
            elif file_count > 500:
                torrent_file_size = 20 + (num_pieces * 20) + int(cls._calculate_pathname_bytes(files) * 4 / 5)
            else:
                torrent_file_size = 20 + (num_pieces * 20) + cls._calculate_pathname_bytes(files)

            # iteration = 0  # Track the number of iterations
            # print(f"Initial piece size: {piece_size} bytes")
            # print(f"Initial num_pieces: {num_pieces}, Initial torrent_file_size: {torrent_file_size} bytes")

            # Adjust the piece size to fit within the constraints
            while not ((750 <= num_pieces <= 2200 or num_pieces < 750 and 40960 <= torrent_file_size <= 250000) and torrent_file_size <= 250000):
                # iteration += 1
                # print(f"\nIteration {iteration}:")
                # print(f"Current piece_size: {piece_size} bytes")
                # print(f"Current num_pieces: {num_pieces}, Current torrent_file_size: {torrent_file_size} bytes")
                if num_pieces > 1000 and num_pieces < 2000 and torrent_file_size < 250000:
                    break
                elif num_pieces < 1500 and torrent_file_size >= 250000:
                    piece_size *= 2
                    # print(f"Doubled piece_size to {piece_size} bytes (num_pieces < 1500 and torrent_file_size >= 250 KiB)")
                    if piece_size > our_max_size:
                        piece_size = our_max_size
                        # print(f"piece_size exceeded max_size, set to our_max_size: {our_max_size} bytes")
                        break
                elif num_pieces < 750:
                    piece_size //= 2
                    # print(f"Halved piece_size to {piece_size} bytes (num_pieces < 750)")
                    if piece_size < our_min_size:
                        piece_size = our_min_size
                        # print(f"piece_size went below min_size, set to our_min_size: {our_min_size} bytes")
                        break
                    elif 40960 < torrent_file_size < 250000:
                        # print(f"torrent_file_size is between 40 KiB and 250 KiB, exiting loop.")
                        break
                elif num_pieces > 2200:
                    piece_size *= 2
                    # print(f"Doubled piece_size to {piece_size} bytes (num_pieces > 2500)")
                    if piece_size > our_max_size:
                        piece_size = our_max_size
                        # print(f"piece_size exceeded max_size, set to our_max_size: {our_max_size} bytes")
                        break
                    elif torrent_file_size < 2048:
                        # print(f"torrent_file_size is less than 2 KiB, exiting loop.")
                        break
                elif torrent_file_size > 250000:
                    piece_size *= 2
                    # print(f"Doubled piece_size to {piece_size} bytes (torrent_file_size > 250 KiB)")
                    if piece_size > our_max_size:
                        piece_size = our_max_size
                        # print(f"piece_size exceeded max_size, set to our_max_size: {our_max_size} bytes")
                        cli_ui.warning('WARNING: .torrent size will exceed 250 KiB!')
                        break

                # Update num_pieces
                num_pieces = math.ceil(total_size / piece_size)

                # Recalculate torrent_file_size based on file_count in each iteration
                if file_count > 1000:
                    torrent_file_size = 20 + (num_pieces * 20) + int(cls._calculate_pathname_bytes(files) * 71 / 100)
                elif file_count > 500:
                    torrent_file_size = 20 + (num_pieces * 20) + int(cls._calculate_pathname_bytes(files) * 4 / 5)
                else:
                    torrent_file_size = 20 + (num_pieces * 20) + cls._calculate_pathname_bytes(files)

            # print(f"\nFinal piece_size: {piece_size} bytes after {iteration} iterations.")
            # print(f"Final num_pieces: {num_pieces}, Final torrent_file_size: {torrent_file_size} bytes")
            return piece_size

        def _calculate_total_size(self):
            total_size = sum(file.size for file in self.files)
            return total_size

        @classmethod
        def _calculate_pathname_bytes(cls, files):
            total_pathname_bytes = sum(len(str(file).encode('utf-8')) for file in files)
            return total_pathname_bytes

        def validate_piece_size(self):
            if not hasattr(self, '_piece_size') or self._piece_size is None:
                self.piece_size = self.calculate_piece_size(self._calculate_total_size(), self.piece_size_min, self.piece_size_max, self.files)
            self.metainfo['info']['piece length'] = self.piece_size  # Ensure 'piece length' is set

    def create_torrent(self, meta, path, output_filename):
        # Handle directories and file inclusion logic
        if meta['isdir']:
            if meta['keep_folder']:
                cli_ui.info('--keep-folder was specified. Using complete folder for torrent creation.')
                path = path
            else:
                os.chdir(path)
                globs = glob.glob1(path, "*.mkv") + glob.glob1(path, "*.mp4") + glob.glob1(path, "*.ts")
                no_sample_globs = []
                for file in globs:
                    if not file.lower().endswith('sample.mkv') or "!sample" in file.lower():
                        no_sample_globs.append(os.path.abspath(f"{path}{os.sep}{file}"))
                if len(no_sample_globs) == 1:
                    path = meta['filelist'][0]
        if meta['is_disc']:
            include, exclude = "", ""
        else:
            exclude = ["*.*", "*sample.mkv", "!sample*.*"]
            include = ["*.mkv", "*.mp4", "*.ts"]

        # Create and write the new torrent using the CustomTorrent class
        torrent = self.CustomTorrent(
            meta=meta,
            path=path,
            trackers=["https://fake.tracker"],
            source="L4G",
            private=True,
            exclude_globs=exclude or [],
            include_globs=include or [],
            creation_date=datetime.now(),
            comment="Created by L4G's Upload Assistant",
            created_by="L4G's Upload Assistant"
        )

        # Ensure piece size is validated before writing
        torrent.validate_piece_size()

        # Generate and write the new torrent
        torrent.generate(callback=self.torf_cb, interval=5)
        torrent.write(f"{meta['base_dir']}/tmp/{meta['uuid']}/{output_filename}.torrent", overwrite=True)
        torrent.verify_filesize(path)

        console.print("[bold green].torrent created", end="\r")
        return torrent

    def torf_cb(self, torrent, filepath, pieces_done, pieces_total):
        # print(f'{pieces_done/pieces_total*100:3.0f} % done')
        cli_ui.info_progress("Hashing...", pieces_done, pieces_total)

    def create_random_torrents(self, base_dir, uuid, num, path):
        manual_name = re.sub(r"[^0-9a-zA-Z\[\]\'\-]+", ".", os.path.basename(path))
        base_torrent = Torrent.read(f"{base_dir}/tmp/{uuid}/BASE.torrent")
        for i in range(1, int(num) + 1):
            new_torrent = base_torrent
            new_torrent.metainfo['info']['entropy'] = random.randint(1, 999999)
            Torrent.copy(new_torrent).write(f"{base_dir}/tmp/{uuid}/[RAND-{i}]{manual_name}.torrent", overwrite=True)

    async def create_base_from_existing_torrent(self, torrentpath, base_dir, uuid):
        if os.path.exists(torrentpath):
            base_torrent = Torrent.read(torrentpath)
            base_torrent.trackers = ['https://fake.tracker']
            base_torrent.comment = "Created by L4G's Upload Assistant"
            base_torrent.created_by = "Created by L4G's Upload Assistant"
            # Remove Un-whitelisted info from torrent
            for each in list(base_torrent.metainfo['info']):
                if each not in ('files', 'length', 'name', 'piece length', 'pieces', 'private', 'source'):
                    base_torrent.metainfo['info'].pop(each, None)
            for each in list(base_torrent.metainfo):
                if each not in ('announce', 'comment', 'creation date', 'created by', 'encoding', 'info'):
                    base_torrent.metainfo.pop(each, None)
            base_torrent.source = 'L4G'
            base_torrent.private = True
            Torrent.copy(base_torrent).write(f"{base_dir}/tmp/{uuid}/BASE.torrent", overwrite=True)

    async def get_name(self, meta):
        type = meta.get('type', "").upper()
        title = meta.get('title', "")
        alt_title = meta.get('aka', "")
        year = meta.get('year', "")
        if meta.get('manual_year') > 0:
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
        else:
            episode_title = meta.get('episode_title', '')
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
                            description.write(template_desc + "\n")
                            content_written = True
                except FileNotFoundError:
                    console.print(f"[ERROR] Template '{meta['desc_template']}' not found.")

            base_dir = meta['base_dir']
            uuid = meta['uuid']
            current_dir_path = "*.nfo"
            specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
            if meta['debug']:
                console.print(f"specified_dir_path: {specified_dir_path}")
            if meta.get('nfo') and not content_written:
                if meta['auto_nfo'] is True:
                    nfo_files = glob.glob(specified_dir_path)
                    scene_nfo = True
                else:
                    nfo_files = glob.glob(current_dir_path)
                if meta['debug']:
                    console.print(f"Glob current_dir_path matches: {glob.glob(current_dir_path)}")
                    console.print(f"Glob specified_dir_path matches: {glob.glob(specified_dir_path)}")
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

            if meta.get('desc') and not content_written:
                description.write(meta['desc'] + "\n")
                meta['description'] = "CUSTOM"
                content_written = True

            if not content_written:
                description_text = meta.get('description', '') or ''
                description.write(description_text + "\n")

            description.write("\n")
            return meta

        # Fallback if no description is provided
        if not meta.get('skip_gen_desc', False):
            description_text = meta['description'] if meta['description'] else ""
            with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
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
                        meta[key] = bool(str2bool(str(value.get(key, 'False'))))
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
