# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import contextlib
import glob
import json
import os
import re
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any, Optional, Union, cast

import cli_ui
import click
from rich.markdown import Markdown
from rich.style import Style
from typing_extensions import TypeAlias

from src.console import console

QueueItem: TypeAlias = dict[str, Any]
QueueList: TypeAlias = Union[list[str], list[QueueItem]]


async def _read_json_file(path: str) -> Any:
    content = await asyncio.to_thread(Path(path).read_text, encoding="utf-8")
    return json.loads(content)


async def _write_json_file(path: str, data: Any, indent: int = 4) -> None:
    content = json.dumps(data, indent=indent)
    await asyncio.to_thread(Path(path).write_text, content, encoding="utf-8")


async def _read_text_lines(path: str) -> list[str]:
    content = await asyncio.to_thread(Path(path).read_text, encoding="utf-8")
    return content.splitlines()


class QueueManager:
    @staticmethod
    async def process_site_upload_queue(meta: Mapping[str, Any], base_dir: str) -> tuple[list[QueueItem], Optional[str]]:
        site_upload = meta.get('site_upload')
        if not site_upload:
            return [], None

        # Get the search results file path
        search_results_file = os.path.join(base_dir, "tmp", f"{site_upload}_search_results.json")

        if not os.path.exists(search_results_file):
            console.print(f"[red]Search results file not found: {search_results_file}[/red]")
            return [], None

        try:
            search_results = cast(list[QueueItem], await _read_json_file(search_results_file))
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"[red]Error loading search results file: {e}[/red]")
            return [], None

        # Get processed files log
        processed_files_log = os.path.join(base_dir, "tmp", f"{site_upload}_processed_paths.log")
        processed_paths: set[str] = set()

        if os.path.exists(processed_files_log):
            try:
                processed_paths = set(cast(list[str], await _read_json_file(processed_files_log)))
            except (json.JSONDecodeError, OSError) as e:
                console.print(f"[yellow]Warning: Could not load processed files log: {e}[/yellow]")

        # Extract paths and IMDb IDs, filtering out processed paths
        queue: list[QueueItem] = []
        for item in search_results:
            path = item.get('path')
            try:
                imdb_id = item.get('imdb_id')
            except KeyError:
                imdb_id = 0

            if path and imdb_id is not None and path not in processed_paths:
                # Set tracker and imdb_id in meta for this queue item
                queue_item: QueueItem = {
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

    @staticmethod
    async def process_site_upload_item(queue_item: Mapping[str, Any], meta: MutableMapping[str, Any]) -> str:
        # Set the tracker argument (-tk XXX)
        tracker = cast(str, queue_item['tracker'])
        meta['trackers'] = [tracker]

        # Set the IMDb ID
        imdb = queue_item.get('imdb_id', 0)
        meta['imdb_id'] = imdb

        # Return the path for processing
        return cast(str, queue_item['path'])

    @staticmethod
    async def save_processed_path(processed_files_log: str, path: str) -> None:
        processed_paths: set[str] = set()

        # Load existing processed paths
        if os.path.exists(processed_files_log):
            with contextlib.suppress(json.JSONDecodeError, OSError):
                processed_paths = set(cast(list[str], await _read_json_file(processed_files_log)))

        # Add the new path
        processed_paths.add(path)

        # Save back to file
        try:
            os.makedirs(os.path.dirname(processed_files_log), exist_ok=True)
            await _write_json_file(processed_files_log, list(processed_paths), indent=4)
        except OSError as e:
            console.print(f"[red]Error saving processed path: {e}[/red]")

    @staticmethod
    async def get_log_file(base_dir: str, queue_name: str) -> str:
        """
        Returns the path to the log file for the given base directory and queue name.
        """
        safe_queue_name = queue_name.replace(" ", "_")
        return os.path.join(base_dir, "tmp", f"{safe_queue_name}_processed_files.log")

    @staticmethod
    async def load_processed_files(log_file: str) -> set[str]:
        """
        Loads the list of processed files from the log file.
        """
        if os.path.exists(log_file):
            return set(cast(list[str], await _read_json_file(log_file)))
        return set()

    @staticmethod
    async def gather_files_recursive(
        path: Union[str, bytes],
        allowed_extensions: Optional[Sequence[str]] = None,
    ) -> list[str]:
        """
        Gather files and first-level subfolders.
        Each subfolder is treated as a single unit, without exploring deeper.
        Skip folders that don't contain allowed extensions or disc structures (VIDEO_TS/BDMV).
        """
        queue: list[str] = []
        allowed_extensions_tuple = tuple(allowed_extensions) if allowed_extensions else None

        # Normalize the path to handle Unicode characters properly
        path_str = path.decode('utf-8', errors='replace') if isinstance(path, bytes) else path
        try:
            # Normalize Unicode characters
            import unicodedata
            path_str = unicodedata.normalize('NFC', path_str)

            # Ensure proper path format
            normalized_path = os.path.normpath(path_str)
        except Exception as e:
            console.print(f"[yellow]Warning: Path normalization failed for {path_str}: {e}[/yellow]")
            normalized_path = os.path.normpath(path_str)

        if os.path.isdir(normalized_path):
            try:
                for entry in os.scandir(normalized_path):
                    queue.extend(
                        await QueueManager._process_scandir_entry(entry, normalized_path, allowed_extensions_tuple, allowed_extensions)
                    )

            except (OSError, PermissionError) as e:
                console.print(f"[red]Error scanning directory {normalized_path}: {e}[/red]")
                return []

        elif os.path.isfile(normalized_path):
            if allowed_extensions_tuple is None or normalized_path.lower().endswith(allowed_extensions_tuple):
                queue.append(normalized_path)
        else:
            console.print(f"[red]Invalid path: {normalized_path}[/red]")

        return queue

    @staticmethod
    async def _process_scandir_entry(
        entry: os.DirEntry[str],
        normalized_path: str,
        allowed_extensions_tuple: Optional[tuple[str, ...]],
        allowed_extensions: Optional[Sequence[str]],
    ) -> list[str]:
        entry_paths: list[str] = []
        try:
            # Get the full path and normalize it
            entry_path = os.path.normpath(entry.path)

            if entry.is_dir():
                # Check if this directory should be included
                if await QueueManager.should_include_directory(entry_path, allowed_extensions):
                    entry_paths.append(entry_path)
            elif entry.is_file() and (allowed_extensions_tuple is None or entry.name.lower().endswith(allowed_extensions_tuple)):
                entry_paths.append(entry_path)

        except (OSError, UnicodeDecodeError, UnicodeError) as e:
            console.print(f"[yellow]Warning: Skipping entry due to encoding issue: {e}[/yellow]")
            # Try to get the path in a different way
            try:
                alt_path = os.path.join(normalized_path, entry.name)
                if os.path.exists(alt_path) and (
                    (os.path.isdir(alt_path) and await QueueManager.should_include_directory(alt_path, allowed_extensions))
                    or (
                        os.path.isfile(alt_path)
                        and (allowed_extensions_tuple is None or alt_path.lower().endswith(allowed_extensions_tuple))
                    )
                ):
                    entry_paths.append(alt_path)
            except Exception:
                pass  # nosec B112: ignore further errors here

        return entry_paths

    @staticmethod
    async def should_include_directory(dir_path: str, allowed_extensions: Optional[Sequence[str]] = None) -> bool:
        """
        Check if a directory should be included in the queue.
        Returns True if the directory contains:
        - Files with allowed extensions, OR
        - A subfolder named 'VIDEO_TS' or 'BDMV' (disc structures)
        """
        allowed_extensions_tuple = tuple(allowed_extensions) if allowed_extensions else None
        try:
            # Normalize the path
            dir_path = os.path.normpath(dir_path)

            # Check for disc structures first (VIDEO_TS or BDMV subfolders)
            for entry in os.scandir(dir_path):
                if entry.is_dir() and entry.name.upper() in ('VIDEO_TS', 'BDMV'):
                    return True

            # Check for files with allowed extensions
            if allowed_extensions_tuple:
                for entry in os.scandir(dir_path):
                    if entry.is_file() and entry.name.lower().endswith(allowed_extensions_tuple):
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

    @staticmethod
    async def _resolve_split_path(path: str) -> list[str]:
        queue: list[str] = []
        split_path = path.split()
        if not split_path:
            return queue

        p1 = split_path[0]
        for next_part in split_path[1:]:
            if os.path.exists(p1) and not os.path.exists(f"{p1} {next_part}"):
                queue.append(p1)
                p1 = next_part
            else:
                p1 = f"{p1} {next_part}"

        if os.path.exists(p1):
            queue.append(p1)
        else:
            console.print(f"[red]Path: [bold red]{p1}[/bold red] does not exist")

        return queue

    @staticmethod
    async def resolve_queue_with_glob_or_split(
        path: str,
        paths: Sequence[str],
        allowed_extensions: Optional[Sequence[str]] = None,
    ) -> list[str]:
        """
        Handle glob patterns and split path resolution.
        Treat subfolders as single units and filter files by allowed_extensions.
        """
        queue: list[str] = []
        allowed_extensions_tuple = tuple(allowed_extensions) if allowed_extensions else None
        if os.path.exists(os.path.dirname(path)) and len(paths) <= 1:
            escaped_path = path.replace('[', '[[]')
            queue = [
                file for file in glob.glob(escaped_path)
                if os.path.isdir(file)
                or (os.path.isfile(file) and (allowed_extensions_tuple is None or file.lower().endswith(allowed_extensions_tuple)))
            ]
            if queue:
                await QueueManager.display_queue(queue, save_to_log=False)
        elif os.path.exists(os.path.dirname(path)) and len(paths) > 1:
            queue = [
                file for file in paths
                if os.path.isdir(file)
                or (os.path.isfile(file) and (allowed_extensions_tuple is None or file.lower().endswith(allowed_extensions_tuple)))
            ]
            await QueueManager.display_queue(queue, save_to_log=False)
        elif not os.path.exists(os.path.dirname(path)):
            queue = [
                file for file in await QueueManager._resolve_split_path(path)
                if os.path.isdir(file)
                or (os.path.isfile(file) and (allowed_extensions_tuple is None or file.lower().endswith(allowed_extensions_tuple)))
            ]
            await QueueManager.display_queue(queue, save_to_log=False)
        return queue

    @staticmethod
    async def extract_safe_file_locations(log_file: str) -> list[str]:
        """
        Parse the log file to extract file locations under the 'safe' header.

        :param log_file: Path to the log file to parse.
        :return: List of file paths from the 'safe' section.
        """
        safe_section = False
        safe_file_locations: list[str] = []

        for line in await _read_text_lines(log_file):
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

    @staticmethod
    async def display_queue(
        queue: Sequence[str],
        base_dir: Optional[str] = None,
        queue_name: Optional[str] = None,
        save_to_log: bool = True,
    ) -> None:
        """Displays the queued files in markdown format and optionally saves them to a log file in the tmp directory."""
        md_text = "\n - ".join(queue)
        console.print("\n[bold green]Queuing these files:[/bold green]", end='')
        console.print(Markdown(f"- {md_text.rstrip()}\n\n", style=Style(color='cyan')))
        console.print("\n\n")

        if save_to_log and base_dir and queue_name:
            tmp_dir = os.path.join(base_dir, "tmp")
            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir, mode=0o700, exist_ok=True)
                # Enforce 0700 regardless of process umask (POSIX only).
                if os.name != 'nt':
                    os.chmod(tmp_dir, 0o700)
            else:
                if os.name != 'nt':
                    os.chmod(tmp_dir, 0o700)
            log_file = os.path.join(tmp_dir, f"{queue_name}_queue.log")

            try:
                await _write_json_file(log_file, list(queue), indent=4)
                console.print(f"[bold green]Queue successfully saved to log file: {log_file}")
            except Exception as e:
                console.print(f"[bold red]Failed to save queue to log file: {e}")

    @staticmethod
    async def handle_queue(
        path: str,
        meta: MutableMapping[str, Any],
        paths: Sequence[str],
        base_dir: str,
    ) -> tuple[QueueList, Optional[str]]:
        allowed_extensions = ['.mkv', '.mp4', '.ts']
        queue: list[str] = []

        if meta.get('site_upload'):
            console.print(f"[bold yellow]Processing site upload queue for tracker: {meta['site_upload']}[/bold yellow]")
            site_queue, processed_log = await QueueManager.process_site_upload_queue(meta, base_dir)

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
                safe_file_locations = await QueueManager.extract_safe_file_locations(path)
                if safe_file_locations:
                    console.print(f"[cyan]Extracted {len(safe_file_locations)} safe file locations from the text file.[/cyan]")
                    queue = safe_file_locations
                    meta['queue'] = "unit3d"

                    # Save the queue to the log file
                    try:
                        await _write_json_file(log_file, queue, indent=4)
                        console.print(f"[bold green]Queue log file saved successfully: {log_file}[/bold green]")
                    except OSError as e:
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
                queue = cast(list[str], await _read_json_file(path))
                meta['queue'] = "debugging"

            else:
                console.print(f"[bold red]Log file not found: {path}. Exiting.[/bold red]")
                exit(1)

        elif meta.get('queue'):
            if os.path.exists(log_file):
                existing_queue = cast(list[str], await _read_json_file(log_file))

                if os.path.exists(path):
                    current_files = await QueueManager.gather_files_recursive(path, allowed_extensions=allowed_extensions)
                else:
                    current_files = await QueueManager.resolve_queue_with_glob_or_split(path, paths, allowed_extensions=allowed_extensions)

                existing_set = set(existing_queue)
                current_set = set(current_files)
                new_files = current_set - existing_set
                removed_files = existing_set - current_set
                log_file_proccess = await QueueManager.get_log_file(base_dir, meta['queue'])
                processed_files = await QueueManager.load_processed_files(log_file_proccess)
                queued = [file for file in existing_queue if file not in processed_files]

                console.print(f"[bold yellow]Found an existing queue log file:[/bold yellow] [green]{log_file}[/green]")
                console.print(f"[cyan]The queue log contains {len(existing_queue)} total items and {len(queued)} unprocessed items.[/cyan]")

                if new_files or removed_files:
                    console.print("[bold yellow]Queue changes detected:[/bold yellow]")
                    if new_files and meta.get('debug'):
                        console.print(f"[green]New files found ({len(new_files)}):[/green]")
                        for file in sorted(new_files):
                            console.print(f"  + {file}")
                    if removed_files and meta.get('debug'):
                        console.print(f"[red]Removed files ({len(removed_files)}):[/red]")
                        for file in sorted(removed_files):
                            console.print(f"  - {file}")

                    if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                        console.print("[yellow]Do you want to update the queue log, edit, discard, or keep the existing queue?[/yellow]")
                        edit_choice_raw = cli_ui.ask_string("Enter 'u' to update, 'a' to add specific new files, 'e' to edit, 'd' to discard, or press Enter to keep it as is: ")
                        edit_choice = (edit_choice_raw or "").strip().lower()

                        if edit_choice == 'u':
                            queue = current_files
                            console.print(f"[bold green]Queue updated with current files ({len(queue)} items).")
                            await _write_json_file(log_file, queue, indent=4)
                            console.print(f"[bold green]Queue log file updated: {log_file}[/bold green]")
                        elif edit_choice == 'a':
                            console.print("[yellow]Select which new files to add (comma-separated numbers):[/yellow]")
                            for idx, file in enumerate(sorted(new_files), 1):
                                console.print(f"  {idx}. {file}")
                            selected_raw = cli_ui.ask_string("Enter numbers (e.g., 1,3,5): ")
                            selected = (selected_raw or "").strip()
                            try:
                                indices = [int(x) for x in selected.split(',') if x.strip().isdigit()]
                                selected_files = [file for i, file in enumerate(sorted(new_files), 1) if i in indices]
                                queue = list(existing_queue) + selected_files
                                console.print(f"[bold green]Queue updated with selected new files ({len(queue)} items).")
                                await _write_json_file(log_file, queue, indent=4)
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
                                    await _write_json_file(log_file, queue, indent=4)
                                except json.JSONDecodeError as e:
                                    console.print(f"[bold red]Failed to parse the edited content: {e}. Using the current files.")
                                    queue = current_files
                            else:
                                console.print("[bold red]No changes were made. Using the current files.")
                                queue = current_files
                        elif edit_choice == 'd':
                            console.print("[bold yellow]Discarding the existing queue log. Creating a new queue.")
                            queue = current_files
                            await _write_json_file(log_file, queue, indent=4)
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
                        edit_choice_raw = cli_ui.ask_string("Enter 'e' to edit, 'd' to discard, or press Enter to keep it as is: ")
                        edit_choice = (edit_choice_raw or "").strip().lower()

                        if edit_choice == 'e':
                            edited_content = click.edit(json.dumps(existing_queue, indent=4))
                            if edited_content:
                                try:
                                    queue = json.loads(edited_content.strip())
                                    console.print("[bold green]Successfully updated the queue from the editor.")
                                    await _write_json_file(log_file, queue, indent=4)
                                except json.JSONDecodeError as e:
                                    console.print(f"[bold red]Failed to parse the edited content: {e}. Using the original queue.")
                                    queue = existing_queue
                            else:
                                console.print("[bold red]No changes were made. Using the original queue.")
                                queue = existing_queue
                        elif edit_choice == 'd':
                            console.print("[bold yellow]Discarding the existing queue log. Creating a new queue.")
                            queue = current_files
                            await _write_json_file(log_file, queue, indent=4)
                            console.print(f"[bold green]New queue log file created: {log_file}[/bold green]")
                        else:
                            console.print("[bold green]Keeping the existing queue as is.")
                            queue = existing_queue
                    else:
                        console.print("[bold green]Keeping the existing queue as is.")
                        queue = existing_queue
            else:
                if os.path.exists(path):
                    queue = await QueueManager.gather_files_recursive(path, allowed_extensions=allowed_extensions)
                else:
                    queue = await QueueManager.resolve_queue_with_glob_or_split(path, paths, allowed_extensions=allowed_extensions)

                console.print(f"[cyan]A new queue log file will be created:[/cyan] [green]{log_file}[/green]")
                console.print(f"[cyan]The new queue will contain {len(queue)} items.[/cyan]")
                console.print("[cyan]Do you want to edit the initial queue before saving?[/cyan]")
                edit_choice_raw = cli_ui.ask_string("Enter 'e' to edit, or press Enter to save as is: ")
                edit_choice = (edit_choice_raw or "").strip().lower()

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
                await _write_json_file(log_file, queue, indent=4)
                console.print(f"[bold green]Queue log file created: {log_file}[/bold green]")

        elif os.path.exists(path):
            queue = [path]

        else:
            # Search glob if dirname exists
            if os.path.exists(os.path.dirname(path)) and len(paths) <= 1:
                escaped_path = path.replace('[', '[[]')
                globs = glob.glob(escaped_path)
                queue = globs
                if queue:
                    md_text = "\n - ".join(queue)
                    console.print("\n[bold green]Queuing these files:[/bold green]", end='')
                    console.print(Markdown(f"- {md_text.rstrip()}\n\n", style=Style(color='cyan')))
                    console.print("\n\n")
                else:
                    console.print(f"[red]Path: [bold red]{path}[/bold red] does not exist")

            elif os.path.exists(os.path.dirname(path)) and len(paths) != 1:
                queue = list(paths)
                md_text = "\n - ".join(queue)
                console.print("\n[bold green]Queuing these files:[/bold green]", end='')
                console.print(Markdown(f"- {md_text.rstrip()}\n\n", style=Style(color='cyan')))
                console.print("\n\n")
            elif not os.path.exists(os.path.dirname(path)):
                queue = await QueueManager._resolve_split_path(path)
                if queue:
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
            log_file = await QueueManager.get_log_file(base_dir, meta['queue'])
            processed_files = await QueueManager.load_processed_files(log_file)
            queue = [file for file in queue if file not in processed_files]
            if not queue:
                console.print(f"[bold yellow]All files in the {meta['queue']} queue have already been processed.")
                exit(0)
            if meta['debug']:
                await QueueManager.display_queue(queue, base_dir, queue_name, save_to_log=False)

        return queue, log_file


