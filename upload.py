#!/usr/bin/env python3
# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
import aiofiles
import asyncio
import cli_ui
import discord
import gc
import json
import os
import platform
import re
import requests
import shutil
import sys
import time
import traceback

from packaging import version
from pathlib import Path

from bin.get_mkbrr import ensure_mkbrr_binary
from cogs.redaction import clean_meta_for_export, redact_private_info
from discordbot import send_discord_notification, send_upload_status_notification
from src.add_comparison import add_comparison
from src.args import Args
from src.cleanup import cleanup, reset_terminal
from src.clients import Clients
from src.console import console
from src.get_name import get_name
from src.get_desc import gen_desc
from src.get_tracker_data import get_tracker_data
from src.languages import process_desc_language
from src.nfo_link import nfo_link
from src.queuemanage import handle_queue, save_processed_path, process_site_upload_item
from src.takescreens import disc_screenshots, dvd_screenshots, screenshots
from src.torrentcreate import create_torrent, create_random_torrents, create_base_from_existing_torrent
from src.trackerhandle import process_trackers
from src.trackerstatus import process_all_trackers
from src.trackersetup import TRACKER_SETUP, tracker_class_map, api_trackers, other_api_trackers, http_trackers
from src.trackers.COMMON import COMMON
from src.uphelper import UploadHelper
from src.uploadscreens import upload_screens

cli_ui.setup(color='always', title="Upload Assistant")
running_subprocesses = set()
base_dir = os.path.abspath(os.path.dirname(__file__))

try:
    from data.config import config
except Exception:
    if not os.path.exists(os.path.abspath(f"{base_dir}/data/config.py")):
        cli_ui.info(cli_ui.red, "Configuration file 'config.py' not found.")
        cli_ui.info(cli_ui.red, "Please ensure the file is located at:", cli_ui.yellow, os.path.abspath(f"{base_dir}/data/config.py"))
        cli_ui.info(cli_ui.red, "Follow the setup instructions: https://github.com/Audionut/Upload-Assistant")
        exit()
    else:
        console.print(traceback.print_exc())

from src.prep import Prep  # noqa E402
client = Clients(config=config)
parser = Args(config)
use_discord = False
discord_config = config.get('DISCORD')
if discord_config:
    use_discord = discord_config.get('use_discord', False)


async def merge_meta(meta, saved_meta, path):
    """Merges saved metadata with the current meta, respecting overwrite rules."""
    with open(f"{base_dir}/tmp/{os.path.basename(path)}/meta.json") as f:
        saved_meta = json.load(f)
        overwrite_list = [
            'trackers', 'dupe', 'debug', 'anon', 'category', 'type', 'screens', 'nohash', 'manual_edition', 'imdb', 'tmdb_manual', 'mal', 'manual',
            'hdb', 'ptp', 'blu', 'no_season', 'no_aka', 'no_year', 'no_dub', 'no_tag', 'no_seed', 'client', 'description_link', 'description_file', 'desc', 'draft',
            'modq', 'region', 'freeleech', 'personalrelease', 'unattended', 'manual_season', 'manual_episode', 'torrent_creation', 'qbit_tag', 'qbit_cat',
            'skip_imghost_upload', 'imghost', 'manual_source', 'webdv', 'hardcoded-subs', 'dual_audio', 'manual_type', 'tvmaze_manual'
        ]
        sanitized_saved_meta = {}
        for key, value in saved_meta.items():
            clean_key = key.strip().strip("'").strip('"')
            if clean_key in overwrite_list:
                if clean_key in meta and meta.get(clean_key) is not None:
                    sanitized_saved_meta[clean_key] = meta[clean_key]
                    if meta['debug']:
                        console.print(f"Overriding {clean_key} with meta value:", meta[clean_key])
                else:
                    sanitized_saved_meta[clean_key] = value
            else:
                sanitized_saved_meta[clean_key] = value
        meta.update(sanitized_saved_meta)
    f.close()
    return sanitized_saved_meta


async def print_progress(message, interval=10):
    """Prints a progress message every `interval` seconds until cancelled."""
    try:
        while True:
            await asyncio.sleep(interval)
            console.print(message)
    except asyncio.CancelledError:
        pass


def update_oeimg_to_onlyimage():
    """Update all img_host_* values from 'oeimg' to 'onlyimage' in the config file."""
    config_path = f"{base_dir}/data/config.py"
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(
        r"(['\"]img_host_\d+['\"]\s*:\s*)['\"]oeimg['\"]",
        r"\1'onlyimage'",
        content
    )
    new_content = re.sub(
        r"(['\"])(oeimg_api)(['\"]\s*:)",
        r"\1onlyimage_api\3",
        new_content
    )

    if new_content != content:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        console.print("[green]Updated 'oeimg' to 'onlyimage' and 'oeimg_api' to 'onlyimage_api' in config.py[/green]")
    else:
        console.print("[yellow]No 'oeimg' or 'oeimg_api' found to update in config.py[/yellow]")


