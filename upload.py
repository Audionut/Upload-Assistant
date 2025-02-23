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
from src.trackersetup import tracker_class_map, api_trackers, other_api_trackers, http_trackers
from src.trackerhandle import process_trackers
from src.queuemanage import handle_queue
from src.console import console
from src.torrentcreate import create_torrent, create_random_torrents, create_base_from_existing_torrent
from src.uphelper import UploadHelper
from src.trackerstatus import process_all_trackers
from src.takescreens import disc_screenshots, dvd_screenshots, screenshots


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
    meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await prep.get_name(meta)
    parser = Args(config)
    helper = UploadHelper()
    if meta.get('trackers'):
        trackers = meta['trackers']
    else:
        default_trackers = config['TRACKERS'].get('default_trackers', '')
        trackers = [tracker.strip() for tracker in default_trackers.split(',')]
    if "," in trackers:
        trackers = trackers.split(',')
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
            editargs += ("--trackers", *meta["trackers"])
        meta, help, before_args = parser.parse(editargs, meta)
        meta['edit'] = True
        meta = await prep.gather_prep(meta=meta, mode='cli')
        meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await prep.get_name(meta)
        confirm = await helper.get_confirmation(meta)

    successful_trackers = await process_all_trackers(meta)

    if meta.get('trackers_pass') is not None:
        meta['skip_uploading'] = meta.get('trackers_pass')
    else:
        meta['skip_uploading'] = int(config['DEFAULT'].get('tracker_pass_checks', 1))
    if successful_trackers < meta['skip_uploading'] and not meta['debug']:
        console.print(f"[red]Not enough successful trackers ({successful_trackers}/{meta['skip_uploading']}). EXITING........[/red]")

    else:
        meta['we_are_uploading'] = True
        filename = meta.get('title', None)
        bdinfo = meta.get('bdinfo', None)
        videopath = meta.get('filelist', [None])
        videopath = videopath[0] if videopath else None
        console.print(f"Processing {filename} for upload")
        if 'manual_frames' not in meta:
            meta['manual_frames'] = {}
        manual_frames = meta['manual_frames']
        # Take Screenshots
        if meta['is_disc'] == "BDMV":
            use_vs = meta.get('vapoursynth', False)
            try:
                await disc_screenshots(
                    meta, filename, bdinfo, meta['uuid'], base_dir, use_vs,
                    meta.get('image_list', []), meta.get('ffdebug', False), None
                )
            except Exception as e:
                console.print(f"[red]Error during BDMV screenshot capture: {e}")

        elif meta['is_disc'] == "DVD":
            try:
                await dvd_screenshots(
                    meta, 0, None, None
                )
            except Exception as e:
                print(f"Error during DVD screenshot capture: {e}")

        else:
            try:
                if meta['debug']:
                    console.print(f"videopath: {videopath}, filename: {filename}, meta: {meta['uuid']}, base_dir: {base_dir}, manual_frames: {manual_frames}")
                await screenshots(
                    videopath, filename, meta['uuid'], base_dir, meta,
                    manual_frames=manual_frames  # Pass additional kwargs directly
                )
            except Exception as e:
                print(f"Error during generic screenshot capture: {e}")

        meta['cutoff'] = int(config['DEFAULT'].get('cutoff_screens', 1))
        if len(meta.get('image_list', [])) < meta.get('cutoff') and meta.get('skip_imghost_upload', False) is False:
            if 'image_list' not in meta:
                meta['image_list'] = []
            return_dict = {}
            new_images, dummy_var = await upload_screens(meta, meta['screens'], 1, 0, meta['screens'], [], return_dict=return_dict)

        elif meta.get('skip_imghost_upload', False) is True and meta.get('image_list', False) is False:
            meta['image_list'] = []

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
            json.dump(meta, f, indent=4)

        torrent_path = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")
        if not os.path.exists(torrent_path):
            reuse_torrent = None
            if meta.get('rehash', False) is False:
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
            create_random_torrents(meta['base_dir'], meta['uuid'], meta['randomized'], meta['path'])

        if 'saved_description' in meta and meta['saved_description'] is False:
            meta = await prep.gen_desc(meta)
        else:
            meta = await prep.gen_desc(meta)

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
    processed_files = await load_processed_files(log_file)
    processed_files.add(file_path)
    with open(log_file, "w") as f:
        json.dump(list(processed_files), f, indent=4)


