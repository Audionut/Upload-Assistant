# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# Restricted-use credential — permitted only under UAPL v1.0 and associated service provider terms
import asyncio
import base64
import json
import os
import re
import ssl
from urllib.error import URLError
from pathlib import Path
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


tvdb = None
_TVDB_INIT_ERROR = None
_TVDB_ERROR_REPORTED = False

try:
    tvdb = TVDB(_get_tvdb_k())
except (ssl.SSLError, URLError) as e:
    _TVDB_INIT_ERROR = e
except Exception as e:
    _TVDB_INIT_ERROR = e


def _get_tvdb_or_warn():
    global _TVDB_ERROR_REPORTED

    if tvdb is not None:
        return tvdb

    if not _TVDB_ERROR_REPORTED:
        _TVDB_ERROR_REPORTED = True
        if _TVDB_INIT_ERROR:
            console.print(
                "[yellow]TVDB login failed; continuing without TVDB. "
                f"Reason: {_TVDB_INIT_ERROR}[/yellow]"
            )
            console.print(
                "[yellow]This is usually a local Python CA/cert issue. "
                "Fix options: install/update Windows roots, or set SSL_CERT_FILE to certifi's bundle "
                "(e.g. `python -c \"import certifi; print(certifi.where())\"`).[/yellow]"
            )
        else:
            console.print("[yellow]TVDB unavailable; continuing without TVDB.[/yellow]")

    return None


