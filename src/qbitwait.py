# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import os
import traceback
from typing import Any, Optional, Union, cast

import aiohttp
import qbittorrentapi

from data.config import config
from src.console import console


class Wait:

    def __init__(self):
        self.proxy_url: Optional[str] = None
        self.qbt_proxy_url: Optional[str] = None
        self.qbt_session: Optional[aiohttp.ClientSession] = None
        self.qbt_client: Optional[qbittorrentapi.Client] = None
        self.qbt_client = self._connect_qbittorrent()

    def _connect_qbittorrent(self) -> Optional[qbittorrentapi.Client]:
        config_map = cast(dict[str, Any], config)
        default_section = cast(dict[str, Any], config_map.get('DEFAULT', {}))
        clients_section = cast(dict[str, Any], config_map.get('TORRENT_CLIENTS', {}))

        default_torrent_client = default_section.get('default_torrent_client', '')
        if not isinstance(default_torrent_client, str) or not default_torrent_client:
            raise ValueError("DEFAULT.default_torrent_client is not configured")

        client_obj = clients_section.get(default_torrent_client)
        if not isinstance(client_obj, dict):
            raise ValueError(f"No torrent client configuration for '{default_torrent_client}'")
        client = cast(dict[str, Any], client_obj)

        proxy_value = client.get('qui_proxy_url')
        self.proxy_url = proxy_value if isinstance(proxy_value, str) and proxy_value else None
        self.qbt_session = None
        self.qbt_client = None

        if self.proxy_url:
            # Use qui proxy URL format
            self.qbt_proxy_url = self.proxy_url.rstrip('/')
            return None  # No traditional client needed for proxy
        else:
            # Use traditional qbittorrent API client
            required_keys = ['qbit_url', 'qbit_port', 'qbit_user', 'qbit_pass']
            missing_keys = [key for key in required_keys if key not in client]
            if missing_keys:
                raise ValueError(f"Missing required qBittorrent config keys: {', '.join(missing_keys)}")

            verify_cert_value = client.get('VERIFY_WEBUI_CERTIFICATE', True)
            verify_cert = verify_cert_value.strip().lower() in {'1', 'true', 'yes'} if isinstance(verify_cert_value, str) else bool(verify_cert_value)

            host = str(client.get('qbit_url', '')).strip()
            if not host:
                raise ValueError("qbit_url is not configured")
            port_value = client.get('qbit_port')
            if isinstance(port_value, (int, str)):
                port: Optional[Union[int, str]] = port_value
            elif port_value is None:
                port = None
            else:
                port = str(port_value)
            username_value = client.get('qbit_user')
            password_value = client.get('qbit_pass')
            username = str(username_value) if username_value is not None else None
            password = str(password_value) if password_value is not None else None

            qbt_client = qbittorrentapi.Client(
                host=host,
                port=port,
                username=username,
                password=password,
                VERIFY_WEBUI_CERTIFICATE=verify_cert
            )

            try:
                qbt_client.auth_log_in()
                return qbt_client
            except qbittorrentapi.LoginFailed as e:
                raise RuntimeError(f"qBittorrent login failed: {e}") from e

    async def wait_for_completion(self, infohash: str, check_interval: int = 3) -> None:
        if not self.proxy_url and not self.qbt_client:
            raise Exception("[ERROR] qBittorrent is not configured.")

        print(f"Waiting for torrent {infohash} to complete...")

        if self.proxy_url:
            self.qbt_session = aiohttp.ClientSession()

        try:
            while True:
                if self.proxy_url:
                    if self.qbt_session is None:
                        raise RuntimeError("qbt_session is not initialized")
                    async with self.qbt_session.get(
                        f"{self.qbt_proxy_url}/api/v2/torrents/info",
                        params={'hashes': infohash}
                    ) as response:
                        if response.status == 200:
                            torrents_data = cast(list[dict[str, Any]], await response.json())
                            target_torrent = torrents_data[0] if torrents_data else None
                        else:
                            print(f"[ERROR] Failed to get torrent info via proxy: {response.status}")
                            break
                else:
                    if self.qbt_client is None:
                        raise RuntimeError("qbt_client is not initialized")
                    torrents = self.qbt_client.torrents_info(hashes=infohash)
                    target_torrent = next((t for t in torrents if t.hash == infohash), None)

                if target_torrent:
                    if self.proxy_url:
                        target_dict = cast(dict[str, Any], target_torrent)
                        state_value = target_dict.get('state')
                    else:
                        state_value = getattr(target_torrent, 'state', None)
                    state_str = str(state_value) if state_value is not None else 'unknown'
                    print(f"[DEBUG] Torrent {infohash} state: {state_str}")

                    if state_str in {'pausedUP', 'seeding', 'completed', 'stalledUP', 'uploading'}:
                        print(f"[INFO] Torrent {infohash} has completed!")
                        return
                else:
                    print(f"[ERROR] Torrent with hash {infohash} not found!")
                    break

                await asyncio.sleep(check_interval)
        finally:
            if self.qbt_session:
                await self.qbt_session.close()

    async def select_and_recheck_best_torrent(self, meta: dict[str, Any], path: str, check_interval: int = 5) -> bool:
        if not self.proxy_url and not self.qbt_client:
            console.print("[red]qBittorrent is not configured.[/red]")
            return False

        torrent_comments = meta.get('torrent_comments')
        if not isinstance(torrent_comments, list):
            console.print("[red]No torrent comments found in metadata[/red]")
            return False
        torrent_comments_list: list[dict[str, Any]] = [
            cast(dict[str, Any], tc)
            for tc in cast(list[Any], torrent_comments)
            if isinstance(tc, dict)
        ]

        target_path = path
        if not target_path:
            console.print("[red]No target path available for matching torrents[/red]")
            return False

        matching_torrents: list[dict[str, Any]] = []
        hash_used = meta.get('hash_used')
        if isinstance(hash_used, str) and hash_used:
            torrent_hash = hash_used.lower()
        else:
            meta_name = meta.get('name')
            meta_name_lower = meta_name.lower() if isinstance(meta_name, str) else None
            for tc in torrent_comments_list:
                content_path = str(tc.get('content_path', '') or '')

                if not tc.get('has_working_tracker', False):
                    continue
                tc_name = tc.get('name')
                matches_path = bool(content_path) and os.path.normpath(content_path).lower() == os.path.normpath(target_path).lower()
                matches_name = isinstance(tc_name, str) and meta_name_lower is not None and tc_name.lower() == meta_name_lower
                if matches_path or matches_name:
                    matching_torrents.append(tc)

            if not matching_torrents:
                console.print("[yellow]No matching torrents with working trackers found in qBittorrent[/yellow]")
                return True

            matching_torrents.sort(key=lambda x: int(x.get('seeders', 0) or 0), reverse=True)
            best_torrent = matching_torrents[0]

            best_hash = best_torrent.get('hash')
            if not isinstance(best_hash, str):
                console.print("[red]Best torrent is missing a valid hash[/red]")
                return False
            torrent_hash = best_hash.lower()
            console.print(
                f"[green]Selected best torrent: {best_torrent.get('name')} with {best_torrent.get('seeders', 0)} seeders[/green]"
                f"[yellow] Tracker: {str(best_torrent.get('trackers', 'unknown'))[:20]}[/yellow]"
            )

        if self.proxy_url:
            self.qbt_session = aiohttp.ClientSession()

        try:
            # Recheck the torrent
            if self.proxy_url:
                if self.qbt_session is None:
                    console.print("[bold red]qbt_session is not initialized")
                    return False
                if self.qbt_proxy_url is None:
                    console.print("[bold red]Proxy URL is not configured correctly")
                    return False
                async with self.qbt_session.post(
                    f"{self.qbt_proxy_url}/api/v2/torrents/recheck",
                    data={'hashes': torrent_hash}
                ) as response:
                    if response.status != 200:
                        console.print(f"[bold red]Failed to recheck torrent via proxy: {response.status}")
                        return False
            else:
                if self.qbt_client is None:
                    console.print("[bold red]qbt_client is not initialized")
                    return False
                self.qbt_client.torrents_recheck(torrent_hashes=torrent_hash)

            await asyncio.sleep(3)
        except Exception as e:
            console.print(f"[bold red]Failed to recheck torrent: {e}")
            return False

        try:
            while True:
                if self.proxy_url:
                    if self.qbt_session is None:
                        console.print("[bold red]qbt_session is not initialized")
                        return False
                    if self.qbt_proxy_url is None:
                        console.print("[bold red]Proxy URL is not configured correctly")
                        return False
                    async with self.qbt_session.get(
                        f"{self.qbt_proxy_url}/api/v2/torrents/info",
                        params={'hashes': torrent_hash}
                    ) as response:
                        if response.status == 200:
                            torrents_data = cast(list[dict[str, Any]], await response.json())
                            if torrents_data:
                                torrent = torrents_data[0]
                                state = torrent.get('state')
                                progress = torrent.get('progress', 0)
                                state_str = str(state) if state is not None else 'unknown'
                                try:
                                    progress_float = float(progress or 0)
                                except (TypeError, ValueError):
                                    progress_float = 0.0
                            else:
                                raise Exception("No torrents found in response")
                        else:
                            console.print(f"[bold red]Failed to get torrent info via proxy: {response.status}")
                            return False
                else:
                    if self.qbt_client is None:
                        console.print("[bold red]qbt_client is not initialized")
                        return False
                    torrent_list_raw = cast(Any, self.qbt_client.torrents_info(hashes=torrent_hash))
                    if torrent_list_raw is None:
                        raise Exception("qBittorrent returned no torrent info")
                    if isinstance(torrent_list_raw, list):
                        torrent_candidates = cast(list[Any], torrent_list_raw)
                    elif isinstance(torrent_list_raw, tuple):
                        torrent_candidates = list(cast(tuple[Any, ...], torrent_list_raw))
                    else:
                        torrent_candidates = [torrent_list_raw]
                    if not torrent_candidates:
                        raise Exception("No torrents found in TorrentInfoList")
                    torrent = torrent_candidates[0]
                    state = getattr(torrent, 'state', None)
                    progress = getattr(torrent, 'progress', 0)
                    state_str = str(state) if state is not None else 'unknown'
                    progress_float = float(progress or 0)

                print(f"\r[INFO] Torrent is at {progress_float * 100:.2f}% progress of {state_str}...", end='', flush=True)

                if state_str not in ('checkingUP', 'checkingDL', 'checkingResumeData'):
                    print()
                    break

                await asyncio.sleep(check_interval)

            # Get final torrent info
            if self.proxy_url:
                if self.qbt_session is None:
                    console.print("[bold red]qbt_session is not initialized")
                    return False
                if self.qbt_proxy_url is None:
                    console.print("[bold red]Proxy URL is not configured correctly")
                    return False
                async with self.qbt_session.get(
                    f"{self.qbt_proxy_url}/api/v2/torrents/info",
                    params={'hashes': torrent_hash}
                ) as response:
                    if response.status == 200:
                        torrents_data = cast(list[dict[str, Any]], await response.json())
                        if torrents_data:
                            torrent = torrents_data[0]
                            final_state = torrent.get('state')
                            final_progress = torrent.get('progress', 0)
                        else:
                            raise Exception("No torrents found in response")
                    else:
                        console.print(f"[bold red]Failed to get final torrent info via proxy: {response.status}")
                        return False
            else:
                if self.qbt_client is None:
                    console.print("[bold red]qbt_client is not initialized")
                    return False
                torrent_list_raw = cast(Any, self.qbt_client.torrents_info(hashes=torrent_hash))
                if torrent_list_raw is None:
                    raise Exception("qBittorrent returned no torrent info")
                if isinstance(torrent_list_raw, list):
                    torrent_candidates = cast(list[Any], torrent_list_raw)
                elif isinstance(torrent_list_raw, tuple):
                    torrent_candidates = list(cast(tuple[Any, ...], torrent_list_raw))
                else:
                    torrent_candidates = [torrent_list_raw]
                if not torrent_candidates:
                    raise Exception("No torrents found in TorrentInfoList")
                torrent = torrent_candidates[0]
                final_state = getattr(torrent, 'state', 'unknown')
                final_progress = float(getattr(torrent, 'progress', 0) or 0)

            console.print(f"[green]Recheck completed. State: {final_state}, Progress: {final_progress*100:.2f}%[/green]")
            meta['we_rechecked_torrent'] = True

            if final_state not in {'pausedUP', 'seeding', 'completed', 'stalledUP', 'uploading'}:
                console.print("[yellow]Torrent needs to download missing data. Waiting for completion...[/yellow]")
                await self.wait_for_completion(torrent_hash, check_interval)

            return True

        except Exception as e:
            console.print(f"[bold red]Error while waiting for recheck: {e}")
            traceback.print_exc()
            return False
        finally:
            if self.qbt_session:
                await self.qbt_session.close()
