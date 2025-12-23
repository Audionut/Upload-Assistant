# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import json
import traceback
from src.console import console
from src.args import Args
from data.config import config


async def get_source_override(meta, other_id=False):
    try:
        with open(f"{meta['base_dir']}/data/templates/user-args.json", 'r', encoding="utf-8") as f:
            console.print("[green]Found user-args.json")
            user_args = json.load(f)

        current_tmdb_id = meta.get('tmdb_id', 0)
        current_imdb_id = meta.get('imdb_id', 0)
        current_tvdb_id = meta.get('tvdb_id', 0)

        # Convert to int for comparison if it's a string
        if isinstance(current_tmdb_id, str) and current_tmdb_id.isdigit():
            current_tmdb_id = int(current_tmdb_id)

        if isinstance(current_imdb_id, str) and current_imdb_id.isdigit():
            current_imdb_id = int(current_imdb_id)

        if isinstance(current_tvdb_id, str) and current_tvdb_id.isdigit():
            current_tvdb_id = int(current_tvdb_id)

        if not other_id:
            for entry in user_args.get('entries', []):
                entry_tmdb_id = entry.get('tmdb_id')
                args = entry.get('args', [])

                if not entry_tmdb_id:
                    continue

                # Parse the entry's TMDB ID from the user-args.json file
                entry_category, entry_normalized_id = await parse_tmdb_id(entry_tmdb_id)
                if entry_category != meta['category']:
                    if meta['debug']:
                        console.print(f"Skipping user entry because override category {entry_category} does not match UA category {meta['category']}:")
                    continue

                # Check if IDs match
                if entry_normalized_id == current_tmdb_id:
                    console.print(f"[green]Found matching override for TMDb ID: {entry_normalized_id}")
                    console.print(f"[yellow]Applying arguments: {' '.join(args)}")

                    meta = await apply_args_to_meta(meta, args)
                    break

        else:
            for entry in user_args.get('other_ids', []):
                # Check for TVDB ID match
                if 'tvdb_id' in entry and str(entry['tvdb_id']) == str(current_tvdb_id) and current_tvdb_id != 0:
                    args = entry.get('args', [])
                    console.print(f"[green]Found matching override for TVDb ID: {current_tvdb_id}")
                    console.print(f"[yellow]Applying arguments: {' '.join(args)}")
                    meta = await apply_args_to_meta(meta, args)
                    break

                # Check for IMDB ID match (without tt prefix)
                if 'imdb_id' in entry:
                    entry_imdb = entry['imdb_id']
                    if str(entry_imdb).startswith('tt'):
                        entry_imdb = entry_imdb[2:]

                    if str(entry_imdb) == str(current_imdb_id) and current_imdb_id != 0:
                        args = entry.get('args', [])
                        console.print(f"[green]Found matching override for IMDb ID: {current_imdb_id}")
                        console.print(f"[yellow]Applying arguments: {' '.join(args)}")
                        meta = await apply_args_to_meta(meta, args)
                        break

    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error loading user-args.json: {e}")

    return meta


async def parse_tmdb_id(tmdb_id, category=None):
    if tmdb_id is None:
        return category, 0

    tmdb_id = str(tmdb_id).strip().lower()
    if not tmdb_id or tmdb_id == 0:
        return category, 0

    if '/' in tmdb_id:
        parts = tmdb_id.split('/')
        if len(parts) >= 2:
            prefix = parts[0]
            id_part = parts[1]

            if prefix == 'tv':
                category = 'TV'
            elif prefix == 'movie':
                category = 'MOVIE'

            try:
                normalized_id = int(id_part)
                return category, normalized_id
            except ValueError:
                return category, 0

    try:
        normalized_id = int(tmdb_id)
        return category, normalized_id
    except ValueError:
        return category, 0


async def apply_args_to_meta(meta, args):
    try:
        arg_keys_to_track = set()
        arg_values = {}

        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith('--'):
                # Remove '--' prefix and convert dashes to underscores
                key = arg[2:].replace('-', '_')
                arg_keys_to_track.add(key)

                # Store the value if it exists
                if i + 1 < len(args) and not args[i + 1].startswith('--'):
                    arg_values[key] = args[i + 1]  # Store the value with its key
                    i += 1
            i += 1

        if meta['debug']:
            console.print(f"[Debug] Tracking changes for keys: {', '.join(arg_keys_to_track)}")

        # Create a new Args instance and process the arguments
        arg_processor = Args(config)
        full_args = ['upload.py'] + args
        updated_meta, _, _ = arg_processor.parse(full_args, meta.copy())
        updated_meta['path'] = meta.get('path')
        modified_keys = []

        # Handle ID arguments specifically
        id_mappings = {
            'tmdb': ['tmdb_id', 'tmdb', 'tmdb_manual'],
            'tvmaze': ['tvmaze_id', 'tvmaze', 'tvmaze_manual'],
            'imdb': ['imdb_id', 'imdb', 'imdb_manual'],
            'tvdb': ['tvdb_id', 'tvdb', 'tvdb_manual'],
        }

        for key in arg_keys_to_track:
            # Special handling for ID fields
            if key in id_mappings:
                if key in arg_values:  # Check if we have a value for this key
                    value = arg_values[key]
                    # Convert to int if possible
                    try:
                        if isinstance(value, str) and value.isdigit():
                            value = int(value)
                        elif isinstance(value, str) and key == 'imdb' and value.startswith('tt'):
                            value = int(value[2:])  # Remove 'tt' prefix and convert to int
                    except ValueError:
                        pass

                    # Update all related keys
                    for related_key in id_mappings[key]:
                        meta[related_key] = value
                        modified_keys.append(related_key)
                        if meta['debug']:
                            console.print(f"[Debug] Override: {related_key} changed from {meta.get(related_key)} to {value}")
            # Handle regular fields
            elif key in updated_meta and key in meta:
                # Skip path to preserve original
                if key == 'path':
                    continue

                new_value = updated_meta[key]
                old_value = meta[key]
                # Only update if the value actually changed
                if new_value != old_value:
                    meta[key] = new_value
                    modified_keys.append(key)
                    if meta['debug']:
                        console.print(f"[Debug] Override: {key} changed from {old_value} to {new_value}")
        if meta['debug'] and modified_keys:
            console.print(f"[Debug] Applied overrides for: {', '.join(modified_keys)}")

    except Exception as e:
        console.print(f"[red]Error processing arguments: {e}")
        if meta['debug']:
            console.print(traceback.format_exc())

    return meta
