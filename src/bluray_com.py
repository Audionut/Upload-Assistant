# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import httpx
import random
import asyncio
import re
import json
import cli_ui
import os
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()


async def search_bluray(meta):
    imdb_id = f"tt{meta['imdb_id']:07d}"
    url = f"https://www.blu-ray.com/search/?quicksearch=1&quicksearch_country=all&quicksearch_keyword={imdb_id}&section=theatrical"
    debug_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/debug_bluray_search_{imdb_id}.html"

    try:
        if os.path.exists(debug_filename):
            if meta['debug']:
                console.print(f"[green]Found existing file for {imdb_id}[/green]")
            with open(debug_filename, "r", encoding="utf-8") as f:
                response_text = f.read()

            if response_text and "No index" not in response_text:
                return response_text
            else:
                console.print("[yellow]Cached file exists but appears to be invalid, will fetch fresh data[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Error reading cached file: {str(e)}[/yellow]")

    # If we're here, we need to make a request
    if meta['debug']:
        console.print(f"[dim]Search URL: {url}[/dim]")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.blu-ray.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    }

    max_retries = 2
    retry_count = 0
    backoff_time = 3.0
    response_text = None

    while retry_count <= max_retries:
        try:
            delay = random.uniform(1, 3)
            if meta['debug']:
                console.print(f"[dim]Waiting {delay:.2f} seconds before request (attempt {retry_count + 1}/{max_retries + 1})...[/dim]")
            await asyncio.sleep(delay)

            if meta['debug']:
                console.print(f"[yellow]Sending request to blu-ray.com (attempt {retry_count + 1}/{max_retries + 1})...[/yellow]")
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200 and "No index" not in response.text:
                    response_text = response.text

                    try:
                        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/debug_bluray_search_{imdb_id}.html", "w", encoding="utf-8") as f:
                            f.write(response_text)
                        if meta['debug']:
                            console.print(f"[dim]Saved search response to debug_bluray_search_{imdb_id}.html[/dim]")
                    except Exception as e:
                        console.print(f"[dim]Could not save debug file: {str(e)}[/dim]")

                    break

                elif "No index" in response.text:
                    console.print(f"[red]Blocked by blu-ray.com (Anti-scraping protection) (attempt {retry_count + 1}/{max_retries + 1})[/red]")
                    console.print(f"[dim]Response preview: {response.text[:150]}...[/dim]")

                    # use less retries for blocked requests since it's probably just borked
                    if retry_count < 2:
                        backoff_time *= 2
                        console.print(f"[yellow]Retrying in {backoff_time:.1f} seconds...[/yellow]")
                        await asyncio.sleep(backoff_time)
                        retry_count += 1
                    else:
                        console.print("[red]Maximum retries reached, giving up on search[/red]")
                        break
                else:
                    console.print(f"[red]Failed with status code: {response.status_code} (attempt {retry_count + 1}/{max_retries + 1})[/red]")

                    if retry_count < max_retries:
                        backoff_time *= 2
                        if meta['debug']:
                            console.print(f"[yellow]Retrying in {backoff_time:.1f} seconds...[/yellow]")
                        await asyncio.sleep(backoff_time)
                        retry_count += 1
                    else:
                        console.print("[red]Maximum retries reached, giving up on search[/red]")
                        break

        except httpx.RequestError as e:
            console.print(f"[red]HTTP request error when accessing {url} (attempt {retry_count + 1}/{max_retries + 1}): {str(e)}[/red]")
            if retry_count < max_retries:
                backoff_time *= 2
                if meta['debug']:
                    console.print(f"[yellow]Retrying in {backoff_time:.1f} seconds...[/yellow]")
                await asyncio.sleep(backoff_time)
                retry_count += 1
            else:
                console.print("[red]Maximum retries reached, giving up on search[/red]")
                break

    if not response_text:
        console.print("[red]Failed to retrieve search results after all attempts[/red]")
        return None

    return response_text


def extract_bluray_links(html_content):
    if not html_content:
        console.print("[red]No HTML content to extract links from[/red]")
        return None

    results = []

    try:
        soup = BeautifulSoup(html_content, 'lxml')
        movie_divs = soup.select('div.figure')
        if not movie_divs:
            return None

        for i, movie_div in enumerate(movie_divs, 1):
            link = movie_div.find('a', class_='alphaborder')

            if link and 'href' in link.attrs:
                movie_url = link['href']
                releases_url = f"{movie_url}#Releases"
                title_div = movie_div.select_one('div.figurecaptionbottom div[style*="font-weight: bold"]')
                year_div = movie_div.select_one('div.figurecaptionbottom div[style*="margin-top"]')

                title = title_div.text.strip() if title_div else "Unknown Title"
                year = year_div.text.strip() if year_div else "Unknown Year"

                console.print(f"[green]Found movie: {title} ({year})[/green]")
                console.print(f"[dim]URL: {releases_url}[/dim]")

                results.append({
                    'title': title,
                    'year': year,
                    'releases_url': releases_url
                })
            else:
                console.print("[red]Movie div doesn't have a valid link[/red]")

        return results

    except Exception as e:
        console.print(f"[red]Error parsing HTML: {str(e)}[/red]")
        console.print_exception()
        return None


async def extract_bluray_release_info(html_content, meta):
    if not html_content:
        console.print("[red]No HTML content to extract release info from[/red]")
        return []

    matching_releases = []
    is_3d = meta.get('3D', '') == 'yes'
    resolution = meta.get('resolution', '').lower()
    is_4k = '2160p' in resolution or '4k' in resolution
    is_dvd = meta['is_disc'] == "DVD"
    release_type = "4K" if is_4k else "3D" if is_3d else "DVD" if is_dvd else "BD"

    if is_3d:
        console.print("[blue]Looking for 3D Blu-ray releases[/blue]")
    elif is_4k:
        console.print("[blue]Looking for 4K/UHD Blu-ray releases[/blue]")
    elif is_dvd:
        console.print("[blue]Looking for DVD releases[/blue]")
    else:
        console.print("[blue]Looking for standard Blu-ray releases[/blue]")

    try:
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/debug_bluray_{release_type}.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        if meta['debug']:
            console.print(f"[dim]Saved releases response to debug_bluray_{release_type}.html[/dim]")
    except Exception as e:
        console.print(f"[dim]Could not save debug file: {str(e)}[/dim]")

    try:
        dvd_sections = None
        soup = BeautifulSoup(html_content, 'lxml')
        if is_dvd:
            dvd_sections = soup.find_all('h3', string=lambda s: s and ('DVD Editions' in s))
            selected_sections = dvd_sections
        else:
            bluray_sections = soup.find_all('h3', string=lambda s: s and ('Blu-ray Editions' in s or '4K Blu-ray Editions' in s or '3D Blu-ray Editions' in s))
            selected_sections = bluray_sections

        if meta['debug']:
            release_type_debug = "DVD" if is_dvd else "Blu-ray"
            console.print(f"[blue]Found {len(selected_sections)} {release_type_debug} section(s)[/blue]")
        filtered_sections = []
        for section in selected_sections:
            section_title = section.text

            # Check if this section matches what we're looking for
            if is_3d and '3D Blu-ray Editions' in section_title:
                filtered_sections.append(section)
                if meta['debug']:
                    console.print(f"[green]Including 3D section: {section_title}[/green]")
            elif is_4k and '4K Blu-ray Editions' in section_title:
                filtered_sections.append(section)
                if meta['debug']:
                    console.print(f"[green]Including 4K section: {section_title}[/green]")
            elif is_dvd and 'DVD Editions' in section_title:
                filtered_sections.append(section)
                if meta['debug']:
                    console.print(f"[green]Including DVD section: {section_title}[/green]")
            elif not is_3d and not is_4k and 'Blu-ray Editions' in section_title and '3D Blu-ray Editions' not in section_title and '4K Blu-ray Editions' not in section_title:
                filtered_sections.append(section)
                if meta['debug']:
                    console.print(f"[green]Including standard Blu-ray section: {section_title}[/green]")

        # If no sections match our filter criteria, use all sections
        if not filtered_sections:
            console.print("[yellow]No sections match exact media type, using all available sections[/yellow]")
            filtered_sections = selected_sections

        for section_idx, section in enumerate(filtered_sections, 1):
            parent_tr = section.find_parent('tr')
            if not parent_tr:
                console.print(f"[red]Could not find parent tr for {release_type_debug} section[/red]")
                continue

            release_links = []
            current = section.find_next()
            while current and (not current.name == 'h3'):
                if current.name == 'a' and current.has_attr('href') and ('blu-ray.com/movies/' in current['href'] or 'blu-ray.com/dvd/' in current['href']):
                    release_links.append(current)
                current = current.find_next()

            for link_idx, link in enumerate(release_links, 1):
                try:
                    release_url = link['href']
                    title = link.get('title', link.text.strip())
                    country_flag = link.find_previous('img', width='18', height='12')
                    country = country_flag.get('title', 'Unknown') if country_flag else 'Unknown'
                    price_tag = link.find_next('small', style=lambda s: s and 'color: green' in s)
                    price = price_tag.text.strip() if price_tag else "Unknown"
                    publisher_tag = link.find_next('small', style=lambda s: s and 'color: #999999' in s)
                    publisher = publisher_tag.text.strip() if publisher_tag else "Unknown"

                    release_id_match = re.search(r'blu-ray\.com/(movies|dvd)/.*?/(\d+)/', release_url)
                    if release_id_match:
                        release_id = release_id_match.group(1)
                        if meta['debug']:
                            console.print(f"[green]Found release ID: {release_id}[/green]")

                        matching_releases.append({
                            'title': title,
                            'url': release_url,
                            'price': price,
                            'publisher': publisher,
                            'country': country,
                            'release_id': release_id
                        })
                    else:
                        console.print(f"[red]Could not extract release ID from URL: {release_url}[/red]")

                except Exception as e:
                    console.print(f"[red]Error processing release: {str(e)}[/red]")
                    console.print_exception()

        console.print(f"[green]Found {len(matching_releases)} potential matching releases[/green]")
        return matching_releases

    except Exception as e:
        console.print(f"[red]Error parsing Blu-ray release HTML: {str(e)}[/red]")
        console.print_exception()
        return []


