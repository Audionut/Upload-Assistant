# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import httpx
import json
import os
import re
import time
import urllib.parse
from bs4 import BeautifulSoup
from data.config import config
from src.console import console


async def is_scene(video, meta, imdb=None, lower=False):
    if meta['debug']:
        scene_start_time = time.time()

    scene = False
    is_all_lowercase = False
    base = os.path.basename(video)
    match = re.match(r"^(.+)\.[a-zA-Z0-9]{3}$", os.path.basename(video))

    if match and (not meta['is_disc'] or meta['keep_folder']):
        base = match.group(1)
        is_all_lowercase = base.islower()

    quoted_base = urllib.parse.quote(base)

    # Define cache directories
    cache_dir = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], 'srrdb')
    search_cache_dir = os.path.join(cache_dir, 'search')
    details_cache_dir = os.path.join(cache_dir, 'details')
    os.makedirs(search_cache_dir, exist_ok=True)
    os.makedirs(details_cache_dir, exist_ok=True)

    async with httpx.AsyncClient() as client:
        if 'scene' not in meta and not lower and not meta.get('emby_debug', False):
            # Cache file for search
            search_cache_file = os.path.join(search_cache_dir, f"{quoted_base}.json")
            response_json = None

            # Try to load from cache
            if os.path.exists(search_cache_file):
                try:
                    with open(search_cache_file, 'r', encoding='utf-8') as f:
                        response_json = json.load(f)
                    if meta['debug']:
                        console.print(f"[cyan]SRRDB: Using cached search for {base}")
                except Exception:
                    response_json = None

            if response_json is None:
                url = f"https://api.srrdb.com/v1/search/r:{quoted_base}"
                if meta['debug']:
                    console.print("Using SRRDB url", url)
                try:
                    response = await client.get(url, timeout=30.0)
                    if response.status_code == 200:
                        response_json = response.json()
                        # Save to cache
                        with open(search_cache_file, 'w', encoding='utf-8') as f:
                            json.dump(response_json, f)
                except Exception as e:
                    console.print(f"[yellow]SRRDB: Search request failed: {e}")

            if response_json and int(response_json.get('resultsCount', 0)) > 0:
                first_result = response_json['results'][0]
                meta['scene_name'] = first_result['release']
                video = f"{first_result['release']}.mkv"
                scene = True
                if is_all_lowercase and not meta.get('tag'):
                    meta['we_need_tag'] = True
                if first_result.get('imdbId'):
                    imdb_str = first_result['imdbId']
                    imdb = int(imdb_str) if (imdb_str.isdigit() and not meta.get('imdb_manual')) else 0

                # NFO Download Handling
                if not meta.get('nfo') and not meta.get('emby', False):
                    if first_result.get("hasNFO") == "yes":
                        try:
                            release = first_result['release']
                            release_lower = release.lower()

                            # Details Cache
                            details_cache_file = os.path.join(details_cache_dir, f"{release}.json")
                            release_details_dict = None

                            if os.path.exists(details_cache_file):
                                try:
                                    with open(details_cache_file, 'r', encoding='utf-8') as f:
                                        release_details_dict = json.load(f)
                                except Exception:
                                    release_details_dict = None

                            if release_details_dict is None:
                                release_details_url = f"https://api.srrdb.com/v1/details/{release}"
                                release_details_response = await client.get(release_details_url, timeout=30.0)
                                if release_details_response.status_code == 200:
                                    release_details_dict = release_details_response.json()
                                    with open(details_cache_file, 'w', encoding='utf-8') as f:
                                        json.dump(release_details_dict, f)

                            if release_details_dict:
                                try:
                                    for file in release_details_dict.get('files', []):
                                        if file['name'].endswith('.nfo'):
                                            release_lower = os.path.splitext(file['name'])[0]
                                except (KeyError, ValueError):
                                    pass

                            nfo_url = f"https://www.srrdb.com/download/file/{release}/{release_lower}.nfo"
                            save_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
                            os.makedirs(save_path, exist_ok=True)
                            nfo_file_path = os.path.join(save_path, f"{release_lower}.nfo")
                            meta['scene_nfo_file'] = nfo_file_path

                            # Check if NFO already exists (Local Cache)
                            if os.path.exists(nfo_file_path):
                                meta['nfo'] = True
                                meta['auto_nfo'] = True
                            else:
                                nfo_response = await client.get(nfo_url, timeout=30.0)
                                if nfo_response.status_code == 200:
                                    with open(nfo_file_path, 'wb') as f:
                                        f.write(nfo_response.content)
                                        meta['nfo'] = True
                                        meta['auto_nfo'] = True
                                    if meta['debug']:
                                        console.print(f"[green]NFO downloaded to {nfo_file_path}")
                                else:
                                    console.print("[yellow]NFO file not available for download.")
                        except Exception as e:
                            console.print("[yellow]Failed to download NFO file:", e)
            else:
                if meta['debug'] and response_json:
                    console.print("[yellow]SRRDB: No match found")

        elif not scene and lower and not meta.get('emby_debug', False):
            release_name = None
            try:
                name = meta.get('filename', None).replace(" ", ".")
                tag = meta.get('tag', None).replace("-", "")
            except Exception:
                name = None
                tag = None
            if name and tag:
                url = f"https://api.srrdb.com/v1/search/start:{name}/group:{tag}"

                if meta['debug']:
                    console.print("Using SRRDB url", url)

                try:
                    response = await client.get(url, timeout=10.0)
                    response_json = response.json()

                    if int(response_json.get('resultsCount', 0)) > 0:
                        first_result = response_json['results'][0]
                        imdb_str = first_result.get('imdbId')
                        if imdb_str and imdb_str == str(meta.get('imdb_id')).zfill(7) and meta.get('imdb_id') != 0:
                            meta['scene'] = True
                            release_name = first_result['release']

                            if not meta.get('nfo'):
                                if first_result.get("hasNFO") == "yes":
                                    try:
                                        release = first_result['release']
                                        release_lower = release.lower()
                                        nfo_url = f"https://www.srrdb.com/download/file/{release}/{quoted_base}.nfo"
                                        save_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
                                        os.makedirs(save_path, exist_ok=True)
                                        nfo_file_path = os.path.join(save_path, f"{release_lower}.nfo")

                                        if not os.path.exists(nfo_file_path):
                                            nfo_response = await client.get(nfo_url, timeout=30.0)
                                            if nfo_response.status_code == 200:
                                                with open(nfo_file_path, 'wb') as f:
                                                    f.write(nfo_response.content)
                                                    meta['nfo'] = True
                                                    meta['auto_nfo'] = True
                                                console.print(f"[green]NFO downloaded to {nfo_file_path}")
                                        else:
                                            meta['nfo'] = True
                                            meta['auto_nfo'] = True
                                    except Exception as e:
                                        console.print("[yellow]Failed to download NFO file:", e)

                        return release_name
                    else:
                        if meta['debug']:
                            console.print("[yellow]SRRDB: No match found with lower/tag search")
                        return None

                except Exception as e:
                    console.print(f"[yellow]SRRDB search failed: {e}")
                    return None
            else:
                if meta['debug']:
                    console.print("[yellow]SRRDB: Missing name or tag for lower/tag search")
                return None

    check_predb = config['DEFAULT'].get('check_predb', False)
    if not scene and check_predb and not meta.get('emby_debug', False):
        if meta['debug']:
            console.print("[yellow]SRRDB: No scene match found, checking predb")
        scene = await predb_check(meta, video)

    if meta['debug']:
        scene_end_time = time.time()
        console.print(f"Scene data processed in {scene_end_time - scene_start_time:.2f} seconds")

    return video, scene, imdb