def reset_terminal():
    """Reset the terminal to a sane state."""
    if os.name == "posix":
        try:
            if sys.stdin and sys.stdin.fileno() >= 0 and sys.stdin.isatty():
                os.system("stty sane")
        except (ValueError, OSError):
            pass


async def do_the_thing(base_dir):
    await asyncio.sleep(0.1)  # Ensure it's not racing
    reset_terminal()
    meta = dict()
    paths = []
    for each in sys.argv[1:]:
        if os.path.exists(each):
            paths.append(os.path.abspath(each))
        else:
            break

    try:
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

                if meta.get('delete_meta') and os.path.exists(meta_file):
                    os.remove(meta_file)
                    console.print("[bold red]Successfully deleted meta.json")

                if os.path.exists(meta_file):
                    with open(meta_file, "r") as f:
                        saved_meta = json.load(f)
                        console.print("[yellow]Existing metadata file found, it holds cached values")
                        meta.update(await merge_meta(meta, saved_meta, path))
                else:
                    if meta['debug']:
                        console.print(f"[yellow]No metadata file found at {meta_file}")

            except Exception as e:
                console.print(f"[red]Failed to load metadata for path '{path}': {e}")
                reset_terminal()

            if meta['debug']:
                start_time = time.time()

            console.print(f"[green]Gathering info for {os.path.basename(path)}")
            await process_meta(meta, base_dir)

            if 'we_are_uploading' not in meta:
                console.print("we are not uploading.......")
                if 'queue' in meta and meta.get('queue') is not None:
                    processed_files_count += 1
                    console.print(f"[cyan]Processed {processed_files_count}/{total_files} files.")
                    if not meta['debug']:
                        if log_file:
                            await save_processed_file(log_file, path)

            else:
                await process_trackers(meta, config, client, console, api_trackers, tracker_class_map, http_trackers, other_api_trackers)
                if 'queue' in meta and meta.get('queue') is not None:
                    processed_files_count += 1
                    console.print(f"[cyan]Processed {processed_files_count}/{total_files} files.")
                    if not meta['debug']:
                        if log_file:
                            await save_processed_file(log_file, path)

            if 'limit_queue' in meta and meta['limit_queue'] > 0:
                if processed_files_count >= meta['limit_queue']:
                    console.print(f"[red]Processing limit of {meta['limit_queue']} files reached. Stopping queue processing.")
                    break

            if meta['debug']:
                finish_time = time.time()
                console.print(f"Uploads processed in {finish_time - start_time:.4f} seconds")

    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}")
        reset_terminal()

    finally:
        if not sys.stdin.closed:
            reset_terminal()


def check_python_version():
    pyver = platform.python_version_tuple()
    if int(pyver[0]) != 3 or int(pyver[1]) < 9:
        console.print("[bold red]Python version is too low. Please use Python 3.9 or higher.")
        sys.exit(1)


async def cleanup():
    """Ensure all running tasks and subprocesses are properly cleaned up before exiting."""
    console.print("[yellow]Cleaning up tasks before exiting...[/yellow]")

    # Terminate all tracked subprocesses
    while running_subprocesses:
        proc = running_subprocesses.pop()
        if proc.returncode is None:  # If still running
            console.print(f"[yellow]Terminating subprocess {proc.pid}...[/yellow]")
            proc.terminate()  # Send SIGTERM first
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)  # Wait for process to exit
            except asyncio.TimeoutError:
                console.print(f"[red]Subprocess {proc.pid} did not exit in time, force killing.[/red]")
                proc.kill()  # Force kill if it doesn't exit

        # Close process streams safely
        if proc.stdout:
            try:
                proc.stdout.close()
            except Exception:
                pass
        if proc.stderr:
            try:
                proc.stderr.close()
            except Exception:
                pass
        if proc.stdin:
            try:
                proc.stdin.close()
            except Exception:
                pass

    # Give some time for subprocess transport cleanup
    await asyncio.sleep(0.1)

    # Cancel all running asyncio tasks **gracefully**
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    console.print(f"[yellow]Cancelling {len(tasks)} remaining tasks...[/yellow]")

    for task in tasks:
        task.cancel()

    # Stage 1: Give tasks a moment to cancel themselves
    await asyncio.sleep(0.1)  # Ensures task loop unwinds properly

    # Stage 2: Gather tasks with exception handling
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
            console.print(f"[red]Error during cleanup: {result}[/red]")

    console.print("[green]Cleanup completed. Exiting safely.[/green]")


async def main():
    try:
        await do_the_thing(base_dir)  # Ensure base_dir is correctly defined
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
        sys.exit(0)
