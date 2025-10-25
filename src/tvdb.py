import asyncio
import base64
import re
from tvdb_v4_official import TVDB

from src.console import console


def _get_tvdb_k() -> str:
    k = (
        b"MDEwMTEwMDEwMDExMDAxMDAxMDExMDAxMDExMTEwMDAwMTAwMTExMDAxMTAxMTAxMDEwMTAwMDEwMDExMDEwMD"
        b"AxMDAxMTAxMDExMDEwMTAwMTAxMDAwMTAxMTEwMTAwMDEwMTEwMDEwMDExMDAxMDAxMDAxMDAxMDAxMTAwMTEw"
        b"MTAwMTEwMTAxMDEwMDExMDAxMTAwMDAwMDExMDAwMDAxMDAxMTEwMDExMDEwMTAwMTEwMTAwMDAxMTAxMTAwMD"
        b"EwMDExMDAwMTAxMDExMTAxMDAwMTAxMDAxMTAwMTAwMTAxMTAwMTAxMDEwMTAwMDEwMDAxMDEwMTExMDEwMDAx"
        b"MDAxMTEwMDExMTEwMTAwMTAwMDAxMDAxMTAxMDEwMDEwMTEwMTAwMTAwMDExMTAxMDEwMDAxMDExMTEwMDAwMT"
        b"AxMTAwMTAxMDEwMTExMDEwMTAwMTAwMTEwMTAxMDAxMDAxMTEwMDEwMTAxMTEwMTAxMTAxMDAxMTAxMDEw"
    )
    binary_bytes = base64.b64decode(k)
    b64_bytes = bytes(
        int(binary_bytes[i: i + 8], 2) for i in range(0, len(binary_bytes), 8)
    )
    return base64.b64decode(b64_bytes).decode()


tvdb = TVDB(_get_tvdb_k())


