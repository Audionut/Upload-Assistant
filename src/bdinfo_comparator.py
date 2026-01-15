import difflib
import os
from typing import Any
from src.console import console


def get_relevant_lines(bd_info_text: str) -> list[str]:
    """
    Parses BDInfo text to extract and normalize relevant video, audio, and subtitle tracks.

    Args:
        bd_info_text: The raw string content of a BDInfo report.

    Returns:
        A list of normalized strings containing video lines followed by sorted audio and subtitle lines.
    """
    video_tracks: list[str] = []
    audio_tracks: list[str] = []
    subtitle_tracks: list[str] = []

    for line in bd_info_text.splitlines():
        clean_line = line.strip()

        if "kbps" in clean_line:
            normalized_line = " ".join(clean_line.split())

            if "fps" in normalized_line and "/" in normalized_line:
                video_tracks.append(normalized_line)
            elif "Presentation Graphics" in normalized_line or "Subtitle:" in normalized_line:
                subtitle_tracks.append(normalized_line)
            elif "/" in normalized_line and "kHz" in normalized_line:
                audio_tracks.append(normalized_line)

    # Return grouped result: video first, then sorted audio and subtitles for easier comparison
    return video_tracks + sorted(audio_tracks) + sorted(subtitle_tracks)


def compare_bdinfo(meta: dict[str, Any], entry: dict[str, Any]) -> str:
    """
    Compares the current BDInfo against a duplicate release's BDInfo and prints a diff to the console.

    Args:
        entry: dict[str, Any],
        entry: A dictionary containing information about the duplicate release, including its BDInfo.

    Returns:
        A formatted warning string if differences are not found or if data is missing.
    """
    warning_message = ""
    release_name = str(entry.get('name', '') or '')
    duplicate_bdinfo_content = str(entry.get('bd_info', '') or '')

    source_bd_content = ""

    is_extended_report = (
        "PLAYLIST REPORT:" in duplicate_bdinfo_content or
        "DISC INFO:" in duplicate_bdinfo_content
    )

    file_prefix = "BD_SUMMARY_EXT_00" if is_extended_report else "BD_SUMMARY_00"
    local_info_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/{file_prefix}.txt"

    if os.path.exists(local_info_path):
        with open(local_info_path, "r", encoding="utf-8") as file_handle:
            source_bd_content = file_handle.read()

    source_parsed_lines = get_relevant_lines(source_bd_content)
    target_parsed_lines = get_relevant_lines(duplicate_bdinfo_content)

    diff_generator = difflib.ndiff(source_parsed_lines, target_parsed_lines)

    console.print(f"\n[bold yellow]RELEASE:[/bold yellow] {release_name}")
    console.print("[dim]Comparison Details:[/dim]\n")

    comparison_results: list[dict[str, str]] = []

    for line in diff_generator:
        # Ignore difflib's internal hint lines (starting with '? ')
        if line.startswith("? "):
            continue

        prefix = line[:2]  # "- ", "+ ", or "  "
        content = line[2:].strip()

        if not content:
            continue

        comparison_results.append({"prefix": prefix, "content": content})

    has_detected_changes = False

    def sorting_priority(item: dict[str, str]) -> tuple[int, str]:
        """
        Define priority: 0 for Video, 1 for Audio, 2 for Subtitles.
        Then sorts alphabetically within those groups.
        """
        content = item["content"].lower()
        if "fps" in content:
            priority = 0
        elif "subtitle" in content or "presentation graphics" in content:
            priority = 2
        else:
            priority = 1

        return (priority, content)

    # Sort using the custom priority function
    comparison_results.sort(key=sorting_priority)

    for item in comparison_results:
        prefix = item["prefix"]
        content = item["content"]

        if prefix == "- ":
            has_detected_changes = True
            console.print(f"[bold red][-] YOURS:     {content}[/bold red]")
        elif prefix == "+ ":
            has_detected_changes = True
            console.print(f"[bold green][+] DUPLICATE: {content}[/bold green]")
        else:
            # "  " indicates a match in ndiff
            console.print(f"[bold white][ ] MATCH:     {content}[/bold white]")

    if not duplicate_bdinfo_content:
        warning_message = (
            f"[yellow]⚠  Warning[/yellow] for dupe [bold green]{release_name}[/bold green]:\n"
            "No BDInfo found for duplicate release!"
        )
    elif not has_detected_changes:
        warning_message = (
            f"[yellow]⚠  Warning[/yellow] for dupe [bold green]{release_name}[/bold green]:\n"
            "No differences found between your BDInfo and the duplicate release BDInfo."
        )

    return warning_message
