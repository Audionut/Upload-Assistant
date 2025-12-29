# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
import qbittorrentapi
import os
import traceback
import aiohttp
import asyncio
from data.config import config
from src.console import console


class Wait:

    def __init__(self):
        self.qbt_client = self._connect_qbittorrent()

    def _connect_qbittorrent(self):
        default_torrent_client = config['DEFAULT']['default_torrent_client']
        client = config['TORRENT_CLIENTS'][default_torrent_client]

        self.proxy_url = client.get('qui_proxy_url')
        self.qbt_session = None
        self.qbt_client = None

        if self.proxy_url:
            # Use qui proxy URL format
            self.qbt_proxy_url = self.proxy_url.rstrip('/')
            return None  # No traditional client needed for proxy
        else:
            # Use traditional qbittorrent API client
            qbt_client = qbittorrentapi.Client(
                host=client['qbit_url'],
                port=client['qbit_port'],
                username=client['qbit_user'],
                password=client['qbit_pass'],
                VERIFY_WEBUI_CERTIFICATE=client.get('VERIFY_WEBUI_CERTIFICATE', True)
            )

            try:
                qbt_client.auth_log_in()
                return qbt_client
            except qbittorrentapi.LoginFailed as e:
                raise Exception(f"[ERROR] qBittorrent login failed: {e}")

    async def select_and_recheck_best_torrent(self, meta, path, check_interval=5):
        if not self.proxy_url and not self.qbt_client:
            console.print("[red]qBittorrent is not configured.[/red]")
            return False

        if not meta.get('torrent_comments'):
            console.print("[red]No torrent comments found in metadata[/red]")
            return True

        target_path = path
        if not target_path:
            console.print("[red]No target path available for matching torrents[/red]")
            return False

        matching_torrents = []
        if meta.get('hash_used', None):
            torrent_hash = meta['hash_used'].lower()
        else:
            for tc in meta['torrent_comments']:
                content_path = tc.get('content_path', '')

                if not tc.get('has_working_tracker', False):
                    continue

                if content_path and os.path.normpath(content_path).lower() == os.path.normpath(target_path).lower():
                    matching_torrents.append(tc)
                elif tc.get('name') and meta.get('name') and tc['name'].lower() == meta['name'].lower():
                    matching_torrents.append(tc)

            if not matching_torrents:
                console.print("[yellow]No matching torrents with working trackers found in qBittorrent[/yellow]")
                return True

            matching_torrents.sort(key=lambda x: x.get('seeders', 0), reverse=True)
            best_torrent = matching_torrents[0]

            torrent_hash = best_torrent['hash'].lower()
            console.print(f"[green]Selected best torrent: {best_torrent.get('name')} with {best_torrent.get('seeders', 0)} seeders[/green][yellow] Tracker: {best_torrent.get('trackers', 'unknown')[:20]}[/yellow]")

        if self.proxy_url:
            self.qbt_session = aiohttp.ClientSession()

        try:
            # Recheck the torrent
            if self.proxy_url:
                async with self.qbt_session.post(
                    f"{self.qbt_proxy_url}/api/v2/torrents/recheck",
                    data={'hashes': torrent_hash}
                ) as response:
                    if response.status != 200:
                        console.print(f"[bold red]Failed to recheck torrent via proxy: {response.status}")
                        return False
            else:
                self.qbt_client.torrents_recheck(torrent_hashes=torrent_hash)

            await asyncio.sleep(3)
        except Exception as e:
            console.print(f"[bold red]Failed to recheck torrent: {e}")
            return False

        try:
            while True:
                if self.proxy_url:
                    async with self.qbt_session.get(
                        f"{self.qbt_proxy_url}/api/v2/torrents/info",
                        params={'hashes': torrent_hash}
                    ) as response:
                        if response.status == 200:
                            torrents_data = await response.json()
                            if torrents_data:
                                torrent = torrents_data[0]
                                state = torrent.get('state')
                                progress = torrent.get('progress')
                            else:
                                raise Exception("No torrents found in response")
                        else:
                            console.print(f"[bold red]Failed to get torrent info via proxy: {response.status}")
                            return False
                else:
                    torrent_list = self.qbt_client.torrents_info(hashes=torrent_hash)
                    if isinstance(torrent_list, (list, tuple)) or getattr(torrent_list, "__class__", None).__name__ == "TorrentInfoList":
                        if len(torrent_list) > 0:
                            torrent = torrent_list[0]
                        else:
                            raise Exception("No torrents found in TorrentInfoList")
                    else:
                        torrent = torrent_list
                    state = torrent.state
                    progress = torrent.progress

                print(f"\r[INFO] Torrent is at {progress * 100:.2f}% progress of {state}...", end='', flush=True)

                if state not in ('checkingUP', 'checkingDL', 'checkingResumeData'):
                    print()
                    break

                await asyncio.sleep(check_interval)

            # Get final torrent info
            if self.proxy_url:
                async with self.qbt_session.get(
                    f"{self.qbt_proxy_url}/api/v2/torrents/info",
                    params={'hashes': torrent_hash}
                ) as response:
                    if response.status == 200:
                        torrents_data = await response.json()
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
                torrent_list = self.qbt_client.torrents_info(hashes=torrent_hash)
                if isinstance(torrent_list, (list, tuple)) or getattr(torrent_list, "__class__", None).__name__ == "TorrentInfoList":
                    if len(torrent_list) > 0:
                        torrent = torrent_list[0]
                    else:
                        raise Exception("No torrents found in TorrentInfoList")
                else:
                    torrent = torrent_list
                final_state = torrent.state
                final_progress = torrent.progress

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
