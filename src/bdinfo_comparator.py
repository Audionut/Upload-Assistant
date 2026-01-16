import difflib
import re
from pathlib import Path
from typing import Any, Tuple, List, Dict
from src.console import console

PLAYLIST_VARIATION_PATTERN = re.compile(r"/\s*DN\s*-\d+dB", re.IGNORECASE)
BITRATE_VARIATION_PATTERN = re.compile(r"\d+([.,]\d+)?(?=\s*kbps)", re.IGNORECASE)
BBCODE_PATTERN = re.compile(r"\[[^\]]*\]")


def get_relevant_lines(meta: Dict[str, Any], duplicate_content: str) -> Tuple[List[str], List[str]]:
    """
    Extracts and normalizes relevant BDInfo lines for comparison between source and duplicate content.
    """
    summary, extended_summary = load_bdinfo_file(meta)
    clean_duplicate = remove_bbcode(duplicate_content)

    clean_sum, clean_ext, clean_dup = remove_playlist_variations(summary, extended_summary, clean_duplicate)

    is_extended = any(key in clean_dup for key in ("PLAYLIST REPORT:", "DISC INFO:"))
    is_full = is_extended and "Video:" in clean_dup

    target_lines = normalize_and_filter(clean_dup, strict_mode=is_full)
    source_content = clean_ext if (is_extended and not is_full) else clean_sum
    source_lines = normalize_and_filter(source_content)

    return source_lines, target_lines


def normalize_and_filter(content: str, strict_mode: bool = False) -> List[str]:
    """
    Filters content to keep only relevant technical lines and normalizes whitespace.
    """
    results: List[str] = []
    keywords = ("Video:", "Audio:", "Subtitle:")

    for line in content.splitlines():
        clean_line = line.strip()
        line_lower = clean_line.lower()

        if any(x in line_lower for x in ("kbps", "presentation graphics", "subtitle:")):
            if strict_mode and not any(k in clean_line for k in keywords):
                continue
            results.append(" ".join(clean_line.split()))

    return results


def remove_playlist_variations(summary: str, extended: str, duplicate: str) -> Tuple[str, str, str]:
    """
    Removes technical variations that differ between playlists but represent the same media content.
    """
    def process_content(text: str) -> str:
        if not text:
            return ""

        text = re.sub(PLAYLIST_VARIATION_PATTERN, "", text)
        cleaned_lines: List[str] = []

        for line in text.splitlines():
            line_lower = line.lower()

            if "presentation graphics" in line_lower or "subtitle:" in line_lower:
                line = re.sub(BITRATE_VARIATION_PATTERN, "", line).rstrip()
                if line.endswith('kbps'):
                    line = line[:-4].rstrip()
                if line.endswith('/'):
                    line = line[:-1].rstrip()

            if line.startswith('*'):
                line = line[:1].rstrip()

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    return process_content(summary), process_content(extended), process_content(duplicate)


def compare_bdinfo(meta: Dict[str, Any], entry: Dict[str, Any]) -> Tuple[str, str]:
    """
    Performs a visual comparison between local BDInfo and a duplicate entry, returning status messages.
    """
    release_name = str(entry.get("name", "") or "")
    duplicate_content = has_bdinfo_content(entry)
    source_lines, target_lines = get_relevant_lines(meta, duplicate_content)

    diff_generator = difflib.ndiff(source_lines, target_lines)

    console.print(f"\n[bold yellow]RELEASE:[/bold yellow] {release_name}")
    console.print("[dim]Comparison Details:[/dim]\n")

    comparison_results: List[Dict[str, str]] = []
    stats = {"+ ": 0, "- ": 0}

    for line in diff_generator:
        if line.startswith("? "):
            continue

        prefix, content = line[:2], line[2:].strip()
        if not content:
            continue

        comparison_results.append({"prefix": prefix, "content": content})
        if prefix in stats:
            stats[prefix] += 1

    comparison_results.sort(key=sorting_priority)

    has_detected_changes = False
    for item in comparison_results:
        prefix, content = item["prefix"], item["content"]
        if prefix != "  ":
            has_detected_changes = True

        style = "bold red" if prefix == "- " else "bold green" if prefix == "+ " else "bold white"
        label = "YOURS" if prefix == "- " else "DUPLICATE" if prefix == "+ " else "MATCH"
        symbol = prefix.strip() or " "

        console.print(f"[{style}][{symbol}] {label.ljust(10)}: {content}[/{style}]")

    warning_message = generate_warning(release_name, duplicate_content, has_detected_changes)

    add_val = f"+{stats['+ ']}".ljust(3)
    rem_val = f"-{stats['- ']}".ljust(3)
    diff_summary = f"[bold green]{add_val}[/bold green] [bold red]{rem_val}[/bold red]"

    status_icon = "[yellow]⚠  [/yellow]" if not (stats['+ '] or stats['- ']) else " "
    results = f"{diff_summary} | {status_icon}{release_name}"

    return warning_message, results


def generate_warning(release_name: str, has_content: str, has_changes: bool) -> str:
    """
    Generates user-friendly warning messages based on the comparison state.
    """
    if not has_content:
        return f"[yellow]⚠  Warning[/yellow] for dupe [bold green]{release_name}[/bold green]: [red]No BDInfo found![/red]"
    if not has_changes:
        return f"[yellow]⚠  Warning[/yellow] for dupe [bold green]{release_name}[/bold green]: [red]No differences found.[/red]"
    return ""


def load_bdinfo_file(meta: Dict[str, Any]) -> Tuple[str, str]:
    """
    Reads summary and extended summary files from the temporary metadata directory.
    """
    base_path = Path(meta.get('base_dir', '')) / 'tmp' / str(meta.get('uuid', ''))

    def read_file(name: str) -> str:
        file_path = base_path / name
        return file_path.read_text(encoding="utf-8") if file_path.exists() else ""

    return read_file("BD_SUMMARY_00.txt"), read_file("BD_SUMMARY_EXT_00.txt")


def has_bdinfo_content(entry: Dict[str, Any]) -> str:
    """
    Attempts to locate BDInfo content within an entry's fields.
    """
    content = str(entry.get("bd_info", "") or "")
    if not content:
        description = str(entry.get("description", "") or "")
        keywords = ["Disc Title:", "Disc Label:", "Disc Size: "]
        if any(keyword in description for keyword in keywords):
            content = description
    return content


def remove_bbcode(content: str) -> str:
    """
    Strips BBCode tags from the provided string.
    """
    return re.sub(BBCODE_PATTERN, "", content)


def sorting_priority(item: Dict[str, str]) -> Tuple[int, str]:
    """
    Determines the display order of differences (Video first, then General, then Subtitles).
    """
    content = item["content"].lower()
    if "fps" in content:
        priority = 0
    elif any(x in content for x in ("subtitle", "presentation graphics")):
        priority = 2
    else:
        priority = 1
    return priority, content
