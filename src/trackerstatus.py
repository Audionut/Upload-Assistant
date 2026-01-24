# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import copy
import os
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any, Optional, cast

import cli_ui
from torf import Torrent
from typing_extensions import TypeAlias

from src.cleanup import cleanup_manager
from src.clients import Clients
from src.console import console
from src.dupe_checking import DupeChecker
from src.imdb import imdb_manager
from src.torrentcreate import TorrentCreator
from src.trackers.PTP import PTP
from src.trackersetup import TRACKER_SETUP, tracker_class_map
from src.uphelper import UploadHelper

Meta: TypeAlias = MutableMapping[str, Any]


class TrackerStatusManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.trackers_config = cast(Mapping[str, Mapping[str, Any]], config.get('TRACKERS', {}))

    async def process_all_trackers(self, meta: Meta) -> int:
        tracker_status: dict[str, dict[str, bool]] = {}
        successful_trackers = 0
        client: Any = Clients(config=self.config)
        tracker_setup: Any = TRACKER_SETUP(config=self.config)
        helper: Any = UploadHelper(self.config)
        dupe_checker = DupeChecker(self.config)
        meta_lock = asyncio.Lock()
        for tracker in meta['trackers']:
            if 'tracker_status' not in meta:
                meta['tracker_status'] = {}
            if tracker not in meta['tracker_status']:
                meta['tracker_status'][tracker] = {}

        async def process_single_tracker(tracker_name: str, shared_meta: Meta) -> tuple[str, dict[str, bool]]:
            nonlocal successful_trackers
            local_meta = copy.deepcopy(shared_meta)  # Ensure each task gets its own copy of meta
            local_tracker_status = {'banned': False, 'skipped': False, 'dupe': False, 'upload': False, 'other': False}
            disctype = local_meta.get('disctype', None)
            we_already_asked = False

            if local_meta['name'].endswith('DUPE?'):
                local_meta['name'] = local_meta['name'].replace(' DUPE?', '')

            if tracker_name == "MANUAL":
                local_tracker_status['upload'] = True
                successful_trackers += 1

            if tracker_name in tracker_class_map:
                tracker_class: Any = tracker_class_map[tracker_name](config=self.config)
                if tracker_name in {"THR", "PTP"} and local_meta.get('imdb_id', 0) == 0:
                    while True:
                        if local_meta.get('unattended', False):
                            local_meta['imdb_id'] = 0
                            local_tracker_status['skipped'] = True
                            break
                        try:
                            imdb_id = cli_ui.ask_string(
                                f"Unable to find IMDB id, please enter e.g.(tt1234567) or press Enter to skip uploading to {tracker_name}:"
                            )
                        except EOFError:
                            console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                            await cleanup_manager.cleanup()
                            cleanup_manager.reset_terminal()
                            sys.exit(1)

                        if imdb_id is None or imdb_id.strip() == "":
                            local_meta['imdb_id'] = 0
                            break

                        imdb_id = imdb_id.strip().lower()
                        if imdb_id.startswith("tt") and imdb_id[2:].isdigit():
                            local_meta['imdb_id'] = int(imdb_id[2:])
                            local_meta['imdb'] = str(imdb_id[2:].zfill(7))
                            local_meta['imdb_info'] = await imdb_manager.get_imdb_info_api(
                                local_meta['imdb_id'],
                                manual_language=local_meta.get('manual_language'),
                                debug=bool(local_meta.get('debug', False)),
                            )
                            break
                        else:
                            cli_ui.error("Invalid IMDB ID format. Expected format: tt1234567")

                result = await tracker_setup.check_banned_group(tracker_class.tracker, tracker_class.banned_groups, local_meta)
                local_tracker_status['banned'] = bool(result)

                if local_meta['tracker_status'][tracker_name].get('skip_upload'):
                    local_tracker_status['skipped'] = True
                elif 'skipped' not in local_meta:
                    local_tracker_status['skipped'] = False

                if not local_tracker_status['banned'] and not local_tracker_status['skipped']:
                    claimed = await tracker_setup.get_torrent_claims(local_meta, tracker_name)
                    local_tracker_status['skipped'] = bool(claimed)

                    if tracker_name not in {"PTP"} and not local_tracker_status['skipped']:
                        dupes: list[Any] = cast(list[Any], await tracker_class.search_existing(local_meta, disctype))
                        # set trackers here so that they are not double checked later with cross seeding
                        async with meta_lock:
                            meta.setdefault('dupe_checked_trackers', []).append(tracker_name)
                        if local_meta['tracker_status'][tracker_name].get('other', False):
                            local_tracker_status['other'] = True
                    elif tracker_name == "PTP":
                        ptp: Any = PTP(config=self.config)
                        groupID = await ptp.get_group_by_imdb(local_meta['imdb'])
                        async with meta_lock:
                            meta['ptp_groupID'] = groupID
                        dupes = cast(list[Any], await ptp.search_existing(groupID or "", cast(dict[str, Any], local_meta), disctype))
                    else:
                        dupes = []

                    if tracker_name == "ASC" and meta.get('anon', 'false'):
                        console.print("PT: [yellow]Aviso: Você solicitou um upload anônimo, mas o ASC não suporta essa opção.[/yellow][red] O envio não será anônimo.[/red]")
                        console.print("EN: [yellow]Warning: You requested an anonymous upload, but ASC does not support this option.[/yellow][red] The upload will not be anonymous.[/red]")

                    if ('skipping' not in local_meta or local_meta['skipping'] is None) and not local_tracker_status['skipped']:
                        dupes = cast(list[Any], await dupe_checker.filter_dupes(dupes, local_meta, tracker_name))

                        matched_episode_ids = local_meta.get('matched_episode_ids', [])
                        trumpable_id = local_meta.get('trumpable_id')
                        cross_seed_key = f'{tracker_name}_cross_seed'
                        cross_seed_value = local_meta.get(cross_seed_key) if cross_seed_key in local_meta else None

                        # Only shared-state writes go under the lock
                        async with meta_lock:
                            if matched_episode_ids:
                                meta['matched_episode_ids'] = matched_episode_ids
                            if trumpable_id:
                                meta['trumpable_id'] = trumpable_id
                            if cross_seed_key in local_meta:
                                meta[cross_seed_key] = cross_seed_value

                        is_dupe, local_meta = await helper.dupe_check(dupes, local_meta, tracker_name)
                        if is_dupe:
                            local_tracker_status['dupe'] = True

                        if tracker_name in ["AITHER", "LST"]:
                            were_trumping = local_meta.get('were_trumping', False)
                            trump_reason = local_meta.get('trump_reason')
                            trumpable_id_after_dupe_check = local_meta.get('trumpable_id')
                            async with meta_lock:
                                if were_trumping:
                                    meta['were_trumping'] = were_trumping
                                if trump_reason:
                                    meta['trump_reason'] = trump_reason
                                if trumpable_id_after_dupe_check:
                                    meta['trumpable_id'] = trumpable_id_after_dupe_check

                    elif 'skipping' in local_meta:
                        local_tracker_status['skipped'] = True

                    if tracker_name == "MTV" and not local_tracker_status['banned'] and not local_tracker_status['skipped'] and not local_tracker_status['dupe']:
                        tracker_config = self.trackers_config.get(tracker_name, {})
                        if str(tracker_config.get('skip_if_rehash', 'false')).lower() == "true":
                            torrent_path = os.path.abspath(f"{local_meta['base_dir']}/tmp/{local_meta['uuid']}/BASE.torrent")
                            if not os.path.exists(torrent_path):
                                check_torrent = await client.find_existing_torrent(cast(dict[str, Any], local_meta))
                                if check_torrent:
                                    console.print(f"[yellow]Existing torrent found on {check_torrent}[yellow]")
                                    await TorrentCreator.create_base_from_existing_torrent(check_torrent, local_meta['base_dir'], local_meta['uuid'])
                                    torrent = Torrent.read(torrent_path)
                                    if torrent.piece_size > 8388608:
                                        console.print("[yellow]No existing torrent found with piece size lesser than 8MB[yellow]")
                                        local_tracker_status['skipped'] = True
                            elif os.path.exists(torrent_path):
                                torrent = Torrent.read(torrent_path)
                                if torrent.piece_size > 8388608:
                                    console.print("[yellow]Existing torrent found with piece size greater than 8MB[yellow]")
                                    local_tracker_status['skipped'] = True

                    we_already_asked = bool(local_meta.get('we_asked', False))

                if not local_meta['debug']:
                    if not local_tracker_status['banned'] and not local_tracker_status['skipped'] and not local_tracker_status['dupe']:
                        if not local_meta.get('unattended', False):
                            console.print(f"[bold yellow]Tracker '{tracker_name}' passed all checks.")
                        if (
                            not local_meta['unattended']
                            or (local_meta['unattended'] and local_meta.get('unattended_confirm', False))
                        ) and not we_already_asked:
                            try:
                                tracker_rename = await tracker_class.get_name(meta)
                            except Exception:
                                try:
                                    tracker_rename = await tracker_class.edit_name(meta)
                                except Exception:
                                    tracker_rename = None

                            display_name: Optional[str] = None
                            if tracker_rename is not None:
                                if isinstance(tracker_rename, dict) and 'name' in tracker_rename:
                                    display_name = cast(str, tracker_rename['name'])
                                elif isinstance(tracker_rename, str):
                                    display_name = tracker_rename

                            if display_name is not None and display_name != "" and display_name != meta['name']:
                                console.print(f"[bold yellow]{tracker_name} applies a naming change for this release: [green]{display_name}[/green][/bold yellow]")
                            try:
                                edit_choice = "y" if local_meta['unattended'] else input("Enter 'y' to upload, or press enter to skip uploading:")
                                if edit_choice.lower() == 'y':
                                    local_tracker_status['upload'] = True
                                    successful_trackers += 1
                                else:
                                    local_tracker_status['upload'] = False
                            except EOFError:
                                console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                                await cleanup_manager.cleanup()
                                cleanup_manager.reset_terminal()
                                sys.exit(1)
                        else:
                            local_tracker_status['upload'] = True
                            successful_trackers += 1
                else:
                    local_tracker_status['upload'] = True
                    successful_trackers += 1

            return tracker_name, local_tracker_status

        if meta.get('unattended', False):
            searching_trackers: list[str] = [name for name in meta['trackers'] if name in tracker_class_map]
            if searching_trackers:
                console.print(f"[yellow]Searching for existing torrents on: {', '.join(searching_trackers)}...")
            tasks = [process_single_tracker(tracker_name, meta) for tracker_name in meta['trackers']]
            results = await asyncio.gather(*tasks)

            # Collect passed trackers and skip reasons
            passed_trackers: list[str] = []
            dupe_trackers: list[str] = []
            skipped_trackers: list[str] = []

            for tracker_name, status in results:
                tracker_status[tracker_name] = status
                if not status['banned'] and not status['skipped'] and not status['dupe']:
                    passed_trackers.append(tracker_name)
                elif status['dupe']:
                    dupe_trackers.append(tracker_name)
                elif status['skipped']:
                    skipped_trackers.append(tracker_name)

            if skipped_trackers:
                console.print(f"[red]Skipped due to specific tracker conditions: [bold yellow]{', '.join(skipped_trackers)}[/bold yellow].")
            if dupe_trackers:
                console.print(f"[red]Found potential dupes on: [bold yellow]{', '.join(dupe_trackers)}[/bold yellow].")
            if passed_trackers:
                console.print(f"[bold green]Trackers passed all checks: [bold yellow]{', '.join(passed_trackers)}")
        else:
            passed_trackers: list[str] = []
            for tracker_name in meta['trackers']:
                if tracker_name in tracker_class_map:
                    console.print(f"[yellow]Searching for existing torrents on {tracker_name}...")
                tracker_name, status = await process_single_tracker(tracker_name, meta)
                tracker_status[tracker_name] = status
                if not status['banned'] and not status['skipped'] and not status['dupe']:
                    passed_trackers.append(tracker_name)

        if meta['debug']:
            console.print("\n[bold]Tracker Processing Summary:[/bold]")
            for t_name, status in tracker_status.items():
                banned_status = 'Yes' if status['banned'] else 'No'
                skipped_status = 'Yes' if status['skipped'] else 'No'
                dupe_status = 'Yes' if status['dupe'] else 'No'
                upload_status = 'Yes' if status['upload'] else 'No'
                console.print(f"Tracker: {t_name} | Banned: {banned_status} | Skipped: {skipped_status} | Dupe: {dupe_status} | [yellow]Upload:[/yellow] {upload_status}")
            console.print(f"\n[bold]Trackers Passed all Checks:[/bold] {successful_trackers}")
            print()
            console.print("[bold red]DEBUG MODE does not upload to sites")

        meta['tracker_status'] = tracker_status
        return successful_trackers


async def process_all_trackers(meta: Meta, config: dict[str, Any]) -> int:
    return await TrackerStatusManager(config=config).process_all_trackers(meta)
