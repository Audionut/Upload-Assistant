# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import os
import sys
import time
import traceback
from collections.abc import Mapping, Sequence
from typing import Any, Optional, cast

import aiofiles
import cli_ui
from typing_extensions import TypeAlias

from cogs.redaction import Redaction
from src.cleanup import cleanup_manager
from src.get_desc import DescriptionBuilder
from src.manualpackage import ManualPackageManager
from src.trackers.PTP import PTP
from src.trackers.THR import THR
from src.trackersetup import TRACKER_SETUP

Meta: TypeAlias = dict[str, Any]
StatusDict: TypeAlias = dict[str, Any]


def check_mod_q_and_draft(
    tracker_class: Any,
    meta: Meta,
) -> tuple[Optional[str], Optional[str], dict[str, Any]]:
    tracker_capabilities = {
        'A4K': {'mod_q': True, 'draft': False},
        'AITHER': {'mod_q': True, 'draft': False},
        'BHD': {'draft_live': True},
        'BLU': {'mod_q': True, 'draft': False},
        'LST': {'mod_q': True, 'draft': True},
        'LT': {'mod_q': True, 'draft': False},
        'LUME': {'mod_q': True, 'draft': False},
    }

    modq, draft = None, None
    tracker_caps = tracker_capabilities.get(tracker_class.tracker, {})
    if tracker_class.tracker == 'BHD' and tracker_caps.get('draft_live'):
        draft_int = tracker_class.get_live(meta)
        draft = "Draft" if draft_int == 0 else "Live"

    else:
        if tracker_caps.get('mod_q'):
            modq_flag = tracker_class.get_flag(meta, 'modq')
            modq_enabled = str(modq_flag).lower() in ["1", "true", "yes"]
            modq = 'Yes' if modq_enabled else 'No'
        if tracker_caps.get('draft'):
            draft_flag = tracker_class.get_flag(meta, 'draft')
            draft_enabled = str(draft_flag).lower() in ["1", "true", "yes"]
            draft = 'Yes' if draft_enabled else 'No'

    return modq, draft, tracker_caps


