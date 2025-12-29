# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import cli_ui
import sys
import traceback
import time

from cogs.redaction import redact_private_info
from src.cleanup import cleanup, reset_terminal
from src.get_desc import DescriptionBuilder
from src.manualpackage import package
from src.trackers.PTP import PTP
from src.trackers.THR import THR
from src.trackersetup import TRACKER_SETUP


async def check_mod_q_and_draft(tracker_class, meta, debug, disctype):
    tracker_capabilities = {
        'AITHER': {'mod_q': True, 'draft': False},
        'BHD': {'draft_live': True},
        'BLU': {'mod_q': True, 'draft': False},
        'LST': {'mod_q': True, 'draft': True},
        'LT': {'mod_q': True, 'draft': False}
    }

    modq, draft = None, None
    tracker_caps = tracker_capabilities.get(tracker_class.tracker, {})
    if tracker_class.tracker == 'BHD' and tracker_caps.get('draft_live'):
        draft_int = await tracker_class.get_live(meta)
        draft = "Draft" if draft_int == 0 else "Live"

    else:
        if tracker_caps.get('mod_q'):
            modq = await tracker_class.get_flag(meta, 'modq')
            modq = 'Yes' if modq else 'No'
        if tracker_caps.get('draft'):
            draft = await tracker_class.get_flag(meta, 'draft')
            draft = 'Yes' if draft else 'No'

    return modq, draft


