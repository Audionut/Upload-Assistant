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
                name = f"{title} {alt_title} {year} {three_d} {edition} {repack} {resolution} {region} {uhd} {source} {hdr} {video_codec} {audio}"
                potential_missing = ['edition', 'region', 'distributor']
            elif meta['is_disc'] == 'DVD':
                name = f"{title} {alt_title} {year} {edition} {repack} {source} {dvd_size} {audio}"
                potential_missing = ['edition', 'distributor']
            elif meta['is_disc'] == 'HDDVD':
                name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {source} {video_codec} {audio}"
                potential_missing = ['edition', 'region', 'distributor']
        elif type == "REMUX" and source in ("BluRay", "HDDVD"):  # BluRay/HDDVD Remux
            name = f"{title} {alt_title} {year} {three_d} {edition} {repack} {resolution} {uhd} {source} REMUX {hdr} {video_codec} {audio}"
            potential_missing = ['edition', 'description']
        elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
            name = f"{title} {alt_title} {year} {edition} {repack} {source} REMUX  {audio}"
            potential_missing = ['edition', 'description']
        elif type == "ENCODE":  # Encode
            name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {uhd} {source} {audio} {hdr} {video_encode}"
            potential_missing = ['edition', 'description']
        elif type == "WEBDL":  # WEB-DL
            name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {uhd} {service} WEB-DL {audio} {hdr} {video_encode}"
            potential_missing = ['edition', 'service']
        elif type == "WEBRIP":  # WEBRip
            name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {uhd} {service} WEBRip {audio} {hdr} {video_encode}"
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
                name = f"{title} {year} {alt_title} {season}{episode} {three_d} {edition} {repack} {resolution} {region} {uhd} {source} {hdr} {video_codec} {audio}"
                potential_missing = ['edition', 'region', 'distributor']
            if meta['is_disc'] == 'DVD':
                name = f"{title} {alt_title} {season}{episode}{three_d} {edition} {repack} {source} {dvd_size} {audio}"
                potential_missing = ['edition', 'distributor']
            elif meta['is_disc'] == 'HDDVD':
                name = f"{title} {alt_title} {year} {edition} {repack} {resolution} {source} {video_codec} {audio}"
                potential_missing = ['edition', 'region', 'distributor']
        elif type == "REMUX" and source in ("BluRay", "HDDVD"):  # BluRay Remux
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {three_d} {edition} {repack} {resolution} {uhd} {source} REMUX {hdr} {video_codec} {audio}"  # SOURCE
            potential_missing = ['edition', 'description']
        elif type == "REMUX" and source in ("PAL DVD", "NTSC DVD", "DVD"):  # DVD Remux
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {source} REMUX {audio}"  # SOURCE
            potential_missing = ['edition', 'description']
        elif type == "ENCODE":  # Encode
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {resolution} {uhd} {source} {audio} {hdr} {video_encode}"  # SOURCE
            potential_missing = ['edition', 'description']
        elif type == "WEBDL":  # WEB-DL
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {resolution} {uhd} {service} WEB-DL {audio} {hdr} {video_encode}"
            potential_missing = ['edition', 'service']
        elif type == "WEBRIP":  # WEBRip
            name = f"{title} {year} {alt_title} {season}{episode} {episode_title} {part} {edition} {repack} {resolution} {uhd} {service} WEBRip {audio} {hdr} {video_encode}"
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
