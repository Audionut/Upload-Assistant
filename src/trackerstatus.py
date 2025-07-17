import asyncio
import os
from torf import Torrent
from src.trackers.PTP import PTP
from src.trackersetup import TRACKER_SETUP, tracker_class_map, http_trackers
from src.console import console
from data.config import config
from src.clients import Clients
from src.uphelper import UploadHelper
from src.torrentcreate import create_base_from_existing_torrent
from src.dupe_checking import filter_dupes
from src.imdb import get_imdb_info_api
import cli_ui
import copy


async def process_all_trackers(meta):
    tracker_status = {}
    successful_trackers = 0
    client = Clients(config=config)
    tracker_setup = TRACKER_SETUP(config=config)
    helper = UploadHelper()
    meta_lock = asyncio.Lock()  # noqa F841
    for tracker in meta['trackers']:
        if 'tracker_status' not in meta:
            meta['tracker_status'] = {}
        if tracker not in meta['tracker_status']:
            meta['tracker_status'][tracker] = {}

    async def process_single_tracker(tracker_name, shared_meta):
        nonlocal successful_trackers
        local_meta = copy.deepcopy(shared_meta)  # Ensure each task gets its own copy of meta
        local_tracker_status = {'banned': False, 'skipped': False, 'dupe': False, 'upload': False}
        disctype = local_meta.get('disctype', None)

        if local_meta['name'].endswith('DUPE?'):
            local_meta['name'] = local_meta['name'].replace(' DUPE?', '')

        if tracker_name == "MANUAL":
            local_tracker_status['upload'] = True
            successful_trackers += 1

        if tracker_name in tracker_class_map:
            tracker_class = tracker_class_map[tracker_name](config=config)
            if tracker_name in http_trackers:
                await tracker_class.validate_credentials(meta)
            if tracker_name in {"THR", "PTP"}:
                if local_meta.get('imdb_id', 0) == 0:
                    while True:
                        if local_meta.get('unattended', False):
                            local_meta['imdb_id'] = 0
                            local_tracker_status['skipped'] = True
                            break

                        imdb_id = cli_ui.ask_string(
                            f"Unable to find IMDB id, please enter e.g.(tt1234567) or press Enter to skip uploading to {tracker_name}:"
                        )

                        if imdb_id is None or imdb_id.strip() == "":
                            local_meta['imdb_id'] = 0
                            break

                        imdb_id = imdb_id.strip().lower()
                        if imdb_id.startswith("tt") and imdb_id[2:].isdigit():
                            local_meta['imdb_id'] = int(imdb_id[2:])
                            local_meta['imdb'] = str(imdb_id[2:].zfill(7))
                            local_meta['imdb_info'] = await get_imdb_info_api(local_meta['imdb_id'], local_meta)
                            break
                        else:
                            cli_ui.error("Invalid IMDB ID format. Expected format: tt1234567")

            result = await tracker_setup.check_banned_group(tracker_class.tracker, tracker_class.banned_groups, local_meta)
            if result:
                local_tracker_status['banned'] = True
            else:
                local_tracker_status['banned'] = False

            if local_meta['tracker_status'][tracker_name].get('skip_upload'):
                local_tracker_status['skipped'] = True

            if not local_tracker_status['banned'] and not local_tracker_status['skipped']:
                if tracker_name == "AITHER":
                    if await tracker_setup.get_torrent_claims(local_meta, tracker_name):
                        local_tracker_status['skipped'] = True
                    else:
                        local_tracker_status['skipped'] = False

                if tracker_name not in {"PTP", "TL"} and not local_tracker_status['skipped']:
                    dupes = await tracker_class.search_existing(local_meta, disctype)
                elif tracker_name == "PTP":
                    ptp = PTP(config=config)
                    groupID = await ptp.get_group_by_imdb(local_meta['imdb'])
                    meta['ptp_groupID'] = groupID
                    dupes = await ptp.search_existing(groupID, local_meta, disctype)

                if tracker_name == "ASC" and meta.get('anon', 'false'):
                    console.print("PT: [yellow]Aviso: Você solicitou um upload anônimo, mas o ASC não suporta essa opção.[/yellow][red] O envio não será anônimo.[/red]")
                    console.print("EN: [yellow]Warning: You requested an anonymous upload, but ASC does not support this option.[/yellow][red] The upload will not be anonymous.[/red]")

                if ('skipping' not in local_meta or local_meta['skipping'] is None) and tracker_name != "TL":
                    dupes = await filter_dupes(dupes, local_meta, tracker_name)
                    local_meta, is_dupe = await helper.dupe_check(dupes, local_meta, tracker_name)
                    if is_dupe:
                        local_tracker_status['dupe'] = True
                elif 'skipping' in local_meta:
                    local_tracker_status['skipped'] = True

                if tracker_name == "MTV":
                    if not local_tracker_status['banned'] and not local_tracker_status['skipped'] and not local_tracker_status['dupe']:
                        tracker_config = config['TRACKERS'].get(tracker_name, {})
                        if str(tracker_config.get('skip_if_rehash', 'false')).lower() == "true":
                            torrent_path = os.path.abspath(f"{local_meta['base_dir']}/tmp/{local_meta['uuid']}/BASE.torrent")
                            if not os.path.exists(torrent_path):
                                check_torrent = await client.find_existing_torrent(local_meta)
                                if check_torrent:
                                    console.print(f"[yellow]Existing torrent found on {check_torrent}[yellow]")
                                    await create_base_from_existing_torrent(check_torrent, local_meta['base_dir'], local_meta['uuid'])
                                    torrent = Torrent.read(torrent_path)
                                    if torrent.piece_size > 8388608:
                                        console.print("[yellow]No existing torrent found with piece size lesser than 8MB[yellow]")
                                        local_tracker_status['skipped'] = True
                            elif os.path.exists(torrent_path):
                                torrent = Torrent.read(torrent_path)
                                if torrent.piece_size > 8388608:
                                    console.print("[yellow]Existing torrent found with piece size greater than 8MB[yellow]")
                                    local_tracker_status['skipped'] = True

                we_already_asked = local_meta.get('we_asked', False)

            if not local_meta['debug']:
                if not local_tracker_status['banned'] and not local_tracker_status['skipped'] and not local_tracker_status['dupe']:
                    if not local_meta.get('unattended', False):
                        console.print(f"[bold yellow]Tracker '{tracker_name}' passed all checks.")
                    if (
                        not local_meta['unattended']
                        or (local_meta['unattended'] and local_meta.get('unattended-confirm', False))
                    ) and not we_already_asked:
                        edit_choice = "y" if local_meta['unattended'] else input("Enter 'y' to upload, or press enter to skip uploading:")
                        if edit_choice.lower() == 'y':
                            local_tracker_status['upload'] = True
                            successful_trackers += 1
                        else:
                            local_tracker_status['upload'] = False
                    else:
                        local_tracker_status['upload'] = True
                        successful_trackers += 1
            else:
                local_tracker_status['upload'] = True
                successful_trackers += 1
            meta['we_asked'] = False

        return tracker_name, local_tracker_status

    if meta.get('unattended', False):
        searching_trackers = [name for name in meta['trackers'] if name in tracker_class_map]
        if searching_trackers:
            console.print(f"[yellow]Searching for existing torrents on: {', '.join(searching_trackers)}...")
        tasks = [process_single_tracker(tracker_name, meta) for tracker_name in meta['trackers']]
        results = await asyncio.gather(*tasks)

        # Collect passed trackers and skip reasons
        passed_trackers = []
        dupe_trackers = []
        skipped_trackers = []

        for tracker_name, status in results:
            tracker_status[tracker_name] = status
            if not status['banned'] and not status['skipped'] and not status['dupe']:
                passed_trackers.append(tracker_name)
            elif status['dupe']:
                dupe_trackers.append(tracker_name)
            elif status['skipped']:
                skipped_trackers.append(tracker_name)

        if skipped_trackers:
            console.print(f"[red]Trackers skipped due to conditions: [bold yellow]{', '.join(skipped_trackers)}[/bold yellow].")
        if dupe_trackers:
            console.print(f"[red]Found potential dupes on: [bold yellow]{', '.join(dupe_trackers)}[/bold yellow].")
        if passed_trackers:
            console.print(f"[bold green]Trackers passed all checks: [bold yellow]{', '.join(passed_trackers)}")
    else:
        passed_trackers = []
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