class tvdb_data:
    def __init__(self, config):
        self.config = config
        pass

    async def search_tvdb_series(self, filename, year=None, debug=False):
        if debug:
            console.print(f"filename for TVDB search: {filename} year: {year}")
        results = tvdb.search({filename}, year=year, type="series", lang="eng")
        await asyncio.sleep(0.1)
        try:
            if results and len(results) > 0:
                # Try to find the best match based on year
                best_match = None
                search_year = str(year) if year else ''

                if search_year:
                    # First, try to find exact year match
                    for result in results:
                        if result.get('year') == search_year:
                            best_match = result
                            break

                # If no exact match, check aliases for year-based names
                if not best_match and search_year:
                    for result in results:
                        aliases = result.get('aliases', [])
                        if aliases:
                            # Check if any alias contains the year in parentheses
                            for alias in aliases:
                                alias_name = alias.get('name', '') if isinstance(alias, dict) else alias
                                if f"({search_year})" in alias_name:
                                    best_match = result
                                    break
                            if best_match:
                                break

                # If still no match, use first result
                if not best_match:
                    best_match = results[0]

                series_id = best_match['tvdb_id']
                if debug:
                    console.print(f"[blue]TVDB series ID: {series_id}[/blue]")
                return results, series_id
            else:
                console.print("[yellow]No TVDB results found[/yellow]")
                return None, None
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return None, None

    async def get_tvdb_episodes(self, series_id, debug=False):
        try:
            # Get all episodes for the series
            episodes = tvdb.get_series_episodes(
                series_id,
                season_type="default",
                lang="eng"
            )
            # Extract specific English alias only if it contains a year (e.g., "Cats eye (2025)")
            specific_alias = None
            if 'aliases' in episodes:
                # Pattern to match a 4-digit year in parentheses
                year_pattern = re.compile(r'\((\d{4})\)')
                eng_aliases = [
                    alias['name'] for alias in episodes['aliases']
                    if alias.get('language') == 'eng' and year_pattern.search(alias['name'])
                ]
                if eng_aliases:
                    # Get the last English alias with year (usually the most specific one)
                    specific_alias = eng_aliases[-1]
                    if debug:
                        console.print(f"[blue]English alias with year: {specific_alias}[/blue]")
            return episodes, specific_alias

        except Exception as e:
            console.print(f"[red]Error getting episodes: {e}[/red]")
            return None, None

    async def get_imdb_id_from_tvdb_episode_id(self, episode_id, debug=False):
        try:
            episode_data = tvdb.get_episode_extended(episode_id)
            if debug:
                console.print(f"[yellow]Episode data retrieved for episode ID {episode_id}[/yellow]")

            remote_ids = episode_data.get('remoteIds', [])
            imdb_id = None

            if isinstance(remote_ids, list):
                for remote_id in remote_ids:
                    if remote_id.get('type') == 2 or remote_id.get('sourceName') == 'IMDB':
                        imdb_id = remote_id.get('id')
                        break

            if imdb_id and debug:
                console.print(f"[blue]TVDB episode ID: {episode_id} maps to IMDB ID: {imdb_id}[/blue]")
            elif debug:
                console.print(f"[yellow]No IMDB ID found for TVDB episode ID: {episode_id}[/yellow]")

            return imdb_id
        except Exception as e:
            console.print(f"[red]Error getting IMDB ID from TVDB episode ID: {e}[/red]")
            return None

    async def get_specific_episode_data(self, data, season, episode, debug=False):
        if debug:
            console.print("[yellow]Getting specific episode data from TVDB data[/yellow]")

        # Handle both dict (full series data) and list (episodes only) formats
        if isinstance(data, dict):
            episodes = data.get('episodes', [])
        elif isinstance(data, list):
            episodes = data
        else:
            console.print("[red]No episode data available or invalid format[/red]")
            return None, None, None, None, None, None

        if not episodes:
            console.print("[red]No episodes found in data[/red]")
            return None, None, None, None, None, None

        # Convert season and episode to int for comparison
        try:
            season_int = int(season) if season is not None else None
            episode_int = int(episode) if episode is not None and episode != 0 else None
        except (ValueError, TypeError) as e:
            console.print(f"[red]Invalid season or episode format: season={season}, episode={episode}, error={e}[/red]")
            return None, None, None, None, None, None

        if season_int is None:
            console.print(f"[red]Season is None after conversion: season_int={season_int}[/red]")
            return None, None, None, None, None, None

        if debug:
            console.print(f"[blue]Total episodes retrieved from TVDB: {len(episodes)}[/blue]")
            console.print(f"[blue]Looking for Season: {season_int}, Episode: {episode_int}[/blue]")

        # If episode_int is None or 0, return first episode of the season
        if episode_int is None or episode_int == 0:
            for ep in episodes:
                if ep.get('seasonNumber') == season_int:
                    if debug:
                        console.print(f"[green]Found first episode of season {season_int}: S{season_int:02d}E{ep.get('number'):02d} - {ep.get('name')}[/green]")
                    return (
                        ep.get('seasonName'),
                        ep.get('name'),
                        ep.get('overview'),
                        ep.get('seasonNumber'),
                        ep.get('number'),
                        ep.get('year'),
                        ep.get('id')
                    )

        # Try to find exact season/episode match
        for ep in episodes:
            if ep.get('seasonNumber') == season_int and ep.get('number') == episode_int:
                if debug:
                    console.print(f"[green]Found exact match: S{season_int:02d}E{episode_int:02d} - {ep.get('name')}[/green]")
                return (
                    ep.get('seasonName'),
                    ep.get('name'),
                    ep.get('overview'),
                    ep.get('seasonNumber'),
                    ep.get('number'),
                    ep.get('year'),
                    ep.get('id')
                )

        # Try to find an episode with this absolute number directly
        console.print("[yellow]No exact match found, trying absolute number mapping...[/yellow]")
        for ep in episodes:
            if ep.get('absoluteNumber') == episode_int:
                mapped_season = ep.get('seasonNumber')
                mapped_episode = ep.get('number')
                if debug:
                    console.print(f"[green]Mapped absolute #{episode_int} -> S{mapped_season:02d}E{mapped_episode:02d} - {ep.get('name')}[/green]")
                return (
                    ep.get('seasonName'),
                    ep.get('name'),
                    ep.get('overview'),
                    ep.get('seasonNumber'),
                    ep.get('number'),
                    ep.get('year'),
                    ep.get('id')
                )

        console.print(f"[red]Could not find episode for S{season_int:02d}E{episode_int:02d} or absolute #{episode_int}[/red]")
        return None, None, None, None, None, None
