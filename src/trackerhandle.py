import asyncio
import traceback
import cli_ui
from src.trackers.THR import THR
from src.trackers.PTP import PTP
from src.trackersetup import TRACKER_SETUP
from src.trackers.COMMON import COMMON
from src.manualpackage import package


async def check_mod_q_and_draft(tracker_class, meta, debug, disctype):
    tracker_capabilities = {
        'AITHER': {'mod_q': True, 'draft': False},
        'BHD': {'draft_live': True},
        'BLU': {'mod_q': True, 'draft': False},
        'LST': {'mod_q': True, 'draft': True}
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
    common = COMMON(config=config)
    tracker_setup = TRACKER_SETUP(config=config)
    enabled_trackers = tracker_setup.trackers_enabled(meta)

    async def process_single_tracker(tracker):
        if meta['name'].endswith('DUPE?'):
            meta['name'] = meta['name'].replace(' DUPE?', '')

        if meta['debug']:
            debug = "(DEBUG)"
        else:
            debug = ""
        disctype = meta.get('disctype', None)
        tracker = tracker.replace(" ", "").upper().strip()

        if tracker in api_trackers:
            tracker_class = tracker_class_map[tracker](config=config)
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
                        await tracker_class.upload(meta, disctype)
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        return
                    await client.add_to_client(meta, tracker_class.tracker)
                except Exception:
                    console.print(traceback.format_exc())
                    return

        elif tracker in other_api_trackers:
            tracker_class = tracker_class_map[tracker](config=config)
            tracker_status = meta.get('tracker_status', {})
            upload_status = tracker_status.get(tracker, {}).get('upload', False)
            if upload_status:
                try:
                    if tracker == "RTF":
                        await tracker_class.api_test(meta)
                    try:
                        await tracker_class.upload(meta, disctype)
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        return
                    if tracker == 'SN':
                        await asyncio.sleep(16)
                    await client.add_to_client(meta, tracker_class.tracker)
                except Exception:
                    console.print(traceback.format_exc())
                    return

        elif tracker in http_trackers:
            tracker_class = tracker_class_map[tracker](config=config)
            tracker_status = meta.get('tracker_status', {})
            upload_status = tracker_status.get(tracker, {}).get('upload', False)
            if upload_status:
                try:
                    if tracker == "AR":
                        await tracker_class.validate_credentials(meta) is True
                    try:
                        await tracker_class.upload(meta, disctype)
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        return
                    await client.add_to_client(meta, tracker_class.tracker)
                except Exception:
                    console.print(traceback.format_exc())
                    return

        elif tracker == "MANUAL":
            if meta['unattended']:
                do_manual = True
            else:
                do_manual = cli_ui.ask_yes_no("Get files for manual upload?", default=True)
            if do_manual:
                for manual_tracker in enabled_trackers:
                    if manual_tracker != 'MANUAL':
                        manual_tracker = manual_tracker.replace(" ", "").upper().strip()
                        tracker_class = tracker_class_map[manual_tracker](config=config)
                        if manual_tracker in api_trackers:
                            await common.unit3d_edit_desc(meta, tracker_class.tracker, tracker_class.signature)
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
                    await thr.upload(meta, disctype)
                except Exception as e:
                    console.print(f"[red]Upload failed: {e}")
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
                        await ptp.upload(meta, ptpUrl, ptpData, disctype)
                        await asyncio.sleep(5)
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        return
                    await client.add_to_client(meta, "PTP")
                except Exception:
                    console.print(traceback.format_exc())
                    return

    # Process each tracker sequentially
    for tracker in enabled_trackers:
        await process_single_tracker(tracker)
