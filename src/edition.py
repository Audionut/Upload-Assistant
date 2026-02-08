# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
from typing import Any, Callable, Optional, Union, cast

import guessit

from src.console import console
from src.region import get_distributor

guessit_module: Any = cast(Any, guessit)
GuessitFn = Callable[[str, Optional[dict[str, Any]]], dict[str, Any]]


def guessit_fn(value: str, options: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return cast(dict[str, Any], guessit_module.guessit(value, options))


def get_edition(video: str, bdinfo: Optional[dict[str, Any]], filelist: list[str], manual_edition: Union[str, list[str]], meta: dict[str, Any]) -> tuple[str, str, bool]:
    edition = ""
    imdb_info = cast(dict[str, Any], meta.get('imdb_info', {}))
    edition_details = cast(dict[str, dict[str, Any]], imdb_info.get('edition_details', {}))

    if meta.get('category') == "MOVIE" and not meta.get('anime') and edition_details and not manual_edition:
        if meta.get('is_disc') != "BDMV" and meta.get('mediainfo', {}).get('media', {}).get('track'):
                mediainfo = cast(dict[str, Any], meta.get('mediainfo', {}))
                tracks = cast(list[dict[str, Any]], mediainfo.get('media', {}).get('track', []))
                general_track = next((track for track in tracks if track.get('@type') == 'General'), None)

                if general_track and general_track.get('Duration'):
                    try:
                        media_duration_seconds = float(general_track['Duration'])
                        formatted_duration = format_duration(media_duration_seconds)
                        if meta['debug']:
                            console.print(f"[cyan]Found media duration: {formatted_duration} ({media_duration_seconds} seconds)[/cyan]")

                        leeway_seconds = 50
                        matching_editions: list[dict[str, Any]] = []

                        # Find all matching editions
                        for edition_info in edition_details.values():
                            edition_seconds = float(edition_info.get('seconds', 0) or 0)
                            edition_formatted = format_duration(edition_seconds)
                            difference = abs(media_duration_seconds - edition_seconds)

                            if difference <= leeway_seconds:
                                attributes = edition_info.get('attributes')
                                attributes_list = cast(list[Any], attributes) if isinstance(attributes, list) else []
                                has_attributes = bool(attributes_list)
                                if meta['debug']:
                                    console.print(f"[green]Potential match: {edition_info.get('display_name', '')} - duration {edition_formatted}, difference: {format_duration(difference)}[/green]")

                                if has_attributes:
                                    edition_name = " ".join(smart_title(str(attr)) for attr in attributes_list)

                                    matching_editions.append({
                                        'name': edition_name,
                                        'display_name': str(edition_info.get('display_name', '')),
                                        'has_attributes': bool(edition_info.get('attributes') and len(edition_info['attributes']) > 0),
                                        'minutes': edition_info.get('minutes'),
                                        'difference': difference,
                                        'formatted_duration': edition_formatted
                                    })
                                else:
                                    if meta['debug']:
                                        console.print("[yellow]Edition without attributes are theatrical editions and skipped[/yellow]")

                        if len(matching_editions) > 1:
                            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                                console.print(f"[yellow]Media file duration {formatted_duration} matches multiple editions:[/yellow]")
                                for i, ed in enumerate(matching_editions):
                                    diff_formatted = format_duration(float(ed.get('difference', 0) or 0))
                                    console.print(f"[yellow]{i+1}. [green]{ed.get('name', '')} ({ed.get('display_name', '')}, duration: {ed.get('formatted_duration', '')}, diff: {diff_formatted})[/yellow]")

                                try:
                                    choice = console.input(f"[yellow]Select edition number (1-{len(matching_editions)}) or press Enter to use the closest match: [/yellow]")

                                    if choice.strip() and choice.isdigit() and 1 <= int(choice) <= len(matching_editions):
                                        selected = matching_editions[int(choice)-1]
                                    else:
                                        selected = min(matching_editions, key=lambda x: float(x.get('difference', 0) or 0))
                                        console.print(f"[yellow]Using closest match: {selected.get('name', '')}[/yellow]")
                                except Exception as e:
                                    console.print(f"[red]Error processing selection: {e}. Using closest match.[/red]")
                                    selected = min(matching_editions, key=lambda x: float(x.get('difference', 0) or 0))
                            else:
                                selected = min(matching_editions, key=lambda x: float(x.get('difference', 0) or 0))
                                console.print(f"[yellow]Multiple matches found in unattended mode. Using closest match: {selected.get('name', '')}[/yellow]")

                            edition = str(selected.get('name', '')) if selected.get('has_attributes') else ""

                            console.print(f"[bold green]Setting edition from duration match: {edition}[/bold green]")

                        elif len(matching_editions) == 1:
                            selected = matching_editions[0]
                            edition = str(selected.get('name', '')) if selected.get('has_attributes') else ""  # No special edition for single matches without attributes

                            console.print(f"[bold green]Setting edition from duration match: {edition}[/bold green]")

                        else:
                            if meta['debug']:
                                console.print(f"[yellow]No matching editions found within {leeway_seconds} seconds of media duration[/yellow]")

                    except (ValueError, TypeError) as e:
                        console.print(f"[yellow]Error parsing duration: {e}[/yellow]")

        elif meta.get('is_disc') == "BDMV" and meta.get('discs'):
            if meta['debug']:
                console.print("[cyan]Checking BDMV playlists for edition matches...[/cyan]")
            matched_editions: list[str] = []

            all_playlists: list[dict[str, Any]] = []
            discs = cast(list[dict[str, Any]], meta.get('discs', []))
            for disc in discs:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    playlists = disc.get('playlists')
                    if isinstance(playlists, list):
                        all_playlists.extend(cast(list[dict[str, Any]], playlists))
                else:
                    valid_playlists = disc.get('all_valid_playlists')
                    if isinstance(valid_playlists, list):
                        all_playlists.extend(cast(list[dict[str, Any]], valid_playlists))
            if meta['debug']:
                console.print(f"[cyan]Found {len(all_playlists)} playlists to check against IMDb editions[/cyan]")

            leeway_seconds = 50
            matched_editions_with_attributes: list[str] = []
            matched_editions_without_attributes: list[str] = []

            for playlist in all_playlists:
                playlist_file = str(playlist.get('file') or "")
                playlist_edition = str(playlist.get('edition') or "")
                if playlist.get('duration'):
                    playlist_duration = float(playlist.get('duration') or 0)
                    formatted_duration = format_duration(playlist_duration)
                    if meta['debug']:
                        console.print(f"[cyan]Checking playlist duration: {formatted_duration} seconds[/cyan]")

                    playlist_matching_editions: list[dict[str, Any]] = []

                    for edition_info in edition_details.values():
                        edition_seconds = float(edition_info.get('seconds', 0) or 0)
                        difference = abs(playlist_duration - edition_seconds)

                        if difference <= leeway_seconds:
                            # Store the complete edition info
                            attributes = edition_info.get('attributes')
                            attributes_list = cast(list[Any], attributes) if isinstance(attributes, list) else []
                            if attributes_list:
                                edition_name = " ".join(smart_title(str(attr)) for attr in attributes_list)
                            else:
                                edition_name = f"{edition_info.get('minutes')} Minute Version (Theatrical)"

                            playlist_matching_editions.append({
                                'name': edition_name,
                                'display_name': str(edition_info.get('display_name', '')),
                                'has_attributes': bool(edition_info.get('attributes') and len(edition_info['attributes']) > 0),
                                'minutes': edition_info.get('minutes'),
                                'difference': difference
                            })

                    # If multiple editions match this playlist, ask the user
                    if len(playlist_matching_editions) > 1:
                        if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                            console.print(f"[yellow]Playlist edition [green]{playlist_edition} [yellow]using file [green]{playlist_file} [yellow]with duration [green]{formatted_duration} [yellow]matches multiple editions:[/yellow]")
                            for i, ed in enumerate(playlist_matching_editions):
                                console.print(f"[yellow]{i+1}. [green]{ed['name']} ({ed['display_name']}, diff: {ed['difference']:.2f} seconds)")

                            try:
                                choice = console.input(f"[yellow]Select edition number (1-{len(playlist_matching_editions)}), press e to use playlist edition or press Enter to use the closest match: [/yellow]")

                                playlist_selected: Union[str, dict[str, Any]]

                                if choice.strip() and choice.isdigit() and 1 <= int(choice) <= len(playlist_matching_editions):
                                    playlist_selected = playlist_matching_editions[int(choice)-1]
                                elif choice.strip().lower() == 'e':
                                    playlist_selected = str(playlist_edition)
                                else:
                                    # Default to the closest match (smallest difference)
                                    playlist_selected = min(playlist_matching_editions, key=lambda x: x['difference'])
                                    console.print(f"[yellow]Using closest match: {playlist_selected['name']}[/yellow]")

                                # Add the selected edition to our matches
                                if isinstance(playlist_selected, str):
                                    normalized_playlist = playlist_selected.strip().lower()
                                    if not normalized_playlist:
                                        # Empty playlist edition, fall back to closest match
                                        console.print("[yellow]Empty playlist edition, using closest match.[/yellow]")
                                        playlist_selected = min(playlist_matching_editions, key=lambda x: x['difference'])
                                        if playlist_selected['has_attributes']:
                                            if playlist_selected['name'] not in matched_editions_with_attributes:
                                                matched_editions_with_attributes.append(playlist_selected['name'])
                                                console.print(f"[green]Added edition with attributes: {playlist_selected['name']}[/green]")
                                        else:
                                            matched_editions_without_attributes.append(str(playlist_selected['minutes']))
                                            console.print(f"[yellow]Added edition without attributes: {playlist_selected['name']}[/yellow]")
                                    elif normalized_playlist in ("theatrical", "theater", "theatre"):
                                        # Theatrical is a non-attribute edition; use closest match's minutes
                                        console.print(f"[yellow]Playlist edition '{playlist_selected}' is theatrical, treating as non-attribute edition.[/yellow]")
                                        fallback = min(playlist_matching_editions, key=lambda x: x['difference'])
                                        matched_editions_without_attributes.append(str(fallback['minutes']))
                                    else:
                                        # Genuine attribute edition from playlist
                                        if playlist_selected.strip() not in matched_editions_with_attributes:
                                            matched_editions_with_attributes.append(playlist_selected.strip())
                                            console.print(f"[green]Using playlist edition: {playlist_selected}[/green]")
                                        else:
                                            console.print(f"[yellow]Playlist edition '{playlist_selected}' already added, skipping duplicate.[/yellow]")
                                else:
                                    if playlist_selected['has_attributes']:
                                        if playlist_selected['name'] not in matched_editions_with_attributes:
                                            matched_editions_with_attributes.append(playlist_selected['name'])
                                            console.print(f"[green]Added edition with attributes: {playlist_selected['name']}[/green]")
                                    else:
                                        matched_editions_without_attributes.append(str(playlist_selected['minutes']))
                                        console.print(f"[yellow]Added edition without attributes: {playlist_selected['name']}[/yellow]")

                            except Exception as e:
                                console.print(f"[red]Error processing selection: {e}. Using closest match.[/red]")
                                # Default to closest match
                                fallback_selected = min(playlist_matching_editions, key=lambda x: x['difference'])
                                if fallback_selected['has_attributes']:
                                    matched_editions_with_attributes.append(fallback_selected['name'])
                                else:
                                    matched_editions_without_attributes.append(str(fallback_selected['minutes']))
                        else:
                            console.print(f"[yellow]Playlist edition [green]{playlist_edition} [yellow]using file [green]{playlist_file} [yellow]with duration [green]{formatted_duration} [yellow]matches multiple editions, but unattended mode is enabled. Using closest match.[/yellow]")
                            unattended_selected = min(playlist_matching_editions, key=lambda x: x['difference'])
                            if unattended_selected['has_attributes']:
                                matched_editions_with_attributes.append(unattended_selected['name'])
                            else:
                                matched_editions_without_attributes.append(str(unattended_selected['minutes']))

                    # If just one edition matches, add it directly
                    elif len(playlist_matching_editions) == 1:
                        edition_info = playlist_matching_editions[0]
                        if meta['debug']:
                            console.print(f"[green]Playlist {playlist_edition} matches edition: {edition_info['display_name']} {edition_info['name']}[/green]")

                        if edition_info['has_attributes']:
                            if edition_info['name'] not in matched_editions_with_attributes:
                                matched_editions_with_attributes.append(edition_info['name'])
                                if meta['debug']:
                                    console.print(f"[green]Added edition with attributes: {edition_info['name']}[/green]")
                        else:
                            matched_editions_without_attributes.append(str(edition_info['minutes']))
                            if meta['debug']:
                                console.print(f"[yellow]Added edition without attributes: {edition_info['name']}[/yellow]")

                # Process the matched editions
                if matched_editions_with_attributes or matched_editions_without_attributes:
                    # Only use "Theatrical" if we have at least one edition with attributes
                    if matched_editions_with_attributes and matched_editions_without_attributes:
                        matched_editions = matched_editions_with_attributes + ["Theatrical"]
                        if meta['debug']:
                            console.print("[cyan]Adding 'Theatrical' label because we have both attribute and non-attribute editions[/cyan]")
                    elif matched_editions_with_attributes:
                        matched_editions = matched_editions_with_attributes
                        if meta['debug']:
                            console.print("[cyan]Using only editions with attributes[/cyan]")
                    else:
                        if meta['debug']:
                            console.print("[cyan]No useful editions found[/cyan]")

                    # Handle final edition formatting
                    if matched_editions:
                        # If multiple editions, prefix with count
                        if len(matched_editions) > 1:
                            unique_editions = list(set(matched_editions))  # Remove duplicates
                            if "Theatrical" in unique_editions:
                                unique_editions.remove("Theatrical")
                                unique_editions = ["Theatrical"] + sorted(unique_editions)
                            edition = f"{len(unique_editions)}in1 " + " / ".join(unique_editions) if len(unique_editions) > 1 else unique_editions[0]  # Just one unique edition
                        else:
                            edition = matched_editions[0]

                        if meta['debug']:
                            console.print(f"[bold green]Setting edition from BDMV playlist matches: {edition}[/bold green]")

    if edition and (edition.lower() in ["cut", "approximate"] or len(edition) < 6):
        edition = ""
    if edition and "edition" in edition.lower():
        edition = re.sub(r'\bedition\b', '', edition, flags=re.IGNORECASE).strip()
    if edition and "extended" in edition.lower():
        edition = "Extended"

    if not edition:
        if video.lower().startswith('dc'):
            video = video.lower().replace('dc', '', 1)

        guess: Any = guessit_fn(video)

        tag_value: Any = guess.get('release_group', 'NOGROUP')
        tag = " ".join(str(t) for t in cast(list[Any], tag_value)) if isinstance(tag_value, list) else str(tag_value)
        repack = ""

        if bdinfo is not None:
            try:
                edition_value: Any = guessit_fn(bdinfo['label']).get('edition', '')
            except Exception as e:
                if meta['debug']:
                    console.print(f"BDInfo Edition Guess Error: {e}", markup=False)
                edition_value = ""
        else:
            try:
                edition_value = guess.get('edition', "")
            except Exception as e:
                if meta['debug']:
                    console.print(f"Video Edition Guess Error: {e}", markup=False)
                edition_value = ""

        edition = " ".join(str(e) for e in cast(list[Any], edition_value)) if isinstance(edition_value, list) else str(edition_value or "")

        if len(filelist) == 1:
            video = os.path.basename(video)

        video = video.upper().replace('.', ' ').replace(tag.upper(), '').replace('-', '')

        if "OPEN MATTE" in video.upper():
            edition = edition + " Open Matte"

    # Manual edition overrides everything
    if manual_edition:
        if isinstance(manual_edition, list):
            manual_edition = " ".join(str(e) for e in manual_edition)
        edition = str(manual_edition)

    edition = edition.replace(",", " ")

    # Handle repack info
    repack = ""
    if "REPACK" in (video.upper() or edition.upper()) or "V2" in video:
        repack = "REPACK"
    if "REPACK2" in (video.upper() or edition.upper()) or "V3" in video:
        repack = "REPACK2"
    if "REPACK3" in (video.upper() or edition.upper()) or "V4" in video:
        repack = "REPACK3"
    if "PROPER" in (video.upper() or edition.upper()):
        repack = "PROPER"
    if "PROPER2" in (video.upper() or edition.upper()):
        repack = "PROPER2"
    if "PROPER3" in (video.upper() or edition.upper()):
        repack = "PROPER3"
    if "RERIP" in (video.upper() or edition.upper()):
        repack = "RERIP"

    # Only remove REPACK, RERIP, or PROPER from edition if not in manual edition
    if not manual_edition or (isinstance(manual_edition, str) and all(tag.lower() not in ['repack', 'repack2', 'repack3', 'proper', 'proper2', 'proper3', 'rerip'] for tag in manual_edition.strip().lower().split())):
        edition = re.sub(r"(\bREPACK\d?\b|\bRERIP\b|\bPROPER\b)", "", edition, flags=re.IGNORECASE).strip()

    if not meta.get('webdv', False):
        hybrid = False
        if "HYBRID" in video.upper() or "HYBRID" in edition.upper():
            hybrid = True
    else:
        hybrid = meta.get('webdv', False)

    # Handle distributor info
    if edition:
        distributors = get_distributor(edition)

        bad = ['internal', 'limited', 'retail', 'version', 'remastered']

        if distributors and meta['is_disc']:
            bad.append(distributors.lower())
            meta['distributor'] = distributors

        if any(term.lower() in edition.lower() for term in bad):
            edition = re.sub(r'\b(?:' + '|'.join(bad) + r')\b', '', edition, flags=re.IGNORECASE).strip()
            # Clean up extra spaces
            while '  ' in edition:
                edition = edition.replace('  ', ' ')

        if edition != "":
            edition = edition.strip().upper()
            if meta['debug']:
                console.print(f"Final Edition: {edition}")

    return edition, repack, hybrid


def format_duration(seconds: float) -> str:
    """Convert seconds to a human-readable HH:MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def smart_title(s: str) -> str:
    """Custom title function that doesn't capitalize after apostrophes"""
    result = s.title()
    # Fix capitalization after apostrophes
    return re.sub(r"(\w)'(\w)", lambda m: f"{m.group(1)}'{m.group(2).lower()}", result)