async def process_trackers(
    meta: Meta,
    config: dict[str, Any],
    client: Any,
    console: Any,
    api_trackers: Sequence[str],
    tracker_class_map: Mapping[str, Any],
    http_trackers: Sequence[str],
    other_api_trackers: Sequence[str],
    http_client: Any = None,
) -> None:
    tracker_setup = TRACKER_SETUP(config=config, http_client=http_client)
    tracker_setup_any = cast(Any, tracker_setup)
    enabled_trackers = list(cast(Sequence[str], tracker_setup_any.trackers_enabled(meta)))
    manual_packager = ManualPackageManager(config)
    timing_enabled = True

    unit3d_trackers = {
        "A4K",
        "AITHER",
        "BLU",
        "CBR",
        "DP",
        "EMUW",
        "FRIKI",
        "FNP",
        "HHD",
        "HUNO",
        "IHD",
        "ITT",
        "LCD",
        "LDU",
        "LUME",
        "LST",
        "LT",
        "OE",
        "OTW",
        "PT",
        "PTT",
        "R4E",
        "RAS",
        "RF",
        "SAM",
        "SHRI",
        "SP",
        "STC",
        "TIK",
        "TLZ",
        "TOS",
        "TTR",
        "ULCX",
        "UTP",
        "YOINK",
        "YUS",
    }


    tracker_status = cast(StatusDict, meta.get('tracker_status') or {})
    active_trackers: list[str] = []
    skipped_trackers: list[str] = []
    for tracker in enabled_trackers:
        if tracker == "MANUAL":
            active_trackers.append(tracker)
            continue
        upload_status = cast(Mapping[str, Any], tracker_status.get(tracker, {})).get('upload', False)
        if upload_status:
            active_trackers.append(tracker)
        else:
            skipped_trackers.append(tracker)

    if skipped_trackers:
        console.print(f"[cyan]Skipping tracker tasks (upload disabled): {', '.join(skipped_trackers)}[/cyan]")

    def log_timing(tracker: str, label: str, start_time: Optional[float] = None) -> None:
        if not timing_enabled:
            return
        elapsed = None
        if start_time is not None:
            elapsed = time.perf_counter() - start_time
        if elapsed is not None:
            console.print(f"[cyan]{tracker} timing: {label} {elapsed:.2f}s[/cyan]")
        else:
            console.print(f"[cyan]{tracker} timing: {label}[/cyan]")

    async def preload_nfo(meta: Meta) -> None:
        if meta.get("cached_nfo_bytes") is not None or meta.get("cached_nfo_missing") is True:
            return
        base_dir = meta.get("base_dir")
        uuid = meta.get("uuid")
        if not base_dir or not uuid:
            return

        def list_nfo_files(directory: str) -> list[str]:
            files: list[str] = []
            try:
                entries = os.listdir(directory)
            except OSError:
                return files
            for entry in entries:
                if not entry.lower().endswith(".nfo"):
                    continue
                absolute_path = os.path.join(directory, entry)
                if os.path.isfile(absolute_path):
                    files.append(absolute_path)
            return files

        tmp_dir = os.path.join(base_dir, "tmp", uuid)
        nfo_files = await asyncio.to_thread(list_nfo_files, tmp_dir)

        if (
            not nfo_files
            and meta.get("keep_nfo", False)
            and (meta.get("keep_folder", False) or meta.get("isdir", False))
        ):
            search_dir = os.path.dirname(cast(str, meta.get("path", "")))
            if search_dir:
                nfo_files = await asyncio.to_thread(list_nfo_files, search_dir)

        if nfo_files:
            async with aiofiles.open(nfo_files[0], "rb") as f:
                nfo_bytes = await f.read()
            meta["cached_nfo_bytes"] = nfo_bytes
            meta["cached_nfo_name"] = os.path.basename(nfo_files[0])
        else:
            meta["cached_nfo_missing"] = True

    async def preload_mediainfo(meta: Meta) -> None:
        if meta.get("cached_mediainfo_bytes") is not None or meta.get("cached_mediainfo_missing") is True:
            return
        base_dir = meta.get("base_dir")
        uuid = meta.get("uuid")
        if not base_dir or not uuid:
            return

        mediainfo_path = os.path.join(base_dir, "tmp", uuid, "MEDIAINFO_CLEANPATH.txt")
        try:
            if os.path.isfile(mediainfo_path):
                async with aiofiles.open(mediainfo_path, "rb") as f:
                    mediainfo_bytes = await f.read()
                meta["cached_mediainfo_bytes"] = mediainfo_bytes
            else:
                meta["cached_mediainfo_missing"] = True
        except OSError:
            meta["cached_mediainfo_missing"] = True

    async def preload_bdinfo(meta: Meta) -> None:
        if meta.get("cached_bdinfo_bytes") is not None or meta.get("cached_bdinfo_missing") is True:
            return
        base_dir = meta.get("base_dir")
        uuid = meta.get("uuid")
        if not base_dir or not uuid:
            return

        bdinfo_path = os.path.join(base_dir, "tmp", uuid, "BD_SUMMARY_00.txt")
        try:
            if os.path.isfile(bdinfo_path):
                async with aiofiles.open(bdinfo_path, "rb") as f:
                    bdinfo_bytes = await f.read()
                meta["cached_bdinfo_bytes"] = bdinfo_bytes
            else:
                meta["cached_bdinfo_missing"] = True
        except OSError:
            meta["cached_bdinfo_missing"] = True

    base_torrent_bytes: Optional[bytes] = None
    if active_trackers:
        try:
            preload_start = time.perf_counter()
            torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"
            async with aiofiles.open(torrent_file_path, "rb") as f:
                base_torrent_bytes = await f.read()
            log_timing("TRACKERS", "preload BASE.torrent", preload_start)
        except Exception as e:
            console.print(f"[yellow]Warning: Unable to preload BASE.torrent for tracker uploads: {e}[/yellow]")
            base_torrent_bytes = None

    if any(tracker in unit3d_trackers for tracker in active_trackers):
        try:
            nfo_start = time.perf_counter()
            await preload_nfo(meta)
            if meta.get("cached_nfo_bytes") is not None:
                log_timing("UNIT3D", "preload NFO (found)", nfo_start)
            elif meta.get("cached_nfo_missing") is True:
                log_timing("UNIT3D", "preload NFO (missing)", nfo_start)
            else:
                log_timing("UNIT3D", "preload NFO", nfo_start)
        except Exception as e:
            console.print(f"[yellow]Warning: Unable to preload NFO for UNIT3D uploads: {e}[/yellow]")

        try:
            mediainfo_start = time.perf_counter()
            await preload_mediainfo(meta)
            if meta.get("cached_mediainfo_bytes") is not None:
                log_timing("UNIT3D", "preload MEDIAINFO (found)", mediainfo_start)
            elif meta.get("cached_mediainfo_missing") is True:
                log_timing("UNIT3D", "preload MEDIAINFO (missing)", mediainfo_start)
            else:
                log_timing("UNIT3D", "preload MEDIAINFO", mediainfo_start)
        except Exception as e:
            console.print(f"[yellow]Warning: Unable to preload MEDIAINFO for UNIT3D uploads: {e}[/yellow]")

        try:
            bdinfo_start = time.perf_counter()
            await preload_bdinfo(meta)
            if meta.get("cached_bdinfo_bytes") is not None:
                log_timing("UNIT3D", "preload BDINFO (found)", bdinfo_start)
            elif meta.get("cached_bdinfo_missing") is True:
                log_timing("UNIT3D", "preload BDINFO (missing)", bdinfo_start)
            else:
                log_timing("UNIT3D", "preload BDINFO", bdinfo_start)
        except Exception as e:
            console.print(f"[yellow]Warning: Unable to preload BDINFO for UNIT3D uploads: {e}[/yellow]")

    def print_tracker_result(
        tracker: str,
        tracker_class: Any,
        status: Mapping[str, Any],
        is_success: bool,
    ) -> None:
        """Print tracker upload result immediately after upload completes."""
        try:
            # Check config settings for what to print
            print_links = meta.get('print_tracker_links', True)
            print_messages = meta.get('print_tracker_messages', False)

            # If neither option is enabled, don't print anything
            if not print_links and not print_messages:
                return

            message = None
            if is_success:
                if tracker == "MTV" and 'status_message' in status and "data error" not in str(status['status_message']):
                    if print_links:
                        message = f"[green]{str(status['status_message'])}[/green]"
                elif 'torrent_id' in status and print_links:
                    torrent_url = str(getattr(tracker_class, "torrent_url", ""))
                    message = f"[green]{torrent_url}{status['torrent_id']}[/green]"
                elif (
                    'status_message' in status
                    and "data error" not in str(status['status_message'])
                    and (print_messages or (print_links and 'torrent_id' not in status))
                ):
                    message = f"{tracker}: {Redaction.redact_private_info(status['status_message'])}"
            else:
                if 'status_message' in status and "data error" in str(status['status_message']):
                    console.print(f"[red]{tracker}: {str(status['status_message'])}[/red]")
                    return

            if message is not None:
                if config["DEFAULT"].get("show_upload_duration", True) or meta.get('upload_timer', True):
                    duration = meta.get(f'{tracker}_upload_duration')
                    if duration and isinstance(duration, (int, float)):
                        color = "#21ff00" if duration < 5 else "#9fd600" if duration < 10 else "#cfaa00" if duration < 15 else "#f17100" if duration < 20 else "#ff0000"
                        message += f" [[{color}]{duration:.2f}s[/{color}]]"
                console.print(message)
        except Exception as e:
            console.print(f"[red]Error printing {tracker} result: {e}[/red]")

    async def process_single_tracker(tracker: str) -> None:
        tracker_class: Any = None
        tracker_timings: dict[str, float] = {}
        tracker_start_time = time.perf_counter()
        log_timing(tracker, "tracker task start")
        if tracker not in {"MANUAL", "THR", "PTP"}:
            # Try to pass http_client to UNIT3D-based trackers, fall back otherwise
            if tracker in ["A4K", "AITHER", "BLU", "CBR", "DP", "EMUW", "FRIKI", "FNP", "HHD", "HUNO", "IHD", "ITT", "LCD", "LDU", "LUME", "LST", "LT", "OE", "OTW", "PT", "PTT", "R4E", "RAS", "RF", "SAM", "SHRI", "SP", "STC", "TIK", "TLZ", "TOS", "TTR", "ULCX", "UTP", "YOINK", "YUS"]:
                try:
                    tracker_class = tracker_class_map[tracker](config=config, http_client=http_client)
                except TypeError:
                    tracker_class = tracker_class_map[tracker](config=config)
            else:
                tracker_class = tracker_class_map[tracker](config=config)
        if str(meta.get('name', '')).endswith('DUPE?'):
            meta['name'] = str(meta.get('name', '')).replace(' DUPE?', '')

        disctype = cast(Optional[str], meta.get('disctype'))
        disctype_value = str(disctype) if disctype is not None else ""
        tracker = tracker.replace(" ", "").upper().strip()

        if tracker in api_trackers:
            tracker_status = cast(StatusDict, meta.get('tracker_status') or {})
            upload_status = cast(Mapping[str, Any], tracker_status.get(tracker, {})).get('upload', False)
            if upload_status:
                try:
                    modq, draft, tracker_caps = check_mod_q_and_draft(tracker_class, meta)
                    if tracker_caps.get('mod_q') and modq == "Yes":
                        console.print(f"{tracker} (modq: {modq})")
                    if (tracker_caps.get('draft') or tracker_caps.get('draft_live')) and draft in ["Yes", "Draft"]:
                        console.print(f"{tracker} (draft: {draft})")
                    if tracker == "TOS" and meta.get('keep_nfo', False):
                        await tracker_class.tos_rehash(meta)
                    is_uploaded = False
                    try:
                        upload_start_time = time.time()
                        upload_perf_start = time.perf_counter()
                        log_timing(tracker, "upload() start")
                        is_uploaded = await tracker_class.upload(meta, disctype_value, base_torrent_bytes)
                        upload_duration = time.time() - upload_start_time
                        meta[f'{tracker}_upload_duration'] = upload_duration
                        log_timing(tracker, "upload() end", upload_perf_start)
                        tracker_timings["upload"] = time.perf_counter() - upload_perf_start
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        console.print(traceback.format_exc())
                        return
                except Exception:
                    console.print(traceback.format_exc())
                    return

                if is_uploaded is None:
                    console.print(f"[yellow]Warning: {tracker_class.tracker} upload method returned None instead of boolean. Treating as failed upload.[/yellow]")
                    is_uploaded = False

                status = cast(StatusDict, meta.get('tracker_status') or {}).get(tracker_class.tracker, {})
                if is_uploaded and 'status_message' in status and "data error" not in str(status['status_message']):
                    print_tracker_result(tracker, tracker_class, status, True)
                    add_start = time.perf_counter()
                    log_timing(tracker, "add_to_client() start")
                    await client.add_to_client(meta, tracker_class.tracker)
                    log_timing(tracker, "add_to_client() end", add_start)
                    tracker_timings["add_to_client"] = time.perf_counter() - add_start
                else:
                    print_tracker_result(tracker, tracker_class, status, False)
                    console.print(f"[red]{tracker} upload failed or returned data error.[/red]")

        elif tracker in other_api_trackers:
            tracker_status = cast(StatusDict, meta.get('tracker_status') or {})
            upload_status = cast(Mapping[str, Any], tracker_status.get(tracker, {})).get('upload', False)
            if upload_status:
                try:
                    is_uploaded = False
                    try:
                        upload_start_time = time.time()
                        upload_perf_start = time.perf_counter()
                        log_timing(tracker, "upload() start")
                        is_uploaded = await tracker_class.upload(meta, disctype_value, base_torrent_bytes)
                        upload_duration = time.time() - upload_start_time
                        meta[f'{tracker}_upload_duration'] = upload_duration
                        log_timing(tracker, "upload() end", upload_perf_start)
                        tracker_timings["upload"] = time.perf_counter() - upload_perf_start
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        console.print(traceback.format_exc())
                        return
                    if tracker == 'SN':
                        await asyncio.sleep(16)
                except Exception:
                    console.print(traceback.format_exc())
                    return

                # Detect and handle None return value from upload method
                if is_uploaded is None:
                    console.print(f"[yellow]Warning: {tracker_class.tracker} upload method returned None instead of boolean. Treating as failed upload.[/yellow]")
                    is_uploaded = False

                status = cast(StatusDict, meta.get('tracker_status') or {}).get(tracker_class.tracker, {})
                if is_uploaded and 'status_message' in status and "data error" not in str(status['status_message']):
                    print_tracker_result(tracker, tracker_class, status, True)
                    add_start = time.perf_counter()
                    log_timing(tracker, "add_to_client() start")
                    await client.add_to_client(meta, tracker_class.tracker)
                    log_timing(tracker, "add_to_client() end", add_start)
                    tracker_timings["add_to_client"] = time.perf_counter() - add_start
                else:
                    print_tracker_result(tracker, tracker_class, status, False)
                    console.print(f"[red]{tracker} upload failed or returned data error.[/red]")

        elif tracker in http_trackers:
            tracker_status = cast(StatusDict, meta.get('tracker_status') or {})
            upload_status = cast(Mapping[str, Any], tracker_status.get(tracker, {})).get('upload', False)
            if upload_status:
                try:
                    is_uploaded = False
                    try:
                        upload_start_time = time.time()
                        upload_perf_start = time.perf_counter()
                        log_timing(tracker, "upload() start")
                        is_uploaded = await tracker_class.upload(meta, disctype_value, base_torrent_bytes)
                        upload_duration = time.time() - upload_start_time
                        meta[f'{tracker}_upload_duration'] = upload_duration
                        log_timing(tracker, "upload() end", upload_perf_start)
                        tracker_timings["upload"] = time.perf_counter() - upload_perf_start
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        console.print(traceback.format_exc())
                        return

                except Exception:
                    console.print(traceback.format_exc())
                    return

                # Detect and handle None return value from upload method
                if is_uploaded is None:
                    console.print(f"[yellow]Warning: {tracker_class.tracker} upload method returned None instead of boolean. Treating as failed upload.[/yellow]")
                    is_uploaded = False

                status = cast(StatusDict, meta.get('tracker_status') or {}).get(tracker_class.tracker, {})
                if is_uploaded and 'status_message' in status and "data error" not in str(status['status_message']):
                    print_tracker_result(tracker, tracker_class, status, True)
                    add_start = time.perf_counter()
                    log_timing(tracker, "add_to_client() start")
                    await client.add_to_client(meta, tracker_class.tracker)
                    log_timing(tracker, "add_to_client() end", add_start)
                    tracker_timings["add_to_client"] = time.perf_counter() - add_start
                else:
                    print_tracker_result(tracker, tracker_class, status, False)
                    console.print(f"[red]{tracker} upload failed or returned data error.[/red]")

        elif tracker == "MANUAL":
            if meta['unattended']:
                do_manual = True
            else:
                try:
                    do_manual = cli_ui.ask_yes_no("Get files for manual upload?", default=True)
                except EOFError:
                    console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                    await cleanup_manager.cleanup()
                    cleanup_manager.reset_terminal()
                    sys.exit(1)
            if do_manual:
                for manual_tracker in enabled_trackers:
                    if manual_tracker != 'MANUAL':
                        manual_tracker = manual_tracker.replace(" ", "").upper().strip()
                        tracker_class = tracker_class_map[manual_tracker](config=config)
                        if manual_tracker in api_trackers:
                            await DescriptionBuilder(manual_tracker, config).unit3d_edit_desc(meta, manual_tracker)
                        else:
                            await tracker_class.edit_desc(meta)
                url = await manual_packager.package(meta)
                if url is False:
                    console.print(f"[yellow]Unable to upload prep files, they can be found at `tmp/{meta['uuid']}")
                else:
                    console.print(f"[green]{meta['name']}")
                    console.print(f"[green]Files can be found at: [yellow]{url}[/yellow]")

        elif tracker == "THR":
            tracker_status = cast(StatusDict, meta.get('tracker_status') or {})
            upload_status = cast(Mapping[str, Any], tracker_status.get(tracker, {})).get('upload', False)
            if upload_status:
                thr = THR(config=config)
                thr_any = cast(Any, thr)
                is_uploaded = False
                try:
                    upload_start_time = time.time()
                    upload_perf_start = time.perf_counter()
                    log_timing(tracker, "upload() start")
                    is_uploaded = await thr_any.upload(meta, disctype_value, base_torrent_bytes)
                    upload_duration = time.time() - upload_start_time
                    meta[f'{tracker}_upload_duration'] = upload_duration
                    log_timing(tracker, "upload() end", upload_perf_start)
                    tracker_timings["upload"] = time.perf_counter() - upload_perf_start
                except Exception as e:
                    console.print(f"[red]Upload failed: {e}")
                    console.print(traceback.format_exc())
                    return
                if is_uploaded:
                    status = cast(StatusDict, meta.get('tracker_status') or {}).get('THR', {})
                    print_tracker_result(tracker, thr, status, True)
                    add_start = time.perf_counter()
                    log_timing(tracker, "add_to_client() start")
                    await client.add_to_client(meta, "THR")
                    log_timing(tracker, "add_to_client() end", add_start)
                    tracker_timings["add_to_client"] = time.perf_counter() - add_start
                else:
                    status = cast(StatusDict, meta.get('tracker_status') or {}).get('THR', {})
                    print_tracker_result(tracker, thr, status, False)
                    console.print(f"[red]{tracker} upload failed or returned data error.[/red]")

        elif tracker == "PTP":
            tracker_status = cast(StatusDict, meta.get('tracker_status') or {})
            upload_status = cast(Mapping[str, Any], tracker_status.get(tracker, {})).get('upload', False)
            if upload_status:
                try:
                    ptp = PTP(config=config)
                    groupID = meta.get('ptp_groupID', None)
                    ptpUrl, ptpData = await ptp.fill_upload_form(groupID, meta)
                    is_uploaded = False
                    try:
                        upload_start_time = time.time()
                        upload_perf_start = time.perf_counter()
                        log_timing(tracker, "upload() start")
                        is_uploaded = await ptp.upload(meta, ptpUrl, ptpData, disctype_value, base_torrent_bytes)
                        upload_duration = time.time() - upload_start_time
                        meta[f'{tracker}_upload_duration'] = upload_duration
                        await asyncio.sleep(5)
                        log_timing(tracker, "upload() end", upload_perf_start)
                        tracker_timings["upload"] = time.perf_counter() - upload_perf_start
                    except Exception as e:
                        console.print(f"[red]Upload failed: {e}")
                        console.print(traceback.format_exc())
                        return
                    status = cast(StatusDict, meta.get('tracker_status') or {}).get(ptp.tracker, {})
                    if is_uploaded and 'status_message' in status and "data error" not in str(status['status_message']):
                        print_tracker_result(tracker, ptp, status, True)
                        add_start = time.perf_counter()
                        log_timing(tracker, "add_to_client() start")
                        await client.add_to_client(meta, "PTP")
                        log_timing(tracker, "add_to_client() end", add_start)
                        tracker_timings["add_to_client"] = time.perf_counter() - add_start
                    else:
                        print_tracker_result(tracker, ptp, status, False)
                        console.print(f"[red]{tracker} upload failed or returned data error.[/red]")
                except Exception:
                    console.print(traceback.format_exc())
                    return

        tracker_total = time.perf_counter() - tracker_start_time
        log_timing(tracker, "tracker task end", tracker_start_time)
        summary_parts = [f"total {tracker_total:.2f}s"]
        upload_time = tracker_timings.get("upload")
        if upload_time is not None:
            summary_parts.append(f"upload {upload_time:.2f}s")
        add_time = tracker_timings.get("add_to_client")
        if add_time is not None:
            summary_parts.append(f"add_to_client {add_time:.2f}s")
        console.print(f"[cyan]{tracker} timing summary: {', '.join(summary_parts)}[/cyan]")

    multi_screens = int(config['DEFAULT'].get('multiScreens', 2))
    discs = cast(list[Any], meta.get('discs') or [])
    one_disc = True
    if discs and len(discs) == 1:
        one_disc = True
    elif discs and len(discs) > 1:
        one_disc = False

    if (not meta.get('tv_pack') and one_disc) or multi_screens == 0:
        # Run all tracker tasks concurrently with individual error handling
        tasks: list[tuple[str, asyncio.Task[None]]] = []
        for tracker in active_trackers:
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
        for tracker in active_trackers:
            await process_single_tracker(tracker)

    console.print("[green]All tracker uploads processed.[/green]")