async def process_site_upload_queue(meta: Mapping[str, Any], base_dir: str) -> tuple[list[QueueItem], Optional[str]]:
    return await QueueManager.process_site_upload_queue(meta, base_dir)


async def process_site_upload_item(queue_item: Mapping[str, Any], meta: MutableMapping[str, Any]) -> str:
    return await QueueManager.process_site_upload_item(queue_item, meta)


async def save_processed_path(processed_files_log: str, path: str) -> None:
    await QueueManager.save_processed_path(processed_files_log, path)


async def get_log_file(base_dir: str, queue_name: str) -> str:
    return await QueueManager.get_log_file(base_dir, queue_name)


async def load_processed_files(log_file: str) -> set[str]:
    return await QueueManager.load_processed_files(log_file)


async def gather_files_recursive(
    path: Union[str, bytes],
    allowed_extensions: Optional[Sequence[str]] = None,
) -> list[str]:
    return await QueueManager.gather_files_recursive(path, allowed_extensions=allowed_extensions)


async def should_include_directory(
    dir_path: str,
    allowed_extensions: Optional[Sequence[str]] = None,
) -> bool:
    return await QueueManager.should_include_directory(dir_path, allowed_extensions=allowed_extensions)


async def resolve_queue_with_glob_or_split(
    path: str,
    paths: Sequence[str],
    allowed_extensions: Optional[Sequence[str]] = None,
) -> list[str]:
    return await QueueManager.resolve_queue_with_glob_or_split(path, paths, allowed_extensions=allowed_extensions)


async def extract_safe_file_locations(log_file: str) -> list[str]:
    return await QueueManager.extract_safe_file_locations(log_file)


async def display_queue(
    queue: Sequence[str],
    base_dir: Optional[str] = None,
    queue_name: Optional[str] = None,
    save_to_log: bool = True,
) -> None:
    await QueueManager.display_queue(queue, base_dir=base_dir, queue_name=queue_name, save_to_log=save_to_log)


async def handle_queue(
    path: str,
    meta: MutableMapping[str, Any],
    paths: Sequence[str],
    base_dir: str,
) -> tuple[QueueList, Optional[str]]:
    return await QueueManager.handle_queue(path, meta, paths, base_dir)