class tvdb_data:
    def __init__(self, config):
        self.config = config
        pass

    async def search_tvdb_series(self, filename, year=None, debug=False):
        if debug:
            console.print(f"filename for TVDB search: {filename} year: {year}")
        client = _get_tvdb_or_warn()
        if client is None:
            return None, None

        results = client.search({filename}, year=year, type="series", lang="eng")
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

    async def get_tvdb_episodes(self, series_id, base_dir=None, debug=False, season=None, episode=None, absolute_number=None, aired_date=None):
        # Backward compat: older call sites used (series_id, debug)
        if isinstance(base_dir, bool) and debug is False:
            debug = base_dir
            base_dir = None

        def _episode_is_present(episodes: list) -> bool:
            if not episodes:
                return False

            # If no specific episode requested, any cached payload is acceptable.
            if season is None and episode is None and absolute_number is None and not aired_date:
                return True

            aired_norm = None
            if aired_date:
                aired_norm = str(aired_date).strip().replace('.', '-')

            # Normalize numeric inputs
            try:
                season_int = int(season) if season is not None else None
            except (TypeError, ValueError):
                season_int = None

            try:
                episode_int = int(episode) if episode is not None else None
            except (TypeError, ValueError):
                episode_int = None

            try:
                absolute_int = int(absolute_number) if absolute_number is not None else None
            except (TypeError, ValueError):
                absolute_int = None

            # For daily-style episodes, match by aired date.
            if aired_norm:
                for ep in episodes:
                    if isinstance(ep, dict) and ep.get('aired') == aired_norm:
                        return True

            # Treat episode==0/None as "no specific episode" (season packs, etc.)
            if episode_int in (None, 0) and absolute_int is None and not aired_norm:
                return True

            for ep in episodes:
                if not isinstance(ep, dict):
                    continue

                if absolute_int is not None and ep.get('absoluteNumber') == absolute_int:
                    return True

                if season_int is not None and episode_int not in (None, 0):
                    if ep.get('seasonNumber') == season_int and ep.get('number') == episode_int:
                        return True

            return False

        cache_path = None
        if base_dir:
            try:
                cache_dir = Path(base_dir) / 'data' / 'tvdb'
                cache_path = cache_dir / f"{series_id}.json"

                if cache_path.exists():
                    with cache_path.open('r', encoding='utf-8') as f:
                        cached = json.load(f)

                    if isinstance(cached, dict) and isinstance(cached.get('episodes'), list):
                        if not _episode_is_present(cached.get('episodes', [])):
                            if debug:
                                console.print(
                                    f"[yellow]Cached TVDB data for {series_id} does not include requested episode; refreshing from TVDB[/yellow]"
                                )
                        else:
                            if debug:
                                console.print(f"[cyan]Using cached TVDB episodes for {series_id}[/cyan]")

                            episodes_data = {
                                'episodes': cached.get('episodes', []),
                                'aliases': cached.get('aliases', []) if isinstance(cached.get('aliases', []), list) else []
                            }

                            specific_alias = None
                            if episodes_data.get('aliases'):
                                year_pattern = re.compile(r'\((\d{4})\)')
                                eng_aliases = [
                                    alias['name'] for alias in episodes_data['aliases']
                                    if isinstance(alias, dict) and alias.get('language') == 'eng' and year_pattern.search(alias.get('name', ''))
                                ]
                                if eng_aliases:
                                    specific_alias = eng_aliases[-1]
                                    if debug:
                                        console.print(f"[blue]English alias with year: {specific_alias}[/blue]")

                            return episodes_data, specific_alias
            except Exception as cache_error:
                if debug:
                    console.print(f"[yellow]Failed to read TVDB cache for {series_id}: {cache_error}[/yellow]")

        try:
            client = _get_tvdb_or_warn()
            if client is None:
                return None, None

            # Get all episodes for the series with pagination
            all_episodes = []
            page = 0
            max_pages = 20  # Safety limit to prevent infinite loops
            pages_fetched = 0

            while page < max_pages:
                if debug and page > 0:
                    console.print(f"[cyan]Fetching TVDB episodes page {page + 1}[/cyan]")

                try:
                    episodes_response = client.get_series_episodes(
                        series_id,
                        season_type="default",
                        page=page,
                        lang="eng"
                    )

                    # Handle both dict response and direct episodes list
                    if isinstance(episodes_response, dict):
                        current_episodes = episodes_response.get('episodes', [])
                    else:
                        # Fallback for direct list response
                        current_episodes = episodes_response if isinstance(episodes_response, list) else []

                    if not current_episodes:
                        if debug:
                            console.print(f"[yellow]No episodes found on page {page + 1}, stopping pagination[/yellow]")
                        break

                    all_episodes.extend(current_episodes)
                    pages_fetched += 1

                    if debug:
                        console.print(f"[cyan]Retrieved {len(current_episodes)} episodes from page {page + 1} (total: {len(all_episodes)})[/cyan]")

                    # If we got fewer than 500 results, we've reached the end
                    if len(current_episodes) < 500:
                        if debug:
                            console.print(f"[cyan]Page {page + 1} returned {len(current_episodes)} episodes (< 500), pagination complete[/cyan]")
                        break

                    page += 1
                    await asyncio.sleep(0.1)  # Rate limiting

                except Exception as page_error:
                    if debug:
                        console.print(f"[yellow]Error fetching page {page + 1}: {page_error}[/yellow]")
                    # If first page fails, re-raise; otherwise, stop pagination
                    if page == 0:
                        raise page_error
                    else:
                        break

            if debug:
                console.print(f"[green]Total episodes retrieved: {len(all_episodes)} across {page + 1} page(s)[/green]")

            # Create the response structure
            episodes_data = {
                'episodes': all_episodes,
                'aliases': []  # Will be populated if available from first response
            }

            # Try to get aliases from series info (may need separate call)
            try:
                if all_episodes:
                    # Get series details for aliases
                    series_info = client.get_series_extended(series_id)
                    if 'aliases' in series_info:
                        episodes_data['aliases'] = series_info['aliases']
            except Exception as alias_error:
                if debug:
                    console.print(f"[yellow]Could not retrieve series aliases: {alias_error}[/yellow]")

            # If this was a multi-page series and we have a base_dir, cache results for next time.
            if cache_path and pages_fetched > 1:
                try:
                    # Ensure cache dir exists; on POSIX explicitly apply typical dir perms.
                    if os.name == 'posix':
                        cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                        try:
                            os.chmod(cache_path.parent, 0o700)
                        except Exception:
                            pass
                    else:
                        cache_path.parent.mkdir(parents=True, exist_ok=True)

                    with cache_path.open('w', encoding='utf-8') as f:
                        json.dump(episodes_data, f, ensure_ascii=False)

                    if os.name == 'posix':
                        try:
                            os.chmod(cache_path, 0o644)
                        except Exception:
                            pass
                    if debug:
                        console.print(f"[green]Cached TVDB episodes to {cache_path}[/green]")
                except Exception as cache_write_error:
                    if debug:
                        console.print(f"[yellow]Failed to write TVDB cache for {series_id}: {cache_write_error}[/yellow]")

            # Extract specific English alias only if it contains a year (e.g., "Cats eye (2025)")
            specific_alias = None
            if 'aliases' in episodes_data and episodes_data['aliases']:
                # Pattern to match a 4-digit year in parentheses
                year_pattern = re.compile(r'\((\d{4})\)')
                eng_aliases = [
                    alias['name'] for alias in episodes_data['aliases']
                    if alias.get('language') == 'eng' and year_pattern.search(alias['name'])
                ]
                if eng_aliases:
                    # Get the last English alias with year (usually the most specific one)
                    specific_alias = eng_aliases[-1]
                    if debug:
                        console.print(f"[blue]English alias with year: {specific_alias}[/blue]")

            return episodes_data, specific_alias

        except Exception as e:
            console.print(f"[red]Error getting episodes: {e}[/red]")
            return None, None

    async def get_tvdb_by_external_id(self, imdb, tmdb, debug=False, tv_movie=False):
        client = _get_tvdb_or_warn()
        if client is None:
            return None

        # Try IMDB first if available
        if imdb:
            try:
                if isinstance(imdb, str) and imdb.startswith('tt'):
                    imdb_formatted = imdb
                elif isinstance(imdb, str) and imdb.isdigit():
                    imdb_formatted = f"tt{int(imdb):07d}"
                elif isinstance(imdb, int):
                    imdb_formatted = f"tt{imdb:07d}"
                else:
                    imdb_formatted = str(imdb)

                if debug:
                    console.print(f"[cyan]Trying TVDB lookup with IMDB ID: {imdb_formatted}[/cyan]")

                results = client.search_by_remote_id(imdb_formatted)
                await asyncio.sleep(0.1)

                if results and len(results) > 0:
                    if debug:
                        console.print(f"[blue]results: {results}[/blue]")

                    # Look for series results first
                    for result in results:
                        if 'series' in result:
                            series_id = result['series']['id']
                            if debug:
                                console.print(f"[blue]TVDB series ID from IMDB: {series_id}[/blue]")
                            return series_id

                    # If tv_movie is True, check for episode with seriesId first, then movie
                    if tv_movie:
                        # Check if any result has an episode with a seriesId
                        for result in results:
                            if 'episode' in result and result['episode'].get('seriesId'):
                                series_id = result['episode']['seriesId']
                                if debug:
                                    console.print(f"[blue]TVDB series ID from episode entry (tv_movie): {series_id}[/blue]")
                                return series_id

                        # If no episode with seriesId, accept movie results
                        for result in results:
                            if 'movie' in result:
                                movie_id = result['movie']['id']
                                if debug:
                                    console.print(f"[blue]TVDB movie ID from IMDB (tv_movie): {movie_id}[/blue]")
                                return movie_id

                    if debug:
                        result_types = [list(result.keys())[0] for result in results if result]
                        console.print(f"[yellow]IMDB search returned results but no {'series or movie' if tv_movie else 'series'} found (got: {result_types})[/yellow]")
                else:
                    if debug:
                        console.print("[yellow]No TVDB series found for IMDB ID[/yellow]")
            except Exception as e:
                if debug:
                    console.print(f"[red]Error getting TVDB by IMDB ID: {e}[/red]")

        if tmdb:
            try:
                tmdb_str = str(tmdb)

                if debug:
                    console.print(f"[cyan]Trying TVDB lookup with TMDB ID: {tmdb_str}[/cyan]")

                results = client.search_by_remote_id(tmdb_str)
                await asyncio.sleep(0.1)

                if results and len(results) > 0:
                    if debug:
                        console.print(f"[blue]results: {results}[/blue]")

                    # Look for series results first
                    for result in results:
                        if 'series' in result:
                            series_id = result['series']['id']
                            if debug:
                                console.print(f"[blue]TVDB series ID from TMDB: {series_id}[/blue]")
                            return series_id

                    # If tv_movie is True, check for episode with seriesId first, then movie
                    if tv_movie:
                        # Check if any result has an episode with a seriesId
                        for result in results:
                            if 'episode' in result and result['episode'].get('seriesId'):
                                series_id = result['episode']['seriesId']
                                if debug:
                                    console.print(f"[blue]TVDB series ID from episode entry (tv_movie): {series_id}[/blue]")
                                return series_id

                        # If no episode with seriesId, accept movie results
                        for result in results:
                            if 'movie' in result:
                                movie_id = result['movie']['id']
                                if debug:
                                    console.print(f"[blue]TVDB movie ID from TMDB (tv_movie): {movie_id}[/blue]")
                                return movie_id

                    if debug:
                        result_types = [list(result.keys())[0] for result in results if result]
                        console.print(f"[yellow]TMDB search returned results but no {'series or movie' if tv_movie else 'series'} found (got: {result_types})[/yellow]")
                else:
                    if debug:
                        console.print("[yellow]No TVDB series found for TMDB ID[/yellow]")
            except Exception as e:
                if debug:
                    console.print(f"[red]Error getting TVDB by TMDB ID: {e}[/red]")

        result_type_str = "series or movie" if tv_movie else "series"
        console.print(f"[yellow]No TVDB {result_type_str} found for any available external ID[/yellow]")
        return None

    async def get_imdb_id_from_tvdb_episode_id(self, episode_id, debug=False):
        try:
            client = _get_tvdb_or_warn()
            if client is None:
                return None

            episode_data = client.get_episode_extended(episode_id)
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

    async def get_specific_episode_data(self, data, season, episode, debug=False, aired_date=None):
        if debug:
            console.print("[yellow]Getting specific episode data from TVDB data[/yellow]")

        # Handle both dict (full series data) and list (episodes only) formats
        if isinstance(data, dict):
            episodes = data.get('episodes', [])
        elif isinstance(data, list):
            episodes = data
        else:
            console.print("[red]No episode data available or invalid format[/red]")
            return None, None, None, None, None, None, None

        if not episodes:
            console.print("[red]No episodes found in data[/red]")
            return None, None, None, None, None, None, None

        # Convert season and episode to int for comparison
        try:
            season_int = int(season) if season is not None else None
            episode_int = int(episode) if episode is not None and episode != 0 else None
        except (ValueError, TypeError) as e:
            console.print(f"[red]Invalid season or episode format: season={season}, episode={episode}, error={e}[/red]")
            return None, None, None, None, None, None, None

        if season_int is None:
            console.print(f"[red]Season is None after conversion: season_int={season_int}[/red]")
            return None, None, None, None, None, None, None

        if debug:
            console.print(f"[blue]Total episodes retrieved from TVDB: {len(episodes)}[/blue]")
            console.print(f"[blue]Looking for Season: {season_int}, Episode: {episode_int}[/blue]")

        # For daily shows, match by air date if provided.
        if aired_date:
            aired_norm = str(aired_date).strip().replace('.', '-')
            for ep in episodes:
                if ep.get('aired') == aired_norm:
                    if debug:
                        console.print(f"[green]Matched daily episode by air date {aired_norm}: S{ep.get('seasonNumber'):02d}E{ep.get('number'):02d} - {ep.get('name')}[/green]")
                    return (
                        ep.get('seasonName'),
                        ep.get('name'),
                        ep.get('overview'),
                        ep.get('seasonNumber'),
                        ep.get('number'),
                        ep.get('year'),
                        ep.get('id')
                    )

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
        return None, None, None, None, None, None, None