async def extract_product_id(url, meta):
    pattern = r'blu-ray\.com/.*?/(\d+)/'
    match = re.search(pattern, url)

    if match:
        product_id = match.group(1)
        if meta['debug']:
            console.print(f"[green]Successfully extracted product ID: {product_id}[/green]")
        return product_id

    console.print(f"[red]Could not extract product ID from URL: {url}[/red]")
    return None


async def get_bluray_releases(meta):
    console.print("[blue]===== Starting blu-ray.com release search =====[/blue]")
    console.print(f"[blue]Movie: {meta.get('filename', 'Unknown')}, IMDB ID: tt{meta.get('imdb_id', '0000000'):07d}[/blue]")

    html_content = await search_bluray(meta)

    if not html_content:
        console.print("[red]Failed to get search results from blu-ray.com[/red]")
        return []

    movie_links = extract_bluray_links(html_content)

    if not movie_links:
        if meta['debug']:
            console.print(f"[red]No movies found for IMDB ID: tt{meta['imdb_id']:07d}[/red]")
        return []

    matching_releases = []

    for idx, movie in enumerate(movie_links, 1):
        if meta['debug']:
            console.print(f"[blue]Processing movie {idx}/{len(movie_links)}: {movie['title']} ({movie['year']})[/blue]")
        releases_url = movie['releases_url']
        product_id = await extract_product_id(releases_url, meta)
        if not product_id:
            console.print(f"[red]Could not extract product ID from {releases_url}[/red]")
            continue

        ajax_url = f"https://www.blu-ray.com/products/menu_ajax.php?p={product_id}&c=20&action=showreleasesall"
        console.print(f"[dim]Releases URL: {ajax_url}[/dim]")

        is_3d = meta.get('3D', '') == 'yes'
        resolution = meta.get('resolution', '').lower()
        is_4k = '2160p' in resolution or '4k' in resolution
        release_type = "4K" if is_4k else "3D" if is_3d else "BD"
        release_debug_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/debug_bluray_{release_type}.html"

        try:
            if os.path.exists(release_debug_filename):
                if meta['debug']:
                    console.print(f"[green]Found existing release data for product ID {product_id}[/green]")
                with open(release_debug_filename, "r", encoding="utf-8") as f:
                    response_text = f.read()

                if response_text and "No index" not in response_text:
                    movie_releases = await extract_bluray_release_info(response_text, meta)

                    for release in movie_releases:
                        release['movie_title'] = movie['title']
                        release['movie_year'] = movie['year']

                    matching_releases.extend(movie_releases)
                    continue
                else:
                    console.print("[yellow]Cached file exists but appears to be invalid, will fetch fresh data[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Error reading cached file: {str(e)}[/yellow]")

        # If we're here, we need to make a request
        delay = random.uniform(2, 4)
        if meta['debug']:
            console.print(f"[dim]Waiting {delay:.2f} seconds before request...[/dim]")
        await asyncio.sleep(delay)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": releases_url,
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            max_retries = 2
            retry_count = 0
            backoff_time = 3.0

            while retry_count <= max_retries:
                try:
                    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                        response = await client.get(ajax_url, headers=headers)

                        if response.status_code == 200 and "No index" not in response.text:
                            movie_releases = await extract_bluray_release_info(response.text, meta)

                            for release in movie_releases:
                                release['movie_title'] = movie['title']
                                release['movie_year'] = movie['year']

                            console.print(f"[green]Found {len(movie_releases)} matching releases for this movie[/green]")
                            matching_releases.extend(movie_releases)
                            break
                        elif "No index" in response.text:
                            console.print(f"[red]Blocked by blu-ray.com when accessing {ajax_url} (attempt {retry_count + 1}/{max_retries + 1})[/red]")
                            if retry_count < max_retries:
                                backoff_time *= 2
                                console.print(f"[yellow]Retrying in {backoff_time:.1f} seconds...[/yellow]")
                                await asyncio.sleep(backoff_time)
                                retry_count += 1
                            else:
                                console.print("[red]Maximum retries reached, giving up on this URL[/red]")
                                break
                        else:
                            console.print(f"[red]Failed to get release information from {ajax_url}, status code: {response.status_code} (attempt {retry_count + 1}/{max_retries + 1})[/red]")
                            if retry_count < max_retries:
                                backoff_time *= 2
                                console.print(f"[yellow]Retrying in {backoff_time:.1f} seconds...[/yellow]")
                                await asyncio.sleep(backoff_time)
                                retry_count += 1
                            else:
                                console.print("[red]Maximum retries reached, giving up on this URL[/red]")
                                break

                except httpx.RequestError as e:
                    console.print(f"[red]HTTP request error when accessing {ajax_url} (attempt {retry_count + 1}/{max_retries + 1}): {str(e)}[/red]")
                    if retry_count < max_retries:
                        backoff_time *= 2
                        console.print(f"[yellow]Retrying in {backoff_time:.1f} seconds...[/yellow]")
                        await asyncio.sleep(backoff_time)
                        retry_count += 1
                    else:
                        console.print("[red]Maximum retries reached, giving up on this URL[/red]")
                        break

        except Exception as e:
            console.print(f"[red]Error fetching release details from {ajax_url}: {str(e)}[/red]")
            console.print_exception()

    console.print("[yellow]===== BluRay.com search results summary =====[/yellow]")

    if matching_releases:
        if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
            for idx, release in enumerate(matching_releases, 1):
                console.print(f"[green]{idx}. {release['movie_title']} ({release['movie_year']}):[/green]")
                console.print(f"   [blue]Title: {release['title']}[/blue]")
                console.print(f"   [blue]Country: {release['country']}[/blue]")
                console.print(f"   [blue]Publisher: {release['publisher']}[/blue]")
                console.print(f"   [blue]Price: {release['price']}[/blue]")
                console.print(f"   [dim]URL: {release['url']}[/dim]")

            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                console.print()
                console.print("[green]Release Selection")
                console.print("[green]=======================================")
                console.print("[dim]Please select a release to use for region and distributor information:")
                console.print("[dim]Enter release number, 'a' for all releases, or 'n' to skip")
                console.print("[dim]Selecting all releases will search every release for more information...")
                console.print("[dim]More releases will require more time to process")
            else:
                console.print("[yellow]Unattended mode - selecting all releases")

            while True:
                try:
                    selection = input(f"Selection (1-{len(matching_releases)}/a/n): ").strip().lower()
                    if selection == 'a':
                        cli_ui.info("All releases selected")
                        detailed_releases = await process_all_releases(matching_releases, meta)
                        return detailed_releases
                    elif selection == 'n':
                        cli_ui.info("Skipped - not using Blu-ray.com information")
                        return []
                    else:
                        try:
                            selected_idx = int(selection)

                            if 1 <= selected_idx <= len(matching_releases):
                                selected_release = matching_releases[selected_idx - 1]
                                cli_ui.info(f"Selected: {selected_release['title']} - {selected_release['country']} - {selected_release['publisher']}")
                                region_code = map_country_to_region_code(selected_release['country'])
                                meta['region'] = region_code
                                meta['distributor'] = selected_release['publisher'].upper()
                                meta['release_url'] = selected_release['url']
                                cli_ui.info(f"Set region code to: {region_code}, distributor to: {selected_release['publisher'].upper()}")

                                if meta.get('use_bluray_images', False):
                                    console.print("[yellow]Fetching release details to get cover images...[/yellow]")
                                    selected_release = await fetch_release_details(selected_release, meta)

                                    if 'cover_images' in selected_release and selected_release['cover_images']:
                                        meta['cover_images'] = selected_release['cover_images']
                                        await download_cover_images(meta)

                                return [selected_release]
                            else:
                                cli_ui.warning(f"Invalid selection: {selected_idx}. Must be between 1 and {len(matching_releases)}")
                        except ValueError:
                            cli_ui.warning(f"Invalid input: '{selection}'. Please enter a number, 'a', or 'n'")

                except (KeyboardInterrupt, EOFError):
                    raise SystemExit("Selection cancelled by user")
        else:
            console.print("[yellow]Unattended mode - selecting all releases")
            detailed_releases = await process_all_releases(matching_releases, meta)
            return detailed_releases

    imdb_id = meta.get('imdb_id', '0000000')
    release_count = len(matching_releases)
    debug_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/bluray_results_tt{imdb_id}_{release_count}releases.json"

    # always save a file in case the existing results are invalid
    try:
        with open(debug_filename, "w", encoding="utf-8") as f:
            json.dump({
                "movie": {
                    "title": meta.get("title", "Unknown"),
                    "imdb_id": f"tt{meta.get('imdb_id', '0000000'):07d}"
                },
                "matching_releases": matching_releases
            }, f, indent=2)
        if meta['debug']:
            console.print(f"[dim]Saved results to {debug_filename}[/dim]")
    except Exception as e:
        console.print(f"[dim]Could not save debug results: {str(e)}[/dim]")

    return matching_releases