async def process_trackers(meta, config, client, console, api_trackers, tracker_class_map, http_trackers, other_api_trackers):
    tracker_setup = TRACKER_SETUP(config=config)
    enabled_trackers = tracker_setup.trackers_enabled(meta)

    async def process_single_tracker(tracker):
        if not tracker == "MANUAL":
            tracker_class = tracker_class_map[tracker](config=config)
        if meta['name'].endswith('DUPE?'):
            meta['name'] = meta['name'].replace(' DUPE?', '')

        if meta['debug']:
            debug = "(DEBUG)"
        else:
            debug = ""
        disctype = meta.get('disctype', None)
        tracker = tracker.replace(" ", "").upper().strip()

        if tracker in api_trackers:
            tracker_status = meta.get('tracker_status', {})
            upload_status = tracker_status.get(tracker, {}).get('upload', False)
            if upload_status:
                try:
                    modq, draft = await check_mod_q_and_draft(tracker_class, meta, debug, disctype)
                    if modq == "Yes":
                        console.print(f"(modq: {modq})")
                    if draft == "Yes":
                        console.print(f"(draft: {draft})")
                    try:
                        upload_start_time = time.time()
                        await tracker_class.upload(meta, disctype)
                        upload_duration = time.time() - upload_start_time
                        meta[f'{tracker}_upload_duration'] = upload_duration
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        console.print(traceback.format_exc())
                        return
                except Exception:
                    console.print(traceback.format_exc())
                    return
                status = meta.get('tracker_status', {}).get(tracker_class.tracker, {})
                if 'status_message' in status and "data error" not in str(status['status_message']):
                    await client.add_to_client(meta, tracker_class.tracker)

        elif tracker in other_api_trackers:
            tracker_status = meta.get('tracker_status', {})
            upload_status = tracker_status.get(tracker, {}).get('upload', False)
            if upload_status:
                try:
                    try:
                        upload_start_time = time.time()
                        await tracker_class.upload(meta, disctype)
                        upload_duration = time.time() - upload_start_time
                        meta[f'{tracker}_upload_duration'] = upload_duration
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        console.print(traceback.format_exc())
                        return
                    if tracker == 'SN':
                        await asyncio.sleep(16)
                except Exception:
                    console.print(traceback.format_exc())
                    return
                status = meta.get('tracker_status', {}).get(tracker_class.tracker, {})
                if 'status_message' in status and "data error" not in str(status['status_message']):
                    await client.add_to_client(meta, tracker_class.tracker)

        elif tracker in http_trackers:
            tracker_status = meta.get('tracker_status', {})
            upload_status = tracker_status.get(tracker, {}).get('upload', False)
            if upload_status:
                try:
                    try:
                        upload_start_time = time.time()
                        await tracker_class.upload(meta, disctype)
                        upload_duration = time.time() - upload_start_time
                        meta[f'{tracker}_upload_duration'] = upload_duration
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        console.print(traceback.format_exc())
                        return

                except Exception:
                    console.print(traceback.format_exc())
                    return
                status = meta.get('tracker_status', {}).get(tracker_class.tracker, {})
                if 'status_message' in status and "data error" not in str(status['status_message']):
                    await client.add_to_client(meta, tracker_class.tracker)

        elif tracker == "MANUAL":
            if meta['unattended']:
                do_manual = True
            else:
                try:
                    do_manual = cli_ui.ask_yes_no("Get files for manual upload?", default=True)
                except EOFError:
                    console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                    await cleanup()
                    reset_terminal()
                    sys.exit(1)
            if do_manual:
                for manual_tracker in enabled_trackers:
                    if manual_tracker != 'MANUAL':
                        manual_tracker = manual_tracker.replace(" ", "").upper().strip()
                        tracker_class = tracker_class_map[manual_tracker](config=config)
                        if manual_tracker in api_trackers:
                            await DescriptionBuilder(config).unit3d_edit_desc(meta, tracker_class.tracker, tracker_class.signature)
                        else:
                            await tracker_class.edit_desc(meta)
                url = await package(meta)
                if url is False:
                    console.print(f"[yellow]Unable to upload prep files, they can be found at `tmp/{meta['uuid']}")
                else:
                    console.print(f"[green]{meta['name']}")
                    console.print(f"[green]Files can be found at: [yellow]{url}[/yellow]")

        elif tracker == "THR":
            tracker_status = meta.get('tracker_status', {})
            upload_status = tracker_status.get(tracker, {}).get('upload', False)
            if upload_status:
                thr = THR(config=config)
                try:
                    upload_start_time = time.time()
                    await thr.upload(meta, disctype)
                    upload_duration = time.time() - upload_start_time
                    meta[f'{tracker}_upload_duration'] = upload_duration
                except Exception as e:
                    console.print(f"[red]Upload failed: {e}")
                    console.print(traceback.format_exc())
                    return
                await client.add_to_client(meta, "THR")

        elif tracker == "PTP":
            tracker_status = meta.get('tracker_status', {})
            upload_status = tracker_status.get(tracker, {}).get('upload', False)
            if upload_status:
                try:
                    ptp = PTP(config=config)
                    groupID = meta.get('ptp_groupID', None)
                    ptpUrl, ptpData = await ptp.fill_upload_form(groupID, meta)
                    try:
                        upload_start_time = time.time()
                        await ptp.upload(meta, ptpUrl, ptpData, disctype)
                        upload_duration = time.time() - upload_start_time
                        meta[f'{tracker}_upload_duration'] = upload_duration
                        await asyncio.sleep(5)
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        console.print(traceback.format_exc())
                        return
                    await client.add_to_client(meta, "PTP")
                except Exception:
                    console.print(traceback.format_exc())
                    return

    multi_screens = int(config['DEFAULT'].get('multiScreens', 2))
    discs = meta.get('discs', [])
    one_disc = True
    if discs and len(discs) == 1:
        one_disc = True
    elif discs and len(discs) > 1:
        one_disc = False

    if (not meta.get('tv_pack') and one_disc) or multi_screens == 0:
        # Run all tracker tasks concurrently with individual error handling
        tasks = []
        for tracker in enabled_trackers:
            task = asyncio.create_task(process_single_tracker(tracker))
            tasks.append((tracker, task))

        # Wait for all tasks to complete, but don't let one tracker's failure stop others
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

        # Log any exceptions that occurred
        for (tracker, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                console.print(f"[red]{tracker} encountered an error: {result}[/red]")
                if meta.get('debug'):
                    console.print(traceback.format_exception(type(result), result, result.__traceback__))
    else:
        # Process each tracker sequentially
        for tracker in enabled_trackers:
            await process_single_tracker(tracker)

    try:
        if meta.get('print_tracker_messages', False):
            for tracker, status in meta.get('tracker_status', {}).items():
                try:
                    if 'status_message' in status:
                        message = f"{tracker}: {redact_private_info(status['status_message'])}"
                        if config["DEFAULT"].get("show_upload_duration", False) or meta.get('upload_timer', False):
                            duration = meta.get(f'{tracker}_upload_duration')
                            if duration and isinstance(duration, (int, float)):
                                color = "#21ff00" if duration < 5 else "#9fd600" if duration < 10 else "#cfaa00" if duration < 15 else "#f17100" if duration < 20 else "#ff0000"
                                message += f" [[{color}]{duration:.2f}s[/{color}]]"
                        console.print(message)
                except Exception as e:
                    console.print(f"[red]Error printing {tracker} status message: {e}[/red]")
        elif not meta.get('print_tracker_links', True):
            console.print("[green]All tracker uploads processed.[/green]")
    except Exception as e:
        console.print(f"[red]Error printing tracker messages: {e}[/red]")
        pass
    if meta.get('print_tracker_links', True):
        try:
            for tracker, status in meta.get('tracker_status', {}).items():
                try:
                    message = None
                    if tracker == "MTV" and 'status_message' in status and "data error" not in str(status['status_message']):
                        message = f"[green]{str(status['status_message'])}[/green]"
                    if 'torrent_id' in status:
                        tracker_class = tracker_class_map[tracker](config=config)
                        torrent_url = tracker_class.torrent_url
                        message = f"[green]{torrent_url}{status['torrent_id']}[/green]"
                    else:
                        if (
                            'status_message' in status
                            and 'torrent_id' not in status
                            and "data error" not in str(status['status_message'])
                            and tracker != "MTV"
                        ):
                            message = f"{tracker}: {redact_private_info(status['status_message'])}"
                        elif 'status_message' in status and "data error" in str(status['status_message']):
                            console.print(f"[red]{tracker}: {str(status['status_message'])}[/red]")
                        else:
                            if 'skipping' in status and not status['skipping']:
                                console.print(f"[red]{tracker} gave no useful message.")
                    if message is not None:
                        if config["DEFAULT"].get("show_upload_duration", False) or meta.get('upload_timer', False):
                            duration = meta.get(f'{tracker}_upload_duration')
                            if duration and isinstance(duration, (int, float)):
                                color = "#21ff00" if duration < 5 else "#9fd600" if duration < 10 else "#cfaa00" if duration < 15 else "#f17100" if duration < 20 else "#ff0000"
                                message += f" [[{color}]{duration:.2f}s[/{color}]]"
                        console.print(message)
                except Exception as e:
                    console.print(f"[red]Error printing {tracker} data: {e}[/red]")
            console.print("[green]All tracker uploads processed.[/green]")
        except Exception as e:
            console.print(f"[red]Error in tracker print loop: {e}[/red]")
            pass
