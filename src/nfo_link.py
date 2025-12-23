# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
import subprocess
import datetime
from src.console import console
from data.config import config


async def create_season_nfo(season_folder, season_number, season_year, tvdbid, tvmazeid, plot, outline):
    """Create a season.nfo file in the given season folder."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nfo_content = f'''<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<season>
  <plot><![CDATA[{plot}]]></plot>
  <outline><![CDATA[{outline}]]></outline>
  <lockdata>false</lockdata>
  <dateadded>{now}</dateadded>
  <title>Season {season_number}</title>
  <year>{season_year}</year>
  <sorttitle>Season {season_number}</sorttitle>
  <tvdbid>{tvdbid}</tvdbid>
  <uniqueid type="tvdb">{tvdbid}</uniqueid>
  <uniqueid type="tvmaze">{tvmazeid}</uniqueid>
  <tvmazeid>{tvmazeid}</tvmazeid>
  <seasonnumber>{season_number}</seasonnumber>
</season>'''
    nfo_path = os.path.join(season_folder, "season.nfo")
    with open(nfo_path, "w", encoding="utf-8") as f:
        f.write(nfo_content)
    return nfo_path


async def nfo_link(meta):
    """Create an Emby-compliant NFO file from metadata"""
    try:
        # Get basic info
        imdb_info = meta.get('imdb_info', {})
        title = imdb_info.get('title', meta.get('title', ''))
        if meta['category'] == "MOVIE":
            year = imdb_info.get('year', meta.get('year', ''))
        else:
            year = meta.get('search_year', '')
        plot = meta.get('overview', '')
        rating = imdb_info.get('rating', '')
        runtime = imdb_info.get('runtime', meta.get('runtime', ''))
        genres = imdb_info.get('genres', meta.get('genres', ''))
        country = imdb_info.get('country', meta.get('country', ''))
        aka = imdb_info.get('aka', title)  # Fallback to title if no aka
        tagline = imdb_info.get('plot', '')
        premiered = meta.get('release_date', '')

        # IDs
        imdb_id = imdb_info.get('imdbID', meta.get('imdb_id', '')).replace('tt', '')
        tmdb_id = meta.get('tmdb_id', '')
        tvdb_id = meta.get('tvdb_id', '')

        # Cast and crew
        cast = meta.get('cast', [])
        directors = meta.get('directors', [])
        studios = meta.get('studios', [])

        # Build NFO XML content with proper structure
        nfo_content = '''<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<movie>'''

        # Add plot with CDATA
        if plot:
            nfo_content += f'\n  <plot><![CDATA[{plot}]]></plot>'

        # Add tagline if available
        if tagline:
            nfo_content += f'\n  <outline><![CDATA[{tagline}]]></outline>'
            nfo_content += f'\n  <tagline>{tagline}</tagline>'

        # Basic metadata
        nfo_content += f'\n  <title>{title}</title>'
        nfo_content += f'\n  <originaltitle>{aka}</originaltitle>'

        # Add cast/actors
        for actor in cast:
            name = actor.get('name', '')
            role = actor.get('character', actor.get('role', ''))
            tmdb_actor_id = actor.get('id', '')
            if name:
                nfo_content += '\n  <actor>'
                nfo_content += f'\n    <name>{name}</name>'
                if role:
                    nfo_content += f'\n    <role>{role}</role>'
                nfo_content += '\n    <type>Actor</type>'
                if tmdb_actor_id:
                    nfo_content += f'\n    <tmdbid>{tmdb_actor_id}</tmdbid>'
                nfo_content += '\n  </actor>'

        # Add directors
        for director in directors:
            director_name = director.get('name', director) if isinstance(director, dict) else director
            director_id = director.get('id', '') if isinstance(director, dict) else ''
            if director_name:
                nfo_content += '\n  <director'
                if director_id:
                    nfo_content += f' tmdbid="{director_id}"'
                nfo_content += f'>{director_name}</director>'

        # Add rating and year
        if rating:
            nfo_content += f'\n  <rating>{rating}</rating>'
        if year:
            nfo_content += f'\n  <year>{year}</year>'

        nfo_content += f'\n  <sorttitle>{title}</sorttitle>'

        # Add IDs
        if imdb_id:
            nfo_content += f'\n  <imdbid>tt{imdb_id}</imdbid>'
        if tvdb_id:
            nfo_content += f'\n  <tvdbid>{tvdb_id}</tvdbid>'
        if tmdb_id:
            nfo_content += f'\n  <tmdbid>{tmdb_id}</tmdbid>'

        # Add dates
        if premiered:
            nfo_content += f'\n  <premiered>{premiered}</premiered>'
            nfo_content += f'\n  <releasedate>{premiered}</releasedate>'

        # Add runtime (convert to minutes if needed)
        if runtime:
            # Handle runtime in different formats
            runtime_minutes = runtime
            if isinstance(runtime, str) and 'min' in runtime:
                runtime_minutes = runtime.replace('min', '').strip()
            nfo_content += f'\n  <runtime>{runtime_minutes}</runtime>'

        # Add country
        if country:
            nfo_content += f'\n  <country>{country}</country>'

        # Add genres
        if genres:
            if isinstance(genres, str):
                genre_list = [g.strip() for g in genres.split(',')]
            else:
                genre_list = genres
            for genre in genre_list:
                if genre:
                    nfo_content += f'\n  <genre>{genre}</genre>'

        # Add studios
        for studio in studios:
            studio_name = studio.get('name', studio) if isinstance(studio, dict) else studio
            if studio_name:
                nfo_content += f'\n  <studio>{studio_name}</studio>'

        # Add unique IDs
        if tmdb_id:
            nfo_content += f'\n  <uniqueid type="tmdb">{tmdb_id}</uniqueid>'
        if imdb_id:
            nfo_content += f'\n  <uniqueid type="imdb">tt{imdb_id}</uniqueid>'
        if tvdb_id:
            nfo_content += f'\n  <uniqueid type="tvdb">{tvdb_id}</uniqueid>'

        # Add legacy ID
        if imdb_id:
            nfo_content += f'\n  <id>tt{imdb_id}</id>'

        nfo_content += '\n</movie>'

        # Save NFO file
        movie_name = meta.get('title', 'movie')
        # Remove or replace invalid characters: < > : " | ? * \ /
        movie_name = re.sub(r'[<>:"|?*\\/]', '', movie_name)
        meta['linking_failed'] = False
        link_dir = await linking(meta, movie_name, year)

        uuid = meta.get('uuid')
        filelist = meta.get('filelist', [])
        if len(filelist) == 1 and os.path.isfile(filelist[0]) and not meta.get('keep_folder'):
            # Single file - create symlink in the target folder
            src_file = filelist[0]
            filename = os.path.splitext(os.path.basename(src_file))[0]
        else:
            filename = uuid

        if meta['category'] == "TV" and link_dir is not None and not meta.get('linking_failed', False):
            season_number = meta.get('season_int') or meta.get('season') or "1"
            season_year = meta.get('search_year') or meta.get('year') or ""
            tvdbid = meta.get('tvdb_id', '')
            tvmazeid = meta.get('tvmaze_id', '')
            plot = meta.get('overview', '')
            outline = imdb_info.get('plot', '')

            season_folder = link_dir
            if not os.path.exists(f"{season_folder}/season.nfo"):
                await create_season_nfo(
                    season_folder, season_number, season_year, tvdbid, tvmazeid, plot, outline
                )
            nfo_file_path = os.path.join(season_folder, "season.nfo")

        elif link_dir is not None and not meta.get('linking_failed', False):
            nfo_file_path = os.path.join(link_dir, f"{filename}.nfo")
        else:
            if meta.get('linking_failed', False):
                console.print("[red]Linking failed, saving NFO in data/nfos[/red]")
            nfo_dir = os.path.join(f"{meta['base_dir']}/data/nfos/{meta['uuid']}/")
            os.makedirs(nfo_dir, exist_ok=True)
            nfo_file_path = os.path.join(nfo_dir, f"{filename}.nfo")
        with open(nfo_file_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)

        if meta['debug']:
            console.print(f"[green]Emby NFO created at {nfo_file_path}")

        return nfo_file_path

    except Exception as e:
        console.print(f"[red]Failed to create Emby NFO: {e}")
        return None


async def linking(meta, movie_name, year):
    if meta['category'] == "MOVIE":
        if not meta['is_disc']:
            folder_name = f"{movie_name} ({year})"
        elif meta['is_disc'] == "BDMV":
            folder_name = f"{movie_name} ({year}) - Disc"
        else:
            folder_name = f"{movie_name} ({year}) - {meta['is_disc']}"
    else:
        if not meta.get('search_year'):
            if not meta['is_disc']:
                folder_name = f"{movie_name}"
            elif meta['is_disc'] == "BDMV":
                folder_name = f"{movie_name} - Disc"
            else:
                folder_name = f"{movie_name} - {meta['is_disc']}"
        else:
            if not meta['is_disc']:
                folder_name = f"{movie_name} ({meta['search_year']})"
            elif meta['is_disc'] == "BDMV":
                folder_name = f"{movie_name} ({meta['search_year']}) - Disc"
            else:
                folder_name = f"{movie_name} ({meta['search_year']}) - {meta['is_disc']}"

    if meta['category'] == "TV":
        target_base = config['DEFAULT'].get('emby_tv_dir', None)
    else:
        target_base = config['DEFAULT'].get('emby_dir', None)
    if target_base is not None:
        if meta['category'] == "MOVIE":
            target_dir = os.path.join(target_base, folder_name)
        else:
            if meta.get('season') == 'S00':
                season = "Specials"
            else:
                season_int = str(meta.get('season_int')).zfill(2)
                season = f"Season {season_int}"
            target_dir = os.path.join(target_base, folder_name, season)

        os.makedirs(target_dir, exist_ok=True)
        # Get source path and files
        path = meta.get('path')
        filelist = meta.get('filelist', [])

        if not path:
            console.print("[red]No path found in meta.")
            return None

        # Handle single file vs folder content
        if len(filelist) == 1 and os.path.isfile(filelist[0]) and not meta.get('keep_folder'):
            # Single file - create symlink in the target folder
            src_file = filelist[0]
            filename = os.path.basename(src_file)
            target_file = os.path.join(target_dir, filename)

            try:
                cmd = f'mklink "{target_file}" "{src_file}"'
                subprocess.run(cmd, check=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if meta.get('debug'):
                    console.print(f"[green]Created symlink: {target_file}")

            except subprocess.CalledProcessError:
                meta['linking_failed'] = True

        else:
            # Folder content - symlink all files from the source folder
            src_dir = path if os.path.isdir(path) else os.path.dirname(path)

            # Get all files in the source directory
            for root, dirs, files in os.walk(src_dir):
                for file in files:
                    src_file = os.path.join(root, file)
                    # Create relative path structure in target
                    rel_path = os.path.relpath(src_file, src_dir)
                    target_file = os.path.join(target_dir, rel_path)

                    # Create subdirectories if needed
                    target_file_dir = os.path.dirname(target_file)
                    os.makedirs(target_file_dir, exist_ok=True)

                    try:
                        cmd = f'mklink "{target_file}" "{src_file}"'
                        subprocess.run(cmd, check=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                        if meta.get('debug'):
                            console.print(f"[green]Created symlink: {file}")

                    except subprocess.CalledProcessError:
                        meta['linking_failed'] = True

        console.print(f"[green]Movie folder created: {target_dir}")
        return target_dir
    else:
        return None
