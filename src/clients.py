# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiohttp
import asyncio
import base64
import bencode
import collections
import defusedxml.xmlrpc
import errno
import os
import platform
import qbittorrentapi
import re
import shutil
import ssl
import subprocess
import time
import traceback
import transmission_rpc
import urllib.parse
import xmlrpc.client  # nosec B411 - Secured with defusedxml.xmlrpc.monkey_patch() below
from typing import Any, Dict, DefaultDict, Tuple, Union, Optional, List, Callable, Awaitable

from cogs.redaction import redact_private_info
from deluge_client import DelugeRPCClient
from src.console import console
from src.torrentcreate import TorrentCreator
from torf import Torrent

# Secure XML-RPC client using defusedxml to prevent XML attacks
defusedxml.xmlrpc.monkey_patch()

# These have to be global variables to be shared across all instances since a new instance is made every time
qbittorrent_cached_clients: Dict[Tuple[str, int, str], qbittorrentapi.Client] = {}  # Cache for qbittorrent clients that have been successfully logged into
qbittorrent_locks: DefaultDict[Tuple[str, int, str], asyncio.Lock] = collections.defaultdict(asyncio.Lock)  # Locks for qbittorrent clients to prevent concurrent logins


class Clients():
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def create_ssl_context_for_client(self, client_config: Dict[str, Any]) -> ssl.SSLContext:
        """Create SSL context for qBittorrent client based on VERIFY_WEBUI_CERTIFICATE setting."""
        ssl_context = ssl.create_default_context()
        if not client_config.get('VERIFY_WEBUI_CERTIFICATE', True):
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    async def retry_qbt_operation(self, operation_func: Callable[[], Awaitable[Any]], operation_name: str, max_retries: int = 2, initial_timeout: float = 10.0) -> Any:
        for attempt in range(max_retries + 1):
            timeout = initial_timeout * (2 ** attempt)  # Exponential backoff: 10s, 20s, 40s
            try:
                result = await asyncio.wait_for(operation_func(), timeout=timeout)
                if attempt > 0:
                    console.print(f"[green]{operation_name} succeeded on attempt {attempt + 1}")
                return result
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    console.print(f"[yellow]{operation_name} timed out after {timeout}s (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                    await asyncio.sleep(1)  # Brief pause before retry
                else:
                    console.print(f"[bold red]{operation_name} failed after {max_retries + 1} attempts (final timeout: {timeout}s)")
                    raise  # Re-raise the TimeoutError so caller can handle it

    async def init_qbittorrent_client(self, client: Dict[str, Any]) -> Optional[qbittorrentapi.Client]:
        # Creates and logs into a qbittorrent client, with caching to avoid redundant logins
        # If login fails, returns None
        client_key = (client['qbit_url'], client['qbit_port'], client['qbit_user'])
        async with qbittorrent_locks[client_key]:
            # We lock to further prevent concurrent logins for the same client. If two clients try to init at the same time, if the first one succeeds, the second one can use the cached client.
            potential_cached_client = qbittorrent_cached_clients.get(client_key)
            if potential_cached_client is not None:
                return potential_cached_client

            qbt_client = qbittorrentapi.Client(
                host=client['qbit_url'],
                port=client['qbit_port'],
                username=client['qbit_user'],
                password=client['qbit_pass'],
                VERIFY_WEBUI_CERTIFICATE=client.get('VERIFY_WEBUI_CERTIFICATE', True)
            )
            try:
                await self.retry_qbt_operation(
                    lambda: asyncio.to_thread(qbt_client.auth_log_in),
                    "qBittorrent login"
                )
            except asyncio.TimeoutError:
                console.print("[bold red]Connection to qBittorrent timed out after retries")
                return None
            except qbittorrentapi.LoginFailed:
                console.print("[bold red]Failed to login to qBittorrent - incorrect credentials")
                return None
            except qbittorrentapi.APIConnectionError:
                console.print("[bold red]Failed to connect to qBittorrent - check host/port")
                return None
            else:
                qbittorrent_cached_clients[client_key] = qbt_client
                return qbt_client

    async def add_to_client(self, meta: Dict[str, Any], tracker: str, cross: bool = False) -> None:
        if cross:
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}_cross].torrent"
        elif meta['debug']:
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}_DEBUG].torrent"
        else:
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}].torrent"
        if meta.get('no_seed', False) is True:
            console.print("[bold red]--no-seed was passed, so the torrent will not be added to the client")
            console.print("[bold yellow]Add torrent manually to the client")
            return
        if os.path.exists(torrent_path):
            torrent = Torrent.read(torrent_path)
        else:
            console.print(f"[bold red]Torrent file {torrent_path} does not exist, cannot add to client")
            return

        inject_clients = []
        if meta.get('client') and meta.get('client') != 'none':
            inject_clients = [meta['client']]
            if meta['debug']:
                console.print(f"[cyan]DEBUG: Using client from meta: {inject_clients}[/cyan]")
        elif meta.get('client') == 'none':
            if meta['debug']:
                console.print("[cyan]DEBUG: meta client is 'none', skipping adding to client[/cyan]")
            return
        else:
            try:
                inject_clients_config = self.config['DEFAULT'].get('injecting_client_list')
                if isinstance(inject_clients_config, str) and inject_clients_config.strip():
                    inject_clients = [inject_clients_config]
                    if meta['debug']:
                        console.print(f"[cyan]DEBUG: Converted injecting_client_list string to list: {inject_clients}[/cyan]")
                elif isinstance(inject_clients_config, list):
                    # Filter out empty strings and whitespace-only strings
                    inject_clients = [c for c in inject_clients_config if c and str(c).strip()]
                    if meta['debug']:
                        console.print(f"[cyan]DEBUG: Using injecting_client_list from config: {inject_clients}[/cyan]")
                else:
                    inject_clients = []
            except Exception as e:
                if meta['debug']:
                    console.print(f"[cyan]DEBUG: Error reading injecting_client_list from config: {e}[/cyan]")

            if not inject_clients:
                default_client = self.config['DEFAULT'].get('default_torrent_client')
                if default_client and default_client != 'none':
                    if meta['debug']:
                        console.print(f"[cyan]DEBUG: Falling back to default_torrent_client: {default_client}[/cyan]")
                    inject_clients = [default_client]

        if not inject_clients:
            if meta['debug']:
                console.print("[cyan]DEBUG: No clients configured for injecting[/cyan]")
            return

        if meta['debug']:
            console.print(f"[cyan]DEBUG: Clients to inject into: {inject_clients}[/cyan]")

        for client_name in inject_clients:
            if client_name == "none" or not client_name:
                continue

            if client_name not in self.config['TORRENT_CLIENTS']:
                console.print(f"[bold red]Torrent client '{client_name}' not found in config.")
                continue

            client = self.config['TORRENT_CLIENTS'][client_name]
            torrent_client = client['torrent_client']

            # Must pass client_name to remote_path_map
            local_path, remote_path = await self.remote_path_map(meta, client_name)

            if meta['debug']:
                console.print(f"[bold green]Adding to {client_name} ({torrent_client})")

            try:
                if torrent_client.lower() == "rtorrent":
                    self.rtorrent(meta['path'], torrent_path, torrent, meta, local_path, remote_path, client, tracker)
                elif torrent_client == "qbit":
                    await self.qbittorrent(meta['path'], torrent, local_path, remote_path, client, meta['is_disc'], meta['filelist'], meta, tracker, cross)
                elif torrent_client.lower() == "deluge":
                    if meta['type'] == "DISC":
                        path = os.path.dirname(meta['path'])  # noqa F841
                    self.deluge(meta['path'], torrent_path, torrent, local_path, remote_path, client, meta)
                elif torrent_client.lower() == "transmission":
                    self.transmission(meta['path'], torrent, local_path, remote_path, client, meta)
                elif torrent_client.lower() == "watch":
                    shutil.copy(torrent_path, client['watch_folder'])
            except Exception as e:
                console.print(f"[bold red]Failed to add torrent to {client_name}: {e}")
        return

    async def find_existing_torrent(self, meta: Dict[str, Any]) -> Optional[str]:
        # Determine piece size preferences
        mtv_config = self.config['TRACKERS'].get('MTV')
        piece_limit = self.config['DEFAULT'].get('prefer_max_16_torrent', False)
        mtv_torrent = False
        if isinstance(mtv_config, dict):
            mtv_torrent = mtv_config.get('prefer_mtv_torrent', False)
            prefer_small_pieces = mtv_torrent
        else:
            if piece_limit:
                prefer_small_pieces = True
            else:
                prefer_small_pieces = False
        best_match = None  # Track the best match for fallback if prefer_small_pieces is enabled

        default_torrent_client = self.config['DEFAULT']['default_torrent_client']

        if meta.get('client') and meta['client'] != 'none':
            clients_to_search = [meta['client']]
            if meta['debug']:
                console.print(f"[cyan]DEBUG: Using client from meta: {clients_to_search}[/cyan]")
        else:
            searching_list = self.config['DEFAULT'].get('searching_client_list', [])

            if isinstance(searching_list, list) and len(searching_list) > 0:
                clients_to_search = [c for c in searching_list if c and c != 'none']
                if meta['debug']:
                    console.print(f"[cyan]DEBUG: Using searching_client_list from config: {clients_to_search}[/cyan]")
            else:
                clients_to_search = []

            if not clients_to_search:
                if default_torrent_client and default_torrent_client != 'none':
                    clients_to_search = [default_torrent_client]
                    if meta['debug']:
                        console.print(f"[cyan]DEBUG: Falling back to default_torrent_client: {default_torrent_client}[/cyan]")
                else:
                    console.print("[yellow]No clients configured for searching...[/yellow]")
                    return None

        for client_name in clients_to_search:
            if client_name not in self.config['TORRENT_CLIENTS']:
                console.print(f"[yellow]Client '{client_name}' not found in TORRENT_CLIENTS config, skipping...")
                continue

            result = await self._search_single_client_for_torrent(
                meta, client_name, prefer_small_pieces, mtv_torrent, piece_limit, best_match
            )

            if result:
                if isinstance(result, dict):
                    # Got a valid torrent but not ideal piece size
                    best_match = result
                    # If prefer_small_pieces is False, we don't care about piece size optimization
                    # so stop searching after finding the first valid torrent
                    if not prefer_small_pieces:
                        console.print(f"[green]Found valid torrent in client '{client_name}', stopping search[/green]")
                        torrent_path = best_match.get('torrent_path')
                        return torrent_path if isinstance(torrent_path, str) else None
                else:
                    # Got a path - this means we found a torrent with ideal piece size
                    console.print(f"[green]Found valid torrent with preferred piece size in client '{client_name}', stopping search[/green]")
                    return result if isinstance(result, str) else None

        if prefer_small_pieces and best_match:
            console.print(f"[yellow]Using best match torrent with hash: [bold yellow]{best_match['torrenthash']}[/bold yellow]")
            torrent_path = best_match.get('torrent_path')
            return torrent_path if isinstance(torrent_path, str) else None

        console.print("[bold yellow]No Valid .torrent found")
        return None

    async def _search_single_client_for_torrent(self, meta: Dict[str, Any], client_name: str, prefer_small_pieces: bool, mtv_torrent: bool, piece_limit: bool, best_match: Optional[Dict[str, Any]]) -> Union[Dict[str, Any], str, None]:
        """Search a single client for an existing torrent by hash or via API search (qbit only)."""

        client = self.config['TORRENT_CLIENTS'][client_name]
        torrent_client = client.get('torrent_client', '').lower()
        torrent_storage_dir = client.get('torrent_storage_dir')
        qbt_client: Optional[qbittorrentapi.Client] = None
        proxy_url: Optional[str] = None

        # Iterate through pre-specified hashes
        for hash_key in ['torrenthash', 'ext_torrenthash']:
            hash_value = meta.get(hash_key)
            if hash_value:
                hash_value_str = str(hash_value)
                # If no torrent_storage_dir defined, use saved torrent from qbit
                extracted_torrent_dir = os.path.join(meta.get('base_dir', ''), "tmp", meta.get('uuid', ''))

                if torrent_storage_dir:
                    torrent_path = os.path.join(torrent_storage_dir, f"{hash_value_str}.torrent")
                else:
                    if torrent_client != 'qbit':
                        return None

                    try:
                        proxy_url = client.get('qui_proxy_url')
                        if proxy_url:
                            qbt_proxy_url = proxy_url.rstrip('/')
                            async with aiohttp.ClientSession() as session:
                                try:
                                    async with session.post(f"{qbt_proxy_url}/api/v2/torrents/export",
                                                            data={'hash': hash_value_str}) as response:
                                        if response.status == 200:
                                            torrent_file_content = await response.read()
                                        else:
                                            console.print(f"[red]Failed to export torrent via proxy: {response.status}")
                                            continue
                                except Exception as e:
                                    console.print(f"[red]Error exporting torrent via proxy: {e}")
                                    continue
                        else:
                            potential_qbt_client = await self.init_qbittorrent_client(client)
                            if not potential_qbt_client:
                                continue
                            else:
                                qbt_client = potential_qbt_client

                            if qbt_client is None:
                                console.print("[bold red]qBittorrent client not initialized")
                                continue
                            qbt_client_local: qbittorrentapi.Client = qbt_client

                            try:
                                torrent_file_content = await self.retry_qbt_operation(
                                    lambda: asyncio.to_thread(qbt_client_local.torrents_export, torrent_hash=hash_value_str),
                                    f"Export torrent {hash_value_str}"
                                )
                            except (asyncio.TimeoutError, qbittorrentapi.APIError):
                                continue
                        if not torrent_file_content:
                            console.print(f"[bold red]qBittorrent returned an empty response for hash {hash_value_str}")
                            continue  # Skip to the next hash

                        # Save the .torrent file
                        os.makedirs(extracted_torrent_dir, exist_ok=True)
                        torrent_path = os.path.join(extracted_torrent_dir, f"{hash_value_str}.torrent")

                        with open(torrent_path, "wb") as f:
                            f.write(torrent_file_content)

                        console.print(f"[green]Successfully saved .torrent file: {torrent_path}")

                    except qbittorrentapi.APIError as e:
                        console.print(f"[bold red]Failed to fetch .torrent from qBittorrent for hash {hash_value_str}: {e}")
                        continue

                # Validate the .torrent file
                valid, resolved_path = await self.is_valid_torrent(meta, torrent_path, hash_value_str, torrent_client, client)

                if valid:
                    return resolved_path

        # Search the client if no pre-specified hash matches
        if torrent_client == 'qbit' and client.get('enable_search'):
            try:
                qbt_session: Optional[aiohttp.ClientSession] = None

                proxy_url = client.get('qui_proxy_url')

                if proxy_url:
                    ssl_context = self.create_ssl_context_for_client(client)
                    qbt_session = aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=10),
                        connector=aiohttp.TCPConnector(ssl=ssl_context)
                    )
                else:
                    qbt_client = await self.init_qbittorrent_client(client)

                found_hash = await self.search_qbit_for_torrent(meta, client, qbt_client, qbt_session, proxy_url)

                # Clean up session if we created one
                if qbt_session:
                    await qbt_session.close()

            except KeyboardInterrupt:
                console.print("[bold red]Search cancelled by user")
                found_hash = None
                if qbt_session:
                    await qbt_session.close()
            except asyncio.TimeoutError:
                if qbt_session:
                    await qbt_session.close()
                raise
            except Exception as e:
                console.print(f"[bold red]Error searching qBittorrent: {e}")
                found_hash = None
                if qbt_session:
                    await qbt_session.close()
            if found_hash:
                extracted_torrent_dir = os.path.join(meta.get('base_dir', ''), "tmp", meta.get('uuid', ''))

                if torrent_storage_dir:
                    found_torrent_path = os.path.join(torrent_storage_dir, f"{found_hash}.torrent")
                else:
                    found_torrent_path = os.path.join(extracted_torrent_dir, f"{found_hash}.torrent")

                    if not os.path.exists(found_torrent_path):
                        console.print(f"[yellow]Exporting .torrent file from qBittorrent for hash: {found_hash}[/yellow]")

                        try:
                            proxy_url = client.get('qui_proxy_url')
                            if proxy_url:
                                qbt_proxy_url = proxy_url.rstrip('/')
                                async with aiohttp.ClientSession() as session:
                                    try:
                                        async with session.post(f"{qbt_proxy_url}/api/v2/torrents/export",
                                                                data={'hash': found_hash}) as response:
                                            if response.status == 200:
                                                torrent_file_content = await response.read()
                                            else:
                                                console.print(f"[red]Failed to export torrent via proxy: {response.status}")
                                                found_hash = None
                                    except Exception as e:
                                        console.print(f"[red]Error exporting torrent via proxy: {e}")
                                        found_hash = None
                            else:
                                # Reuse or create qbt_client if needed
                                if qbt_client is None:
                                    qbt_client = qbittorrentapi.Client(
                                        host=client['qbit_url'],
                                        port=client['qbit_port'],
                                        username=client['qbit_user'],
                                        password=client['qbit_pass'],
                                        VERIFY_WEBUI_CERTIFICATE=client.get('VERIFY_WEBUI_CERTIFICATE', True)
                                    )
                                    try:
                                        await self.retry_qbt_operation(
                                            lambda: asyncio.to_thread(qbt_client.auth_log_in),
                                            "qBittorrent login"
                                        )
                                    except (asyncio.TimeoutError, qbittorrentapi.LoginFailed, qbittorrentapi.APIConnectionError) as e:
                                        console.print(f"[bold red]Failed to connect to qBittorrent for export: {e}")
                                        found_hash = None

                                if found_hash:  # Only proceed if we still have a hash
                                    try:
                                        torrent_file_content = await self.retry_qbt_operation(
                                            lambda: asyncio.to_thread(qbt_client.torrents_export, torrent_hash=found_hash),
                                            f"Export torrent {found_hash}"
                                        )
                                    except (asyncio.TimeoutError, qbittorrentapi.APIError) as e:
                                        console.print(f"[red]Error exporting torrent: {e}")

                            if found_hash:  # Only proceed if export succeeded
                                if not torrent_file_content:
                                    found_hash = None
                                else:
                                    os.makedirs(extracted_torrent_dir, exist_ok=True)
                                    with open(found_torrent_path, "wb") as f:
                                        f.write(torrent_file_content)
                                    console.print(f"[green]Successfully saved .torrent file: {found_torrent_path}")
                        except Exception as e:
                            console.print(f"[bold red]Unexpected error fetching .torrent from qBittorrent: {e}")
                            console.print("[cyan]DEBUG: Skipping found_hash due to unexpected error[/cyan]")
                            found_hash = None
                    else:
                        console.print(f"[cyan]DEBUG: .torrent file already exists at {found_torrent_path}[/cyan]")

                # Only validate if we still have a hash (export succeeded or file already existed)
                if found_hash:
                    valid, resolved_path = await self.is_valid_torrent(
                        meta, found_torrent_path, found_hash, torrent_client, client
                    )
                else:
                    valid = False
                    console.print("[cyan]DEBUG: Skipping validation because found_hash is None[/cyan]")

                if valid:
                    torrent = Torrent.read(resolved_path)
                    piece_size = torrent.piece_size
                    piece_in_mib = int(piece_size) / 1024 / 1024

                    if not prefer_small_pieces:
                        console.print(f"[green]Found a valid torrent from client search with piece size {piece_in_mib} MiB: [bold yellow]{found_hash}")
                        return resolved_path

                    # Track best match for small pieces
                    if piece_size <= 8388608 and mtv_torrent:
                        console.print(f"[green]Found a valid torrent with preferred piece size from client search: [bold yellow]{found_hash}")
                        return resolved_path

                    if piece_size < 16777216 and piece_limit:  # 16 MiB
                        console.print(f"[green]Found a valid torrent with piece size under 16 MiB from client search: [bold yellow]{found_hash}")
                        return resolved_path

                    if best_match is None or piece_size < best_match['piece_size']:
                        best_match = {'torrenthash': found_hash, 'torrent_path': resolved_path, 'piece_size': piece_size}
                        console.print(f"[yellow]Storing valid torrent from client search as best match: [bold yellow]{found_hash}")

        return best_match

    async def is_valid_torrent(self, meta: Dict[str, Any], torrent_path: str, torrenthash: str, torrent_client: str, client: Dict[str, Any]) -> Tuple[bool, str]:
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
                if meta['uuid'] != torrent_name and meta['debug']:
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
                local_path, remote_path = await self.remote_path_map(meta, client)

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
                    max_piece_size = meta.get('max_piece_size')
                    if reuse_torrent.pieces >= 5000 and reuse_torrent.piece_size < 4294304 and (max_piece_size is None or max_piece_size >= 4):
                        if meta['debug']:
                            console.print("[bold red]Torrent needs to have less than 5000 pieces with a 4 MiB piece size")
                        valid = False
                    elif reuse_torrent.pieces >= 8000 and reuse_torrent.piece_size < 8488608 and (max_piece_size is None or max_piece_size >= 8) and not meta.get('prefer_small_pieces', False):
                        if meta['debug']:
                            console.print("[bold red]Torrent needs to have less than 8000 pieces with a 8 MiB piece size")
                        valid = False
                    elif 'max_piece_size' not in meta and reuse_torrent.pieces >= 12000:
                        if meta['debug']:
                            console.print("[bold red]Torrent needs to have less than 12000 pieces to be valid")
                        valid = False
                    elif reuse_torrent.piece_size < 32768:
                        if meta['debug']:
                            console.print("[bold red]Piece size too small to reuse")
                        valid = False
                    elif 'max_piece_size' not in meta and torrent_file_size_kib > 250:
                        if meta['debug']:
                            console.log("[bold red]Torrent file size exceeds 250 KiB")
                        valid = False
                    elif wrong_file:
                        if meta['debug']:
                            console.log("[bold red]Provided .torrent has files that were not expected")
                        valid = False
                    else:
                        if meta['debug']:
                            console.log(f"[bold green]REUSING .torrent with infohash: [bold yellow]{torrenthash}")
                except Exception as e:
                    console.print(f'[bold red]Error checking reuse torrent: {e}')
                    valid = False

            if meta['debug']:
                console.log(f"Final validity after piece checks: valid={valid}")
        else:
            if meta['debug']:
                console.log("[bold yellow]Unwanted Files/Folders Identified")

        return valid, torrent_path

    async def search_qbit_for_torrent(self, meta: Dict[str, Any], client: Dict[str, Any], qbt_client: Optional[qbittorrentapi.Client] = None, qbt_session: Optional[aiohttp.ClientSession] = None, proxy_url: Optional[str] = None) -> Optional[str]:
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
            if qbt_client is None and proxy_url is None:
                potential_qbt_client = await self.init_qbittorrent_client(client)
                if potential_qbt_client is None:
                    return None
                qbt_client = potential_qbt_client
            elif proxy_url and qbt_session is None:
                ssl_context = self.create_ssl_context_for_client(client)
                qbt_session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10),
                    connector=aiohttp.TCPConnector(ssl=ssl_context)
                )

        except qbittorrentapi.LoginFailed:
            console.print("[bold red]INCORRECT QBIT LOGIN CREDENTIALS")
            return None
        except qbittorrentapi.APIConnectionError:
            console.print("[bold red]APIConnectionError: INCORRECT HOST/PORT")
            return None

        if proxy_url and qbt_session is None:
            console.print("[bold red]Proxy URL configured but session was not created")
            return None
        if not proxy_url and qbt_client is None:
            console.print("[bold red]qBittorrent client is not initialized")
            return None

        # Ensure extracted torrent directory exists
        os.makedirs(extracted_torrent_dir, exist_ok=True)

        # **Step 1: Find correct torrents using content_path**
        best_match = None
        matching_torrents = []

        try:
            if proxy_url:
                if qbt_session is None:
                    console.print("[bold red]Proxy session not initialized")
                    return None
                qbt_proxy_url = proxy_url.rstrip('/')
                async with qbt_session.get(f"{qbt_proxy_url}/api/v2/torrents/info") as response:
                    if response.status == 200:
                        torrents_data = await response.json()

                        class MockTorrent:
                            def __init__(self, data: Dict[str, Any]):
                                for key, value in data.items():
                                    setattr(self, key, value)
                                # For proxy API, we need to fetch files separately or use num_files from torrents/info
                                # The torrents/info endpoint doesn't include files array but has 'num_files' field
                                if not hasattr(self, 'tracker'):
                                    self.tracker = ''
                                if not hasattr(self, 'comment'):
                                    self.comment = ''
                                # Create a files list based on num_files to make len() work
                                if hasattr(self, 'num_files'):
                                    self.files = [None] * self.num_files  # Dummy list with correct length
                                elif not hasattr(self, 'files'):
                                    self.files = []

                            def __getattr__(self, name: str) -> Any:
                                return None
                        torrents = [MockTorrent(torrent) for torrent in torrents_data]
                    else:
                        console.print(f"[bold red]Failed to get torrents list via proxy: {response.status}")
                        return None
            else:
                if qbt_client is None:
                    console.print("[bold red]qBittorrent client not initialized")
                    return None
                torrents = await self.retry_qbt_operation(
                    lambda: asyncio.to_thread(qbt_client.torrents_info),
                    "Get torrents list",
                    initial_timeout=14.0
                )
        except asyncio.TimeoutError:
            console.print("[bold red]Getting torrents list timed out after retries")
            return None
        except Exception as e:
            console.print(f"[bold red]Error getting torrents list: {e}")
            return None

        torrent_count = 0
        for torrent in torrents:
            try:
                torrent_path = torrent.name
                torrent_count += 1
            except AttributeError:
                continue  # Ignore torrents with missing attributes

            if meta['uuid'].lower() != torrent_path.lower():
                continue

            if meta['debug']:
                console.print(f"[cyan]Matched Torrent: {torrent.hash}")
                console.print(f"Name: {torrent.name}")
                console.print(f"Save Path: {torrent.save_path}")
                console.print(f"Content Path: {torrent_path}")

            matching_torrents.append({'hash': torrent.hash, 'name': torrent.name})

        console.print(f"[cyan]DEBUG: Checked {torrent_count} total torrents in qBittorrent[/cyan]")
        if not matching_torrents:
            console.print("[yellow]No matching torrents found in qBittorrent.")
            return None

        console.print(f"[green]Total Matching Torrents: {len(matching_torrents)}")

        # **Step 2: Extract and Save .torrent Files**
        processed_hashes = set()
        best_match = None
        torrent_hash = None
        for matching_torrent in matching_torrents:
            try:
                torrent_hash = str(matching_torrent['hash'])
                if torrent_hash in processed_hashes:
                    continue  # Avoid processing duplicates

                processed_hashes.add(torrent_hash)

            except Exception as e:
                console.print(f"[bold red]Unexpected error while handling torrent{f' {torrent_hash}' if torrent_hash else ''}: {e}")
                torrent_hash = None

            if not torrent_hash:
                continue

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

                torrent_file_content = None
                if proxy_url:
                    if qbt_session is None:
                        console.print("[bold red]Proxy session not initialized")
                        continue
                    qbt_proxy_url = proxy_url.rstrip('/')
                    try:
                        async with qbt_session.post(f"{qbt_proxy_url}/api/v2/torrents/export",
                                                    data={'hash': torrent_hash}) as response:
                            if response.status == 200:
                                torrent_file_content = await response.read()
                            else:
                                console.print(f"[red]Failed to export torrent via proxy: {response.status}")
                    except Exception as e:
                        console.print(f"[red]Error exporting torrent via proxy: {e}")
                else:
                    if qbt_client is None:
                        console.print("[bold red]qBittorrent client not initialized")
                        continue
                    torrent_file_content = await self.retry_qbt_operation(
                        lambda: asyncio.to_thread(qbt_client.torrents_export, torrent_hash=torrent_hash),
                        f"Export torrent {torrent_hash}"
                    )

                if torrent_file_content is not None:
                    torrent_file_path = os.path.join(extracted_torrent_dir, f"{torrent_hash}.torrent")

                    with open(torrent_file_path, "wb") as f:
                        f.write(torrent_file_content)
                    if meta['debug']:
                        console.print(f"[green]Successfully saved .torrent file: {torrent_file_path}")
                else:
                    console.print(f"[bold red]Failed to export .torrent for {torrent_hash} after retries")
                    continue  # Skip this torrent if unable to fetch

            # **Validate the .torrent file**
            try:
                valid, torrent_path = await self.is_valid_torrent(meta, torrent_file_path, torrent_hash, 'qbit', client)
            except Exception as e:
                console.print(f"[bold red]Error validating torrent {torrent_hash}: {e}")
                valid = False
                torrent_path = None

            if valid:
                if prefer_small_pieces:
                    # **Track best match based on piece size**
                    try:
                        torrent_data = Torrent.read(torrent_file_path)
                        piece_size = torrent_data.piece_size
                        if isinstance(piece_size, int):
                            best_piece_size_raw_value: Any = best_match.get('piece_size') if best_match else None
                            best_piece_size: Optional[int] = best_piece_size_raw_value if isinstance(best_piece_size_raw_value, int) else None
                            if best_match is None or (isinstance(best_piece_size, int) and piece_size < best_piece_size):
                                best_match = {
                                    'hash': torrent_hash,
                                    'torrent_path': torrent_path if torrent_path else torrent_file_path,
                                    'piece_size': piece_size
                                }
                                console.print(f"[green]Updated best match: {best_match}")
                    except Exception as e:
                        console.print(f"[bold red]Error reading torrent data for {torrent_hash}: {e}")
                        continue
                else:
                    # If `prefer_small_pieces` is False, return first valid torrent
                    console.print(f"[green]Returning first valid torrent: {torrent_hash}")
                    return torrent_hash
            else:
                if meta['debug']:
                    console.print(f"[bold red]{torrent_hash} failed validation")
                os.remove(torrent_file_path)

        # **Return the best match if `prefer_small_pieces` is enabled**
        if best_match:
            console.print(f"[green]Using best match torrent with hash: {best_match['hash']}")
            result = str(best_match['hash']) if 'hash' in best_match else None
        else:
            console.print("[yellow]No valid torrents found.")
            result = None

        if qbt_session and proxy_url:
            await qbt_session.close()

        return result

    def rtorrent(self, path: str, torrent_path: str, torrent: Torrent, meta: Dict[str, Any], local_path: str, remote_path: str, client: Dict[str, Any], tracker: str) -> None:
        # Get the appropriate source path (same as in qbittorrent method)
        if len(meta.get('filelist', [])) == 1 and os.path.isfile(meta['filelist'][0]) and not meta.get('keep_folder'):
            # If there's a single file and not keep_folder, use the file itself as the source
            src = meta['filelist'][0]
        else:
            # Otherwise, use the directory
            src = meta.get('path')

        if not src:
            error_msg = "[red]No source path found in meta."
            console.print(f"[bold red]{error_msg}")
            raise ValueError(error_msg)

        # Determine linking method
        linking_method = client.get('linking', None)  # "symlink", "hardlink", or None
        if meta.get('debug', False):
            console.print("Linking method:", linking_method)
        use_symlink = linking_method == "symlink"
        use_hardlink = linking_method == "hardlink"

        if use_symlink and use_hardlink:
            error_msg = "Cannot use both hard links and symlinks simultaneously"
            console.print(f"[bold red]{error_msg}")
            raise ValueError(error_msg)

        # Process linking if enabled
        if use_symlink or use_hardlink:
            # Get linked folder for this drive
            linked_folder = client.get('linked_folder', [])
            if meta.get('debug', False):
                console.print(f"Linked folders: {linked_folder}")
            if not isinstance(linked_folder, list):
                linked_folder = [linked_folder]  # Convert to list if single value

            # Determine drive letter (Windows) or root (Linux)
            if platform.system() == "Windows":
                src_drive = os.path.splitdrive(src)[0]
            else:
                # On Unix/Linux, use the root directory or first directory component
                src_drive = "/"
                # Extract the first directory component for more specific matching
                src_parts = src.strip('/').split('/')
                if src_parts:
                    src_root_dir = '/' + src_parts[0]
                    # Check if any linked folder contains this root
                    for folder in linked_folder:
                        if src_root_dir in folder or folder in src_root_dir:
                            src_drive = src_root_dir
                            break

            # Find a linked folder that matches the drive
            link_target = None
            if platform.system() == "Windows":
                # Windows matching based on drive letters
                for folder in linked_folder:
                    folder_drive = os.path.splitdrive(folder)[0]
                    if folder_drive == src_drive:
                        link_target = folder
                        break
            else:
                # Unix/Linux matching based on path containment
                for folder in linked_folder:
                    # Check if source path is in the linked folder or vice versa
                    if src.startswith(folder) or folder.startswith(src) or folder.startswith(src_drive):
                        link_target = folder
                        break

            if meta.get('debug', False):
                console.print(f"Source drive: {src_drive}")
                console.print(f"Link target: {link_target}")

            # If using symlinks and no matching drive folder, allow any available one
            if use_symlink and not link_target and linked_folder:
                link_target = linked_folder[0]

            if (use_symlink or use_hardlink) and not link_target:
                error_msg = f"No suitable linked folder found for drive {src_drive}"
                console.print(f"[bold red]{error_msg}")
                raise ValueError(error_msg)

            # Create tracker-specific directory inside linked folder
            if use_symlink or use_hardlink:
                # allow overridden folder name with link_dir_name config var
                tracker_cfg = self.config["TRACKERS"].get(tracker.upper(), {})
                link_dir_name = str(tracker_cfg.get("link_dir_name", "")).strip()
                if link_target is None:
                    raise RuntimeError("link_target cannot be None")
                tracker_dir = os.path.join(link_target, link_dir_name or tracker)
                os.makedirs(tracker_dir, exist_ok=True)

                if meta.get('debug', False):
                    console.print(f"[bold yellow]Linking to tracker directory: {tracker_dir}")
                    console.print(f"[cyan]Source path: {src}")

                # Extract only the folder or file name from `src`
                src_name = os.path.basename(src.rstrip(os.sep))  # Ensure we get just the name
                dst = os.path.join(tracker_dir, src_name)  # Destination inside linked folder

                # path magic
                if os.path.exists(dst) or os.path.islink(dst):
                    if meta.get('debug', False):
                        console.print(f"[yellow]Skipping linking, path already exists: {dst}")
                else:
                    if use_hardlink:
                        try:
                            # Check if we're linking a file or directory
                            if os.path.isfile(src):
                                # For a single file, create a hardlink directly
                                try:
                                    os.link(src, dst)
                                    if meta.get('debug', False):
                                        console.print(f"[green]Hard link created: {dst} -> {src}")
                                except OSError as e:
                                    # If hardlink fails, try to copy the file instead
                                    console.print(f"[yellow]Hard link failed: {e}")
                                    console.print(f"[yellow]Falling back to file copy for: {src}")
                                    shutil.copy2(src, dst)  # copy2 preserves metadata
                                    console.print(f"[green]File copied instead: {dst}")
                            else:
                                # For directories, we need to link each file inside
                                os.makedirs(dst, exist_ok=True)

                                for root, _, files in os.walk(src):
                                    # Get the relative path from source
                                    rel_path = os.path.relpath(root, src)

                                    # Create corresponding directory in destination
                                    if rel_path != '.':
                                        dst_dir = os.path.join(dst, rel_path)
                                        os.makedirs(dst_dir, exist_ok=True)

                                    # Create hardlinks for each file
                                    for file in files:
                                        src_file = os.path.join(root, file)
                                        dst_file = os.path.join(dst if rel_path == '.' else dst_dir, file)
                                        try:
                                            os.link(src_file, dst_file)
                                            if meta.get('debug', False) and files.index(file) == 0:
                                                console.print(f"[green]Hard link created for file: {dst_file} -> {src_file}")
                                        except OSError as e:
                                            # If hardlink fails, copy file instead
                                            console.print(f"[yellow]Hard link failed for file {file}: {e}")
                                            shutil.copy2(src_file, dst_file)  # copy2 preserves metadata
                                            console.print(f"[yellow]File copied instead: {dst_file}")

                                if meta.get('debug', False):
                                    console.print(f"[green]Directory structure and files processed: {dst}")
                        except OSError as e:
                            error_msg = f"Failed to create link: {e}"
                            console.print(f"[bold red]{error_msg}")
                            if meta.get('debug', False):
                                console.print(f"[yellow]Source: {src} (exists: {os.path.exists(src)})")
                                console.print(f"[yellow]Destination: {dst}")
                            # Don't raise exception - just warn and continue
                            console.print("[yellow]Continuing with rTorrent addition despite linking failure")

                    elif use_symlink:
                        try:
                            if platform.system() == "Windows":
                                os.symlink(src, dst, target_is_directory=os.path.isdir(src))
                            else:
                                os.symlink(src, dst)

                            if meta.get('debug', False):
                                console.print(f"[green]Symbolic link created: {dst} -> {src}")

                        except OSError as e:
                            error_msg = f"Failed to create symlink: {e}"
                            console.print(f"[bold red]{error_msg}")
                            # Don't raise exception - just warn and continue
                            console.print("[yellow]Continuing with rTorrent addition despite linking failure")

                # Use the linked path for rTorrent if linking was successful
                if (use_symlink or use_hardlink) and os.path.exists(dst):
                    path = dst

        # Apply remote pathing to `tracker_dir` before assigning `save_path`
        if use_symlink or use_hardlink:
            if tracker_dir is None:
                raise ValueError("Linking enabled but tracker_dir was not set")
            save_path = tracker_dir  # Default to linked directory
        else:
            save_path = path  # Default to the original path

        # Handle remote path mapping
        if (
            local_path is not None and remote_path is not None and
            local_path != "" and remote_path != "" and
            local_path.lower() != remote_path.lower()
        ):
            # Normalize paths for comparison
            norm_save_path = os.path.normpath(save_path).lower()
            norm_local_path = os.path.normpath(local_path).lower()

            # Check if the save_path starts with local_path
            if norm_save_path.startswith(norm_local_path):
                # Get the relative part of the path
                rel_path = os.path.relpath(save_path, local_path)
                # Combine remote path with relative path
                save_path = os.path.join(remote_path, rel_path)

            # For direct replacement if the above approach doesn't work
            elif local_path.lower() in save_path.lower():
                save_path = save_path.replace(local_path, remote_path, 1)  # Replace only at the beginning

        if meta['debug']:
            console.print(f"[cyan]Original path: {path}")
            console.print(f"[cyan]Mapped save path: {save_path}")

        rtorrent = xmlrpc.client.Server(client['rtorrent_url'], context=ssl.create_default_context())
        metainfo = bencode.bread(torrent_path)
        if meta['debug']:
            print(f"{rtorrent}: {redact_private_info(rtorrent)}")
            print(f"{metainfo}: {redact_private_info(metainfo)}")
        try:
            # Use dst path if linking was successful, otherwise use original path
            resume_path = dst if (use_symlink or use_hardlink) and os.path.exists(dst) else path
            if meta['debug']:
                console.print(f"[cyan]Using resume path: {resume_path}")
            fast_resume = self.add_fast_resume(metainfo, resume_path, torrent)
        except EnvironmentError as exc:
            console.print("[red]Error making fast-resume data (%s)" % (exc,))
            raise

        new_meta = bencode.bencode(fast_resume)
        if new_meta != metainfo:
            fr_file = torrent_path.replace('.torrent', '-resume.torrent')
            if meta['debug']:
                console.print("Creating fast resume file:", fr_file)
            bencode.bwrite(fast_resume, fr_file)

        # Use dst path if linking was successful, otherwise use original path
        path = dst if (use_symlink or use_hardlink) and os.path.exists(dst) else path

        isdir = os.path.isdir(path)
        # Remote path mount
        modified_fr = False
        if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
            path_dir = os.path.dirname(path)
            path = path.replace(local_path, remote_path)
            path = path.replace(os.sep, '/')
            shutil.copy(fr_file, f"{path_dir}/fr.torrent")
            fr_file = f"{os.path.dirname(path)}/fr.torrent"
            modified_fr = True
            if meta['debug']:
                console.print(f"[cyan]Modified fast resume file path because path mapping: {fr_file}")
        if isdir is False:
            path = os.path.dirname(path)
        if meta['debug']:
            console.print(f"[cyan]Final path for rTorrent: {path}")

        console.print("[bold yellow]Adding and starting torrent")
        rtorrent.load.start_verbose('', fr_file, f"d.directory_base.set={path}")
        if meta['debug']:
            console.print(f"[green]rTorrent load start for {fr_file} with d.directory_base.set={path}")
        time.sleep(1)
        # Add labels
        if client.get('rtorrent_label', None) is not None:
            if meta['debug']:
                console.print(f"[cyan]Setting rTorrent label: {client['rtorrent_label']}")
            rtorrent.d.custom1.set(torrent.infohash, client['rtorrent_label'])
        if meta.get('rtorrent_label') is not None:
            rtorrent.d.custom1.set(torrent.infohash, meta['rtorrent_label'])
            if meta['debug']:
                console.print(f"[cyan]Setting rTorrent label from meta: {meta['rtorrent_label']}")

        # Delete modified fr_file location
        if modified_fr:
            if meta['debug']:
                console.print(f"[cyan]Removing modified fast resume file: {fr_file}")
            os.remove(f"{path_dir}/fr.torrent")
        if meta.get('debug', False):
            console.print(f"[cyan]Path: {path}")
        return

    async def qbittorrent(self, path: str, torrent: Torrent, local_path: str, remote_path: str, client: Dict[str, Any], is_disc: bool, filelist: List[str], meta: Dict[str, Any], tracker: str, cross: bool = False) -> None:
        if meta.get('keep_folder'):
            path = os.path.dirname(path)
        else:
            isdir = os.path.isdir(path)
            if len(filelist) != 1 or not isdir:
                path = os.path.dirname(path)

        # Get the appropriate source path
        if len(meta['filelist']) == 1 and os.path.isfile(meta['filelist'][0]) and not meta.get('keep_folder'):
            # If there's a single file and not keep_folder, use the file itself as the source
            src = meta['filelist'][0]
        else:
            # Otherwise, use the directory
            src = meta.get('path')

        if not src:
            error_msg = "[red]No source path found in meta."
            console.print(f"[bold red]{error_msg}")
            raise ValueError(error_msg)

        # Determine linking method
        linking_method = client.get('linking', None)  # "symlink", "hardlink", or None
        if meta['debug']:
            console.print("Linking method:", linking_method)
        use_symlink = linking_method == "symlink"
        use_hardlink = linking_method == "hardlink"

        if use_symlink and use_hardlink:
            error_msg = "Cannot use both hard links and symlinks simultaneously"
            console.print(f"[bold red]{error_msg}")
            raise ValueError(error_msg)

        # Get linked folder for this drive
        linked_folder = client.get('linked_folder', [])
        if meta['debug']:
            console.print(f"Linked folders: {linked_folder}")
        if not isinstance(linked_folder, list):
            linked_folder = [linked_folder]  # Convert to list if single value

        # Determine drive letter (Windows) or root (Linux)
        if platform.system() == "Windows":
            src_drive = os.path.splitdrive(src)[0]
        else:
            # On Unix/Linux, use the full mount point path for more accurate matching
            src_drive = "/"

            # Get all mount points on the system to find the most specific match
            mounted_volumes = []
            try:
                # Read mount points from /proc/mounts or use 'mount' command output
                if os.path.exists('/proc/mounts'):
                    with open('/proc/mounts', 'r') as f:
                        for line in f:
                            parts = line.split()
                            if len(parts) >= 2:
                                mount_point = parts[1]
                                mounted_volumes.append(mount_point)
                else:
                    # Fall back to mount command if /proc/mounts doesn't exist
                    output = subprocess.check_output(['mount'], text=True)
                    for line in output.splitlines():
                        parts = line.split()
                        if len(parts) >= 3:
                            mount_point = parts[2]
                            mounted_volumes.append(mount_point)
            except Exception as e:
                if meta.get('debug', False):
                    console.print(f"[yellow]Error getting mount points: {str(e)}")

            # Sort mount points by length (descending) to find most specific match first
            mounted_volumes.sort(key=len, reverse=True)

            # Find the most specific mount point that contains our source path
            for mount_point in mounted_volumes:
                if src.startswith(mount_point):
                    src_drive = mount_point
                    if meta.get('debug', False):
                        console.print(f"[cyan]Found mount point: {mount_point} for path: {src}")
                    break

            # If we couldn't find a specific mount point, fall back to linked folder matching
            if src_drive == "/":
                # Extract the first directory component for basic matching
                src_parts = src.strip('/').split('/')
                if src_parts:
                    src_root_dir = '/' + src_parts[0]
                    # Check if any linked folder contains this root
                    for folder in linked_folder:
                        if src_root_dir in folder or folder in src_root_dir:
                            src_drive = src_root_dir
                            break

        # Find a linked folder that matches the drive
        link_target = None
        if platform.system() == "Windows":
            # Windows matching based on drive letters
            for folder in linked_folder:
                folder_drive = os.path.splitdrive(folder)[0]
                if folder_drive == src_drive:
                    link_target = folder
                    break
        else:
            # Unix/Linux matching based on path containment
            for folder in linked_folder:
                # Check if the linked folder starts with the mount point
                if folder.startswith(src_drive) or src.startswith(folder):
                    link_target = folder
                    break

                # Also check if this is a sibling mount point with the same structure
                folder_parts = folder.split('/')
                src_drive_parts = src_drive.split('/')

                # Check if both are mounted under the same parent directory
                if (len(folder_parts) >= 2 and len(src_drive_parts) >= 2 and
                        folder_parts[1] == src_drive_parts[1]):

                    potential_match = os.path.join(src_drive, folder_parts[-1])
                    if os.path.exists(potential_match):
                        link_target = potential_match
                        if meta['debug']:
                            console.print(f"[cyan]Found sibling mount point linked folder: {link_target}")
                        break

        if meta['debug']:
            console.print(f"Source drive: {src_drive}")
            console.print(f"Link target: {link_target}")
        # If using symlinks and no matching drive folder, allow any available one
        if use_symlink and not link_target and linked_folder:
            link_target = linked_folder[0]

        if (use_symlink or use_hardlink) and not link_target:
            error_msg = f"No suitable linked folder found for drive {src_drive}"
            console.print(f"[bold red]{error_msg}")
            raise ValueError(error_msg)

        tracker_dir = None
        if use_symlink or use_hardlink:
            tracker_cfg = self.config["TRACKERS"].get(tracker.upper(), {})
            link_dir_name = str(tracker_cfg.get("link_dir_name", "")).strip()
            if link_target is None:
                raise RuntimeError("link_target cannot be None")
            tracker_dir = os.path.join(link_target, link_dir_name or tracker)
            await asyncio.to_thread(os.makedirs, tracker_dir, exist_ok=True)

            if cross:
                linking_success = await create_cross_seed_links(
                    meta=meta,
                    torrent=torrent,
                    tracker_dir=tracker_dir,
                    use_hardlink=use_hardlink
                )
            else:
                src_name = os.path.basename(src.rstrip(os.sep))
                dst = os.path.join(tracker_dir, src_name)
                linking_success = await async_link_directory(
                    src=src,
                    dst=dst,
                    use_hardlink=use_hardlink,
                    debug=meta.get('debug', False)
                )

            allow_fallback = client.get('allow_fallback', True)
            if not linking_success and allow_fallback:
                console.print(f"[yellow]Using original path without linking: {src}")
                use_hardlink = False
                use_symlink = False
            elif not linking_success:
                console.print("[bold red]Linking failed and fallback is disabled; aborting qBittorrent add")
                return
        elif cross:
            console.print("[yellow]Cross seed requested, but no linking method is configured. Proceeding with original path naming.")

        proxy_url = client.get('qui_proxy_url')
        qbt_client = None
        qbt_session = None

        if proxy_url:
            ssl_context = self.create_ssl_context_for_client(client)
            qbt_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=aiohttp.TCPConnector(ssl=ssl_context)
            )
            qbt_proxy_url = proxy_url.rstrip('/')
        else:
            potential_qbt_client = await self.init_qbittorrent_client(client)
            if not potential_qbt_client:
                return
            else:
                qbt_client = potential_qbt_client

        if meta['debug']:
            console.print("[bold yellow]Adding and rechecking torrent")

        # Apply remote pathing to `tracker_dir` before assigning `save_path`
        if use_symlink or use_hardlink:
            if tracker_dir is None:
                raise ValueError("Linking enabled but tracker_dir was not set")
            save_path = tracker_dir  # Default to linked directory
        else:
            save_path = path  # Default to the original path

        # Handle remote path mapping
        if (
            local_path is not None and remote_path is not None and
            local_path != "" and remote_path != "" and
            local_path.lower() != remote_path.lower()
        ):
            # Normalize paths for comparison
            norm_save_path = os.path.normpath(save_path).lower()
            norm_local_path = os.path.normpath(local_path).lower()

            # Check if the save_path starts with local_path
            if norm_save_path.startswith(norm_local_path):
                # Get the relative part of the path
                rel_path = os.path.relpath(save_path, local_path)
                # Combine remote path with relative path
                save_path = os.path.join(remote_path, rel_path)

            # For direct replacement if the above approach doesn't work
            elif local_path.lower() in save_path.lower():
                save_path = save_path.replace(local_path, remote_path, 1)  # Replace only at the beginning

        # Always normalize separators for qBittorrent (it expects forward slashes)
        save_path = save_path.replace(os.sep, '/')

        # Ensure qBittorrent save path is formatted correctly
        if not save_path.endswith('/'):
            save_path += '/'

        if meta['debug']:
            console.print(f"[cyan]Original path: {path}")
            console.print(f"[cyan]Mapped save path: {save_path}")

        # Automatic management
        auto_management = False
        if not use_symlink and not use_hardlink:
            am_config = client.get('automatic_management_paths', '')
            if meta['debug']:
                console.print(f"AM Config: {am_config}")
            if isinstance(am_config, list):
                for each in am_config:
                    if os.path.normpath(each).lower() in os.path.normpath(path).lower():
                        auto_management = True
            else:
                if os.path.normpath(am_config).lower() in os.path.normpath(path).lower() and am_config.strip() != "":
                    auto_management = True

        if cross and client.get('qbit_cross_cat'):
            qbt_category = client['qbit_cross_cat']
        else:
            qbt_category = client.get("qbit_cat") if not meta.get("qbit_cat") else meta.get('qbit_cat')
        content_layout = client.get('content_layout', 'Original')
        if meta['debug']:
            console.print("qbt_category:", qbt_category)
            console.print(f"Content Layout: {content_layout}")
            console.print(f"[bold yellow]qBittorrent save path: {save_path}")

        if cross:
            skip_checking = True
            paused_on_add = True
        else:
            skip_checking = True
            paused_on_add = False
        tag = None
        if cross and client.get('qbit_cross_tag'):
            tag = client['qbit_cross_tag']
        else:
            if meta.get('qbit_tag'):
                tag = meta['qbit_tag']
            elif client.get("use_tracker_as_tag", False) and tracker:
                tag = tracker
            elif client.get('qbit_tag'):
                tag = client['qbit_tag']

        try:
            if proxy_url:
                if qbt_session is None:
                    raise RuntimeError("qbt_session cannot be None")
                # Create FormData for multipart/form-data request
                data = aiohttp.FormData()
                data.add_field('savepath', save_path)
                data.add_field('autoTMM', str(auto_management).lower())
                data.add_field('skip_checking', str(skip_checking).lower())
                data.add_field('paused', str(paused_on_add).lower())
                data.add_field('contentLayout', content_layout)
                if qbt_category:
                    data.add_field('category', qbt_category)
                if tag:
                    data.add_field('tags', tag)
                data.add_field('torrents', torrent.dump(), filename='torrent.torrent', content_type='application/x-bittorrent')
                if meta['debug']:
                    console.print(f"[cyan]POSTing to {redact_private_info(qbt_proxy_url)}/api/v2/torrents/add with data: savepath={save_path}, autoTMM={auto_management}, skip_checking={skip_checking}, paused={paused_on_add}, contentLayout={content_layout}, category={qbt_category}, tags={tag}")

                async with qbt_session.post(f"{qbt_proxy_url}/api/v2/torrents/add",
                                            data=data) as response:
                    if response.status != 200:
                        console.print(f"[bold red]Failed to add torrent via proxy: {response.status}")
                        return
            else:
                if qbt_client is None:
                    raise RuntimeError("qbt_client cannot be None")
                await self.retry_qbt_operation(
                    lambda: asyncio.to_thread(qbt_client.torrents_add,
                                              torrent_files=torrent.dump(),
                                              save_path=save_path,
                                              use_auto_torrent_management=auto_management,
                                              is_skip_checking=skip_checking,
                                              paused=paused_on_add,
                                              content_layout=content_layout,
                                              category=qbt_category,
                                              tags=tag),
                    "Add torrent to qBittorrent",
                    initial_timeout=14.0
                )
        except (asyncio.TimeoutError, qbittorrentapi.APIConnectionError):
            console.print("[bold red]Failed to add torrent to qBittorrent")
            if qbt_session:
                await qbt_session.close()
            return
        except Exception as e:
            console.print(f"[bold red]Error adding torrent: {e}")
            if qbt_session:
                await qbt_session.close()
            return

        # Wait for torrent to be added
        timeout = 30
        for _ in range(timeout):
            try:
                if proxy_url:
                    if qbt_session is None:
                        raise RuntimeError("qbt_session cannot be None")
                    async with qbt_session.get(f"{qbt_proxy_url}/api/v2/torrents/info",
                                               params={'hashes': torrent.infohash}) as response:
                        if response.status == 200:
                            torrents_info = await response.json()
                            if len(torrents_info) > 0:
                                if meta.get('debug'):
                                    console.print(f"[green]Found {tracker} torrent in qBittorrent.")
                                break
                        else:
                            pass  # Continue waiting
                else:
                    if qbt_client is None:
                        raise RuntimeError("qbt_client cannot be None")
                    torrents_info = await self.retry_qbt_operation(
                        lambda: asyncio.to_thread(qbt_client.torrents_info, torrent_hashes=torrent.infohash),
                        "Check torrent addition",
                        max_retries=1,
                        initial_timeout=10.0
                    )
                    if len(torrents_info) > 0:
                        break
            except asyncio.TimeoutError:
                pass  # Continue waiting
            except Exception:
                pass  # Continue waiting
            await asyncio.sleep(1)
        else:
            console.print("[red]Torrent addition timed out.")
            if qbt_session:
                await qbt_session.close()
            return

        if not cross:
            try:
                if proxy_url:
                    if meta['debug']:
                        console.print("[yellow]No qui proxy resume support....")
                    # async with qbt_session.post(f"{qbt_proxy_url}/api/v2/torrents/resume",
                    #                            data={'hashes': torrent.infohash}) as response:
                    #    if response.status != 200:
                    #        console.print(f"[yellow]Failed to resume torrent via proxy: {response.status}")
                else:
                    if qbt_client is None:
                        raise RuntimeError("qbt_client cannot be None")
                    await self.retry_qbt_operation(
                        lambda: asyncio.to_thread(qbt_client.torrents_resume, torrent.infohash),
                        "Resume torrent"
                    )
            except asyncio.TimeoutError:
                console.print("[yellow]Failed to resume torrent after retries")
            except Exception as e:
                console.print(f"[yellow]Error resuming torrent: {e}")

        if tracker in client.get("super_seed_trackers", []) and not cross:
            try:
                if meta['debug']:
                    console.print(f"{tracker}: Setting super-seed mode.")
                if proxy_url:
                    if qbt_session is None:
                        raise RuntimeError("qbt_session cannot be None")
                    async with qbt_session.post(f"{qbt_proxy_url}/api/v2/torrents/setSuperSeeding",
                                                data={'hashes': torrent.infohash, "value": "true"}) as response:
                        if response.status != 200:
                            console.print(f"{tracker}: Failed to set super-seed via proxy: {response.status}")
                else:
                    if qbt_client is None:
                        raise RuntimeError("qbt_client cannot be None")
                    await self.retry_qbt_operation(
                        lambda: asyncio.to_thread(qbt_client.torrents_set_super_seeding, torrent_hashes=torrent.infohash),
                        "Set super-seed mode",
                        initial_timeout=10.0
                    )
            except asyncio.TimeoutError:
                console.print(f"{tracker}: Super-seed request timed out")
            except Exception as e:
                console.print(f"{tracker}: Super-seed error: {e}")

        if meta['debug']:
            try:
                if proxy_url:
                    if qbt_session is None:
                        raise RuntimeError("qbt_session should not be None")
                    async with qbt_session.get(f"{qbt_proxy_url}/api/v2/torrents/info",
                                               params={'hashes': torrent.infohash}) as response:
                        if response.status == 200:
                            info = await response.json()
                            if info:
                                console.print(f"[cyan]Actual qBittorrent save path: {info[0].get('save_path', 'Unknown')}")
                            else:
                                console.print("[yellow]No torrent info returned from proxy")
                        else:
                            console.print(f"[yellow]Failed to get torrent info via proxy: {response.status}")
                else:
                    if qbt_client is None:
                        raise RuntimeError("qbt_client should not be None")
                    info = await self.retry_qbt_operation(
                        lambda: asyncio.to_thread(qbt_client.torrents_info, torrent_hashes=torrent.infohash),
                        "Get torrent info for debug",
                        initial_timeout=10.0
                    )
                    if info:
                        console.print(f"[cyan]Actual qBittorrent save path: {info[0].save_path}")
                    else:
                        console.print("[yellow]No torrent info returned from qBittorrent")
            except asyncio.TimeoutError:
                console.print("[yellow]Failed to get torrent info for debug after retries")
            except Exception as e:
                console.print(f"[yellow]Error getting torrent info for debug: {e}")

        if meta['debug']:
            console.print(f"Added to: {save_path}")

        if qbt_session:
            await qbt_session.close()

    def deluge(self, path: str, torrent_path: str, torrent: Torrent, local_path: str, remote_path: str, client: Dict[str, Any], meta: Dict[str, Any]) -> None:
        deluge_client = DelugeRPCClient(client['deluge_url'], int(client['deluge_port']), client['deluge_user'], client['deluge_pass'])
        # deluge_client = LocalDelugeRPCClient()
        deluge_client.connect()
        if deluge_client.connected is True:
            console.print("Connected to Deluge")
            isdir = os.path.isdir(path)  # noqa F841
            # Remote path mount
            if local_path.lower() in path.lower() and local_path.lower() != remote_path.lower():
                path = path.replace(local_path, remote_path)
                path = path.replace(os.sep, '/')

            path = os.path.dirname(path)

            deluge_client.call('core.add_torrent_file', torrent_path, base64.b64encode(torrent.dump()), {'download_location': path, 'seed_mode': True})
            if meta['debug']:
                console.print(f"[cyan]Path: {path}")
        else:
            console.print("[bold red]Unable to connect to deluge")

    def transmission(self, path: str, torrent: Torrent, local_path: str, remote_path: str, client: Dict[str, Any], meta: Dict[str, Any]) -> None:
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

    def add_fast_resume(self, metainfo: Dict[str, Any], datapath: str, torrent: Torrent) -> Dict[str, Any]:
        """ Add fast resume data to a metafile dict.
        """
        # Get list of files
        files = metainfo["info"].get("files", None)
        single = files is None
        if single:
            if os.path.isdir(datapath):
                datapath = os.path.join(datapath, metainfo["info"]["name"])
            files = [{
                "path": [os.path.abspath(datapath)],
                "length": metainfo["info"]["length"],
            }]

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

    async def remote_path_map(self, meta: Dict[str, Any], torrent_client_name: Optional[Union[str, Dict[str, Any]]] = None) -> Tuple[str, str]:
        if isinstance(torrent_client_name, dict):
            client_config = torrent_client_name
        elif isinstance(torrent_client_name, str) and torrent_client_name:
            try:
                client_config = self.config['TORRENT_CLIENTS'][torrent_client_name]
            except KeyError as exc:
                raise KeyError(f"Torrent client '{torrent_client_name}' not found in TORRENT_CLIENTS") from exc
        else:
            raise ValueError("torrent_client_name must be a client name or client config dict")

        local_paths = client_config.get('local_path', ['/LocalPath'])
        remote_paths = client_config.get('remote_path', ['/RemotePath'])

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

    async def get_ptp_from_hash(self, meta: Dict[str, Any], pathed: bool = False) -> Dict[str, Any]:
        default_torrent_client = self.config['DEFAULT']['default_torrent_client']
        client = self.config['TORRENT_CLIENTS'][default_torrent_client]
        torrent_client = client['torrent_client']
        if torrent_client == 'rtorrent':
            await self.get_ptp_from_hash_rtorrent(meta, pathed)
            return meta
        elif torrent_client == 'qbit':
            proxy_url = client.get('qui_proxy_url')
            qbt_client = None
            qbt_session = None

            if proxy_url:
                ssl_context = self.create_ssl_context_for_client(client)
                qbt_session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10),
                    connector=aiohttp.TCPConnector(ssl=ssl_context)
                )
                qbt_proxy_url = proxy_url.rstrip('/')
            else:
                potential_qbt_client = await self.init_qbittorrent_client(client)
                if not potential_qbt_client:
                    return meta
                else:
                    qbt_client = potential_qbt_client

            info_hash_v1 = meta.get('infohash')
            if meta['debug']:
                console.print(f"[cyan]Searching for infohash: {info_hash_v1}")

            class TorrentInfo:
                def __init__(self, properties_data: Dict[str, Any]) -> None:
                    self.hash = properties_data.get('hash', info_hash_v1)
                    self.infohash_v1 = properties_data.get('infohash_v1', info_hash_v1)
                    self.name = properties_data.get('name', '')
                    self.comment = properties_data.get('comment', '')
                    self.tracker = ''
                    self.files: list[Any] = []

            try:
                if proxy_url:
                    if qbt_session is None:
                        raise RuntimeError("qbt_session should not be None")
                    async with qbt_session.get(f"{qbt_proxy_url}/api/v2/torrents/properties",
                                               params={'hash': info_hash_v1}) as response:
                        if response.status == 200:
                            torrent_properties = await response.json()
                            if meta['debug']:
                                console.print(f"[cyan]Retrieved torrent properties via proxy for hash: {info_hash_v1}")

                            torrents = [TorrentInfo(torrent_properties)]
                        else:
                            console.print(f"[bold red]Failed to get torrent properties via proxy: {response.status}")
                            if qbt_session:
                                await qbt_session.close()
                            return meta
                else:
                    try:
                        if qbt_client is None:
                            raise RuntimeError("qbt_client should not be None")
                        torrent_properties = await self.retry_qbt_operation(
                            lambda: asyncio.to_thread(qbt_client.torrents_properties, torrent_hash=info_hash_v1),
                            f"Get torrent properties for hash {info_hash_v1}",
                            initial_timeout=14.0
                        )
                        if meta['debug']:
                            console.print(f"[cyan]Retrieved torrent properties via client for hash: {info_hash_v1}")

                        torrents = [TorrentInfo(torrent_properties)]
                    except Exception as e:
                        console.print(f"[yellow]Failed to get properties: {e}")
                        return meta
            except asyncio.TimeoutError:
                console.print("[bold red]Getting torrents list timed out after retries")
                if qbt_session:
                    await qbt_session.close()
                return meta
            except Exception as e:
                console.print(f"[bold red]Error getting torrents list: {e}")
                if qbt_session:
                    await qbt_session.close()
                return meta
            found = False

            folder_id = os.path.basename(meta['path'])
            if meta.get('uuid', None) is None:
                meta['uuid'] = folder_id

            extracted_torrent_dir = os.path.join(meta.get('base_dir', ''), "tmp", meta.get('uuid', ''))
            os.makedirs(extracted_torrent_dir, exist_ok=True)

            for torrent in torrents:
                try:
                    if getattr(torrent, 'infohash_v1', '') == info_hash_v1:
                        comment = getattr(torrent, 'comment', "")
                        match = None

                        if 'torrent_comments' not in meta:
                            meta['torrent_comments'] = []

                        comment_data = {
                            'hash': getattr(torrent, 'infohash_v1', ''),
                            'name': getattr(torrent, 'name', ''),
                            'comment': comment,
                        }
                        meta['torrent_comments'].append(comment_data)

                        if meta.get('debug', False):
                            console.print(f"[cyan]Stored comment for torrent: {comment[:100]}...")

                        if "passthepopcorn.me" in comment:
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
                        elif "https://upload.cx" in comment:
                            match = re.search(r'/(\d+)$', comment)
                            if match:
                                meta['ulcx'] = match.group(1)
                        elif "https://hdbits.org" in comment:
                            match = re.search(r'id=(\d+)', comment)
                            if match:
                                meta['hdb'] = match.group(1)
                        elif "https://broadcasthe.net" in comment:
                            match = re.search(r'id=(\d+)', comment)
                            if match:
                                meta['btn'] = match.group(1)
                        elif "https://beyond-hd.me" in comment:
                            match = re.search(r'details/(\d+)', comment)
                            if match:
                                meta['bhd'] = match.group(1)
                        elif "/torrents/" in comment:
                            match = re.search(r'/(\d+)$', comment)
                            if match:
                                meta['huno'] = match.group(1)

                        if match:
                            for tracker in ['ptp', 'bhd', 'btn', 'huno', 'blu', 'aither', 'ulcx', 'lst', 'oe', 'hdb']:
                                if meta.get(tracker):
                                    console.print(f"[bold cyan]meta updated with {tracker.upper()} ID: {meta[tracker]}")

                        if meta.get('torrent_comments') and meta['debug']:
                            console.print(f"[green]Stored {len(meta['torrent_comments'])} torrent comments for later use")

                        if not pathed:
                            torrent_storage_dir = client.get('torrent_storage_dir')
                            if not torrent_storage_dir:
                                # Export .torrent file
                                torrent_hash = getattr(torrent, 'infohash_v1', '')
                                if meta.get('debug', False):
                                    console.print(f"[cyan]Exporting .torrent file for hash: {torrent_hash}")

                                try:
                                    if proxy_url:
                                        if qbt_session is None:
                                            raise RuntimeError("qbt_session should not be None")
                                        async with qbt_session.post(f"{qbt_proxy_url}/api/v2/torrents/export",
                                                                    data={'hash': torrent_hash}) as response:
                                            if response.status == 200:
                                                torrent_file_content = await response.read()
                                            else:
                                                console.print(f"[red]Failed to export torrent via proxy: {response.status}")
                                                continue
                                    else:
                                        if qbt_client is None:
                                            raise RuntimeError("qbt_client should not be None")
                                        torrent_file_content = await self.retry_qbt_operation(
                                            lambda: asyncio.to_thread(qbt_client.torrents_export, torrent_hash=torrent_hash),
                                            f"Export torrent {torrent_hash}"
                                        )
                                    torrent_file_path = os.path.join(extracted_torrent_dir, f"{torrent_hash}.torrent")

                                    with open(torrent_file_path, "wb") as f:
                                        f.write(torrent_file_content)

                                    # Validate the .torrent file before saving as BASE.torrent
                                    valid, _ = await self.is_valid_torrent(meta, torrent_file_path, torrent_hash, 'qbit', client)
                                    if not valid:
                                        if meta['debug']:
                                            console.print(f"[bold red]Validation failed for {torrent_file_path}")
                                        os.remove(torrent_file_path)  # Remove invalid file
                                    else:
                                        await TorrentCreator.create_base_from_existing_torrent(torrent_file_path, meta['base_dir'], meta['uuid'])
                                except asyncio.TimeoutError:
                                    console.print(f"[bold red]Failed to export .torrent for {torrent_hash} after retries")

                            found = True
                            break
                except Exception as e:
                    if qbt_session:
                        await qbt_session.close()
                    console.print(f"[bold red]Error processing torrent {getattr(torrent, 'name', 'Unknown')}: {e}")
                    if meta.get('debug', False):
                        import traceback
                        console.print(f"[bold red]Traceback: {traceback.format_exc()}")
                    continue

            if not found:
                console.print("[bold red]Matching site torrent with the specified infohash_v1 not found.")

            if qbt_session:
                await qbt_session.close()

            return meta
        else:
            return meta

    async def get_ptp_from_hash_rtorrent(self, meta: Dict[str, Any], pathed: bool = False) -> Dict[str, Any]:
        default_torrent_client = self.config['DEFAULT']['default_torrent_client']
        client = self.config['TORRENT_CLIENTS'][default_torrent_client]
        torrent_storage_dir = client.get('torrent_storage_dir')
        info_hash_v1 = meta.get('infohash')

        if not torrent_storage_dir or not info_hash_v1:
            console.print("[yellow]Missing torrent storage directory or infohash")
            return meta

        # Normalize info hash format for rTorrent (uppercase)
        info_hash_v1 = info_hash_v1.upper().strip()
        torrent_path = os.path.join(torrent_storage_dir, f"{info_hash_v1}.torrent")

        # Extract folder ID for use in temporary file path
        folder_id = os.path.basename(meta['path'])
        if meta.get('uuid', None) is None:
            meta['uuid'] = folder_id

        extracted_torrent_dir = os.path.join(meta.get('base_dir', ''), "tmp", meta.get('uuid', ''))
        os.makedirs(extracted_torrent_dir, exist_ok=True)

        # Check if the torrent file exists directly
        if os.path.exists(torrent_path):
            console.print(f"[green]Found matching torrent file: {torrent_path}")
        else:
            # Try to find the torrent file in storage directory (case insensitive)
            found = False
            console.print(f"[yellow]Searching for torrent file with hash {info_hash_v1} in {torrent_storage_dir}")

            if os.path.exists(torrent_storage_dir):
                for filename in os.listdir(torrent_storage_dir):
                    if filename.lower().endswith(".torrent"):
                        file_hash = os.path.splitext(filename)[0]  # Remove .torrent extension
                        if file_hash.upper() == info_hash_v1:
                            torrent_path = os.path.join(torrent_storage_dir, filename)
                            found = True
                            console.print(f"[green]Found torrent file with matching hash: {filename}")
                            break

            if not found:
                console.print(f"[bold red]No torrent file found for hash: {info_hash_v1}")
                return meta

        # Parse the torrent file to get the comment
        try:
            torrent = Torrent.read(torrent_path)
            comment = torrent.comment or ""

            # Try to find tracker IDs in the comment
            if meta.get('debug'):
                console.print(f"[cyan]Torrent comment: {comment}")

            if 'torrent_comments' not in meta:
                meta['torrent_comments'] = []

            comment_data = {
                'hash': getattr(torrent, 'infohash_v1', '') or '',
                'name': getattr(torrent, 'name', '') or '',
                'comment': comment,
            }
            meta['torrent_comments'].append(comment_data)

            if meta.get('debug', False):
                console.print(f"[cyan]Stored comment for torrent: {comment[:100]}...")

            # Handle various tracker URL formats in the comment
            if "passthepopcorn.me" in comment:
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
                match = re.search(r'details/(\d+)', comment)
                if match:
                    meta['bhd'] = match.group(1)

            # If we found a tracker ID, log it
            for tracker in ['ptp', 'bhd', 'btn', 'blu', 'aither', 'lst', 'oe', 'hdb']:
                if meta.get(tracker):
                    console.print(f"[bold cyan]meta updated with {tracker.upper()} ID: {meta[tracker]}")

            if meta.get('torrent_comments') and meta['debug']:
                console.print(f"[green]Stored {len(meta['torrent_comments'])} torrent comments for later use")

            if not pathed:
                valid, resolved_path = await self.is_valid_torrent(
                    meta, torrent_path, info_hash_v1, 'rtorrent', client
                )

                if valid:
                    base_torrent_path = os.path.join(extracted_torrent_dir, "BASE.torrent")

                    try:
                        await TorrentCreator.create_base_from_existing_torrent(resolved_path, meta['base_dir'], meta['uuid'])
                        if meta['debug']:
                            console.print("[green]Created BASE.torrent from existing torrent")
                    except Exception as e:
                        console.print(f"[bold red]Error creating BASE.torrent: {e}")
                        try:
                            shutil.copy2(resolved_path, base_torrent_path)
                            console.print(f"[yellow]Created simple torrent copy as fallback: {base_torrent_path}")
                        except Exception as copy_err:
                            console.print(f"[bold red]Failed to create backup copy: {copy_err}")

        except Exception as e:
            console.print(f"[bold red]Error reading torrent file: {e}")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

        return meta

    async def get_pathed_torrents(self, path: str, meta: Dict[str, Any]) -> None:
        try:
            matching_torrents = await self.find_qbit_torrents_by_path(path, meta)

            # If we found matches, use the hash from the first exact match
            if matching_torrents:
                exact_matches = [t for t in matching_torrents]
                if exact_matches:
                    meta['infohash'] = exact_matches[0]['hash']
                    if meta['debug']:
                        console.print(f"[green]Found exact torrent match with hash: {meta['infohash']}")

            else:
                if meta['debug']:
                    console.print("[yellow]No matching torrents for the path found in qBittorrent[/yellow]")

        except asyncio.TimeoutError:
            raise
        except Exception as e:
            console.print(f"[red]Error searching for torrents: {str(e)}[/red]")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

    async def find_qbit_torrents_by_path(self, content_path: str, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        if meta.get('debug'):
            console.print(f"[yellow]Searching for torrents in qBittorrent for path: {content_path}[/yellow]")
        try:
            mtv_config = self.config['TRACKERS'].get('MTV')
            piece_limit = self.config['DEFAULT'].get('prefer_max_16_torrent', False)
            mtv_torrent = False
            piece_size_constraints_enabled: Union[str, bool]
            if isinstance(mtv_config, dict):
                mtv_torrent = mtv_config.get('prefer_mtv_torrent', False)
                # MTV preference takes priority as it's more restrictive (8 MiB vs 16 MiB)
                if mtv_torrent:
                    piece_size_constraints_enabled = 'MTV'
                elif piece_limit:
                    piece_size_constraints_enabled = '16MiB'
                else:
                    piece_size_constraints_enabled = False
            else:
                piece_size_constraints_enabled = '16MiB' if piece_limit else False

            meta['piece_size_constraints_enabled'] = piece_size_constraints_enabled

            # Determine which clients to search
            clients_to_search = []

            if meta.get('client') and meta['client'] != 'none':
                # Only search the explicitly requested client
                clients_to_search = [meta['client']]
            else:
                # Use searching_client_list if available, otherwise default client
                searching_list = self.config['DEFAULT'].get('searching_client_list', [])
                if searching_list and isinstance(searching_list, list) and len(searching_list) > 0:
                    # Filter out empty strings and 'none' values
                    clients_to_search = [c for c in searching_list if c and c != 'none']

                if not clients_to_search:
                    default_client = self.config['DEFAULT'].get('default_torrent_client')
                    if default_client and default_client != 'none':
                        clients_to_search = [default_client]

            if not clients_to_search:
                if meta.get('debug'):
                    console.print("[yellow]No clients configured for searching")
                return []

            all_matching_torrents = []
            for client_name in clients_to_search:
                client_config = self.config['TORRENT_CLIENTS'].get(client_name)
                if not client_config:
                    if meta['debug']:
                        console.print(f"[yellow]Client '{client_name}' not found in TORRENT_CLIENTS config")
                    continue

                torrent_client_type = client_config.get('torrent_client')

                if torrent_client_type != 'qbit':
                    if meta['debug']:
                        console.print(f"[yellow]Skipping non-qBit client: {client_name}")
                    continue

                if meta['debug']:
                    console.print(f"[cyan]Searching qBittorrent client: {client_name}")

                torrents = await self._search_single_qbit_client(client_config, content_path, meta, client_name)

                if torrents:
                    # Found matching torrents in this client
                    all_matching_torrents.extend(torrents)

                    # Check if we should stop searching additional clients
                    found_piece_size = meta.get('found_preferred_piece_size', False)
                    constraints_enabled = meta.get('piece_size_constraints_enabled', False)

                    should_stop = False

                    if not constraints_enabled:
                        # No constraints, stop after finding any torrent
                        should_stop = True
                        if meta['debug']:
                            console.print(f"[green]Found {len(torrents)} matching torrent(s) in client '{client_name}' (no piece size constraints), stopping search[/green]")
                    elif found_piece_size == 'no_constraints':
                        # Found valid torrent and no constraints were set
                        should_stop = True
                        if meta['debug']:
                            console.print(f"[green]Found {len(torrents)} matching torrent(s) in client '{client_name}', stopping search[/green]")
                    elif found_piece_size == 'MTV':
                        # MTV constraint is always satisfied since it's most restrictive
                        should_stop = True
                        if meta['debug']:
                            console.print(f"[green]Found torrent with MTV preferred piece size (≤8 MiB) in client '{client_name}', stopping search[/green]")
                    elif found_piece_size == '16MiB' and constraints_enabled == '16MiB':
                        # 16MiB constraint satisfied (and MTV not required)
                        should_stop = True
                        if meta['debug']:
                            console.print(f"[green]Found torrent with 16 MiB piece size in client '{client_name}', stopping search[/green]")
                    else:
                        # Constraints enabled but not met, continue searching
                        if meta['debug']:
                            constraint_name = "MTV (≤8 MiB)" if constraints_enabled == 'MTV' else "16 MiB"
                            console.print(f"[yellow]Found {len(torrents)} torrent(s) in client '{client_name}' but no {constraint_name} piece size match, continuing search[/yellow]")

                    if should_stop:
                        break
                else:
                    if meta['debug']:
                        console.print(f"[yellow]No matching torrents found in client '{client_name}', continuing to next client[/yellow]")

            # Deduplicate by hash (in case same torrent exists in multiple clients)
            seen_hashes = set()
            unique_torrents = []
            for torrent in all_matching_torrents:
                if torrent['hash'] not in seen_hashes:
                    seen_hashes.add(torrent['hash'])
                    unique_torrents.append(torrent)

            if meta['debug'] and len(all_matching_torrents) != len(unique_torrents):
                console.print(f"[cyan]Deduplicated {len(all_matching_torrents)} torrents to {len(unique_torrents)} unique torrents")

            return unique_torrents

        except asyncio.TimeoutError:
            raise
        except Exception as e:
            console.print(f"[bold red]Error finding torrents: {str(e)}")
            if meta['debug']:
                console.print(traceback.format_exc())
            return []

    async def _search_single_qbit_client(self, client_config: Dict[str, Any], content_path: str, meta: Dict[str, Any], client_name: str) -> List[Dict[str, Any]]:
        """Search a single qBittorrent client for matching torrents."""
        try:
            tracker_patterns = {
                'ptp': {"url": "passthepopcorn.me", "pattern": r'torrentid=(\d+)'},
                'aither': {"url": "https://aither.cc", "pattern": r'/(\d+)$'},
                'lst': {"url": "https://lst.gg", "pattern": r'/(\d+)$'},
                'oe': {"url": "https://onlyencodes.cc", "pattern": r'/(\d+)$'},
                'blu': {"url": "https://blutopia.cc", "pattern": r'/(\d+)$'},
                'hdb': {"url": "https://hdbits.org", "pattern": r'id=(\d+)'},
                'btn': {"url": "https://broadcasthe.net", "pattern": r'id=(\d+)'},
                'bhd': {"url": "https://beyond-hd.me", "pattern": r'details/(\d+)'},
                'huno': {"url": "https://hawke.uno", "pattern": r'/(\d+)$'},
                'ulcx': {"url": "https://upload.cx", "pattern": r'/(\d+)$'},
                'rf': {"url": "https://reelflix.xyz", "pattern": r'/(\d+)$'},
                'otw': {"url": "https://oldtoons.world", "pattern": r'/(\d+)$'},
                'yus': {"url": "https://yu-scene.net", "pattern": r'/(\d+)$'},
                'dp': {"url": "https://darkpeers.org", "pattern": r'/(\d+)$'},
                'sp': {"url": "https://seedpool.org", "pattern": r'/(\d+)$'},
            }

            tracker_priority = ['aither', 'ulcx', 'lst', 'blu', 'oe', 'btn', 'bhd', 'huno', 'hdb', 'rf', 'otw', 'yus', 'dp', 'sp', 'ptp']

            qbt_session: Optional[aiohttp.ClientSession] = None
            qbt_client: Optional[qbittorrentapi.Client] = None
            qbt_proxy_url = ''
            proxy_url = client_config.get('qui_proxy_url', '').strip()
            if proxy_url:
                try:
                    ssl_context = self.create_ssl_context_for_client(client_config)
                    session = aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=10),
                        connector=aiohttp.TCPConnector(ssl=ssl_context)
                    )

                    # Store session and URL for later API calls
                    qbt_session = session
                    qbt_proxy_url = proxy_url

                except Exception as e:
                    console.print(f"[bold red]Failed to connect to qBittorrent proxy: {e}")
                    if 'session' in locals():
                        await session.close()
                    return []
            else:
                potential_qbt_client = await self.init_qbittorrent_client(client_config)
                if not potential_qbt_client:
                    return []
                else:
                    qbt_client = potential_qbt_client

            search_term = meta['uuid'].replace('[', '.').replace(']', '.')
            try:
                if proxy_url:
                    # Build qui's enhanced filter options with expression support
                    qui_filters = {
                        "status": [],  # Empty = all statuses, or specify like ["downloading","seeding"]
                        "excludeStatus": ["unregistered", "tracker_down"],
                        "categories": [],
                        "excludeCategories": [],
                        "tags": [],
                        "excludeTags": [],
                        "trackers": [],
                        "excludeTrackers": [],
                    }

                    # Build URL query string with standard qBittorrent API parameters
                    query_parts = [
                        f"search={urllib.parse.quote(search_term)}",
                        "sort=added_on",
                        "reverse=true",
                        "limit=100"
                    ]

                    # Add status parameters if they exist
                    if qui_filters.get('excludeStatus'):
                        # Join multiple excludeStatus filters with comma (qBittorrent style)
                        filter_value = ','.join(qui_filters['excludeStatus'])
                        query_parts.append(f"filter={urllib.parse.quote(filter_value)}")

                    if qui_filters.get('categories'):
                        # Join multiple categories with comma
                        category_value = ','.join(qui_filters['categories'])
                        query_parts.append(f"category={urllib.parse.quote(category_value)}")

                    if qui_filters.get('tags'):
                        # Join multiple tags with comma
                        tag_value = ','.join(qui_filters['tags'])
                        query_parts.append(f"tag={urllib.parse.quote(tag_value)}")

                    query_string = "&".join(query_parts)
                    url = f"{qbt_proxy_url}/api/v2/torrents/search?{query_string}"

                    if meta['debug']:
                        console.print(f"[cyan]Searching qBittorrent via proxy: {redact_private_info(url)}...")

                    if qbt_session is None:
                        return []
                    async with qbt_session.get(url) as response:
                        if response.status == 200:
                            response_data = await response.json()

                            # The qui proxy returns {'torrents': [...]} while standard API returns [...]
                            if isinstance(response_data, dict) and 'torrents' in response_data:
                                torrents_data = response_data['torrents']
                            else:
                                torrents_data = response_data

                            # Ensure torrents_data is iterable
                            if torrents_data is None:
                                torrents_data = []

                            if meta.get('debug', False):
                                if torrents_data:
                                    console.print(f"[cyan]qBittorrent proxy search returned {len(torrents_data)} torrents for '{search_term}'")
                                else:
                                    console.print("[cyan]No matching torrents found via proxy search")

                            # Convert to objects that match qbittorrentapi structure

                            class MockTorrent:
                                def __init__(self, data: Dict[str, Any]):
                                    for key, value in data.items():
                                        setattr(self, key, value)
                                    if not hasattr(self, 'files'):
                                        self.files: list[Any] = []
                                    if not hasattr(self, 'tracker'):
                                        self.tracker = ''
                                    if not hasattr(self, 'comment'):
                                        self.comment = ''

                                def __getattr__(self, name: str) -> Any:
                                    return None
                            torrents = [MockTorrent(torrent) for torrent in torrents_data]
                        else:
                            if response.status == 404:
                                if meta['debug']:
                                    console.print(f"[yellow]No torrents found via proxy search for '[green]{search_term}' [yellow]Maybe tracker errors?")
                            else:
                                if meta['debug']:
                                    console.print(f"[bold red]Failed to get torrents list via proxy: {response.status}")
                            if qbt_session:
                                await qbt_session.close()
                            return []
                else:
                    if qbt_client is None:
                        return []
                    torrents = await self.retry_qbt_operation(
                        lambda: asyncio.to_thread(qbt_client.torrents_info),
                        "Get torrents list",
                        initial_timeout=14.0
                    )
            except asyncio.TimeoutError:
                console.print("[bold red]Getting torrents list timed out after retries")
                if qbt_session:
                    await qbt_session.close()
                return []
            except Exception as e:
                console.print(f"[bold red]Error getting torrents list: {e}")
                if qbt_session:
                    await qbt_session.close()
                return []

            matching_torrents = []

            # First collect exact path matches
            for torrent in torrents:
                try:
                    torrent_name = torrent.name
                    if not torrent_name:
                        if meta['debug']:
                            console.print("[yellow]Skipping torrent with missing name attribute")
                        continue

                    is_match = False

                    # Match logic for single files vs disc/multi-file
                    # Add a fallback default value for meta['is_disc']
                    is_disc = meta.get('is_disc', "")

                    if is_disc in ("", None) and len(meta.get('filelist', [])) == 1:
                        file_name = os.path.basename(meta['filelist'][0])
                        if torrent_name.lower() == file_name.lower():
                            is_match = True
                        elif torrent_name.lower() == meta['uuid'].lower():
                            is_match = True
                    else:
                        if torrent_name.lower() == meta['uuid'].lower():
                            is_match = True

                    if not is_match:
                        continue

                    torrent_properties = []

                    if is_match:
                        tracker_url = torrent.tracker or ""
                        tracker_url_list = [tracker_url] if tracker_url else []
                        try:
                            if proxy_url and not torrent.comment:
                                if meta['debug']:
                                    console.print(f"[cyan]Fetching torrent properties via proxy for torrent: {torrent.name}")
                                if qbt_session is None:
                                    raise RuntimeError("qbt_session should not be None")
                                async with qbt_session.get(f"{qbt_proxy_url}/api/v2/torrents/properties",
                                                           params={'hash': torrent.hash}) as response:
                                    if response.status == 200:
                                        torrent_properties = await response.json()
                                        torrent.comment = torrent_properties.get('comment', '')
                                    else:
                                        if meta['debug']:
                                            console.print(f"[yellow]Failed to get properties for torrent {torrent.name} via proxy: {response.status}")
                                        continue
                            elif not proxy_url:
                                if qbt_client is None:
                                    raise RuntimeError("qbt_client should not be None")
                                torrent_trackers = await self.retry_qbt_operation(
                                    lambda: asyncio.to_thread(qbt_client.torrents_trackers, torrent_hash=torrent.hash),
                                    f"Get trackers for torrent {torrent.name}"
                                )
                        except (asyncio.TimeoutError, qbittorrentapi.APIError):
                            if meta['debug']:
                                console.print(f"[yellow]Failed to get trackers for torrent {torrent.name} after retries")
                            continue
                        except Exception as e:
                            if meta['debug']:
                                console.print(f"[yellow]Error getting trackers for torrent {torrent.name}: {e}")
                            continue

                        if proxy_url:
                            torrent_trackers = getattr(torrent, 'trackers', []) or []
                            has_working_tracker = True
                        else:
                            try:
                                display_trackers = []

                                # Filter out DHT, PEX, LSD "trackers"
                                for tracker in torrent_trackers or []:
                                    if tracker.get('url', '').startswith(('** [DHT]', '** [PeX]', '** [LSD]')):
                                        continue
                                    display_trackers.append(tracker)

                                # Now process the filtered trackers
                                has_working_tracker = False
                                for display_tracker in display_trackers:
                                    url = display_tracker.get('url', 'Unknown URL')
                                    status_code = display_tracker.get('status', 0)
                                    status_text = {
                                        0: "Disabled",
                                        1: "Not contacted",
                                        2: "Working",
                                        3: "Updating",
                                        4: "Error"
                                    }.get(status_code, f"Unknown ({status_code})")

                                    if status_code == 2:
                                        has_working_tracker = True
                                        if meta['debug']:
                                            console.print(f"[green]Tracker working: {url[:15]} - {status_text}")
                                    else:
                                        msg = display_tracker.get('msg', '')
                                        console.print(f"[yellow]Tracker not working: {url[:15]} - {status_text}{f' - {msg}' if msg else ''}")

                            except qbittorrentapi.APIError as e:
                                if meta['debug']:
                                    console.print(f"[red]Error fetching trackers for torrent {torrent.name}: {e}")
                                continue

                        if 'torrent_comments' not in meta:
                            meta['torrent_comments'] = []

                        await match_tracker_url(tracker_url_list, meta)

                        match_info = {
                            'hash': torrent.hash,
                            'name': torrent.name,
                            'save_path': torrent.save_path,
                            'content_path': os.path.normpath(os.path.join(torrent.save_path, torrent.name)),
                            'size': torrent.size,
                            'category': torrent.category,
                            'seeders': torrent.num_complete,
                            'trackers': tracker_url,
                            'has_working_tracker': has_working_tracker,
                            'comment': torrent.comment,
                        }

                        # Initialize a list for found tracker IDs
                        tracker_found = False
                        tracker_id_matches = []

                        for tracker_id in tracker_priority:
                            tracker_info = tracker_patterns.get(tracker_id)
                            if not tracker_info:
                                continue

                            if tracker_info["url"] in torrent.comment and has_working_tracker:
                                match = re.search(tracker_info["pattern"], torrent.comment)
                                if match:
                                    tracker_id_value = match.group(1)
                                    tracker_id_matches.append({
                                        'id': tracker_id,
                                        'tracker_id': tracker_id_value
                                    })
                                    meta[tracker_id] = tracker_id_value
                                    tracker_found = True

                        if torrent.tracker and 'hawke.uno' in torrent.tracker:
                            # Try to extract torrent ID from the comment first
                            if has_working_tracker:
                                huno_id = None
                                if "/torrents/" in torrent.comment:
                                    match = re.search(r'/torrents/(\d+)', torrent.comment)
                                    if match:
                                        huno_id = match.group(1)

                                # If we found an ID, use it
                                if huno_id:
                                    tracker_id_matches.append({
                                        'id': 'huno',
                                        'tracker_id': huno_id,
                                    })
                                    meta['huno'] = huno_id
                                    tracker_found = True

                        if torrent.tracker and 'tracker.anthelion.me' in torrent.tracker:
                            ant_id = 1
                            if has_working_tracker:
                                tracker_id_matches.append({
                                    'id': 'ant',
                                    'tracker_id': ant_id,
                                })
                                meta['ant'] = ant_id
                                tracker_found = True

                        match_info['tracker_urls'] = tracker_id_matches
                        match_info['has_tracker'] = tracker_found

                        if tracker_found:
                            meta['found_tracker_match'] = True

                        if meta.get('debug', False):
                            console.print(f"[cyan]Stored comment for torrent: {torrent.comment[:100]}...")

                        meta['torrent_comments'].append(match_info)
                        matching_torrents.append(match_info)

                except Exception as e:
                    if meta['debug']:
                        console.print(f"[yellow]Error processing torrent {torrent.name}: {str(e)}")
                    continue

            if matching_torrents:
                def get_priority_score(torrent: Dict[str, Any]) -> Tuple[bool, int, bool]:
                    # Start with a high score for torrents with no matching trackers
                    priority_score = 100

                    # If torrent has tracker URLs, find the highest priority one
                    if torrent.get('tracker_urls'):
                        for tracker_url in torrent['tracker_urls']:
                            tracker_id = tracker_url.get('id')
                            if tracker_id in tracker_priority:
                                # Lower index in priority list = higher priority
                                score = tracker_priority.index(tracker_id)
                                priority_score = min(priority_score, score)

                    # Return tuple for sorting: (has_working_tracker, tracker_priority, has_tracker)
                    return (
                        not torrent['has_working_tracker'],
                        priority_score,
                        not torrent['has_tracker']
                    )

                # Sort matches by the priority score function
                matching_torrents.sort(key=get_priority_score)

                if matching_torrents:
                    # Extract tracker IDs to meta for the best match (first one after sorting)
                    best_match = matching_torrents[0]
                    meta['infohash'] = best_match['hash']
                    found_valid_torrent = False

                    # Always extract tracker IDs from the best match
                    if best_match['has_tracker']:
                        for tracker in best_match['tracker_urls']:
                            if tracker.get('id') and tracker.get('tracker_id'):
                                meta[tracker['id']] = tracker['tracker_id']
                                if meta['debug']:
                                    console.print(f"[bold cyan]Found {tracker['id'].upper()} ID: {tracker['tracker_id']} in torrent comment")

                    if not meta.get('base_torrent_created'):
                        torrent_storage_dir = client_config.get('torrent_storage_dir')

                        extracted_torrent_dir = os.path.join(meta.get('base_dir', ''), "tmp", meta.get('uuid', ''))
                        os.makedirs(extracted_torrent_dir, exist_ok=True)

                        # Set up piece size preference logic
                        mtv_config = self.config.get('TRACKERS', {}).get('MTV', {})
                        prefer_small_pieces = mtv_config.get('prefer_mtv_torrent', False)
                        piece_limit = self.config['DEFAULT'].get('prefer_max_16_torrent', False)

                        # Use piece preference if MTV preference is true, otherwise use general piece limit
                        use_piece_preference = prefer_small_pieces or piece_limit
                        piece_size_best_match: Union[Dict[str, Any], None] = None  # Track the best match for fallback if piece preference is enabled

                        # Try the best match first (from the sorted matching torrents)
                        best_torrent_match = matching_torrents[0]
                        torrent_hash = best_torrent_match['hash']
                        torrent_file_path = None

                        if torrent_storage_dir:
                            potential_path = os.path.join(torrent_storage_dir, f"{torrent_hash}.torrent")
                            if os.path.exists(potential_path):
                                torrent_file_path = potential_path
                                if meta.get('debug', False):
                                    console.print(f"[cyan]Found existing .torrent file: {torrent_file_path}")

                        if not torrent_file_path:
                            if meta.get('debug', False):
                                console.print(f"[cyan]Exporting .torrent file for hash: {torrent_hash}")

                            torrent_file_content = None
                            if proxy_url:
                                if qbt_session is None:
                                    console.print("[bold red]Proxy session not initialized")
                                    return []
                                qbt_proxy_url = proxy_url.rstrip('/')
                                try:
                                    async with qbt_session.post(f"{qbt_proxy_url}/api/v2/torrents/export",
                                                                data={'hash': torrent_hash}) as response:
                                        if response.status == 200:
                                            torrent_file_content = await response.read()
                                        else:
                                            console.print(f"[red]Failed to export torrent via proxy: {response.status}")
                                except Exception as e:
                                    console.print(f"[red]Error exporting torrent via proxy: {e}")
                            else:
                                if qbt_client is None:
                                    console.print("[bold red]qBittorrent client not initialized")
                                    return []
                                torrent_file_content = await self.retry_qbt_operation(
                                    lambda: asyncio.to_thread(qbt_client.torrents_export, torrent_hash=torrent_hash),
                                    f"Export torrent {torrent_hash}"
                                )
                            if torrent_file_content is not None:
                                torrent_file_path = os.path.join(extracted_torrent_dir, f"{torrent_hash}.torrent")

                                with open(torrent_file_path, "wb") as f:
                                    f.write(torrent_file_content)

                                if meta.get('debug', False):
                                    console.print(f"[green]Exported .torrent file to: {torrent_file_path}")
                            else:
                                console.print(f"[bold red]Failed to export .torrent for {torrent_hash} after retries")

                        if torrent_file_path:
                            valid, torrent_path = await self.is_valid_torrent(meta, torrent_file_path, torrent_hash, 'qbit', client_config)
                            if valid:
                                if use_piece_preference:
                                    # **Track best match based on piece size**
                                    try:
                                        torrent_data = Torrent.read(torrent_file_path)
                                        piece_size = torrent_data.piece_size
                                        # For prefer_small_pieces: prefer smallest pieces
                                        # For piece_limit: prefer torrents with piece size <= 16 MiB (16777216 bytes)
                                        is_better_match = False
                                        if prefer_small_pieces:
                                            # MTV preference: always prefer smaller pieces
                                            if piece_size_best_match is None:
                                                is_better_match = True
                                            else:
                                                is_better_match = piece_size < piece_size_best_match['piece_size']
                                        elif piece_limit:
                                            # General preference: prefer <= 16 MiB pieces, then smaller within that range
                                            if piece_size <= 16777216:  # 16 MiB
                                                if piece_size_best_match is None:
                                                    is_better_match = True
                                                else:
                                                    is_better_match = (piece_size_best_match['piece_size'] > 16777216 or
                                                                       piece_size < piece_size_best_match['piece_size'])

                                        if is_better_match:
                                            piece_size_best_match = {
                                                'hash': torrent_hash,
                                                'torrent_path': torrent_path if torrent_path else torrent_file_path,
                                                'piece_size': piece_size
                                            }
                                            if meta['debug']:
                                                console.print(f"[green]Updated best match: {piece_size_best_match}")
                                    except Exception as e:
                                        console.print(f"[bold red]Error reading torrent data for {torrent_hash}: {e}")
                                        if os.path.exists(torrent_file_path) and torrent_file_path.startswith(extracted_torrent_dir):
                                            os.remove(torrent_file_path)
                                else:
                                    # If piece preference is disabled, return first valid torrent
                                    try:
                                        await TorrentCreator.create_base_from_existing_torrent(torrent_file_path, meta['base_dir'], meta['uuid'])
                                        if meta['debug']:
                                            console.print(f"[green]Created BASE.torrent from first valid torrent: {torrent_hash}")
                                        meta['base_torrent_created'] = True
                                        meta['hash_used'] = torrent_hash
                                        found_valid_torrent = True
                                    except Exception as e:
                                        console.print(f"[bold red]Error creating BASE.torrent: {e}")
                            else:
                                if meta['debug']:
                                    console.print(f"[bold red]{torrent_hash} failed validation")
                                if os.path.exists(torrent_file_path) and torrent_file_path.startswith(extracted_torrent_dir):
                                    os.remove(torrent_file_path)

                                # If first torrent fails validation, continue to try other matches
                                if not found_valid_torrent:
                                    if meta['debug']:
                                        console.print("[yellow]First torrent failed validation, trying other torrent matches...")

                        # Try other matches if the best match isn't valid or if we need to find all valid torrents for piece preference
                        if not found_valid_torrent or (use_piece_preference and not piece_size_best_match):
                            if meta['debug']:
                                console.print("[yellow]Trying other torrent matches...")
                            for torrent_match in matching_torrents[1:]:  # Skip the first one since we already tried it
                                alt_torrent_hash = torrent_match['hash']
                                alt_torrent_file_path = None

                                if meta.get('debug', False):
                                    console.print(f"[cyan]Trying alternative torrent: {alt_torrent_hash}")

                                # Check if alternative torrent file exists in storage directory
                                if torrent_storage_dir:
                                    alt_potential_path = os.path.join(torrent_storage_dir, f"{alt_torrent_hash}.torrent")
                                    if os.path.exists(alt_potential_path):
                                        alt_torrent_file_path = alt_potential_path
                                        if meta.get('debug', False):
                                            console.print(f"[cyan]Found existing alternative .torrent file: {alt_torrent_file_path}")

                                # If not found in storage directory, export from qBittorrent
                                if not alt_torrent_file_path:
                                    alt_torrent_file_content = None
                                    if proxy_url:
                                        if qbt_session is None:
                                            return []
                                        qbt_proxy_url = proxy_url.rstrip('/')
                                        try:
                                            async with qbt_session.post(f"{qbt_proxy_url}/api/v2/torrents/export",
                                                                        data={'hash': alt_torrent_hash}) as response:
                                                if response.status == 200:
                                                    alt_torrent_file_content = await response.read()
                                                else:
                                                    console.print(f"[red]Failed to export alternative torrent via proxy: {response.status}")
                                        except Exception as e:
                                            console.print(f"[red]Error exporting alternative torrent via proxy: {e}")
                                    else:
                                        if qbt_client is None:
                                            return []
                                        alt_torrent_file_content = await self.retry_qbt_operation(
                                            lambda: asyncio.to_thread(qbt_client.torrents_export, torrent_hash=alt_torrent_hash),
                                            f"Export alternative torrent {alt_torrent_hash}"
                                        )
                                    if alt_torrent_file_content is not None:
                                        alt_torrent_file_path = os.path.join(extracted_torrent_dir, f"{alt_torrent_hash}.torrent")

                                        with open(alt_torrent_file_path, "wb") as f:
                                            f.write(alt_torrent_file_content)

                                        if meta.get('debug', False):
                                            console.print(f"[green]Exported alternative .torrent file to: {alt_torrent_file_path}")
                                    else:
                                        console.print(f"[bold red]Failed to export alternative .torrent for {alt_torrent_hash} after retries")
                                        continue

                                # Validate the alternative torrent
                                if alt_torrent_file_path:
                                    alt_valid, alt_torrent_path = await self.is_valid_torrent(
                                        meta, alt_torrent_file_path, alt_torrent_hash, 'qbit', client_config
                                    )

                                    if alt_valid:
                                        if use_piece_preference:
                                            # **Track best match based on piece size**
                                            try:
                                                torrent_data = Torrent.read(alt_torrent_file_path)
                                                piece_size = torrent_data.piece_size
                                                # For prefer_small_pieces: prefer smallest pieces
                                                # For piece_limit: prefer torrents with piece size <= 16 MiB (16777216 bytes)
                                                is_better_match = False
                                                if prefer_small_pieces:
                                                    # MTV preference: always prefer smaller pieces
                                                    if piece_size_best_match is None:
                                                        is_better_match = True
                                                    else:
                                                        is_better_match = piece_size < piece_size_best_match['piece_size']
                                                elif piece_limit:
                                                    # General preference: prefer <= 16 MiB pieces, then smaller within that range
                                                    if piece_size <= 16777216:  # 16 MiB
                                                        if piece_size_best_match is None:
                                                            is_better_match = True
                                                        else:
                                                            is_better_match = (piece_size_best_match['piece_size'] > 16777216 or
                                                                               piece_size < piece_size_best_match['piece_size'])

                                                if is_better_match:
                                                    piece_size_best_match = {
                                                        'hash': alt_torrent_hash,
                                                        'torrent_path': alt_torrent_path if alt_torrent_path else alt_torrent_file_path,
                                                        'piece_size': piece_size
                                                    }
                                                    if meta['debug']:
                                                        console.print(f"[green]Updated best match: {piece_size_best_match}")
                                            except Exception as e:
                                                console.print(f"[bold red]Error reading torrent data for {alt_torrent_hash}: {e}")
                                        else:
                                            # If piece preference is disabled, return first valid torrent
                                            try:
                                                await TorrentCreator.create_base_from_existing_torrent(alt_torrent_file_path, meta['base_dir'], meta['uuid'])
                                                if meta['debug']:
                                                    console.print(f"[green]Created BASE.torrent from alternative torrent {alt_torrent_hash}")
                                                meta['infohash'] = alt_torrent_hash
                                                meta['base_torrent_created'] = True
                                                meta['hash_used'] = alt_torrent_hash
                                                found_valid_torrent = True
                                                break
                                            except Exception as e:
                                                console.print(f"[bold red]Error creating BASE.torrent for alternative: {e}")
                                    else:
                                        if meta['debug']:
                                            console.print(f"[bold red]{alt_torrent_hash} failed validation")
                                        if os.path.exists(alt_torrent_file_path) and alt_torrent_file_path.startswith(extracted_torrent_dir):
                                            os.remove(alt_torrent_file_path)

                            if not found_valid_torrent:
                                if meta['debug']:
                                    console.print("[bold red]No valid torrents found after checking all matches, falling back to a best match if preference is set")
                                meta['we_checked_them_all'] = True

                        # **Return the best match if piece preference is enabled**
                        if use_piece_preference and piece_size_best_match and not found_valid_torrent:
                            try:
                                preference_type = "MTV preference" if prefer_small_pieces else "16 MiB piece limit"
                                console.print(f"[green]Using best match torrent ({preference_type}) with hash: {piece_size_best_match['hash']}")
                                await TorrentCreator.create_base_from_existing_torrent(piece_size_best_match['torrent_path'], meta['base_dir'], meta['uuid'])
                                if meta['debug']:
                                    piece_size_mib = piece_size_best_match['piece_size'] / 1024 / 1024
                                    console.print(f"[green]Created BASE.torrent from best match torrent: {piece_size_best_match['hash']} (piece size: {piece_size_mib:.1f} MiB)")
                                meta['infohash'] = piece_size_best_match['hash']
                                meta['base_torrent_created'] = True
                                meta['hash_used'] = piece_size_best_match['hash']
                                found_valid_torrent = True

                                # Check if the best match actually meets the piece size constraint
                                piece_size = piece_size_best_match['piece_size']
                                if prefer_small_pieces and piece_size <= 8388608:  # 8 MiB
                                    meta['found_preferred_piece_size'] = 'MTV'
                                elif piece_limit and piece_size <= 16777216:  # 16 MiB
                                    meta['found_preferred_piece_size'] = '16MiB'
                                else:
                                    # Found a torrent but it doesn't meet the constraint
                                    meta['found_preferred_piece_size'] = False
                            except Exception as e:
                                console.print(f"[bold red]Error creating BASE.torrent from best match: {e}")
                        elif use_piece_preference and not piece_size_best_match:
                            console.print("[yellow]No preferred torrents found matching piece size preferences.")
                            meta['we_checked_them_all'] = True
                            meta['found_preferred_piece_size'] = False

                        # If piece preference is not enabled, set flag to indicate we can stop searching
                        if not use_piece_preference and found_valid_torrent:
                            meta['found_preferred_piece_size'] = 'no_constraints'

            # Display results summary
            if meta['debug']:
                if matching_torrents:
                    console.print(f"[green]Found {len(matching_torrents)} matching torrents in {client_name}")
                    console.print(f"[green]Torrents with working trackers: {sum(1 for t in matching_torrents if t.get('has_working_tracker', False))}")
                else:
                    console.print(f"[yellow]No matching torrents found in {client_name}")

            if qbt_session:
                await qbt_session.close()

            return matching_torrents

        except asyncio.TimeoutError:
            if qbt_session:
                await qbt_session.close()
            raise
        except Exception as e:
            console.print(f"[bold red]Error finding torrents in {client_name}: {str(e)}")
            if meta['debug']:
                console.print(traceback.format_exc())
            if qbt_session:
                await qbt_session.close()
            return []