async def validate_tracker_logins(meta, trackers=None):
    if 'tracker_status' not in meta:
        meta['tracker_status'] = {}

    # Filter trackers that are in both the list and tracker_class_map
    valid_trackers = [tracker for tracker in trackers if tracker in tracker_class_map and tracker in http_trackers]
    if "RTF" in trackers:
        valid_trackers.append("RTF")

    if valid_trackers:

        async def validate_single_tracker(tracker_name):
            """Validate credentials for a single tracker."""
            try:
                if tracker_name not in meta['tracker_status']:
                    meta['tracker_status'][tracker_name] = {}

                tracker_class = tracker_class_map[tracker_name](config=config)
                if meta['debug']:
                    console.print(f"[cyan]Validating {tracker_name} credentials...[/cyan]")
                if tracker_name == "RTF":
                    login = await tracker_class.api_test(meta)
                else:
                    login = await tracker_class.validate_credentials(meta)

                if not login:
                    meta['tracker_status'][tracker_name]['skipped'] = True

                return tracker_name, login
            except Exception as e:
                console.print(f"[red]Error validating {tracker_name}: {e}[/red]")
                meta['tracker_status'][tracker_name]['skipped'] = True
                return tracker_name, False

        # Run all tracker validations concurrently
        await asyncio.gather(*[validate_single_tracker(tracker) for tracker in valid_trackers])


