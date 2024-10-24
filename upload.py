import requests
from src.args import Args
from src.clients import Clients
from src.prep import Prep
from src.trackers.COMMON import COMMON
from src.trackers.HUNO import HUNO
from src.trackers.BLU import BLU
from src.trackers.BHD import BHD
from src.trackers.AITHER import AITHER
from src.trackers.STC import STC
from src.trackers.R4E import R4E
from src.trackers.THR import THR
from src.trackers.STT import STT
from src.trackers.HP import HP
from src.trackers.PTP import PTP
from src.trackers.SN import SN
from src.trackers.ACM import ACM
from src.trackers.HDB import HDB
from src.trackers.LCD import LCD
from src.trackers.TTG import TTG
from src.trackers.LST import LST
from src.trackers.FL import FL
from src.trackers.LT import LT
from src.trackers.NBL import NBL
from src.trackers.ANT import ANT
from src.trackers.PTER import PTER
from src.trackers.MTV import MTV
from src.trackers.JPTV import JPTV
from src.trackers.TL import TL
from src.trackers.TDC import TDC
from src.trackers.HDT import HDT
from src.trackers.RF import RF
from src.trackers.OE import OE
from src.trackers.BHDTV import BHDTV
from src.trackers.RTF import RTF
from src.trackers.OTW import OTW
from src.trackers.FNP import FNP
from src.trackers.CBR import CBR
from src.trackers.UTP import UTP
from src.trackers.AL import AL
from src.trackers.SHRI import SHRI
from src.trackers.TIK import TIK
from src.trackers.TVC import TVC
from src.trackers.PSS import PSS
from src.trackers.ULCX import ULCX
from src.trackers.SPD import SPD
import json
from pathlib import Path
import asyncio
import os
import sys
import platform
import shutil
import glob
import cli_ui
import traceback

from src.console import console
from rich.markdown import Markdown
from rich.style import Style


cli_ui.setup(color='always', title="L4G's Upload Assistant")

base_dir = os.path.abspath(os.path.dirname(__file__))

try:
    from data.config import config
except Exception:
    if not os.path.exists(os.path.abspath(f"{base_dir}/data/config.py")):
        cli_ui.info(cli_ui.red, "Configuration file 'config.py' not found.")
        cli_ui.info(cli_ui.red, "Please ensure the file is located at:", cli_ui.yellow, os.path.abspath(f"{base_dir}/data/config.py"))
        cli_ui.info(cli_ui.red, "Follow the setup instructions: https://github.com/Audionut/Upload-Assistant")
        exit()
    else:
        console.print(traceback.print_exc())

client = Clients(config=config)
parser = Args(config)