async def create_cross_seed_links(meta: Dict[str, Any], torrent: Torrent, tracker_dir: str, use_hardlink: bool) -> bool:
    debug = meta.get('debug', False)
    metainfo = getattr(torrent, 'metainfo', {})
    if not isinstance(metainfo, dict):
        metainfo = {}
    info_raw = metainfo.get('info')
    info = info_raw if isinstance(info_raw, dict) else {}
    torrent_name = info.get('name.utf-8') or info.get('name') or getattr(torrent, 'name', None)
    if not torrent_name:
        console.print("[bold red]Cross-seed torrent is missing an info name; cannot build link structure")
        return False

    multi_file = bool(info.get('files'))
    torrent_files = []

    def decode_component(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='ignore')
        return str(value)

    if multi_file:
        for file_entry in info.get('files', []):
            raw_path = file_entry.get('path.utf-8') or file_entry.get('path') or []
            if isinstance(raw_path, (list, tuple)):
                components = [decode_component(part) for part in raw_path]
                rel_path = os.path.join(*components) if components else ''
            else:
                rel_path = decode_component(raw_path)
            rel_path = rel_path.replace('/', os.sep)
            rel_path = rel_path.replace('\\', os.sep)
            rel_path = os.path.normpath(rel_path)
            if rel_path.startswith('..'):
                rel_path = rel_path.lstrip('.\\/')
            torrent_files.append({
                'relative_path': rel_path,
                'length': file_entry.get('length')
            })
    else:
        torrent_files.append({
            'relative_path': torrent_name,
            'length': info.get('length')
        })

    destination_root = os.path.join(tracker_dir, torrent_name) if multi_file else tracker_dir
    if multi_file:
        await asyncio.to_thread(os.makedirs, destination_root, exist_ok=True)
    else:
        await asyncio.to_thread(os.makedirs, tracker_dir, exist_ok=True)

    release_root = meta.get('path')
    candidate_paths = []
    if release_root and os.path.isdir(release_root):
        for root, _, files in os.walk(release_root):
            for file in files:
                candidate_paths.append(os.path.join(root, file))
    else:
        candidate_paths.extend(meta.get('filelist', []))
        parent_guess = os.path.dirname(meta['filelist'][0]) if meta.get('filelist') else os.path.dirname(release_root or '')
        if parent_guess and os.path.isdir(parent_guess):
            for root, _, files in os.walk(parent_guess):
                for file in files:
                    candidate_paths.append(os.path.join(root, file))

    unique_candidates = []
    seen = set()
    tracker_abs = os.path.abspath(tracker_dir) if tracker_dir else None
    for candidate in candidate_paths:
        if not candidate:
            continue
        abs_candidate = os.path.abspath(candidate)
        if abs_candidate in seen:
            continue
        seen.add(abs_candidate)
        if not os.path.isfile(abs_candidate):
            continue
        if tracker_abs:
            try:
                if os.path.commonpath([abs_candidate, tracker_abs]) == tracker_abs:
                    continue
            except ValueError:
                pass
        try:
            size = os.path.getsize(abs_candidate)
        except OSError:
            size = None
        unique_candidates.append({
            'path': abs_candidate,
            'name': os.path.basename(abs_candidate).lower(),
            'size': size,
            'used': False
        })

    if not unique_candidates:
        console.print("[bold red]Unable to find source files for cross-seed linking")
        return False

    def pick_candidate(filename: Optional[str], length: Optional[int]) -> tuple[Optional[str], Optional[str]]:
        lower_name = (filename or '').lower()

        if lower_name:
            for entry in unique_candidates:
                if entry['used']:
                    continue
                if entry['name'] == lower_name and length is not None and entry['size'] == length:
                    entry['used'] = True
                    return entry['path'], 'name_size'

        if lower_name:
            for entry in unique_candidates:
                if entry['used']:
                    continue
                if entry['name'] == lower_name:
                    entry['used'] = True
                    return entry['path'], 'name_only'

        if length is not None:
            for entry in unique_candidates:
                if entry['used']:
                    continue
                if entry['size'] == length:
                    entry['used'] = True
                    return entry['path'], 'size_only'

        for entry in unique_candidates:
            if entry['used']:
                continue
            entry['used'] = True
            return entry['path'], 'fallback'

        return None, None

    for torrent_file in torrent_files:
        relative_path = torrent_file['relative_path']
        dest_file_path = os.path.join(tracker_dir, torrent_name, relative_path) if multi_file else os.path.join(tracker_dir, torrent_name)
        dest_file_path = os.path.normpath(dest_file_path)
        tracker_root = os.path.abspath(tracker_dir)
        try:
            if os.path.commonpath([tracker_root, os.path.abspath(dest_file_path)]) != tracker_root:
                console.print(f"[bold red]Refusing to create link outside tracker directory: {dest_file_path}")
                return False
        except ValueError:
            console.print(f"[bold red]Refusing to create link outside tracker directory: {dest_file_path}")
            return False

        source_file, match_reason = pick_candidate(os.path.basename(relative_path), torrent_file.get('length'))
        if not source_file:
            console.print(f"[bold red]Failed to map cross-seed file: {relative_path}")
            return False
        if match_reason == 'fallback' and debug:
            console.print(f"[yellow]Cross-seed mapping fallback used for: {relative_path}")

        dest_parent = os.path.dirname(dest_file_path)
        if dest_parent:
            await asyncio.to_thread(os.makedirs, dest_parent, exist_ok=True)
        if await asyncio.to_thread(os.path.exists, dest_file_path):
            if debug:
                console.print(f"[yellow]Cross-seed link already exists, keeping: {dest_file_path}")
            continue

        linked = await async_link_directory(source_file, dest_file_path, use_hardlink=use_hardlink, debug=debug)
        if not linked:
            console.print(f"[bold red]Linking failed for cross-seed file: {relative_path}")
            return False

    if debug:
        console.print(f"[green]Prepared cross-seed link tree at {os.path.join(tracker_dir, torrent_name) if multi_file else tracker_dir}")
    return True


