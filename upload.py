#!/usr/bin/env python3
from src.args import Args
from src.clients import Clients
from src.uploadscreens import upload_screens
import json
from pathlib import Path
import asyncio
import os
import sys
import platform
import shutil
import cli_ui
import traceback
import time
import gc
import re
import requests
import discord
from packaging import version
from src.trackersetup import tracker_class_map, api_trackers, other_api_trackers, http_trackers
from src.trackerhandle import process_trackers
from src.queuemanage import handle_queue
from src.console import console
from src.torrentcreate import create_torrent, create_random_torrents, create_base_from_existing_torrent
from src.uphelper import UploadHelper
from src.trackerstatus import process_all_trackers
from src.takescreens import disc_screenshots, dvd_screenshots, screenshots
from src.cleanup import cleanup, reset_terminal
from src.add_comparison import add_comparison
from src.get_name import get_name
from src.get_desc import gen_desc
from discordbot import send_discord_notification, send_upload_status_notification
from cogs.redaction import clean_meta_for_export
from src.languages import process_desc_language


cli_ui.setup(color='always', title="Audionut's Upload Assistant")
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
discord_config = config.get('discord')
if discord_config:
    use_discord = discord_config.get('use_discord', False)


async def merge_meta(meta, saved_meta, path):
    """Merges saved metadata with the current meta, respecting overwrite rules."""
    with open(f"{base_dir}/tmp/{os.path.basename(path)}/meta.json") as f:
        saved_meta = json.load(f)
        overwrite_list = [
            'trackers', 'dupe', 'debug', 'anon', 'category', 'type', 'screens', 'nohash', 'manual_edition', 'imdb', 'tmdb_manual', 'mal', 'manual',
            'hdb', 'ptp', 'blu', 'no_season', 'no_aka', 'no_year', 'no_dub', 'no_tag', 'no_seed', 'client', 'desclink', 'descfile', 'desc', 'draft',
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
    meta['base_dir'] = base_dir
    prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=config)
    try:
        meta = await prep.gather_prep(meta=meta, mode='cli')
    except Exception as e:
        console.print(f"Error in gather_prep: {e}")
        console.print(traceback.format_exc())
        return
    meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await get_name(meta)
    parser = Args(config)
    helper = UploadHelper()
    if meta.get('trackers'):
        trackers = meta['trackers']
    else:
        default_trackers = config['TRACKERS'].get('default_trackers', '')
        trackers = [tracker.strip() for tracker in default_trackers.split(',')]

    if isinstance(trackers, str):
        if "," in trackers:
            trackers = [t.strip().upper() for t in trackers.split(',')]
        else:
            trackers = [trackers.strip().upper()]  # Make it a list with one element
    else:
        trackers = [t.strip().upper() for t in trackers]
    meta['trackers'] = trackers
    with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
        json.dump(meta, f, indent=4)
        f.close()
    confirm = await helper.get_confirmation(meta)
    while confirm is False:
        editargs = cli_ui.ask_string("Input args that need correction e.g. (--tag NTb --category tv --tmdb 12345)")
        editargs = (meta['path'],) + tuple(editargs.split())
        if meta.get('debug', False):
            editargs += ("--debug",)
        if meta.get('trackers', None) is not None:
            editargs += ("--trackers", ",".join(meta["trackers"]))
        meta, help, before_args = parser.parse(editargs, meta)
        if isinstance(meta.get('trackers'), str):
            if "," in meta['trackers']:
                meta['trackers'] = [t.strip() for t in meta['trackers'].split(',')]
            else:
                meta['trackers'] = [meta['trackers']]
        meta['edit'] = True
        meta = await prep.gather_prep(meta=meta, mode='cli')
        meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await get_name(meta)
        confirm = await helper.get_confirmation(meta)

    console.print(f"[green]Processing {meta['name']} for upload...[/green]")

    audio_prompted = False
    for tracker in ["HUNO", "OE", "AITHER", "ULCX", "DP", "CBR", "ASC", "BT", "LDU"]:
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

    successful_trackers = await process_all_trackers(meta)

    if meta.get('trackers_pass') is not None:
        meta['skip_uploading'] = meta.get('trackers_pass')
    else:
        meta['skip_uploading'] = int(config['DEFAULT'].get('tracker_pass_checks', 1))
    if successful_trackers < int(meta['skip_uploading']) and not meta['debug']:
        console.print(f"[red]Not enough successful trackers ({successful_trackers}/{meta['skip_uploading']}). EXITING........[/red]")

    else:
        meta['we_are_uploading'] = True
        filename = meta.get('title', None)
        bdmv_filename = meta.get('filename', None)
        bdinfo = meta.get('bdinfo', None)
        videopath = meta.get('filelist', [None])
        videopath = videopath[0] if videopath else None
        console.print(f"Processing {filename} for upload.....")
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
                            raise Exception(f"Error during screenshot capture: {e}")

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
                finally:
                    await asyncio.sleep(0.1)
                    await cleanup()
                    gc.collect()
                    reset_terminal()

                if 'image_list' not in meta:
                    meta['image_list'] = []
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
                            "image_sizes": meta.get('image_sizes', {})
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

        if not meta['mkbrr']:
            meta['mkbrr'] = int(config['DEFAULT'].get('mkbrr', False))
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

        if 'saved_description' in meta and meta['saved_description'] is False:
            meta = await gen_desc(meta)

        if meta.get('description') in ('None', '', ' '):
            meta['description'] = None

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
    pattern = rf'__version__\s*=\s*"{re.escape(to_version)}"\s*(.*?)__version__\s*=\s*"{re.escape(from_version)}"'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
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

    meta['current_version'] = await update_notification(base_dir)

    cleanup_only = any(arg in ('--cleanup', '-cleanup') for arg in sys.argv) and len(sys.argv) <= 2

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
                console.print("[bold green]Successfully emptied tmp directory")
            if not meta.get('path') or cleanup_only:
                exit(0)

        if not meta.get('path'):
            exit(0)

        path = meta['path']
        path = os.path.abspath(path)
        if path.endswith('"'):
            path = path[:-1]

        queue, log_file = await handle_queue(path, meta, paths, base_dir)

        processed_files_count = 0
        skipped_files_count = 0
        base_meta = {k: v for k, v in meta.items()}
        for path in queue:
            total_files = len(queue)
            try:
                meta = base_meta.copy()
                meta['path'] = path
                meta['uuid'] = None

                if not path:
                    raise ValueError("The 'path' variable is not defined or is empty.")

                tmp_path = os.path.join(base_dir, "tmp", os.path.basename(path))

                if meta.get('delete_tmp', False) and os.path.exists(tmp_path):
                    try:
                        shutil.rmtree(tmp_path)
                        os.makedirs(tmp_path, exist_ok=True)
                        console.print(f"[bold green]Successfully cleaned temp directory for {os.path.basename(path)}")
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

            sanitize_meta = config['DEFAULT'].get('sanitize_meta', True)
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

            if 'we_are_uploading' not in meta:
                console.print("we are not uploading.......")
                if 'queue' in meta and meta.get('queue') is not None:
                    processed_files_count += 1
                    skipped_files_count += 1
                    console.print(f"[cyan]Processed {processed_files_count}/{total_files} files with {skipped_files_count} skipped uploading.")
                    if not meta['debug']:
                        if log_file:
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
                    if not meta['debug']:
                        if log_file:
                            await save_processed_file(log_file, path)
                    await asyncio.sleep(0.1)
                    if sanitize_meta:
                        try:
                            await asyncio.sleep(0.2)  # We can't race the status prints
                            meta = await clean_meta_for_export(meta)
                        except Exception as e:
                            console.print(f"[red]Error cleaning meta for export: {e}")
                    await cleanup()
                    gc.collect()
                    reset_terminal()

            if 'limit_queue' in meta and int(meta['limit_queue']) > 0:
                if (processed_files_count - skipped_files_count) >= int(meta['limit_queue']):
                    console.print(f"[red]Uploading limit of {meta['limit_queue']} files reached. Stopping queue processing. {skipped_files_count} skipped files.")
                    break

            if meta['debug']:
                finish_time = time.time()
                console.print(f"Uploads processed in {finish_time - start_time:.4f} seconds")

            if use_discord and bot:
                await send_discord_notification(config, bot, f"Finsished uploading: {meta['path']}", debug=meta.get('debug', False), meta=meta)

            if sanitize_meta:
                try:
                    await asyncio.sleep(0.3)  # We can't race the status prints
                    meta = await clean_meta_for_export(meta)
                except Exception as e:
                    console.print(f"[red]Error cleaning meta for export: {e}")

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
    finally:
        await cleanup()
        reset_terminal()


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
        reset_terminal()
        sys.exit(0)