async def parse_release_details(response_text, release, meta):
    try:
        soup = BeautifulSoup(response_text, 'lxml')
        specs_td = soup.find('td', width="228px", style=lambda s: s and 'font-size: 12px' in s)

        if not specs_td:
            console.print("[red]Could not find specs section on the release page[/red]")
            return release

        specs = {
            'video': {},
            'audio': [],
            'subtitles': [],
            'discs': {},
            'playback': {},
        }

        # Parse video section
        video_section = extract_section(specs_td, 'Video')
        if video_section:
            codec_match = re.search(r'Codec: ([^<\n]+)', video_section)
            if codec_match:
                specs['video']['codec'] = codec_match.group(1).strip()
                if meta['debug']:
                    console.print(f"[blue]Video Codec: {specs['video']['codec']}[/blue]")

            resolution_match = re.search(r'Resolution: ([^<\n]+)', video_section)
            if resolution_match:
                specs['video']['resolution'] = resolution_match.group(1).strip()
                if meta['debug']:
                    console.print(f"[blue]Resolution: {specs['video']['resolution']}[/blue]")

        # Parse audio section
        audio_section = extract_section(specs_td, 'Audio')
        if audio_section:
            audio_div = specs_td.find('div', id='longaudio')
            if not audio_div:
                audio_div = specs_td.find('div', id='shortaudio')
                if meta['debug']:
                    console.print("[dim]Using shortaudio because longaudio wasn't found[/dim]")
            if audio_div:
                audio_html = str(audio_div)
                audio_html = re.sub(r'<br\s*/?>', '\n', audio_html)
                audio_soup = BeautifulSoup(audio_html, 'lxml')
                raw_text = audio_soup.get_text()
                raw_lines = [line.strip() for line in raw_text.split('\n') if line.strip() and 'less' not in line]

                audio_lines = []
                i = 0
                while i < len(raw_lines):
                    current_line = raw_lines[i]
                    is_atmos = 'atmos' in current_line.lower()

                    # If it's an Atmos track and there's a next line with the same language, combine them
                    if is_atmos and i + 1 < len(raw_lines):
                        next_line = raw_lines[i + 1]
                        current_lang = current_line.split(':', 1)[0].strip() if ':' in current_line else ''
                        next_lang = next_line.split(':', 1)[0].strip() if ':' in next_line else ''

                        if current_lang and current_lang == next_lang:
                            # This is likely an Atmos track followed by its core track
                            # Combine them into a single entry
                            if 'Dolby Atmos' in current_line and ('Dolby Digital' in next_line or 'Dolby TrueHD' in next_line):
                                channel_info = ""
                                if '7.1' in next_line:
                                    channel_info = "7.1"
                                elif '5.1' in next_line:
                                    channel_info = "5.1"
                                if 'TrueHD' in next_line:
                                    combined_track = f"{current_lang}: Dolby TrueHD Atmos {channel_info}"
                                else:
                                    combined_track = f"{current_lang}: Dolby Atmos {channel_info}"

                                audio_lines.append(combined_track)
                                i += 2
                                continue

                    if current_line.startswith("Note:"):
                        # This is a note for the previous track
                        if audio_lines:
                            audio_lines[-1] = f"{audio_lines[-1]} - {current_line}"
                    else:
                        # This is a new track
                        audio_lines.append(current_line)

                    i += 1

                specs['audio'] = audio_lines
                if meta['debug']:
                    console.print(f"[blue]Audio Tracks: {len(audio_lines)} found[/blue]")
                    for track in audio_lines:
                        console.print(f"[dim]  - {track}[/dim]")

        # Parse subtitle section
        subtitle_section = extract_section(specs_td, 'Subtitles')
        if subtitle_section:
            subs_div = specs_td.find('div', id='longsubs')
            if not subs_div:
                subs_div = specs_td.find('div', id='shortsubs')
                if meta['debug']:
                    console.print("[dim]Using shortsubs because longsubs wasn't found[/dim]")
            if subs_div:
                subtitle_text = subs_div.get_text().strip()
                subtitle_text = re.sub(r'\s*\(less\)\s*', '', subtitle_text)
                subtitles = [s.strip() for s in re.split(r',|\n', subtitle_text) if s.strip()]
                specs['subtitles'] = subtitles
                if meta['debug']:
                    console.print(f"[blue]Subtitles: {', '.join(subtitles)}[/blue]")

        # Parse disc section
        disc_section = extract_section(specs_td, 'Discs')
        if disc_section:
            disc_type_match = re.search(r'(Blu-ray Disc|DVD|Ultra HD Blu-ray|4K Ultra HD)', disc_section)
            if disc_type_match:
                specs['discs']['type'] = disc_type_match.group(1).strip()
                if meta['debug']:
                    console.print(f"[blue]Disc Type: {specs['discs']['type']}[/blue]")

            disc_count_match = re.search(r'Single disc \(1 ([^)]+)\)|(One|Two|Three|Four|Five|\d+)[ -]disc set(?:\s*\(([^)]+)\))?', disc_section)
            if meta['debug']:
                console.print(f"[dim]Disc Count Match: {disc_count_match}[/dim]")
            if disc_count_match:
                if disc_count_match.group(1):
                    specs['discs']['count'] = 1
                    specs['discs']['format'] = disc_count_match.group(1).strip()
                else:
                    disc_count = disc_count_match.group(2)
                    if disc_count.isdigit():
                        specs['discs']['count'] = int(disc_count)
                    else:
                        number_map = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
                        specs['discs']['count'] = number_map.get(disc_count, 1)

                    if disc_count_match.group(3):
                        bd_format_match = re.search(r'(\d+\s*BD-\d+|\d+\s*BD)', disc_count_match.group(3))
                        if meta['debug']:
                            console.print(f"[dim]BD Format Match: {bd_format_match}[/dim]")
                        if bd_format_match:
                            specs['discs']['format'] = bd_format_match.group(1).strip()
                        else:
                            bd_match = re.search(r'(\d+\s*BD-\d+)', disc_count_match.group(3))
                            if bd_match:
                                specs['discs']['format'] = bd_match.group(1).strip()
                            else:
                                specs['discs']['format'] = "multiple discs"
                    else:
                        specs['discs']['format'] = "multiple discs"

        # Parse playback section
        playback_section = extract_section(specs_td, 'Playback')
        if playback_section:
            region_match = re.search(r'(?:2K Blu-ray|4K Blu-ray|DVD): Region ([A-C])(?: \(([^)]+)\))?', playback_section)
            if region_match:
                specs['playback']['region'] = region_match.group(1).strip()
                specs['playback']['region_notes'] = region_match.group(2).strip() if region_match.group(2) else ""
                if meta['debug']:
                    console.print(f"[blue]Region: {specs['playback']['region']}[/blue]")
                if specs['playback']['region_notes']:
                    if meta['debug']:
                        console.print(f"[dim]Region Notes: {specs['playback']['region_notes']}[/dim]")

        if meta.get('use_bluray_images', False):
            cover_images = extract_cover_images(response_text)
            if cover_images:
                release['cover_images'] = cover_images
                if meta['debug']:
                    console.print(f"[green]Found {len(cover_images)} cover images:[/green]")
                    for img_type, url in cover_images.items():
                        console.print(f"[dim]  - {img_type}: {url}[/dim]")

        release['specs'] = specs
        if meta['debug']:
            console.print(f"[green]Successfully parsed details for {release['title']}[/green]")
        return release

    except Exception as e:
        console.print(f"[red]Error parsing release details: {str(e)}[/red]")
        console.print_exception()
        return release


