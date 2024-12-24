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

from src.trackersetup import tracker_class_map, api_trackers, other_api_trackers, http_trackers
from src.trackerhandle import process_trackers
from src.queuemanage import handle_queue
from src.console import console

cli_ui.setup(color='always', title="Audionut's Upload Assistant")

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


async def process_meta(meta, base_dir):
    """Process the metadata for each queued path."""

    if meta['imghost'] is None:
        meta['imghost'] = config['DEFAULT']['img_host_1']

    if not meta['unattended']:
        ua = config['DEFAULT'].get('auto_mode', False)
        if str(ua).lower() == "true":
            meta['unattended'] = True
            console.print("[yellow]Running in Auto Mode")
    meta['base_dir'] = base_dir
    prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=config)
    meta = await prep.gather_prep(meta=meta, mode='cli')
    if not meta:
        return
    else:
        meta['cutoff'] = int(config['DEFAULT'].get('cutoff_screens', 3))
        if len(meta.get('image_list', [])) < meta.get('cutoff') and meta.get('skip_imghost_upload', False) is False:
            if 'image_list' not in meta:
                meta['image_list'] = []
            return_dict = {}
            new_images, dummy_var = upload_screens(meta, meta['screens'], 1, 0, meta['screens'], [], return_dict=return_dict)

        elif meta.get('skip_imghost_upload', False) is True and meta.get('image_list', False) is False:
            meta['image_list'] = []

        torrent_path = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")
        if not os.path.exists(torrent_path):
            reuse_torrent = None
            if meta.get('rehash', False) is False:
                reuse_torrent = await client.find_existing_torrent(meta)
                if reuse_torrent is not None:
                    await prep.create_base_from_existing_torrent(reuse_torrent, meta['base_dir'], meta['uuid'])

            if meta['nohash'] is False and reuse_torrent is None:
                prep.create_torrent(meta, Path(meta['path']), "BASE")
            if meta['nohash']:
                meta['client'] = "none"

        elif os.path.exists(torrent_path) and meta.get('rehash', False) is True and meta['nohash'] is False:
            prep.create_torrent(meta, Path(meta['path']), "BASE")

        if int(meta.get('randomized', 0)) >= 1:
            prep.create_random_torrents(meta['base_dir'], meta['uuid'], meta['randomized'], meta['path'])

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
            json.dump(meta, f, indent=4)


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
    Adds a processed file to the log.
    """
    processed_files = load_processed_files(log_file)
    processed_files.add(file_path)
    with open(log_file, "w") as f:
        json.dump(list(processed_files), f, indent=4)


async def do_the_thing(base_dir):
    meta = {'base_dir': base_dir}
    paths = []
    for each in sys.argv[1:]:
        if os.path.exists(each):
            paths.append(os.path.abspath(each))
        else:
            break

    meta, help, before_args = parser.parse(tuple(' '.join(sys.argv[1:]).split(' ')), meta)
    if meta.get('cleanup') and os.path.exists(f"{base_dir}/tmp"):
        shutil.rmtree(f"{base_dir}/tmp")
        console.print("[bold green]Successfully emptied tmp directory")

    if not meta.get('path'):
        exit(0)

    path = meta['path']
    path = os.path.abspath(path)
    if path.endswith('"'):
        path = path[:-1]

    queue, log_file = await handle_queue(path, meta, paths, base_dir)

    processed_files_count = 0
    base_meta = {k: v for k, v in meta.items()}
    for path in queue:
        total_files = len(queue)
        try:
            meta = base_meta.copy()
            meta['path'] = path
            meta['uuid'] = None

            if not path:
                raise ValueError("The 'path' variable is not defined or is empty.")

            meta_file = os.path.join(base_dir, "tmp", os.path.basename(path), "meta.json")

            if os.path.exists(meta_file):
                with open(meta_file, "r") as f:
                    saved_meta = json.load(f)
                    meta.update(await merge_meta(meta, saved_meta, path))
            else:
                if meta['debug']:
                    console.print(f"[yellow]No metadata file found at {meta_file}")

        except Exception as e:
            console.print(f"[red]Failed to load metadata for path '{path}': {e}")
        console.print(f"[green]Gathering info for {os.path.basename(path)}")
        await process_meta(meta, base_dir)
        if 'we_are_uploading' not in meta:
            console.print("we are not uploading.......")
            if meta.get('queue') is not None:
                processed_files_count += 1
                console.print(f"[cyan]Processed {processed_files_count}/{total_files} files.")
                if not meta['debug']:
                    if log_file:
                        await save_processed_file(log_file, path)

        else:
            await process_trackers(meta, config, client, console, api_trackers, tracker_class_map, http_trackers, other_api_trackers)
            if meta.get('queue') is not None:
                processed_files_count += 1
                console.print(f"[cyan]Processed {processed_files_count}/{total_files} files.")
                if not meta['debug']:
                    if log_file:
                        await save_processed_file(log_file, path)


if __name__ == '__main__':
    pyver = platform.python_version_tuple()
    if int(pyver[0]) != 3 or int(pyver[1]) < 12:
        console.print("[bold red]Python version is too low. Please use Python 3.12 or higher.")
        sys.exit(1)

    try:
        asyncio.run(do_the_thing(base_dir))  # Pass the correct base_dir value here
    except (KeyboardInterrupt):
        console.print("[bold red]Program interrupted. Exiting.")