async def process_meta(meta, base_dir, bot=None):
    """Process the metadata for each queued path."""
    if use_discord and bot:
        await send_discord_notification(config, bot, f"Starting upload process for: {meta['path']}", debug=meta.get('debug', False), meta=meta)

    if meta['imghost'] is None:
        meta['imghost'] = config['DEFAULT']['img_host_1']
        try:
            result = any(
                config['DEFAULT'].get(key) == "oeimg"
                for key in config['DEFAULT']
                if key.startswith("img_host_")
            )
            if result:
                console.print("[red]oeimg is now onlyimage, your config is being updated[/red]")
                update_oeimg_to_onlyimage()
        except Exception as e:
            console.print(f"[red]Error checking image hosts: {e}[/red]")
            return

    if not meta['unattended']:
        ua = config['DEFAULT'].get('auto_mode', False)
        if str(ua).lower() == "true":
            meta['unattended'] = True
            console.print("[yellow]Running in Auto Mode")
    prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=config)
    try:
        results = await asyncio.gather(
            prep.gather_prep(meta=meta, mode='cli'),
            return_exceptions=True  # Returns exceptions instead of raising them
        )
        for result in results:
            if isinstance(result, Exception):
                return
            else:
                meta = result
    except Exception as e:
        console.print(f"Error in gather_prep: {e}")
        console.print(traceback.format_exc())
        return

    meta['emby_debug'] = meta.get('emby_debug') if meta.get('emby_debug', False) else config['DEFAULT'].get('emby_debug', False)
    if meta.get('emby_cat', None) == "movie" and meta.get('category', None) != "MOVIE":
        console.print(f"[red]Wrong category detected! Expected 'MOVIE', but found: {meta.get('category', None)}[/red]")
        meta['we_are_uploading'] = False
        return
    elif meta.get('emby_cat', None) == "tv" and meta.get('category', None) != "TV":
        console.print("[red]TV content is not supported at this time[/red]")
        meta['we_are_uploading'] = False
        return

    # If unattended confirm and we had to get metadata ids from filename searching, skip the quick return so we can prompt about database information
    if meta.get('emby', False) and not meta.get('no_ids', False) and not meta.get('unattended_confirm', False) and meta.get('unattended', False):
        await nfo_link(meta)
        meta['we_are_uploading'] = False
        return

    parser = Args(config)
    helper = UploadHelper()

    if not meta.get('emby', False):
        if meta.get('trackers_remove', False):
            remove_list = [t.strip().upper() for t in meta['trackers_remove'].split(',')]
            for tracker in remove_list:
                if tracker in meta['trackers']:
                    meta['trackers'].remove(tracker)

        meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await get_name(meta)

        if meta['debug']:
            console.print(f"Trackers list before editing: {meta['trackers']}")
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
            json.dump(meta, f, indent=4)
            f.close()

    if meta.get('emby_debug', False):
        meta['original_imdb'] = meta.get('imdb_id', None)
        meta['original_tmdb'] = meta.get('tmdb_id', None)
        meta['original_mal'] = meta.get('mal_id', None)
        meta['original_tvmaze'] = meta.get('tvmaze_id', None)
        meta['original_tvdb'] = meta.get('tvdb_id', None)
        meta['original_category'] = meta.get('category', None)
        if 'matched_tracker' not in meta:
            await client.get_pathed_torrents(meta['path'], meta)
            if meta['is_disc']:
                search_term = os.path.basename(meta['path'])
                search_file_folder = 'folder'
            else:
                search_term = os.path.basename(meta['filelist'][0]) if meta['filelist'] else None
                search_file_folder = 'file'
            await get_tracker_data(meta['video'], meta, search_term, search_file_folder, meta['category'], only_id=meta['only_id'])

    editargs_tracking = ()
    previous_trackers = meta.get('trackers', [])
    try:
        confirm = await helper.get_confirmation(meta)
    except EOFError:
        console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
        await cleanup()
        reset_terminal()
        sys.exit(1)
    while confirm is False:
        try:
            editargs = cli_ui.ask_string("Input args that need correction e.g. (--tag NTb --category tv --tmdb 12345)")
        except EOFError:
            console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
            await cleanup()
            reset_terminal()
            sys.exit(1)

        if editargs == "continue":
            break

        if not editargs or not editargs.strip():
            console.print("[yellow]No input provided. Please enter arguments, type `continue` to continue or press Ctrl+C to exit.[/yellow]")
            continue

        try:
            editargs = tuple(editargs.split())
        except AttributeError:
            console.print("[red]Bad input detected[/red]")
            confirm = False
            continue
        # Tracks multiple edits
        editargs_tracking = editargs_tracking + editargs
        # Carry original args over, let parse handle duplicates
        meta, help, before_args = parser.parse(tuple(' '.join(sys.argv[1:]).split(' ')) + editargs_tracking, meta)
        if not meta.get('trackers'):
            meta['trackers'] = previous_trackers
        if isinstance(meta.get('trackers'), str):
            if "," in meta['trackers']:
                meta['trackers'] = [t.strip().upper() for t in meta['trackers'].split(',')]
            else:
                meta['trackers'] = [meta['trackers'].strip().upper()]
        elif isinstance(meta.get('trackers'), list):
            meta['trackers'] = [t.strip().upper() for t in meta['trackers'] if isinstance(t, str)]
        if meta['debug']:
            console.print(f"Trackers list during edit process: {meta['trackers']}")
        meta['edit'] = True
        meta = await prep.gather_prep(meta=meta, mode='cli')
        meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await get_name(meta)
        try:
            confirm = await helper.get_confirmation(meta)
        except EOFError:
            console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
            await cleanup()
            reset_terminal()
            sys.exit(1)

    if meta.get('emby', False):
        if not meta['debug']:
            await nfo_link(meta)
        meta['we_are_uploading'] = False
        return

    if 'remove_trackers' in meta and meta['remove_trackers']:
        removed = []
        for tracker in meta['remove_trackers']:
            if tracker in meta['trackers']:
                if meta['debug']:
                    console.print(f"[DEBUG] Would have removed {tracker} found in client")
                else:
                    meta['trackers'].remove(tracker)
                    removed.append(tracker)
        if removed:
            console.print(f"[yellow]Removing trackers already in your client: {', '.join(removed)}[/yellow]")
    if not meta['trackers']:
        console.print("[red]No trackers remain after removal.[/red]")
        successful_trackers = 0
        meta['skip_uploading'] = 10

    else:
        console.print(f"[green]Processing {meta['name']} for upload...[/green]")

        # reset trackers after any removals
        trackers = meta['trackers']

        audio_prompted = False
        for tracker in ["AITHER", "ASC", "BJS", "BT", "CBR", "DP", "FF", "GPW", "HUNO", "IHD", "LDU", "LT", "OE", "PTS", "SAM", "SHRI", "SPD", "TTR", "ULCX"]:
            if tracker in trackers:
                if not audio_prompted:
                    await process_desc_language(meta, desc=None, tracker=tracker)
                    audio_prompted = True
                else:
                    if 'tracker_status' not in meta:
                        meta['tracker_status'] = {}
                    if tracker not in meta['tracker_status']:
                        meta['tracker_status'][tracker] = {}
                    if meta.get('unattended_audio_skip', False) or meta.get('unattended_subtitle_skip', False):
                        meta['tracker_status'][tracker]['skip_upload'] = True
                    else:
                        meta['tracker_status'][tracker]['skip_upload'] = False

        await asyncio.sleep(0.2)
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
            json.dump(meta, f, indent=4)
        await asyncio.sleep(0.2)

        try:
            await validate_tracker_logins(meta, trackers)
            await asyncio.sleep(0.2)
        except Exception as e:
            console.print(f"[yellow]Warning: Tracker validation encountered an error: {e}[/yellow]")

        successful_trackers = await process_all_trackers(meta)

        if meta.get('trackers_pass') is not None:
            meta['skip_uploading'] = meta.get('trackers_pass')
        else:
            meta['skip_uploading'] = int(config['DEFAULT'].get('tracker_pass_checks', 1))

    if successful_trackers < int(meta['skip_uploading']) and not meta['debug']:
        console.print(f"[red]Not enough successful trackers ({successful_trackers}/{meta['skip_uploading']}). EXITING........[/red]")

    else:
        meta['we_are_uploading'] = True
        common = COMMON(config)
        if meta.get('site_check', False):
            for tracker in meta['trackers']:
                upload_status = meta['tracker_status'].get(tracker, {}).get('upload', False)
                if not upload_status:
                    if tracker == "AITHER" and meta.get('aither_trumpable') and len(meta.get('aither_trumpable', [])) > 0:
                        pass
                    else:
                        continue
                if tracker not in meta['tracker_status']:
                    continue

                log_path = f"{base_dir}/tmp/{tracker}_search_results.json"
                if not await common.path_exists(log_path):
                    await common.makedirs(os.path.dirname(log_path))

                search_data = []
                if os.path.exists(log_path):
                    try:
                        async with aiofiles.open(log_path, 'r', encoding='utf-8') as f:
                            content = await f.read()
                            search_data = json.loads(content) if content.strip() else []
                    except Exception:
                        search_data = []

                existing_uuids = {entry.get('uuid') for entry in search_data if isinstance(entry, dict)}

                if meta['uuid'] not in existing_uuids:
                    search_entry = {
                        'uuid': meta['uuid'],
                        'path': meta.get('path', ''),
                        'imdb_id': meta.get('imdb_id', 0),
                        'tmdb_id': meta.get('tmdb_id', 0),
                        'tvdb_id': meta.get('tvdb_id', 0),
                        'mal_id': meta.get('mal_id', 0),
                        'tvmaze_id': meta.get('tvmaze_id', 0),
                    }
                    if tracker == "AITHER":
                        search_entry['trumpable'] = meta.get('aither_trumpable', '')
                    search_data.append(search_entry)

                    async with aiofiles.open(log_path, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(search_data, indent=4))
            meta['we_are_uploading'] = False
            return

        filename = meta.get('title', None)
        bdmv_filename = meta.get('filename', None)
        bdinfo = meta.get('bdinfo', None)
        videopath = meta.get('filelist', [None])
        videopath = videopath[0] if videopath else None
        console.print(f"Processing {filename} for upload.....")

        meta['frame_overlay'] = config['DEFAULT'].get('frame_overlay', False)
        for tracker in ['AZ', 'CZ', 'PHD']:
            upload_status = meta['tracker_status'].get(tracker, {}).get('upload', False)
            if tracker in meta['trackers'] and meta['frame_overlay'] and upload_status is True:
                meta['frame_overlay'] = False
                console.print("[yellow]AZ, CZ, and PHD do not allow frame overlays. Frame overlay will be disabled for this upload.[/yellow]")

        bdmv_mi_created = False
        for tracker in ["ANT", "DC", "HUNO", "LCD"]:
            upload_status = meta['tracker_status'].get(tracker, {}).get('upload', False)
            if tracker in trackers and upload_status is True:
                if not bdmv_mi_created:
                    await common.get_bdmv_mediainfo(meta)
                    bdmv_mi_created = True

        progress_task = asyncio.create_task(print_progress("[yellow]Still processing, please wait...", interval=10))
        try:
            if 'manual_frames' not in meta:
                meta['manual_frames'] = {}
            manual_frames = meta['manual_frames']

            if meta.get('comparison', False):
                await add_comparison(meta)

            else:
                image_data_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/image_data.json"
                if os.path.exists(image_data_file) and not meta.get('image_list'):
                    try:
                        with open(image_data_file, 'r') as img_file:
                            image_data = json.load(img_file)

                            if 'image_list' in image_data and not meta.get('image_list'):
                                meta['image_list'] = image_data['image_list']
                                if meta.get('debug'):
                                    console.print(f"[cyan]Loaded {len(image_data['image_list'])} previously saved image links")

                            if 'image_sizes' in image_data and not meta.get('image_sizes'):
                                meta['image_sizes'] = image_data['image_sizes']
                                if meta.get('debug'):
                                    console.print("[cyan]Loaded previously saved image sizes")

                            if 'tonemapped' in image_data and not meta.get('tonemapped'):
                                meta['tonemapped'] = image_data['tonemapped']
                                if meta.get('debug'):
                                    console.print("[cyan]Loaded previously saved tonemapped status[/cyan]")
                    except Exception as e:
                        console.print(f"[yellow]Could not load saved image data: {str(e)}")

                # Take Screenshots
                try:
                    if meta['is_disc'] == "BDMV":
                        use_vs = meta.get('vapoursynth', False)
                        try:
                            await disc_screenshots(
                                meta, bdmv_filename, bdinfo, meta['uuid'], base_dir, use_vs,
                                meta.get('image_list', []), meta.get('ffdebug', False), None
                            )
                        except asyncio.CancelledError:
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup()
                            gc.collect()
                            reset_terminal()
                            raise Exception("Error during screenshot capture")
                        except Exception as e:
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup()
                            gc.collect()
                            reset_terminal()
                            raise Exception(f"Error during screenshot capture: {e}")

                    elif meta['is_disc'] == "DVD":
                        try:
                            await dvd_screenshots(
                                meta, 0, None, None
                            )
                        except asyncio.CancelledError:
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup()
                            gc.collect()
                            reset_terminal()
                            raise Exception("Error during screenshot capture")
                        except Exception as e:
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup()
                            gc.collect()
                            reset_terminal()
                            raise Exception(f"Error during screenshot capture: {e}")

                    else:
                        try:
                            if meta['debug']:
                                console.print(f"videopath: {videopath}, filename: {filename}, meta: {meta['uuid']}, base_dir: {base_dir}, manual_frames: {manual_frames}")

                            await screenshots(
                                videopath, filename, meta['uuid'], base_dir, meta,
                                manual_frames=manual_frames  # Pass additional kwargs directly
                            )
                        except asyncio.CancelledError:
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup()
                            gc.collect()
                            reset_terminal()
                            raise Exception("Error during screenshot capture")
                        except Exception as e:
                            console.print(traceback.format_exc())
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup()
                            gc.collect()
                            reset_terminal()
                            try:
                                raise Exception(f"Error during screenshot capture: {e}")
                            except Exception as e2:
                                if "workers" in str(e2):
                                    console.print("[red]max workers issue, see https://github.com/Audionut/Upload-Assistant/wiki/ffmpeg---max-workers-issues[/red]")
                                raise e2

                except asyncio.CancelledError:
                    await cleanup_screenshot_temp_files(meta)
                    await asyncio.sleep(0.1)
                    await cleanup()
                    gc.collect()
                    reset_terminal()
                    raise Exception("Error during screenshot capture")
                except Exception:
                    await cleanup_screenshot_temp_files(meta)
                    await asyncio.sleep(0.1)
                    await cleanup()
                    gc.collect()
                    reset_terminal()
                    raise Exception
                finally:
                    await asyncio.sleep(0.1)
                    await cleanup()
                    gc.collect()
                    reset_terminal()

                if 'image_list' not in meta:
                    meta['image_list'] = []
                manual_frames_str = meta.get('manual_frames', '')
                if isinstance(manual_frames_str, str):
                    manual_frames_list = [f.strip() for f in manual_frames_str.split(',') if f.strip()]
                    manual_frames_count = len(manual_frames_list)
                    if meta['debug']:
                        console.print(f"Manual frames entered: {manual_frames_count}")
                else:
                    manual_frames_count = 0
                if manual_frames_count > 0:
                    meta['screens'] = manual_frames_count
                if len(meta.get('image_list', [])) < meta.get('cutoff') and meta.get('skip_imghost_upload', False) is False:
                    return_dict = {}
                    try:
                        new_images, dummy_var = await upload_screens(
                            meta, meta['screens'], 1, 0, meta['screens'], [], return_dict=return_dict
                        )
                    except asyncio.CancelledError:
                        console.print("\n[red]Upload process interrupted! Cancelling tasks...[/red]")
                        return
                    except Exception as e:
                        raise e
                    finally:
                        reset_terminal()
                        if meta['debug']:
                            console.print("[yellow]Cleaning up resources...[/yellow]")
                        gc.collect()

                elif meta.get('skip_imghost_upload', False) is True and meta.get('image_list', False) is False:
                    meta['image_list'] = []

                with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
                    json.dump(meta, f, indent=4)

                if 'image_list' in meta and meta['image_list']:
                    try:
                        image_data = {
                            "image_list": meta.get('image_list', []),
                            "image_sizes": meta.get('image_sizes', {}),
                            "tonemapped": meta.get('tonemapped', False)
                        }

                        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/image_data.json", 'w') as img_file:
                            json.dump(image_data, img_file, indent=4)

                        if meta.get('debug'):
                            console.print(f"[cyan]Saved {len(meta['image_list'])} images to image_data.json")
                    except Exception as e:
                        console.print(f"[yellow]Failed to save image data: {str(e)}")
        finally:
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass

        # check for valid image hosts for trackers that require it
        for tracker_name in meta['trackers']:
            if tracker_name in ['BHD', 'DC', 'GPW', 'HUNO', 'MTV', 'OE', 'PTP', 'TVC']:
                tracker_class = tracker_class_map[tracker_name](config=config)
                await tracker_class.check_image_hosts(meta)

        torrent_path = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")
        if not os.path.exists(torrent_path):
            reuse_torrent = None
            if meta.get('rehash', False) is False and not meta['base_torrent_created'] and not meta['we_checked_them_all']:
                reuse_torrent = await client.find_existing_torrent(meta)
                if reuse_torrent is not None:
                    await create_base_from_existing_torrent(reuse_torrent, meta['base_dir'], meta['uuid'])

            if meta['nohash'] is False and reuse_torrent is None:
                create_torrent(meta, Path(meta['path']), "BASE")
            if meta['nohash']:
                meta['client'] = "none"

        elif os.path.exists(torrent_path) and meta.get('rehash', False) is True and meta['nohash'] is False:
            create_torrent(meta, Path(meta['path']), "BASE")

        if int(meta.get('randomized', 0)) >= 1:
            if not meta['mkbrr']:
                create_random_torrents(meta['base_dir'], meta['uuid'], meta['randomized'], meta['path'])

        meta = await gen_desc(meta)

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
            json.dump(meta, f, indent=4)