async def do_the_thing(base_dir):
    meta = dict()
    meta['base_dir'] = base_dir
    paths = []
    for each in sys.argv[1:]:
        if os.path.exists(each):
            paths.append(os.path.abspath(each))
        else:
            break
    meta, help, before_args = parser.parse(tuple(' '.join(sys.argv[1:]).split(' ')), meta)
    if meta['cleanup'] and os.path.exists(f"{base_dir}/tmp"):
        shutil.rmtree(f"{base_dir}/tmp")
        console.print("[bold green]Sucessfully emptied tmp directory")
    if not meta['path']:
        exit(0)
    path = meta['path']
    path = os.path.abspath(path)
    if path.endswith('"'):
        path = path[:-1]
    queue = []
    if os.path.exists(path):
        meta, help, before_args = parser.parse(tuple(' '.join(sys.argv[1:]).split(' ')), meta)
        queue = [path]
    else:
        # Search glob if dirname exists
        if os.path.exists(os.path.dirname(path)) and len(paths) <= 1:
            escaped_path = path.replace('[', '[[]')
            globs = glob.glob(escaped_path)
            queue = globs
            if len(queue) != 0:
                md_text = "\n - ".join(queue)
                console.print("\n[bold green]Queuing these files:[/bold green]", end='')
                console.print(Markdown(f"- {md_text.rstrip()}\n\n", style=Style(color='cyan')))
                console.print("\n\n")
            else:
                console.print(f"[red]Path: [bold red]{path}[/bold red] does not exist")

        elif os.path.exists(os.path.dirname(path)) and len(paths) != 1:
            queue = paths
            md_text = "\n - ".join(queue)
            console.print("\n[bold green]Queuing these files:[/bold green]", end='')
            console.print(Markdown(f"- {md_text.rstrip()}\n\n", style=Style(color='cyan')))
            console.print("\n\n")
        elif not os.path.exists(os.path.dirname(path)):
            split_path = path.split()
            p1 = split_path[0]
            for i, each in enumerate(split_path):
                try:
                    if os.path.exists(p1) and not os.path.exists(f"{p1} {split_path[i + 1]}"):
                        queue.append(p1)
                        p1 = split_path[i + 1]
                    else:
                        p1 += f" {split_path[i + 1]}"
                except IndexError:
                    if os.path.exists(p1):
                        queue.append(p1)
                    else:
                        console.print(f"[red]Path: [bold red]{p1}[/bold red] does not exist")
            if len(queue) >= 1:
                md_text = "\n - ".join(queue)
                console.print("\n[bold green]Queuing these files:[/bold green]", end='')
                console.print(Markdown(f"- {md_text.rstrip()}\n\n", style=Style(color='cyan')))
                console.print("\n\n")

        else:
            # Add Search Here
            console.print("[red]There was an issue with your input. If you think this was not an issue, please make a report that includes the full command used.")
            exit()

    base_meta = {k: v for k, v in meta.items()}
    for path in queue:
        meta = {k: v for k, v in base_meta.items()}
        meta['path'] = path
        meta['uuid'] = None
        try:
            with open(f"{base_dir}/tmp/{os.path.basename(path)}/meta.json") as f:
                saved_meta = json.load(f)
                for key, value in saved_meta.items():
                    overwrite_list = [
                        'trackers', 'dupe', 'debug', 'anon', 'category', 'type', 'screens', 'nohash', 'manual_edition', 'imdb', 'tmdb_manual', 'mal', 'manual',
                        'hdb', 'ptp', 'blu', 'no_season', 'no_aka', 'no_year', 'no_dub', 'no_tag', 'no_seed', 'client', 'desclink', 'descfile', 'desc', 'draft', 'modq', 'region', 'freeleech',
                        'personalrelease', 'unattended', 'season', 'episode', 'torrent_creation', 'qbit_tag', 'qbit_cat', 'skip_imghost_upload', 'imghost', 'manual_source', 'webdv', 'hardcoded-subs', 'dual_audio'
                    ]
                    if meta.get(key, None) != value and key in overwrite_list:
                        saved_meta[key] = meta[key]
                meta = saved_meta
                f.close()
        except FileNotFoundError:
            pass
        console.print(f"[green]Gathering info for {os.path.basename(path)}")
        if meta['imghost'] is None:
            meta['imghost'] = config['DEFAULT']['img_host_1']
        if not meta['unattended']:
            ua = config['DEFAULT'].get('auto_mode', False)
            if str(ua).lower() == "true":
                meta['unattended'] = True
                console.print("[yellow]Running in Auto Mode")
        prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=config)
        meta = await prep.gather_prep(meta=meta, mode='cli')
        meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await prep.get_name(meta)

        if meta.get('image_list', False) in (False, []) and meta.get('skip_imghost_upload', False) is False:
            return_dict = {}
            meta['image_list'], dummy_var = prep.upload_screens(meta, meta['screens'], 1, 0, meta['screens'], [], return_dict)
            if meta['debug']:
                console.print(meta['image_list'])
            # meta['uploaded_screens'] = True
        elif meta.get('skip_imghost_upload', False) is True and meta.get('image_list', False) is False:
            meta['image_list'] = []

        if not os.path.exists(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")):
            reuse_torrent = None
            if meta.get('rehash', False) is False:
                reuse_torrent = await client.find_existing_torrent(meta)
                if reuse_torrent is not None:
                    prep.create_base_from_existing_torrent(reuse_torrent, meta['base_dir'], meta['uuid'])
            if meta['nohash'] is False and reuse_torrent is None:
                prep.create_torrent(meta, Path(meta['path']), "BASE")
            if meta['nohash']:
                meta['client'] = "none"
        elif os.path.exists(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")) and meta.get('rehash', False) is True and meta['nohash'] is False:
            prep.create_torrent(meta, Path(meta['path']), "BASE")
        if int(meta.get('randomized', 0)) >= 1:
            prep.create_random_torrents(meta['base_dir'], meta['uuid'], meta['randomized'], meta['path'])

        if meta.get('trackers', None) is not None:
            trackers = meta['trackers']
        else:
            trackers = config['TRACKERS']['default_trackers']
        if "," in trackers:
            trackers = trackers.split(',')
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w') as f:
            json.dump(meta, f, indent=4)
            f.close()
        confirm = get_confirmation(meta)
        while confirm is False:
            # help.print_help()
            editargs = cli_ui.ask_string("Input args that need correction e.g.(--tag NTb --category tv --tmdb 12345)")
            editargs = (meta['path'],) + tuple(editargs.split())
            if meta['debug']:
                editargs = editargs + ("--debug",)
            meta, help, before_args = parser.parse(editargs, meta)
            # meta = await prep.tmdb_other_meta(meta)
            meta['edit'] = True
            meta = await prep.gather_prep(meta=meta, mode='cli')
            meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await prep.get_name(meta)
            confirm = get_confirmation(meta)

        if isinstance(trackers, list) is False:
            trackers = [trackers]
        trackers = [s.strip().upper() for s in trackers]
        if meta.get('manual', False):
            trackers.insert(0, "MANUAL")

        ####################################
        #######  Upload to Trackers  #######  # noqa #F266
        ####################################
        common = COMMON(config=config)
        api_trackers = ['BLU', 'AITHER', 'STC', 'R4E', 'STT', 'RF', 'ACM', 'LCD', 'HUNO', 'LT', 'JPTV', 'TDC', 'OE',
                        'OTW', 'FNP', 'CBR', 'UTP', 'AL', 'SHRI', 'LST', 'TIK', 'PSS', 'ULCX', 'BHD']
        other_api_trackers = ['SN', 'NBL', 'ANT', 'BHDTV', 'RTF', 'TL', 'TVC', 'SPD']
        http_trackers = ['HDB', 'TTG', 'FL', 'PTER', 'HDT', 'MTV']
        tracker_class_map = {
            'BLU': BLU, 'BHD': BHD, 'AITHER': AITHER, 'STC': STC, 'R4E': R4E, 'THR': THR, 'STT': STT, 'HP': HP, 'PTP': PTP, 'RF': RF, 'SN': SN, 'TIK': TIK, 'TVC': TVC,
            'ACM': ACM, 'HDB': HDB, 'LCD': LCD, 'TTG': TTG, 'LST': LST, 'HUNO': HUNO, 'FL': FL, 'LT': LT, 'NBL': NBL, 'ANT': ANT, 'PTER': PTER, 'JPTV': JPTV,
            'TL': TL, 'TDC': TDC, 'HDT': HDT, 'MTV': MTV, 'OE': OE, 'BHDTV': BHDTV, 'RTF': RTF, 'OTW': OTW, 'FNP': FNP, 'CBR': CBR, 'UTP': UTP, 'AL': AL,
            'SHRI': SHRI, 'PSS': PSS, 'ULCX': ULCX, 'SPD': SPD}

        tracker_capabilities = {
            'LST': {'mod_q': True, 'draft': True},
            'BLU': {'mod_q': True, 'draft': False},
            'AITHER': {'mod_q': True, 'draft': False},
            'BHD': {'draft_live': True},
        }

        async def check_mod_q_and_draft(tracker_class, meta, debug, disctype):
            modq, draft = None, None

            tracker_caps = tracker_capabilities.get(tracker_class.tracker, {})

            # Handle BHD specific draft/live logic
            if tracker_class.tracker == 'BHD' and tracker_caps.get('draft_live'):
                draft_int = await tracker_class.get_live(meta)
                draft = "Draft" if draft_int == 0 else "Live"

            # Handle mod_q and draft for other trackers
            else:
                if tracker_caps.get('mod_q'):
                    modq = await tracker_class.get_flag(meta, 'modq')
                    modq = 'Yes' if modq else 'No'
                if tracker_caps.get('draft'):
                    draft = await tracker_class.get_flag(meta, 'draft')
                    draft = 'Yes' if draft else 'No'

            return modq, draft

        for tracker in trackers:
            disctype = meta.get('disctype', None)
            tracker = tracker.replace(" ", "").upper().strip()
            if meta['name'].endswith('DUPE?'):
                meta['name'] = meta['name'].replace(' DUPE?', '')

            if meta['debug']:
                debug = "(DEBUG)"
            else:
                debug = ""

            if tracker in api_trackers:
                tracker_class = tracker_class_map[tracker](config=config)

                if meta['unattended']:
                    upload_to_tracker = True
                else:
                    try:
                        upload_to_tracker = cli_ui.ask_yes_no(
                            f"Upload to {tracker_class.tracker}? {debug}",
                            default=meta['unattended']
                        )
                    except (KeyboardInterrupt, EOFError):
                        sys.exit(1)  # Exit immediately

                if upload_to_tracker:
                    # Get mod_q, draft, or draft/live depending on the tracker
                    modq, draft = await check_mod_q_and_draft(tracker_class, meta, debug, disctype)

                    # Print mod_q and draft info if relevant
                    if modq is not None:
                        console.print(f"(modq: {modq})")
                    if draft is not None:
                        console.print(f"(draft: {draft})")

                    console.print(f"Uploading to {tracker_class.tracker}")

                    # Check if the group is banned for the tracker
                    if check_banned_group(tracker_class.tracker, tracker_class.banned_groups, meta):
                        continue

                    dupes = await tracker_class.search_existing(meta, disctype)
                    dupes = await common.filter_dupes(dupes, meta)
                    meta = dupe_check(dupes, meta)

                    # Proceed with upload if the meta is set to upload
                    if meta.get('upload', False):
                        await tracker_class.upload(meta, disctype)
                        perm = config['DEFAULT'].get('get_permalink', False)
                        if perm:
                            # need a wait so we don't race the api
                            await asyncio.sleep(5)
                            await tracker_class.search_torrent_page(meta, disctype)
                            await asyncio.sleep(0.5)
                        await client.add_to_client(meta, tracker_class.tracker)

            if tracker in other_api_trackers:
                tracker_class = tracker_class_map[tracker](config=config)

                if meta['unattended']:
                    upload_to_tracker = True
                else:
                    try:
                        upload_to_tracker = cli_ui.ask_yes_no(
                            f"Upload to {tracker_class.tracker}? {debug}",
                            default=meta['unattended']
                        )
                    except (KeyboardInterrupt, EOFError):
                        sys.exit(1)  # Exit immediately

                if upload_to_tracker:
                    # Get mod_q, draft, or draft/live depending on the tracker
                    modq, draft = await check_mod_q_and_draft(tracker_class, meta, debug, disctype)

                    # Print mod_q and draft info if relevant
                    if modq is not None:
                        console.print(f"(modq: {modq})")
                    if draft is not None:
                        console.print(f"(draft: {draft})")

                    console.print(f"Uploading to {tracker_class.tracker}")

                    # Check if the group is banned for the tracker
                    if check_banned_group(tracker_class.tracker, tracker_class.banned_groups, meta):
                        continue

                    # Perform the existing checks for dupes except TL
                    if tracker != "TL":
                        if tracker == "RTF":
                            await tracker_class.api_test(meta)

                        dupes = await tracker_class.search_existing(meta, disctype)
                        dupes = await common.filter_dupes(dupes, meta)
                        meta = dupe_check(dupes, meta)

                    # Proceed with upload if the meta is set to upload
                    if tracker == "TL" or meta.get('upload', False):
                        await tracker_class.upload(meta, disctype)
                        if tracker == 'SN':
                            await asyncio.sleep(16)
                        await client.add_to_client(meta, tracker_class.tracker)

            if tracker in http_trackers:
                tracker_class = tracker_class_map[tracker](config=config)

                if meta['unattended']:
                    upload_to_tracker = True
                else:
                    try:
                        upload_to_tracker = cli_ui.ask_yes_no(
                            f"Upload to {tracker_class.tracker}? {debug}",
                            default=meta['unattended']
                        )
                    except (KeyboardInterrupt, EOFError):
                        sys.exit(1)  # Exit immediately

                if upload_to_tracker:
                    console.print(f"Uploading to {tracker}")
                    if check_banned_group(tracker_class.tracker, tracker_class.banned_groups, meta):
                        continue
                    if await tracker_class.validate_credentials(meta) is True:
                        dupes = await tracker_class.search_existing(meta, disctype)
                        dupes = await common.filter_dupes(dupes, meta)
                        meta = dupe_check(dupes, meta)
                        if meta['upload'] is True:
                            await tracker_class.upload(meta, disctype)
                            await client.add_to_client(meta, tracker_class.tracker)

            if tracker == "MANUAL":
                if meta['unattended']:
                    do_manual = True
                else:
                    do_manual = cli_ui.ask_yes_no("Get files for manual upload?", default=True)
                if do_manual:
                    for manual_tracker in trackers:
                        if manual_tracker != 'MANUAL':
                            manual_tracker = manual_tracker.replace(" ", "").upper().strip()
                            tracker_class = tracker_class_map[manual_tracker](config=config)
                            if manual_tracker in api_trackers:
                                await common.unit3d_edit_desc(meta, tracker_class.tracker, tracker_class.signature)
                            else:
                                await tracker_class.edit_desc(meta)
                    url = await prep.package(meta)
                    if url is False:
                        console.print(f"[yellow]Unable to upload prep files, they can be found at `tmp/{meta['uuid']}")
                    else:
                        console.print(f"[green]{meta['name']}")
                        console.print(f"[green]Files can be found at: [yellow]{url}[/yellow]")

            if tracker == "THR":
                if meta['unattended']:
                    upload_to_thr = True
                else:
                    try:
                        upload_to_ptp = cli_ui.ask_yes_no(
                            f"Upload to THR? {debug}",
                            default=meta['unattended']
                        )
                    except (KeyboardInterrupt, EOFError):
                        sys.exit(1)  # Exit immediately
                if upload_to_thr:
                    console.print("Uploading to THR")
                    # nable to get IMDB id/Youtube Link
                    if meta.get('imdb_id', '0') == '0':
                        imdb_id = cli_ui.ask_string("Unable to find IMDB id, please enter e.g.(tt1234567)")
                        meta['imdb_id'] = imdb_id.replace('tt', '').zfill(7)
                    if meta.get('youtube', None) is None:
                        youtube = cli_ui.ask_string("Unable to find youtube trailer, please link one e.g.(https://www.youtube.com/watch?v=dQw4w9WgXcQ)")
                        meta['youtube'] = youtube
                    thr = THR(config=config)
                    try:
                        with requests.Session() as session:
                            console.print("[yellow]Logging in to THR")
                            session = thr.login(session)
                            console.print("[yellow]Searching for Dupes")
                            dupes = thr.search_existing(session, disctype, meta.get('imdb_id'))
                            dupes = await common.filter_dupes(dupes, meta)
                            meta = dupe_check(dupes, meta)
                            if meta['upload'] is True:
                                await thr.upload(session, meta, disctype)
                                await client.add_to_client(meta, "THR")
                    except Exception:
                        console.print(traceback.print_exc())

            if tracker == "PTP":
                if meta['unattended']:
                    upload_to_ptp = True
                else:
                    try:
                        upload_to_ptp = cli_ui.ask_yes_no(
                            f"Upload to {tracker}? {debug}",
                            default=meta['unattended']
                        )
                    except (KeyboardInterrupt, EOFError):
                        sys.exit(1)  # Exit immediately

                if upload_to_ptp:  # Ensure the variable is defined before this check
                    console.print(f"Uploading to {tracker}")
                    if meta.get('imdb_id', '0') == '0':
                        imdb_id = cli_ui.ask_string("Unable to find IMDB id, please enter e.g.(tt1234567)")
                        meta['imdb_id'] = imdb_id.replace('tt', '').zfill(7)
                    ptp = PTP(config=config)
                    if check_banned_group("PTP", ptp.banned_groups, meta):
                        continue
                    try:
                        console.print("[yellow]Searching for Group ID")
                        groupID = await ptp.get_group_by_imdb(meta['imdb_id'])
                        if groupID is None:
                            console.print("[yellow]No Existing Group found")
                            if meta.get('youtube', None) is None or "youtube" not in str(meta.get('youtube', '')):
                                youtube = cli_ui.ask_string("Unable to find youtube trailer, please link one e.g.(https://www.youtube.com/watch?v=dQw4w9WgXcQ)", default="")
                                meta['youtube'] = youtube
                            meta['upload'] = True
                        else:
                            console.print("[yellow]Searching for Existing Releases")
                            dupes = await ptp.search_existing(groupID, meta, disctype)
                            dupes = await common.filter_dupes(dupes, meta)
                            meta = dupe_check(dupes, meta)
                        if meta.get('imdb_info', {}) == {}:
                            meta['imdb_info'] = await prep.get_imdb_info(meta['imdb_id'], meta)
                        if meta['upload'] is True:
                            ptpUrl, ptpData = await ptp.fill_upload_form(groupID, meta)
                            await ptp.upload(meta, ptpUrl, ptpData, disctype)
                            await asyncio.sleep(5)
                            await client.add_to_client(meta, "PTP")
                    except Exception:
                        console.print(traceback.print_exc())


def get_confirmation(meta):
    if meta['debug'] is True:
        console.print("[bold red]DEBUG: True")
    console.print(f"Prep material saved to {meta['base_dir']}/tmp/{meta['uuid']}")
    console.print()
    cli_ui.info_section(cli_ui.yellow, "Database Info")
    cli_ui.info(f"Title: {meta['title']} ({meta['year']})")
    console.print()
    cli_ui.info(f"Overview: {meta['overview']}")
    console.print()
    cli_ui.info(f"Category: {meta['category']}")
    if int(meta.get('tmdb', 0)) != 0:
        cli_ui.info(f"TMDB: https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb']}")
    if int(meta.get('imdb_id', '0')) != 0:
        cli_ui.info(f"IMDB: https://www.imdb.com/title/tt{meta['imdb_id']}")
    if int(meta.get('tvdb_id', '0')) != 0:
        cli_ui.info(f"TVDB: https://www.thetvdb.com/?id={meta['tvdb_id']}&tab=series")
    if int(meta.get('mal_id', 0)) != 0:
        cli_ui.info(f"MAL : https://myanimelist.net/anime/{meta['mal_id']}")
    console.print()
    if int(meta.get('freeleech', '0')) != 0:
        cli_ui.info(f"Freeleech: {meta['freeleech']}")
    if meta['tag'] == "":
        tag = ""
    else:
        tag = f" / {meta['tag'][1:]}"
    if meta['is_disc'] == "DVD":
        res = meta['source']
    else:
        res = meta['resolution']

    cli_ui.info(f"{res} / {meta['type']}{tag}")
    if meta.get('personalrelease', False) is True:
        cli_ui.info("Personal Release!")
    console.print()
    if meta.get('unattended', False) is False:
        get_missing(meta)
        ring_the_bell = "\a" if config['DEFAULT'].get("sfx_on_prompt", True) is True else ""  # \a rings the bell
        cli_ui.info(ring_the_bell)

        # Handle the 'keep_folder' logic based on 'is disc' and 'isdir'
        if meta.get('is disc', False) is False:
            meta['keep_folder'] = False  # Ensure 'keep_folder' is False if 'is disc' is True

        if meta.get('keep_folder'):
            if meta['isdir']:
                cli_ui.info_section(cli_ui.yellow, "Uploading with --keep-folder")
                kf_confirm = cli_ui.ask_yes_no("You specified --keep-folder. Uploading in folders might not be allowed. Are you sure you want to proceed?", default=False)
                if not kf_confirm:
                    cli_ui.info('Aborting...')
                    exit()

        cli_ui.info_section(cli_ui.yellow, "Is this correct?")
        cli_ui.info(f"Name: {meta['name']}")
        confirm = cli_ui.ask_yes_no("Correct?", default=False)

    else:
        cli_ui.info(f"Name: {meta['name']}")
        confirm = True

    return confirm


def dupe_check(dupes, meta):
    if not dupes:
        console.print("[green]No dupes found")
        meta['upload'] = True
        return meta
    else:
        console.print()
        dupe_text = "\n".join(dupes)
        console.print()
        cli_ui.info_section(cli_ui.bold, "Check if these are actually dupes!")
        cli_ui.info(dupe_text)
        if meta['unattended']:
            if meta.get('dupe', False) is False:
                console.print("[red]Found potential dupes. Aborting. If this is not a dupe, or you would like to upload anyways, pass --skip-dupe-check")
                upload = False
            else:
                console.print("[yellow]Found potential dupes. --skip-dupe-check was passed. Uploading anyways")
                upload = True
        console.print()
        if not meta['unattended']:
            if meta.get('dupe', False) is False:
                upload = cli_ui.ask_yes_no("Upload Anyways?", default=False)
            else:
                upload = True
        if upload is False:
            meta['upload'] = False
        else:
            meta['upload'] = True
            for each in dupes:
                if each == meta['name']:
                    meta['name'] = f"{meta['name']} DUPE?"

        return meta


# Return True if banned group
def check_banned_group(tracker, banned_group_list, meta):
    if meta['tag'] == "":
        return False
    else:
        q = False
        for tag in banned_group_list:
            if isinstance(tag, list):
                if meta['tag'][1:].lower() == tag[0].lower():
                    console.print(f"[bold yellow]{meta['tag'][1:]}[/bold yellow][bold red] was found on [bold yellow]{tracker}'s[/bold yellow] list of banned groups.")
                    console.print(f"[bold red]NOTE: [bold yellow]{tag[1]}")
                    q = True
            else:
                if meta['tag'][1:].lower() == tag.lower():
                    console.print(f"[bold yellow]{meta['tag'][1:]}[/bold yellow][bold red] was found on [bold yellow]{tracker}'s[/bold yellow] list of banned groups.")
                    q = True
        if q:
            if not cli_ui.ask_yes_no(cli_ui.red, "Upload Anyways?", default=False):
                return True
    return False


def get_missing(meta):
    info_notes = {
        'edition': 'Special Edition/Release',
        'description': "Please include Remux/Encode Notes if possible (either here or edit your upload)",
        'service': "WEB Service e.g.(AMZN, NF)",
        'region': "Disc Region",
        'imdb': 'IMDb ID (tt1234567)',
        'distributor': "Disc Distributor e.g.(BFI, Criterion, etc)"
    }
    missing = []
    if meta.get('imdb_id', '0') == '0':
        meta['imdb_id'] = '0'
        meta['potential_missing'].append('imdb_id')
    if len(meta['potential_missing']) > 0:
        for each in meta['potential_missing']:
            if str(meta.get(each, '')).replace(' ', '') in ["", "None", "0"]:
                if each == "imdb_id":
                    each = 'imdb'
                missing.append(f"--{each} | {info_notes.get(each)}")
    if missing != []:
        cli_ui.info_section(cli_ui.yellow, "Potentially missing information:")
        for each in missing:
            if each.split('|')[0].replace('--', '').strip() in ["imdb"]:
                cli_ui.info(cli_ui.red, each)
            else:
                cli_ui.info(each)

    console.print()
    return


if __name__ == '__main__':
    pyver = platform.python_version_tuple()
    if int(pyver[0]) != 3 or int(pyver[1]) < 12:
        console.print("[bold red]Python version is too low. Please use Python 3.12 or higher.")
        sys.exit(1)

    try:
        asyncio.run(do_the_thing(base_dir))  # Pass the correct base_dir value here
    except (KeyboardInterrupt):
        console.print("[bold red]Program interrupted. Exiting.")
