# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import re
import requests
import urllib.parse
from bs4 import BeautifulSoup
from data.config import config
from src.console import console


async def is_scene(video, meta, imdb=None, lower=False):
    scene = False
    is_all_lowercase = False
    base = os.path.basename(video)
    match = re.match(r"^(.+)\.[a-zA-Z0-9]{3}$", os.path.basename(video))

    if match and (not meta['is_disc'] or meta['keep_folder']):
        base = match.group(1)
        is_all_lowercase = base.islower()
    base = urllib.parse.quote(base)
    if 'scene' not in meta and not lower and not meta.get('emby_debug', False):
        url = f"https://api.srrdb.com/v1/search/r:{base}"
        if meta['debug']:
            console.print("Using SRRDB url", url)
        try:
            response = requests.get(url, timeout=30)
            response_json = response.json()
            if meta['debug']:
                console.print(response_json)

            if int(response_json.get('resultsCount', 0)) > 0:
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

                            release_details_url = f"https://api.srrdb.com/v1/details/{release}"
                            release_details_response = requests.get(release_details_url, timeout=30)
                            if release_details_response.status_code == 200:
                                try:
                                    release_details_dict = release_details_response.json()
                                    for file in release_details_dict['files']:
                                        if file['name'].endswith('.nfo'):
                                            release_lower = os.path.splitext(file['name'])[0]
                                except (KeyError, ValueError):
                                    pass

                            nfo_url = f"https://www.srrdb.com/download/file/{release}/{release_lower}.nfo"

                            # Define path and create directory
                            save_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
                            os.makedirs(save_path, exist_ok=True)
                            nfo_file_path = os.path.join(save_path, f"{release_lower}.nfo")
                            meta['scene_nfo_file'] = nfo_file_path

                            # Download the NFO file
                            nfo_response = requests.get(nfo_url, timeout=30)
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
                if meta['debug']:
                    console.print("[yellow]SRRDB: No match found")

        except Exception as e:
            console.print(f"[yellow]SRRDB: No match found, or request has timed out: {e}")

    elif not scene and lower and not meta.get('emby_debug', False):
        release_name = None
        name = meta.get('filename', None).replace(" ", ".")
        tag = meta.get('tag', None).replace("-", "")
        url = f"https://api.srrdb.com/v1/search/start:{name}/group:{tag}"
        if meta['debug']:
            console.print("Using SRRDB url", url)

        try:
            response = requests.get(url, timeout=10)
            response_json = response.json()

            if int(response_json.get('resultsCount', 0)) > 0:
                first_result = response_json['results'][0]
                imdb_str = first_result['imdbId']
                if imdb_str and imdb_str == str(meta.get('imdb_id')).zfill(7) and meta.get('imdb_id') != 0:
                    meta['scene'] = True
                    release_name = first_result['release']

                    # NFO Download Handling
                    if not meta.get('nfo'):
                        if first_result.get("hasNFO") == "yes":
                            try:
                                release = first_result['release']
                                release_lower = release.lower()
                                nfo_url = f"https://www.srrdb.com/download/file/{release}/{base}.nfo"

                                # Define path and create directory
                                save_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
                                os.makedirs(save_path, exist_ok=True)
                                nfo_file_path = os.path.join(save_path, f"{release_lower}.nfo")

                                # Download the NFO file
                                nfo_response = requests.get(nfo_url, timeout=30)
                                if nfo_response.status_code == 200:
                                    with open(nfo_file_path, 'wb') as f:
                                        f.write(nfo_response.content)
                                        meta['nfo'] = True
                                        meta['auto_nfo'] = True
                                    console.print(f"[green]NFO downloaded to {nfo_file_path}")
                                else:
                                    console.print("[yellow]NFO file not available for download.")
                            except Exception as e:
                                console.print("[yellow]Failed to download NFO file:", e)

                return release_name

        except Exception as e:
            console.print(f"[yellow]SRRDB search failed: {e}")
            return None

    check_predb = config['DEFAULT'].get('check_predb', False)
    if not scene and check_predb and not meta.get('emby_debug', False):
        if meta['debug']:
            console.print("[yellow]SRRDB: No scene match found, checking predb")
        scene = await predb_check(meta, video)

    return video, scene, imdb


async def predb_check(meta, video):
    url = f"https://predb.pw/search.php?search={urllib.parse.quote(os.path.basename(video))}"
    if meta['debug']:
        console.print("Using predb url", url)
    try:
        response = requests.get(url, timeout=10)
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
    except requests.RequestException as e:
        console.print(f"[red]Predb: Request failed: {e}")
        return False