async def cleanup_screenshot_temp_files(meta):
    """Cleanup temporary screenshot files to prevent orphaned files in case of failures."""
    tmp_dir = f"{meta['base_dir']}/tmp/{meta['uuid']}"
    if os.path.exists(tmp_dir):
        try:
            for file in os.listdir(tmp_dir):
                file_path = os.path.join(tmp_dir, file)
                if os.path.isfile(file_path) and file.endswith((".png", ".jpg")):
                    os.remove(file_path)
                    if meta['debug']:
                        console.print(f"[yellow]Removed temporary screenshot file: {file_path}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error cleaning up temporary screenshot files: {e}[/red]", highlight=False)


async def get_log_file(base_dir, queue_name):
    """
    Returns the path to the log file for the given base directory and queue name.
    """
    safe_queue_name = queue_name.replace(" ", "_")
    return os.path.join(base_dir, "tmp", f"{safe_queue_name}_processed_files.log")


async def load_processed_files(log_file):
    """
    Loads the list of processed files from the log file.
    """
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            return set(json.load(f))
    return set()


async def save_processed_file(log_file, file_path):
    """
    Adds a processed file to the log, deduplicating and always appending to the end.
    """
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            try:
                processed_files = json.load(f)
            except Exception:
                processed_files = []
    else:
        processed_files = []

    processed_files = [entry for entry in processed_files if entry != file_path]
    processed_files.append(file_path)

    with open(log_file, "w") as f:
        json.dump(processed_files, f, indent=4)


