import cli_ui
import os
import json
import sys

from data.config import config
from src.cleanup import cleanup, reset_terminal
from src.console import console


class UploadHelper:
    async def dupe_check(self, dupes, meta, tracker_name):
        if not dupes:
            if meta['debug']:
                console.print(f"[green]No dupes found at[/green] [yellow]{tracker_name}[/yellow]")
            meta['upload'] = True
            return meta, False
        else:
            if meta.get('trumpable', False):
                trumpable_dupes = [d for d in dupes if isinstance(d, dict) and d.get('trumpable')]
                if trumpable_dupes:
                    trumpable_text = "\n".join([
                        f"{d['name']} - {d['link']}" if 'link' in d else d['name']
                        for d in trumpable_dupes
                    ])
                    console.print("[bold red]Trumpable found![/bold red]")
                    console.print(f"[bold cyan]{trumpable_text}[/bold cyan]")
                # Remove trumpable dupes from the main list
                dupes = [d for d in dupes if not (isinstance(d, dict) and d.get('trumpable'))]
            if (not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False))) and not meta.get('ask_dupe', False):
                dupe_text = "\n".join([
                    f"{d['name']} - {d['link']}" if isinstance(d, dict) and 'link' in d and d['link'] is not None else (d['name'] if isinstance(d, dict) else d)
                    for d in dupes
                ])
                if not dupe_text and meta.get('trumpable', False):
                    console.print("[yellow]Please check the trumpable entries above to see if you want to upload, and report the trumpable torrent if you upload.[/yellow]")
                    if meta.get('dupe', False) is False:
                        try:
                            upload = cli_ui.ask_yes_no(f"Upload to {tracker_name} anyway?", default=False)
                            meta['we_asked'] = True
                        except EOFError:
                            console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                            await cleanup()
                            reset_terminal()
                            sys.exit(1)
                    else:
                        upload = True
                        meta['we_asked'] = False
                else:
                    if meta.get('filename_match', False) and meta.get('file_count_match', False):
                        console.print(f'[bold red]Exact filename matches found! - {meta["filename_match"]}[/bold red]')
                        try:
                            upload = cli_ui.ask_yes_no(f"Upload to {tracker_name} anyway?", default=False)
                            meta['we_asked'] = True
                        except EOFError:
                            console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                            await cleanup()
                            reset_terminal()
                            sys.exit(1)
                    else:
                        console.print(f"[bold blue]Check if these are actually dupes from {tracker_name}:[/bold blue]")
                        console.print()
                        console.print(f"[bold cyan]{dupe_text}[/bold cyan]")
                        if meta.get('dupe', False) is False:
                            try:
                                upload = cli_ui.ask_yes_no(f"Upload to {tracker_name} anyway?", default=False)
                                meta['we_asked'] = True
                            except EOFError:
                                console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                                await cleanup()
                                reset_terminal()
                                sys.exit(1)
                        else:
                            upload = True
                            meta['we_asked'] = False
            else:
                if meta.get('dupe', False) is False:
                    upload = False
                    meta['we_asked'] = True
                else:
                    upload = True

            if upload is False:
                return meta, True
            else:
                for each in dupes:
                    each_name = each['name'] if isinstance(each, dict) else each
                    if each_name == meta['name']:
                        meta['name'] = f"{meta['name']} DUPE?"

                return meta, False

    async def get_confirmation(self, meta):
        if meta['debug'] is True:
            console.print("[bold red]DEBUG: True - Will not actually upload!")
            console.print(f"Prep material saved to {meta['base_dir']}/tmp/{meta['uuid']}")
        console.print()
        console.print("[bold yellow]Database Info[/bold yellow]")
        console.print(f"[bold]Title:[/bold] {meta['title']} ({meta['year']})")
        console.print()
        if not meta.get('emby', False):
            console.print(f"[bold]Overview:[/bold] {meta['overview'][:100]}....")
            console.print()
            if meta.get('category') == 'TV' and not meta.get('tv_pack') and meta.get('auto_episode_title'):
                console.print(f"[bold]Episode Title:[/bold] {meta['auto_episode_title']}")
                console.print()
            if meta.get('category') == 'TV' and not meta.get('tv_pack') and meta.get('overview_meta'):
                console.print(f"[bold]Episode overview:[/bold] {meta['overview_meta']}")
                console.print()
            console.print(f"[bold]Genre:[/bold] {meta['genres']}")
            console.print()
            if str(meta.get('demographic', '')) != '':
                console.print(f"[bold]Demographic:[/bold] {meta['demographic']}")
                console.print()
        console.print(f"[bold]Category:[/bold] {meta['category']}")
        console.print()
        if meta.get('emby_debug', False):
            if int(meta.get('original_imdb', 0)) != 0:
                imdb = str(meta.get('original_imdb', 0)).zfill(7)
                console.print(f"[bold]IMDB:[/bold] https://www.imdb.com/title/tt{imdb}")
            if int(meta.get('original_tmdb', 0)) != 0:
                console.print(f"[bold]TMDB:[/bold] https://www.themoviedb.org/{meta['category'].lower()}/{meta['original_tmdb']}")
            if int(meta.get('original_tvdb', 0)) != 0:
                console.print(f"[bold]TVDB:[/bold] https://www.thetvdb.com/?id={meta['original_tvdb']}&tab=series")
            if int(meta.get('original_tvmaze', 0)) != 0:
                console.print(f"[bold]TVMaze:[/bold] https://www.tvmaze.com/shows/{meta['original_tvmaze']}")
            if int(meta.get('original_mal', 0)) != 0:
                console.print(f"[bold]MAL:[/bold] https://myanimelist.net/anime/{meta['original_mal']}")
        else:
            if int(meta.get('tmdb_id') or 0) != 0:
                console.print(f"[bold]TMDB:[/bold] https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb_id']}")
            if int(meta.get('imdb_id') or 0) != 0:
                console.print(f"[bold]IMDB:[/bold] https://www.imdb.com/title/tt{meta['imdb']}")
            if int(meta.get('tvdb_id') or 0) != 0:
                console.print(f"[bold]TVDB:[/bold] https://www.thetvdb.com/?id={meta['tvdb_id']}&tab=series")
            if int(meta.get('tvmaze_id') or 0) != 0:
                console.print(f"[bold]TVMaze:[/bold] https://www.tvmaze.com/shows/{meta['tvmaze_id']}")
            if int(meta.get('mal_id') or 0) != 0:
                console.print(f"[bold]MAL:[/bold] https://myanimelist.net/anime/{meta['mal_id']}")
        console.print()
        if not meta.get('emby', False):
            if int(meta.get('freeleech', 0)) != 0:
                console.print(f"[bold]Freeleech:[/bold] {meta['freeleech']}")
            tag = "" if meta['tag'] == "" else f" / {meta['tag'][1:]}"
            res = meta['source'] if meta['is_disc'] == "DVD" else meta['resolution']
            console.print(f"{res} / {meta['type']}{tag}")
            if meta.get('personalrelease', False) is True:
                console.print("[bold green]Personal Release![/bold green]")
            console.print()

        if meta.get('unattended', False) and not meta.get('unattended_confirm', False) and not meta.get('emby_debug', False):
            if meta['debug'] is True:
                console.print("[bold yellow]Unattended mode is enabled, skipping confirmation.[/bold yellow]")
            return True
        else:
            if not meta.get('emby', False):
                await self.get_missing(meta)
                ring_the_bell = "\a" if config['DEFAULT'].get("sfx_on_prompt", True) is True else ""
                if ring_the_bell:
                    console.print(ring_the_bell)

            if meta.get('is disc', False) is True:
                meta['keep_folder'] = False

            if meta.get('keep_folder') and meta['isdir']:
                console.print("[bold yellow]Uploading with --keep-folder[/bold yellow]")
                kf_confirm = console.input("[bold yellow]You specified --keep-folder. Uploading in folders might not be allowed.[/bold yellow] [green]Proceed? y/N: [/green]").strip().lower()
                if kf_confirm != 'y':
                    console.print("[bold red]Aborting...[/bold red]")
                    exit()

            if not meta.get('emby', False):
                console.print(f"[bold]Name:[/bold] {meta['name']}")
                confirm = console.input("[bold green]Is this correct?[/bold green] [yellow]y/N[/yellow]: ").strip().lower() == 'y'
            elif not meta.get('emby_debug', False):
                confirm = console.input("[bold green]Is this correct?[/bold green] [yellow]y/N[/yellow]: ").strip().lower() == 'y'
        if meta.get('emby_debug', False):
            if meta.get('original_imdb', 0) != meta.get('imdb_id', 0):
                imdb = str(meta.get('imdb_id', 0)).zfill(7)
                console.print(f"[bold red]IMDB ID changed from {meta['original_imdb']} to {meta['imdb_id']}[/bold red]")
                console.print(f"[bold cyan]IMDB URL:[/bold cyan] [yellow]https://www.imdb.com/title/tt{imdb}[/yellow]")
            if meta.get('original_tmdb', 0) != meta.get('tmdb_id', 0):
                console.print(f"[bold red]TMDB ID changed from {meta['original_tmdb']} to {meta['tmdb_id']}[/bold red]")
                console.print(f"[bold cyan]TMDB URL:[/bold cyan] [yellow]https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb_id']}[/yellow]")
            if meta.get('original_mal', 0) != meta.get('mal_id', 0):
                console.print(f"[bold red]MAL ID changed from {meta['original_mal']} to {meta['mal_id']}[/bold red]")
                console.print(f"[bold cyan]MAL URL:[/bold cyan] [yellow]https://myanimelist.net/anime/{meta['mal_id']}[/yellow]")
            if meta.get('original_tvmaze', 0) != meta.get('tvmaze_id', 0):
                console.print(f"[bold red]TVMaze ID changed from {meta['original_tvmaze']} to {meta['tvmaze_id']}[/bold red]")
                console.print(f"[bold cyan]TVMaze URL:[/bold cyan] [yellow]https://www.tvmaze.com/shows/{meta['tvmaze_id']}[/yellow]")
            if meta.get('original_tvdb', 0) != meta.get('tvdb_id', 0):
                console.print(f"[bold red]TVDB ID changed from {meta['original_tvdb']} to {meta['tvdb_id']}[/bold red]")
                console.print(f"[bold cyan]TVDB URL:[/bold cyan] [yellow]https://www.thetvdb.com/?id={meta['tvdb_id']}&tab=series[/yellow]")
            if meta.get('original_category', None) != meta.get('category', None):
                console.print(f"[bold red]Category changed from {meta['original_category']} to {meta['category']}[/bold red]")
            console.print(f"[bold cyan]Regex Title:[/bold cyan] [yellow]{meta.get('regex_title', 'N/A')}[/yellow], [bold cyan]Secondary Title:[/bold cyan] [yellow]{meta.get('regex_secondary_title', 'N/A')}[/yellow], [bold cyan]Year:[/bold cyan] [yellow]{meta.get('regex_year', 'N/A')}, [bold cyan]AKA:[/bold cyan] [yellow]{meta.get('aka', '')}[/yellow]")
            console.print()
            if meta.get('original_imdb', 0) == meta.get('imdb_id', 0) and meta.get('original_tmdb', 0) == meta.get('tmdb_id', 0) and meta.get('original_mal', 0) == meta.get('mal_id', 0) and meta.get('original_tvmaze', 0) == meta.get('tvmaze_id', 0) and meta.get('original_tvdb', 0) == meta.get('tvdb_id', 0) and meta.get('original_category', None) == meta.get('category', None):
                console.print("[bold yellow]Database ID's are correct![/bold yellow]")
                return True
            else:
                nfo_dir = os.path.join(f"{meta['base_dir']}/data")
                os.makedirs(nfo_dir, exist_ok=True)
                json_file_path = os.path.join(nfo_dir, "db_check.json")

                def imdb_url(imdb_id):
                    return f"https://www.imdb.com/title/tt{str(imdb_id).zfill(7)}" if imdb_id and str(imdb_id).isdigit() else None

                def tmdb_url(tmdb_id, category):
                    return f"https://www.themoviedb.org/{str(category).lower()}/{tmdb_id}" if tmdb_id and category else None

                def tvdb_url(tvdb_id):
                    return f"https://www.thetvdb.com/?id={tvdb_id}&tab=series" if tvdb_id else None

                def tvmaze_url(tvmaze_id):
                    return f"https://www.tvmaze.com/shows/{tvmaze_id}" if tvmaze_id else None

                def mal_url(mal_id):
                    return f"https://myanimelist.net/anime/{mal_id}" if mal_id else None

                db_check_entry = {
                    "path": meta.get('path'),
                    "original": {
                        "imdb_id": meta.get('original_imdb', 'N/A'),
                        "imdb_url": imdb_url(meta.get('original_imdb')),
                        "tmdb_id": meta.get('original_tmdb', 'N/A'),
                        "tmdb_url": tmdb_url(meta.get('original_tmdb'), meta.get('original_category')),
                        "tvdb_id": meta.get('original_tvdb', 'N/A'),
                        "tvdb_url": tvdb_url(meta.get('original_tvdb')),
                        "tvmaze_id": meta.get('original_tvmaze', 'N/A'),
                        "tvmaze_url": tvmaze_url(meta.get('original_tvmaze')),
                        "mal_id": meta.get('original_mal', 'N/A'),
                        "mal_url": mal_url(meta.get('original_mal')),
                        "category": meta.get('original_category', 'N/A')
                    },
                    "changed": {
                        "imdb_id": meta.get('imdb_id', 'N/A'),
                        "imdb_url": imdb_url(meta.get('imdb_id')),
                        "tmdb_id": meta.get('tmdb_id', 'N/A'),
                        "tmdb_url": tmdb_url(meta.get('tmdb_id'), meta.get('category')),
                        "tvdb_id": meta.get('tvdb_id', 'N/A'),
                        "tvdb_url": tvdb_url(meta.get('tvdb_id')),
                        "tvmaze_id": meta.get('tvmaze_id', 'N/A'),
                        "tvmaze_url": tvmaze_url(meta.get('tvmaze_id')),
                        "mal_id": meta.get('mal_id', 'N/A'),
                        "mal_url": mal_url(meta.get('mal_id')),
                        "category": meta.get('category', 'N/A')
                    },
                    "tracker": meta.get('matched_tracker', 'N/A'),
                }

                # Append to JSON file (as a list of entries)
                if os.path.exists(json_file_path):
                    with open(json_file_path, 'r', encoding='utf-8') as f:
                        try:
                            db_data = json.load(f)
                            if not isinstance(db_data, list):
                                db_data = []
                        except Exception:
                            db_data = []
                else:
                    db_data = []

                db_data.append(db_check_entry)

                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(db_data, f, indent=2, ensure_ascii=False)
                return True

        return confirm

    async def get_missing(self, meta):
        info_notes = {
            'edition': 'Special Edition/Release',
            'description': "Please include Remux/Encode Notes if possible",
            'service': "WEB Service e.g.(AMZN, NF)",
            'region': "Disc Region",
            'imdb': 'IMDb ID (tt1234567)',
            'distributor': "Disc Distributor e.g.(BFI, Criterion)"
        }
        missing = []
        if meta.get('imdb_id', 0) == 0:
            meta['imdb_id'] = 0
            meta['potential_missing'].append('imdb_id')
        for each in meta['potential_missing']:
            if str(meta.get(each, '')).strip() in ["", "None", "0"]:
                missing.append(f"--{each} | {info_notes.get(each, '')}")
        if missing:
            console.print("[bold yellow]Potentially missing information:[/bold yellow]")
            for each in missing:
                cli_ui.info(each)
