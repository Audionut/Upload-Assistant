import os
import re
import urllib.parse
import requests
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
    if 'scene' not in meta and not lower:
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
                    imdb = int(imdb_str) if imdb_str.isdigit() else 0

                # NFO Download Handling
                if not meta.get('nfo') and not meta.get('emby', False):
                    if first_result.get("hasNFO") == "yes":
                        try:
                            release = first_result['release']
                            release_lower = release.lower()
                            nfo_url = f"https://www.srrdb.com/download/file/{release}/{release_lower}.nfo"

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

    elif not scene and lower:
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

    return video, scene, imdb