def get_local_version(version_file):
    """Extracts the local version from the version.py file."""
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
        else:
            console.print("[red]Version not found in local file.")
            return None
    except FileNotFoundError:
        console.print("[red]Version file not found.")
        return None


def get_remote_version(url):
    """Fetches the latest version information from the remote repository."""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            content = response.text
            match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1), content
            else:
                console.print("[red]Version not found in remote file.")
                return None, None
        else:
            console.print(f"[red]Failed to fetch remote version file. Status code: {response.status_code}")
            return None, None
    except requests.RequestException as e:
        console.print(f"[red]An error occurred while fetching the remote version file: {e}")
        return None, None


def extract_changelog(content, from_version, to_version):
    """Extracts the changelog entries between the specified versions."""
    # Try to find the to_version with 'v' prefix first (current format)
    patterns_to_try = [
        rf'__version__\s*=\s*"{re.escape(to_version)}"\s*\n\s*"""\s*(.*?)\s*"""',  # Try with 'v' prefix
        rf'__version__\s*=\s*"{re.escape(to_version.lstrip("v"))}"\s*\n\s*"""\s*(.*?)\s*"""'  # Try without 'v' prefix
    ]

    for pattern in patterns_to_try:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            changelog = match.group(1).strip()
            # Remove the comment markers (# ) that were added by the GitHub Action
            changelog = re.sub(r'^# ', '', changelog, flags=re.MULTILINE)
            return changelog

    return None