async def download_cover_images(meta):
    if 'cover_images' not in meta or not meta['cover_images']:
        console.print("[yellow]No cover images to download[/yellow]")
        return False

    temp_dir = f"{meta['base_dir']}/tmp/{meta['uuid']}"
    os.makedirs(temp_dir, exist_ok=True)

    reuploaded_images_path = os.path.join(meta['base_dir'], "tmp", meta['uuid'], "covers.json")
    if os.path.exists(reuploaded_images_path):
        try:
            with open(reuploaded_images_path, 'r', encoding='utf-8') as f:
                existing_covers = json.load(f)

            matching_release = False
            if isinstance(existing_covers, list) and len(existing_covers) > 0:
                for cover in existing_covers:
                    if cover.get('release_url') == meta.get('release_url'):
                        if meta['debug']:
                            console.print(f"[green]Found existing cover images for this release URL: {meta.get('release_url')}[/green]")
                        matching_release = True
                        return True

            if not matching_release:
                if meta['debug']:
                    console.print(f"[yellow]Existing covers.json found but none match current release URL: {meta.get('release_url')}[/yellow]")
                    console.print("[yellow]Deleting outdated covers.json file[/yellow]")
                os.remove(reuploaded_images_path)

        except Exception as e:
            console.print(f"[red]Error reading covers.json: {str(e)}[/red]")
            try:
                os.remove(reuploaded_images_path)
                if meta['debug']:
                    console.print("[yellow]Deleted potentially corrupted covers.json file[/yellow]")
            except Exception as delete_error:
                console.print(f"[red]Failed to delete corrupted covers.json: {str(delete_error)}[/red]")

    downloaded_images = {}
    console.print("[blue]Downloading cover images...[/blue]")

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for img_type, url in meta['cover_images'].items():
            file_ext = os.path.splitext(url)[1]
            local_filename = f"{temp_dir}/cover_{img_type}{file_ext}"

            try:
                console.print(f"[dim]Downloading {img_type} cover from {url}[/dim]")
                response = await client.get(url)

                if response.status_code == 200:
                    with open(local_filename, "wb") as f:
                        f.write(response.content)
                    downloaded_images[img_type] = local_filename
                    console.print(f"[green]✓[/green] Downloaded {img_type} cover to {local_filename}")
                else:
                    console.print(f"[red]Failed to download {img_type} cover: HTTP {response.status_code}[/red]")
            except Exception as e:
                console.print(f"[red]Error downloading {img_type} cover: {str(e)}[/red]")

    if downloaded_images:
        meta['downloaded_cover_images'] = downloaded_images
        console.print(f"[green]Successfully downloaded {len(downloaded_images)} cover images[/green]")
        return True
    else:
        console.print("[yellow]No cover images were downloaded[/yellow]")
        return False


def extract_cover_images(html_content):
    cover_images = {}
    soup = BeautifulSoup(html_content, 'lxml')
    scripts = soup.find_all('script', string=lambda s: s and "$(document).ready" in s and "append('<img id=" in s)

    for script in scripts:
        script_text = script.string
        img_id_match = re.search(r"'<img id=\"(\w+)\"", script_text)
        url_match = re.search(r"src=\"([^\"]+)\"", script_text)

        if img_id_match and url_match:
            img_id = img_id_match.group(1)
            url = url_match.group(1)
            url = clean_image_url(url)

            if "front" in img_id.lower():
                cover_images["front"] = url
            elif "back" in img_id.lower():
                cover_images["back"] = url
            elif "slip" in img_id.lower():
                cover_images["slip"] = url
            else:
                cover_images[img_id] = url

    if not cover_images:
        overlay_divs = soup.find_all('div', class_='simple_overlay')
        for div in overlay_divs:
            img = div.find('img')
            if img and 'id' in img.attrs and 'src' in img.attrs:
                img_id = img['id']
                url = img['src']

                if "front" in img_id.lower():
                    cover_images["front"] = url
                elif "back" in img_id.lower():
                    cover_images["back"] = url
                elif "slip" in img_id.lower():
                    cover_images["slip"] = url
                else:
                    cover_images[img_id] = url

    return cover_images


def clean_image_url(url):
    if not url:
        return url

    extensions = ['.jpg', '.png', '.gif', '.jpeg', '.webp']
    end_pos = None

    for ext in extensions:
        pos = url.lower().find(ext)
        if pos > 0:
            end_pos = pos + len(ext)
            break

    if end_pos:
        return url[:end_pos]
    return url


async def fetch_release_details(release, meta):
    release_url = release['url']
    release_id = release.get('release_id', '0000000')
    debug_filename = f"{meta['base_dir']}/tmp/{meta['uuid']}/debug_release_{release_id}.html"
    if meta['debug']:
        console.print(f"[yellow]Fetching details for: {release['title']} - {release_url}[/yellow]")

    try:
        import os
        if os.path.exists(debug_filename):
            if meta['debug']:
                console.print(f"[green]Found existing debug file for release ID {release_id}[/green]")
            with open(debug_filename, "r", encoding="utf-8") as f:
                response_text = f.read()

            if response_text and "No index" not in response_text:
                return await parse_release_details(response_text, release, meta)
            else:
                console.print("[yellow]Cached file exists but appears to be invalid, will fetch fresh data[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Error reading cached file: {str(e)}[/yellow]")

    # If we're here, we need to make a request
    delay = random.uniform(2, 4)
    if meta['debug']:
        console.print(f"[dim]Waiting {delay:.2f} seconds before request...[/dim]")
    await asyncio.sleep(delay)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.blu-ray.com/movies/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin"
    }

    max_retries = 2
    retry_count = 0
    backoff_time = 3.0
    response_text = None

    while retry_count <= max_retries:
        try:
            if meta['debug']:
                console.print(f"[yellow]Sending request to {release_url} (attempt {retry_count + 1}/{max_retries + 1})...[/yellow]")

            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(release_url, headers=headers)

                if response.status_code == 200 and "No index" not in response.text:
                    response_text = response.text

                    try:
                        release_id = release.get('release_id', '0000000')
                        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/debug_release_{release_id}.html", "w", encoding="utf-8") as f:
                            f.write(response_text)
                        if meta['debug']:
                            console.print(f"[dim]Saved release page to debug_release_{release_id}.html[/dim]")
                    except Exception as e:
                        console.print(f"[dim]Could not save debug file: {str(e)}[/dim]")

                    break

                elif "No index" in response.text:
                    console.print(f"[red]Blocked by blu-ray.com when accessing {release_url} (attempt {retry_count + 1}/{max_retries + 1})[/red]")
                    if retry_count < 2:
                        backoff_time *= 2
                        console.print(f"[yellow]Retrying in {backoff_time:.1f} seconds...[/yellow]")
                        await asyncio.sleep(backoff_time)
                        retry_count += 1
                    else:
                        console.print("[red]Maximum retries reached, giving up on this release[/red]")
                        break
                else:
                    console.print(f"[red]Failed to get release details, status code: {response.status_code} (attempt {retry_count + 1}/{max_retries + 1})[/red]")
                    if retry_count < max_retries:
                        backoff_time *= 2
                        console.print(f"[yellow]Retrying in {backoff_time:.1f} seconds...[/yellow]")
                        await asyncio.sleep(backoff_time)
                        retry_count += 1
                    else:
                        console.print("[red]Maximum retries reached, giving up on this release[/red]")
                        break

        except httpx.RequestError as e:
            console.print(f"[red]HTTP request error when accessing {release_url} (attempt {retry_count + 1}/{max_retries + 1}): {str(e)}[/red]")
            if retry_count < max_retries:
                backoff_time *= 2
                console.print(f"[yellow]Retrying in {backoff_time:.1f} seconds...[/yellow]")
                await asyncio.sleep(backoff_time)
                retry_count += 1
            else:
                console.print("[red]Maximum retries reached, giving up on this release[/red]")
                break

    if not response_text:
        console.print("[red]Failed to retrieve release details after all attempts[/red]")
        return release
    else:
        release = await parse_release_details(response_text, release, meta)
        return release


def extract_section(specs_td, section_title):
    section_span = specs_td.find('span', class_='subheading', string=section_title)
    if not section_span:
        return None

    section_content = []
    current_element = section_span.next_sibling

    while current_element:
        if current_element.name == 'span' and 'subheading' in current_element.get('class', []):
            break

        if isinstance(current_element, str):
            section_content.append(current_element)
        elif current_element.name:
            section_content.append(current_element.get_text())

        current_element = current_element.next_sibling

    return ''.join(section_content)


