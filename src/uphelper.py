import cli_ui
from difflib import SequenceMatcher
from rich.console import Console
from data.config import config

console = Console()


class UploadHelper:
    async def dupe_check(self, dupes, meta, tracker_name):
        if not dupes:
            if meta['debug']:
                console.print(f"[green]No dupes found at[/green] [yellow]{tracker_name}[/yellow]")
            meta['upload'] = True
            return meta, False
        else:
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                dupe_text = "\n".join([d['name'] if isinstance(d, dict) else d for d in dupes])
                console.print(f"[bold blue]Check if these are actually dupes from {tracker_name}:[/bold blue]")
                console.print()
                console.print(f"[bold cyan]{dupe_text}[/bold cyan]")
                if meta.get('dupe', False) is False:
                    upload = cli_ui.ask_yes_no(f"Upload to {tracker_name} anyway?", default=False)
                    meta['we_asked'] = True
                else:
                    upload = True
                    meta['we_asked'] = False
            else:
                if meta.get('dupe', False) is False:
                    upload = False
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
        if meta.get('emby', False):
            if int(meta.get('original_imdb', 0)) != 0:
                console.print(f"[bold]IMDB:[/bold] https://www.imdb.com/title/tt{meta['original_imdb']}")
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

        if meta.get('unattended', False) and not meta.get('unattended_confirm', False):
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
        if meta.get('emby', False):
            if meta.get('original_imdb', 0) != meta.get('imdb_id', 0):
                console.print(f"[bold red]IMDB ID changed from {meta['original_imdb']} to {meta['imdb_id']}[/bold red]")
                console.print(f"[bold cyan]IMDB URL:[/bold cyan] [yellow]https://www.imdb.com/title/tt{meta['imdb_id']}[/yellow]")
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
            console.print(f"[bold cyan]Regex Title:[/bold cyan] [yellow]{meta.get('regex_title', 'N/A')}[/yellow], [bold cyan]Secondary Title:[/bold cyan] [yellow]{meta.get('regex_secondary_title', 'N/A')}[/yellow], [bold cyan]Year:[/bold cyan] [yellow]{meta.get('regex_year', 'N/A')}[/yellow]")
            console.print()
            if meta.get('original_imdb', 0) == meta.get('imdb_id', 0) and meta.get('original_tmdb', 0) == meta.get('tmdb_id', 0) and meta.get('original_mal', 0) == meta.get('mal_id', 0) and meta.get('original_tvmaze', 0) == meta.get('tvmaze_id', 0) and meta.get('original_tvdb', 0) == meta.get('tvdb_id', 0) and meta.get('original_category', None) == meta.get('category', None):
                console.print("[bold yellow]Database ID's are correct![/bold yellow]")
                regex_title = meta.get('regex_title', None)
                title = meta.get('title', None)
                if regex_title and title:
                    similarity = SequenceMatcher(None, str(regex_title).lower(), str(title).lower()).ratio()
                    if similarity < 0.90:
                        console.print()
                        console.print(f"[bold cyan]Regex Title Mismatch:[/bold cyan] [yellow]{regex_title}[/yellow], [bold cyan]Title:[/bold cyan] [yellow]{title}[/yellow]")
                        confirm = console.input("[bold green]Continue?[/bold green] [yellow]y/N[/yellow]: ").strip().lower() == 'y'
                    else:
                        regex_year = meta.get('regex_year', 0)
                        year = meta.get('year', 0)
                        if regex_year and year:
                            if int(regex_year) != int(year):
                                console.print()
                                console.print(f"[bold cyan]Regex Year Mismatch:[/bold cyan] [yellow]{regex_year}[/yellow], [bold cyan]Year:[/bold cyan] [yellow]{year}[/yellow]")
                                confirm = console.input("[bold green]Continue?[/bold green] [yellow]y/N[/yellow]: ").strip().lower() == 'y'
                        else:
                            return True
                    return True
                else:
                    return True
            else:
                console.print("path: ", meta['path'])
                console.print()
                console.print("[bold red]Filename searching was required, double check the database information.[/bold red]")
                confirm = console.input("[bold green]Is the database information correct?[/bold green] [yellow]y/N[/yellow]: ").strip().lower() == 'y'

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
