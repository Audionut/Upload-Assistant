# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import os
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Any, Optional, Union, cast

import aiohttp
import defusedxml.xmlrpc
import qbittorrentapi
from torf import Torrent

from src.console import console
from src.torrent_clients import DelugeClientMixin, QbittorrentClientMixin, RtorrentClientMixin, TransmissionClientMixin

# Secure XML-RPC client using defusedxml to prevent XML attacks
defusedxml.xmlrpc.monkey_patch()


class Clients(QbittorrentClientMixin, RtorrentClientMixin, DelugeClientMixin, TransmissionClientMixin):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @staticmethod
    def _extract_tracker_ids_from_comment(comment: str) -> dict[str, str]:
        if not comment:
            return {}

        def _is_host(host: str, domain: str) -> bool:
            host = host.lower()
            domain = domain.lower()
            return host == domain or host.endswith(f".{domain}")

        def _last_path_id(path: str) -> Optional[str]:
            match = re.search(r"/(\d+)$", path)
            return match.group(1) if match else None

        def _query_id(query: str, key: str) -> Optional[str]:
            values = urllib.parse.parse_qs(query).get(key)
            return values[0] if values else None

        tracker_ids: dict[str, str] = {}
        urls: list[str] = re.findall(r"https?://[^\s\"'<>]+", comment)
        for url in urls:
            parsed = urllib.parse.urlparse(url)
            host = (parsed.hostname or "").lower()
            path = parsed.path

            if _is_host(host, "passthepopcorn.me"):
                ptp_id = _query_id(parsed.query, "torrentid")
                if ptp_id:
                    tracker_ids["ptp"] = ptp_id
            elif _is_host(host, "aither.cc"):
                tracker_id = _last_path_id(path)
                if tracker_id:
                    tracker_ids["aither"] = tracker_id
            elif _is_host(host, "lst.gg"):
                tracker_id = _last_path_id(path)
                if tracker_id:
                    tracker_ids["lst"] = tracker_id
            elif _is_host(host, "onlyencodes.cc"):
                tracker_id = _last_path_id(path)
                if tracker_id:
                    tracker_ids["oe"] = tracker_id
            elif _is_host(host, "blutopia.cc"):
                tracker_id = _last_path_id(path)
                if tracker_id:
                    tracker_ids["blu"] = tracker_id
            elif _is_host(host, "upload.cx"):
                tracker_id = _last_path_id(path)
                if tracker_id:
                    tracker_ids["ulcx"] = tracker_id
            elif _is_host(host, "hdbits.org"):
                hdb_id = _query_id(parsed.query, "id")
                if hdb_id:
                    tracker_ids["hdb"] = hdb_id
            elif _is_host(host, "broadcasthe.net"):
                btn_id = _query_id(parsed.query, "id")
                if btn_id:
                    tracker_ids["btn"] = btn_id
            elif _is_host(host, "beyond-hd.me"):
                match = re.search(r"/details/(\d+)", path)
                if match:
                    tracker_ids["bhd"] = match.group(1)
            elif _is_host(host, "hawke.uno"):
                tracker_id = _last_path_id(path)
                if tracker_id:
                    tracker_ids["huno"] = tracker_id

        return tracker_ids

    async def add_to_client(self, meta: dict[str, Any], tracker: str, cross: bool = False) -> None:
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

        inject_clients: list[str] = []
        client_value = meta.get('client')
        if isinstance(client_value, str) and client_value != 'none':
            inject_clients = [client_value]
            if meta['debug']:
                console.print(f"[cyan]DEBUG: Using client from meta: {inject_clients}[/cyan]")
        elif client_value == 'none':
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
                    inject_clients_list = cast(list[Any], inject_clients_config)
                    inject_clients = [str(c).strip() for c in inject_clients_list if str(c).strip()]
                    if meta['debug']:
                        console.print(f"[cyan]DEBUG: Using injecting_client_list from config: {inject_clients}[/cyan]")
                else:
                    inject_clients = []
            except Exception as e:
                if meta['debug']:
                    console.print(f"[cyan]DEBUG: Error reading injecting_client_list from config: {e}[/cyan]")

            if not inject_clients:
                default_client = self.config['DEFAULT'].get('default_torrent_client')
                if isinstance(default_client, str) and default_client != 'none':
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
            await self.inject_delay(meta, tracker, client_name)

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
                    self.deluge(meta['path'], torrent_path, torrent, local_path, remote_path, client, meta)
                elif torrent_client.lower() == "transmission":
                    self.transmission(meta['path'], torrent, local_path, remote_path, client, meta)
                elif torrent_client.lower() == "watch":
                    shutil.copy(torrent_path, client['watch_folder'])
            except Exception as e:
                console.print(f"[bold red]Failed to add torrent to {client_name}: {e}")
        return

    async def inject_delay(self, meta: dict[str, Any], tracker: str, client_name: str) -> None:
        """
        Applies an optional delay before injecting a torrent into the client.

        The delay can be configured either per tracker or globally in the default settings.
        When both are defined, the tracker-specific value takes precedence over the client setting.

        This mechanism exists to handle cases where a tracker requires a short amount
        of time to register the uploaded torrent hash. Injecting the torrent too early
        may cause connectivity issues, such as failing to discover peers even though
        they are already available.

        By waiting before injection, this function helps ensure proper tracker
        synchronization and more reliable peer discovery.
        """
        tracker_cfg = self.config.get("TRACKERS", {}).get(tracker, {})
        has_tracker_delay = isinstance(tracker_cfg, dict) and "inject_delay" in tracker_cfg
        inject_delay = tracker_cfg.get("inject_delay") if has_tracker_delay else self.config["DEFAULT"].get("inject_delay", 0)
        if inject_delay is not None:
            try:
                inject_delay = int(inject_delay)
            except (ValueError, TypeError):
                if has_tracker_delay:
                    console.print(f"{tracker}: [bold red]CONFIG ERROR: 'inject_delay' must be an integer")
                else:
                    console.print("[bold red]CONFIG ERROR: 'inject_delay' must be an integer")
                inject_delay = 0

            if inject_delay < 0:
                console.print("[bold red]CONFIG ERROR: 'inject_delay' must be >= 0")
                inject_delay = 0
            if inject_delay > 0:
                if meta["debug"] or inject_delay > 5:
                    if has_tracker_delay:
                        console.print(f"{tracker}: [cyan]Waiting {inject_delay} seconds before adding to client '{client_name}'[/cyan]")
                    else:
                        console.print(f"[cyan]Waiting {inject_delay} seconds before adding to client '{client_name}'[/cyan]")
                await asyncio.sleep(inject_delay)

    async def find_existing_torrent(self, meta: dict[str, Any]) -> Optional[str]:
        # Determine piece size preferences
        trackers_config = cast(dict[str, Any], self.config.get('TRACKERS', {}))
        mtv_config = trackers_config.get('MTV', {})
        piece_limit = bool(self.config['DEFAULT'].get('prefer_max_16_torrent', False))
        mtv_torrent = False
        if isinstance(mtv_config, dict):
            mtv_config_dict = cast(dict[str, Any], mtv_config)
            mtv_torrent = bool(mtv_config_dict.get('prefer_mtv_torrent', False))
            prefer_small_pieces = mtv_torrent
        else:
            prefer_small_pieces = bool(piece_limit)
        best_match = None  # Track the best match for fallback if prefer_small_pieces is enabled

        default_torrent_client = cast(str, self.config['DEFAULT']['default_torrent_client'])

        clients_to_search: list[str]
        meta_client = meta.get('client')
        if isinstance(meta_client, str) and meta_client != 'none':
            clients_to_search = [meta_client]
            if meta['debug']:
                console.print(f"[cyan]DEBUG: Using client from meta: {clients_to_search}[/cyan]")
        else:
            searching_list = self.config['DEFAULT'].get('searching_client_list', [])
            searching_list_values = cast(list[Any], searching_list) if isinstance(searching_list, list) else []

            if searching_list_values:
                clients_to_search = [str(c) for c in searching_list_values if str(c) and str(c) != 'none']
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
                    return result

        if prefer_small_pieces and best_match:
            console.print(f"[yellow]Using best match torrent with hash: [bold yellow]{best_match['torrenthash']}[/bold yellow]")
            torrent_path = best_match.get('torrent_path')
            return torrent_path if isinstance(torrent_path, str) else None

        console.print("[bold yellow]No Valid .torrent found")
        return None

    async def _search_single_client_for_torrent(self, meta: dict[str, Any], client_name: str, prefer_small_pieces: bool, mtv_torrent: bool, piece_limit: bool, best_match: Optional[dict[str, Any]]) -> Union[dict[str, Any], str, None]:
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

                            qbt_client_local: qbittorrentapi.Client = qbt_client

                            try:
                                torrent_file_content = await self.retry_qbt_operation(
                                    lambda qbt_client_local=qbt_client_local, hash_value_str=hash_value_str: asyncio.to_thread(
                                        qbt_client_local.torrents_export, torrent_hash=hash_value_str
                                    ),
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

                        await asyncio.to_thread(Path(torrent_path).write_bytes, torrent_file_content)

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
            qbt_session: Optional[aiohttp.ClientSession] = None
            try:

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

                        torrent_file_content: Optional[bytes] = None

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
                                            lambda qbt_client=qbt_client, found_hash=found_hash: asyncio.to_thread(
                                                qbt_client.torrents_export, torrent_hash=found_hash
                                            ),
                                            f"Export torrent {found_hash}"
                                        )
                                    except (asyncio.TimeoutError, qbittorrentapi.APIError) as e:
                                        console.print(f"[red]Error exporting torrent: {e}")

                            if found_hash:  # Only proceed if export succeeded
                                if not torrent_file_content:
                                    found_hash = None
                                else:
                                    os.makedirs(extracted_torrent_dir, exist_ok=True)
                                    await asyncio.to_thread(Path(found_torrent_path).write_bytes, torrent_file_content)
                                    console.print(f"[green]Successfully saved .torrent file: {found_torrent_path}")
                        except Exception as e:
                            console.print(f"[bold red]Unexpected error fetching .torrent from qBittorrent: {e}")
                            console.print("[cyan]DEBUG: Skipping found_hash due to unexpected error[/cyan]")
                            found_hash = None
                    else:
                        console.print(f"[cyan]DEBUG: .torrent file already exists at {found_torrent_path}[/cyan]")

                # Only validate if we still have a hash (export succeeded or file already existed)
                resolved_path = ""
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

    async def is_valid_torrent(self, meta: dict[str, Any], torrent_path: str, torrenthash: str, torrent_client: str, client: dict[str, Any]) -> tuple[bool, str]:
        valid = False
        wrong_file = False
        filelist = cast(list[str], meta.get('filelist', []))
        meta_path = str(meta.get('path', ''))
        meta_uuid = str(meta.get('uuid', ''))

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
            if (meta.get('is_disc') and meta.get('is_disc') != '') or (meta.get('keep_folder', False) and meta.get('isdir', False)):
                torrent_name = torrent.metainfo['info']['name']
                if meta_uuid != torrent_name and meta['debug']:
                    console.print("Modified file structure, skipping hash")
                    valid = False
                torrent_filepath = os.path.commonpath(torrent.files)
                if os.path.basename(meta_path) in torrent_filepath:
                    valid = True
                if meta['debug']:
                    console.log(f"Torrent is valid based on disc/basename or keep-folder: {valid}")

            # If one file, check for folder
            elif len(torrent.files) == len(filelist) == 1:
                if os.path.basename(torrent.files[0]) == os.path.basename(filelist[0]):
                    if str(torrent.files[0]) == os.path.basename(torrent.files[0]):
                        valid = True
                    else:
                        wrong_file = True
                if meta['debug']:
                    console.log(f"Single file match status: valid={valid}, wrong_file={wrong_file}")

            # Check if number of files matches number of videos
            elif len(torrent.files) == len(filelist):
                torrent_filepath = os.path.commonpath(torrent.files)
                actual_filepath = os.path.commonpath(filelist)
                local_path, remote_path = await self.remote_path_map(meta, client)
                if local_path.lower() in meta_path.lower() and local_path.lower() != remote_path.lower():
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

    async def remote_path_map(self, meta: dict[str, Any], torrent_client_name: Optional[Union[str, dict[str, Any]]] = None) -> tuple[str, str]:
        if isinstance(torrent_client_name, dict):
            client_config: dict[str, Any] = torrent_client_name
        elif isinstance(torrent_client_name, str) and torrent_client_name:
            try:
                client_config = cast(dict[str, Any], self.config['TORRENT_CLIENTS'][torrent_client_name])
            except KeyError as exc:
                raise KeyError(f"Torrent client '{torrent_client_name}' not found in TORRENT_CLIENTS") from exc
        else:
            raise ValueError("torrent_client_name must be a client name or client config dict")

        def _coerce_paths(value: Any) -> list[str]:
            if isinstance(value, list):
                value_list = cast(list[Any], value)
                return [str(v) for v in value_list if str(v)]
            return [str(value)] if value is not None else []

        local_paths = _coerce_paths(client_config.get('local_path', ['/LocalPath']))
        remote_paths = _coerce_paths(client_config.get('remote_path', ['/RemotePath']))
        if not local_paths:
            local_paths = ['/LocalPath']
        if not remote_paths:
            remote_paths = ['/RemotePath']

        list_local_path = local_paths[0]
        list_remote_path = remote_paths[0]
        meta_path = str(meta.get('path', ''))

        for i, local_path_value in enumerate(local_paths):
            if os.path.normpath(local_path_value).lower() in meta_path.lower():
                list_local_path = local_path_value
                list_remote_path = remote_paths[i] if i < len(remote_paths) else remote_paths[0]
                break

        local_path = os.path.normpath(list_local_path)
        remote_path = os.path.normpath(list_remote_path)
        if local_path.endswith(os.sep):
            remote_path = remote_path + os.sep

        return local_path, remote_path

    async def get_ptp_from_hash(self, meta: dict[str, Any], pathed: bool = False) -> dict[str, Any]:
        default_torrent_client = self.config['DEFAULT']['default_torrent_client']
        client = self.config['TORRENT_CLIENTS'][default_torrent_client]
        torrent_client = client['torrent_client']
        if torrent_client == 'rtorrent':
            await self.get_ptp_from_hash_rtorrent(meta, pathed)
            return meta
        elif torrent_client == 'qbit':
            return await self.get_ptp_from_hash_qbit(meta, client, pathed)
        else:
            return meta