async def process_all_releases(releases, meta):
    if not releases:
        return []

    if meta['debug']:
        console.print()
        console.print("Processing Local Details")
        console.print("----------------------------")

    disc_count = len(meta.get('discs', []))
    if meta['debug']:
        console.print(f"[dim]Local disc count from meta: {disc_count}")

    meta_video_specs = {}
    meta_audio_specs = []
    meta_subtitles = []

    if disc_count > 0 and 'discs' in meta and 'bdinfo' in meta['discs'][0]:
        bdinfo = meta['discs'][0]['bdinfo']

        if 'video' in bdinfo and bdinfo['video']:
            meta_video_specs = bdinfo['video'][0]
            codec = meta_video_specs.get('codec', '')
            resolution = meta_video_specs.get('res', '')
            if meta['debug']:
                console.print(f"[dim]Local video: {codec} {resolution}")

        if 'audio' in bdinfo and bdinfo['audio']:
            meta_audio_specs = bdinfo['audio']
            for track in meta_audio_specs:
                if meta['debug']:
                    console.print(f"[dim]Local audio: {track.get('language', '')} {track.get('codec', '')} {track.get('channels', '')} {track.get('bitrate', '')}")

        bd_summary_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
        filtered_languages = []
        meta_subtitles = []  # Initialize here so it's clear we're creating it

        if os.path.exists(bd_summary_path):
            if meta['debug']:
                console.print(f"[blue]Opening BD_SUMMARY file: {bd_summary_path}[/blue]")
                console.print("[dim]Stripping extremely small subtitle tracks from bdinfo[/dim]")
            try:
                with open(bd_summary_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                # Parse the subtitles section
                for line in lines:
                    line = line.strip()
                    subtitle_line = None
                    if line.startswith("Subtitle:"):
                        subtitle_line = line
                    elif line.startswith("* Subtitle:"):
                        subtitle_line = line[2:].strip()

                    if subtitle_line:
                        # Extract the subtitle language and bitrate
                        subtitle_match = re.match(r"Subtitle:\s+(\w+)\s+/\s+([\d.]+)\s+kbps", subtitle_line)
                        if subtitle_match:
                            language = subtitle_match.group(1)
                            bitrate = float(subtitle_match.group(2))

                            # Keep subtitles with a bitrate >= 1.0 kbps
                            if bitrate >= 1.0:
                                filtered_languages.append(language.lower())
                                meta_subtitles.append(language)  # Add to meta_subtitles directly
                                if meta['debug']:
                                    console.print(f"[green]✓ Keeping subtitle: {language} ({bitrate} kbps)[/green]")
                            else:
                                if meta['debug']:
                                    console.print(f"[red]✗ Discarding subtitle due to size: {language} ({bitrate} kbps)[/red]")

                if meta_subtitles:
                    if meta['debug']:
                        console.print(f"[blue]Added subtitle languages: {', '.join(meta_subtitles)}[/blue]")
                else:
                    console.print("[yellow]No valid subtitles found to add.[/yellow]")

            except Exception as e:
                console.print(f"[red]Error reading BD_SUMMARY file: {str(e)}[/red]")
        else:
            console.print(f"[red]BD_SUMMARY file not found: {bd_summary_path}[/red]")

    detailed_releases = []
    for idx, release in enumerate(releases, 1):
        console.print(f"[cyan]Processing release {idx}/{len(releases)}: {release['title']} ({release['country']})")
        detailed_release = await fetch_release_details(release, meta)
        detailed_releases.append(detailed_release)

    if meta['debug']:
        console.print()
        cli_ui.info_section("Processing Complete")
    cli_ui.info(f"Successfully processed {len(detailed_releases)} releases")

    logs = []  # Initialize a list to store logs for each release

    def log_and_print(message, log_list):
        if meta['debug']:
            console.print(message)
        log_list.append(message)

    if detailed_releases:
        scored_releases = []
        for idx, release in enumerate(detailed_releases, 1):
            release_logs = []
            if meta['debug']:
                console.print(f"\n[bold blue]=== Release {idx}/{len(detailed_releases)}: {release['title']} ({release['country']}) ===[/bold blue]")
            log_and_print(f"[blue]Release URL: {release['url']}[/blue]", release_logs)
            score = 100.0

            if 'specs' in release:
                specs = release['specs']

                specs_missing = False
                # Check for completeness of data (penalty for missing info)
                if not specs.get('video', {}):
                    score -= 5  # Missing video info
                    specs_missing = True
                    log_and_print("[red]✗[/red] Missing video info", release_logs)
                    log_and_print("[dim]Penalty for missing video info: 5.0[/dim]", release_logs)
                if not specs.get('audio', []):
                    score -= 5  # Missing audio info
                    specs_missing = True
                    log_and_print("[red]✗[/red] Missing audio info", release_logs)
                    log_and_print("[dim]Penalty for missing audio info: 5.0[/dim]", release_logs)
                if meta_subtitles and not specs.get('subtitles', []):
                    score -= 5  # Missing subtitle info when bdinfo has subtitles
                    specs_missing = True
                    log_and_print("[red]✗[/red] Missing subtitle info", release_logs)
                    log_and_print("[dim]Penalty for missing subtitle info: 5.0[/dim]", release_logs)
                if not specs.get('discs', {}):
                    score -= 5  # Missing disc info
                    specs_missing = True
                    log_and_print("[red]✗[/red] Missing disc info", release_logs)
                    log_and_print("[dim]Penalty for missing disc info: 5.0[/dim]", release_logs)

                # Disc format check
                if 'discs' in specs and 'format' in specs['discs'] and 'discs' in meta and 'bdinfo' in meta['discs'][0]:
                    release_format = specs['discs']['format'].lower()
                    disc_size_gb = meta['discs'][0]['bdinfo'].get('size', 0)

                    expected_format = ""
                    if disc_size_gb < 25:
                        expected_format = "bd-25"
                    elif disc_size_gb < 50:
                        expected_format = "bd-50"
                    elif disc_size_gb < 66:
                        expected_format = "bd-66"
                    else:
                        expected_format = "bd-100"

                    format_match = False
                    if release_format == "bd" or "bd" == release_format:
                        format_match = "generic"
                        log_and_print(f"[yellow]⚠[/yellow] Generic BD format found: {specs['discs']['format']} for size {disc_size_gb:.2f} GB", release_logs)
                    elif expected_format and expected_format in release_format:
                        format_match = True
                        log_and_print(f"[green]✓[/green] Disc format match: {specs['discs']['format']} matches size {disc_size_gb:.2f} GB", release_logs)
                    elif expected_format:
                        score -= 50
                        log_and_print(f"[yellow]⚠[/yellow] Disc format mismatch: {specs['discs']['format']} vs expected {expected_format.upper()} (size: {disc_size_gb:.2f} GB)", release_logs)
                        if meta['debug']:
                            log_and_print("[dim]Penalty for disc format mismatch: 50.0[/dim]", release_logs)

                    if format_match == "generic":
                        score -= 5
                        if meta['debug']:
                            log_and_print("[dim]Reduced penalty for generic BD format: 5.0[/dim]", release_logs)

                # Video format checks
                if 'video' in specs and meta_video_specs:
                    release_codec = specs['video'].get('codec', '').lower()
                    meta_codec = meta_video_specs.get('codec', '').lower()

                    codec_match = False
                    if ('avc' in release_codec and 'avc' in meta_codec) or \
                       ('h.264' in release_codec and ('avc' in meta_codec or 'h.264' in meta_codec)):
                        codec_match = True
                        log_and_print("[green]✓[/green] Video codec match: AVC/H.264", release_logs)
                    elif ('hevc' in release_codec and 'hevc' in meta_codec) or \
                         ('h.265' in release_codec and ('hevc' in meta_codec or 'h.265' in meta_codec)):
                        codec_match = True
                        log_and_print("[green]✓[/green] Video codec match: HEVC/H.265", release_logs)
                    elif ('vc-1' in release_codec and 'vc-1' in meta_codec) or \
                         ('vc1' in release_codec and 'vc1' in meta_codec):
                        codec_match = True
                        log_and_print("[green]✓[/green] Video codec match: VC-1", release_logs)
                    elif ('mpeg-2' in release_codec and 'mpeg-2' in meta_codec) or \
                         ('mpeg2' in release_codec and 'mpeg2' in meta_codec):
                        codec_match = True
                        log_and_print("[green]✓[/green] Video codec match: MPEG-2", release_logs)

                    if not codec_match:
                        score -= 80
                        log_and_print(f"[red]✗[/red] Video codec mismatch: {release_codec} vs {meta_codec}", release_logs)
                        if meta['debug']:
                            log_and_print("[dim]Penalty for video codec mismatch 80.0[/dim]", release_logs)

                    # Resolution match check
                    release_res = specs['video'].get('resolution', '').lower()
                    meta_res = meta_video_specs.get('res', '').lower()

                    res_match = False
                    if '1080' in release_res and '1080' in meta_res:
                        res_match = True
                        log_and_print("[green]✓[/green] Resolution match: 1080p", release_logs)
                    elif ('2160' in release_res or '4k' in release_res) and ('2160' in meta_res or '4k' in meta_res):
                        res_match = True
                        log_and_print("[green]✓[/green] Resolution match: 4K/2160p", release_logs)

                    if not res_match:
                        score -= 80
                        log_and_print(f"[red]✗[/red] Resolution mismatch: {release_res} vs {meta_res}", release_logs)
                        if meta['debug']:
                            log_and_print("[dim]Penalty for resolution mismatch 80.0[/dim]", release_logs)
                else:
                    score -= 5
                    log_and_print("[yellow]?[/yellow] Cannot compare video formats", release_logs)

                # Audio track checks
                if 'audio' in specs and meta_audio_specs:
                    audio_matches = 0
                    partial_audio_matches = 0
                    missing_audio_tracks = 0
                    available_release_tracks = specs.get('audio', [])[:]
                    reduced_penalty_count = 0
                    for meta_idx, meta_track in enumerate(meta_audio_specs):
                        meta_lang = meta_track.get('language', '').lower()
                        meta_format = meta_track.get('codec', '').lower().replace('audio', '')
                        meta_channels = meta_track.get('channels', '').lower().replace('audio', '')
                        meta_sample_rate = meta_track.get('sample_rate', '').lower()
                        meta_bit_depth = meta_track.get('bit_depth', '').lower()
                        meta_bitrate = meta_track.get('bitrate', '').lower()

                        # Special handling for Atmos tracks
                        if meta_track.get('atmos_why_you_be_like_this', '').lower() == 'atmos' or 'atmos' in meta_channels:
                            if 'truehd' in meta_format:
                                meta_format = 'dolby truehd atmos'
                            elif 'dolby' in meta_format:
                                meta_format = 'dolby atmos'
                            if meta_channels.strip() in ['atmos audio', 'atmos', '']:
                                if meta_sample_rate in ['7.1', '5.1', '2.0', '1.0']:
                                    meta_channels = meta_sample_rate
                                else:
                                    meta_channels = '7.1'

                            if 'khz' in meta_bitrate and 'khz' not in meta_sample_rate:
                                meta_sample_rate = meta_bitrate
                                meta_bitrate = ""

                            if 'kbps' in meta_bit_depth:
                                bitrate_part = re.search(r'(\d+\s*kbps)', meta_bit_depth)
                                if bitrate_part:
                                    meta_bitrate = bitrate_part.group(1)
                                    bit_depth_part = re.search(r'(\d+)-bit', meta_bit_depth)
                                    if bit_depth_part:
                                        meta_bit_depth = bit_depth_part.group(1) + "-bit"
                                    else:
                                        meta_bit_depth = ""

                        # Skip bit depth if it contains "DN -" (Dolby Digital Normalization)
                        if 'dn -' in meta_bit_depth:
                            meta_bit_depth = ""

                        reduced_penalty = False
                        if meta_idx > 0 and meta_bitrate and "kbps" in meta_bitrate:
                            bitrate_value = int(meta_bitrate.replace("kbps", "").strip())
                            if bitrate_value <= 258:
                                reduced_penalty = True

                        best_match_score = 0
                        best_match_core_score = 0
                        best_match_idx = -1
                        track_found = False

                        for idx, release_track in enumerate(available_release_tracks):
                            release_track_lower = release_track.lower()
                            current_match_score = 0
                            core_match_score = 0

                            lang_match = False
                            if meta_lang and meta_lang in release_track_lower:
                                lang_match = True
                                current_match_score += 1
                                core_match_score += 1

                            if not lang_match:
                                continue

                            format_match = False
                            if 'lpcm' in meta_format and ('pcm' in release_track_lower or 'lpcm' in release_track_lower):
                                format_match = True
                                current_match_score += 1
                                core_match_score += 1
                            elif 'dts-hd' in meta_format and 'dts-hd' in release_track_lower:
                                format_match = True
                                current_match_score += 1
                                core_match_score += 1
                            elif 'dts' in meta_format and 'dts' in release_track_lower:
                                format_match = True
                                current_match_score += 1
                                core_match_score += 1
                            elif 'dolby' in meta_format and 'dolby' in release_track_lower:
                                format_match = True
                                current_match_score += 1
                                core_match_score += 1
                            elif 'truehd' in meta_format and 'truehd' in release_track_lower:
                                format_match = True
                                current_match_score += 1
                                core_match_score += 1
                            elif 'atmos' in meta_format and 'atmos' in release_track_lower:
                                format_match = True
                                current_match_score += 1
                                core_match_score += 1

                            channel_match = False
                            if meta_channels:
                                if '5.1' in meta_channels and '5.1' in release_track_lower:
                                    channel_match = True
                                    current_match_score += 1
                                    core_match_score += 1
                                elif '7.1' in meta_channels and '7.1' in release_track_lower:
                                    channel_match = True
                                    current_match_score += 1
                                    core_match_score += 1
                                elif '2.0' in meta_channels and '2.0' in release_track_lower:
                                    channel_match = True
                                    current_match_score += 1
                                    core_match_score += 1
                                elif '2.0' in meta_channels and 'stereo' in release_track_lower:
                                    channel_match = True
                                    current_match_score += 1
                                    core_match_score += 1
                                elif '1.0' in meta_channels and '1.0' in release_track_lower:
                                    channel_match = True
                                    current_match_score += 1
                                    core_match_score += 1
                                elif '1.0' in meta_channels and 'mono' in release_track_lower:
                                    channel_match = True
                                    current_match_score += 1
                                    core_match_score += 1
                                elif '2.0' in meta_channels and 'mono' in release_track_lower:
                                    channel_match = False
                                elif '1.0' in meta_channels and ('2.0' in release_track_lower or 'stereo' in release_track_lower):
                                    channel_match = False

                            # Check sample rate and bit depth in the release track (may be in notes)
                            if meta_sample_rate:
                                sample_rate_str = meta_sample_rate.replace(' ', '').lower()
                                if sample_rate_str in release_track_lower.replace(' ', ''):
                                    current_match_score += 1
                                elif "note:" in release_track_lower and sample_rate_str in release_track_lower:
                                    current_match_score += 1

                            if meta_bit_depth and meta_bit_depth != "":
                                bit_depth_str = meta_bit_depth.lower()
                                if bit_depth_str in release_track_lower:
                                    current_match_score += 1
                                elif bit_depth_str.replace('-', '') in release_track_lower.replace(' ', ''):
                                    current_match_score += 1
                                elif "note:" in release_track_lower and bit_depth_str.replace('-', '') in release_track_lower.replace(' ', ''):
                                    current_match_score += 1

                            if meta_bitrate and meta_bitrate != "":
                                bitrate_str = meta_bitrate.lower()
                                if bitrate_str in release_track_lower:
                                    current_match_score += 1
                                elif "note:" in release_track_lower and bitrate_str in release_track_lower:
                                    current_match_score += 1

                            if current_match_score > best_match_score:
                                best_match_score = current_match_score
                                best_match_core_score = core_match_score
                                best_match_idx = idx

                            if lang_match and (format_match or channel_match):
                                track_found = True

                        if track_found and best_match_idx >= 0:
                            # Calculate matches based on core fields (language, format, channels)
                            # Maximum core score: language (1) + format (1) + channels (1) = 3
                            core_match_quality = best_match_core_score / 3.0
                            matched_track = available_release_tracks[best_match_idx]

                            if core_match_quality >= 1:
                                audio_matches += 1
                                log_and_print(f"[green]✓[/green] Found good match for {meta_lang} {meta_format} {meta_channels} track: '{matched_track}' (match quality: 100%)", release_logs)
                            else:
                                partial_audio_matches += 1
                                percent = int(core_match_quality * 100)
                                log_and_print(f"[yellow]⚠[/yellow] Found partial match for {meta_lang} {meta_format} {meta_channels} track: '{matched_track}' (match quality: {percent}%)", release_logs)

                            available_release_tracks.pop(best_match_idx)

                        else:
                            missing_audio_tracks += 1
                            if reduced_penalty:
                                reduced_penalty_count += 1
                                log_and_print(f"[red]✗[/red] No match found for {meta_lang} {meta_format} {meta_channels} track (Low bitrate, half penalty)", release_logs)
                            else:
                                log_and_print(f"[red]✗[/red] No match found for {meta_lang} {meta_format} {meta_channels} {meta_bitrate} track", release_logs)

                    total_tracks = len(meta_audio_specs)
                    if total_tracks > 0:
                        full_match_percentage = (audio_matches / total_tracks) * 100
                        partial_match_percentage = (partial_audio_matches / total_tracks) * 100

                        if audio_matches == total_tracks:
                            audio_penalty = 0
                        # Single bdinfo track penalty adjustment
                        elif total_tracks == 1:
                            if audio_matches == 1:
                                audio_penalty = 0
                            elif partial_audio_matches == 1:
                                audio_penalty = 5.0
                            else:
                                audio_penalty = 10.0
                        # Multiple bdinfo tracks penalty adjustment
                        else:
                            audio_penalty = 0
                            audio_penalty += partial_audio_matches * 2.5
                            missing_tracks = total_tracks - (audio_matches + partial_audio_matches)
                            normal_missing = missing_audio_tracks - reduced_penalty_count
                            audio_penalty += normal_missing * 5.0
                            audio_penalty += reduced_penalty_count * 2.5

                        if meta['debug']:
                            log_and_print(f"[dim]Audio penalty: {audio_penalty:.1f}[/dim]", release_logs)
                        score -= audio_penalty

                        if audio_matches > 0:
                            log_and_print(f"[green]✓[/green] Audio tracks with good matches: {audio_matches}/{total_tracks} ({full_match_percentage:.1f}% of tracks)", release_logs)
                            if partial_audio_matches > 0:
                                log_and_print(f"[yellow]⚠[/yellow] Audio tracks with partial matches: {partial_audio_matches}/{total_tracks} ({partial_match_percentage:.1f}% of tracks)", release_logs)
                        elif partial_audio_matches > 0:
                            log_and_print(f"[yellow]⚠[/yellow] There were only partial audio track matches: {partial_audio_matches}/{total_tracks}", release_logs)
                        else:
                            log_and_print("[red]✗[/red] No audio tracks match!", release_logs)

                        extra_audio_tracks = []
                        if available_release_tracks:
                            for release_track in available_release_tracks:
                                extra_audio_tracks.append(release_track)
                                log_and_print(f"[yellow]⚠[/yellow] Release has extra audio track not in BDInfo: {release_track}", release_logs)

                        if extra_audio_tracks:
                            extra_penalty = len(extra_audio_tracks * 5)
                            score -= extra_penalty
                            log_and_print(f"[red]-[/red] Found {len(extra_audio_tracks)} additional audio tracks in release not in BDInfo", release_logs)
                            if meta['debug']:
                                log_and_print(f"[dim]Extra audio tracks penalty: {extra_penalty:.1f} points[/dim]", release_logs)

                else:
                    score -= 5
                    log_and_print("[yellow]?[/yellow] Cannot compare audio tracks", release_logs)

                # Subtitle checks
                if 'subtitles' in specs and meta_subtitles:
                    sub_matches = 0
                    missing_subs = 0
                    available_release_subs = specs.get('subtitles', [])[:]

                    for meta_sub in meta_subtitles:
                        meta_sub_lower = meta_sub.lower()
                        sub_found = False
                        matched_idx = -1

                        for idx, release_sub in enumerate(available_release_subs):
                            release_sub_lower = release_sub.lower()
                            if meta_sub_lower in release_sub_lower or release_sub_lower in meta_sub_lower:
                                sub_found = True
                                matched_idx = idx
                                break

                        if sub_found and matched_idx >= 0:
                            matched_sub = available_release_subs[matched_idx]
                            sub_matches += 1
                            log_and_print(f"[green]✓[/green] Subtitle match found: {meta_sub} -> {matched_sub}", release_logs)
                            available_release_subs.pop(matched_idx)
                        else:
                            missing_subs += 1
                            log_and_print(f"[red]✗[/red] No match found for subtitle: {meta_sub}", release_logs)

                    total_subs = len(meta_subtitles)
                    if total_subs > 0:
                        match_percentage = (sub_matches / total_subs) * 100
                        missing_tracks = total_subs - sub_matches
                        if total_subs == 1 and sub_matches == 0:
                            sub_penalty = 10.0
                        else:
                            sub_penalty = 5.0 * missing_tracks
                        if meta['debug']:
                            log_and_print(f"[dim]Subtitle penalty: {sub_penalty:.1f}[/dim]", release_logs)
                        score -= sub_penalty

                        if sub_matches > 0:
                            log_and_print(f"[green]✓[/green] Subtitle matches: {sub_matches}/{total_subs} ({match_percentage:.1f}%)", release_logs)
                        else:
                            log_and_print("[red]✗[/red] No subtitle tracks match!", release_logs)

                        extra_subtitles = []
                        if available_release_subs:
                            for release_sub in available_release_subs:
                                extra_subtitles.append(release_sub)
                                log_and_print(f"[yellow]⚠[/yellow] Release has extra subtitle not in BDInfo: {release_sub}", release_logs)

                        if extra_subtitles:
                            extra_penalty = len(extra_subtitles * 5)
                            score -= extra_penalty
                            log_and_print(f"[red]-[/red] Found {len(extra_subtitles)} additional subtitles in release not in BDInfo", release_logs)
                            if meta['debug']:
                                log_and_print(f"[dim]Extra subtitles penalty: {extra_penalty:.1f} points[/dim]", release_logs)

                else:
                    score -= 5
                    log_and_print("[yellow]?[/yellow] Cannot compare subtitles", release_logs)
            else:
                score -= 80
                log_and_print("[red]✗[/red] No specifications available for this release", release_logs)

            log_and_print(f"[blue]Final score: {score:.1f}/100 for {release['title']} ({release['country']})[/blue]", release_logs)
            log_and_print("", release_logs)
            scored_releases.append((score, release))
            logs.append((release, release_logs))

        scored_releases.sort(reverse=True, key=lambda x: x[0])

        if scored_releases:
            bluray_score = meta.get('bluray_score', 100)
            bluray_single_score = meta.get('bluray_single_score', 100)
            best_score, best_release = scored_releases[0]
            close_matches = [release for score, release in scored_releases if best_score - score <= 40]

            if len(scored_releases) == 1 and best_score == 100:
                cli_ui.info(f"Single perfect match found: {best_release['title']} ({best_release['country']}) with score {best_score:.1f}/100")
                region_code = map_country_to_region_code(best_release['country'])
                meta['region'] = region_code
                meta['distributor'] = best_release['publisher'].upper()
                meta['release_url'] = best_release['url']
                if 'cover_images' in best_release:
                    meta['cover_images'] = best_release['cover_images']
                    await download_cover_images(meta)
                console.print(f"[yellow]Set region code to: {region_code}, distributor to: {best_release['publisher'].upper()}")

            elif len(scored_releases) == 1:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    cli_ui.info(f"Single match found: {close_matches[0]['title']} ({close_matches[0]['country']}) with score {best_score:.1f}/100")
                    while True:
                        user_input = input("Do you want to use this release? (y/n): ").strip().lower()
                        try:
                            if user_input == 'y':
                                region_code = map_country_to_region_code(close_matches[0]['country'])
                                meta['region'] = region_code
                                meta['distributor'] = close_matches[0]['publisher'].upper()
                                meta['release_url'] = close_matches[0]['url']
                                if 'cover_images' in close_matches[0]:
                                    meta['cover_images'] = close_matches[0]['cover_images']
                                    await download_cover_images(meta)
                                console.print(f"[yellow]Set region code to: {region_code}, distributor to: {close_matches[0]['publisher'].upper()}")
                                break
                            elif user_input == 'n':
                                cli_ui.warning("No release selected.")
                                detailed_releases = []
                                break
                            else:
                                console.print("[red]Invalid input. Please enter 'y' or 'n'.[/red]")
                        except ValueError:
                            console.print("[red]Invalid input. Please enter 'y' or 'n'.[/red]")
                        except KeyboardInterrupt:
                            console.print("[red]Operation cancelled.[/red]")
                            break
                elif best_score > bluray_single_score:
                    cli_ui.info(f"Best match: {best_release['title']} ({best_release['country']}) with score {best_score:.1f}/100")
                    region_code = map_country_to_region_code(best_release['country'])
                    meta['region'] = region_code
                    meta['distributor'] = best_release['publisher'].upper()
                    meta['release_url'] = best_release['url']
                    if 'cover_images' in best_release:
                        meta['cover_images'] = best_release['cover_images']
                        await download_cover_images(meta)
                    console.print(f"[yellow]Set region code to: {region_code}, distributor to: {best_release['publisher'].upper()}")
                else:
                    cli_ui.warning(f"No suitable release found. Best match was {best_release['title']} ({best_release['country']}) with score {best_score:.1f}/100")
                    detailed_releases = []

            elif len(close_matches) > 1:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                    console.print("[yellow]Multiple releases are within 40 points of the best match. Please confirm which release to use:[/yellow]")
                    if format_match == "generic":
                        console.print("[red]Note: Generic BD format found, please confirm the release.[/red]")
                    if specs_missing:
                        console.print("[red]Note: Missing specs in release, please confirm the release.[/red]")
                    for idx, release in enumerate(close_matches, 1):
                        score = next(score for score, r in scored_releases if r == release)
                        console.print(f"{idx}. [blue]{release['title']} ({release['country']})[/blue] - Score: {score:.1f}/100")

                    while True:
                        console.print("Enter the number of the release to use, 'p' to print logs for a release, or 'n' to skip:")
                        user_input = input("Selection: ").strip().lower()
                        if user_input == 'n':
                            cli_ui.warning("No release selected.")
                            detailed_releases = []
                            break
                        elif user_input == 'p':
                            try:
                                release_idx = int(input(f"Enter the release number (1-{len(close_matches)}) to print logs: ").strip())
                                if 1 <= release_idx <= len(close_matches):
                                    selected_release = close_matches[release_idx - 1]
                                    for logged_release, release_logs in logs:
                                        if logged_release == selected_release:
                                            console.print(f"[yellow]Logs for release: {logged_release['title']} ({logged_release['country']})[/yellow]")
                                            for log in release_logs:
                                                console.print(log)
                                            break
                                else:
                                    console.print(f"[red]Invalid selection. Please enter a number between 1 and {len(close_matches)}.[/red]")
                            except ValueError:
                                console.print("[red]Invalid input. Please enter a valid number.[/red]")
                            except KeyboardInterrupt:
                                console.print("[red]Operation cancelled.[/red]")
                                break
                        else:
                            try:
                                selected_idx = int(user_input)
                                if 1 <= selected_idx <= len(close_matches):
                                    selected_release = close_matches[selected_idx - 1]
                                    cli_ui.info(f"Selected: {selected_release['title']} ({selected_release['country']})")
                                    region_code = map_country_to_region_code(selected_release['country'])
                                    meta['region'] = region_code
                                    meta['distributor'] = selected_release['publisher'].upper()
                                    meta['release_url'] = selected_release['url']
                                    if 'cover_images' in selected_release:
                                        meta['cover_images'] = selected_release['cover_images']
                                        await download_cover_images(meta)
                                    console.print(f"[yellow]Set region code to: {region_code}, distributor to: {selected_release['publisher'].upper()}[/yellow]")
                                    break
                                else:
                                    console.print(f"[red]Invalid selection. Please enter a number between 1 and {len(close_matches)}.[/red]")
                            except ValueError:
                                console.print("[red]Invalid input. Please enter a number or 'n'.[/red]")
                            except KeyboardInterrupt:
                                console.print("[red]Operation cancelled.[/red]")
                                break
                elif best_score > bluray_score:
                    cli_ui.info(f"Best match: {best_release['title']} ({best_release['country']}) with score {best_score:.1f}/100")
                    region_code = map_country_to_region_code(best_release['country'])
                    meta['region'] = region_code
                    meta['distributor'] = best_release['publisher'].upper()
                    meta['release_url'] = best_release['url']
                    if 'cover_images' in best_release:
                        meta['cover_images'] = best_release['cover_images']
                        await download_cover_images(meta)
                    console.print(f"[yellow]Set region code to: {region_code}, distributor to: {best_release['publisher'].upper()}[/yellow]")
                else:
                    cli_ui.warning(f"No suitable release found. Best match was {best_release['title']} ({best_release['country']}) with score {best_score:.1f}/100")
                    detailed_releases = []

            else:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                    console.print("[red]This is the probably the best match, but it is not a perfect match.[/red]")
                    console.print("[yellow]All other releases have a score at least 40 points lower.")
                    for logged_release, release_logs in logs:
                        if logged_release == best_release:
                            console.print(f"[yellow]Logs for release: {logged_release['title']} ({logged_release['country']})[/yellow]")
                            for log in release_logs:
                                console.print(log)
                    while True:
                        user_input = input("Do you want to use this release? (y/n): ").strip().lower()
                        try:
                            if user_input == 'y':
                                region_code = map_country_to_region_code(best_release['country'])
                                meta['region'] = region_code
                                meta['distributor'] = best_release['publisher'].upper()
                                meta['release_url'] = best_release['url']
                                if 'cover_images' in best_release:
                                    meta['cover_images'] = best_release['cover_images']
                                    await download_cover_images(meta)
                                console.print(f"[yellow]Set region code to: {region_code}, distributor to: {best_release['publisher'].upper()}[/yellow]")
                                break
                            elif user_input == 'n':
                                cli_ui.warning("No release selected.")
                                detailed_releases = []
                                break
                            else:
                                console.print("[red]Invalid input. Please enter 'y' or 'n'.[/red]")
                        except ValueError:
                            console.print("[red]Invalid input. Please enter 'y' or 'n'.[/red]")
                        except KeyboardInterrupt:
                            console.print("[red]Operation cancelled.[/red]")
                            break
                elif best_score > bluray_score:
                    cli_ui.info(f"Best match: {best_release['title']} ({best_release['country']}) with score {best_score:.1f}/100")
                    region_code = map_country_to_region_code(best_release['country'])
                    meta['region'] = region_code
                    meta['distributor'] = best_release['publisher'].upper()
                    meta['release_url'] = best_release['url']
                    if 'cover_images' in best_release:
                        meta['cover_images'] = best_release['cover_images']
                        await download_cover_images(meta)
                    console.print(f"[yellow]Set region code to: {region_code}, distributor to: {best_release['publisher'].upper()}[/yellow]")
                else:
                    cli_ui.warning(f"No suitable release found. Best match was {best_release['title']} ({best_release['country']}) with score {best_score:.1f}/100")
                    detailed_releases = []

    return detailed_releases


def map_country_to_region_code(country_name):
    country_map = {
        "Afghanistan": "AFG",
        "Albania": "ALB",
        "Algeria": "ALG",
        "Andorra": "AND",
        "Angola": "ANG",
        "Argentina": "ARG",
        "Armenia": "ARM",
        "Aruba": "ARU",
        "Australia": "AUS",
        "Austria": "AUT",
        "Azerbaijan": "AZE",
        "Bahamas": "BAH",
        "Bahrain": "BHR",
        "Bangladesh": "BAN",
        "Barbados": "BRB",
        "Belarus": "BLR",
        "Belgium": "BEL",
        "Belize": "BLZ",
        "Benin": "BEN",
        "Bermuda": "BER",
        "Bhutan": "BHU",
        "Bolivia": "BOL",
        "Bosnia and Herzegovina": "BIH",
        "Botswana": "BOT",
        "Brazil": "BRA",
        "British Virgin Islands": "VGB",
        "Brunei": "BRU",
        "Burkina Faso": "BFA",
        "Burundi": "BDI",
        "Cambodia": "CAM",
        "Cameroon": "CMR",
        "Canada": "CAN",
        "Cape Verde": "CPV",
        "Cayman Islands": "CAY",
        "Central African Republic": "CTA",
        "Chad": "CHA",
        "Chile": "CHI",
        "China": "CHN",
        "Colombia": "COL",
        "Comoros": "COM",
        "Congo": "CGO",
        "Cook Islands": "COK",
        "Costa Rica": "CRC",
        "Croatia": "CRO",
        "Cuba": "CUB",
        "Cyprus": "CYP",
        "Dominican Republic": "DOM",
        "Ecuador": "ECU",
        "Egypt": "EGY",
        "El Salvador": "SLV",
        "Equatorial Guinea": "EQG",
        "Eritrea": "ERI",
        "Ethiopia": "ETH",
        "Fiji": "FIJ",
        "France": "FRA",
        "Gabon": "GAB",
        "Gambia": "GAM",
        "Georgia": "GEO",
        "Germany": "GER",
        "Ghana": "GHA",
        "Greece": "GRE",
        "Grenada": "GRN",
        "Guatemala": "GUA",
        "Guinea": "GUI",
        "Guyana": "GUY",
        "Haiti": "HAI",
        "Honduras": "HON",
        "Hong Kong": "HKG",
        "Hungary": "HUN",
        "Iceland": "ISL",
        "India": "IND",
        "Indonesia": "IDN",
        "Iran": "IRN",
        "Iraq": "IRQ",
        "Ireland": "IRL",
        "Israel": "ISR",
        "Italy": "ITA",
        "Jamaica": "JAM",
        "Japan": "JPN",
        "Jordan": "JOR",
        "Kazakhstan": "KAZ",
        "Kenya": "KEN",
        "Kuwait": "KUW",
        "Kyrgyzstan": "KGZ",
        "Laos": "LAO",
        "Lebanon": "LBN",
        "Liberia": "LBR",
        "Libya": "LBY",
        "Liechtenstein": "LIE",
        "Luxembourg": "LUX",
        "Macau": "MAC",
        "Madagascar": "MAD",
        "Malaysia": "MAS",
        "Malta": "MLT",
        "Mexico": "MEX",
        "Monaco": "MON",
        "Mongolia": "MNG",
        "Morocco": "MAR",
        "Mozambique": "MOZ",
        "Namibia": "NAM",
        "Nepal": "NEP",
        "Netherlands": "NLD",
        "New Zealand": "NZL",
        "Nicaragua": "NCA",
        "Niger": "NIG",
        "North Korea": "PRK",
        "North Macedonia": "MKD",
        "Norway": "NOR",
        "Oman": "OMA",
        "Pakistan": "PAK",
        "Panama": "PAN",
        "Papua New Guinea": "PNG",
        "Paraguay": "PAR",
        "Peru": "PER",
        "Philippines": "PHI",
        "Poland": "POL",
        "Portugal": "POR",
        "Puerto Rico": "PUR",
        "Qatar": "QAT",
        "Romania": "ROU",
        "Russia": "RUS",
        "Rwanda": "RWA",
        "Saint Lucia": "LCA",
        "Samoa": "SAM",
        "San Marino": "SMR",
        "Saudi Arabia": "KSA",
        "Senegal": "SEN",
        "Serbia": "SRB",
        "Singapore": "SIN",
        "South Africa": "RSA",
        "South Korea": "KOR",
        "Spain": "ESP",
        "Sri Lanka": "LKA",
        "Sudan": "SDN",
        "Suriname": "SUR",
        "Switzerland": "SUI",
        "Syria": "SYR",
        "Chinese Taipei": "TWN",
        "Tajikistan": "TJK",
        "Tanzania": "TAN",
        "Thailand": "THA",
        "Trinidad and Tobago": "TRI",
        "Tunisia": "TUN",
        "Turkey": "TUR",
        "Uganda": "UGA",
        "Ukraine": "UKR",
        "United Arab Emirates": "UAE",
        "United Kingdom": "GBR",
        "United States": "USA",
        "Uruguay": "URU",
        "Uzbekistan": "UZB",
        "Venezuela": "VEN",
        "Vietnam": "VIE",
        "Zambia": "ZAM",
        "Zimbabwe": "ZIM",
    }

    region_code = country_map.get(country_name)
    if not region_code:
        region_code = None

    return region_code