async def async_link_directory(src: str, dst: str, use_hardlink: bool = True, debug: bool = False) -> bool:
    try:
        # Create destination directory
        await asyncio.to_thread(os.makedirs, os.path.dirname(dst), exist_ok=True)

        # Check if destination already exists
        if await asyncio.to_thread(os.path.exists, dst):
            if debug:
                console.print(f"[yellow]Skipping linking, path already exists: {dst}")
            return True

        # Handle file linking
        if await asyncio.to_thread(os.path.isfile, src):
            if use_hardlink:
                try:
                    await asyncio.to_thread(os.link, src, dst)
                    if debug:
                        console.print(f"[green]Hard link created: {dst} -> {src}")
                    return True
                except OSError as e:
                    console.print(f"[yellow]Hard link failed: {e}")
                    return False
            else:  # Use symlink
                try:
                    if platform.system() == "Windows":
                        await asyncio.to_thread(os.symlink, src, dst, target_is_directory=False)
                    else:
                        await asyncio.to_thread(os.symlink, src, dst)

                    if debug:
                        console.print(f"[green]Symbolic link created: {dst} -> {src}")
                    return True
                except OSError as e:
                    console.print(f"[yellow]Symlink failed: {e}")
                    return False

        # Handle directory linking
        else:
            if use_hardlink:
                # For hardlinks, we need to recreate the directory structure
                await asyncio.to_thread(os.makedirs, dst, exist_ok=True)

                # Get all files in the source directory
                all_items = []
                for root, dirs, files in await asyncio.to_thread(os.walk, src):
                    for file in files:
                        src_path = os.path.join(root, file)
                        rel_path = os.path.relpath(src_path, src)
                        all_items.append((src_path, os.path.join(dst, rel_path), rel_path))

                # Create subdirectories first (to avoid race conditions)
                subdirs = set()
                for _, dst_path, _ in all_items:
                    subdir = os.path.dirname(dst_path)
                    if subdir and subdir not in subdirs:
                        subdirs.add(subdir)
                        await asyncio.to_thread(os.makedirs, subdir, exist_ok=True)

                # Create hardlinks for all files
                success = True
                for src_path, dst_path, rel_path in all_items:
                    try:
                        await asyncio.to_thread(os.link, src_path, dst_path)
                        if debug and rel_path == os.path.relpath(all_items[0][0], src):
                            console.print(f"[green]Hard link created for file: {dst_path} -> {src_path}")
                    except OSError as e:
                        console.print(f"[yellow]Hard link failed for file {rel_path}: {e}")
                        success = False
                        break

                return success
            else:
                # For symlinks, just link the directory itself
                try:
                    if platform.system() == "Windows":
                        await asyncio.to_thread(os.symlink, src, dst, target_is_directory=True)
                    else:
                        await asyncio.to_thread(os.symlink, src, dst)

                    if debug:
                        console.print(f"[green]Symbolic link created: {dst} -> {src}")
                    return True
                except OSError as e:
                    console.print(f"[yellow]Symlink failed: {e}")
                    return False

    except Exception as e:
        console.print(f"[bold red]Error during linking: {e}")
        return False


