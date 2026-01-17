# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import datetime
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any, Optional, cast

from src.console import console

Meta = dict[str, Any]


class NfoLinkManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.default_config = cast(dict[str, Any], config.get('DEFAULT', {}))

    async def create_season_nfo(
        self,
        season_folder: str,
        season_number: str,
        season_year: str,
        tvdbid: str,
        tvmazeid: str,
        plot: str,
        outline: str,
    ) -> str:
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

    async def nfo_link(self, meta: Meta) -> Optional[str]:
        """Create an Emby-compliant NFO file from metadata"""
        try:
            # Get basic info
            imdb_info = cast(dict[str, Any], meta.get('imdb_info') or {})
            title = str(imdb_info.get('title') or meta.get('title') or '')
            year = (
                str(imdb_info.get('year') or meta.get('year') or '')
                if meta['category'] == "MOVIE"
                else str(meta.get('search_year') or '')
            )
            plot = str(meta.get('overview') or '')
            rating = str(imdb_info.get('rating') or '')
            runtime = imdb_info.get('runtime') or meta.get('runtime') or ''
            genres = imdb_info.get('genres') or meta.get('genres') or ''
            country = str(imdb_info.get('country') or meta.get('country') or '')
            aka = str(imdb_info.get('aka') or title)
            tagline = str(imdb_info.get('plot') or '')
            premiered = str(meta.get('release_date') or '')

            # IDs
            imdb_id_raw = imdb_info.get('imdbID') or meta.get('imdb_id') or ''
            imdb_id = str(imdb_id_raw).replace('tt', '') if imdb_id_raw else ''
            tmdb_id = str(meta.get('tmdb_id') or '')
            tvdb_id = str(meta.get('tvdb_id') or '')

            # Cast and crew
            cast_list = cast(list[dict[str, Any]], meta.get('cast') or [])
            directors = cast(list[Any], meta.get('directors') or [])
            studios = cast(list[Any], meta.get('studios') or [])

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
            for actor in cast_list:
                name = str(actor.get('name') or '')
                role = str(actor.get('character') or actor.get('role') or '')
                tmdb_actor_id = str(actor.get('id') or '')
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
                if isinstance(director, Mapping):
                    director_map = cast(Mapping[str, Any], director)
                    director_name = str(director_map.get('name') or '')
                    director_id = str(director_map.get('id') or '')
                else:
                    director_name = str(director)
                    director_id = ''
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
                runtime_minutes = str(runtime)
                if isinstance(runtime, str) and 'min' in runtime:
                    runtime_minutes = runtime.replace('min', '').strip()
                nfo_content += f'\n  <runtime>{runtime_minutes}</runtime>'

            # Add country
            if country:
                nfo_content += f'\n  <country>{country}</country>'

            # Add genres
            if genres:
                if isinstance(genres, str):
                    genre_list: list[str] = [g.strip() for g in genres.split(',')]
                elif isinstance(genres, Sequence):
                    genre_list = [str(g).strip() for g in cast(Sequence[Any], genres)]
                else:
                    genre_list = []
                for genre in genre_list:
                    if genre:
                        nfo_content += f'\n  <genre>{genre}</genre>'

            # Add studios
            for studio in studios:
                studio_name = (
                    str(cast(Mapping[str, Any], studio).get('name') or '')
                    if isinstance(studio, Mapping)
                    else str(studio)
                )
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
            movie_name = str(meta.get('title') or 'movie')
            # Remove or replace invalid characters: < > : " | ? * \ /
            movie_name = re.sub(r'[<>:"|?*\\/]', '', movie_name)
            meta['linking_failed'] = False
            link_dir = await self.linking(meta, movie_name, year)

            uuid = str(meta.get('uuid') or '')
            filelist = cast(list[str], meta.get('filelist') or [])
            if len(filelist) == 1 and os.path.isfile(filelist[0]) and not meta.get('keep_folder'):
                # Single file - create symlink in the target folder
                src_file = filelist[0]
                filename = os.path.splitext(os.path.basename(src_file))[0]
            else:
                filename = uuid

            if meta['category'] == "TV" and link_dir is not None and not meta.get('linking_failed', False):
                season_number = str(meta.get('season_int') or meta.get('season') or "1")
                season_year = str(meta.get('search_year') or meta.get('year') or "")
                tvdbid = str(meta.get('tvdb_id') or '')
                tvmazeid = str(meta.get('tvmaze_id') or '')
                plot = str(meta.get('overview') or '')
                outline = str(imdb_info.get('plot') or '')

                season_folder = link_dir
                if not os.path.exists(f"{season_folder}/season.nfo"):
                    await self.create_season_nfo(
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

    async def linking(self, meta: Meta, movie_name: str, year: str) -> Optional[str]:
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

        target_base = (
            self.default_config.get('emby_tv_dir')
            if meta['category'] == "TV"
            else self.default_config.get('emby_dir')
        )
        if target_base is not None:
            if meta['category'] == "MOVIE":
                target_dir = os.path.join(target_base, folder_name)
            else:
                if meta.get('season') == 'S00':
                    season = "Specials"
                else:
                    season_value = meta.get('season_int')
                    season_int = str(season_value).zfill(2) if season_value is not None else "01"
                    season = f"Season {season_int}"
                target_dir = os.path.join(target_base, folder_name, season)

            os.makedirs(target_dir, exist_ok=True)
            # Get source path and files
            path = cast(Optional[str], meta.get('path'))
            filelist = cast(list[str], meta.get('filelist') or [])

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
                    cmd = ['cmd', '/c', 'mklink', target_file, src_file] if os.name == 'nt' else ['ln', '-s', src_file, target_file]
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    if meta.get('debug'):
                        console.print(f"[green]Created symlink: {target_file}")

                except subprocess.CalledProcessError:
                    meta['linking_failed'] = True

            else:
                # Folder content - symlink all files from the source folder
                src_dir = path if os.path.isdir(path) else os.path.dirname(path)

                # Get all files in the source directory
                for root, _dirs, files in os.walk(src_dir):
                    for file in files:
                        src_file = os.path.join(root, file)
                        # Create relative path structure in target
                        rel_path = os.path.relpath(src_file, src_dir)
                        target_file = os.path.join(target_dir, rel_path)

                        # Create subdirectories if needed
                        target_file_dir = os.path.dirname(target_file)
                        os.makedirs(target_file_dir, exist_ok=True)

                        try:
                            cmd = ['cmd', '/c', 'mklink', target_file, src_file] if os.name == 'nt' else ['ln', '-s', src_file, target_file]
                            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                            if meta.get('debug'):
                                console.print(f"[green]Created symlink: {file}")

                        except subprocess.CalledProcessError:
                            meta['linking_failed'] = True

            console.print(f"[green]Movie folder created: {target_dir}")
            return target_dir
        return None
