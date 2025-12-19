# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import json
import glob
import click
import re

from src.console import console
from rich.markdown import Markdown
from rich.style import Style


async def process_site_upload_queue(meta, base_dir):
    site_upload = meta.get('site_upload')
    if not site_upload:
        return [], None

    # Get the search results file path
    search_results_file = os.path.join(base_dir, "tmp", f"{site_upload}_search_results.json")

    if not os.path.exists(search_results_file):
        console.print(f"[red]Search results file not found: {search_results_file}[/red]")
        return [], None

    try:
        with open(search_results_file, 'r', encoding='utf-8') as f:
            search_results = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        console.print(f"[red]Error loading search results file: {e}[/red]")
        return [], None

    # Get processed files log
    processed_files_log = os.path.join(base_dir, "tmp", f"{site_upload}_processed_paths.log")
    processed_paths = set()

    if os.path.exists(processed_files_log):
        try:
            with open(processed_files_log, 'r', encoding='utf-8') as f:
                processed_paths = set(json.load(f))
        except (json.JSONDecodeError, IOError) as e:
            console.print(f"[yellow]Warning: Could not load processed files log: {e}[/yellow]")

    # Extract paths and IMDb IDs, filtering out processed paths
    queue = []
    for item in search_results:
        path = item.get('path')
        try:
            imdb_id = item.get('imdb_id')
        except KeyError:
            imdb_id = 0

        if path and imdb_id is not None and path not in processed_paths:
            # Set tracker and imdb_id in meta for this queue item
            queue_item = {
                'path': path,
                'imdb_id': imdb_id,
                'tracker': site_upload
            }
            queue.append(queue_item)

    console.print(f"[cyan]Found {len(queue)} unprocessed items for {site_upload} upload[/cyan]")

    if queue:
        # Display the queue
        paths_only = [item['path'] for item in queue]
        md_text = "\n - ".join(paths_only)
        console.print("\n[bold green]Queuing these files for site upload:[/bold green]", end='')
        console.print(Markdown(f"- {md_text.rstrip()}\n\n", style=Style(color='cyan')))
        console.print(f"[yellow]Tracker: {site_upload}[/yellow]")
        console.print("\n\n")

    return queue, processed_files_log


async def process_site_upload_item(queue_item, meta):
    # Set the tracker argument (-tk XXX)
    meta['trackers'] = [queue_item['tracker']]

    # Set the IMDb ID
    try:
        imdb = queue_item['imdb_id']
    except KeyError:
        imdb = 0
    meta['imdb_id'] = imdb

    # Return the path for processing
    return queue_item['path']


