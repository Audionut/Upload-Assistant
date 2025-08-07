import os
import re
import anitopy
from guessit import guessit
from src.console import console


async def get_name(meta):
    type = meta.get('type', "").upper()
    title = meta.get('title', "")
    alt_title = meta.get('aka', "")
    year = meta.get('year', "")
    if int(meta.get('manual_year')) > 0:
        year = meta.get('manual_year')
    resolution = meta.get('resolution', "")
    if resolution == "OTHER":
        resolution = ""
    audio = meta.get('audio', "")
    service = meta.get('service', "")
    season = meta.get('season', "")
    episode = meta.get('episode', "")
    part = meta.get('part', "")
    repack = meta.get('repack', "")
    three_d = meta.get('3D', "")
    tag = meta.get('tag', "")
    source = meta.get('source', "")
    uhd = meta.get('uhd', "")
    hdr = meta.get('hdr', "")
    hybrid = 'Hybrid' if meta.get('webdv', "") else ""
    if meta.get('manual_episode_title'):
        episode_title = meta.get('manual_episode_title')
    elif meta.get('daily_episode_title'):
        episode_title = meta.get('daily_episode_title')
    else:
        episode_title = ""
    if meta.get('is_disc', "") == "BDMV":  # Disk
        video_codec = meta.get('video_codec', "")
        region = meta.get('region', "")
    elif meta.get('is_disc', "") == "DVD":
        region = meta.get('region', "")
        dvd_size = meta.get('dvd_size', "")
    else:
        video_codec = meta.get('video_codec', "")
        video_encode = meta.get('video_encode', "")
    edition = meta.get('edition', "")
    if 'hybrid' in edition.upper():
        edition = edition.replace('Hybrid', '').strip()

    if meta['category'] == "TV":
        if meta['search_year'] != "":
            year = meta['year']
        else:
            year = ""
        if meta.get('manual_date'):
            # Ignore season and year for --daily flagged shows, just use manual date stored in episode_name
            season = ''
            episode = ''
    if meta.get('no_season', False) is True:
        season = ''
    if meta.get('no_year', False) is True:
        year = ''
    if meta.get('no_aka', False) is True:
        alt_title = ''
    if meta['debug']:
        console.log("[cyan]get_name cat/type")
        console.log(f"CATEGORY: {meta['category']}")
        console.log(f"TYPE: {meta['type']}")
        console.log("[cyan]get_name meta:")
        # console.log(meta)

    # YAY NAMING FUN
    if meta['category'] == "MOVIE":  # MOVIE SPECIFIC
        if type == "DISC":  # Disk
            if meta['is_disc'] == 'BDMV':
                name = f"{title} {alt_title} {year} {three_d} {edition} {hybrid} {repack} {resolution} {region} {uhd} {source} {hdr} {video_codec} {audio}"
                potential_missing = ['edition', 'region', 'distributor']
            elif meta['is_disc'] == 'DVD':
                name = f"{title} {alt_title} {year} {edition} {repack} {source} {dvd_size} {audio}"
                potential_missing = ['edition', 'distributor']
            elif meta['is_disc'] == 'HDDVD':
                name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {source} {video_codec} {audio}"
                potential_missing = ['edition', 'region', 'distributor']
        elif type == "REMUX" and source in ("BluRay", "HDDVD"):  # BluRay/HDDVD Remux
            name = f"{title} {alt_title} {year} {three_d} {edition} {hybrid} {repack} {resolution} {uhd} {source} REMUX {hdr} {video_codec} {audio}"
            potential_missing = ['edition', 'description']
        elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
            name = f"{title} {alt_title} {year} {edition} {repack} {source} REMUX  {audio}"
            potential_missing = ['edition', 'description']
        elif type == "ENCODE":  # Encode
            name = f"{title} {alt_title} {year} {edition} {hybrid} {repack} {resolution} {uhd} {source} {audio} {hdr} {video_encode}"
            potential_missing = ['edition', 'description']
        elif type == "WEBDL":  # WEB-DL
            name = f"{title} {alt_title} {year} {edition} {hybrid} {repack} {resolution} {uhd} {service} WEB-DL {audio} {hdr} {video_encode}"
            potential_missing = ['edition', 'service']
        elif type == "WEBRIP":  # WEBRip
            name = f"{title} {alt_title} {year} {edition} {hybrid} {repack} {resolution} {uhd} {service} WEBRip {audio} {hdr} {video_encode}"
            potential_missing = ['edition', 'service']
        elif type == "HDTV":  # HDTV
            name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {source} {audio} {video_encode}"
            potential_missing = []
        elif type == "DVDRIP":
            name = f"{title} {alt_title} {year} {source} {video_encode} DVDRip {audio}"
            potential_missing = []
    elif meta['category'] == "TV":  # TV SPECIFIC
        if type == "DISC":  # Disk
            if meta['is_disc'] == 'BDMV':
                name = f"{title} {year} {alt_title} {season}{episode} {three_d} {edition} {hybrid} {repack} {resolution} {region} {uhd} {source} {hdr} {video_codec} {audio}"
                potential_missing = ['edition', 'region', 'distributor']
            if meta['is_disc'] == 'DVD':
                name = f"{title} {alt_title} {season}{episode}{three_d} {edition} {repack} {source} {dvd_size} {audio}"
                potential_missing = ['edition', 'distributor']
            elif meta['is_disc'] == 'HDDVD':
                name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {source} {video_codec} {audio}"
                potential_missing = ['edition', 'region', 'distributor']
        elif type == "REMUX" and source in ("BluRay", "HDDVD"):  # BluRay Remux
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {three_d} {edition} {hybrid} {repack} {resolution} {uhd} {source} REMUX {hdr} {video_codec} {audio}"  # SOURCE
            potential_missing = ['edition', 'description']
        elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {source} REMUX {audio}"  # SOURCE
            potential_missing = ['edition', 'description']
        elif type == "ENCODE":  # Encode
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {hybrid} {repack} {resolution} {uhd} {source} {audio} {hdr} {video_encode}"  # SOURCE
            potential_missing = ['edition', 'description']
        elif type == "WEBDL":  # WEB-DL
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {hybrid} {repack} {resolution} {uhd} {service} WEB-DL {audio} {hdr} {video_encode}"
            potential_missing = ['edition', 'service']
        elif type == "WEBRIP":  # WEBRip
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {hybrid} {repack} {resolution} {uhd} {service} WEBRip {audio} {hdr} {video_encode}"
            potential_missing = ['edition', 'service']
        elif type == "HDTV":  # HDTV
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {resolution} {source} {audio} {video_encode}"
            potential_missing = []
        elif type == "DVDRIP":
            name = f"{title} {alt_title} {season} {source} DVDRip {video_encode}"
            potential_missing = []

    try:
        name = ' '.join(name.split())
    except Exception:
        console.print("[bold red]Unable to generate name. Please re-run and correct any of the following args if needed.")
        console.print(f"--category [yellow]{meta['category']}")
        console.print(f"--type [yellow]{meta['type']}")
        console.print(f"--source [yellow]{meta['source']}")
        console.print("[bold green]If you specified type, try also specifying source")

        exit()
    name_notag = name
    name = name_notag + tag
    clean_name = await clean_filename(name)
    return name_notag, name, clean_name, potential_missing