async def predb_check(meta, video):
    url = f"https://predb.pw/search.php?search={urllib.parse.quote(os.path.basename(video))}"
    if meta['debug']:
        console.print("Using predb url", url)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "lxml")
            found = False
            video_base = os.path.basename(video).lower()
            for row in soup.select('table.zebra-striped tbody tr'):
                tds = row.find_all('td')
                if len(tds) >= 3:
                    # The 3rd <td> contains the release name link
                    release_a = tds[2].find('a', title=True)
                    if release_a:
                        release_name = release_a['title'].strip().lower()
                        if meta['debug']:
                            console.print(f"[yellow]Predb: Checking {release_name} against {video_base}")
                        if release_name == video_base:
                            found = True
                            meta['scene_name'] = release_a['title'].strip()
                            console.print("[green]Predb: Match found")
                            # The 4th <td> contains the group
                            if len(tds) >= 4:
                                group_a = tds[3].find('a')
                                if group_a:
                                    meta['tag'] = group_a.text.strip()
                            return True
            if not found:
                console.print("[yellow]Predb: No match found")
                return False
        else:
            console.print(f"[red]Predb: Error {response.status_code} while checking")
            return False
    except httpx.RequestError as e:
        console.print(f"[red]Predb: Request failed: {e}")
        return False