async def update_notification(base_dir):
    version_file = os.path.join(base_dir, 'data', 'version.py')
    remote_version_url = 'https://raw.githubusercontent.com/Audionut/Upload-Assistant/master/data/version.py'

    notice = config['DEFAULT'].get('update_notification', True)
    verbose = config['DEFAULT'].get('verbose_notification', False)

    local_version = get_local_version(version_file)
    if not local_version:
        return

    if not notice:
        return local_version

    remote_version, remote_content = get_remote_version(remote_version_url)
    if not remote_version:
        return local_version

    if version.parse(remote_version) > version.parse(local_version):
        console.print(f"[red][NOTICE] [green]Update available: v[/green][yellow]{remote_version}")
        console.print(f"[red][NOTICE] [green]Current version: v[/green][yellow]{local_version}")
        asyncio.create_task(asyncio.sleep(1))
        if verbose and remote_content:
            changelog = extract_changelog(remote_content, local_version, remote_version)
            if changelog:
                asyncio.create_task(asyncio.sleep(1))
                console.print(f"{changelog}")
            else:
                console.print("[yellow]Changelog not found between versions.[/yellow]")

    return local_version


async def do_the_thing(base_dir):
    await asyncio.sleep(0.1)  # Ensure it's not racing
    bot = None
    meta = dict()
    paths = []
    for each in sys.argv[1:]:
        if os.path.exists(each):
            paths.append(os.path.abspath(each))
        else:
            break

    meta['ua_name'] = 'Upload Assistant'
    meta['current_version'] = await update_notification(base_dir)

    signature = 'Created by Upload Assistant'
    if meta.get('current_version', ''):
        signature += f" {meta['current_version']}"
    meta['ua_signature'] = signature
    meta['base_dir'] = base_dir

    cleanup_only = any(arg in ('--cleanup', '-cleanup') for arg in sys.argv) and len(sys.argv) <= 2
    sanitize_meta = config['DEFAULT'].get('sanitize_meta', True)

    try:
        # If cleanup is the only operation, use a dummy path to satisfy the parser
        if cleanup_only:
            args_list = sys.argv[1:] + ['dummy_path']
            meta, help, before_args = parser.parse(tuple(' '.join(args_list).split(' ')), meta)
            meta['path'] = None  # Clear the dummy path after parsing
        else:
            meta, help, before_args = parser.parse(tuple(' '.join(sys.argv[1:]).split(' ')), meta)

        if meta.get('cleanup'):
            if os.path.exists(f"{base_dir}/tmp"):
                shutil.rmtree(f"{base_dir}/tmp")
                console.print("[yellow]Successfully emptied tmp directory[/yellow]")
                console.print()
            if not meta.get('path') or cleanup_only:
                exit(0)

        if not meta.get('path'):
            exit(0)

        path = meta['path']
        path = os.path.abspath(path)
        if path.endswith('"'):
            path = path[:-1]

        is_binary = await get_mkbrr_path(meta, base_dir)
        if not meta['mkbrr']:
            try:
                meta['mkbrr'] = int(config['DEFAULT'].get('mkbrr', False))
            except ValueError:
                if meta['debug']:
                    console.print("[yellow]Invalid mkbrr config value, defaulting to False[/yellow]")
                meta['mkbrr'] = False
        if meta['mkbrr'] and not is_binary:
            console.print("[bold red]mkbrr binary is not available. Please ensure it is installed correctly.[/bold red]")
            console.print("[bold red]Reverting to Torf[/bold red]")
            console.print()
            meta['mkbrr'] = False

        queue, log_file = await handle_queue(path, meta, paths, base_dir)

        processed_files_count = 0
        skipped_files_count = 0
        base_meta = {k: v for k, v in meta.items()}

        for queue_item in queue:
            total_files = len(queue)
            try:
                meta = base_meta.copy()

                if meta.get('site_upload_queue'):
                    # Extract path and metadata from site upload queue item
                    path = await process_site_upload_item(queue_item, meta)
                    current_item_path = path  # Store for logging
                else:
                    # Regular queue processing
                    path = queue_item
                    current_item_path = path

                meta['path'] = path
                meta['uuid'] = None

                if not path:
                    raise ValueError("The 'path' variable is not defined or is empty.")

                tmp_path = os.path.join(base_dir, "tmp", os.path.basename(path))

                if meta.get('delete_tmp', False) and os.path.exists(tmp_path):
                    try:
                        shutil.rmtree(tmp_path)
                        os.makedirs(tmp_path, exist_ok=True)
                        if meta['debug']:
                            console.print(f"[yellow]Successfully cleaned temp directory for {os.path.basename(path)}[/yellow]")
                            console.print()
                    except Exception as e:
                        console.print(f"[bold red]Failed to delete temp directory: {str(e)}")

                meta_file = os.path.join(base_dir, "tmp", os.path.basename(path), "meta.json")

                keep_meta = config['DEFAULT'].get('keep_meta', False)

                if not keep_meta or meta.get('delete_meta', False):
                    if os.path.exists(meta_file):
                        try:
                            os.remove(meta_file)
                            if meta['debug']:
                                console.print(f"[bold yellow]Found and deleted existing metadata file: {meta_file}")
                        except Exception as e:
                            console.print(f"[bold red]Failed to delete metadata file {meta_file}: {str(e)}")
                    else:
                        if meta['debug']:
                            console.print(f"[yellow]No metadata file found at {meta_file}")

                if keep_meta and os.path.exists(meta_file):
                    with open(meta_file, "r") as f:
                        saved_meta = json.load(f)
                        console.print("[yellow]Existing metadata file found, it holds cached values")
                        meta.update(await merge_meta(meta, saved_meta, path))

            except Exception as e:
                console.print(f"[red]Exception: '{path}': {e}")
                reset_terminal()

            if use_discord and config['DISCORD'].get('discord_bot_token') and not meta['debug']:
                if (config.get('DISCORD', {}).get('only_unattended', False) and meta.get('unattended', False)) or not config.get('DISCORD', {}).get('only_unattended', False):
                    try:
                        console.print("[cyan]Starting Discord bot initialization...")
                        intents = discord.Intents.default()
                        intents.message_content = True
                        bot = discord.Client(intents=intents)
                        token = config['DISCORD']['discord_bot_token']
                        await asyncio.wait_for(bot.login(token), timeout=10)
                        connect_task = asyncio.create_task(bot.connect())

                        try:
                            await asyncio.wait_for(bot.wait_until_ready(), timeout=20)
                            console.print("[green]Discord Bot is ready!")
                        except asyncio.TimeoutError:
                            console.print("[bold red]Bot failed to connect within timeout period.")
                            console.print("[yellow]Continuing without Discord integration...")
                            if 'connect_task' in locals():
                                connect_task.cancel()
                    except discord.LoginFailure:
                        console.print("[bold red]Discord bot token is invalid. Please check your configuration.")
                    except discord.ClientException as e:
                        console.print(f"[bold red]Discord client exception: {e}")
                    except Exception as e:
                        console.print(f"[bold red]Unexpected error during Discord bot initialization: {e}")

            if meta['debug']:
                start_time = time.time()

            console.print(f"[green]Gathering info for {os.path.basename(path)}")

            await process_meta(meta, base_dir, bot=bot)

            if 'we_are_uploading' not in meta or not meta.get('we_are_uploading', False):
                if not meta.get('site_check', False):
                    if not meta.get('emby', False):
                        console.print("we are not uploading.......")
                    if 'queue' in meta and meta.get('queue') is not None:
                        processed_files_count += 1
                        if not meta.get('emby', False):
                            skipped_files_count += 1
                            console.print(f"[cyan]Processed {processed_files_count}/{total_files} files with {skipped_files_count} skipped uploading.")
                        else:
                            console.print(f"[cyan]Processed {processed_files_count}/{total_files}.")
                        if not meta['debug'] or "debug" in os.path.basename(log_file):
                            if log_file:
                                if meta.get('site_upload_queue'):
                                    await save_processed_path(log_file, current_item_path)
                                else:
                                    await save_processed_file(log_file, path)

            else:
                console.print()
                console.print("[yellow]Processing uploads to trackers.....")
                await process_trackers(meta, config, client, console, api_trackers, tracker_class_map, http_trackers, other_api_trackers)
                if use_discord and bot:
                    await send_upload_status_notification(config, bot, meta)
                if 'queue' in meta and meta.get('queue') is not None:
                    processed_files_count += 1
                    if 'limit_queue' in meta and int(meta['limit_queue']) > 0:
                        console.print(f"[cyan]Successfully uploaded {processed_files_count - skipped_files_count} of {meta['limit_queue']} in limit with {total_files} files.")
                    else:
                        console.print(f"[cyan]Successfully uploaded {processed_files_count - skipped_files_count}/{total_files} files.")
                    if not meta['debug'] or "debug" in os.path.basename(log_file):
                        if log_file:
                            if meta.get('site_upload_queue'):
                                await save_processed_path(log_file, current_item_path)
                            else:
                                await save_processed_file(log_file, path)

            if meta['debug']:
                finish_time = time.time()
                console.print(f"Uploads processed in {finish_time - start_time:.4f} seconds")

            if use_discord and bot:
                if config['DISCORD'].get('send_upload_links'):
                    try:
                        discord_message = ""
                        for tracker, status in meta.get('tracker_status', {}).items():
                            try:
                                if tracker == "MTV" and 'status_message' in status and "data error" not in str(status['status_message']):
                                    discord_message += f"{str(status['status_message'])}\n"
                                if 'torrent_id' in status:
                                    tracker_class = tracker_class_map[tracker](config=config)
                                    torrent_url = tracker_class.torrent_url
                                    discord_message += f"{tracker}: {torrent_url}{status['torrent_id']}\n"
                                else:
                                    if (
                                        'status_message' in status
                                        and 'torrent_id' not in status
                                        and "data error" not in str(status['status_message'])
                                        and tracker != "MTV"
                                    ):
                                        discord_message += f"{tracker}: {redact_private_info(status['status_message'])}\n"
                                    elif 'status_message' in status and "data error" in str(status['status_message']):
                                        discord_message += f"{tracker}: {str(status['status_message'])}\n"
                                    else:
                                        if 'skipping' in status and not status['skipping']:
                                            discord_message += f"{tracker} gave no useful message.\n"
                            except Exception as e:
                                discord_message += f"Error printing {tracker} data: {e}\n"
                        discord_message += "All tracker uploads processed.\n"
                        await send_discord_notification(config, bot, discord_message, debug=meta.get('debug', False), meta=meta)
                    except Exception as e:
                        console.print(f"[red]Error in tracker print loop: {e}[/red]")
                else:
                    await send_discord_notification(config, bot, f"Finished uploading: {meta['path']}\n", debug=meta.get('debug', False), meta=meta)

            find_requests = config['DEFAULT'].get('search_requests', False) if meta.get('search_requests') is None else meta.get('search_requests')
            if find_requests and meta['trackers'] not in ([], None) and not (meta.get('site_check', False) and 'is_disc' not in meta):
                console.print("[green]Searching for requests on supported trackers.....")
                tracker_setup = TRACKER_SETUP(config=config)
                if meta.get('site_check', False):
                    trackers = meta['requested_trackers']
                else:
                    trackers = meta['trackers']
                await tracker_setup.tracker_request(meta, trackers)

            if meta.get('site_check', False):
                if 'queue' in meta and meta.get('queue') is not None:
                    processed_files_count += 1
                    skipped_files_count += 1
                    console.print(f"[cyan]Processed {processed_files_count}/{total_files} files.")
                    if not meta['debug'] or "debug" in os.path.basename(log_file):
                        if log_file:
                            if meta.get('site_upload_queue'):
                                await save_processed_path(log_file, current_item_path)
                            else:
                                await save_processed_file(log_file, path)

            if meta.get('delete_tmp', False) and os.path.exists(tmp_path) and meta.get('emby', False):
                try:
                    shutil.rmtree(tmp_path)
                    console.print(f"[yellow]Successfully deleted temp directory for {os.path.basename(path)}[/yellow]")
                    console.print()
                except Exception as e:
                    console.print(f"[bold red]Failed to delete temp directory: {str(e)}")

            if 'limit_queue' in meta and int(meta['limit_queue']) > 0:
                if (processed_files_count - skipped_files_count) >= int(meta['limit_queue']):
                    if sanitize_meta and not meta.get('emby', False):
                        try:
                            await asyncio.sleep(0.2)  # We can't race the status prints
                            meta = await clean_meta_for_export(meta)
                        except Exception as e:
                            console.print(f"[red]Error cleaning meta for export: {e}")
                    await cleanup()
                    gc.collect()
                    reset_terminal()
                    break

            if sanitize_meta and not meta.get('emby', False):
                try:
                    await asyncio.sleep(0.2)
                    meta = await clean_meta_for_export(meta)
                except Exception as e:
                    console.print(f"[red]Error cleaning meta for export: {e}")
            await cleanup()
            gc.collect()
            reset_terminal()

    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}")
        if sanitize_meta:
            meta = await clean_meta_for_export(meta)
        console.print(traceback.format_exc())
        reset_terminal()

    finally:
        if bot is not None:
            await bot.close()
        if 'connect_task' in locals():
            connect_task.cancel()
            try:
                await connect_task
            except asyncio.CancelledError:
                pass
        if not sys.stdin.closed:
            reset_terminal()