async def clean_filename(name):
    invalid = '<>:"/\\|?*'
    for char in invalid:
        name = name.replace(char, '-')
    return name


async def extract_title_and_year(meta, filename):
    basename = os.path.basename(filename)
    basename = os.path.splitext(basename)[0]

    secondary_title = None
    year = None

    # Check for AKA patterns first
    aka_patterns = [' AKA ', '.aka.', ' aka ', '.AKA.']
    for pattern in aka_patterns:
        if pattern in basename:
            aka_parts = basename.split(pattern, 1)
            if len(aka_parts) > 1:
                primary_title = aka_parts[0].strip()
                secondary_part = aka_parts[1].strip()

                # Look for a year in the primary title
                year_match_primary = re.search(r'\b(19|20)\d{2}\b', primary_title)
                if year_match_primary:
                    year = year_match_primary.group(0)

                # Process secondary title
                secondary_match = re.match(r"^(\d+)", secondary_part)
                if secondary_match:
                    secondary_title = secondary_match.group(1)
                else:
                    # Catch everything after AKA until it hits a year or release info
                    year_or_release_match = re.search(r'\b(19|20)\d{2}\b|\bBluRay\b|\bREMUX\b|\b\d+p\b|\bDTS-HD\b|\bAVC\b', secondary_part)
                    if year_or_release_match:
                        # Check if we found a year in the secondary part
                        if re.match(r'\b(19|20)\d{2}\b', year_or_release_match.group(0)):
                            # If no year was found in primary title, or we want to override
                            if not year:
                                year = year_or_release_match.group(0)

                        secondary_title = secondary_part[:year_or_release_match.start()].strip()
                    else:
                        secondary_title = secondary_part

                primary_title = primary_title.replace('.', ' ')
                secondary_title = secondary_title.replace('.', ' ')
                return primary_title, secondary_title, year

    # if not AKA, catch titles that begin with a year
    year_start_match = re.match(r'^(19|20)\d{2}', basename)
    if year_start_match:
        title = year_start_match.group(0)
        rest = basename[len(title):].lstrip('. _-')
        # Look for another year in the rest of the title
        year_match = re.search(r'\b(19|20)\d{2}\b', rest)
        year = year_match.group(0) if year_match else None
        if year:
            return title, None, year

    folder_name = os.path.basename(meta['uuid']) if meta['uuid'] else ""
    if meta['debug']:
        console.print(f"[cyan]Extracting title and year from folder name: {folder_name}[/cyan]")
    # lets do some subsplease handling
    if 'subsplease' in folder_name.lower():
        parsed_title = anitopy.parse(
            guessit(folder_name, {"excludes": ["country", "language"]})['title']
        )['anime_title']
        if parsed_title:
            return parsed_title, None, None

    year_pattern = r'(18|19|20)\d{2}'
    res_pattern = r'\b(480|576|720|1080|2160)[pi]\b'
    type_pattern = r'(WEBDL|BluRay|REMUX|HDRip|Blu-Ray|Web-DL|webrip|web-rip|DVD|BD100|BD50|BD25|HDTV|UHD|HDR|DOVI|REPACK|Season)(?=[._\-\s]|$)'
    season_pattern = r'\bS(\d{1,3})\b'
    season_episode_pattern = r'\bS(\d{1,3})E(\d{1,3})\b'
    date_pattern = r'\b(20\d{2})\.(\d{1,2})\.(\d{1,2})\b'

    # Check for the specific pattern: year.year (e.g., "1970.2014")
    double_year_pattern = r'\b(18|19|20)\d{2}\.(18|19|20)\d{2}\b'
    double_year_match = re.search(double_year_pattern, folder_name)

    if double_year_match:
        full_match = double_year_match.group(0)
        years = full_match.split('.')
        first_year = years[0]
        second_year = years[1]

        if meta['debug']:
            console.print(f"[cyan]Found double year pattern: {full_match}, using {second_year} as year[/cyan]")

        modified_folder_name = folder_name.replace(full_match, first_year)
        year_match = None
        res_match = re.search(res_pattern, modified_folder_name, re.IGNORECASE)
        season_pattern_match = re.search(season_pattern, modified_folder_name, re.IGNORECASE)
        season_episode_match = re.search(season_episode_pattern, modified_folder_name, re.IGNORECASE)
        type_match = re.search(type_pattern, modified_folder_name, re.IGNORECASE)

        indices = [('year', double_year_match.end(), second_year)]
        if res_match:
            indices.append(('res', res_match.start(), res_match.group()))
        if season_pattern_match:
            indices.append(('season', season_pattern_match.start(), season_pattern_match.group()))
        if season_episode_match:
            indices.append(('season_episode', season_episode_match.start(), season_episode_match.group()))
        if type_match:
            indices.append(('type', type_match.start(), type_match.group()))

        folder_name_for_title = modified_folder_name
        actual_year = second_year

    else:
        date_match = re.search(date_pattern, folder_name)
        year_match = re.search(year_pattern, folder_name)
        res_match = re.search(res_pattern, folder_name, re.IGNORECASE)
        season_pattern_match = re.search(season_pattern, folder_name, re.IGNORECASE)
        season_episode_match = re.search(season_episode_pattern, folder_name, re.IGNORECASE)
        type_match = re.search(type_pattern, folder_name, re.IGNORECASE)

        indices = []
        if date_match:
            indices.append(('date', date_match.start(), date_match.group()))
        if year_match and not date_match:
            indices.append(('year', year_match.start(), year_match.group()))
        if res_match:
            indices.append(('res', res_match.start(), res_match.group()))
        if season_pattern_match:
            indices.append(('season', season_pattern_match.start(), season_pattern_match.group()))
        if season_episode_match:
            indices.append(('season_episode', season_episode_match.start(), season_episode_match.group()))
        if type_match:
            indices.append(('type', type_match.start(), type_match.group()))

        folder_name_for_title = folder_name
        actual_year = year_match.group() if year_match and not date_match else None

    if indices:
        indices.sort(key=lambda x: x[1])
        first_type, first_index, first_value = indices[0]
        title_part = folder_name_for_title[:first_index]
        title_part = re.sub(r'[\.\-_ ]+$', '', title_part)
        # Handle unmatched opening parenthesis
        if title_part.count('(') > title_part.count(')'):
            paren_pos = title_part.rfind('(')
            content_after_paren = folder_name[paren_pos + 1:first_index].strip()

            if content_after_paren:
                secondary_title = content_after_paren

            title_part = title_part[:paren_pos].rstrip()
    else:
        title_part = folder_name

    replacements = {
        '_': ' ',
        '.': ' ',
        'DVD9': '',
        'DVD5': '',
        'DVDR': '',
        'BDR': '',
        'HDDVD': '',
        'WEB-DL': '',
        'WEBRip': '',
        'WEB': '',
        'BluRay': '',
        'Blu-ray': '',
        'HDTV': '',
        'DVDRip': '',
        'REMUX': '',
        'HDR': '',
        'UHD': '',
        '4K': '',
        'DVD': '',
        'HDRip': '',
        'BDMV': '',
        'R1': '',
        'R2': '',
        'R3': '',
        'R4': '',
        'R5': '',
        'R6': '',
        "Director's Cut": '',
        "Extended Edition": '',
        "directors cut": '',
        "director cut": '',
    }
    filename = re.sub(r'\s+', ' ', filename)
    filename = await multi_replace(title_part, replacements)

    if filename:
        # Look for content in parentheses
        bracket_pattern = r'\s*\(([^)]+)\)\s*'
        bracket_match = re.search(bracket_pattern, filename)

        if bracket_match:
            bracket_content = bracket_match.group(1).strip()

            # Only add to secondary_title if we don't already have one
            if not secondary_title and bracket_content:
                secondary_title = bracket_content
                secondary_title = re.sub(r'[\.\-_ ]+$', '', secondary_title)

            filename = re.sub(bracket_pattern, ' ', filename)
            filename = re.sub(r'\s+', ' ', filename).strip()

    if filename:
        return filename, secondary_title, actual_year

    # If no pattern match works but there's still a year in the filename, extract it
    year_match = re.search(r'(?<!\d)(19|20)\d{2}(?!\d)', basename)
    if year_match:
        year = year_match.group(0)
        return None, None, year

    return None, None, None


async def multi_replace(text, replacements):
    for old, new in replacements.items():
        text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
    return text