async def match_tracker_url(tracker_urls: List[str], meta: Dict[str, Any]) -> None:
    tracker_url_patterns = {
        'acm': ["https://eiga.moi"],
        'aither': ["https://aither.cc"],
        'ant': ["tracker.anthelion.me"],
        'ar': ["tracker.alpharatio"],
        'asc': ["amigos-share.club"],
        'az': ["tracker.avistaz.to"],
        'bhd': ["https://beyond-hd.me", "tracker.beyond-hd.me"],
        'bjs': ["tracker.bj-share.info"],
        'blu': ["https://blutopia.cc"],
        'bt': ["t.brasiltracker.org"],
        'btn': ["https://broadcasthe.net"],
        'cbr': ["capybarabr.com"],
        'cz': ["tracker.cinemaz.to"],
        'dc': ["tracker.digitalcore.club", "trackerprxy.digitalcore.club"],
        'dp': ["https://darkpeers.org"],
        'ff': ["tracker.funfile.org"],
        'fl': ["reactor.filelist", "reactor.thefl.org"],
        'fnp': ["https://fearnopeer.com"],
        'gpw': ["https://tracker.greatposterwall.com"],
        'hdb': ["https://tracker.hdbits.org"],
        'hds': ["hd-space.pw"],
        'hdt': ["https://hdts-announce.ru"],
        'hhd': ["https://homiehelpdesk.net"],
        'huno': ["https://hawke.uno"],
        'ihd': ["https://infinityhd.net"],
        'is': ["https://immortalseed.me"],
        'itt': ["https://itatorrents.xyz"],
        'lcd': ["locadora.cc"],
        'ldu': ["theldu.to"],
        'lst': ["https://lst.gg"],
        'lt': ["https://lat-team.com"],
        'mtv': ["tracker.morethantv"],
        'nbl': ["tracker.nebulance"],
        'oe': ["https://onlyencodes.cc"],
        'otw': ["https://oldtoons.world"],
        'phd': ["tracker.privatehd"],
        'pt': ["https://portugas.org"],
        'ptp': ["passthepopcorn.me"],
        'pts': ["https://tracker.ptskit.com"],
        'ras': ["https://rastastugan.org"],
        'rf': ["https://reelflix.xyz", "https://reelflix.cc"],
        'rtf': ["peer.retroflix"],
        'sam': ["https://samaritano.cc"],
        'sp': ["https://seedpool.org"],
        'spd': ["ramjet.speedapp.io", "ramjet.speedapp.to", "ramjet.speedappio.org"],
        'stc': ["https://skipthecommercials.xyz"],
        'thr': ["torrenthr"],
        'tl': ["tracker.tleechreload", "tracker.torrentleech"],
        'tlz': ["https://tlzdigital.com/"],
        'tos': ["https://theoldschool.cc"],
        'ttr': ["https://torrenteros.org"],
        'tvc': ["https://tvchaosuk.com"],
        'ulcx': ["https://upload.cx"],
        'yoink': ["yoinked.org"],
        'yus': ["https://yu-scene.net"],
    }
    found_ids = set()
    for tracker in tracker_urls:
        for tracker_id, patterns in tracker_url_patterns.items():
            for pattern in patterns:
                if pattern in tracker:
                    found_ids.add(tracker_id.upper())
                    if meta.get('debug'):
                        console.print(f"[bold cyan]Matched {tracker_id.upper()} in tracker URL: {redact_private_info(tracker)}")
                    if tracker_id.upper() == 'PTP' and 'passthepopcorn.me' in tracker:
                        if tracker.startswith('http://'):
                            console.print("[red]Found PTP announce URL using plaintext HTTP.\n")
                            console.print("[red]PTP is turning off their plaintext HTTP tracker soon. You must update your announce URLS. See PTP/forums.php?page=1&action=viewthread&threadid=46663")
                            await asyncio.sleep(10)

    if "remove_trackers" not in meta or not isinstance(meta["remove_trackers"], list):
        meta["remove_trackers"] = []

    for tracker_id in found_ids:
        if tracker_id not in meta["remove_trackers"]:
            meta["remove_trackers"].append(tracker_id)
    if meta.get('debug'):
        console.print(f"[bold cyan]Storing matched tracker IDs for later removal: {meta['remove_trackers']}")
