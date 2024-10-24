# -*- coding: utf-8 -*-
from src.args import Args
from src.console import console
from src.exceptions import *  # noqa: F403
from src.trackers.PTP import PTP
from src.trackers.BLU import BLU
from src.trackers.AITHER import AITHER
from src.trackers.LST import LST
from src.trackers.OE import OE
from src.trackers.HDB import HDB
from src.trackers.TIK import TIK
from src.trackers.COMMON import COMMON

try:
    import traceback
    from src.discparse import DiscParse
    import multiprocessing
    import os
    import re
    import math
    from str2bool import str2bool
    import asyncio
    from guessit import guessit
    import ntpath
    from pathlib import Path
    import urllib
    import urllib.parse
    import ffmpeg
    import random
    import json
    import glob
    import requests
    import pyimgbox
    from pymediainfo import MediaInfo
    import tmdbsimple as tmdb
    from datetime import datetime
    from difflib import SequenceMatcher
    import torf
    from torf import Torrent
    import base64
    import time
    import anitopy
    import shutil
    from imdb import Cinemagoer
    import itertools
    import cli_ui
    from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn
    import platform
    import aiohttp
    from PIL import Image
    import io
    import sys
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

    async def prompt_user_for_confirmation(self, message: str) -> bool:
        try:
            response = input(f"{message} (Y/n): ").strip().lower()
            if response in ["y", "yes", ""]:
                return True
            return False
        except EOFError:
            sys.exit(1)

    async def check_images_concurrently(self, imagelist, meta):
        approved_image_hosts = ['ptpimg', 'imgbox']
        invalid_host_found = False  # Track if any image is on a non-approved host

        # Ensure meta['image_sizes'] exists
        if 'image_sizes' not in meta:
            meta['image_sizes'] = {}

        # Function to check each image's URL, host, and log size
        async def check_and_collect(image_dict):
            img_url = image_dict.get('raw_url')
            if not img_url:
                return None

            # Verify the image link
            if await self.check_image_link(img_url):
                # Check if the image is hosted on an approved image host
                if not any(host in img_url for host in approved_image_hosts):
                    nonlocal invalid_host_found
                    invalid_host_found = True  # Mark that we found an invalid host

                # Download the image to check its size
                async with aiohttp.ClientSession() as session:
                    async with session.get(img_url) as response:
                        if response.status == 200:
                            image_content = await response.read()  # Download the entire image content
                            image_size = len(image_content)  # Calculate the size in bytes
                            # Store the image size in meta['image_sizes']
                            meta['image_sizes'][img_url] = image_size
                            console.print(f"Size of {img_url}: {image_size / 1024:.2f} KiB")
                        else:
                            console.print(f"[red]Failed to get size for {img_url}. Skipping.")

                return image_dict
            else:
                return None

        # Run image verification concurrently
        tasks = [check_and_collect(image_dict) for image_dict in imagelist]
        results = await asyncio.gather(*tasks)

        # Collect valid images
        valid_images = [image for image in results if image is not None]

        # Convert default_trackers string into a list
        default_trackers = self.config['TRACKERS'].get('default_trackers', '')
        trackers_list = [tracker.strip() for tracker in default_trackers.split(',')]

        # Ensure meta['trackers'] is a list
        if meta.get('trackers') is not None:
            if isinstance(meta.get('trackers', ''), str):
                meta['trackers'] = [tracker.strip() for tracker in meta['trackers'].split(',')]
            if 'MTV' in meta.get('trackers', []):
                if invalid_host_found:
                    console.print("[red]Warning: Some images are not hosted on an MTV-approved image host. MTV will fail if you keep these images.[/red]")
        # Issue warning if any valid image is on an unapproved host and MTV is in the trackers list
        elif 'MTV' in trackers_list:
            if invalid_host_found:
                console.print("[red]Warning: Some images are not hosted on an MTV-approved image host. MTV will fail if you keep these images.[/red]")

        return valid_images

    async def check_image_link(self, url):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '').lower()
                        if 'image' in content_type:
                            # Attempt to load the image
                            image_data = await response.read()
                            try:
                                image = Image.open(io.BytesIO(image_data))
                                image.verify()  # This will check if the image is broken
                                console.print(f"[green]Image verified successfully: {url}[/green]")
                                return True
                            except (IOError, SyntaxError) as e:  # noqa #F841
                                console.print(f"[red]Image verification failed (corrupt image): {url}[/red]")
                                return False
                        else:
                            console.print(f"[red]Content type is not an image: {url}[/red]")
                            return False
                    else:
                        console.print(f"[red]Failed to retrieve image: {url} (status code: {response.status})[/red]")
                        return False
            except Exception as e:
                console.print(f"[red]Exception occurred while checking image: {url} - {str(e)}[/red]")
                return False

    async def update_meta_with_unit3d_data(self, meta, tracker_data, tracker_name):
        # Unpack the expected 9 elements, ignoring any additional ones
        tmdb, imdb, tvdb, mal, desc, category, infohash, imagelist, filename, *rest = tracker_data

        if tmdb not in [None, '0']:
            meta['tmdb_manual'] = tmdb
        if imdb not in [None, '0']:
            meta['imdb'] = str(imdb).zfill(7)
        if tvdb not in [None, '0']:
            meta['tvdb_id'] = tvdb
        if mal not in [None, '0']:
            meta['mal'] = mal
        if desc not in [None, '0', '']:
            meta[f'{tracker_name.lower()}_desc'] = desc
        if category.upper() in ['MOVIE', 'TV SHOW', 'FANRES']:
            meta['category'] = 'TV' if category.upper() == 'TV SHOW' else category.upper()

        if not meta.get('image_list'):  # Only handle images if image_list is not already populated
            if imagelist:  # Ensure imagelist is not empty before setting
                valid_images = await self.check_images_concurrently(imagelist, meta)
                if valid_images:
                    meta['image_list'] = valid_images
                    if meta.get('image_list'):  # Double-check if image_list is set before handling it
                        if not (meta.get('blu') or meta.get('aither') or meta.get('lst') or meta.get('oe') or meta.get('tik')) or meta['unattended']:
                            await self.handle_image_list(meta, tracker_name)

        if filename:
            meta[f'{tracker_name.lower()}_filename'] = filename

        console.print(f"[green]{tracker_name} data successfully updated in meta[/green]")

    async def update_metadata_from_tracker(self, tracker_name, tracker_instance, meta, search_term, search_file_folder):
        tracker_key = tracker_name.lower()
        manual_key = f"{tracker_key}_manual"
        found_match = False

        if tracker_name in ["BLU", "AITHER", "LST", "OE", "TIK"]:
            if meta.get(tracker_key) is not None:
                console.print(f"[cyan]{tracker_name} ID found in meta, reusing existing ID: {meta[tracker_key]}[/cyan]")
                tracker_data = await COMMON(self.config).unit3d_torrent_info(
                    tracker_name,
                    tracker_instance.torrent_url,
                    tracker_instance.search_url,
                    meta,
                    id=meta[tracker_key]
                )
            else:
                console.print(f"[yellow]No ID found in meta for {tracker_name}, searching by file name[/yellow]")
                tracker_data = await COMMON(self.config).unit3d_torrent_info(
                    tracker_name,
                    tracker_instance.torrent_url,
                    tracker_instance.search_url,
                    meta,
                    file_name=search_term
                )

            if any(item not in [None, '0'] for item in tracker_data[:3]):  # Check for valid tmdb, imdb, or tvdb
                console.print(f"[green]Valid data found on {tracker_name}, setting meta values[/green]")
                await self.update_meta_with_unit3d_data(meta, tracker_data, tracker_name)
                found_match = True
            else:
                console.print(f"[yellow]No valid data found on {tracker_name}[/yellow]")
                found_match = False

        elif tracker_name == "PTP":
            imdb_id = None  # Ensure imdb_id is defined
            # Check if the PTP ID is already in meta
            if meta.get('ptp') is None:
                # No PTP ID in meta, search by search term
                imdb_id, ptp_torrent_id, ptp_torrent_hash = await tracker_instance.get_ptp_id_imdb(search_term, search_file_folder, meta)
                if ptp_torrent_id:
                    meta['ptp'] = ptp_torrent_id
                    meta['imdb'] = str(imdb_id).zfill(7) if imdb_id else None

                    console.print(f"[green]{tracker_name} IMDb ID found: tt{meta['imdb']}[/green]")
                    if not meta['unattended']:
                        if await self.prompt_user_for_confirmation("Do you want to use this ID data from PTP?"):
                            found_match = True

                            # Retrieve PTP description and image list
                            ptp_desc, ptp_imagelist = await tracker_instance.get_ptp_description(ptp_torrent_id, meta, meta.get('is_disc', False))
                            meta['description'] = ptp_desc
                            meta['skip_gen_desc'] = True

                            if not meta['is_disc']:
                                if not meta.get('image_list'):  # Only handle images if image_list is not already populated
                                    valid_images = await self.check_images_concurrently(ptp_imagelist, meta)
                                    if valid_images:
                                        meta['image_list'] = valid_images
                                        await self.handle_image_list(meta, tracker_name)

                        else:
                            found_match = False

                    else:
                        found_match = True
                        ptp_desc, ptp_imagelist = await tracker_instance.get_ptp_description(ptp_torrent_id, meta, meta.get('is_disc', False))
                        meta['description'] = ptp_desc
                        meta['skip_gen_desc'] = True

                        if not meta['is_disc']:
                            if not meta.get('image_list'):  # Only handle images if image_list is not already populated
                                valid_images = await self.check_images_concurrently(ptp_imagelist)
                                if valid_images:
                                    meta['image_list'] = valid_images
                else:
                    console.print("[yellow]Skipping PTP as no match found[/yellow]")
                    found_match = False

            else:
                ptp_torrent_id = meta['ptp']
                console.print("[cyan]Using specified PTP ID to get IMDb ID[/cyan]")
                imdb_id, _, meta['ext_torrenthash'] = await tracker_instance.get_imdb_from_torrent_id(ptp_torrent_id)
                if imdb_id:
                    meta['imdb'] = str(imdb_id).zfill(7)
                    console.print(f"[green]IMDb ID found: tt{meta['imdb']}[/green]")
                    found_match = True
                    meta['skipit'] = True
                    ptp_desc, ptp_imagelist = await tracker_instance.get_ptp_description(meta['ptp'], meta, meta.get('is_disc', False))
                    meta['description'] = ptp_desc
                    meta['skip_gen_desc'] = True
                    if not meta['is_disc']:
                        if not meta.get('image_list'):  # Only handle images if image_list is not already populated
                            valid_images = await self.check_images_concurrently(ptp_imagelist, meta)
                            if valid_images:
                                meta['image_list'] = valid_images
                                console.print("[green]PTP images added to metadata.[/green]")
                else:
                    console.print(f"[yellow]Could not find IMDb ID using PTP ID: {ptp_torrent_id}[/yellow]")
                    found_match = False

        elif tracker_name == "HDB":
            if meta.get('hdb') is not None:
                meta[manual_key] = meta[tracker_key]
                console.print(f"[cyan]{tracker_name} ID found in meta, reusing existing ID: {meta[tracker_key]}[/cyan]")

                # Use get_info_from_torrent_id function if ID is found in meta
                imdb, tvdb_id, hdb_name, meta['ext_torrenthash'] = await tracker_instance.get_info_from_torrent_id(meta[tracker_key])

                meta['tvdb_id'] = str(tvdb_id) if tvdb_id else meta.get('tvdb_id')
                meta['hdb_name'] = hdb_name
                found_match = True

                # Skip user confirmation if searching by ID
                console.print(f"[green]{tracker_name} data found: IMDb ID: {imdb}, TVDb ID: {meta['tvdb_id']}, HDB Name: {meta['hdb_name']}[/green]")
            else:
                console.print("[yellow]No ID found in meta for HDB, searching by file name[/yellow]")

                # Use search_filename function if ID is not found in meta
                imdb, tvdb_id, hdb_name, meta['ext_torrenthash'], tracker_id = await tracker_instance.search_filename(search_term, search_file_folder, meta)

                meta['tvdb_id'] = str(tvdb_id) if tvdb_id else meta.get('tvdb_id')
                meta['hdb_name'] = hdb_name
                if tracker_id:
                    meta[tracker_key] = tracker_id
                found_match = True

                if found_match:
                    if imdb or tvdb_id or hdb_name:
                        console.print(f"[green]{tracker_name} data found: IMDb ID: {imdb}, TVDb ID: {meta['tvdb_id']}, HDB Name: {meta['hdb_name']}[/green]")
                        if await self.prompt_user_for_confirmation(f"Do you want to use the ID's found on {tracker_name}?"):
                            console.print(f"[green]{tracker_name} data retained.[/green]")
                        else:
                            console.print(f"[yellow]{tracker_name} data discarded.[/yellow]")
                            meta[tracker_key] = None
                            meta['tvdb_id'] = None
                            meta['hdb_name'] = None
                            found_match = False
                    else:
                        found_match = False

        return meta, found_match

    async def handle_image_list(self, meta, tracker_name):
        if meta.get('image_list'):
            console.print(f"[cyan]Found the following images from {tracker_name}:")
            for img in meta['image_list']:
                console.print(f"[blue]{img}[/blue]")

            if meta['unattended']:
                keep_images = True
            else:
                keep_images = await self.prompt_user_for_confirmation(f"Do you want to keep the images found on {tracker_name}?")
                if not keep_images:
                    meta['image_list'] = []
                    meta['image_sizes'] = {}
                    console.print(f"[yellow]Images discarded from {tracker_name}.")
                else:
                    console.print(f"[green]Images retained from {tracker_name}.")

    async def gather_prep(self, meta, mode):
        meta['mode'] = mode
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        meta['isdir'] = os.path.isdir(meta['path'])
        base_dir = meta['base_dir']

        if meta.get('uuid', None) is None:
            folder_id = os.path.basename(meta['path'])
            meta['uuid'] = folder_id
        if not os.path.exists(f"{base_dir}/tmp/{meta['uuid']}"):
            Path(f"{base_dir}/tmp/{meta['uuid']}").mkdir(parents=True, exist_ok=True)

        if meta['debug']:
            console.print(f"[cyan]ID: {meta['uuid']}")

        meta['is_disc'], videoloc, bdinfo, meta['discs'] = await self.get_disc(meta)

        # Debugging information
        # console.print(f"Debug: meta['filelist'] before population: {meta.get('filelist', 'Not Set')}")

        if meta['is_disc'] == "BDMV":
            video, meta['scene'], meta['imdb'] = self.is_scene(meta['path'], meta.get('imdb', None))
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
                meta['resolution'] = self.mi_resolution(bdinfo['video'][0]['res'], guessit(video), width="OTHER", scan="p", height="OTHER", actual_height=0)
            meta['sd'] = self.is_sd(meta['resolution'])

            mi = None

        elif meta['is_disc'] == "DVD":
            video, meta['scene'], meta['imdb'] = self.is_scene(meta['path'], meta.get('imdb', None))
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
                mi = self.exportInfo(f"{meta['discs'][0]['path']}/VTS_{meta['discs'][0]['main_set'][0][:2]}_1.VOB", False, meta['uuid'], meta['base_dir'], export_text=False)
                meta['mediainfo'] = mi
            else:
                mi = meta['mediainfo']

            meta['dvd_size'] = await self.get_dvd_size(meta['discs'], meta.get('manual_dvds'))
            meta['resolution'] = self.get_resolution(guessit(video), meta['uuid'], base_dir)
            meta['sd'] = self.is_sd(meta['resolution'])

        elif meta['is_disc'] == "HDDVD":
            video, meta['scene'], meta['imdb'] = self.is_scene(meta['path'], meta.get('imdb', None))
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
                mi = self.exportInfo(meta['discs'][0]['largest_evo'], False, meta['uuid'], meta['base_dir'], export_text=False)
                meta['mediainfo'] = mi
            else:
                mi = meta['mediainfo']
            meta['resolution'] = self.get_resolution(guessit(video), meta['uuid'], base_dir)
            meta['sd'] = self.is_sd(meta['resolution'])

        else:
            videopath, meta['filelist'] = self.get_video(videoloc, meta.get('mode', 'discord'))
            search_term = os.path.basename(meta['filelist'][0]) if meta['filelist'] else None
            search_file_folder = 'file'
            video, meta['scene'], meta['imdb'] = self.is_scene(videopath, meta.get('imdb', None))
            guess_name = ntpath.basename(video).replace('-', ' ')
            filename = guessit(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]}).get("title", guessit(re.sub("[^0-9a-zA-Z]+", " ", guess_name), {"excludes": ["country", "language"]})["title"])
            untouched_filename = os.path.basename(video)
            try:
                meta['search_year'] = guessit(video)['year']
            except Exception:
                meta['search_year'] = ""

            if not meta.get('edit', False):
                mi = self.exportInfo(videopath, meta['isdir'], meta['uuid'], base_dir, export_text=True)
                meta['mediainfo'] = mi
            else:
                mi = meta['mediainfo']

            if meta.get('resolution', None) is None:
                meta['resolution'] = self.get_resolution(guessit(video), meta['uuid'], base_dir)
            meta['sd'] = self.is_sd(meta['resolution'])

        if " AKA " in filename.replace('.', ' '):
            filename = filename.split('AKA')[0]
        meta['filename'] = filename

        meta['bdinfo'] = bdinfo

        # Debugging information after population
        # console.print(f"Debug: meta['filelist'] after population: {meta.get('filelist', 'Not Set')}")

        if not meta.get('image_list'):
            # Reuse information from trackers with fallback
            found_match = False

            if search_term:
                # Check if specific trackers are already set in meta
                specific_tracker = None
                if meta.get('ptp'):
                    specific_tracker = 'PTP'
                elif meta.get('hdb'):
                    specific_tracker = 'HDB'
                elif meta.get('blu'):
                    specific_tracker = 'BLU'
                elif meta.get('aither'):
                    specific_tracker = 'AITHER'
                elif meta.get('lst'):
                    specific_tracker = 'LST'
                elif meta.get('oe'):
                    specific_tracker = 'OE'
                elif meta.get('tik'):
                    specific_tracker = 'TIK'

                # If a specific tracker is found, only process that one
                if specific_tracker:
                    console.print(f"[blue]Processing only the {specific_tracker} tracker based on meta.[/blue]")

                    if specific_tracker == 'PTP' and str(self.config['TRACKERS'].get('PTP', {}).get('useAPI')).lower() == "true":
                        ptp = PTP(config=self.config)
                        meta, match = await self.update_metadata_from_tracker('PTP', ptp, meta, search_term, search_file_folder)
                        if match:
                            found_match = True

                    elif specific_tracker == 'BLU' and str(self.config['TRACKERS'].get('BLU', {}).get('useAPI')).lower() == "true":
                        blu = BLU(config=self.config)
                        meta, match = await self.update_metadata_from_tracker('BLU', blu, meta, search_term, search_file_folder)
                        if match:
                            found_match = True

                    elif specific_tracker == 'AITHER' and str(self.config['TRACKERS'].get('AITHER', {}).get('useAPI')).lower() == "true":
                        aither = AITHER(config=self.config)
                        meta, match = await self.update_metadata_from_tracker('AITHER', aither, meta, search_term, search_file_folder)
                        if match:
                            found_match = True

                    elif specific_tracker == 'LST' and str(self.config['TRACKERS'].get('LST', {}).get('useAPI')).lower() == "true":
                        lst = LST(config=self.config)
                        meta, match = await self.update_metadata_from_tracker('LST', lst, meta, search_term, search_file_folder)
                        if match:
                            found_match = True

                    elif specific_tracker == 'OE' and str(self.config['TRACKERS'].get('OE', {}).get('useAPI')).lower() == "true":
                        oe = OE(config=self.config)
                        meta, match = await self.update_metadata_from_tracker('OE', oe, meta, search_term, search_file_folder)
                        if match:
                            found_match = True

                    elif specific_tracker == 'TIK' and str(self.config['TRACKERS'].get('TIK', {}).get('useAPI')).lower() == "true":
                        tik = TIK(config=self.config)
                        meta, match = await self.update_metadata_from_tracker('TIK', tik, meta, search_term, search_file_folder)
                        if match:
                            found_match = True

                    elif specific_tracker == 'HDB' and str(self.config['TRACKERS'].get('HDB', {}).get('useAPI')).lower() == "true":
                        hdb = HDB(config=self.config)
                        meta, match = await self.update_metadata_from_tracker('HDB', hdb, meta, search_term, search_file_folder)
                        if match:
                            found_match = True
                else:
                    # Process all trackers if no specific tracker is set in meta
                    default_trackers = self.config['TRACKERS'].get('default_trackers', "").split(", ")

                    if "PTP" in default_trackers and not found_match:
                        if str(self.config['TRACKERS'].get('PTP', {}).get('useAPI')).lower() == "true":
                            ptp = PTP(config=self.config)
                            meta, match = await self.update_metadata_from_tracker('PTP', ptp, meta, search_term, search_file_folder)
                            if match:
                                found_match = True

                    if "BLU" in default_trackers and not found_match:
                        if str(self.config['TRACKERS'].get('BLU', {}).get('useAPI')).lower() == "true":
                            blu = BLU(config=self.config)
                            meta, match = await self.update_metadata_from_tracker('BLU', blu, meta, search_term, search_file_folder)
                            if match:
                                found_match = True

                    if "HDB" in default_trackers and not found_match:
                        if str(self.config['TRACKERS'].get('HDB', {}).get('useAPI')).lower() == "true":
                            hdb = HDB(config=self.config)
                            meta, match = await self.update_metadata_from_tracker('HDB', hdb, meta, search_term, search_file_folder)
                            if match:
                                found_match = True

                if not found_match:
                    console.print("[yellow]No matches found on any trackers.[/yellow]")
                else:
                    console.print(f"[green]Match found: {found_match}[/green]")
            else:
                console.print("[yellow]Warning: No valid search term available, skipping tracker updates.[/yellow]")
        else:
            console.print("Skipping existing search as meta already populated")

        if 'manual_frames' not in meta:
            meta['manual_frames'] = {}
        manual_frames = meta['manual_frames']
        # Take Screenshots
        if meta['is_disc'] == "BDMV":
            if meta.get('edit', False) is False:
                if meta.get('vapoursynth', False) is True:
                    use_vs = True
                else:
                    use_vs = False
                try:
                    ds = multiprocessing.Process(target=self.disc_screenshots, args=(filename, bdinfo, meta['uuid'], base_dir, use_vs, meta.get('image_list', []), meta.get('ffdebug', False), None))
                    ds.start()
                    while ds.is_alive() is True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    ds.terminate()
        elif meta['is_disc'] == "DVD":
            if meta.get('edit', False) is False:
                try:
                    ds = multiprocessing.Process(target=self.dvd_screenshots, args=(meta, 0, None))
                    ds.start()
                    while ds.is_alive() is True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    ds.terminate()
        else:
            if meta.get('edit', False) is False:
                try:
                    s = multiprocessing.Process(
                        target=self.screenshots,
                        args=(videopath, filename, meta['uuid'], base_dir, meta),  # Positional arguments
                        kwargs={'manual_frames': manual_frames}  # Keyword argument
                    )
                    s.start()
                    while s.is_alive() is True:
                        await asyncio.sleep(3)
                except KeyboardInterrupt:
                    s.terminate()

        meta['tmdb'] = meta.get('tmdb_manual', None)
        if meta.get('type', None) is None:
            meta['type'] = self.get_type(video, meta['scene'], meta['is_disc'])
        if meta.get('category', None) is None:
            meta['category'] = self.get_cat(video)
        else:
            meta['category'] = meta['category'].upper()
        if meta.get('tmdb', None) is None and meta.get('imdb', None) is None:
            meta['category'], meta['tmdb'], meta['imdb'] = self.get_tmdb_imdb_from_mediainfo(mi, meta['category'], meta['is_disc'], meta['tmdb'], meta['imdb'])
        if meta.get('tmdb', None) is None and meta.get('imdb', None) is None:
            meta = await self.get_tmdb_id(filename, meta['search_year'], meta, meta['category'], untouched_filename)
        elif meta.get('imdb', None) is not None and meta.get('tmdb_manual', None) is None:
            meta['imdb_id'] = str(meta['imdb']).replace('tt', '')
            meta = await self.get_tmdb_from_imdb(meta, filename)
        else:
            meta['tmdb_manual'] = meta.get('tmdb', None)

        # If no tmdb, use imdb for meta
        if int(meta['tmdb']) == 0:
            meta = await self.imdb_other_meta(meta)
        else:
            meta = await self.tmdb_other_meta(meta)
        # Search tvmaze
        meta['tvmaze_id'], meta['imdb_id'], meta['tvdb_id'] = await self.search_tvmaze(filename, meta['search_year'], meta.get('imdb_id', '0'), meta.get('tvdb_id', 0))
        # If no imdb, search for it
        if meta.get('imdb_id', None) is None:
            meta['imdb_id'] = await self.search_imdb(filename, meta['search_year'])
        if meta.get('imdb_info', None) is None and int(meta['imdb_id']) != 0:
            meta['imdb_info'] = await self.get_imdb_info(meta['imdb_id'], meta)
        if meta.get('tag', None) is None:
            meta['tag'] = self.get_tag(video, meta)
        else:
            if not meta['tag'].startswith('-') and meta['tag'] != "":
                meta['tag'] = f"-{meta['tag']}"
        meta = await self.get_season_episode(video, meta)
        meta = await self.tag_override(meta)

        meta['video'] = video
        meta['audio'], meta['channels'], meta['has_commentary'] = self.get_audio_v2(mi, meta, bdinfo)
        if meta['tag'][1:].startswith(meta['channels']):
            meta['tag'] = meta['tag'].replace(f"-{meta['channels']}", '')
        if meta.get('no_tag', False):
            meta['tag'] = ""
        meta['3D'] = self.is_3d(mi, bdinfo)
        if meta.get('manual_source', None):
            meta['source'] = meta['manual_source']
            _, meta['type'] = self.get_source(meta['type'], video, meta['path'], meta['is_disc'], meta)
        else:
            meta['source'], meta['type'] = self.get_source(meta['type'], video, meta['path'], meta['is_disc'], meta)
        if meta.get('service', None) in (None, ''):
            meta['service'], meta['service_longname'] = self.get_service(video, meta.get('tag', ''), meta['audio'], meta['filename'])
        elif meta.get('service'):
            services = self.get_service(get_services_only=True)
            meta['service_longname'] = max((k for k, v in services.items() if v == meta['service']), key=len, default=meta['service'])
        meta['uhd'] = self.get_uhd(meta['type'], guessit(meta['path']), meta['resolution'], meta['path'])
        meta['hdr'] = self.get_hdr(mi, bdinfo)
        meta['distributor'] = self.get_distributor(meta['distributor'])
        if meta.get('is_disc', None) == "BDMV":  # Blu-ray Specific
            meta['region'] = self.get_region(bdinfo, meta.get('region', None))
            meta['video_codec'] = self.get_video_codec(bdinfo)
        else:
            meta['video_encode'], meta['video_codec'], meta['has_encode_settings'], meta['bit_depth'] = self.get_video_encode(mi, meta['type'], bdinfo)
        if meta.get('no_edition') is False:
            meta['edition'], meta['repack'] = self.get_edition(meta['path'], bdinfo, meta['filelist'], meta.get('manual_edition'))
            if "REPACK" in meta.get('edition', ""):
                meta['repack'] = re.search(r"REPACK[\d]?", meta['edition'])[0]
                meta['edition'] = re.sub(r"REPACK[\d]?", "", meta['edition']).strip().replace('  ', ' ')
        else:
            meta['edition'] = ""

        # WORK ON THIS
        meta.get('stream', False)
        meta['stream'] = self.stream_optimized(meta['stream'])
        meta.get('anon', False)
        meta['anon'] = self.is_anon(meta['anon'])
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
    def get_video(self, videoloc, mode):
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
    Get and parse mediainfo
    """
    def exportInfo(self, video, isdir, folder_id, base_dir, export_text):
        def filter_mediainfo(data):
            filtered = {
                "creatingLibrary": data.get("creatingLibrary"),
                "media": {
                    "@ref": data["media"]["@ref"],
                    "track": []
                }
            }

            for track in data["media"]["track"]:
                if track["@type"] == "General":
                    filtered["media"]["track"].append({
                        "@type": track["@type"],
                        "UniqueID": track.get("UniqueID", {}),
                        "VideoCount": track.get("VideoCount", {}),
                        "AudioCount": track.get("AudioCount", {}),
                        "TextCount": track.get("TextCount", {}),
                        "MenuCount": track.get("MenuCount", {}),
                        "FileExtension": track.get("FileExtension", {}),
                        "Format": track.get("Format", {}),
                        "Format_Version": track.get("Format_Version", {}),
                        "FileSize": track.get("FileSize", {}),
                        "Duration": track.get("Duration", {}),
                        "OverallBitRate": track.get("OverallBitRate", {}),
                        "FrameRate": track.get("FrameRate", {}),
                        "FrameCount": track.get("FrameCount", {}),
                        "StreamSize": track.get("StreamSize", {}),
                        "IsStreamable": track.get("IsStreamable", {}),
                        "File_Created_Date": track.get("File_Created_Date", {}),
                        "File_Created_Date_Local": track.get("File_Created_Date_Local", {}),
                        "File_Modified_Date": track.get("File_Modified_Date", {}),
                        "File_Modified_Date_Local": track.get("File_Modified_Date_Local", {}),
                        "Encoded_Application": track.get("Encoded_Application", {}),
                        "Encoded_Library": track.get("Encoded_Library", {}),
                    })
                elif track["@type"] == "Video":
                    filtered["media"]["track"].append({
                        "@type": track["@type"],
                        "StreamOrder": track.get("StreamOrder", {}),
                        "ID": track.get("ID", {}),
                        "UniqueID": track.get("UniqueID", {}),
                        "Format": track.get("Format", {}),
                        "Format_Profile": track.get("Format_Profile", {}),
                        "Format_Version": track.get("Format_Version", {}),
                        "Format_Level": track.get("Format_Level", {}),
                        "Format_Tier": track.get("Format_Tier", {}),
                        "HDR_Format": track.get("HDR_Format", {}),
                        "HDR_Format_Version": track.get("HDR_Format_Version", {}),
                        "HDR_Format_String": track.get("HDR_Format_String", {}),
                        "HDR_Format_Profile": track.get("HDR_Format_Profile", {}),
                        "HDR_Format_Level": track.get("HDR_Format_Level", {}),
                        "HDR_Format_Settings": track.get("HDR_Format_Settings", {}),
                        "HDR_Format_Compression": track.get("HDR_Format_Compression", {}),
                        "HDR_Format_Compatibility": track.get("HDR_Format_Compatibility", {}),
                        "CodecID": track.get("CodecID", {}),
                        "CodecID_Hint": track.get("CodecID_Hint", {}),
                        "Duration": track.get("Duration", {}),
                        "BitRate": track.get("BitRate", {}),
                        "Width": track.get("Width", {}),
                        "Height": track.get("Height", {}),
                        "Stored_Height": track.get("Stored_Height", {}),
                        "Sampled_Width": track.get("Sampled_Width", {}),
                        "Sampled_Height": track.get("Sampled_Height", {}),
                        "PixelAspectRatio": track.get("PixelAspectRatio", {}),
                        "DisplayAspectRatio": track.get("DisplayAspectRatio", {}),
                        "FrameRate_Mode": track.get("FrameRate_Mode", {}),
                        "FrameRate": track.get("FrameRate", {}),
                        "FrameRate_Num": track.get("FrameRate_Num", {}),
                        "FrameRate_Den": track.get("FrameRate_Den", {}),
                        "FrameCount": track.get("FrameCount", {}),
                        "Standard": track.get("Standard", {}),
                        "ColorSpace": track.get("ColorSpace", {}),
                        "ChromaSubsampling": track.get("ChromaSubsampling", {}),
                        "ChromaSubsampling_Position": track.get("ChromaSubsampling_Position", {}),
                        "BitDepth": track.get("BitDepth", {}),
                        "ScanType": track.get("ScanType", {}),
                        "ScanOrder": track.get("ScanOrder", {}),
                        "Delay": track.get("Delay", {}),
                        "Delay_Source": track.get("Delay_Source", {}),
                        "StreamSize": track.get("StreamSize", {}),
                        "Language": track.get("Language", {}),
                        "Default": track.get("Default", {}),
                        "Forced": track.get("Forced", {}),
                        "colour_description_present": track.get("colour_description_present", {}),
                        "colour_description_present_Source": track.get("colour_description_present_Source", {}),
                        "colour_range": track.get("colour_range", {}),
                        "colour_range_Source": track.get("colour_range_Source", {}),
                        "colour_primaries": track.get("colour_primaries", {}),
                        "colour_primaries_Source": track.get("colour_primaries_Source", {}),
                        "transfer_characteristics": track.get("transfer_characteristics", {}),
                        "transfer_characteristics_Source": track.get("transfer_characteristics_Source", {}),
                        "transfer_characteristics_Original": track.get("transfer_characteristics_Original", {}),
                        "matrix_coefficients": track.get("matrix_coefficients", {}),
                        "matrix_coefficients_Source": track.get("matrix_coefficients_Source", {}),
                        "MasteringDisplay_ColorPrimaries": track.get("MasteringDisplay_ColorPrimaries", {}),
                        "MasteringDisplay_ColorPrimaries_Source": track.get("MasteringDisplay_ColorPrimaries_Source", {}),
                        "MasteringDisplay_Luminance": track.get("MasteringDisplay_Luminance", {}),
                        "MasteringDisplay_Luminance_Source": track.get("MasteringDisplay_Luminance_Source", {}),
                        "MaxCLL": track.get("MaxCLL", {}),
                        "MaxCLL_Source": track.get("MaxCLL_Source", {}),
                        "MaxFALL": track.get("MaxFALL", {}),
                        "MaxFALL_Source": track.get("MaxFALL_Source", {}),
                    })
                elif track["@type"] == "Audio":
                    filtered["media"]["track"].append({
                        "@type": track["@type"],
                        "StreamOrder": track.get("StreamOrder", {}),
                        "ID": track.get("ID", {}),
                        "UniqueID": track.get("UniqueID", {}),
                        "Format": track.get("Format", {}),
                        "Format_Commercial_IfAny": track.get("Format_Commercial_IfAny", {}),
                        "Format_Settings_Endianness": track.get("Format_Settings_Endianness", {}),
                        "Format_AdditionalFeatures": track.get("Format_AdditionalFeatures", {}),
                        "CodecID": track.get("CodecID", {}),
                        "Duration": track.get("Duration", {}),
                        "BitRate_Mode": track.get("BitRate_Mode", {}),
                        "BitRate": track.get("BitRate", {}),
                        "Channels": track.get("Channels", {}),
                        "ChannelPositions": track.get("ChannelPositions", {}),
                        "ChannelLayout": track.get("ChannelLayout", {}),
                        "Channels_Original": track.get("Channels_Original", {}),
                        "ChannelLayout_Original": track.get("ChannelLayout_Original", {}),
                        "SamplesPerFrame": track.get("SamplesPerFrame", {}),
                        "SamplingRate": track.get("SamplingRate", {}),
                        "SamplingCount": track.get("SamplingCount", {}),
                        "FrameRate": track.get("FrameRate", {}),
                        "FrameCount": track.get("FrameCount", {}),
                        "Compression_Mode": track.get("Compression_Mode", {}),
                        "Delay": track.get("Delay", {}),
                        "Delay_Source": track.get("Delay_Source", {}),
                        "Video_Delay": track.get("Video_Delay", {}),
                        "StreamSize": track.get("StreamSize", {}),
                        "Title": track.get("Title", {}),
                        "Language": track.get("Language", {}),
                        "ServiceKind": track.get("ServiceKind", {}),
                        "Default": track.get("Default", {}),
                        "Forced": track.get("Forced", {}),
                        "extra": track.get("extra", {}),
                    })
                elif track["@type"] == "Text":
                    filtered["media"]["track"].append({
                        "@type": track["@type"],
                        "@typeorder": track.get("@typeorder", {}),
                        "StreamOrder": track.get("StreamOrder", {}),
                        "ID": track.get("ID", {}),
                        "UniqueID": track.get("UniqueID", {}),
                        "Format": track.get("Format", {}),
                        "CodecID": track.get("CodecID", {}),
                        "Duration": track.get("Duration", {}),
                        "BitRate": track.get("BitRate", {}),
                        "FrameRate": track.get("FrameRate", {}),
                        "FrameCount": track.get("FrameCount", {}),
                        "ElementCount": track.get("ElementCount", {}),
                        "StreamSize": track.get("StreamSize", {}),
                        "Title": track.get("Title", {}),
                        "Language": track.get("Language", {}),
                        "Default": track.get("Default", {}),
                        "Forced": track.get("Forced", {}),
                    })
                elif track["@type"] == "Menu":
                    filtered["media"]["track"].append({
                        "@type": track["@type"],
                        "extra": track.get("extra", {}),
                    })
            return filtered

        if not os.path.exists(f"{base_dir}/tmp/{folder_id}/MEDIAINFO.txt") and export_text:
            console.print("[bold yellow]Exporting MediaInfo...")
            if not isdir:
                os.chdir(os.path.dirname(video))
            media_info = MediaInfo.parse(video, output="STRING", full=False, mediainfo_options={'inform_version': '1'})
            with open(f"{base_dir}/tmp/{folder_id}/MEDIAINFO.txt", 'w', newline="", encoding='utf-8') as export:
                export.write(media_info)
            with open(f"{base_dir}/tmp/{folder_id}/MEDIAINFO_CLEANPATH.txt", 'w', newline="", encoding='utf-8') as export_cleanpath:
                export_cleanpath.write(media_info.replace(video, os.path.basename(video)))
            console.print("[bold green]MediaInfo Exported.")

        if not os.path.exists(f"{base_dir}/tmp/{folder_id}/MediaInfo.json.txt"):
            media_info_json = MediaInfo.parse(video, output="JSON", mediainfo_options={'inform_version': '1'})
            media_info_dict = json.loads(media_info_json)
            filtered_info = filter_mediainfo(media_info_dict)
            with open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", 'w', encoding='utf-8') as export:
                json.dump(filtered_info, export, indent=4)

        with open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", 'r', encoding='utf-8') as f:
            mi = json.load(f)

        return mi

    """
    Get Resolution
    """

    def get_resolution(self, guess, folder_id, base_dir):
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
            elif framerate == "25.000":
                scan = "p"
            else:
                scan = "i"
            width_list = [3840, 2560, 1920, 1280, 1024, 854, 720, 15360, 7680, 0]
            height_list = [2160, 1440, 1080, 720, 576, 540, 480, 8640, 4320, 0]
            width = self.closest(width_list, int(width))
            actual_height = int(height)
            height = self.closest(height_list, int(height))
            res = f"{width}x{height}{scan}"
            resolution = self.mi_resolution(res, guess, width, scan, height, actual_height)
        return resolution

    def closest(self, lst, K):
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

    def mi_resolution(self, res, guess, width, scan, height, actual_height):
        res_map = {
            "3840x2160p": "2160p", "2160p": "2160p",
            "2560x1440p": "1440p", "1440p": "1440p",
            "1920x1080p": "1080p", "1080p": "1080p",
            "1920x1080i": "1080i", "1080i": "1080i",
            "1280x720p": "720p", "720p": "720p",
            "1280x540p": "720p", "1280x576p": "720p",
            "1024x576p": "576p", "576p": "576p",
            "1024x576i": "576i", "576i": "576i",
            "854x480p": "480p", "480p": "480p",
            "854x480i": "480i", "480i": "480i",
            "720x576p": "576p", "576p": "576p",
            "720x576i": "576i", "576i": "576i",
            "720x480p": "480p", "480p": "480p",
            "720x480i": "480i", "480i": "480i",
            "15360x8640p": "8640p", "8640p": "8640p",
            "7680x4320p": "4320p", "4320p": "4320p",
            "OTHER": "OTHER"}
        resolution = res_map.get(res, None)
        if actual_height == 540:
            resolution = "OTHER"
        if resolution is None:
            try:
                resolution = guess['screen_size']
            except Exception:
                width_map = {
                    '3840p': '2160p',
                    '2560p': '1550p',
                    '1920p': '1080p',
                    '1920i': '1080i',
                    '1280p': '720p',
                    '1024p': '576p',
                    '1024i': '576i',
                    '854p': '480p',
                    '854i': '480i',
                    '720p': '576p',
                    '720i': '576i',
                    '15360p': '4320p',
                    'OTHERp': 'OTHER'
                }
                resolution = width_map.get(f"{width}{scan}", "OTHER")
            resolution = self.mi_resolution(resolution, guess, width, scan, height, actual_height)

        return resolution

    def is_sd(self, resolution):
        if resolution in ("480i", "480p", "576i", "576p", "540p"):
            sd = 1
        else:
            sd = 0
        return sd

    """
    Is a scene release?
    """
    def is_scene(self, video, imdb=None):
        scene = False
        base = os.path.basename(video)
        base = os.path.splitext(base)[0]
        base = urllib.parse.quote(base)
        url = f"https://api.srrdb.com/v1/search/r:{base}"
        try:
            response = requests.get(url, timeout=30)
            response = response.json()
            if int(response.get('resultsCount', 0)) != 0:
                video = f"{response['results'][0]['release']}.mkv"
                scene = True
                r = requests.get(f"https://api.srrdb.com/v1/imdb/{base}")
                r = r.json()
                if r['releases'] != [] and imdb is None:
                    imdb = r['releases'][0].get('imdb', imdb) if r['releases'][0].get('imdb') is not None else imdb
                console.print(f"[green]SRRDB: Matched to {response['results'][0]['release']}")
        except Exception:
            video = video
            scene = False
            console.print("[yellow]SRRDB: No match found, or request has timed out")
        return video, scene, imdb

    """
    Generate Screenshots
    """
    def sanitize_filename(self, filename):
        # Replace invalid characters like colons with an underscore
        return re.sub(r'[<>:"/\\|?*]', '_', filename)

    def disc_screenshots(self, filename, bdinfo, folder_id, base_dir, use_vs, image_list, ffdebug, num_screens=None):
        if num_screens is None:
            num_screens = self.screens
        if num_screens == 0 or len(image_list) >= num_screens:
            return

        # Sanitize the filename
        sanitized_filename = self.sanitize_filename(filename)

        # Get longest m2ts
        length = 0
        for each in bdinfo['files']:
            int_length = sum(int(float(x)) * 60 ** i for i, x in enumerate(reversed(each['length'].split(':'))))
            if int_length > length:
                length = int_length
                for root, dirs, files in os.walk(bdinfo['path']):
                    for name in files:
                        if name.lower() == each['file'].lower():
                            file = f"{root}/{name}"

        if "VC-1" in bdinfo['video'][0]['codec'] or bdinfo['video'][0]['hdr_dv'] != "":
            keyframe = 'nokey'
        else:
            keyframe = 'none'

        os.chdir(f"{base_dir}/tmp/{folder_id}")
        i = len(glob.glob(f"{sanitized_filename}-*.png"))
        if i >= num_screens:
            i = num_screens
            console.print('[bold green]Reusing screenshots')
        else:
            console.print("[bold yellow]Saving Screens...")
            if use_vs is True:
                from src.vs import vs_screengn
                vs_screengn(source=file, encode=None, filter_b_frames=False, num=num_screens, dir=f"{base_dir}/tmp/{folder_id}/")
            else:
                loglevel = 'verbose' if bool(ffdebug) else 'quiet'
                debug = not ffdebug
                with Progress(
                    TextColumn("[bold green]Saving Screens..."),
                    BarColumn(),
                    "[cyan]{task.completed}/{task.total}",
                    TimeRemainingColumn()
                ) as progress:
                    screen_task = progress.add_task("[green]Saving Screens...", total=num_screens + 1)
                    ss_times = []
                    for i in range(num_screens + 1):
                        image = f"{base_dir}/tmp/{folder_id}/{sanitized_filename}-{i}.png"
                        try:
                            ss_times = self.valid_ss_time(ss_times, num_screens + 1, length)
                            (
                                ffmpeg
                                .input(file, ss=ss_times[-1], skip_frame=keyframe)
                                .output(image, vframes=1, pix_fmt="rgb24")
                                .overwrite_output()
                                .global_args('-loglevel', loglevel)
                                .run(quiet=debug)
                            )
                        except Exception:
                            console.print(traceback.format_exc())

                        self.optimize_images(image)
                        if os.path.getsize(Path(image)) <= 31000000 and self.img_host == "imgbb":
                            i += 1
                        elif os.path.getsize(Path(image)) <= 10000000 and self.img_host in ["imgbox", 'pixhost']:
                            i += 1
                        elif os.path.getsize(Path(image)) <= 75000:
                            console.print("[bold yellow]Image is incredibly small, retaking")
                            time.sleep(1)
                        elif self.img_host == "ptpimg":
                            i += 1
                        elif self.img_host == "lensdump":
                            i += 1
                        else:
                            console.print("[red]Image too large for your image host, retaking")
                            time.sleep(1)
                        progress.advance(screen_task)

                # Remove the smallest image
                smallest = None
                smallestsize = float('inf')
                for screens in glob.glob1(f"{base_dir}/tmp/{folder_id}/", f"{sanitized_filename}-*"):
                    screen_path = os.path.join(f"{base_dir}/tmp/{folder_id}/", screens)
                    screensize = os.path.getsize(screen_path)
                    if screensize < smallestsize:
                        smallestsize = screensize
                        smallest = screen_path

                if smallest is not None:
                    os.remove(smallest)

    def dvd_screenshots(self, meta, disc_num, num_screens=None):
        if num_screens is None:
            num_screens = self.screens
        if num_screens == 0 or (len(meta.get('image_list', [])) >= num_screens and disc_num == 0):
            return
        ifo_mi = MediaInfo.parse(f"{meta['discs'][disc_num]['path']}/VTS_{meta['discs'][disc_num]['main_set'][0][:2]}_0.IFO", mediainfo_options={'inform_version': '1'})
        sar = 1
        for track in ifo_mi.tracks:
            if track.track_type == "Video":
                if isinstance(track.duration, str):
                    # If the duration is a string, split and find the longest duration
                    durations = [float(d) for d in track.duration.split(' / ')]
                    length = max(durations) / 1000  # Use the longest duration
                else:
                    # If the duration is already an int or float, use it directly
                    length = float(track.duration) / 1000  # noqa #F841 # Convert to seconds

                # Proceed as usual for other fields
                par = float(track.pixel_aspect_ratio)
                dar = float(track.display_aspect_ratio)
                width = float(track.width)
                height = float(track.height)
        if par < 1:
            # multiply that dar by the height and then do a simple width / height
            new_height = dar * height
            sar = width / new_height
            w_sar = 1
            h_sar = sar
        else:
            sar = par
            w_sar = sar
            h_sar = 1

        main_set_length = len(meta['discs'][disc_num]['main_set'])
        if main_set_length >= 3:
            main_set = meta['discs'][disc_num]['main_set'][1:-1]
        elif main_set_length == 2:
            main_set = meta['discs'][disc_num]['main_set'][1:]
        elif main_set_length == 1:
            main_set = meta['discs'][disc_num]['main_set']
        n = 0
        os.chdir(f"{meta['base_dir']}/tmp/{meta['uuid']}")
        i = 0
        if len(glob.glob(f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['discs'][disc_num]['name']}-*.png")) >= num_screens:
            i = num_screens
            console.print('[bold green]Reusing screenshots')
        else:
            if bool(meta.get('ffdebug', False)) is True:
                loglevel = 'verbose'
                debug = False
            looped = 0
            retake = False
            with Progress(
                TextColumn("[bold green]Saving Screens..."),
                BarColumn(),
                "[cyan]{task.completed}/{task.total}",
                TimeRemainingColumn()
            ) as progress:
                screen_task = progress.add_task("[green]Saving Screens...", total=num_screens + 1)
                ss_times = []
                for i in range(num_screens + 1):
                    if n >= len(main_set):
                        n = 0
                    if n >= num_screens:
                        n -= num_screens
                    image = f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['discs'][disc_num]['name']}-{i}.png"
                    if not os.path.exists(image) or retake is not False:
                        retake = False
                        loglevel = 'quiet'
                        debug = True
                        if bool(meta.get('debug', False)):
                            loglevel = 'error'
                            debug = False

                        def _is_vob_good(n, loops, num_screens):
                            voblength = 300
                            vob_mi = MediaInfo.parse(f"{meta['discs'][disc_num]['path']}/VTS_{main_set[n]}", output='JSON')
                            vob_mi = json.loads(vob_mi)
                            try:
                                voblength = float(vob_mi['media']['track'][1]['Duration'])
                                return voblength, n
                            except Exception:
                                try:
                                    voblength = float(vob_mi['media']['track'][2]['Duration'])
                                    return voblength, n
                                except Exception:
                                    n += 1
                                    if n >= len(main_set):
                                        n = 0
                                    if n >= num_screens:
                                        n -= num_screens
                                    if loops < 6:
                                        loops = loops + 1
                                        voblength, n = _is_vob_good(n, loops, num_screens)
                                        return voblength, n
                                    else:
                                        return 300, n
                        try:
                            voblength, n = _is_vob_good(n, 0, num_screens)
                            # img_time = random.randint(round(voblength/5), round(voblength - voblength/5))
                            ss_times = self.valid_ss_time(ss_times, num_screens + 1, voblength)
                            ff = ffmpeg.input(f"{meta['discs'][disc_num]['path']}/VTS_{main_set[n]}", ss=ss_times[-1])
                            if w_sar != 1 or h_sar != 1:
                                ff = ff.filter('scale', int(round(width * w_sar)), int(round(height * h_sar)))
                            (
                                ff
                                .output(image, vframes=1, pix_fmt="rgb24")
                                .overwrite_output()
                                .global_args('-loglevel', loglevel)
                                .run(quiet=debug)
                            )
                        except Exception:
                            console.print(traceback.format_exc())
                        self.optimize_images(image)
                        n += 1
                        try:
                            if os.path.getsize(Path(image)) <= 31000000 and self.img_host == "imgbb":
                                i += 1
                            elif os.path.getsize(Path(image)) <= 10000000 and self.img_host in ["imgbox", 'pixhost']:
                                i += 1
                            elif os.path.getsize(Path(image)) <= 75000:
                                console.print("[yellow]Image is incredibly small (and is most likely to be a single color), retaking")
                                retake = True
                                time.sleep(1)
                            elif self.img_host == "ptpimg":
                                i += 1
                            elif self.img_host == "lensdump":
                                i += 1
                            elif self.img_host == "ptscreens":
                                i += 1
                            elif self.img_host == "oeimg":
                                i += 1
                            else:
                                console.print("[red]Image too large for your image host, retaking")
                                retake = True
                                time.sleep(1)
                            looped = 0
                        except Exception:
                            if looped >= 25:
                                console.print('[red]Failed to take screenshots')
                                exit()
                            looped += 1
                    progress.advance(screen_task)
            # remove smallest image
            smallest = None
            smallestsize = 99**99
            for screens in glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}/", f"{meta['discs'][disc_num]['name']}-*"):
                screen_path = os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}/", screens)
                screensize = os.path.getsize(screen_path)
                if screensize < smallestsize:
                    smallestsize = screensize
                    smallest = screen_path

            if smallest is not None:
                os.remove(smallest)

    def screenshots(self, path, filename, folder_id, base_dir, meta, num_screens=None, force_screenshots=False, manual_frames=None):
        if 'image_list' not in meta:
            meta['image_list'] = []

        existing_images = [img for img in meta['image_list'] if isinstance(img, dict) and img.get('img_url', '').startswith('http')]

        if len(existing_images) >= 3 and not force_screenshots:
            console.print("[yellow]There are already at least 3 images in the image list. Skipping additional screenshots.")
            return

        if num_screens is None:
            num_screens = self.screens - len(existing_images)
        if num_screens <= 0:
            return

        with open(f"{base_dir}/tmp/{folder_id}/MediaInfo.json", encoding='utf-8') as f:
            mi = json.load(f)
            video_track = mi['media']['track'][1]
            length = video_track.get('Duration', mi['media']['track'][0]['Duration'])
            width = float(video_track.get('Width'))
            height = float(video_track.get('Height'))
            par = float(video_track.get('PixelAspectRatio', 1))
            dar = float(video_track.get('DisplayAspectRatio'))
            frame_rate = float(video_track.get('FrameRate', 24.0))

            if par == 1:
                sar = w_sar = h_sar = 1
            elif par < 1:
                new_height = dar * height
                sar = width / new_height
                w_sar = 1
                h_sar = sar
            else:
                sar = w_sar = par
                h_sar = 1
            length = round(float(length))
            os.chdir(f"{base_dir}/tmp/{folder_id}")
            i = 0

            loglevel = 'quiet'
            debug = True
            if bool(meta.get('ffdebug', False)) is True:
                loglevel = 'verbose'
                debug = False

            retake = False
            with Progress(
                TextColumn("[bold green]Saving Screens..."),
                BarColumn(),
                "[cyan]{task.completed}/{task.total}",
                TimeRemainingColumn()
            ) as progress:
                ss_times = []
                screen_task = progress.add_task("[green]Saving Screens...", total=num_screens)

                if manual_frames:
                    if isinstance(manual_frames, str):
                        manual_frames = [frame.strip() for frame in manual_frames.split(',') if frame.strip().isdigit()]
                    elif isinstance(manual_frames, list):
                        manual_frames = [frame for frame in manual_frames if isinstance(frame, int) or frame.isdigit()]

                    # Convert to integers
                    manual_frames = [int(frame) for frame in manual_frames]
                    ss_times = [frame / frame_rate for frame in manual_frames]

                    # If not enough manual frames, fill in with random frames
                    if len(ss_times) < num_screens:
                        console.print(f"[yellow]Not enough manual frames provided. Using random frames for remaining {num_screens - len(ss_times)} screenshots.")
                        random_times = self.valid_ss_time(ss_times, num_screens - len(ss_times), length)
                        ss_times.extend(random_times)

                else:
                    # No manual frames provided, generate random times
                    # console.print("[yellow]No manual frames provided. Generating random frames.")
                    ss_times = self.valid_ss_time(ss_times, num_screens, length)
                    console.print(f"ss_times {ss_times}")

                for i in range(num_screens):
                    image_path = os.path.abspath(f"{base_dir}/tmp/{folder_id}/{filename}-{i}.png")
                    console.print(f"image_path {image_path}")
                    if not os.path.exists(image_path) or retake is not False:
                        console.print("Hit retry=false")
                        retake = False
                        try:
                            console.print(f"Taking screenshot at time (s): {ss_times[i]}")
                            ff = ffmpeg.input(path, ss=ss_times[i])

                            if w_sar != 1 or h_sar != 1:
                                ff = ff.filter('scale', int(round(width * w_sar)), int(round(height * h_sar)))

                            console.print(f"Saving screenshot to {image_path}")
                            (
                                ff
                                .output(image_path, vframes=1, pix_fmt="rgb24")
                                .overwrite_output()
                                .global_args('-loglevel', loglevel)
                                .run(quiet=debug)
                            )

                        except Exception as e:
                            console.print(f"[red]Error during screenshot capture: {e}")
                            sys.exit(1)

                        self.optimize_images(image_path)
                        if not manual_frames:
                            if os.path.getsize(Path(image_path)) <= 75000:
                                console.print("[yellow]Image is incredibly small, retaking")
                                retake = True
                                time.sleep(1)
                        if os.path.getsize(Path(image_path)) <= 31000000 and self.img_host == "imgbb" and retake is False:
                            i += 1
                        elif os.path.getsize(Path(image_path)) <= 10000000 and self.img_host in ["imgbox", 'pixhost'] and retake is False:
                            i += 1
                        elif self.img_host in ["ptpimg", "lensdump", "ptscreens", "oeimg"] and retake is False:
                            i += 1
                        elif self.img_host == "freeimage.host":
                            console.print("[bold red]Support for freeimage.host has been removed. Please remove from your config")
                            exit()
                        elif retake is True:
                            pass
                        else:
                            console.print("[red]Image too large for your image host, retaking")
                            retake = True
                            time.sleep(1)

                    progress.advance(screen_task)

                new_images = glob.glob(f"{filename}-*.png")
                for image in new_images:
                    img_dict = {
                        'img_url': image,
                        'raw_url': image,
                        'web_url': image
                    }
                    meta['image_list'].append(img_dict)

                if len(meta['image_list']) > self.screens:
                    local_images = [img for img in meta['image_list'] if not img['img_url'].startswith('http')]
                    if local_images:
                        smallest = min(local_images, key=lambda x: os.path.getsize(x['img_url']))
                        os.remove(smallest['img_url'])
                        meta['image_list'].remove(smallest)
                    else:
                        console.print("[yellow]No local images found to remove.")

    def valid_ss_time(self, ss_times, num_screens, length, manual_frames=None):
        if manual_frames:
            ss_times.extend(manual_frames[:num_screens])  # Use only as many as needed
            console.print(f"[green]Using provided manual frame numbers for screenshots: {ss_times}")
            return ss_times

        # Generate random times if manual frames are not provided
        while len(ss_times) < num_screens:
            valid_time = True
            sst = random.randint(round(length / 5), round(4 * length / 5))  # Adjust range for more spread out times
            for each in ss_times:
                tolerance = length / 10 / num_screens
                if abs(sst - each) <= tolerance:
                    valid_time = False
                    break
            if valid_time:
                ss_times.append(sst)

        return ss_times

    def optimize_images(self, image):
        if self.config['DEFAULT'].get('optimize_images', True) is True:
            if self.config['DEFAULT'].get('shared_seedbox', True) is True:
                # Get number of CPU cores
                num_cores = multiprocessing.cpu_count()
                # Limit the number of threads based on half available cores
                max_threads = num_cores // 2
                # Set cores for oxipng usage
                os.environ['RAYON_NUM_THREADS'] = str(max_threads)
            if os.path.exists(image):
                try:
                    pyver = platform.python_version_tuple()
                    if int(pyver[0]) == 3 and int(pyver[1]) >= 7:
                        import oxipng
                    if os.path.getsize(image) >= 16000000:
                        oxipng.optimize(image, level=6)
                    else:
                        oxipng.optimize(image, level=3)
                except (KeyboardInterrupt, Exception):
                    sys.exit(1)
        return

    """
    Get type and category
    """

    def get_type(self, video, scene, is_disc):
        filename = os.path.basename(video).lower()
        if "remux" in filename:
            type = "REMUX"
        elif any(word in filename for word in [" web ", ".web.", "web-dl"]):
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
            console.print("[bold red]DVDRip Detected, exiting")
            exit()
        else:
            type = "ENCODE"
        return type

    def get_cat(self, video):
        # if category is None:
        category = guessit(video.replace('1.0', ''))['type']
        if category.lower() == "movie":
            category = "MOVIE"  # 1
        elif category.lower() in ("tv", "episode"):
            category = "TV"  # 2
        else:
            category = "MOVIE"
        return category

    async def get_tmdb_from_imdb(self, meta, filename):
        if meta.get('tmdb_manual') is not None:
            meta['tmdb'] = meta['tmdb_manual']
            return meta
        imdb_id = meta['imdb']
        if str(imdb_id)[:2].lower() != "tt":
            imdb_id = f"tt{imdb_id}"
        find = tmdb.Find(id=imdb_id)
        info = find.info(external_source="imdb_id")
        if len(info['movie_results']) >= 1:
            meta['category'] = "MOVIE"
            meta['tmdb'] = info['movie_results'][0]['id']
        elif len(info['tv_results']) >= 1:
            meta['category'] = "TV"
            meta['tmdb'] = info['tv_results'][0]['id']
        else:
            imdb_info = await self.get_imdb_info(imdb_id.replace('tt', ''), meta)
            title = imdb_info.get("title")
            if title is None:
                title = filename
            year = imdb_info.get('year')
            if year is None:
                year = meta['search_year']
            console.print(f"[yellow]TMDb was unable to find anything with that IMDb, searching TMDb for {title}")
            meta = await self.get_tmdb_id(title, year, meta, meta['category'], imdb_info.get('original title', imdb_info.get('localized title', meta['uuid'])))
            if meta.get('tmdb') in ('None', '', None, 0, '0'):
                if meta.get('mode', 'discord') == 'cli':
                    console.print('[yellow]Unable to find a matching TMDb entry')
                    tmdb_id = console.input("Please enter tmdb id: ")
                    parser = Args(config=self.config)
                    meta['category'], meta['tmdb'] = parser.parse_tmdb_id(id=tmdb_id, category=meta.get('category'))
        await asyncio.sleep(2)
        return meta

    async def get_tmdb_id(self, filename, search_year, meta, category, untouched_filename="", attempted=0):
        search = tmdb.Search()
        try:
            if category == "MOVIE":
                search.movie(query=filename, year=search_year)
            elif category == "TV":
                search.tv(query=filename, first_air_date_year=search_year)
            if meta.get('tmdb_manual') is not None:
                meta['tmdb'] = meta['tmdb_manual']
            else:
                meta['tmdb'] = search.results[0]['id']
                meta['category'] = category
        except IndexError:
            try:
                if category == "MOVIE":
                    search.movie(query=filename)
                elif category == "TV":
                    search.tv(query=filename)
                meta['tmdb'] = search.results[0]['id']
                meta['category'] = category
            except IndexError:
                if category == "MOVIE":
                    category = "TV"
                else:
                    category = "MOVIE"
                if attempted <= 1:
                    attempted += 1
                    meta = await self.get_tmdb_id(filename, search_year, meta, category, untouched_filename, attempted)
                elif attempted == 2:
                    attempted += 1
                    meta = await self.get_tmdb_id(anitopy.parse(guessit(untouched_filename, {"excludes": ["country", "language"]})['title'])['anime_title'], search_year, meta, meta['category'], untouched_filename, attempted)
                if meta['tmdb'] in (None, ""):
                    console.print(f"[red]Unable to find TMDb match for {filename}")
                    if meta.get('mode', 'discord') == 'cli':
                        tmdb_id = cli_ui.ask_string("Please enter tmdb id in this format: tv/12345 or movie/12345")
                        parser = Args(config=self.config)
                        meta['category'], meta['tmdb'] = parser.parse_tmdb_id(id=tmdb_id, category=meta.get('category'))
                        meta['tmdb_manual'] = meta['tmdb']
                        return meta

        return meta

    async def tmdb_other_meta(self, meta):

        if meta['tmdb'] == "0":
            try:
                title = guessit(meta['path'], {"excludes": ["country", "language"]})['title'].lower()
                title = title.split('aka')[0]
                meta = await self.get_tmdb_id(guessit(title, {"excludes": ["country", "language"]})['title'], meta['search_year'], meta)
                if meta['tmdb'] == "0":
                    meta = await self.get_tmdb_id(title, "", meta, meta['category'])
            except Exception:
                if meta.get('mode', 'discord') == 'cli':
                    console.print("[bold red]Unable to find tmdb entry. Exiting.")
                    exit()
                else:
                    console.print("[bold red]Unable to find tmdb entry")
                    return meta
        if meta['category'] == "MOVIE":
            movie = tmdb.Movies(meta['tmdb'])
            response = movie.info()
            meta['title'] = response['title']
            if response['release_date']:
                meta['year'] = datetime.strptime(response['release_date'], '%Y-%m-%d').year
            else:
                console.print('[yellow]TMDB does not have a release date, using year from filename instead (if it exists)')
                meta['year'] = meta['search_year']
            external = movie.external_ids()
            if meta.get('imdb', None) is None:
                imdb_id = external.get('imdb_id', "0")
                if imdb_id == "" or imdb_id is None:
                    meta['imdb_id'] = '0'
                else:
                    meta['imdb_id'] = str(int(imdb_id.replace('tt', ''))).zfill(7)
            else:
                meta['imdb_id'] = str(meta['imdb']).replace('tt', '').zfill(7)
            if meta.get('tvdb_id', '0') in ['', ' ', None, 'None', '0']:
                meta['tvdb_id'] = external.get('tvdb_id', '0')
                if meta['tvdb_id'] in ["", None, " ", "None"]:
                    meta['tvdb_id'] = '0'
            try:
                videos = movie.videos()
                for each in videos.get('results', []):
                    if each.get('site', "") == 'YouTube' and each.get('type', "") == "Trailer":
                        meta['youtube'] = f"https://www.youtube.com/watch?v={each.get('key')}"
                        break
            except Exception:
                console.print('[yellow]Unable to grab videos from TMDb.')

            meta['aka'], original_language = await self.get_imdb_aka(meta['imdb_id'])
            if original_language is not None:
                meta['original_language'] = original_language
            else:
                meta['original_language'] = response['original_language']

            meta['original_title'] = response.get('original_title', meta['title'])
            meta['keywords'] = self.get_keywords(movie)
            meta['genres'] = self.get_genres(response)
            meta['tmdb_directors'] = self.get_directors(movie)
            if meta.get('anime', False) is False:
                meta['mal_id'], meta['aka'], meta['anime'] = self.get_anime(response, meta)
            if meta.get('mal') is not None:
                meta['mal_id'] = meta['mal']
            meta['poster'] = response.get('poster_path', "")
            meta['tmdb_poster'] = response.get('poster_path', "")
            meta['overview'] = response['overview']
            meta['tmdb_type'] = 'Movie'
            meta['runtime'] = response.get('episode_run_time', 60)
        elif meta['category'] == "TV":
            tv = tmdb.TV(meta['tmdb'])
            response = tv.info()
            meta['title'] = response['name']
            if response['first_air_date']:
                meta['year'] = datetime.strptime(response['first_air_date'], '%Y-%m-%d').year
            else:
                console.print('[yellow]TMDB does not have a release date, using year from filename instead (if it exists)')
                meta['year'] = meta['search_year']
            external = tv.external_ids()
            if meta.get('imdb', None) is None:
                imdb_id = external.get('imdb_id', "0")
                if imdb_id == "" or imdb_id is None:
                    meta['imdb_id'] = '0'
                else:
                    meta['imdb_id'] = str(int(imdb_id.replace('tt', ''))).zfill(7)
            else:
                meta['imdb_id'] = str(int(meta['imdb'].replace('tt', ''))).zfill(7)
            if meta.get('tvdb_id', '0') in ['', ' ', None, 'None', '0']:
                meta['tvdb_id'] = external.get('tvdb_id', '0')
                if meta['tvdb_id'] in ["", None, " ", "None"]:
                    meta['tvdb_id'] = '0'
            try:
                videos = tv.videos()
                for each in videos.get('results', []):
                    if each.get('site', "") == 'YouTube' and each.get('type', "") == "Trailer":
                        meta['youtube'] = f"https://www.youtube.com/watch?v={each.get('key')}"
                        break
            except Exception:
                console.print('[yellow]Unable to grab videos from TMDb.')

            # meta['aka'] = f" AKA {response['original_name']}"
            meta['aka'], original_language = await self.get_imdb_aka(meta['imdb_id'])
            if original_language is not None:
                meta['original_language'] = original_language
            else:
                meta['original_language'] = response['original_language']
            meta['original_title'] = response.get('original_name', meta['title'])
            meta['keywords'] = self.get_keywords(tv)
            meta['genres'] = self.get_genres(response)
            meta['tmdb_directors'] = self.get_directors(tv)
            meta['mal_id'], meta['aka'], meta['anime'] = self.get_anime(response, meta)
            if meta.get('mal') is not None:
                meta['mal_id'] = meta['mal']
            meta['poster'] = response.get('poster_path', '')
            meta['overview'] = response['overview']

            meta['tmdb_type'] = response.get('type', 'Scripted')
            runtime = response.get('episode_run_time', [60])
            if runtime == []:
                runtime = [60]
            meta['runtime'] = runtime[0]
        if meta['poster'] not in (None, ''):
            meta['poster'] = f"https://image.tmdb.org/t/p/original{meta['poster']}"

        difference = SequenceMatcher(None, meta['title'].lower(), meta['aka'][5:].lower()).ratio()
        if difference >= 0.9 or meta['aka'][5:].strip() == "" or meta['aka'][5:].strip().lower() in meta['title'].lower():
            meta['aka'] = ""
        if f"({meta['year']})" in meta['aka']:
            meta['aka'] = meta['aka'].replace(f"({meta['year']})", "").strip()

        return meta

    def get_keywords(self, tmdb_info):
        if tmdb_info is not None:
            tmdb_keywords = tmdb_info.keywords()
            if tmdb_keywords.get('keywords') is not None:
                keywords = [f"{keyword['name'].replace(',', ' ')}" for keyword in tmdb_keywords.get('keywords')]
            elif tmdb_keywords.get('results') is not None:
                keywords = [f"{keyword['name'].replace(',', ' ')}" for keyword in tmdb_keywords.get('results')]
            return (', '.join(keywords))
        else:
            return ''

    def get_genres(self, tmdb_info):
        if tmdb_info is not None:
            tmdb_genres = tmdb_info.get('genres', [])
            if tmdb_genres is not []:
                genres = [f"{genre['name'].replace(',', ' ')}" for genre in tmdb_genres]
            return (', '.join(genres))
        else:
            return ''

    def get_directors(self, tmdb_info):
        if tmdb_info is not None:
            tmdb_credits = tmdb_info.credits()
            directors = []
            if tmdb_credits.get('cast', []) != []:
                for each in tmdb_credits['cast']:
                    if each.get('known_for_department', '') == "Directing":
                        directors.append(each.get('original_name', each.get('name')))
            return directors
        else:
            return ''

    def get_anime(self, response, meta):
        tmdb_name = meta['title']
        if meta.get('aka', "") == "":
            alt_name = ""
        else:
            alt_name = meta['aka']
        anime = False
        animation = False
        for each in response['genres']:
            if each['id'] == 16:
                animation = True
        if response['original_language'] == 'ja' and animation is True:
            romaji, mal_id, eng_title, season_year, episodes = self.get_romaji(tmdb_name, meta.get('mal', None))
            alt_name = f" AKA {romaji}"

            anime = True
            # mal = AnimeSearch(romaji)
            # mal_id = mal.results[0].mal_id
        else:
            mal_id = 0
        if meta.get('mal_id', 0) != 0:
            mal_id = meta.get('mal_id')
        if meta.get('mal') is not None:
            mal_id = meta.get('mal')
        return mal_id, alt_name, anime

    def get_romaji(self, tmdb_name, mal):
        if mal is None:
            mal = 0
            tmdb_name = tmdb_name.replace('-', "").replace("The Movie", "")
            tmdb_name = ' '.join(tmdb_name.split())
            query = '''
                query ($search: String) {
                    Page (page: 1) {
                        pageInfo {
                            total
                        }
                    media (search: $search, type: ANIME, sort: SEARCH_MATCH) {
                        id
                        idMal
                        title {
                            romaji
                            english
                            native
                        }
                        seasonYear
                        episodes
                    }
                }
            }
            '''
            # Define our query variables and values that will be used in the query request
            variables = {
                'search': tmdb_name
            }
        else:
            query = '''
                query ($search: Int) {
                    Page (page: 1) {
                        pageInfo {
                            total
                        }
                    media (idMal: $search, type: ANIME, sort: SEARCH_MATCH) {
                        id
                        idMal
                        title {
                            romaji
                            english
                            native
                        }
                        seasonYear
                        episodes
                    }
                }
            }
            '''
            # Define our query variables and values that will be used in the query request
            variables = {
                'search': mal
            }

        # Make the HTTP Api request
        url = 'https://graphql.anilist.co'
        try:
            response = requests.post(url, json={'query': query, 'variables': variables})
            json = response.json()
            media = json['data']['Page']['media']
        except Exception:
            console.print('[red]Failed to get anime specific info from anilist. Continuing without it...')
            media = []
        if media not in (None, []):
            result = {'title': {}}
            difference = 0
            for anime in media:
                search_name = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", tmdb_name.lower().replace(' ', ''))
                for title in anime['title'].values():
                    if title is not None:
                        title = re.sub(u'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]+ (?=[A-Za-z ]+–)', "", title.lower().replace(' ', ''), re.U)
                        diff = SequenceMatcher(None, title, search_name).ratio()
                        if diff >= difference:
                            result = anime
                            difference = diff

            romaji = result['title'].get('romaji', result['title'].get('english', ""))
            mal_id = result.get('idMal', 0)
            eng_title = result['title'].get('english', result['title'].get('romaji', ""))
            season_year = result.get('season_year', "")
            episodes = result.get('episodes', 0)
        else:
            romaji = eng_title = season_year = ""
            episodes = mal_id = 0
        if mal_id in [None, 0]:
            mal_id = mal
        if not episodes:
            episodes = 0
        return romaji, mal_id, eng_title, season_year, episodes

    """
    Mediainfo/Bdinfo > meta
    """
    def get_audio_v2(self, mi, meta, bdinfo):
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
            if format_settings in ['Explicit']:
                format_settings = ""
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
                if meta.get('original_language', '') != 'en':
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
            codec = track.get('CodecID_Hint', '')

        audio = f"{dual} {codec or ''} {format_settings or ''} {chan or ''}{extra or ''}"
        audio = ' '.join(audio.split())
        return audio, chan, has_commentary

    def is_3d(self, mi, bdinfo):
        if bdinfo is not None:
            if bdinfo['video'][0]['3d'] != "":
                return "3D"
            else:
                return ""
        else:
            return ""

    def get_tag(self, video, meta):
        try:
            tag = guessit(video)['release_group']
            tag = f"-{tag}"
        except Exception:
            tag = ""
        if tag == "-":
            tag = ""
        if tag[1:].lower() in ["nogroup", 'nogrp']:
            tag = ""
        return tag

    def get_source(self, type, video, path, is_disc, meta):
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

    def get_uhd(self, type, guess, resolution, path):
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

    def get_hdr(self, mi, bdinfo):
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

    def get_region(self, bdinfo, region=None):
        label = bdinfo.get('label', bdinfo.get('title', bdinfo.get('path', ''))).replace('.', ' ')
        if region is not None:
            region = region.upper()
        else:
            regions = {
                'AFG': 'AFG', 'AIA': 'AIA', 'ALA': 'ALA', 'ALG': 'ALG', 'AND': 'AND', 'ANG': 'ANG', 'ARG': 'ARG',
                'ARM': 'ARM', 'ARU': 'ARU', 'ASA': 'ASA', 'ATA': 'ATA', 'ATF': 'ATF', 'ATG': 'ATG', 'AUS': 'AUS',
                'AUT': 'AUT', 'AZE': 'AZE', 'BAH': 'BAH', 'BAN': 'BAN', 'BDI': 'BDI', 'BEL': 'BEL', 'BEN': 'BEN',
                'BER': 'BER', 'BES': 'BES', 'BFA': 'BFA', 'BHR': 'BHR', 'BHU': 'BHU', 'BIH': 'BIH', 'BLM': 'BLM',
                'BLR': 'BLR', 'BLZ': 'BLZ', 'BOL': 'BOL', 'BOT': 'BOT', 'BRA': 'BRA', 'BRB': 'BRB', 'BRU': 'BRU',
                'BVT': 'BVT', 'CAM': 'CAM', 'CAN': 'CAN', 'CAY': 'CAY', 'CCK': 'CCK', 'CEE': 'CEE', 'CGO': 'CGO',
                'CHA': 'CHA', 'CHI': 'CHI', 'CHN': 'CHN', 'CIV': 'CIV', 'CMR': 'CMR', 'COD': 'COD', 'COK': 'COK',
                'COL': 'COL', 'COM': 'COM', 'CPV': 'CPV', 'CRC': 'CRC', 'CRO': 'CRO', 'CTA': 'CTA', 'CUB': 'CUB',
                'CUW': 'CUW', 'CXR': 'CXR', 'CYP': 'CYP', 'DJI': 'DJI', 'DMA': 'DMA', 'DOM': 'DOM', 'ECU': 'ECU',
                'EGY': 'EGY', 'ENG': 'ENG', 'EQG': 'EQG', 'ERI': 'ERI', 'ESH': 'ESH', 'ESP': 'ESP', 'ETH': 'ETH',
                'FIJ': 'FIJ', 'FLK': 'FLK', 'FRA': 'FRA', 'FRO': 'FRO', 'FSM': 'FSM', 'GAB': 'GAB', 'GAM': 'GAM',
                'GBR': 'GBR', 'GEO': 'GEO', 'GER': 'GER', 'GGY': 'GGY', 'GHA': 'GHA', 'GIB': 'GIB', 'GLP': 'GLP',
                'GNB': 'GNB', 'GRE': 'GRE', 'GRL': 'GRL', 'GRN': 'GRN', 'GUA': 'GUA', 'GUF': 'GUF', 'GUI': 'GUI',
                'GUM': 'GUM', 'GUY': 'GUY', 'HAI': 'HAI', 'HKG': 'HKG', 'HMD': 'HMD', 'HON': 'HON', 'HUN': 'HUN',
                'IDN': 'IDN', 'IMN': 'IMN', 'IND': 'IND', 'IOT': 'IOT', 'IRL': 'IRL', 'IRN': 'IRN', 'IRQ': 'IRQ',
                'ISL': 'ISL', 'ISR': 'ISR', 'ITA': 'ITA', 'JAM': 'JAM', 'JEY': 'JEY', 'JOR': 'JOR', 'JPN': 'JPN',
                'KAZ': 'KAZ', 'KEN': 'KEN', 'KGZ': 'KGZ', 'KIR': 'KIR', 'KNA': 'KNA', 'KOR': 'KOR', 'KSA': 'KSA',
                'KUW': 'KUW', 'KVX': 'KVX', 'LAO': 'LAO', 'LBN': 'LBN', 'LBR': 'LBR', 'LBY': 'LBY', 'LCA': 'LCA',
                'LES': 'LES', 'LIE': 'LIE', 'LKA': 'LKA', 'LUX': 'LUX', 'MAC': 'MAC', 'MAD': 'MAD', 'MAF': 'MAF',
                'MAR': 'MAR', 'MAS': 'MAS', 'MDA': 'MDA', 'MDV': 'MDV', 'MEX': 'MEX', 'MHL': 'MHL', 'MKD': 'MKD',
                'MLI': 'MLI', 'MLT': 'MLT', 'MNG': 'MNG', 'MNP': 'MNP', 'MON': 'MON', 'MOZ': 'MOZ', 'MRI': 'MRI',
                'MSR': 'MSR', 'MTN': 'MTN', 'MTQ': 'MTQ', 'MWI': 'MWI', 'MYA': 'MYA', 'MYT': 'MYT', 'NAM': 'NAM',
                'NCA': 'NCA', 'NCL': 'NCL', 'NEP': 'NEP', 'NFK': 'NFK', 'NIG': 'NIG', 'NIR': 'NIR', 'NIU': 'NIU',
                'NLD': 'NLD', 'NOR': 'NOR', 'NRU': 'NRU', 'NZL': 'NZL', 'OMA': 'OMA', 'PAK': 'PAK', 'PAN': 'PAN',
                'PAR': 'PAR', 'PCN': 'PCN', 'PER': 'PER', 'PHI': 'PHI', 'PLE': 'PLE', 'PLW': 'PLW', 'PNG': 'PNG',
                'POL': 'POL', 'POR': 'POR', 'PRK': 'PRK', 'PUR': 'PUR', 'QAT': 'QAT', 'REU': 'REU', 'ROU': 'ROU',
                'RSA': 'RSA', 'RUS': 'RUS', 'RWA': 'RWA', 'SAM': 'SAM', 'SCO': 'SCO', 'SDN': 'SDN', 'SEN': 'SEN',
                'SEY': 'SEY', 'SGS': 'SGS', 'SHN': 'SHN', 'SIN': 'SIN', 'SJM': 'SJM', 'SLE': 'SLE', 'SLV': 'SLV',
                'SMR': 'SMR', 'SOL': 'SOL', 'SOM': 'SOM', 'SPM': 'SPM', 'SRB': 'SRB', 'SSD': 'SSD', 'STP': 'STP',
                'SUI': 'SUI', 'SUR': 'SUR', 'SWZ': 'SWZ', 'SXM': 'SXM', 'SYR': 'SYR', 'TAH': 'TAH', 'TAN': 'TAN',
                'TCA': 'TCA', 'TGA': 'TGA', 'THA': 'THA', 'TJK': 'TJK', 'TKL': 'TKL', 'TKM': 'TKM', 'TLS': 'TLS',
                'TOG': 'TOG', 'TRI': 'TRI', 'TUN': 'TUN', 'TUR': 'TUR', 'TUV': 'TUV', 'TWN': 'TWN', 'UAE': 'UAE',
                'UGA': 'UGA', 'UKR': 'UKR', 'UMI': 'UMI', 'URU': 'URU', 'USA': 'USA', 'UZB': 'UZB', 'VAN': 'VAN',
                'VAT': 'VAT', 'VEN': 'VEN', 'VGB': 'VGB', 'VIE': 'VIE', 'VIN': 'VIN', 'VIR': 'VIR', 'WAL': 'WAL',
                'WLF': 'WLF', 'YEM': 'YEM', 'ZAM': 'ZAM', 'ZIM': 'ZIM', "EUR": "EUR"
            }
            for key, value in regions.items():
                if f" {key} " in label:
                    region = value

        if region is None:
            region = ""
        return region

    def get_distributor(self, distributor_in):
        distributor_list = [
            '01 DISTRIBUTION', '100 DESTINATIONS TRAVEL FILM', '101 FILMS', '1FILMS', '2 ENTERTAIN VIDEO', '20TH CENTURY FOX', '2L', '3D CONTENT HUB', '3D MEDIA', '3L FILM', '4DIGITAL', '4DVD', '4K ULTRA HD MOVIES', '4K UHD', '8-FILMS', '84 ENTERTAINMENT', '88 FILMS', '@ANIME', 'ANIME', 'A CONTRACORRIENTE', 'A CONTRACORRIENTE FILMS', 'A&E HOME VIDEO', 'A&E', 'A&M RECORDS', 'A+E NETWORKS', 'A+R', 'A-FILM', 'AAA', 'AB VIDÉO', 'AB VIDEO', 'ABC - (AUSTRALIAN BROADCASTING CORPORATION)', 'ABC', 'ABKCO', 'ABSOLUT MEDIEN', 'ABSOLUTE', 'ACCENT FILM ENTERTAINMENT', 'ACCENTUS', 'ACORN MEDIA', 'AD VITAM', 'ADA', 'ADITYA VIDEOS', 'ADSO FILMS', 'AFM RECORDS', 'AGFA', 'AIX RECORDS',
            'ALAMODE FILM', 'ALBA RECORDS', 'ALBANY RECORDS', 'ALBATROS', 'ALCHEMY', 'ALIVE', 'ALL ANIME', 'ALL INTERACTIVE ENTERTAINMENT', 'ALLEGRO', 'ALLIANCE', 'ALPHA MUSIC', 'ALTERDYSTRYBUCJA', 'ALTERED INNOCENCE', 'ALTITUDE FILM DISTRIBUTION', 'ALUCARD RECORDS', 'AMAZING D.C.', 'AMAZING DC', 'AMMO CONTENT', 'AMUSE SOFT ENTERTAINMENT', 'ANCONNECT', 'ANEC', 'ANIMATSU', 'ANIME HOUSE', 'ANIME LTD', 'ANIME WORKS', 'ANIMEIGO', 'ANIPLEX', 'ANOLIS ENTERTAINMENT', 'ANOTHER WORLD ENTERTAINMENT', 'AP INTERNATIONAL', 'APPLE', 'ARA MEDIA', 'ARBELOS', 'ARC ENTERTAINMENT', 'ARP SÉLECTION', 'ARP SELECTION', 'ARROW', 'ART SERVICE', 'ART VISION', 'ARTE ÉDITIONS', 'ARTE EDITIONS', 'ARTE VIDÉO',
            'ARTE VIDEO', 'ARTHAUS MUSIK', 'ARTIFICIAL EYE', 'ARTSPLOITATION FILMS', 'ARTUS FILMS', 'ASCOT ELITE HOME ENTERTAINMENT', 'ASIA VIDEO', 'ASMIK ACE', 'ASTRO RECORDS & FILMWORKS', 'ASYLUM', 'ATLANTIC FILM', 'ATLANTIC RECORDS', 'ATLAS FILM', 'AUDIO VISUAL ENTERTAINMENT', 'AURO-3D CREATIVE LABEL', 'AURUM', 'AV VISIONEN', 'AV-JET', 'AVALON', 'AVENTI', 'AVEX TRAX', 'AXIOM', 'AXIS RECORDS', 'AYNGARAN', 'BAC FILMS', 'BACH FILMS', 'BANDAI VISUAL', 'BARCLAY', 'BBC', 'BRITISH BROADCASTING CORPORATION', 'BBI FILMS', 'BBI', 'BCI HOME ENTERTAINMENT', 'BEGGARS BANQUET', 'BEL AIR CLASSIQUES', 'BELGA FILMS', 'BELVEDERE', 'BENELUX FILM DISTRIBUTORS', 'BENNETT-WATT MEDIA', 'BERLIN CLASSICS', 'BERLINER PHILHARMONIKER RECORDINGS', 'BEST ENTERTAINMENT', 'BEYOND HOME ENTERTAINMENT', 'BFI VIDEO', 'BFI', 'BRITISH FILM INSTITUTE', 'BFS ENTERTAINMENT', 'BFS', 'BHAVANI', 'BIBER RECORDS', 'BIG HOME VIDEO', 'BILDSTÖRUNG',
            'BILDSTORUNG', 'BILL ZEBUB', 'BIRNENBLATT', 'BIT WEL', 'BLACK BOX', 'BLACK HILL PICTURES', 'BLACK HILL', 'BLACK HOLE RECORDINGS', 'BLACK HOLE', 'BLAQOUT', 'BLAUFIELD MUSIC', 'BLAUFIELD', 'BLOCKBUSTER ENTERTAINMENT', 'BLOCKBUSTER', 'BLU PHASE MEDIA', 'BLU-RAY ONLY', 'BLU-RAY', 'BLURAY ONLY', 'BLURAY', 'BLUE GENTIAN RECORDS', 'BLUE KINO', 'BLUE UNDERGROUND', 'BMG/ARISTA', 'BMG', 'BMGARISTA', 'BMG ARISTA', 'ARISTA', 'ARISTA/BMG', 'ARISTABMG', 'ARISTA BMG', 'BONTON FILM', 'BONTON', 'BOOMERANG PICTURES', 'BOOMERANG', 'BQHL ÉDITIONS', 'BQHL EDITIONS', 'BQHL', 'BREAKING GLASS', 'BRIDGESTONE', 'BRINK', 'BROAD GREEN PICTURES', 'BROAD GREEN', 'BUSCH MEDIA GROUP', 'BUSCH', 'C MAJOR', 'C.B.S.', 'CAICHANG', 'CALIFÓRNIA FILMES', 'CALIFORNIA FILMES', 'CALIFORNIA', 'CAMEO', 'CAMERA OBSCURA', 'CAMERATA', 'CAMP MOTION PICTURES', 'CAMP MOTION', 'CAPELIGHT PICTURES', 'CAPELIGHT', 'CAPITOL', 'CAPITOL RECORDS', 'CAPRICCI', 'CARGO RECORDS', 'CARLOTTA FILMS', 'CARLOTTA', 'CARLOTA', 'CARMEN FILM', 'CASCADE', 'CATCHPLAY', 'CAULDRON FILMS', 'CAULDRON', 'CBS TELEVISION STUDIOS', 'CBS', 'CCTV', 'CCV ENTERTAINMENT', 'CCV', 'CD BABY', 'CD LAND', 'CECCHI GORI', 'CENTURY MEDIA', 'CHUAN XUN SHI DAI MULTIMEDIA', 'CINE-ASIA', 'CINÉART', 'CINEART', 'CINEDIGM', 'CINEFIL IMAGICA', 'CINEMA EPOCH', 'CINEMA GUILD', 'CINEMA LIBRE STUDIOS', 'CINEMA MONDO', 'CINEMATIC VISION', 'CINEPLOIT RECORDS', 'CINESTRANGE EXTREME', 'CITEL VIDEO', 'CITEL', 'CJ ENTERTAINMENT', 'CJ', 'CLASSIC MEDIA', 'CLASSICFLIX', 'CLASSICLINE', 'CLAUDIO RECORDS', 'CLEAR VISION', 'CLEOPATRA', 'CLOSE UP', 'CMS MEDIA LIMITED', 'CMV LASERVISION', 'CN ENTERTAINMENT', 'CODE RED', 'COHEN MEDIA GROUP', 'COHEN', 'COIN DE MIRE CINÉMA', 'COIN DE MIRE CINEMA', 'COLOSSEO FILM', 'COLUMBIA', 'COLUMBIA PICTURES', 'COLUMBIA/TRI-STAR', 'TRI-STAR', 'COMMERCIAL MARKETING', 'CONCORD MUSIC GROUP', 'CONCORDE VIDEO', 'CONDOR', 'CONSTANTIN FILM', 'CONSTANTIN', 'CONSTANTINO FILMES', 'CONSTANTINO', 'CONSTRUCTIVE MEDIA SERVICE', 'CONSTRUCTIVE', 'CONTENT ZONE', 'CONTENTS GATE', 'COQUEIRO VERDE', 'CORNERSTONE MEDIA', 'CORNERSTONE', 'CP DIGITAL', 'CREST MOVIES', 'CRITERION', 'CRITERION COLLECTION', 'CC', 'CRYSTAL CLASSICS', 'CULT EPICS', 'CULT FILMS', 'CULT VIDEO', 'CURZON FILM WORLD', 'D FILMS', "D'AILLY COMPANY", 'DAILLY COMPANY', 'D AILLY COMPANY', "D'AILLY", 'DAILLY', 'D AILLY', 'DA CAPO', 'DA MUSIC', "DALL'ANGELO PICTURES", 'DALLANGELO PICTURES', "DALL'ANGELO", 'DALL ANGELO PICTURES', 'DALL ANGELO', 'DAREDO', 'DARK FORCE ENTERTAINMENT', 'DARK FORCE', 'DARK SIDE RELEASING', 'DARK SIDE', 'DAZZLER MEDIA', 'DAZZLER', 'DCM PICTURES', 'DCM', 'DEAPLANETA', 'DECCA', 'DEEPJOY', 'DEFIANT SCREEN ENTERTAINMENT', 'DEFIANT SCREEN', 'DEFIANT', 'DELOS', 'DELPHIAN RECORDS', 'DELPHIAN', 'DELTA MUSIC & ENTERTAINMENT', 'DELTA MUSIC AND ENTERTAINMENT', 'DELTA MUSIC ENTERTAINMENT', 'DELTA MUSIC', 'DELTAMAC CO. LTD.', 'DELTAMAC CO LTD', 'DELTAMAC CO', 'DELTAMAC', 'DEMAND MEDIA', 'DEMAND', 'DEP', 'DEUTSCHE GRAMMOPHON', 'DFW', 'DGM', 'DIAPHANA', 'DIGIDREAMS STUDIOS', 'DIGIDREAMS', 'DIGITAL ENVIRONMENTS', 'DIGITAL', 'DISCOTEK MEDIA', 'DISCOVERY CHANNEL', 'DISCOVERY', 'DISK KINO', 'DISNEY / BUENA VISTA', 'DISNEY', 'BUENA VISTA', 'DISNEY BUENA VISTA', 'DISTRIBUTION SELECT', 'DIVISA', 'DNC ENTERTAINMENT', 'DNC', 'DOGWOOF', 'DOLMEN HOME VIDEO', 'DOLMEN', 'DONAU FILM', 'DONAU', 'DORADO FILMS', 'DORADO', 'DRAFTHOUSE FILMS', 'DRAFTHOUSE', 'DRAGON FILM ENTERTAINMENT', 'DRAGON ENTERTAINMENT', 'DRAGON FILM', 'DRAGON', 'DREAMWORKS', 'DRIVE ON RECORDS', 'DRIVE ON', 'DRIVE-ON', 'DRIVEON', 'DS MEDIA', 'DTP ENTERTAINMENT AG', 'DTP ENTERTAINMENT', 'DTP AG', 'DTP', 'DTS ENTERTAINMENT', 'DTS', 'DUKE MARKETING', 'DUKE VIDEO DISTRIBUTION', 'DUKE', 'DUTCH FILMWORKS', 'DUTCH', 'DVD INTERNATIONAL', 'DVD', 'DYBEX', 'DYNAMIC', 'DYNIT', 'E1 ENTERTAINMENT', 'E1', 'EAGLE ENTERTAINMENT', 'EAGLE HOME ENTERTAINMENT PVT.LTD.', 'EAGLE HOME ENTERTAINMENT PVTLTD', 'EAGLE HOME ENTERTAINMENT PVT LTD', 'EAGLE HOME ENTERTAINMENT', 'EAGLE PICTURES', 'EAGLE ROCK ENTERTAINMENT', 'EAGLE ROCK', 'EAGLE VISION MEDIA', 'EAGLE VISION', 'EARMUSIC', 'EARTH ENTERTAINMENT', 'EARTH', 'ECHO BRIDGE ENTERTAINMENT', 'ECHO BRIDGE', 'EDEL GERMANY GMBH', 'EDEL GERMANY', 'EDEL RECORDS', 'EDITION TONFILM', 'EDITIONS MONTPARNASSE', 'EDKO FILMS LTD.', 'EDKO FILMS LTD', 'EDKO FILMS',
            'EDKO', "EIN'S M&M CO", 'EINS M&M CO', "EIN'S M&M", 'EINS M&M', 'ELEA-MEDIA', 'ELEA MEDIA', 'ELEA', 'ELECTRIC PICTURE', 'ELECTRIC', 'ELEPHANT FILMS', 'ELEPHANT', 'ELEVATION', 'EMI', 'EMON', 'EMS', 'EMYLIA', 'ENE MEDIA', 'ENE', 'ENTERTAINMENT IN VIDEO', 'ENTERTAINMENT IN', 'ENTERTAINMENT ONE', 'ENTERTAINMENT ONE FILMS CANADA INC.', 'ENTERTAINMENT ONE FILMS CANADA INC', 'ENTERTAINMENT ONE FILMS CANADA', 'ENTERTAINMENT ONE CANADA INC', 'ENTERTAINMENT ONE CANADA', 'ENTERTAINMENTONE', 'EONE', 'EOS', 'EPIC PICTURES', 'EPIC', 'EPIC RECORDS', 'ERATO', 'EROS', 'ESC EDITIONS', 'ESCAPI MEDIA BV', 'ESOTERIC RECORDINGS', 'ESPN FILMS', 'EUREKA ENTERTAINMENT', 'EUREKA', 'EURO PICTURES', 'EURO VIDEO', 'EUROARTS', 'EUROPA FILMES', 'EUROPA', 'EUROPACORP', 'EUROZOOM', 'EXCEL', 'EXPLOSIVE MEDIA', 'EXPLOSIVE', 'EXTRALUCID FILMS', 'EXTRALUCID', 'EYE SEE MOVIES', 'EYE SEE', 'EYK MEDIA', 'EYK', 'FABULOUS FILMS', 'FABULOUS', 'FACTORIS FILMS', 'FACTORIS', 'FARAO RECORDS', 'FARBFILM HOME ENTERTAINMENT', 'FARBFILM ENTERTAINMENT', 'FARBFILM HOME', 'FARBFILM', 'FEELGOOD ENTERTAINMENT', 'FEELGOOD', 'FERNSEHJUWELEN', 'FILM CHEST', 'FILM MEDIA', 'FILM MOVEMENT', 'FILM4', 'FILMART', 'FILMAURO', 'FILMAX', 'FILMCONFECT HOME ENTERTAINMENT', 'FILMCONFECT ENTERTAINMENT', 'FILMCONFECT HOME', 'FILMCONFECT', 'FILMEDIA', 'FILMJUWELEN', 'FILMOTEKA NARODAWA', 'FILMRISE', 'FINAL CUT ENTERTAINMENT', 'FINAL CUT', 'FIREHOUSE 12 RECORDS', 'FIREHOUSE 12', 'FIRST INTERNATIONAL PRODUCTION', 'FIRST INTERNATIONAL', 'FIRST LOOK STUDIOS', 'FIRST LOOK', 'FLAGMAN TRADE', 'FLASHSTAR FILMES', 'FLASHSTAR', 'FLICKER ALLEY', 'FNC ADD CULTURE', 'FOCUS FILMES', 'FOCUS', 'FOKUS MEDIA', 'FOKUSA', 'FOX PATHE EUROPA', 'FOX PATHE', 'FOX EUROPA', 'FOX/MGM', 'FOX MGM', 'MGM', 'MGM/FOX', 'FOX', 'FPE', 'FRANCE TÉLÉVISIONS DISTRIBUTION', 'FRANCE TELEVISIONS DISTRIBUTION', 'FRANCE TELEVISIONS', 'FRANCE', 'FREE DOLPHIN ENTERTAINMENT', 'FREE DOLPHIN', 'FREESTYLE DIGITAL MEDIA', 'FREESTYLE DIGITAL', 'FREESTYLE', 'FREMANTLE HOME ENTERTAINMENT', 'FREMANTLE ENTERTAINMENT', 'FREMANTLE HOME', 'FREMANTL', 'FRENETIC FILMS', 'FRENETIC', 'FRONTIER WORKS', 'FRONTIER', 'FRONTIERS MUSIC', 'FRONTIERS RECORDS', 'FS FILM OY', 'FS FILM', 'FULL MOON FEATURES', 'FULL MOON', 'FUN CITY EDITIONS', 'FUN CITY',
            'FUNIMATION ENTERTAINMENT', 'FUNIMATION', 'FUSION', 'FUTUREFILM', 'G2 PICTURES', 'G2', 'GAGA COMMUNICATIONS', 'GAGA', 'GAIAM', 'GALAPAGOS', 'GAMMA HOME ENTERTAINMENT', 'GAMMA ENTERTAINMENT', 'GAMMA HOME', 'GAMMA', 'GARAGEHOUSE PICTURES', 'GARAGEHOUSE', 'GARAGEPLAY (車庫娛樂)', '車庫娛樂', 'GARAGEPLAY (Che Ku Yu Le )', 'GARAGEPLAY', 'Che Ku Yu Le', 'GAUMONT', 'GEFFEN', 'GENEON ENTERTAINMENT', 'GENEON', 'GENEON UNIVERSAL ENTERTAINMENT', 'GENERAL VIDEO RECORDING', 'GLASS DOLL FILMS', 'GLASS DOLL', 'GLOBE MUSIC MEDIA', 'GLOBE MUSIC', 'GLOBE MEDIA', 'GLOBE', 'GO ENTERTAIN', 'GO', 'GOLDEN HARVEST', 'GOOD!MOVIES', 'GOOD! MOVIES', 'GOOD MOVIES', 'GRAPEVINE VIDEO', 'GRAPEVINE', 'GRASSHOPPER FILM', 'GRASSHOPPER FILMS', 'GRASSHOPPER', 'GRAVITAS VENTURES', 'GRAVITAS', 'GREAT MOVIES', 'GREAT', 'GREEN APPLE ENTERTAINMENT', 'GREEN ENTERTAINMENT', 'GREEN APPLE', 'GREEN', 'GREENNARAE MEDIA', 'GREENNARAE', 'GRINDHOUSE RELEASING', 'GRINDHOUSE', 'GRIND HOUSE', 'GRYPHON ENTERTAINMENT', 'GRYPHON', 'GUNPOWDER & SKY', 'GUNPOWDER AND SKY', 'GUNPOWDER SKY', 'GUNPOWDER + SKY', 'GUNPOWDER', 'HANABEE ENTERTAINMENT', 'HANABEE', 'HANNOVER HOUSE', 'HANNOVER', 'HANSESOUND', 'HANSE SOUND', 'HANSE', 'HAPPINET', 'HARMONIA MUNDI', 'HARMONIA', 'HBO', 'HDC', 'HEC', 'HELL & BACK RECORDINGS', 'HELL AND BACK RECORDINGS', 'HELL & BACK', 'HELL AND BACK', "HEN'S TOOTH VIDEO", 'HENS TOOTH VIDEO', "HEN'S TOOTH", 'HENS TOOTH', 'HIGH FLIERS', 'HIGHLIGHT', 'HILLSONG', 'HISTORY CHANNEL', 'HISTORY', 'HK VIDÉO', 'HK VIDEO', 'HK', 'HMH HAMBURGER MEDIEN HAUS', 'HAMBURGER MEDIEN HAUS', 'HMH HAMBURGER MEDIEN', 'HMH HAMBURGER', 'HMH', 'HOLLYWOOD CLASSIC ENTERTAINMENT', 'HOLLYWOOD CLASSIC', 'HOLLYWOOD PICTURES', 'HOLLYWOOD', 'HOPSCOTCH ENTERTAINMENT', 'HOPSCOTCH', 'HPM', 'HÄNNSLER CLASSIC', 'HANNSLER CLASSIC', 'HANNSLER', 'I-CATCHER', 'I CATCHER', 'ICATCHER', 'I-ON NEW MEDIA', 'I ON NEW MEDIA', 'ION NEW MEDIA', 'ION MEDIA', 'I-ON', 'ION', 'IAN PRODUCTIONS', 'IAN', 'ICESTORM', 'ICON FILM DISTRIBUTION', 'ICON DISTRIBUTION', 'ICON FILM', 'ICON', 'IDEALE AUDIENCE', 'IDEALE', 'IFC FILMS', 'IFC', 'IFILM', 'ILLUSIONS UNLTD.', 'ILLUSIONS UNLTD', 'ILLUSIONS', 'IMAGE ENTERTAINMENT', 'IMAGE', 'IMAGEM FILMES', 'IMAGEM', 'IMOVISION', 'IMPERIAL CINEPIX', 'IMPRINT', 'IMPULS HOME ENTERTAINMENT', 'IMPULS ENTERTAINMENT', 'IMPULS HOME', 'IMPULS', 'IN-AKUSTIK', 'IN AKUSTIK', 'INAKUSTIK', 'INCEPTION MEDIA GROUP', 'INCEPTION MEDIA', 'INCEPTION GROUP', 'INCEPTION', 'INDEPENDENT', 'INDICAN', 'INDIE RIGHTS', 'INDIE', 'INDIGO', 'INFO', 'INJOINGAN', 'INKED PICTURES', 'INKED', 'INSIDE OUT MUSIC', 'INSIDE MUSIC', 'INSIDE OUT', 'INSIDE', 'INTERCOM', 'INTERCONTINENTAL VIDEO', 'INTERCONTINENTAL', 'INTERGROOVE', 'INTERSCOPE', 'INVINCIBLE PICTURES', 'INVINCIBLE', 'ISLAND/MERCURY', 'ISLAND MERCURY', 'ISLANDMERCURY', 'ISLAND & MERCURY', 'ISLAND AND MERCURY', 'ISLAND', 'ITN', 'ITV DVD', 'ITV', 'IVC', 'IVE ENTERTAINMENT', 'IVE', 'J&R ADVENTURES', 'J&R', 'JR', 'JAKOB', 'JONU MEDIA', 'JONU', 'JRB PRODUCTIONS', 'JRB', 'JUST BRIDGE ENTERTAINMENT', 'JUST BRIDGE', 'JUST ENTERTAINMENT', 'JUST', 'KABOOM ENTERTAINMENT', 'KABOOM', 'KADOKAWA ENTERTAINMENT', 'KADOKAWA', 'KAIROS', 'KALEIDOSCOPE ENTERTAINMENT', 'KALEIDOSCOPE', 'KAM & RONSON ENTERPRISES', 'KAM & RONSON', 'KAM&RONSON ENTERPRISES', 'KAM&RONSON', 'KAM AND RONSON ENTERPRISES', 'KAM AND RONSON', 'KANA HOME VIDEO', 'KARMA FILMS', 'KARMA', 'KATZENBERGER', 'KAZE',
            'KBS MEDIA', 'KBS', 'KD MEDIA', 'KD', 'KING MEDIA', 'KING', 'KING RECORDS', 'KINO LORBER', 'KINO', 'KINO SWIAT', 'KINOKUNIYA', 'KINOWELT HOME ENTERTAINMENT/DVD', 'KINOWELT HOME ENTERTAINMENT', 'KINOWELT ENTERTAINMENT', 'KINOWELT HOME DVD', 'KINOWELT ENTERTAINMENT/DVD', 'KINOWELT DVD', 'KINOWELT', 'KIT PARKER FILMS', 'KIT PARKER', 'KITTY MEDIA', 'KNM HOME ENTERTAINMENT', 'KNM ENTERTAINMENT', 'KNM HOME', 'KNM', 'KOBA FILMS', 'KOBA', 'KOCH ENTERTAINMENT', 'KOCH MEDIA', 'KOCH', 'KRAKEN RELEASING', 'KRAKEN', 'KSCOPE', 'KSM', 'KULTUR', "L'ATELIER D'IMAGES", "LATELIER D'IMAGES", "L'ATELIER DIMAGES", 'LATELIER DIMAGES', "L ATELIER D'IMAGES", "L'ATELIER D IMAGES",
            'L ATELIER D IMAGES', "L'ATELIER", 'L ATELIER', 'LATELIER', 'LA AVENTURA AUDIOVISUAL', 'LA AVENTURA', 'LACE GROUP', 'LACE', 'LASER PARADISE', 'LAYONS', 'LCJ EDITIONS', 'LCJ', 'LE CHAT QUI FUME', 'LE PACTE', 'LEDICK FILMHANDEL', 'LEGEND', 'LEOMARK STUDIOS', 'LEOMARK', 'LEONINE FILMS', 'LEONINE', 'LICHTUNG MEDIA LTD', 'LICHTUNG LTD', 'LICHTUNG MEDIA LTD.', 'LICHTUNG LTD.', 'LICHTUNG MEDIA', 'LICHTUNG', 'LIGHTHOUSE HOME ENTERTAINMENT', 'LIGHTHOUSE ENTERTAINMENT', 'LIGHTHOUSE HOME', 'LIGHTHOUSE', 'LIGHTYEAR', 'LIONSGATE FILMS', 'LIONSGATE', 'LIZARD CINEMA TRADE', 'LLAMENTOL', 'LOBSTER FILMS', 'LOBSTER', 'LOGON', 'LORBER FILMS', 'LORBER', 'LOS BANDITOS FILMS', 'LOS BANDITOS', 'LOUD & PROUD RECORDS', 'LOUD AND PROUD RECORDS', 'LOUD & PROUD', 'LOUD AND PROUD', 'LSO LIVE', 'LUCASFILM', 'LUCKY RED', 'LUMIÈRE HOME ENTERTAINMENT', 'LUMIERE HOME ENTERTAINMENT', 'LUMIERE ENTERTAINMENT', 'LUMIERE HOME', 'LUMIERE', 'M6 VIDEO', 'M6', 'MAD DIMENSION', 'MADMAN ENTERTAINMENT', 'MADMAN', 'MAGIC BOX', 'MAGIC PLAY', 'MAGNA HOME ENTERTAINMENT', 'MAGNA ENTERTAINMENT', 'MAGNA HOME', 'MAGNA', 'MAGNOLIA PICTURES', 'MAGNOLIA', 'MAIDEN JAPAN', 'MAIDEN', 'MAJENG MEDIA', 'MAJENG', 'MAJESTIC HOME ENTERTAINMENT', 'MAJESTIC ENTERTAINMENT', 'MAJESTIC HOME', 'MAJESTIC', 'MANGA HOME ENTERTAINMENT', 'MANGA ENTERTAINMENT', 'MANGA HOME', 'MANGA', 'MANTA LAB', 'MAPLE STUDIOS', 'MAPLE', 'MARCO POLO PRODUCTION', 'MARCO POLO', 'MARIINSKY', 'MARVEL STUDIOS', 'MARVEL', 'MASCOT RECORDS', 'MASCOT', 'MASSACRE VIDEO', 'MASSACRE', 'MATCHBOX', 'MATRIX D', 'MAXAM', 'MAYA HOME ENTERTAINMENT', 'MAYA ENTERTAINMENT', 'MAYA HOME', 'MAYAT', 'MDG', 'MEDIA BLASTERS', 'MEDIA FACTORY', 'MEDIA TARGET DISTRIBUTION', 'MEDIA TARGET', 'MEDIAINVISION', 'MEDIATOON', 'MEDIATRES ESTUDIO', 'MEDIATRES STUDIO', 'MEDIATRES', 'MEDICI ARTS', 'MEDICI CLASSICS', 'MEDIUMRARE ENTERTAINMENT', 'MEDIUMRARE', 'MEDUSA', 'MEGASTAR', 'MEI AH', 'MELI MÉDIAS', 'MELI MEDIAS', 'MEMENTO FILMS', 'MEMENTO', 'MENEMSHA FILMS', 'MENEMSHA', 'MERCURY', 'MERCURY STUDIOS', 'MERGE SOFT PRODUCTIONS', 'MERGE PRODUCTIONS', 'MERGE SOFT', 'MERGE', 'METAL BLADE RECORDS', 'METAL BLADE', 'METEOR', 'METRO-GOLDWYN-MAYER', 'METRO GOLDWYN MAYER', 'METROGOLDWYNMAYER', 'METRODOME VIDEO', 'METRODOME', 'METROPOLITAN', 'MFA+', 'MFA', 'MIG FILMGROUP', 'MIG', 'MILESTONE', 'MILL CREEK ENTERTAINMENT', 'MILL CREEK', 'MILLENNIUM MEDIA', 'MILLENNIUM', 'MIRAGE ENTERTAINMENT', 'MIRAGE', 'MIRAMAX', 'MISTERIYA ZVUKA', 'MK2', 'MODE RECORDS', 'MODE', 'MOMENTUM PICTURES', 'MONDO HOME ENTERTAINMENT', 'MONDO ENTERTAINMENT', 'MONDO HOME', 'MONDO MACABRO', 'MONGREL MEDIA', 'MONOLIT', 'MONOLITH VIDEO', 'MONOLITH', 'MONSTER PICTURES', 'MONSTER', 'MONTEREY VIDEO', 'MONTEREY', 'MONUMENT RELEASING', 'MONUMENT', 'MORNINGSTAR', 'MORNING STAR', 'MOSERBAER', 'MOVIEMAX', 'MOVINSIDE', 'MPI MEDIA GROUP', 'MPI MEDIA', 'MPI', 'MR. BONGO FILMS', 'MR BONGO FILMS', 'MR BONGO', 'MRG (MERIDIAN)', 'MRG MERIDIAN', 'MRG', 'MERIDIAN', 'MUBI', 'MUG SHOT PRODUCTIONS', 'MUG SHOT', 'MULTIMUSIC', 'MULTI-MUSIC', 'MULTI MUSIC', 'MUSE', 'MUSIC BOX FILMS', 'MUSIC BOX', 'MUSICBOX', 'MUSIC BROKERS', 'MUSIC THEORIES', 'MUSIC VIDEO DISTRIBUTORS', 'MUSIC VIDEO', 'MUSTANG ENTERTAINMENT', 'MUSTANG', 'MVD VISUAL', 'MVD', 'MVD/VSC', 'MVL', 'MVM ENTERTAINMENT', 'MVM', 'MYNDFORM', 'MYSTIC NIGHT PICTURES', 'MYSTIC NIGHT', 'NAMELESS MEDIA', 'NAMELESS', 'NAPALM RECORDS', 'NAPALM', 'NATIONAL ENTERTAINMENT MEDIA', 'NATIONAL ENTERTAINMENT', 'NATIONAL MEDIA', 'NATIONAL FILM ARCHIVE', 'NATIONAL ARCHIVE', 'NATIONAL FILM', 'NATIONAL GEOGRAPHIC', 'NAT GEO TV', 'NAT GEO', 'NGO', 'NAXOS', 'NBCUNIVERSAL ENTERTAINMENT JAPAN', 'NBC UNIVERSAL ENTERTAINMENT JAPAN', 'NBCUNIVERSAL JAPAN', 'NBC UNIVERSAL JAPAN', 'NBC JAPAN', 'NBO ENTERTAINMENT', 'NBO', 'NEOS', 'NETFLIX', 'NETWORK', 'NEW BLOOD', 'NEW DISC', 'NEW KSM', 'NEW LINE CINEMA', 'NEW LINE', 'NEW MOVIE TRADING CO. LTD', 'NEW MOVIE TRADING CO LTD', 'NEW MOVIE TRADING CO', 'NEW MOVIE TRADING', 'NEW WAVE FILMS', 'NEW WAVE', 'NFI', 'NHK', 'NIPPONART', 'NIS AMERICA', 'NJUTAFILMS', 'NOBLE ENTERTAINMENT', 'NOBLE', 'NORDISK FILM', 'NORDISK', 'NORSK FILM', 'NORSK', 'NORTH AMERICAN MOTION PICTURES', 'NOS AUDIOVISUAIS', 'NOTORIOUS PICTURES', 'NOTORIOUS', 'NOVA MEDIA', 'NOVA', 'NOVA SALES AND DISTRIBUTION', 'NOVA SALES & DISTRIBUTION', 'NSM', 'NSM RECORDS', 'NUCLEAR BLAST', 'NUCLEUS FILMS', 'NUCLEUS', 'OBERLIN MUSIC', 'OBERLIN', 'OBRAS-PRIMAS DO CINEMA', 'OBRAS PRIMAS DO CINEMA', 'OBRASPRIMAS DO CINEMA', 'OBRAS-PRIMAS CINEMA', 'OBRAS PRIMAS CINEMA', 'OBRASPRIMAS CINEMA', 'OBRAS-PRIMAS', 'OBRAS PRIMAS', 'OBRASPRIMAS', 'ODEON', 'OFDB FILMWORKS', 'OFDB', 'OLIVE FILMS', 'OLIVE', 'ONDINE', 'ONSCREEN FILMS', 'ONSCREEN', 'OPENING DISTRIBUTION', 'OPERA AUSTRALIA', 'OPTIMUM HOME ENTERTAINMENT', 'OPTIMUM ENTERTAINMENT', 'OPTIMUM HOME', 'OPTIMUM', 'OPUS ARTE', 'ORANGE STUDIO', 'ORANGE', 'ORLANDO EASTWOOD FILMS', 'ORLANDO FILMS', 'ORLANDO EASTWOOD', 'ORLANDO', 'ORUSTAK PICTURES', 'ORUSTAK', 'OSCILLOSCOPE PICTURES', 'OSCILLOSCOPE', 'OUTPLAY', 'PALISADES TARTAN', 'PAN VISION', 'PANVISION', 'PANAMINT CINEMA', 'PANAMINT', 'PANDASTORM ENTERTAINMENT', 'PANDA STORM ENTERTAINMENT', 'PANDASTORM', 'PANDA STORM', 'PANDORA FILM', 'PANDORA', 'PANEGYRIC', 'PANORAMA', 'PARADE DECK FILMS', 'PARADE DECK', 'PARADISE', 'PARADISO FILMS', 'PARADOX', 'PARAMOUNT PICTURES', 'PARAMOUNT', 'PARIS FILMES', 'PARIS FILMS', 'PARIS', 'PARK CIRCUS', 'PARLOPHONE', 'PASSION RIVER', 'PATHE DISTRIBUTION', 'PATHE', 'PBS', 'PEACE ARCH TRINITY', 'PECCADILLO PICTURES', 'PEPPERMINT', 'PHASE 4 FILMS', 'PHASE 4', 'PHILHARMONIA BAROQUE', 'PICTURE HOUSE ENTERTAINMENT', 'PICTURE ENTERTAINMENT', 'PICTURE HOUSE', 'PICTURE', 'PIDAX',
            'PINK FLOYD RECORDS', 'PINK FLOYD', 'PINNACLE FILMS', 'PINNACLE', 'PLAIN', 'PLATFORM ENTERTAINMENT LIMITED', 'PLATFORM ENTERTAINMENT LTD', 'PLATFORM ENTERTAINMENT LTD.', 'PLATFORM ENTERTAINMENT', 'PLATFORM', 'PLAYARTE', 'PLG UK CLASSICS', 'PLG UK', 'PLG', 'POLYBAND & TOPPIC VIDEO/WVG', 'POLYBAND AND TOPPIC VIDEO/WVG', 'POLYBAND & TOPPIC VIDEO WVG', 'POLYBAND & TOPPIC VIDEO AND WVG', 'POLYBAND & TOPPIC VIDEO & WVG', 'POLYBAND AND TOPPIC VIDEO WVG', 'POLYBAND AND TOPPIC VIDEO AND WVG', 'POLYBAND AND TOPPIC VIDEO & WVG', 'POLYBAND & TOPPIC VIDEO', 'POLYBAND AND TOPPIC VIDEO', 'POLYBAND & TOPPIC', 'POLYBAND AND TOPPIC', 'POLYBAND', 'WVG', 'POLYDOR', 'PONY', 'PONY CANYON', 'POTEMKINE', 'POWERHOUSE FILMS', 'POWERHOUSE', 'POWERSTATIOM', 'PRIDE & JOY', 'PRIDE AND JOY', 'PRINZ MEDIA', 'PRINZ', 'PRIS AUDIOVISUAIS', 'PRO VIDEO', 'PRO-VIDEO', 'PRO-MOTION', 'PRO MOTION', 'PROD. JRB', 'PROD JRB', 'PRODISC', 'PROKINO', 'PROVOGUE RECORDS', 'PROVOGUE', 'PROWARE', 'PULP VIDEO', 'PULP', 'PULSE VIDEO', 'PULSE', 'PURE AUDIO RECORDINGS', 'PURE AUDIO', 'PURE FLIX ENTERTAINMENT', 'PURE FLIX', 'PURE ENTERTAINMENT', 'PYRAMIDE VIDEO', 'PYRAMIDE', 'QUALITY FILMS', 'QUALITY', 'QUARTO VALLEY RECORDS', 'QUARTO VALLEY', 'QUESTAR', 'R SQUARED FILMS', 'R SQUARED', 'RAPID EYE MOVIES', 'RAPID EYE', 'RARO VIDEO', 'RARO', 'RAROVIDEO U.S.', 'RAROVIDEO US', 'RARO VIDEO US', 'RARO VIDEO U.S.', 'RARO U.S.', 'RARO US', 'RAVEN BANNER RELEASING', 'RAVEN BANNER', 'RAVEN', 'RAZOR DIGITAL ENTERTAINMENT', 'RAZOR DIGITAL', 'RCA', 'RCO LIVE', 'RCO', 'RCV', 'REAL GONE MUSIC', 'REAL GONE', 'REANIMEDIA', 'REANI MEDIA', 'REDEMPTION', 'REEL', 'RELIANCE HOME VIDEO & GAMES', 'RELIANCE HOME VIDEO AND GAMES', 'RELIANCE HOME VIDEO', 'RELIANCE VIDEO', 'RELIANCE HOME', 'RELIANCE', 'REM CULTURE', 'REMAIN IN LIGHT', 'REPRISE', 'RESEN', 'RETROMEDIA', 'REVELATION FILMS LTD.', 'REVELATION FILMS LTD', 'REVELATION FILMS', 'REVELATION LTD.', 'REVELATION LTD', 'REVELATION', 'REVOLVER ENTERTAINMENT', 'REVOLVER', 'RHINO MUSIC', 'RHINO', 'RHV', 'RIGHT STUF', 'RIMINI EDITIONS', 'RISING SUN MEDIA', 'RLJ ENTERTAINMENT', 'RLJ', 'ROADRUNNER RECORDS', 'ROADSHOW ENTERTAINMENT', 'ROADSHOW', 'RONE', 'RONIN FLIX', 'ROTANA HOME ENTERTAINMENT', 'ROTANA ENTERTAINMENT', 'ROTANA HOME', 'ROTANA', 'ROUGH TRADE',
            'ROUNDER', 'SAFFRON HILL FILMS', 'SAFFRON HILL', 'SAFFRON', 'SAMUEL GOLDWYN FILMS', 'SAMUEL GOLDWYN', 'SAN FRANCISCO SYMPHONY', 'SANDREW METRONOME', 'SAPHRANE', 'SAVOR', 'SCANBOX ENTERTAINMENT', 'SCANBOX', 'SCENIC LABS', 'SCHRÖDERMEDIA', 'SCHRODERMEDIA', 'SCHRODER MEDIA', 'SCORPION RELEASING', 'SCORPION', 'SCREAM TEAM RELEASING', 'SCREAM TEAM', 'SCREEN MEDIA', 'SCREEN', 'SCREENBOUND PICTURES', 'SCREENBOUND', 'SCREENWAVE MEDIA', 'SCREENWAVE', 'SECOND RUN', 'SECOND SIGHT', 'SEEDSMAN GROUP', 'SELECT VIDEO', 'SELECTA VISION', 'SENATOR', 'SENTAI FILMWORKS', 'SENTAI', 'SEVEN7', 'SEVERIN FILMS', 'SEVERIN', 'SEVILLE', 'SEYONS ENTERTAINMENT', 'SEYONS', 'SF STUDIOS', 'SGL ENTERTAINMENT', 'SGL', 'SHAMELESS', 'SHAMROCK MEDIA', 'SHAMROCK', 'SHANGHAI EPIC MUSIC ENTERTAINMENT', 'SHANGHAI EPIC ENTERTAINMENT', 'SHANGHAI EPIC MUSIC', 'SHANGHAI MUSIC ENTERTAINMENT', 'SHANGHAI ENTERTAINMENT', 'SHANGHAI MUSIC', 'SHANGHAI', 'SHEMAROO', 'SHOCHIKU', 'SHOCK', 'SHOGAKU KAN', 'SHOUT FACTORY', 'SHOUT! FACTORY', 'SHOUT', 'SHOUT!', 'SHOWBOX', 'SHOWTIME ENTERTAINMENT', 'SHOWTIME', 'SHRIEK SHOW', 'SHUDDER', 'SIDONIS', 'SIDONIS CALYSTA', 'SIGNAL ONE ENTERTAINMENT', 'SIGNAL ONE', 'SIGNATURE ENTERTAINMENT', 'SIGNATURE', 'SILVER VISION', 'SINISTER FILM', 'SINISTER', 'SIREN VISUAL ENTERTAINMENT', 'SIREN VISUAL', 'SIREN ENTERTAINMENT', 'SIREN', 'SKANI', 'SKY DIGI',
            'SLASHER // VIDEO', 'SLASHER / VIDEO', 'SLASHER VIDEO', 'SLASHER', 'SLOVAK FILM INSTITUTE', 'SLOVAK FILM', 'SFI', 'SM LIFE DESIGN GROUP', 'SMOOTH PICTURES', 'SMOOTH', 'SNAPPER MUSIC', 'SNAPPER', 'SODA PICTURES', 'SODA', 'SONO LUMINUS', 'SONY MUSIC', 'SONY PICTURES', 'SONY', 'SONY PICTURES CLASSICS', 'SONY CLASSICS', 'SOUL MEDIA', 'SOUL', 'SOULFOOD MUSIC DISTRIBUTION', 'SOULFOOD DISTRIBUTION', 'SOULFOOD MUSIC', 'SOULFOOD', 'SOYUZ', 'SPECTRUM', 'SPENTZOS FILM', 'SPENTZOS', 'SPIRIT ENTERTAINMENT', 'SPIRIT', 'SPIRIT MEDIA GMBH', 'SPIRIT MEDIA', 'SPLENDID ENTERTAINMENT', 'SPLENDID FILM', 'SPO', 'SQUARE ENIX', 'SRI BALAJI VIDEO', 'SRI BALAJI', 'SRI', 'SRI VIDEO', 'SRS CINEMA', 'SRS', 'SSO RECORDINGS', 'SSO', 'ST2 MUSIC', 'ST2', 'STAR MEDIA ENTERTAINMENT', 'STAR ENTERTAINMENT', 'STAR MEDIA', 'STAR', 'STARLIGHT', 'STARZ / ANCHOR BAY', 'STARZ ANCHOR BAY', 'STARZ', 'ANCHOR BAY', 'STER KINEKOR', 'STERLING ENTERTAINMENT', 'STERLING', 'STINGRAY', 'STOCKFISCH RECORDS', 'STOCKFISCH', 'STRAND RELEASING', 'STRAND', 'STUDIO 4K', 'STUDIO CANAL', 'STUDIO GHIBLI', 'GHIBLI', 'STUDIO HAMBURG ENTERPRISES', 'HAMBURG ENTERPRISES', 'STUDIO HAMBURG', 'HAMBURG', 'STUDIO S', 'SUBKULTUR ENTERTAINMENT', 'SUBKULTUR', 'SUEVIA FILMS', 'SUEVIA', 'SUMMIT ENTERTAINMENT', 'SUMMIT', 'SUNFILM ENTERTAINMENT', 'SUNFILM', 'SURROUND RECORDS', 'SURROUND', 'SVENSK FILMINDUSTRI', 'SVENSK', 'SWEN FILMES', 'SWEN FILMS', 'SWEN', 'SYNAPSE FILMS', 'SYNAPSE', 'SYNDICADO', 'SYNERGETIC', 'T- SERIES', 'T-SERIES', 'T SERIES', 'TSERIES', 'T.V.P.', 'TVP', 'TACET RECORDS', 'TACET', 'TAI SENG', 'TAI SHENG', 'TAKEONE', 'TAKESHOBO', 'TAMASA DIFFUSION', 'TC ENTERTAINMENT', 'TC', 'TDK', 'TEAM MARKETING', 'TEATRO REAL', 'TEMA DISTRIBUCIONES', 'TEMPE DIGITAL', 'TF1 VIDÉO', 'TF1 VIDEO', 'TF1', 'THE BLU', 'BLU', 'THE ECSTASY OF FILMS', 'THE FILM DETECTIVE', 'FILM DETECTIVE', 'THE JOKERS', 'JOKERS', 'THE ON', 'ON', 'THIMFILM', 'THIM FILM', 'THIM', 'THIRD WINDOW FILMS', 'THIRD WINDOW', '3RD WINDOW FILMS', '3RD WINDOW', 'THUNDERBEAN ANIMATION', 'THUNDERBEAN', 'THUNDERBIRD RELEASING', 'THUNDERBIRD', 'TIBERIUS FILM', 'TIME LIFE', 'TIMELESS MEDIA GROUP', 'TIMELESS MEDIA', 'TIMELESS GROUP', 'TIMELESS', 'TLA RELEASING', 'TLA', 'TOBIS FILM', 'TOBIS', 'TOEI', 'TOHO', 'TOKYO SHOCK', 'TOKYO', 'TONPOOL MEDIEN GMBH', 'TONPOOL MEDIEN', 'TOPICS ENTERTAINMENT', 'TOPICS', 'TOUCHSTONE PICTURES', 'TOUCHSTONE', 'TRANSMISSION FILMS', 'TRANSMISSION', 'TRAVEL VIDEO STORE', 'TRIART', 'TRIGON FILM', 'TRIGON', 'TRINITY HOME ENTERTAINMENT', 'TRINITY ENTERTAINMENT', 'TRINITY HOME', 'TRINITY', 'TRIPICTURES', 'TRI-PICTURES', 'TRI PICTURES', 'TROMA', 'TURBINE MEDIEN', 'TURTLE RECORDS', 'TURTLE', 'TVA FILMS', 'TVA', 'TWILIGHT TIME', 'TWILIGHT', 'TT', 'TWIN CO., LTD.', 'TWIN CO, LTD.', 'TWIN CO., LTD', 'TWIN CO, LTD', 'TWIN CO LTD', 'TWIN LTD', 'TWIN CO.', 'TWIN CO', 'TWIN', 'UCA', 'UDR', 'UEK', 'UFA/DVD', 'UFA DVD', 'UFADVD', 'UGC PH', 'ULTIMATE3DHEAVEN', 'ULTRA', 'UMBRELLA ENTERTAINMENT', 'UMBRELLA', 'UMC', "UNCORK'D ENTERTAINMENT", 'UNCORKD ENTERTAINMENT', 'UNCORK D ENTERTAINMENT', "UNCORK'D", 'UNCORK D', 'UNCORKD', 'UNEARTHED FILMS', 'UNEARTHED', 'UNI DISC', 'UNIMUNDOS', 'UNITEL', 'UNIVERSAL MUSIC', 'UNIVERSAL SONY PICTURES HOME ENTERTAINMENT', 'UNIVERSAL SONY PICTURES ENTERTAINMENT', 'UNIVERSAL SONY PICTURES HOME', 'UNIVERSAL SONY PICTURES', 'UNIVERSAL HOME ENTERTAINMENT', 'UNIVERSAL ENTERTAINMENT',
            'UNIVERSAL HOME', 'UNIVERSAL STUDIOS', 'UNIVERSAL', 'UNIVERSE LASER & VIDEO CO.', 'UNIVERSE LASER AND VIDEO CO.', 'UNIVERSE LASER & VIDEO CO', 'UNIVERSE LASER AND VIDEO CO', 'UNIVERSE LASER CO.', 'UNIVERSE LASER CO', 'UNIVERSE LASER', 'UNIVERSUM FILM', 'UNIVERSUM', 'UTV', 'VAP', 'VCI', 'VENDETTA FILMS', 'VENDETTA', 'VERSÁTIL HOME VIDEO', 'VERSÁTIL VIDEO', 'VERSÁTIL HOME', 'VERSÁTIL', 'VERSATIL HOME VIDEO', 'VERSATIL VIDEO', 'VERSATIL HOME', 'VERSATIL', 'VERTICAL ENTERTAINMENT', 'VERTICAL', 'VÉRTICE 360º', 'VÉRTICE 360', 'VERTICE 360o', 'VERTICE 360', 'VERTIGO BERLIN', 'VÉRTIGO FILMS', 'VÉRTIGO', 'VERTIGO FILMS', 'VERTIGO', 'VERVE PICTURES', 'VIA VISION ENTERTAINMENT', 'VIA VISION', 'VICOL ENTERTAINMENT', 'VICOL', 'VICOM', 'VICTOR ENTERTAINMENT', 'VICTOR', 'VIDEA CDE', 'VIDEO FILM EXPRESS', 'VIDEO FILM', 'VIDEO EXPRESS', 'VIDEO MUSIC, INC.', 'VIDEO MUSIC, INC', 'VIDEO MUSIC INC.', 'VIDEO MUSIC INC', 'VIDEO MUSIC', 'VIDEO SERVICE CORP.', 'VIDEO SERVICE CORP', 'VIDEO SERVICE', 'VIDEO TRAVEL', 'VIDEOMAX', 'VIDEO MAX', 'VII PILLARS ENTERTAINMENT', 'VII PILLARS', 'VILLAGE FILMS', 'VINEGAR SYNDROME', 'VINEGAR', 'VS', 'VINNY MOVIES', 'VINNY', 'VIRGIL FILMS & ENTERTAINMENT', 'VIRGIL FILMS AND ENTERTAINMENT', 'VIRGIL ENTERTAINMENT', 'VIRGIL FILMS', 'VIRGIL', 'VIRGIN RECORDS', 'VIRGIN', 'VISION FILMS', 'VISION', 'VISUAL ENTERTAINMENT GROUP',
            'VISUAL GROUP', 'VISUAL ENTERTAINMENT', 'VISUAL', 'VIVENDI VISUAL ENTERTAINMENT', 'VIVENDI VISUAL', 'VIVENDI', 'VIZ PICTURES', 'VIZ', 'VLMEDIA', 'VL MEDIA', 'VL', 'VOLGA', 'VVS FILMS', 'VVS', 'VZ HANDELS GMBH', 'VZ HANDELS', 'WARD RECORDS', 'WARD', 'WARNER BROS.', 'WARNER BROS', 'WARNER ARCHIVE', 'WARNER ARCHIVE COLLECTION', 'WAC', 'WARNER', 'WARNER MUSIC', 'WEA', 'WEINSTEIN COMPANY', 'WEINSTEIN', 'WELL GO USA', 'WELL GO', 'WELTKINO FILMVERLEIH', 'WEST VIDEO', 'WEST', 'WHITE PEARL MOVIES', 'WHITE PEARL', 'WICKED-VISION MEDIA', 'WICKED VISION MEDIA', 'WICKEDVISION MEDIA', 'WICKED-VISION', 'WICKED VISION', 'WICKEDVISION', 'WIENERWORLD', 'WILD BUNCH', 'WILD EYE RELEASING', 'WILD EYE', 'WILD SIDE VIDEO', 'WILD SIDE', 'WME', 'WOLFE VIDEO', 'WOLFE', 'WORD ON FIRE', 'WORKS FILM GROUP', 'WORLD WRESTLING', 'WVG MEDIEN', 'WWE STUDIOS', 'WWE', 'X RATED KULT', 'X-RATED KULT', 'X RATED CULT', 'X-RATED CULT', 'X RATED', 'X-RATED', 'XCESS', 'XLRATOR', 'XT VIDEO', 'XT', 'YAMATO VIDEO', 'YAMATO', 'YASH RAJ FILMS', 'YASH RAJS', 'ZEITGEIST FILMS', 'ZEITGEIST', 'ZENITH PICTURES', 'ZENITH', 'ZIMA', 'ZYLO', 'ZYX MUSIC', 'ZYX',
            'MASTERS OF CINEMA', 'MOC'
        ]
        distributor_out = ""
        if distributor_in not in [None, "None", ""]:
            for each in distributor_list:
                if distributor_in.upper() == each:
                    distributor_out = each
        return distributor_out

    def get_video_codec(self, bdinfo):
        codecs = {
            "MPEG-2 Video": "MPEG-2",
            "MPEG-4 AVC Video": "AVC",
            "MPEG-H HEVC Video": "HEVC",
            "VC-1 Video": "VC-1"
        }
        codec = codecs.get(bdinfo['video'][0]['codec'], "")
        return codec

    def get_video_encode(self, mi, type, bdinfo):
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
        if type in ("ENCODE", "WEBRIP"):  # ENCODE or WEBRIP
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

    def get_edition(self, video, bdinfo, filelist, manual_edition):
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
            edition = str(manual_edition)

        print(f"Edition After Manual Edition: {edition}")

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

        print(f"Repack after Checks: {repack}")

        # Only remove REPACK, RERIP, or PROPER from edition if they're not part of manual_edition
        edition = re.sub(r"(\bREPACK\d?\b|\bRERIP\b|\bPROPER\b)", "", edition, flags=re.IGNORECASE).strip()
        bad = ['internal', 'limited', 'retail']

        if edition.lower() in bad:
            edition = ""

        return edition, repack

    """
    Create Torrent
    """
    class CustomTorrent(torf.Torrent):
        # Default piece size limits
        torf.Torrent.piece_size_min = 16384  # 16 KiB
        torf.Torrent.piece_size_max = 67108864  # 64 MiB

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
            total_size = self._calculate_total_size()
            piece_size = self.calculate_piece_size(total_size, self.piece_size_min, self.piece_size_max, self.files)
            self.piece_size = piece_size

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
            our_min_size = 16384
            our_max_size = max_size if max_size else 67108864  # Default to 64 MiB if max_size is None
            piece_size = 67108864  # Start with 64 MiB
            num_pieces = math.ceil(total_size / piece_size)
            torrent_file_size = 20 + (num_pieces * 20) + cls._calculate_pathname_bytes(files)  # Approximate .torrent size

            # Adjust the piece size to fit within the constraints
            while not (1000 <= num_pieces <= 2000 and torrent_file_size <= 102400):  # 100 KiB .torrent size limit
                if num_pieces < 1000:
                    piece_size //= 2
                    if piece_size < our_min_size:
                        piece_size = our_min_size
                        break
                    elif torrent_file_size > 61440:  # Break if .torrent size exceeds 60 KiB
                        break
                elif num_pieces > 2000:
                    piece_size *= 2
                    if piece_size > our_max_size:
                        piece_size = our_max_size
                        break
                    elif torrent_file_size < 81920:  # Break if .torrent size less than 80 KiB
                        break
                    elif torrent_file_size > 2048:  # Break if .torrent size exceeds 2 KiB
                        break
                elif torrent_file_size > 102400:
                    piece_size *= 2
                    if piece_size > our_max_size:
                        piece_size = our_max_size
                        cli_ui.warning('WARNING: .torrent size will exceed 100 KiB!')
                        break
                num_pieces = math.ceil(total_size / piece_size)
                torrent_file_size = 20 + (num_pieces * 20) + cls._calculate_pathname_bytes(files)

            return piece_size

        def _calculate_total_size(self):
            return sum(file.size for file in self.files)

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

    def create_base_from_existing_torrent(self, torrentpath, base_dir, uuid):
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

    """
    Upload Screenshots
    """
    def upload_screens(self, meta, screens, img_host_num, i, total_screens, custom_img_list, return_dict, retry_mode=False, max_retries=3):
        import nest_asyncio
        nest_asyncio.apply()
        os.chdir(f"{meta['base_dir']}/tmp/{meta['uuid']}")
        initial_img_host = self.config['DEFAULT'][f'img_host_{img_host_num}']
        img_host = meta['imghost']  # Use the correctly updated image host from meta

        image_list = []
        successfully_uploaded = set()  # Track successfully uploaded images
        initial_timeout = 10  # Set the initial timeout for backoff

        # Initialize the meta key for image sizes if not already present
        if 'image_sizes' not in meta:
            meta['image_sizes'] = {}

        if custom_img_list:
            image_glob = custom_img_list
            existing_images = []
        else:
            image_glob = glob.glob("*.png")
            if 'POSTER.png' in image_glob:
                image_glob.remove('POSTER.png')
            existing_images = meta.get('image_list', [])

        if len(existing_images) >= total_screens and not retry_mode and img_host == initial_img_host:
            console.print(f"[yellow]Skipping upload because images are already uploaded to {img_host}. Existing images: {len(existing_images)}, Required: {total_screens}")
            return existing_images, total_screens

        def exponential_backoff(retry_count, initial_timeout):
            # Exponential backoff logic with jitter
            if retry_count == 1:
                backoff_time = initial_timeout
            else:
                backoff_time = initial_timeout * (1.5 ** (retry_count - 1))
            backoff_time += random.uniform(0, 1)
            time.sleep(backoff_time)
            return backoff_time

        while True:
            remaining_images = [img for img in image_glob[-screens:] if img not in successfully_uploaded]

            with Progress(
                TextColumn("[bold green]Uploading Screens..."),
                BarColumn(),
                "[cyan]{task.completed}/{task.total}",
                TimeRemainingColumn()
            ) as progress:
                upload_task = progress.add_task("[green]Uploading Screens...", total=len(remaining_images))
                console.print(f"[cyan]Uploading screens to {img_host}...")
                # console.print(f"[debug] Remaining images to upload: {remaining_images}")
                for image in remaining_images:
                    retry_count = 0
                    upload_success = False

                    # Ensure the correct image path is assigned here
                    image_path = os.path.normpath(os.path.join(os.getcwd(), image))  # noqa F841
                    # console.print(f"[debug] Normalized image path: {image_path}")

                    while retry_count < max_retries and not upload_success:
                        try:
                            timeout = exponential_backoff(retry_count + 1, initial_timeout)

                            # Add imgbox handling here
                            if img_host == "imgbox":
                                try:
                                    # console.print("[blue]Uploading images to imgbox...")

                                    # Use the current event loop to run imgbox_upload
                                    loop = asyncio.get_event_loop()

                                    # Run the imgbox upload in the current event loop
                                    image_list = loop.run_until_complete(self.imgbox_upload(os.getcwd(), image_glob, meta))  # Pass all images

                                    # Ensure the image_list contains valid URLs before continuing
                                    if image_list and all('img_url' in img and 'raw_url' in img and 'web_url' in img for img in image_list):
                                        # console.print(f"[green]Successfully uploaded all images to imgbox.")
                                        upload_success = True

                                        # Track the successfully uploaded images without appending again to image_list
                                        for img in image_glob:
                                            successfully_uploaded.add(img)  # Track the uploaded images

                                        # Exit the loop after a successful upload
                                        return image_list, i

                                    else:
                                        console.print("[red]Imgbox upload failed, moving to the next image host.")
                                        img_host_num += 1
                                        next_img_host = self.config['DEFAULT'].get(f'img_host_{img_host_num + 1}', 'No more hosts')
                                        console.print(f"[blue]Moving to next image host: {next_img_host}.")
                                        img_host = self.config['DEFAULT'].get(f'img_host_{img_host_num}')

                                        if not img_host:
                                            console.print("[red]All image hosts failed. Unable to complete uploads.")
                                            return image_list, i

                                except Exception as e:
                                    console.print(f"[yellow]Failed to upload images to imgbox. Exception: {str(e)}")
                                    img_host_num += 1
                                    img_host = self.config['DEFAULT'].get(f'img_host_{img_host_num}')
                                    if not img_host:
                                        console.print("[red]All image hosts failed. Unable to complete uploads.")
                                        return image_list, i

                            elif img_host == "ptpimg":
                                payload = {
                                    'format': 'json',
                                    'api_key': self.config['DEFAULT']['ptpimg_api']
                                }
                                files = [('file-upload[0]', open(image, 'rb'))]
                                headers = {'referer': 'https://ptpimg.me/index.php'}
                                response = requests.post("https://ptpimg.me/upload.php", headers=headers, data=payload, files=files, timeout=timeout)
                                response = response.json()
                                ptpimg_code = response[0]['code']
                                ptpimg_ext = response[0]['ext']
                                img_url = f"https://ptpimg.me/{ptpimg_code}.{ptpimg_ext}"
                                raw_url = img_url
                                web_url = img_url
                                upload_success = True

                            elif img_host == "imgbb":
                                url = "https://api.imgbb.com/1/upload"
                                data = {
                                    'key': self.config['DEFAULT']['imgbb_api'],
                                    'image': base64.b64encode(open(image, "rb").read()).decode('utf8')
                                }
                                response = requests.post(url, data=data, timeout=timeout)
                                response = response.json()
                                img_url = response['data'].get('medium', response['data']['image'])['url']
                                raw_url = response['data']['image']['url']
                                web_url = response['data']['url_viewer']
                                upload_success = True

                            elif img_host == "ptscreens":
                                url = "https://ptscreens.com/api/1/upload"
                                data = {
                                    'image': base64.b64encode(open(image, "rb").read()).decode('utf8')
                                }
                                headers = {
                                    'X-API-Key': self.config['DEFAULT']['ptscreens_api'],
                                }
                                response = requests.post(url, data=data, headers=headers, timeout=timeout)
                                response = response.json()
                                if response.get('status_code') != 200:
                                    console.print("[yellow]PT Screens failed, trying next image host")
                                    break
                                img_url = response['data']['image']['url']
                                raw_url = img_url
                                web_url = img_url
                                upload_success = True

                            elif img_host == "oeimg":
                                url = "https://imgoe.download/api/1/upload"
                                data = {
                                    'image': base64.b64encode(open(image, "rb").read()).decode('utf8')
                                }
                                headers = {
                                    'X-API-Key': self.config['DEFAULT']['oeimg_api'],
                                }
                                response = requests.post(url, data=data, headers=headers, timeout=timeout)
                                response = response.json()
                                if response.get('status_code') != 200:
                                    console.print("[yellow]OEimg failed, trying next image host")
                                    break
                                img_url = response['data']['image']['url']
                                raw_url = response['data']['image']['url']
                                web_url = response['data']['url_viewer']
                                upload_success = True

                            elif img_host == "pixhost":
                                url = "https://api.pixhost.to/images"
                                data = {
                                    'content_type': '0',
                                    'max_th_size': 350,
                                }
                                files = {
                                    'img': ('file-upload[0]', open(image, 'rb')),
                                }
                                response = requests.post(url, data=data, files=files, timeout=timeout)
                                if response.status_code != 200:
                                    console.print("[yellow]Pixhost failed, trying next image host")
                                    break
                                response = response.json()
                                raw_url = response['th_url'].replace('https://t', 'https://img').replace('/thumbs/', '/images/')
                                img_url = response['th_url']
                                web_url = response['show_url']
                                upload_success = True

                            elif img_host == "lensdump":
                                url = "https://lensdump.com/api/1/upload"
                                data = {
                                    'image': base64.b64encode(open(image, "rb").read()).decode('utf8')
                                }
                                headers = {
                                    'X-API-Key': self.config['DEFAULT']['lensdump_api'],
                                }
                                response = requests.post(url, data=data, headers=headers, timeout=timeout)
                                response = response.json()
                                if response.get('status_code') != 200:
                                    console.print("[yellow]Lensdump failed, trying next image host")
                                    break
                                img_url = response['data']['image']['url']
                                raw_url = img_url
                                web_url = response['data']['url_viewer']
                                upload_success = True

                            # Only increment `i` after a successful upload
                            if upload_success:
                                image_size = os.path.getsize(image)  # Get the image size in bytes
                                image_dict = {
                                    'img_url': img_url,
                                    'raw_url': raw_url,
                                    'web_url': web_url
                                }
                                image_list.append(image_dict)
                                successfully_uploaded.add(image)  # Track the uploaded image

                                # Store size in meta, indexed by the img_url
                                meta['image_sizes'][img_url] = image_size  # Keep sizes separate in meta['image_sizes']

                                progress.advance(upload_task)
                                i += 1  # Increment the image counter only after success
                                break  # Break retry loop after a successful upload

                        except Exception as e:
                            retry_count += 1
                            console.print(f"[yellow]Failed to upload {image} to {img_host}. Attempt {retry_count}/{max_retries}. Exception: {str(e)}")
                            exponential_backoff(retry_count, initial_timeout)

                            if retry_count >= max_retries:
                                next_img_host = self.config['DEFAULT'].get(f'img_host_{img_host_num + 1}', 'No more hosts')
                                console.print(f"[red]Max retries reached for {img_host}. Moving to next image host: {next_img_host}.")
                                img_host_num += 1
                                img_host = self.config['DEFAULT'].get(f'img_host_{img_host_num}')
                                if not img_host:
                                    console.print("[red]All image hosts failed. Unable to complete uploads.")
                                    return image_list, i
                                break

                # Exit the loop after switching hosts
                if img_host_num > 1 and not upload_success:
                    continue  # Continue to the next host
                else:
                    break  # Break if upload was successful

        return image_list, i

    async def imgbox_upload(self, chdir, image_glob, meta):
        try:
            os.chdir(chdir)
            image_list = []

            console.print(f"[debug] Starting upload of {len(image_glob)} images to imgbox...")
            async with pyimgbox.Gallery(thumb_width=350, square_thumbs=False) as gallery:
                for image in image_glob:
                    # console.print(f"[blue]Uploading image: {image}")

                    try:
                        async for submission in gallery.add([image]):
                            if not submission['success']:
                                console.print(f"[red]There was an error uploading to imgbox: [yellow]{submission['error']}[/yellow][/red]")
                                return []  # Return empty list in case of failure
                            else:
                                # Add the uploaded image info to image_list
                                image_dict = {
                                    'web_url': submission['web_url'],
                                    'img_url': submission['thumbnail_url'],
                                    'raw_url': submission['image_url']
                                }
                                image_list.append(image_dict)

                                console.print(f"[green]Successfully uploaded image: {image}")

                    except Exception as e:
                        console.print(f"[red]Error during upload for {image}: {str(e)}")
                        return []  # Return empty list in case of error

            # After uploading all images, validate URLs and get sizes
            # console.print("[blue]Validating images and retrieving their sizes...")
            valid_images = await self.check_images_concurrently(image_list, meta)

            if valid_images:
                console.print(f"[yellow]Successfully uploaded and validated {len(valid_images)} images.")
            else:
                console.print("[red]Failed to validate any images.")
                return []  # Return empty list if no valid images

            return valid_images  # Return the valid image list after validation

        except Exception as e:
            console.print(f"[red]An error occurred while uploading images to imgbox: {str(e)}")
            return []  # Return empty list in case of an unexpected failure

    async def get_name(self, meta):
        type = meta.get('type', "")
        title = meta.get('title', "")
        alt_title = meta.get('aka', "")
        year = meta.get('year', "")
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
            console.log(meta)

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
            elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD"):  # DVD Remux
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

        try:
            name = ' '.join(name.split())
        except Exception:
            console.print("[bold red]Unable to generate name. Please re-run and correct any of the following args if needed.")
            console.print(f"--category [yellow]{meta['category']}")
            console.print(f"--type [yellow]{meta['type']}")
            console.print(f"--source [yellow]{meta['source']}")

            exit()
        name_notag = name
        name = name_notag + tag
        clean_name = self.clean_filename(name)
        return name_notag, name, clean_name, potential_missing

    async def get_season_episode(self, video, meta):
        if meta['category'] == 'TV':
            filelist = meta['filelist']
            meta['tv_pack'] = 0
            is_daily = False
            if meta['anime'] is False:
                try:
                    if meta.get('manual_date'):
                        raise ManualDateException  # noqa: F405
                    try:
                        guess_year = guessit(video)['year']
                    except Exception:
                        guess_year = ""
                    if guessit(video)["season"] == guess_year:
                        if f"s{guessit(video)['season']}" in video.lower():
                            season_int = str(guessit(video)["season"])
                            season = "S" + season_int.zfill(2)
                        else:
                            season_int = "1"
                            season = "S01"
                    else:
                        season_int = str(guessit(video)["season"])
                        season = "S" + season_int.zfill(2)

                except Exception:
                    try:
                        guess_date = meta.get('manual_date', guessit(video)['date']) if meta.get('manual_date') else guessit(video)['date']
                        season_int, episode_int = self.daily_to_tmdb_season_episode(meta.get('tmdb'), guess_date)
                        # season = f"S{season_int.zfill(2)}"
                        # episode = f"E{episode_int.zfill(2)}"
                        season = str(guess_date)
                        episode = ""
                        is_daily = True
                    except Exception:
                        console.print_exception()
                        season_int = "1"
                        season = "S01"
                try:
                    if is_daily is not True:
                        episodes = ""
                        if len(filelist) == 1:
                            episodes = guessit(video)['episode']
                            if isinstance(episodes, list):
                                episode = ""
                                for item in guessit(video)["episode"]:
                                    ep = (str(item).zfill(2))
                                    episode += f"E{ep}"
                                episode_int = episodes[0]
                            else:
                                episode_int = str(episodes)
                                episode = "E" + str(episodes).zfill(2)
                        else:
                            episode = ""
                            episode_int = "0"
                            meta['tv_pack'] = 1
                except Exception:
                    episode = ""
                    episode_int = "0"
                    meta['tv_pack'] = 1
            else:
                # If Anime
                parsed = anitopy.parse(Path(video).name)
                romaji, mal_id, eng_title, seasonYear, anilist_episodes = self.get_romaji(parsed['anime_title'], meta.get('mal', None))
                if mal_id:
                    meta['mal_id'] = mal_id
                if meta.get('mal') is not None:
                    mal_id = meta.get('mal')
                if meta.get('tmdb_manual', None) is None:
                    year = parsed.get('anime_year', str(seasonYear))
                    meta = await self.get_tmdb_id(guessit(parsed['anime_title'], {"excludes": ["country", "language"]})['title'], year, meta, meta['category'])
                meta = await self.tmdb_other_meta(meta)
                if meta['category'] != "TV":
                    return meta

                tag = parsed.get('release_group', "")
                if tag != "":
                    meta['tag'] = f"-{tag}"
                if len(filelist) == 1:
                    try:
                        episodes = parsed.get('episode_number', guessit(video).get('episode', '1'))
                        if not isinstance(episodes, list) and not episodes.isnumeric():
                            episodes = guessit(video)['episode']
                        if isinstance(episodes, list):
                            episode_int = int(episodes[0])  # Always convert to integer
                            episode = "".join([f"E{str(int(item)).zfill(2)}" for item in episodes])
                        else:
                            episode_int = int(episodes)  # Convert to integer
                            episode = f"E{str(episode_int).zfill(2)}"
                    except Exception:
                        episode = "E01"
                        episode_int = 1  # Ensure it's an integer
                        console.print('[bold yellow]There was an error guessing the episode number. Guessing E01. Use [bold green]--episode #[/bold green] to correct if needed')
                        await asyncio.sleep(1.5)
                else:
                    episode = ""
                    episode_int = 0  # Ensure it's an integer
                    meta['tv_pack'] = 1

                try:
                    if meta.get('season_int'):
                        season_int = int(meta.get('season_int'))  # Convert to integer
                    else:
                        season = parsed.get('anime_season', guessit(video).get('season', '1'))
                        season_int = int(season)  # Convert to integer
                    season = f"S{str(season_int).zfill(2)}"
                except Exception:
                    try:
                        if episode_int >= anilist_episodes:
                            params = {
                                'id': str(meta['tvdb_id']),
                                'origin': 'tvdb',
                                'absolute': str(episode_int),
                            }
                            url = "https://thexem.info/map/single"
                            response = requests.post(url, params=params).json()
                            if response['result'] == "failure":
                                raise XEMNotFound  # noqa: F405
                            if meta['debug']:
                                console.log(f"[cyan]TheXEM Absolute -> Standard[/cyan]\n{response}")
                            season_int = int(response['data']['scene']['season'])  # Convert to integer
                            season = f"S{str(season_int).zfill(2)}"
                            if len(filelist) == 1:
                                episode_int = int(response['data']['scene']['episode'])  # Convert to integer
                                episode = f"E{str(episode_int).zfill(2)}"
                        else:
                            season_int = 1  # Default to 1 if error occurs
                            season = "S01"
                            names_url = f"https://thexem.info/map/names?origin=tvdb&id={str(meta['tvdb_id'])}"
                            names_response = requests.get(names_url).json()
                            if meta['debug']:
                                console.log(f'[cyan]Matching Season Number from TheXEM\n{names_response}')
                            difference = 0
                            if names_response['result'] == "success":
                                for season_num, values in names_response['data'].items():
                                    for lang, names in values.items():
                                        if lang == "jp":
                                            for name in names:
                                                romaji_check = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", romaji.lower().replace(' ', ''))
                                                name_check = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", name.lower().replace(' ', ''))
                                                diff = SequenceMatcher(None, romaji_check, name_check).ratio()
                                                if romaji_check in name_check and diff >= difference:
                                                    season_int = int(season_num) if season_num != "all" else 1  # Convert to integer
                                                    season = f"S{str(season_int).zfill(2)}"
                                                    difference = diff
                                        if lang == "us":
                                            for name in names:
                                                eng_check = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", eng_title.lower().replace(' ', ''))
                                                name_check = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", name.lower().replace(' ', ''))
                                                diff = SequenceMatcher(None, eng_check, name_check).ratio()
                                                if eng_check in name_check and diff >= difference:
                                                    season_int = int(season_num) if season_num != "all" else 1  # Convert to integer
                                                    season = f"S{str(season_int).zfill(2)}"
                                                    difference = diff
                            else:
                                raise XEMNotFound  # noqa: F405
                    except Exception:
                        if meta['debug']:
                            console.print_exception()
                        try:
                            season = guessit(video).get('season', '1')
                            season_int = int(season)  # Convert to integer
                        except Exception:
                            season_int = 1  # Default to 1 if error occurs
                            season = "S01"
                        console.print(f"[bold yellow]{meta['title']} does not exist on thexem, guessing {season}")
                        console.print(f"[bold yellow]If [green]{season}[/green] is incorrect, use --season to correct")
                        await asyncio.sleep(3)

            if meta.get('manual_season', None) is None:
                meta['season'] = season
            else:
                season_int = meta['manual_season'].lower().replace('s', '')
                meta['season'] = f"S{meta['manual_season'].lower().replace('s', '').zfill(2)}"
            if meta.get('manual_episode', None) is None:
                meta['episode'] = episode
            else:
                episode_int = meta['manual_episode'].lower().replace('e', '')
                meta['episode'] = f"E{meta['manual_episode'].lower().replace('e', '').zfill(2)}"
                meta['tv_pack'] = 0

            # if " COMPLETE " in Path(video).name.replace('.', ' '):
            #     meta['season'] = "COMPLETE"
            meta['season_int'] = season_int
            meta['episode_int'] = episode_int

            meta['episode_title_storage'] = guessit(video, {"excludes": "part"}).get('episode_title', '')
            if meta['season'] == "S00" or meta['episode'] == "E00":
                meta['episode_title'] = meta['episode_title_storage']

            # Guess the part of the episode (if available)
            meta['part'] = ""
            if meta['tv_pack'] == 1:
                part = guessit(os.path.dirname(video)).get('part')
                meta['part'] = f"Part {part}" if part else ""

        return meta

    def get_service(self, video=None, tag=None, audio=None, guess_title=None, get_services_only=False):
        services = {
            '9NOW': '9NOW', '9Now': '9NOW', 'AE': 'AE', 'A&E': 'AE', 'AJAZ': 'AJAZ', 'Al Jazeera English': 'AJAZ',
            'ALL4': 'ALL4', 'Channel 4': 'ALL4', 'AMBC': 'AMBC', 'ABC': 'AMBC', 'AMC': 'AMC', 'AMZN': 'AMZN',
            'Amazon Prime': 'AMZN', 'ANLB': 'ANLB', 'AnimeLab': 'ANLB', 'ANPL': 'ANPL', 'Animal Planet': 'ANPL',
            'AOL': 'AOL', 'ARD': 'ARD', 'AS': 'AS', 'Adult Swim': 'AS', 'ATK': 'ATK', "America's Test Kitchen": 'ATK',
            'ATVP': 'ATVP', 'AppleTV': 'ATVP', 'AUBC': 'AUBC', 'ABC Australia': 'AUBC', 'BCORE': 'BCORE', 'BKPL': 'BKPL',
            'Blackpills': 'BKPL', 'BluTV': 'BLU', 'Binge': 'BNGE', 'BOOM': 'BOOM', 'Boomerang': 'BOOM', 'BRAV': 'BRAV',
            'BravoTV': 'BRAV', 'CBC': 'CBC', 'CBS': 'CBS', 'CC': 'CC', 'Comedy Central': 'CC', 'CCGC': 'CCGC',
            'Comedians in Cars Getting Coffee': 'CCGC', 'CHGD': 'CHGD', 'CHRGD': 'CHGD', 'CMAX': 'CMAX', 'Cinemax': 'CMAX',
            'CMOR': 'CMOR', 'CMT': 'CMT', 'Country Music Television': 'CMT', 'CN': 'CN', 'Cartoon Network': 'CN', 'CNBC': 'CNBC',
            'CNLP': 'CNLP', 'Canal+': 'CNLP', 'CNGO': 'CNGO', 'Cinego': 'CNGO', 'COOK': 'COOK', 'CORE': 'CORE', 'CR': 'CR',
            'Crunchy Roll': 'CR', 'Crave': 'CRAV', 'CRIT': 'CRIT', 'Criterion': 'CRIT', 'CRKL': 'CRKL', 'Crackle': 'CRKL',
            'CSPN': 'CSPN', 'CSpan': 'CSPN', 'CTV': 'CTV', 'CUR': 'CUR', 'CuriosityStream': 'CUR', 'CW': 'CW', 'The CW': 'CW',
            'CWS': 'CWS', 'CWSeed': 'CWS', 'DAZN': 'DAZN', 'DCU': 'DCU', 'DC Universe': 'DCU', 'DDY': 'DDY',
            'Digiturk Diledigin Yerde': 'DDY', 'DEST': 'DEST', 'DramaFever': 'DF', 'DHF': 'DHF', 'Deadhouse Films': 'DHF',
            'DISC': 'DISC', 'Discovery': 'DISC', 'DIY': 'DIY', 'DIY Network': 'DIY', 'DOCC': 'DOCC', 'Doc Club': 'DOCC',
            'DPLY': 'DPLY', 'DPlay': 'DPLY', 'DRPO': 'DRPO', 'Discovery Plus': 'DSCP', 'DSKI': 'DSKI', 'Daisuki': 'DSKI',
            'DSNP': 'DSNP', 'Disney+': 'DSNP', 'DSNY': 'DSNY', 'Disney': 'DSNY', 'DTV': 'DTV', 'EPIX': 'EPIX', 'ePix': 'EPIX',
            'ESPN': 'ESPN', 'ESQ': 'ESQ', 'Esquire': 'ESQ', 'ETTV': 'ETTV', 'El Trece': 'ETTV', 'ETV': 'ETV', 'E!': 'ETV',
            'FAM': 'FAM', 'Fandor': 'FANDOR', 'Facebook Watch': 'FBWatch', 'FJR': 'FJR', 'Family Jr': 'FJR', 'FMIO': 'FMIO',
            'Filmio': 'FMIO', 'FOOD': 'FOOD', 'Food Network': 'FOOD', 'FOX': 'FOX', 'Fox': 'FOX', 'Fox Premium': 'FOXP',
            'UFC Fight Pass': 'FP', 'FPT': 'FPT', 'FREE': 'FREE', 'Freeform': 'FREE', 'FTV': 'FTV', 'FUNI': 'FUNI', 'FUNi': 'FUNI',
            'Foxtel': 'FXTL', 'FYI': 'FYI', 'FYI Network': 'FYI', 'GC': 'GC', 'NHL GameCenter': 'GC', 'GLBL': 'GLBL',
            'Global': 'GLBL', 'GLOB': 'GLOB', 'GloboSat Play': 'GLOB', 'GO90': 'GO90', 'GagaOOLala': 'Gaga', 'HBO': 'HBO',
            'HBO Go': 'HBO', 'HGTV': 'HGTV', 'HIDI': 'HIDI', 'HIST': 'HIST', 'History': 'HIST', 'HLMK': 'HLMK', 'Hallmark': 'HLMK',
            'HMAX': 'HMAX', 'HBO Max': 'HMAX', 'HS': 'HTSR', 'HTSR': 'HTSR', 'HSTR': 'Hotstar', 'HULU': 'HULU', 'Hulu': 'HULU',
            'hoichoi': 'HoiChoi', 'ID': 'ID', 'Investigation Discovery': 'ID', 'IFC': 'IFC', 'iflix': 'IFX',
            'National Audiovisual Institute': 'INA', 'ITV': 'ITV', 'JOYN': 'JOYN', 'KAYO': 'KAYO', 'KNOW': 'KNOW', 'Knowledge Network': 'KNOW',
            'KNPY': 'KNPY', 'Kanopy': 'KNPY', 'LIFE': 'LIFE', 'Lifetime': 'LIFE', 'LN': 'LN', 'MA': 'MA', 'Movies Anywhere': 'MA',
            'MAX': 'MAX', 'MBC': 'MBC', 'MNBC': 'MNBC', 'MSNBC': 'MNBC', 'MTOD': 'MTOD', 'Motor Trend OnDemand': 'MTOD', 'MTV': 'MTV',
            'MUBI': 'MUBI', 'NATG': 'NATG', 'National Geographic': 'NATG', 'NBA': 'NBA', 'NBA TV': 'NBA', 'NBC': 'NBC', 'NF': 'NF',
            'Netflix': 'NF', 'National Film Board': 'NFB', 'NFL': 'NFL', 'NFLN': 'NFLN', 'NFL Now': 'NFLN', 'NICK': 'NICK',
            'Nickelodeon': 'NICK', 'NOW': 'NOW', 'NRK': 'NRK', 'Norsk Rikskringkasting': 'NRK', 'OnDemandKorea': 'ODK', 'Opto': 'OPTO',
            'ORF': 'ORF', 'ORF ON': 'ORF', 'Oprah Winfrey Network': 'OWN', 'PA': 'PA', 'PBS': 'PBS', 'PBSK': 'PBSK', 'PBS Kids': 'PBSK',
            'PCOK': 'PCOK', 'Peacock': 'PCOK', 'PLAY': 'PLAY', 'PLUZ': 'PLUZ', 'Pluzz': 'PLUZ', 'PMNP': 'PMNP', 'PMNT': 'PMNT',
            'PMTP': 'PMTP', 'POGO': 'POGO', 'PokerGO': 'POGO', 'PSN': 'PSN', 'Playstation Network': 'PSN', 'PUHU': 'PUHU', 'QIBI': 'QIBI',
            'RED': 'RED', 'YouTube Red': 'RED', 'RKTN': 'RKTN', 'Rakuten TV': 'RKTN', 'The Roku Channel': 'ROKU', 'RNET': 'RNET',
            'OBB Railnet': 'RNET', 'RSTR': 'RSTR', 'RTE': 'RTE', 'RTE One': 'RTE', 'RTLP': 'RTLP', 'RTL+': 'RTLP', 'RUUTU': 'RUUTU',
            'SBS': 'SBS', 'Science Channel': 'SCI', 'SESO': 'SESO', 'SeeSo': 'SESO', 'SHMI': 'SHMI', 'Shomi': 'SHMI', 'SKST': 'SKST',
            'SkyShowtime': 'SKST', 'SHO': 'SHO', 'Showtime': 'SHO', 'SNET': 'SNET', 'Sportsnet': 'SNET', 'Sony': 'SONY', 'SPIK': 'SPIK',
            'Spike': 'SPIK', 'Spike TV': 'SPKE', 'SPRT': 'SPRT', 'Sprout': 'SPRT', 'STAN': 'STAN', 'Stan': 'STAN', 'STARZ': 'STARZ',
            'STRP': 'STRP', 'Star+': 'STRP', 'STZ': 'STZ', 'Starz': 'STZ', 'SVT': 'SVT', 'Sveriges Television': 'SVT', 'SWER': 'SWER',
            'SwearNet': 'SWER', 'SYFY': 'SYFY', 'Syfy': 'SYFY', 'TBS': 'TBS', 'TEN': 'TEN', 'TIMV': 'TIMV', 'TIMvision': 'TIMV',
            'TFOU': 'TFOU', 'TFou': 'TFOU', 'TIMV': 'TIMV', 'TLC': 'TLC', 'TOU': 'TOU', 'TRVL': 'TRVL', 'TUBI': 'TUBI', 'TubiTV': 'TUBI',
            'TV3': 'TV3', 'TV3 Ireland': 'TV3', 'TV4': 'TV4', 'TV4 Sweeden': 'TV4', 'TVING': 'TVING', 'TVL': 'TVL', 'TV Land': 'TVL',
            'TVNZ': 'TVNZ', 'UFC': 'UFC', 'UKTV': 'UKTV', 'UNIV': 'UNIV', 'Univision': 'UNIV', 'USAN': 'USAN', 'USA Network': 'USAN',
            'VH1': 'VH1', 'VIAP': 'VIAP', 'VICE': 'VICE', 'Viceland': 'VICE', 'Viki': 'VIKI', 'VIMEO': 'VIMEO', 'VLCT': 'VLCT',
            'Velocity': 'VLCT', 'VMEO': 'VMEO', 'Vimeo': 'VMEO', 'VRV': 'VRV', 'VUDU': 'VUDU', 'WME': 'WME', 'WatchMe': 'WME', 'WNET': 'WNET',
            'W Network': 'WNET', 'WWEN': 'WWEN', 'WWE Network': 'WWEN', 'XBOX': 'XBOX', 'Xbox Video': 'XBOX', 'YHOO': 'YHOO', 'Yahoo': 'YHOO',
            'YT': 'YT', 'ZDF': 'ZDF', 'iP': 'iP', 'BBC iPlayer': 'iP', 'iQIYI': 'iQIYI', 'iT': 'iT', 'iTunes': 'iT'
        }

        if get_services_only:
            return services
        service = guessit(video).get('streaming_service', "")

        video_name = re.sub(r"[.()]", " ", video.replace(tag, '').replace(guess_title, ''))
        if "DTS-HD MA" in audio:
            video_name = video_name.replace("DTS-HD.MA.", "").replace("DTS-HD MA ", "")
        for key, value in services.items():
            if (' ' + key + ' ') in video_name and key not in guessit(video, {"excludes": ["country", "language"]}).get('title', ''):
                service = value
            elif key == service:
                service = value
        service_longname = service
        for key, value in services.items():
            if value == service and len(key) > len(service_longname):
                service_longname = key
        if service_longname == "Amazon Prime":
            service_longname = "Amazon"
        return service, service_longname

    def stream_optimized(self, stream_opt):
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

    def clean_filename(self, name):
        invalid = '<>:"/\\|?*'
        for char in invalid:
            name = name.replace(char, '-')
        return name

    async def gen_desc(self, meta):
        if not meta.get('skip_gen_desc', False):
            def clean_text(text):
                return text.replace('\r\n', '').replace('\n', '').strip()

            desclink = meta.get('desclink')
            descfile = meta.get('descfile')

            with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
                description.seek(0)

                if meta.get('desc_template'):
                    from jinja2 import Template
                    try:
                        with open(f"{meta['base_dir']}/data/templates/{meta['desc_template']}.txt", 'r') as f:
                            template = Template(f.read())
                            template_desc = template.render(meta)
                            if clean_text(template_desc):
                                description.write(template_desc + "\n")
                                console.print(f"[INFO] Description from template '{meta['desc_template']}' used.")
                    except FileNotFoundError:
                        console.print(f"[ERROR] Template '{meta['desc_template']}' not found.")

                if meta.get('nfo'):
                    nfo_files = glob.glob("*.nfo")
                    if nfo_files:
                        nfo = nfo_files[0]
                        with open(nfo, 'r', encoding="utf-8") as nfo_file:
                            nfo_content = nfo_file.read()
                        description.write(f"[code]{nfo_content}[/code]\n")
                        meta['description'] = "CUSTOM"
                        console.print(f"[INFO] NFO file '{nfo}' used.")

                if desclink:
                    try:
                        parsed = urllib.parse.urlparse(desclink.replace('/raw/', '/'))
                        split = os.path.split(parsed.path)
                        raw = parsed._replace(path=f"{split[0]}/raw/{split[1]}" if split[0] != '/' else f"/raw{parsed.path}")
                        raw_url = urllib.parse.urlunparse(raw)
                        desclink_content = requests.get(raw_url).text
                        description.write(desclink_content + "\n")
                        meta['description'] = "CUSTOM"
                        console.print(f"[INFO] Description from link '{desclink}' used.")
                    except Exception as e:
                        console.print(f"[ERROR] Failed to fetch description from link: {e}")

                if descfile and os.path.isfile(descfile):
                    with open(descfile, 'r') as f:
                        file_content = f.read()
                    description.write(file_content)
                    meta['description'] = "CUSTOM"
                    console.print(f"[INFO] Description from file '{descfile}' used.")

                if meta.get('desc'):
                    description.write(meta['desc'] + "\n")
                    meta['description'] = "CUSTOM"
                    console.print("[INFO] Custom description used.")

                description.write("\n")
                return meta
        else:
            description_text = meta.get('description') if meta.get('description') else ""
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

    async def package(self, meta):
        if meta['tag'] == "":
            tag = ""
        else:
            tag = f" / {meta['tag'][1:]}"
        if meta['is_disc'] == "DVD":
            res = meta['source']
        else:
            res = meta['resolution']

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/GENERIC_INFO.txt", 'w', encoding="utf-8") as generic:
            generic.write(f"Name: {meta['name']}\n\n")
            generic.write(f"Overview: {meta['overview']}\n\n")
            generic.write(f"{res} / {meta['type']}{tag}\n\n")
            generic.write(f"Category: {meta['category']}\n")
            generic.write(f"TMDB: https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb']}\n")
            if meta['imdb_id'] != "0":
                generic.write(f"IMDb: https://www.imdb.com/title/tt{meta['imdb_id']}\n")
            if meta['tvdb_id'] != "0":
                generic.write(f"TVDB: https://www.thetvdb.com/?id={meta['tvdb_id']}&tab=series\n")
            poster_img = f"{meta['base_dir']}/tmp/{meta['uuid']}/POSTER.png"
            if meta.get('poster', None) not in ['', None] and not os.path.exists(poster_img):
                if meta.get('rehosted_poster', None) is None:
                    r = requests.get(meta['poster'], stream=True)
                    if r.status_code == 200:
                        console.print("[bold yellow]Rehosting Poster")
                        r.raw.decode_content = True
                        with open(poster_img, 'wb') as f:
                            shutil.copyfileobj(r.raw, f)
                        poster, dummy = self.upload_screens(meta, 1, 1, 0, 1, [poster_img], {})
                        poster = poster[0]
                        generic.write(f"TMDB Poster: {poster.get('raw_url', poster.get('img_url'))}\n")
                        meta['rehosted_poster'] = poster.get('raw_url', poster.get('img_url'))
                        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as metafile:
                            json.dump(meta, metafile, indent=4)
                            metafile.close()
                    else:
                        console.print("[bold yellow]Poster could not be retrieved")
            elif os.path.exists(poster_img) and meta.get('rehosted_poster') is not None:
                generic.write(f"TMDB Poster: {meta.get('rehosted_poster')}\n")
            if len(meta['image_list']) > 0:
                generic.write("\nImage Webpage:\n")
                for each in meta['image_list']:
                    generic.write(f"{each['web_url']}\n")
                generic.write("\nThumbnail Image:\n")
                for each in meta['image_list']:
                    generic.write(f"{each['img_url']}\n")
        title = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", meta['title'])
        archive = f"{meta['base_dir']}/tmp/{meta['uuid']}/{title}"
        torrent_files = glob.glob1(f"{meta['base_dir']}/tmp/{meta['uuid']}", "*.torrent")
        if isinstance(torrent_files, list) and len(torrent_files) > 1:
            for each in torrent_files:
                if not each.startswith(('BASE', '[RAND')):
                    os.remove(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/{each}"))
        try:
            if os.path.exists(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"):
                base_torrent = Torrent.read(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")
                manual_name = re.sub(r"[^0-9a-zA-Z\[\]\'\-]+", ".", os.path.basename(meta['path']))
                Torrent.copy(base_torrent).write(f"{meta['base_dir']}/tmp/{meta['uuid']}/{manual_name}.torrent", overwrite=True)
                # shutil.copy(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"), os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['name'].replace(' ', '.')}.torrent").replace(' ', '.'))
            filebrowser = self.config['TRACKERS'].get('MANUAL', {}).get('filebrowser', None)
            shutil.make_archive(archive, 'tar', f"{meta['base_dir']}/tmp/{meta['uuid']}")
            if filebrowser is not None:
                url = '/'.join(s.strip('/') for s in (filebrowser, f"/tmp/{meta['uuid']}"))
                url = urllib.parse.quote(url, safe="https://")
            else:
                files = {
                    "files[]": (f"{meta['title']}.tar", open(f"{archive}.tar", 'rb'))
                }
                response = requests.post("https://uguu.se/upload.php", files=files).json()
                if meta['debug']:
                    console.print(f"[cyan]{response}")
                url = response['files'][0]['url']
            return url
        except Exception:
            return False
        return

    async def get_imdb_aka(self, imdb_id):
        if imdb_id == "0":
            return "", None
        ia = Cinemagoer()
        result = ia.get_movie(imdb_id.replace('tt', ''))

        original_language = result.get('language codes')
        if isinstance(original_language, list):
            if len(original_language) > 1:
                original_language = None
            elif len(original_language) == 1:
                original_language = original_language[0]
        aka = result.get('original title', result.get('localized title', "")).replace(' - IMDb', '').replace('\u00ae', '')
        if aka != "":
            aka = f" AKA {aka}"
        return aka, original_language

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

    def get_tmdb_imdb_from_mediainfo(self, mediainfo, category, is_disc, tmdbid, imdbid):
        if not is_disc:
            if mediainfo['media']['track'][0].get('extra'):
                extra = mediainfo['media']['track'][0]['extra']
                for each in extra:
                    if each.lower().startswith('tmdb'):
                        parser = Args(config=self.config)
                        category, tmdbid = parser.parse_tmdb_id(id=extra[each], category=category)
                    if each.lower().startswith('imdb'):
                        try:
                            imdbid = str(int(extra[each].replace('tt', ''))).zfill(7)
                        except Exception:
                            pass
        return category, tmdbid, imdbid

    def daily_to_tmdb_season_episode(self, tmdbid, date):
        show = tmdb.TV(tmdbid)
        seasons = show.info().get('seasons')
        season = '1'
        episode = '1'
        date = datetime.fromisoformat(str(date))
        for each in seasons:
            air_date = datetime.fromisoformat(each['air_date'])
            if air_date <= date:
                season = str(each['season_number'])
        season_info = tmdb.TV_Seasons(tmdbid, season).info().get('episodes')
        for each in season_info:
            if str(each['air_date']) == str(date):
                episode = str(each['episode_number'])
                break
        else:
            console.print(f"[yellow]Unable to map the date ([bold yellow]{str(date)}[/bold yellow]) to a Season/Episode number")
        return season, episode

    async def get_imdb_info(self, imdbID, meta):
        imdb_info = {}
        if int(str(imdbID).replace('tt', '')) != 0:
            ia = Cinemagoer()
            info = ia.get_movie(imdbID)
            imdb_info['title'] = info.get('title')
            imdb_info['year'] = info.get('year')
            imdb_info['aka'] = info.get('original title', info.get('localized title', imdb_info['title'])).replace(' - IMDb', '')
            imdb_info['type'] = info.get('kind')
            imdb_info['imdbID'] = info.get('imdbID')
            imdb_info['runtime'] = info.get('runtimes', ['0'])[0]
            imdb_info['cover'] = info.get('full-size cover url', '').replace(".jpg", "._V1_FMjpg_UX750_.jpg")
            imdb_info['plot'] = info.get('plot', [''])[0]
            imdb_info['genres'] = ', '.join(info.get('genres', ''))
            imdb_info['rating'] = info.get('rating', 'N/A')
            imdb_info['original_language'] = info.get('language codes')
            if isinstance(imdb_info['original_language'], list):
                if len(imdb_info['original_language']) > 1:
                    imdb_info['original_language'] = None
                elif len(imdb_info['original_language']) == 1:
                    imdb_info['original_language'] = imdb_info['original_language'][0]
            if imdb_info['cover'] == '':
                imdb_info['cover'] = meta.get('poster', '')
            if len(info.get('directors', [])) >= 1:
                imdb_info['directors'] = []
                for director in info.get('directors'):
                    imdb_info['directors'].append(f"nm{director.getID()}")
        else:
            imdb_info = {
                'title': meta['title'],
                'year': meta['year'],
                'aka': '',
                'type': None,
                'runtime': meta.get('runtime', '60'),
                'cover': meta.get('poster'),
            }
            if len(meta.get('tmdb_directors', [])) >= 1:
                imdb_info['directors'] = meta['tmdb_directors']

        return imdb_info

    async def search_imdb(self, filename, search_year):
        imdbID = '0'
        ia = Cinemagoer()
        search = ia.search_movie(filename)
        for movie in search:
            if filename in movie.get('title', ''):
                if movie.get('year') == search_year:
                    imdbID = str(movie.movieID).replace('tt', '')
        return imdbID

    async def imdb_other_meta(self, meta):
        imdb_info = meta['imdb_info'] = await self.get_imdb_info(meta['imdb_id'], meta)
        meta['title'] = imdb_info['title']
        meta['year'] = imdb_info['year']
        meta['aka'] = imdb_info['aka']
        meta['poster'] = imdb_info['cover']
        meta['original_language'] = imdb_info['original_language']
        meta['overview'] = imdb_info['plot']
        meta['imdb_rating'] = imdb_info['rating']

        difference = SequenceMatcher(None, meta['title'].lower(), meta['aka'][5:].lower()).ratio()
        if difference >= 0.9 or meta['aka'][5:].strip() == "" or meta['aka'][5:].strip().lower() in meta['title'].lower():
            meta['aka'] = ""
        if f"({meta['year']})" in meta['aka']:
            meta['aka'] = meta['aka'].replace(f"({meta['year']})", "").strip()
        return meta

    async def search_tvmaze(self, filename, year, imdbID, tvdbID):
        tvdbID = int(tvdbID)
        tvmazeID = 0
        lookup = False
        show = None
        if imdbID is None:
            imdbID = '0'
        if tvdbID is None:
            tvdbID = 0
        if int(tvdbID) != 0:
            params = {
                "thetvdb": tvdbID
            }
            url = "https://api.tvmaze.com/lookup/shows"
            lookup = True
        elif int(imdbID) != 0:
            params = {
                "imdb": f"tt{imdbID}"
            }
            url = "https://api.tvmaze.com/lookup/shows"
            lookup = True
        else:
            params = {
                "q": filename
            }
            url = "https://api.tvmaze.com/search/shows"
        resp = requests.get(url=url, params=params)
        if resp.ok:
            resp = resp.json()
            if resp is None:
                return tvmazeID, imdbID, tvdbID
            if lookup is True:
                show = resp
            else:
                if year not in (None, ''):
                    for each in resp:
                        premier_date = each['show'].get('premiered', '')
                        if premier_date is not None:
                            if premier_date.startswith(str(year)):
                                show = each['show']
                elif len(resp) >= 1:
                    show = resp[0]['show']
            if show is not None:
                tvmazeID = show.get('id')
                if int(imdbID) == 0:
                    if show.get('externals', {}).get('imdb', '0') is not None:
                        imdbID = str(show.get('externals', {}).get('imdb', '0')).replace('tt', '')
                if int(tvdbID) == 0:
                    if show.get('externals', {}).get('tvdb', '0') is not None:
                        tvdbID = show.get('externals', {}).get('tvdb', '0')
        return tvmazeID, imdbID, tvdbID
