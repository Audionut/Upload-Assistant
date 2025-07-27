import os
import re
import subprocess
from src.console import console
from data.config import config


async def nfo_link(meta):
    """Create an Emby-compliant NFO file from metadata"""
    try:
        # Get basic info
        imdb_info = meta.get('imdb_info', {})
        title = imdb_info.get('title', meta.get('title', ''))
        year = imdb_info.get('year', meta.get('year', ''))
        plot = imdb_info.get('plot', meta.get('overview', ''))
        rating = imdb_info.get('rating', '')
        runtime = imdb_info.get('runtime', '')
        genres = imdb_info.get('genres', '')
        country = imdb_info.get('country', '')
        aka = imdb_info.get('aka', '')

        # IDs
        imdb_id = imdb_info.get('imdbID', '').replace('tt', '')
        tmdb_id = meta.get('tmdb_id', '')
        tvdb_id = meta.get('tvdb_id', '')
        mal_id = meta.get('mal_id', '')
        tvmaze_id = meta.get('tvmaze_id', '')

        # Images
        poster = meta.get('poster', '')
        backdrop = meta.get('backdrop', '')

        # Build NFO XML content
        nfo_content = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <movie>
            <title>{title}</title>
            <originaltitle>{aka}</originaltitle>
            <year>{year}</year>
            <plot>{plot}</plot>
            <runtime>{runtime}</runtime>
            <country>{country}</country>
            <rating>{rating}</rating>
            <imdbid>{imdb_id}</imdbid>
            <tmdbid>{tmdb_id}</tmdbid>
            <tvdbid>{tvdb_id}</tvdbid>
            <malid>{mal_id}</malid>
            <tvmazeid>{tvmaze_id}</tvmazeid>
            <thumb aspect="poster">{poster}</thumb>
            <fanart>
                <thumb>{backdrop}</thumb>
            </fanart>
        '''

        # Add genres
        if genres:
            genre_list = [g.strip() for g in genres.split(',')]
            for genre in genre_list:
                nfo_content += f'    <genre>{genre}</genre>\n'

        nfo_content += '</movie>'

        # Save NFO file
        movie_name = meta.get('title', 'movie')
        # Remove or replace invalid characters: < > : " | ? * \ /
        movie_name = re.sub(r'[<>:"|?*\\/]', '', movie_name)
        save_path = await linking(meta, movie_name, year)
        if save_path is not None:
            save_path = os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}/", f"{movie_name}.nfo")
        os.makedirs(save_path, exist_ok=True)
        nfo_file_path = os.path.join(save_path, f"{movie_name}.nfo")

        with open(nfo_file_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)

        if meta['debug']:
            console.print(f"[green]Emby NFO created at {nfo_file_path}")

        return nfo_file_path

    except Exception as e:
        console.print(f"[red]Failed to create Emby NFO: {e}")
        return None


async def linking(meta, movie_name, year):
    folder_name = f"{movie_name} ({year})"
    target_base = config['DEFAULT'].get('emby_dir', None)
    if target_base is not None:
        target_dir = os.path.join(target_base, folder_name)
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

            except subprocess.CalledProcessError as e:
                console.print(f"[red]Failed to create file symlink: {e}")

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

                    except subprocess.CalledProcessError as e:
                        console.print(f"[red]Failed to create symlink for {file}: {e}")

        console.print(f"[green]Movie folder created: {target_dir}")
        return target_dir
    else:
        return None
