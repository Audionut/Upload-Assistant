# -*- coding: utf-8 -*-
from torf import Torrent
import xmlrpc.client
import bencode
import os
import qbittorrentapi
from deluge_client import DelugeRPCClient
import transmission_rpc
import base64
from pyrobase.parts import Bunch
import errno
import asyncio
import ssl
import shutil
import time
from src.console import console
import re
import platform


class Clients():
    """
    Add to torrent client
    """
    def __init__(self, config):
        self.config = config
        pass

    async def add_to_client(self, meta, tracker):
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]{meta['clean_name']}.torrent"
        if meta.get('no_seed', False) is True:
            console.print("[bold red]--no-seed was passed, so the torrent will not be added to the client")
            console.print("[bold yellow]Add torrent manually to the client")
            return
        if os.path.exists(torrent_path):
            torrent = Torrent.read(torrent_path)
        else:
            return
        if meta.get('client', None) is None:
            default_torrent_client = self.config['DEFAULT']['default_torrent_client']
        else:
            default_torrent_client = meta['client']
        if meta.get('client', None) == 'none':
            return
        if default_torrent_client == "none":
            return
        client = self.config['TORRENT_CLIENTS'][default_torrent_client]
        torrent_client = client['torrent_client']

        local_path, remote_path = await self.remote_path_map(meta)

        if meta['debug']:
            console.print(f"[bold green]Adding to {torrent_client}")
        if torrent_client.lower() == "rtorrent":
            self.rtorrent(meta['path'], torrent_path, torrent, meta, local_path, remote_path, client)
        elif torrent_client == "qbit":
            await self.qbittorrent(meta['path'], torrent, local_path, remote_path, client, meta['is_disc'], meta['filelist'], meta, tracker)
        elif torrent_client.lower() == "deluge":
            if meta['type'] == "DISC":
                path = os.path.dirname(meta['path'])  # noqa F841
            self.deluge(meta['path'], torrent_path, torrent, local_path, remote_path, client, meta)
        elif torrent_client.lower() == "transmission":
            self.transmission(meta['path'], torrent, local_path, remote_path, client, meta)
        elif torrent_client.lower() == "watch":
            shutil.copy(torrent_path, client['watch_folder'])
        return

    async def find_existing_torrent(self, meta):
        if meta.get('client', None) is None:
            default_torrent_client = self.config['DEFAULT']['default_torrent_client']
        else:
            default_torrent_client = meta['client']
        if meta.get('client', None) == 'none' or default_torrent_client == 'none':
            return None

        client = self.config['TORRENT_CLIENTS'][default_torrent_client]
        torrent_storage_dir = client.get('torrent_storage_dir')
        torrent_client = client.get('torrent_client', '').lower()
        mtv_config = self.config['TRACKERS'].get('MTV')
        if isinstance(mtv_config, dict):
            prefer_small_pieces = mtv_config.get('prefer_mtv_torrent', False)
        else:
            prefer_small_pieces = False
        best_match = None  # Track the best match for fallback if prefer_small_pieces is enabled

        # Iterate through pre-specified hashes
        for hash_key in ['torrenthash', 'ext_torrenthash']:
            hash_value = meta.get(hash_key)
            if hash_value:
                # If no torrent_storage_dir defined, use saved torrent from qbit
                extracted_torrent_dir = os.path.join(meta.get('base_dir', ''), "tmp", meta.get('uuid', ''))

                if torrent_storage_dir:
                    torrent_path = os.path.join(torrent_storage_dir, f"{hash_value}.torrent")
                else:
                    # Fetch from qBittorrent since we don't have torrent_storage_dir
                    console.print(f"[yellow]Fetching .torrent file from qBittorrent for hash: {hash_value}")

                    try:
                        qbt_client = qbittorrentapi.Client(
                            host=client['qbit_url'],
                            port=client['qbit_port'],
                            username=client['qbit_user'],
                            password=client['qbit_pass'],
                            VERIFY_WEBUI_CERTIFICATE=client.get('VERIFY_WEBUI_CERTIFICATE', True)
                        )
                        qbt_client.auth_log_in()

                        # Retrieve the .torrent file
                        torrent_file_content = qbt_client.torrents_export(torrent_hash=hash_value)
                        if not torrent_file_content:
                            console.print(f"[bold red]qBittorrent returned an empty response for hash {hash_value}")
                            continue  # Skip to the next hash

                        # Save the .torrent file
                        os.makedirs(extracted_torrent_dir, exist_ok=True)
                        torrent_path = os.path.join(extracted_torrent_dir, f"{hash_value}.torrent")

                        with open(torrent_path, "wb") as f:
                            f.write(torrent_file_content)

                        console.print(f"[green]Successfully saved .torrent file: {torrent_path}")

                    except qbittorrentapi.APIError as e:
                        console.print(f"[bold red]Failed to fetch .torrent from qBittorrent for hash {hash_value}: {e}")
                        continue

                # Validate the .torrent file
                valid, resolved_path = await self.is_valid_torrent(meta, torrent_path, hash_value, torrent_client, client, print_err=True)

                if valid:
                    console.print(f"[green]Found a valid torrent: [bold yellow]{hash_value}")
                    return resolved_path

        # Search the client if no pre-specified hash matches
        if torrent_client == 'qbit' and client.get('enable_search'):
            try:
                found_hash = await self.search_qbit_for_torrent(meta, client)
            except KeyboardInterrupt:
                console.print("[bold red]Search cancelled by user")
                found_hash = None
            except Exception as e:
                console.print(f"[bold red]Error searching qBittorrent: {e}")
                found_hash = None
            if found_hash:
                extracted_torrent_dir = os.path.join(meta.get('base_dir', ''), "tmp", meta.get('uuid', ''))
                found_torrent_path = os.path.join(torrent_storage_dir, f"{found_hash}.torrent") if torrent_storage_dir else os.path.join(extracted_torrent_dir, f"{found_hash}.torrent")

                valid, resolved_path = await self.is_valid_torrent(
                    meta, found_torrent_path, found_hash, torrent_client, client, print_err=False
                )

                if valid:
                    torrent = Torrent.read(resolved_path)
                    piece_size = torrent.piece_size
                    piece_in_mib = int(piece_size) / 1024 / 1024

                    if not prefer_small_pieces:
                        console.print(f"[green]Found a valid torrent from client search with piece size {piece_in_mib} MiB: [bold yellow]{found_hash}")
                        return resolved_path

                    # Track best match for small pieces
                    if piece_size <= 8388608:
                        console.print(f"[green]Found a valid torrent with preferred piece size from client search: [bold yellow]{found_hash}")
                        return resolved_path

                    if best_match is None or piece_size < best_match['piece_size']:
                        best_match = {'torrenthash': found_hash, 'torrent_path': resolved_path, 'piece_size': piece_size}
                        console.print(f"[yellow]Storing valid torrent from client search as best match: [bold yellow]{found_hash}")

        # Use best match if no preferred torrent found
        if prefer_small_pieces and best_match:
            console.print(f"[yellow]Using best match torrent with hash: [bold yellow]{best_match['torrenthash']}[/bold yellow]")
            return best_match['torrent_path']

        console.print("[bold yellow]No Valid .torrent found")
        return None

    async def is_valid_torrent(self, meta, torrent_path, torrenthash, torrent_client, client, print_err=False):
        valid = False
        wrong_file = False

        # Normalize the torrent hash based on the client
        if torrent_client in ('qbit', 'deluge'):
            torrenthash = torrenthash.lower().strip()
            torrent_path = torrent_path.replace(torrenthash.upper(), torrenthash)
        elif torrent_client == 'rtorrent':
            torrenthash = torrenthash.upper().strip()
            torrent_path = torrent_path.replace(torrenthash.upper(), torrenthash)

        if meta['debug']:
            console.log(f"Torrent path after normalization: {torrent_path}")

        # Check if torrent file exists
        if os.path.exists(torrent_path):
            try:
                torrent = Torrent.read(torrent_path)
            except Exception as e:
                console.print(f'[bold red]Error reading torrent file: {e}')
                return valid, torrent_path

            # Reuse if disc and basename matches or --keep-folder was specified
            if meta.get('is_disc', None) is not None or (meta['keep_folder'] and meta['isdir']):
                torrent_name = torrent.metainfo['info']['name']
                if meta['uuid'] != torrent_name:
                    console.print("Modified file structure, skipping hash")
                    valid = False
                torrent_filepath = os.path.commonpath(torrent.files)
                if os.path.basename(meta['path']) in torrent_filepath:
                    valid = True
                if meta['debug']:
                    console.log(f"Torrent is valid based on disc/basename or keep-folder: {valid}")

            # If one file, check for folder
            elif len(torrent.files) == len(meta['filelist']) == 1:
                if os.path.basename(torrent.files[0]) == os.path.basename(meta['filelist'][0]):
                    if str(torrent.files[0]) == os.path.basename(torrent.files[0]):
                        valid = True
                    else:
                        wrong_file = True
                if meta['debug']:
                    console.log(f"Single file match status: valid={valid}, wrong_file={wrong_file}")

            # Check if number of files matches number of videos
            elif len(torrent.files) == len(meta['filelist']):
                torrent_filepath = os.path.commonpath(torrent.files)
                actual_filepath = os.path.commonpath(meta['filelist'])
                local_path, remote_path = await self.remote_path_map(meta)

                if local_path.lower() in meta['path'].lower() and local_path.lower() != remote_path.lower():
                    actual_filepath = actual_filepath.replace(local_path, remote_path).replace(os.sep, '/')

                if meta['debug']:
                    console.log(f"Torrent_filepath: {torrent_filepath}")
                    console.log(f"Actual_filepath: {actual_filepath}")

                if torrent_filepath in actual_filepath:
                    valid = True
                if meta['debug']:
                    console.log(f"Multiple file match status: valid={valid}")

        else:
            console.print(f'[bold yellow]{torrent_path} was not found')

        # Additional checks if the torrent is valid so far
        if valid:
            if os.path.exists(torrent_path):
                try:
                    reuse_torrent = Torrent.read(torrent_path)
                    piece_size = reuse_torrent.piece_size
                    piece_in_mib = int(piece_size) / 1024 / 1024
                    torrent_storage_dir_valid = torrent_path
                    torrent_file_size_kib = round(os.path.getsize(torrent_storage_dir_valid) / 1024, 2)
                    if meta['debug']:
                        console.log(f"Checking piece size, count and size: pieces={reuse_torrent.pieces}, piece_size={piece_in_mib} MiB, .torrent size={torrent_file_size_kib} KiB")

                    # Piece size and count validations
                    if not meta.get('prefer_small_pieces', False):
                        if reuse_torrent.pieces >= 8000 and reuse_torrent.piece_size < 8388608:
                            console.print("[bold red]Torrent needs to have less than 8000 pieces with a 8 MiB piece size, regenerating")
                            valid = False
                        elif reuse_torrent.pieces >= 5000 and reuse_torrent.piece_size < 4194304:
                            console.print("[bold red]Torrent needs to have less than 5000 pieces with a 4 MiB piece size, regenerating")
                            valid = False
                    elif 'max_piece_size' not in meta and reuse_torrent.pieces >= 12000:
                        console.print("[bold red]Torrent needs to have less than 12000 pieces to be valid, regenerating")
                        valid = False
                    elif reuse_torrent.piece_size < 32768:
                        console.print("[bold red]Piece size too small to reuse")
                        valid = False
                    elif 'max_piece_size' not in meta and torrent_file_size_kib > 250:
                        console.print("[bold red]Torrent file size exceeds 250 KiB")
                        valid = False
                    elif wrong_file:
                        console.print("[bold red]Provided .torrent has files that were not expected")
                        valid = False
                    else:
                        console.print(f"[bold green]REUSING .torrent with infohash: [bold yellow]{torrenthash}")
                except Exception as e:
                    console.print(f'[bold red]Error checking reuse torrent: {e}')
                    valid = False

            if meta['debug']:
                console.log(f"Final validity after piece checks: valid={valid}")
        else:
            console.print("[bold yellow]Unwanted Files/Folders Identified")

        return valid, torrent_path

    async def search_qbit_for_torrent(self, meta, client):
        mtv_config = self.config['TRACKERS'].get('MTV')
        if isinstance(mtv_config, dict):
            prefer_small_pieces = mtv_config.get('prefer_mtv_torrent', False)
        else:
            prefer_small_pieces = False
        console.print("[green]Searching qBittorrent for an existing .torrent")

        torrent_storage_dir = client.get('torrent_storage_dir')
        extracted_torrent_dir = os.path.join(meta.get('base_dir', ''), "tmp", meta.get('uuid', ''))

        if not extracted_torrent_dir or extracted_torrent_dir.strip() == "tmp/":
            console.print("[bold red]Invalid extracted torrent directory path. Check `meta['base_dir']` and `meta['uuid']`.")
            return None

        try:
            qbt_client = qbittorrentapi.Client(
                host=client['qbit_url'],
                port=client['qbit_port'],
                username=client['qbit_user'],
                password=client['qbit_pass'],
                VERIFY_WEBUI_CERTIFICATE=client.get('VERIFY_WEBUI_CERTIFICATE', True)
            )
            qbt_client.auth_log_in()

        except qbittorrentapi.LoginFailed:
            console.print("[bold red]INCORRECT QBIT LOGIN CREDENTIALS")
            return None
        except qbittorrentapi.APIConnectionError:
            console.print("[bold red]APIConnectionError: INCORRECT HOST/PORT")
            return None

        # Ensure extracted torrent directory exists
        os.makedirs(extracted_torrent_dir, exist_ok=True)

        # **Step 1: Find correct torrents using content_path**
        best_match = None
        matching_torrents = []

        for torrent in qbt_client.torrents.info():
            try:
                torrent_path = torrent.name
            except AttributeError:
                continue  # Ignore torrents with missing attributes

            if meta['is_disc'] in ("", None) and len(meta['filelist']) == 1:
                if torrent_path != meta['uuid'] or len(torrent.files) != len(meta['filelist']):
                    continue

            elif meta['uuid'] != torrent_path:
                continue

            if meta['debug']:
                console.print(f"[cyan]Matched Torrent: {torrent.hash}")
                console.print(f"Name: {torrent.name}")
                console.print(f"Save Path: {torrent.save_path}")
                console.print(f"Content Path: {torrent_path}")

            matching_torrents.append({'hash': torrent.hash, 'name': torrent.name})

        if not matching_torrents:
            console.print("[yellow]No matching torrents found in qBittorrent.")
            return None

        console.print(f"[green]Total Matching Torrents: {len(matching_torrents)}")

        # **Step 2: Extract and Save .torrent Files**
        processed_hashes = set()
        best_match = None

        for torrent in matching_torrents:
            try:
                torrent_hash = torrent['hash']
                if torrent_hash in processed_hashes:
                    continue  # Avoid processing duplicates

                processed_hashes.add(torrent_hash)

                # **Use `torrent_storage_dir` if available**
                if torrent_storage_dir:
                    torrent_file_path = os.path.join(torrent_storage_dir, f"{torrent_hash}.torrent")
                    if not os.path.exists(torrent_file_path):
                        console.print(f"[yellow]Torrent file not found in storage directory: {torrent_file_path}")
                        continue
                else:
                    # **Fetch from qBittorrent API if no `torrent_storage_dir`**
                    if meta['debug']:
                        console.print(f"[cyan]Exporting .torrent file for {torrent_hash}")

                    try:
                        torrent_file_content = qbt_client.torrents_export(torrent_hash=torrent_hash)
                        torrent_file_path = os.path.join(extracted_torrent_dir, f"{torrent_hash}.torrent")

                        with open(torrent_file_path, "wb") as f:
                            f.write(torrent_file_content)
                        if meta['debug']:
                            console.print(f"[green]Successfully saved .torrent file: {torrent_file_path}")

                    except qbittorrentapi.APIError as e:
                        console.print(f"[bold red]Failed to export .torrent for {torrent_hash}: {e}")
                        continue  # Skip this torrent if unable to fetch

                # **Validate the .torrent file**
                valid, torrent_path = await self.is_valid_torrent(meta, torrent_file_path, torrent_hash, 'qbit', client, print_err=False)

                if valid:
                    if prefer_small_pieces:
                        # **Track best match based on piece size**
                        torrent_data = Torrent.read(torrent_file_path)
                        piece_size = torrent_data.piece_size
                        if best_match is None or piece_size < best_match['piece_size']:
                            best_match = {
                                'hash': torrent_hash,
                                'torrent_path': torrent_path if torrent_path else torrent_file_path,
                                'piece_size': piece_size
                            }
                            console.print(f"[green]Updated best match: {best_match}")
                    else:
                        # If `prefer_small_pieces` is False, return first valid torrent
                        console.print(f"[green]Returning first valid torrent: {torrent_hash}")
                        return torrent_hash

            except Exception as e:
                console.print(f"[bold red]Unexpected error while handling {torrent_hash}: {e}")

        # **Return the best match if `prefer_small_pieces` is enabled**
        if best_match:
            console.print(f"[green]Using best match torrent with hash: {best_match['hash']}")
            return best_match['hash']

        console.print("[yellow]No valid torrents found.")
        return None

    def rtorrent(self, path, torrent_path, torrent, meta, local_path, remote_path, client):
        rtorrent = xmlrpc.client.Server(client['rtorrent_url'], context=ssl._create_stdlib_context())
        metainfo = bencode.bread(torrent_path)
        try:
            fast_resume = self.add_fast_resume(metainfo, path, torrent)
        except EnvironmentError as exc:
            console.print("[red]Error making fast-resume data (%s)" % (exc,))
            raise

        new_meta = bencode.bencode(fast_resume)
        if new_meta != metainfo:
            fr_file = torrent_path.replace('.torrent', '-resume.torrent')
            console.print("Creating fast resume")
            bencode.bwrite(fast_resume, fr_file)

        isdir = os.path.isdir(path)
        # if meta['type'] == "DISC":
        #     path = os.path.dirname(path)
        # Remote path mount
        modified_fr = False
        if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
            path_dir = os.path.dirname(path)
            path = path.replace(local_path, remote_path)
            path = path.replace(os.sep, '/')
            shutil.copy(fr_file, f"{path_dir}/fr.torrent")
            fr_file = f"{os.path.dirname(path)}/fr.torrent"
            modified_fr = True
        if isdir is False:
            path = os.path.dirname(path)

        console.print("[bold yellow]Adding and starting torrent")
        rtorrent.load.start_verbose('', fr_file, f"d.directory_base.set={path}")
        time.sleep(1)
        # Add labels
        if client.get('rtorrent_label', None) is not None:
            rtorrent.d.custom1.set(torrent.infohash, client['rtorrent_label'])
        if meta.get('rtorrent_label') is not None:
            rtorrent.d.custom1.set(torrent.infohash, meta['rtorrent_label'])

        # Delete modified fr_file location
        if modified_fr:
            os.remove(f"{path_dir}/fr.torrent")
        if meta['debug']:
            console.print(f"[cyan]Path: {path}")
        return

    async def qbittorrent(self, path, torrent, local_path, remote_path, client, is_disc, filelist, meta, tracker):
        if meta.get('keep_folder'):
            path = os.path.dirname(path)
        else:
            isdir = os.path.isdir(path)
            if len(filelist) != 1 or not isdir:
                path = os.path.dirname(path)

        src = meta.get('path')
        if not src:
            console.print("[red]No source path found in meta. Skipping linking.")
            return

        # Determine linking method
        linking_method = client.get('linking', None)  # "symlink", "hardlink", or None
        if meta['debug']:
            console.print("Linking method:", linking_method)
        use_symlink = linking_method == "symlink"
        use_hardlink = linking_method == "hardlink"

        if use_symlink and use_hardlink:
            console.print("[red]Cannot use both hard links and symlinks. Choose one.")
            return

        # Get linked folder for this drive
        linked_folder = client.get('linked_folder', [])
        if meta['debug']:
            console.print(f"Linked folder: {linked_folder}")
        if not isinstance(linked_folder, list):
            linked_folder = [linked_folder]  # Convert to list if single value

        # Determine drive letter (Windows) or root (Linux)
        drive_letter = os.path.splitdrive(src)[0] if platform.system() == "Windows" else "/"

        # Find a linked folder that matches the drive
        link_target = None
        for folder in linked_folder:
            if folder.startswith(drive_letter):
                link_target = folder
                break

        # If using symlinks and no matching drive folder, allow any available one
        if use_symlink and not link_target:
            link_target = linked_folder[0] if linked_folder else None

        # Ensure link_target is valid
        if not link_target:
            console.print("[red]No valid linked folder found. Skipping linking.")
            return

        # Create tracker-specific directory inside linked folder
        tracker_dir = os.path.join(link_target, tracker)
        os.makedirs(tracker_dir, exist_ok=True)

        if meta['debug']:
            console.print(f"[bold yellow]Linking to tracker directory: {tracker_dir}")

        # Extract only the folder or file name from `src`
        src_name = os.path.basename(src.rstrip(os.sep))  # Ensure we get just the name
        dst = os.path.join(tracker_dir, src_name)  # Destination inside linked folder

        # path magic
        if os.path.exists(dst) or os.path.islink(dst):
            console.print(f"[yellow]Skipping linking, path already exists: {dst}")
        else:
            if use_hardlink:
                try:
                    os.link(src, dst)
                    if meta['debug']:
                        console.print(f"[green]Hard link created: {dst} -> {src}")
                except OSError as e:
                    console.print(f"[red]Failed to create hard link: {e}")

            elif use_symlink:
                try:
                    if platform.system() == "Windows":
                        os.symlink(src, dst, target_is_directory=os.path.isdir(src))
                    else:
                        os.symlink(src, dst)

                    if meta['debug']:
                        console.print(f"[green]Symbolic link created: {dst} -> {src}")

                except OSError as e:
                    console.print(f"[red]Failed to create symlink: {e}")

        # Initialize qBittorrent client
        qbt_client = qbittorrentapi.Client(
            host=client['qbit_url'],
            port=client['qbit_port'],
            username=client['qbit_user'],
            password=client['qbit_pass'],
            VERIFY_WEBUI_CERTIFICATE=client.get('VERIFY_WEBUI_CERTIFICATE', True)
        )

        if meta['debug']:
            console.print("[bold yellow]Adding and rechecking torrent")

        try:
            qbt_client.auth_log_in()
        except qbittorrentapi.LoginFailed:
            console.print("[bold red]INCORRECT QBIT LOGIN CREDENTIALS")
            return

        # Apply remote pathing to `tracker_dir` before assigning `save_path`
        if use_symlink or use_hardlink:
            save_path = tracker_dir  # Default to linked directory
            if local_path.lower() in save_path.lower() and local_path.lower() != remote_path.lower():
                save_path = save_path.replace(local_path, remote_path, 1)  # Replace only at the beginning
                save_path = save_path.replace(os.sep, '/')  # Normalize for remote systems
        else:
            save_path = path  # Default to the original path
            if local_path.lower() in save_path.lower() and local_path.lower() != remote_path.lower():
                save_path = save_path.replace(local_path, remote_path, 1)  # Replace only at the beginning
                save_path = save_path.replace(os.sep, '/')  # Normalize for remote systems

        # Ensure qBittorrent save path is formatted correctly
        if not save_path.endswith('/'):
            save_path += '/'

        # Automatic management
        auto_management = False
        am_config = client.get('automatic_management_paths', '')
        if isinstance(am_config, list):
            for each in am_config:
                if os.path.normpath(each).lower() in os.path.normpath(path).lower():
                    auto_management = True
        else:
            if os.path.normpath(am_config).lower() in os.path.normpath(path).lower() and am_config.strip() != "":
                auto_management = True

        qbt_category = client.get("qbit_cat") if not meta.get("qbit_cat") else meta.get('qbit_cat')

        if meta['debug']:
            console.print("client.get('qbit_cat'):", client.get('qbit_cat'))
            console.print("qbt_category:", qbt_category)

        content_layout = client.get('content_layout', 'Original')

        console.print(f"[bold yellow]qBittorrent save path: {save_path}")

        try:
            qbt_client.torrents_add(
                torrent_files=torrent.dump(),
                save_path=save_path,
                use_auto_torrent_management=auto_management,
                is_skip_checking=True,
                content_layout=content_layout,
                category=qbt_category
            )
        except qbittorrentapi.APIConnectionError as e:
            console.print(f"[red]Failed to add torrent: {e}")
            return

        # Wait for torrent to be added
        timeout = 30
        for _ in range(timeout):
            if len(qbt_client.torrents_info(torrent_hashes=torrent.infohash)) > 0:
                break
            await asyncio.sleep(1)
        else:
            console.print("[red]Torrent addition timed out.")
            return

        # Resume and tag torrent
        qbt_client.torrents_resume(torrent.infohash)
        if client.get('qbit_tag'):
            qbt_client.torrents_add_tags(tags=client['qbit_tag'], torrent_hashes=torrent.infohash)
        if meta.get('qbit_tag'):
            qbt_client.torrents_add_tags(tags=meta['qbit_tag'], torrent_hashes=torrent.infohash)

        if meta['debug']:
            console.print(f"Added to: {save_path}")

    def deluge(self, path, torrent_path, torrent, local_path, remote_path, client, meta):
        client = DelugeRPCClient(client['deluge_url'], int(client['deluge_port']), client['deluge_user'], client['deluge_pass'])
        # client = LocalDelugeRPCClient()
        client.connect()
        if client.connected is True:
            console.print("Connected to Deluge")
            isdir = os.path.isdir(path)  # noqa F841
            # Remote path mount
            if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
                path = path.replace(local_path, remote_path)
                path = path.replace(os.sep, '/')

            path = os.path.dirname(path)

            client.call('core.add_torrent_file', torrent_path, base64.b64encode(torrent.dump()), {'download_location': path, 'seed_mode': True})
            if meta['debug']:
                console.print(f"[cyan]Path: {path}")
        else:
            console.print("[bold red]Unable to connect to deluge")

    def transmission(self, path, torrent, local_path, remote_path, client, meta):
        try:
            tr_client = transmission_rpc.Client(
                protocol=client['transmission_protocol'],
                host=client['transmission_host'],
                port=int(client['transmission_port']),
                username=client['transmission_username'],
                password=client['transmission_password'],
                path=client.get('transmission_path', "/transmission/rpc")
            )
        except Exception:
            console.print("[bold red]Unable to connect to transmission")
            return

        console.print("Connected to Transmission")
        # Remote path mount
        if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
            path = path.replace(local_path, remote_path)
            path = path.replace(os.sep, '/')

        path = os.path.dirname(path)

        if meta.get('transmission_label') is not None:
            label = [meta['transmission_label']]
        elif client.get('transmission_label', None) is not None:
            label = [client['transmission_label']]
        else:
            label = None

        tr_client.add_torrent(
            torrent=torrent.dump(),
            download_dir=path,
            labels=label
        )

        if meta['debug']:
            console.print(f"[cyan]Path: {path}")

    def add_fast_resume(self, metainfo, datapath, torrent):
        """ Add fast resume data to a metafile dict.
        """
        # Get list of files
        files = metainfo["info"].get("files", None)
        single = files is None
        if single:
            if os.path.isdir(datapath):
                datapath = os.path.join(datapath, metainfo["info"]["name"])
            files = [Bunch(
                path=[os.path.abspath(datapath)],
                length=metainfo["info"]["length"],
            )]

        # Prepare resume data
        resume = metainfo.setdefault("libtorrent_resume", {})
        resume["bitfield"] = len(metainfo["info"]["pieces"]) // 20
        resume["files"] = []
        piece_length = metainfo["info"]["piece length"]
        offset = 0

        for fileinfo in files:
            # Get the path into the filesystem
            filepath = os.sep.join(fileinfo["path"])
            if not single:
                filepath = os.path.join(datapath, filepath.strip(os.sep))

            # Check file size
            if os.path.getsize(filepath) != fileinfo["length"]:
                raise OSError(errno.EINVAL, "File size mismatch for %r [is %d, expected %d]" % (
                    filepath, os.path.getsize(filepath), fileinfo["length"],
                ))

            # Add resume data for this file
            resume["files"].append(dict(
                priority=1,
                mtime=int(os.path.getmtime(filepath)),
                completed=(
                    (offset + fileinfo["length"] + piece_length - 1) // piece_length -
                    offset // piece_length
                ),
            ))
            offset += fileinfo["length"]

        return metainfo

    async def remote_path_map(self, meta):
        if meta.get('client', None) is None:
            torrent_client = self.config['DEFAULT']['default_torrent_client']
        else:
            torrent_client = meta['client']
        local_paths = self.config['TORRENT_CLIENTS'][torrent_client].get('local_path', ['/LocalPath'])
        remote_paths = self.config['TORRENT_CLIENTS'][torrent_client].get('remote_path', ['/RemotePath'])

        if not isinstance(local_paths, list):
            local_paths = [local_paths]
        if not isinstance(remote_paths, list):
            remote_paths = [remote_paths]

        list_local_path = local_paths[0]
        list_remote_path = remote_paths[0]

        for i in range(len(local_paths)):
            if os.path.normpath(local_paths[i]).lower() in meta['path'].lower():
                list_local_path = local_paths[i]
                list_remote_path = remote_paths[i]
                break

        local_path = os.path.normpath(list_local_path)
        remote_path = os.path.normpath(list_remote_path)
        if local_path.endswith(os.sep):
            remote_path = remote_path + os.sep

        return local_path, remote_path

    async def get_ptp_from_hash(self, meta):
        default_torrent_client = self.config['DEFAULT']['default_torrent_client']
        client = self.config['TORRENT_CLIENTS'][default_torrent_client]
        qbt_client = qbittorrentapi.Client(
            host=client['qbit_url'],
            port=client['qbit_port'],
            username=client['qbit_user'],
            password=client['qbit_pass'],
            VERIFY_WEBUI_CERTIFICATE=client.get('VERIFY_WEBUI_CERTIFICATE', True)
        )

        try:
            qbt_client.auth_log_in()
        except qbittorrentapi.LoginFailed as e:
            console.print(f"[bold red]Login failed while trying to get info hash: {e}")
            exit(1)

        info_hash_v1 = meta.get('infohash')
        torrents = qbt_client.torrents_info()
        found = False

        extracted_torrent_dir = os.path.join(meta.get('base_dir', ''), "tmp", meta.get('uuid', ''))
        os.makedirs(extracted_torrent_dir, exist_ok=True)

        for torrent in torrents:
            if torrent.get('infohash_v1') == info_hash_v1:
                comment = torrent.get('comment', "")
                match = None

                if "https://passthepopcorn.me" in comment:
                    match = re.search(r'torrentid=(\d+)', comment)
                    if match:
                        meta['ptp'] = match.group(1)
                elif "https://aither.cc" in comment:
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        meta['aither'] = match.group(1)
                elif "https://lst.gg" in comment:
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        meta['lst'] = match.group(1)
                elif "https://onlyencodes.cc" in comment:
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        meta['oe'] = match.group(1)
                elif "https://blutopia.cc" in comment:
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        meta['blu'] = match.group(1)
                elif "https://hdbits.org" in comment:
                    match = re.search(r'id=(\d+)', comment)
                    if match:
                        meta['hdb'] = match.group(1)
                elif "https://broadcasthe.net" in comment:
                    match = re.search(r'id=(\d+)', comment)
                    if match:
                        meta['btn'] = match.group(1)
                elif "https://beyond-hd.me" in comment:
                    meta['bhd'] = info_hash_v1
                elif "https://jptv.club" in comment:
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        meta['jptv'] = match.group(1)

                if match:
                    console.print(f"[bold cyan]meta updated with tracker ID: {match.group(1)}")

                torrent_storage_dir = client.get('torrent_storage_dir')
                if not torrent_storage_dir:
                    # Export .torrent file
                    torrent_hash = torrent.get('infohash_v1')
                    if meta.get('debug', False):
                        console.print(f"[cyan]Exporting .torrent file for hash: {torrent_hash}")

                    try:
                        torrent_file_content = qbt_client.torrents_export(torrent_hash=torrent_hash)
                        torrent_file_path = os.path.join(extracted_torrent_dir, f"{torrent_hash}.torrent")

                        with open(torrent_file_path, "wb") as f:
                            f.write(torrent_file_content)

                        # Validate the .torrent file before saving as BASE.torrent
                        valid, torrent_path = await self.is_valid_torrent(meta, torrent_file_path, torrent_hash, 'qbit', client, print_err=False)
                        if not valid:
                            console.print(f"[bold red]Validation failed for {torrent_file_path}")
                            os.remove(torrent_file_path)  # Remove invalid file
                        else:
                            base_torrent_file_path = os.path.join(extracted_torrent_dir, "BASE.torrent")
                            with open(base_torrent_file_path, "wb") as f:
                                f.write(torrent_file_content)
                            if meta.get('debug', False):
                                console.print(f"[green]Successfully saved .torrent file: {torrent_file_path}")

                    except qbittorrentapi.APIError as e:
                        console.print(f"[bold red]Failed to export .torrent for {torrent_hash}: {e}")

                found = True
                break

        if not found:
            console.print("[bold red]Torrent with the specified infohash_v1 not found.")

        return meta
