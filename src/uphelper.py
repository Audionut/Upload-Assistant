import cli_ui
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
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
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
        if meta.get('unattended', False) is False:
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
            else:
                if meta.get('unattended_confirm', False):
                    console.print("[bold]Filename searching was required, double check the database information.[/bold]")
                confirm = console.input("[bold green]Is the database information correct?[/bold green] [yellow]y/N[/yellow]: ").strip().lower() == 'y'
        if meta.get('emby', False):
            if meta.get('unattended_confirm', False):
                console.print("[bold]Filename searching was required, double check the database information.[/bold]")
            confirm = console.input("[bold green]Is the database information correct?[/bold green] [yellow]y/N[/yellow]: ").strip().lower() == 'y'
        else:
            console.print(f"[bold]Name:[/bold] {meta['name']}")
            confirm = True

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