async def get_mkbrr_path(meta, base_dir=None):
    try:
        mkbrr_path = await ensure_mkbrr_binary(base_dir, debug=meta['debug'], version="v1.14.0")
        return mkbrr_path
    except Exception as e:
        console.print(f"[red]Error setting up mkbrr binary: {e}[/red]")
        return None


def check_python_version():
    pyver = platform.python_version_tuple()
    if int(pyver[0]) != 3 or int(pyver[1]) < 9:
        console.print("[bold red]Python version is too low. Please use Python 3.9 or higher.")
        sys.exit(1)


async def main():
    try:
        await do_the_thing(base_dir)
    except asyncio.CancelledError:
        console.print("[red]Tasks were cancelled. Exiting safely.[/red]")
    except KeyboardInterrupt:
        console.print("[bold red]Program interrupted. Exiting safely.[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Unexpected error: {e}[/bold red]")


if __name__ == "__main__":
    check_python_version()

    try:
        # Use ProactorEventLoop for Windows subprocess handling
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        asyncio.run(main())  # Ensures proper loop handling and cleanup
    except (KeyboardInterrupt, SystemExit):
        pass
    except BaseException as e:
        console.print(f"[bold red]Critical error: {e}[/bold red]")
    finally:
        asyncio.run(cleanup())
        gc.collect()
        reset_terminal()
        sys.exit(0)