async def save_processed_path(processed_files_log, path):
    processed_paths = set()

    # Load existing processed paths
    if os.path.exists(processed_files_log):
        try:
            with open(processed_files_log, 'r', encoding='utf-8') as f:
                processed_paths = set(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass

    # Add the new path
    processed_paths.add(path)

    # Save back to file
    try:
        os.makedirs(os.path.dirname(processed_files_log), exist_ok=True)
        with open(processed_files_log, 'w', encoding='utf-8') as f:
            json.dump(list(processed_paths), f, indent=4)
    except IOError as e:
        console.print(f"[red]Error saving processed path: {e}[/red]")


async def get_log_file(base_dir, queue_name):
    """
    Returns the path to the log file for the given base directory and queue name.
    """
    safe_queue_name = queue_name.replace(" ", "_")
    return os.path.join(base_dir, "tmp", f"{safe_queue_name}_processed_files.log")


async def load_processed_files(log_file):
    """
    Loads the list of processed files from the log file.
    """
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()


async def gather_files_recursive(path, allowed_extensions=None):
    """
    Gather files and first-level subfolders.
    Each subfolder is treated as a single unit, without exploring deeper.
    Skip folders that don't contain allowed extensions or disc structures (VIDEO_TS/BDMV).
    """
    queue = []

    # Normalize the path to handle Unicode characters properly
    try:
        if isinstance(path, bytes):
            path = path.decode('utf-8', errors='replace')

        # Normalize Unicode characters
        import unicodedata
        path = unicodedata.normalize('NFC', path)

        # Ensure proper path format
        path = os.path.normpath(path)

    except Exception as e:
        console.print(f"[yellow]Warning: Path normalization failed for {path}: {e}[/yellow]")

    if os.path.isdir(path):
        try:
            for entry in os.scandir(path):
                try:
                    # Get the full path and normalize it
                    entry_path = os.path.normpath(entry.path)

                    if entry.is_dir():
                        # Check if this directory should be included
                        if await should_include_directory(entry_path, allowed_extensions):
                            queue.append(entry_path)
                    elif entry.is_file() and (allowed_extensions is None or entry.name.lower().endswith(tuple(allowed_extensions))):
                        queue.append(entry_path)

                except (OSError, UnicodeDecodeError, UnicodeError) as e:
                    console.print(f"[yellow]Warning: Skipping entry due to encoding issue: {e}[/yellow]")
                    # Try to get the path in a different way
                    try:
                        alt_path = os.path.join(path, entry.name)
                        if os.path.exists(alt_path):
                            if os.path.isdir(alt_path) and await should_include_directory(alt_path, allowed_extensions):
                                queue.append(alt_path)
                            elif os.path.isfile(alt_path) and (allowed_extensions is None or alt_path.lower().endswith(tuple(allowed_extensions))):
                                queue.append(alt_path)
                    except Exception:
                        continue

        except (OSError, PermissionError) as e:
            console.print(f"[red]Error scanning directory {path}: {e}[/red]")
            return []

    elif os.path.isfile(path):
        if allowed_extensions is None or path.lower().endswith(tuple(allowed_extensions)):
            queue.append(path)
    else:
        console.print(f"[red]Invalid path: {path}[/red]")

    return queue


async def should_include_directory(dir_path, allowed_extensions=None):
    """
    Check if a directory should be included in the queue.
    Returns True if the directory contains:
    - Files with allowed extensions, OR
    - A subfolder named 'VIDEO_TS' or 'BDMV' (disc structures)
    """
    try:
        # Normalize the path
        dir_path = os.path.normpath(dir_path)

        # Check for disc structures first (VIDEO_TS or BDMV subfolders)
        for entry in os.scandir(dir_path):
            if entry.is_dir() and entry.name.upper() in ('VIDEO_TS', 'BDMV'):
                return True

        # Check for files with allowed extensions
        if allowed_extensions:
            for entry in os.scandir(dir_path):
                if entry.is_file() and entry.name.lower().endswith(tuple(allowed_extensions)):
                    return True
        else:
            # If no allowed_extensions specified, include any directory with files
            for entry in os.scandir(dir_path):
                if entry.is_file():
                    return True

        return False

    except (OSError, PermissionError, UnicodeError) as e:
        console.print(f"[yellow]Warning: Could not scan directory {dir_path}: {e}[/yellow]")
        return False


async def _resolve_split_path(path):
    queue = []
    split_path = path.split()
    p1 = split_path[0]

    for i, _ in enumerate(split_path):
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

    return queue


async def resolve_queue_with_glob_or_split(path, paths, allowed_extensions=None):
    """
    Handle glob patterns and split path resolution.
    Treat subfolders as single units and filter files by allowed_extensions.
    """
    queue = []
    if os.path.exists(os.path.dirname(path)) and len(paths) <= 1:
        escaped_path = path.replace('[', '[[]')
        queue = [
            file for file in glob.glob(escaped_path)
            if os.path.isdir(file) or (os.path.isfile(file) and (allowed_extensions is None or file.lower().endswith(tuple(allowed_extensions))))
        ]
        if queue:
            await display_queue(queue)
    elif os.path.exists(os.path.dirname(path)) and len(paths) > 1:
        queue = [
            file for file in paths
            if os.path.isdir(file) or (os.path.isfile(file) and (allowed_extensions is None or file.lower().endswith(tuple(allowed_extensions))))
        ]
        await display_queue(queue)
    elif not os.path.exists(os.path.dirname(path)):
        queue = [
            file for file in await _resolve_split_path(path)
            if os.path.isdir(file) or (os.path.isfile(file) and (allowed_extensions is None or file.lower().endswith(tuple(allowed_extensions))))
        ]
        await display_queue(queue)
    return queue


async def extract_safe_file_locations(log_file):
    """
    Parse the log file to extract file locations under the 'safe' header.

    :param log_file: Path to the log file to parse.
    :return: List of file paths from the 'safe' section.
    """
    safe_section = False
    safe_file_locations = []

    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # Detect the start and end of 'safe' sections
            if line.lower() == "safe":
                safe_section = True
                continue
            elif line.lower() in {"danger", "risky"}:
                safe_section = False

            # Extract 'File Location' if in a 'safe' section
            if safe_section and line.startswith("File Location:"):
                match = re.search(r"File Location:\s*(.+)", line)
                if match:
                    safe_file_locations.append(match.group(1).strip())

    return safe_file_locations


async def display_queue(queue, base_dir, queue_name, save_to_log=True):
    """Displays the queued files in markdown format and optionally saves them to a log file in the tmp directory."""
    md_text = "\n - ".join(queue)
    console.print("\n[bold green]Queuing these files:[/bold green]", end='')
    console.print(Markdown(f"- {md_text.rstrip()}\n\n", style=Style(color='cyan')))
    console.print("\n\n")

    if save_to_log:
        tmp_dir = os.path.join(base_dir, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        log_file = os.path.join(tmp_dir, f"{queue_name}_queue.log")

        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=4)
            console.print(f"[bold green]Queue successfully saved to log file: {log_file}")
        except Exception as e:
            console.print(f"[bold red]Failed to save queue to log file: {e}")


async def handle_queue(path, meta, paths, base_dir):
    allowed_extensions = ['.mkv', '.mp4', '.ts']
    queue = []

    if meta.get('site_upload'):
        console.print(f"[bold yellow]Processing site upload queue for tracker: {meta['site_upload']}[/bold yellow]")
        site_queue, processed_log = await process_site_upload_queue(meta, base_dir)

        if site_queue:
            meta['queue'] = f"{meta['site_upload']}_upload"
            meta['site_upload_queue'] = True

            # Return the structured queue and log file
            return site_queue, processed_log
        else:
            console.print(f"[yellow]No unprocessed items found for {meta['site_upload']} upload[/yellow]")
            return [], None

    log_file = os.path.join(base_dir, "tmp", f"{meta.get('queue', 'default')}_queue.log")

    if path.endswith('.txt') and meta.get('unit3d'):
        console.print(f"[bold yellow]Detected a text file for queue input: {path}[/bold yellow]")
        if os.path.exists(path):
            safe_file_locations = await extract_safe_file_locations(path)
            if safe_file_locations:
                console.print(f"[cyan]Extracted {len(safe_file_locations)} safe file locations from the text file.[/cyan]")
                queue = safe_file_locations
                meta['queue'] = "unit3d"

                # Save the queue to the log file
                try:
                    with open(log_file, 'w', encoding='utf-8') as f:
                        json.dump(queue, f, indent=4)
                    console.print(f"[bold green]Queue log file saved successfully: {log_file}[/bold green]")
                except IOError as e:
                    console.print(f"[bold red]Failed to save the queue log file: {e}[/bold red]")
                    exit(1)
            else:
                console.print("[bold red]No safe file locations found in the text file. Exiting.[/bold red]")
                exit(1)
        else:
            console.print(f"[bold red]Text file not found: {path}. Exiting.[/bold red]")
            exit(1)

    elif path.endswith('.log') and meta['debug']:
        console.print(f"[bold yellow]Processing debugging queue:[/bold yellow] [bold green{path}[/bold green]")
        if os.path.exists(path):
            log_file = path
            with open(path, 'r') as f:
                queue = json.load(f)
                meta['queue'] = "debugging"

        else:
            console.print(f"[bold red]Log file not found: {path}. Exiting.[/bold red]")
            exit(1)

    elif meta.get('queue'):
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                existing_queue = json.load(f)

            if os.path.exists(path):
                current_files = await gather_files_recursive(path, allowed_extensions=allowed_extensions)
            else:
                current_files = await resolve_queue_with_glob_or_split(path, paths, allowed_extensions=allowed_extensions)

            existing_set = set(existing_queue)
            current_set = set(current_files)
            new_files = current_set - existing_set
            removed_files = existing_set - current_set
            log_file_proccess = await get_log_file(base_dir, meta['queue'])
            processed_files = await load_processed_files(log_file_proccess)
            queued = [file for file in existing_queue if file not in processed_files]

            console.print(f"[bold yellow]Found an existing queue log file:[/bold yellow] [green]{log_file}[/green]")
            console.print(f"[cyan]The queue log contains {len(existing_queue)} total items and {len(queued)} unprocessed items.[/cyan]")

            if new_files or removed_files:
                console.print("[bold yellow]Queue changes detected:[/bold yellow]")
                if new_files:
                    console.print(f"[green]New files found ({len(new_files)}):[/green]")
                    for file in sorted(new_files):
                        console.print(f"  + {file}")
                if removed_files:
                    console.print(f"[red]Removed files ({len(removed_files)}):[/red]")
                    for file in sorted(removed_files):
                        console.print(f"  - {file}")

                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    console.print("[yellow]Do you want to update the queue log, edit, discard, or keep the existing queue?[/yellow]")
                    edit_choice = input("Enter 'u' to update, 'a' to add specific new files, 'e' to edit, 'd' to discard, or press Enter to keep it as is: ").strip().lower()

                    if edit_choice == 'u':
                        queue = current_files
                        console.print(f"[bold green]Queue updated with current files ({len(queue)} items).")
                        with open(log_file, 'w', encoding='utf-8') as f:
                            json.dump(queue, f, indent=4)
                        console.print(f"[bold green]Queue log file updated: {log_file}[/bold green]")
                    elif edit_choice == 'a':
                        console.print("[yellow]Select which new files to add (comma-separated numbers):[/yellow]")
                        for idx, file in enumerate(sorted(new_files), 1):
                            console.print(f"  {idx}. {file}")
                        selected = input("Enter numbers (e.g., 1,3,5): ").strip()
                        try:
                            indices = [int(x) for x in selected.split(',') if x.strip().isdigit()]
                            selected_files = [file for i, file in enumerate(sorted(new_files), 1) if i in indices]
                            queue = list(existing_queue) + selected_files
                            console.print(f"[bold green]Queue updated with selected new files ({len(queue)} items).")
                            with open(log_file, 'w', encoding='utf-8') as f:
                                json.dump(queue, f, indent=4)
                            console.print(f"[bold green]Queue log file updated: {log_file}[/bold green]")
                        except Exception as e:
                            console.print(f"[bold red]Failed to update queue with selected files: {e}. Using the existing queue.")
                            queue = existing_queue
                    elif edit_choice == 'e':
                        edited_content = click.edit(json.dumps(current_files, indent=4))
                        if edited_content:
                            try:
                                queue = json.loads(edited_content.strip())
                                console.print("[bold green]Successfully updated the queue from the editor.")
                                with open(log_file, 'w', encoding='utf-8') as f:
                                    json.dump(queue, f, indent=4)
                            except json.JSONDecodeError as e:
                                console.print(f"[bold red]Failed to parse the edited content: {e}. Using the current files.")
                                queue = current_files
                        else:
                            console.print("[bold red]No changes were made. Using the current files.")
                            queue = current_files
                    elif edit_choice == 'd':
                        console.print("[bold yellow]Discarding the existing queue log. Creating a new queue.")
                        queue = current_files
                        with open(log_file, 'w', encoding='utf-8') as f:
                            json.dump(queue, f, indent=4)
                        console.print(f"[bold green]New queue log file created: {log_file}[/bold green]")
                    else:
                        console.print("[bold green]Keeping the existing queue as is.")
                        queue = existing_queue
                else:
                    # In unattended mode, just use the existing queue
                    queue = existing_queue
                    console.print("[bold yellow]New or removed files detected, but unattended mode is active. Using existing queue.")
            else:
                # No changes detected
                console.print("[green]No changes detected in the queue.[/green]")
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    console.print("[yellow]Do you want to edit, discard, or keep the existing queue?[/yellow]")
                    edit_choice = input("Enter 'e' to edit, 'd' to discard, or press Enter to keep it as is: ").strip().lower()

                    if edit_choice == 'e':
                        edited_content = click.edit(json.dumps(existing_queue, indent=4))
                        if edited_content:
                            try:
                                queue = json.loads(edited_content.strip())
                                console.print("[bold green]Successfully updated the queue from the editor.")
                                with open(log_file, 'w', encoding='utf-8') as f:
                                    json.dump(queue, f, indent=4)
                            except json.JSONDecodeError as e:
                                console.print(f"[bold red]Failed to parse the edited content: {e}. Using the original queue.")
                                queue = existing_queue
                        else:
                            console.print("[bold red]No changes were made. Using the original queue.")
                            queue = existing_queue
                    elif edit_choice == 'd':
                        console.print("[bold yellow]Discarding the existing queue log. Creating a new queue.")
                        queue = current_files
                        with open(log_file, 'w', encoding='utf-8') as f:
                            json.dump(queue, f, indent=4)
                        console.print(f"[bold green]New queue log file created: {log_file}[/bold green]")
                    else:
                        console.print("[bold green]Keeping the existing queue as is.")
                        queue = existing_queue
                else:
                    console.print("[bold green]Keeping the existing queue as is.")
                    queue = existing_queue
        else:
            if os.path.exists(path):
                queue = await gather_files_recursive(path, allowed_extensions=allowed_extensions)
            else:
                queue = await resolve_queue_with_glob_or_split(path, paths, allowed_extensions=allowed_extensions)

            console.print(f"[cyan]A new queue log file will be created:[/cyan] [green]{log_file}[/green]")
            console.print(f"[cyan]The new queue will contain {len(queue)} items.[/cyan]")
            console.print("[cyan]Do you want to edit the initial queue before saving?[/cyan]")
            edit_choice = input("Enter 'e' to edit, or press Enter to save as is: ").strip().lower()

            if edit_choice == 'e':
                edited_content = click.edit(json.dumps(queue, indent=4))
                if edited_content:
                    try:
                        queue = json.loads(edited_content.strip())
                        console.print("[bold green]Successfully updated the queue from the editor.")
                    except json.JSONDecodeError as e:
                        console.print(f"[bold red]Failed to parse the edited content: {e}. Using the original queue.")
                else:
                    console.print("[bold red]No changes were made. Using the original queue.")

            # Save the queue to the log file
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=4)
            console.print(f"[bold green]Queue log file created: {log_file}[/bold green]")

    elif os.path.exists(path):
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

    if not queue:
        console.print(f"[red]No valid files or directories found for path: {path}")
        exit(1)

    if meta.get('queue'):
        queue_name = meta['queue']
        log_file = await get_log_file(base_dir, meta['queue'])
        processed_files = await load_processed_files(log_file)
        queue = [file for file in queue if file not in processed_files]
        if not queue:
            console.print(f"[bold yellow]All files in the {meta['queue']} queue have already been processed.")
            exit(0)
        if meta['debug']:
            await display_queue(queue, base_dir, queue_name, save_to_log=False)

    return queue, log_file
