# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
import asyncio
import cli_ui
import httpx
import json
import sys

from anitopy import parse as anitopy_parse
from datetime import datetime
from difflib import SequenceMatcher
from guessit import guessit

from src.cleanup import cleanup, reset_terminal
from src.console import console


async def safe_get(data, path, default=None):
    for key in path:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data


async def get_imdb_info_api(imdbID, manual_language=None, debug=False):
    imdb_info = {}

    if not imdbID or imdbID == 0:
        imdb_info['type'] = None
        return imdb_info

    try:
        if not str(imdbID).startswith("tt"):
            imdbID = f"tt{imdbID:07d}"
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return imdb_info

    query = {
        "query": f"""
        query GetTitleInfo {{
            title(id: "{imdbID}") {{
            id
            titleText {{
                text
                isOriginalTitle
                country {{
                    text
                }}
            }}
            originalTitleText {{
                text
            }}
            releaseYear {{
                year
                endYear
            }}
            titleType {{
                id
            }}
            plot {{
                plotText {{
                plainText
                }}
            }}
            ratingsSummary {{
                aggregateRating
                voteCount
            }}
            primaryImage {{
                url
            }}
            runtime {{
                displayableProperty {{
                value {{
                    plainText
                }}
                }}
                seconds
            }}
            titleGenres {{
                genres {{
                genre {{
                    text
                }}
                }}
            }}
            principalCredits {{
                category {{
                text
                id
                }}
                credits {{
                name {{
                    id
                    nameText {{
                    text
                    }}
                }}
                }}
            }}
            episodes {{
                episodes(first: 500) {{
                    edges {{
                        node {{
                            id
                            series {{
                                displayableEpisodeNumber {{
                                    displayableSeason {{
                                        season
                                    }}
                                    episodeNumber {{
                                        text
                                    }}
                                }}
                            }}
                            titleText {{
                                text
                            }}
                            releaseYear {{
                                year
                            }}
                            releaseDate {{
                                year
                                month
                                day
                            }}
                        }}
                    }}
                    pageInfo {{
                        hasNextPage
                        hasPreviousPage
                    }}
                    total
                }}
            }}
            runtimes(first: 10) {{
                edges {{
                    node {{
                        id
                        seconds
                        displayableProperty {{
                            value {{
                                plainText
                            }}
                        }}
                        attributes {{
                            text
                        }}
                    }}
                }}
            }}
            technicalSpecifications {{
                aspectRatios {{
                    items {{
                        aspectRatio
                        attributes {{
                            text
                        }}
                    }}
                }}
                cameras {{
                    items {{
                        camera
                        attributes {{
                            text
                        }}
                    }}
                }}
                colorations {{
                    items {{
                        text
                        attributes {{
                            text
                        }}
                    }}
                }}
                laboratories {{
                    items {{
                        laboratory
                        attributes {{
                            text
                        }}
                    }}
                }}
                negativeFormats {{
                    items {{
                        negativeFormat
                        attributes {{
                            text
                        }}
                    }}
                }}
                printedFormats {{
                    items {{
                        printedFormat
                        attributes {{
                            text
                        }}
                    }}
                }}
                processes {{
                    items {{
                        process
                        attributes {{
                            text
                        }}
                    }}
                }}
                soundMixes {{
                    items {{
                        text
                        attributes {{
                            text
                        }}
                    }}
                }}
                filmLengths {{
                    items {{
                        filmLength
                        countries {{
                            text
                        }}
                        numReels
                    }}
                }}
            }}
            akas(first: 100) {{
            edges {{
                node {{
                text
                country {{
                    text
                }}
                language {{
                    text
                }}
                attributes {{
                    text
                }}
                }}
            }}
            }}
            countriesOfOrigin {{
                countries {{
                    text
                    }}
                }}
            }}
        }}
        """
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("https://api.graphql.imdb.com/", json=query, headers={"Content-Type": "application/json"}, timeout=10)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            console.print(f"[red]IMDb API error: {e.response.status_code}[/red]")
            return imdb_info
        except httpx.RequestError as e:
            console.print(f"[red]IMDb API Network error: {e}[/red]")
            return imdb_info

    title_data = await safe_get(data, ["data", "title"], {})
    if not title_data:
        return imdb_info  # Return empty if no data found

    imdb_info['imdbID'] = imdbID
    imdb_info['imdb_url'] = f"https://www.imdb.com/title/{imdbID}"
    imdb_info['title'] = await safe_get(title_data, ['titleText', 'text'])
    countries_list = await safe_get(title_data, ['countriesOfOrigin', 'countries'], [])
    if isinstance(countries_list, list) and countries_list:
        # First country for 'country'
        imdb_info['country'] = countries_list[0].get('text', '')
        # All countries joined for 'country_list'
        imdb_info['country_list'] = ', '.join([c.get('text', '') for c in countries_list if isinstance(c, dict) and 'text' in c])
    else:
        imdb_info['country'] = ''
        imdb_info['country_list'] = ''
    imdb_info['year'] = await safe_get(title_data, ['releaseYear', 'year'])
    imdb_info['end_year'] = await safe_get(title_data, ['releaseYear', 'endYear'])
    original_title = await safe_get(title_data, ['originalTitleText', 'text'], '')
    imdb_info['aka'] = original_title if original_title and original_title != imdb_info['title'] else imdb_info['title']
    imdb_info['type'] = await safe_get(title_data, ['titleType', 'id'], None)
    runtime_seconds = await safe_get(title_data, ['runtime', 'seconds'], 0)
    imdb_info['runtime'] = str(runtime_seconds // 60 if runtime_seconds else 60)
    imdb_info['cover'] = await safe_get(title_data, ['primaryImage', 'url'])
    imdb_info['plot'] = await safe_get(title_data, ['plot', 'plotText', 'plainText'], 'No plot available')

    genres = await safe_get(title_data, ['titleGenres', 'genres'], [])
    genre_list = [await safe_get(g, ['genre', 'text'], '') for g in genres]
    imdb_info['genres'] = ', '.join(filter(None, genre_list))

    imdb_info['rating'] = await safe_get(title_data, ['ratingsSummary', 'aggregateRating'], 'N/A')

    async def get_credits(title_data, category_keyword):
        people_list = []
        people_id_list = []
        principal_credits = await safe_get(title_data, ['principalCredits'], [])

        if not isinstance(principal_credits, list):
            return people_list, people_id_list

        for pc in principal_credits:
            category_text = await safe_get(pc, ['category', 'text'], '')

            if category_keyword in category_text:
                credits = await safe_get(pc, ['credits'], [])
                for c in credits:
                    name_obj = await safe_get(c, ['name'], {})
                    person_id = await safe_get(name_obj, ['id'], '')
                    person_name = await safe_get(name_obj, ['nameText', 'text'], '')

                    if person_id and person_name:
                        people_list.append(person_name)
                        people_id_list.append(person_id)
                break

        return people_list, people_id_list

    imdb_info['directors'], imdb_info['directors_id'] = await get_credits(title_data, 'Direct')
    imdb_info['creators'], imdb_info['creators_id'] = await get_credits(title_data, 'Creat')
    imdb_info['writers'], imdb_info['writers_id'] = await get_credits(title_data, 'Writ')
    imdb_info['stars'], imdb_info['stars_id'] = await get_credits(title_data, 'Star')

    editions = await safe_get(title_data, ['runtimes', 'edges'], [])
    if editions:
        edition_list = []
        imdb_info['edition_details'] = {}

        for edge in editions:
            node = await safe_get(edge, ['node'], {})
            seconds = await safe_get(node, ['seconds'], 0)
            minutes = seconds // 60 if seconds else 0
            displayable_property = await safe_get(node, ['displayableProperty', 'value', 'plainText'], '')
            attributes = await safe_get(node, ['attributes'], [])
            attribute_texts = [attr.get('text') for attr in attributes if isinstance(attr, dict)] if attributes else []

            edition_display = f"{displayable_property} ({minutes} min)"
            if attribute_texts:
                edition_display += f" [{', '.join(attribute_texts)}]"

            if seconds and displayable_property:
                edition_list.append(edition_display)

                runtime_key = str(minutes)
                imdb_info['edition_details'][runtime_key] = {
                    'display_name': displayable_property,
                    'seconds': seconds,
                    'minutes': minutes,
                    'attributes': attribute_texts
                }

        imdb_info['editions'] = ', '.join(edition_list)

    akas_edges = await safe_get(title_data, ['akas', 'edges'], default=[])
    imdb_info['akas'] = [
        {
            "title": await safe_get(edge, ['node', 'text']),
            "country": await safe_get(edge, ['node', 'country', 'text']),
            "language": await safe_get(edge, ['node', 'language', 'text']),
            "attributes": await safe_get(edge, ['node', 'attributes'], []),
        }
        for edge in akas_edges
    ]

    if manual_language:
        imdb_info['original_language'] = manual_language

    imdb_info['episodes'] = []
    episodes_data = await safe_get(title_data, ['episodes', 'episodes'], None)
    if episodes_data:
        edges = await safe_get(episodes_data, ['edges'], [])
        for edge in edges:
            node = await safe_get(edge, ['node'], {})

            series_info = await safe_get(node, ['series', 'displayableEpisodeNumber'], {})
            season_info = await safe_get(series_info, ['displayableSeason'], {})
            episode_number_info = await safe_get(series_info, ['episodeNumber'], {})

            episode_info = {
                'id': await safe_get(node, ['id'], ''),
                'title': await safe_get(node, ['titleText', 'text'], 'Unknown Title'),
                'release_year': await safe_get(node, ['releaseYear', 'year'], 'Unknown Year'),
                'release_date': {
                    'year': await safe_get(node, ['releaseDate', 'year'], None),
                    'month': await safe_get(node, ['releaseDate', 'month'], None),
                    'day': await safe_get(node, ['releaseDate', 'day'], None),
                },
                'season': await safe_get(season_info, ['season'], 'unknown'),
                'episode_number': await safe_get(episode_number_info, ['text'], '')
            }
            imdb_info['episodes'].append(episode_info)

    if imdb_info['episodes']:
        seasons_data = {}

        for episode in imdb_info['episodes']:
            season_str = episode.get('season', 'unknown')
            release_year = episode.get('release_year')

            try:
                season_int = int(season_str) if season_str != 'unknown' and season_str else None
            except (ValueError, TypeError):
                season_int = None

            if season_int is not None and release_year and isinstance(release_year, int):
                if season_int not in seasons_data:
                    seasons_data[season_int] = set()
                seasons_data[season_int].add(release_year)

        seasons_summary = []
        for season_num in sorted(seasons_data.keys()):
            years = sorted(list(seasons_data[season_num]))
            season_entry = {
                'season': season_num,
                'year': years[0],
                'year_range': f"{years[0]}" if len(years) == 1 else f"{years[0]}-{years[-1]}"
            }
            seasons_summary.append(season_entry)

        imdb_info['seasons_summary'] = seasons_summary
    else:
        imdb_info['seasons_summary'] = []

    sound_mixes = await safe_get(title_data, ['technicalSpecifications', 'soundMixes', 'items'], [])
    imdb_info['sound_mixes'] = [sm.get('text', '') for sm in sound_mixes if isinstance(sm, dict) and 'text' in sm]

    episodes = imdb_info.get('episodes', [])
    current_year = datetime.now().year
    release_years = [episode['release_year'] for episode in episodes if 'release_year' in episode and isinstance(episode['release_year'], int)]
    if imdb_info['end_year']:
        imdb_info['tv_year'] = imdb_info['end_year']
    elif release_years:
        closest_year = min(release_years, key=lambda year: abs(year - current_year))
        imdb_info['tv_year'] = closest_year
    else:
        imdb_info['tv_year'] = None

    if debug:
        console.print(f"[yellow]IMDb Response: {json.dumps(imdb_info, indent=2)[:1000]}...[/yellow]")

    return imdb_info


async def search_imdb(filename, search_year, quickie=False, category=None, debug=False, secondary_title=None, path=None, untouched_filename=None, attempted=0, duration=None, unattended=False):
    search_results = []
    imdbID = imdb_id = 0
    if attempted is None:
        attempted = 0
    if debug:
        console.print(f"[yellow]Searching IMDb for {filename} and year {search_year}...[/yellow]")
    if attempted:
        await asyncio.sleep(1)  # Whoa baby, slow down

    async def run_imdb_search(filename, search_year, category=None, debug=False, attempted=0, duration=None, wide_search=False):
        search_results = []
        if secondary_title is not None:
            filename = secondary_title
        if attempted is None:
            attempted = 0
        if attempted:
            await asyncio.sleep(1)  # Whoa baby, slow down
        url = "https://api.graphql.imdb.com/"
        if category == "MOVIE":
            filename = filename.replace('and', '&').replace('And', '&').replace('AND', '&').strip()

        constraints_parts = [f'titleTextConstraint: {{searchTerm: "{filename}"}}']

        # Add release date constraint if search_year is provided
        if not wide_search and search_year:
            search_year_int = int(search_year)
            start_year = search_year_int - 1
            end_year = search_year_int + 1
            constraints_parts.append(f'releaseDateConstraint: {{releaseDateRange: {{start: "{start_year}-01-01", end: "{end_year}-12-31"}}}}')

        if not wide_search and duration:
            if isinstance(duration, int):
                duration = str(duration)
                start_duration = int(duration) - 10
                end_duration = int(duration) + 10
                constraints_parts.append(f'runtimeConstraint: {{runtimeRangeMinutes: {{min: {start_duration}, max: {end_duration}}}}}')

        constraints_string = ', '.join(constraints_parts)

        query = {
            "query": f"""
                {{
                    advancedTitleSearch(
                        first: 10,
                        constraints: {{{constraints_string}}}
                    ) {{
                        total
                        edges {{
                            node {{
                                title {{
                                    id
                                    titleText {{
                                        text
                                    }}
                                    titleType {{
                                        text
                                    }}
                                    releaseYear {{
                                        year
                                    }}
                                    plot {{
                                        plotText {{
                                        plainText
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            """
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=query, headers={"Content-Type": "application/json"}, timeout=10)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            console.print(f"[red]IMDb GraphQL API error: {e}[/red]")
            return 0

        results = await safe_get(data, ["data", "advancedTitleSearch", "edges"], [])
        search_results = results

        if debug:
            console.print(f"[yellow]Found {len(results)} results...[/yellow]")
            console.print(f"quickie: {quickie}, category: {category}, search_year: {search_year}")
        return search_results

    if not search_results:
        result = await run_imdb_search(filename, search_year, category, debug, attempted, duration, wide_search=False)
        if result and len(result) > 0:
            search_results = result

    if not search_results and secondary_title:
        if debug:
            console.print(f"[yellow]Trying IMDb with secondary title: {secondary_title}[/yellow]")
        result = await run_imdb_search(secondary_title, search_year, category, debug, attempted, duration, wide_search=True)
        if result and len(result) > 0:
            search_results = result

    # remove 'the' from the beginning of the title if it exists
    if not search_results:
        try:
            words = filename.split()
            bad_words = ['the']
            words_lower = [word.lower() for word in words]

            if words_lower and words_lower[0] in bad_words:
                words.pop(0)
                words_lower.pop(0)
                title = ' '.join(words)
                if debug:
                    console.print(f"[bold yellow]Trying IMDb with the prefix removed: {title}[/bold yellow]")
                result = await run_imdb_search(title, search_year, category, debug, attempted + 1, wide_search=False)
                if result and len(result) > 0:
                    search_results = result
        except Exception as e:
            console.print(f"[bold red]Reduced name search error:[/bold red] {e}")
            search_results = {"results": []}

    # relax the constraints
    if not search_results:
        if debug:
            console.print("[yellow]No results found, trying with a wider search...[/yellow]")
        try:
            result = await run_imdb_search(filename, search_year, category, debug, attempted + 1, wide_search=True)
            if result and len(result) > 0:
                search_results = result
        except Exception as e:
            console.print(f"[red]Error during wide search: {e}[/red]")

    # Try parsed title (anitopy + guessit)
    if not search_results:
        try:
            parsed = guessit(untouched_filename, {"excludes": ["country", "language"]})
            parsed_title = anitopy_parse(parsed['title'])['anime_title']
            if debug:
                console.print(f"[bold yellow]Trying IMDB with parsed title: {parsed_title}[/bold yellow]")
            result = await run_imdb_search(parsed_title, search_year, category, debug, attempted + 1, wide_search=True)
            if result and len(result) > 0:
                search_results = result
        except Exception:
            console.print("[bold red]Guessit failed parsing title, trying another method[/bold red]")

    # Try with less words in the title
    if not search_results:
        try:
            words = filename.split()
            extensions = ['mp4', 'mkv', 'avi', 'webm', 'mov', 'wmv']
            words_lower = [word.lower() for word in words]

            for ext in extensions:
                if ext in words_lower:
                    ext_index = words_lower.index(ext)
                    words.pop(ext_index)
                    words_lower.pop(ext_index)
                    break

            if len(words) > 1:
                reduced_title = ' '.join(words[:-1])
                if debug:
                    console.print(f"[bold yellow]Trying IMDB with reduced name: {reduced_title}[/bold yellow]")
                result = await run_imdb_search(reduced_title, search_year, category, debug, attempted + 1, wide_search=True)
                if result and len(result) > 0:
                    search_results = result
        except Exception as e:
            console.print(f"[bold red]Reduced name search error:[/bold red] {e}")

    # Try with even fewer words
    if not search_results:
        try:
            words = filename.split()
            extensions = ['mp4', 'mkv', 'avi', 'webm', 'mov', 'wmv']
            words_lower = [word.lower() for word in words]

            for ext in extensions:
                if ext in words_lower:
                    ext_index = words_lower.index(ext)
                    words.pop(ext_index)
                    words_lower.pop(ext_index)
                    break

            if len(words) > 2:
                further_reduced_title = ' '.join(words[:-2])
                if debug:
                    console.print(f"[bold yellow]Trying IMDB with further reduced name: {further_reduced_title}[/bold yellow]")
                result = await run_imdb_search(further_reduced_title, search_year, category, debug, attempted + 1, wide_search=True)
                if result and len(result) > 0:
                    search_results = result
        except Exception as e:
            console.print(f"[bold red]Further reduced name search error:[/bold red] {e}")

    if quickie:
        if search_results:
            first_result = search_results[0]
            if debug:
                console.print(f"[cyan]Quickie search result: {first_result}[/cyan]")
            node = await safe_get(first_result, ["node"], {})
            title = await safe_get(node, ["title"], {})
            type_info = await safe_get(title, ["titleType"], {})
            year = await safe_get(title, ["releaseYear", "year"], None)
            imdb_id = await safe_get(title, ["id"], "")
            year_int = int(year) if year else None
            search_year_int = int(search_year) if search_year else None

            type_matches = False
            if type_info:
                title_type = type_info.get("text", "").lower()
                if category and category.lower() == "tv" and "tv series" in title_type:
                    type_matches = True
                elif category and category.lower() == "movie" and "tv series" not in title_type:
                    type_matches = True

            if imdb_id and type_matches:
                if year_int and search_year_int:
                    if year_int == search_year_int:
                        imdbID = int(imdb_id.replace('tt', '').strip())
                        return imdbID
                    else:
                        if debug:
                            console.print(f"[yellow]Year mismatch: found {year_int}, expected {search_year_int}[/yellow]")
                        return 0
                else:
                    imdbID = int(imdb_id.replace('tt', '').strip())
                    return imdbID
            else:
                if not imdb_id and debug:
                    console.print("[yellow]No IMDb ID found in quickie result[/yellow]")
                if not type_matches and debug:
                    console.print(f"[yellow]Type mismatch: found {type_info.get('text', '')}, expected {category}[/yellow]")
                imdbID = 0

        return imdbID if imdbID else 0

    else:
        if len(search_results) == 1:
            imdb_id = await safe_get(search_results[0], ["node", "title", "id"], "")
            if imdb_id:
                imdbID = int(imdb_id.replace('tt', '').strip())
                return imdbID
        elif len(search_results) > 1:
            # Calculate similarity for all results
            results_with_similarity = []
            filename_norm = filename.lower().strip()
            search_year_int = int(search_year) if search_year else 0

            for r in search_results:
                node = await safe_get(r, ["node"], {})
                title = await safe_get(node, ["title"], {})
                title_text = await safe_get(title, ["titleText", "text"], "")
                result_year = await safe_get(title, ["releaseYear", "year"], 0)

                similarity = SequenceMatcher(None, filename_norm, title_text.lower().strip()).ratio()

                # Only boost similarity if titles are very similar (>= 0.99) AND years match
                if similarity >= 0.99 and search_year_int > 0 and result_year > 0:
                    if result_year == search_year_int:
                        similarity += 0.1  # Full boost for exact year match
                    elif result_year == search_year_int - 1:
                        similarity += 0.05  # Half boost for -1 year

                results_with_similarity.append((r, similarity))

            # Sort by similarity (highest first)
            results_with_similarity.sort(key=lambda x: x[1], reverse=True)

            # Filter results: if we have high similarity matches (>= 0.90), hide low similarity ones (< 0.75)
            best_similarity = results_with_similarity[0][1]
            if best_similarity >= 0.90:
                filtered_results_with_similarity = [
                    (result, sim) for result, sim in results_with_similarity
                    if sim >= 0.75
                ]
                results_with_similarity = filtered_results_with_similarity

                if debug:
                    console.print(f"[yellow]Filtered out low similarity results (< 0.70) since best match has {best_similarity:.2f} similarity[/yellow]")

            sorted_results = [r[0] for r in results_with_similarity]

            # Check if the best match is significantly better than others
            best_similarity = results_with_similarity[0][1]
            similarity_threshold = 0.85

            if best_similarity >= similarity_threshold:
                second_best = results_with_similarity[1][1] if len(results_with_similarity) > 1 else 0.0

                if best_similarity - second_best >= 0.10:
                    if debug:
                        console.print(f"[green]Auto-selecting best match: {await safe_get(sorted_results[0], ['node', 'title', 'titleText', 'text'], '')} (similarity: {best_similarity:.2f})[/green]")
                    imdb_id = await safe_get(sorted_results[0], ["node", "title", "id"], "")
                    if imdb_id:
                        imdbID = int(imdb_id.replace('tt', '').strip())
                        return imdbID

            if unattended:
                imdb_id = await safe_get(sorted_results[0], ["node", "title", "id"], "")
                if imdb_id:
                    imdbID = int(imdb_id.replace('tt', '').strip())
                    if debug:
                        console.print(f"[green]Unattended mode: auto-selected IMDb ID {imdbID}[/green]")
                    return imdbID

            # Show sorted results to user
            console.print("[bold yellow]Multiple IMDb results found. Please select the correct entry:[/bold yellow]")

            for idx, result in enumerate(sorted_results):
                node = await safe_get(result, ["node"], {})
                title = await safe_get(node, ["title"], {})
                title_text = await safe_get(title, ["titleText", "text"], "")
                year = await safe_get(title, ["releaseYear", "year"], None)
                imdb_id = await safe_get(title, ["id"], "")
                title_type = await safe_get(title, ["titleType", "text"], "")
                plot = await safe_get(title, ["plot", "plotText", "plainText"], "")
                similarity_score = results_with_similarity[idx][1]

                console.print(f"[cyan]{idx+1}.[/cyan] [bold]{title_text}[/bold] ({year}) [yellow]ID:[/yellow] {imdb_id} [yellow]Type:[/yellow] {title_type} [dim](similarity: {similarity_score:.2f})[/dim]")
                if plot:
                    console.print(f"[green]Plot:[/green] {plot[:200]}{'...' if len(plot) > 200 else ''}")
                console.print()

            if sorted_results:
                selection = None
                while True:
                    try:
                        selection = cli_ui.ask_string("Enter the number of the correct entry, 0 for none, or manual IMDb ID (tt1234567): ")
                    except EOFError:
                        console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                        await cleanup()
                        reset_terminal()
                        sys.exit(1)
                    try:
                        # Check if it's a manual IMDb ID entry
                        if selection.lower().startswith('tt') and len(selection) >= 3:
                            try:
                                manual_imdb_id = selection.lower().replace('tt', '').strip()
                                if manual_imdb_id.isdigit():
                                    console.print(f"[green]Using manual IMDb ID: {selection}[/green]")
                                    return int(manual_imdb_id)
                                else:
                                    console.print("[bold red]Invalid IMDb ID format. Please try again.[/bold red]")
                                    continue
                            except Exception as e:
                                console.print(f"[bold red]Error parsing IMDb ID: {e}. Please try again.[/bold red]")
                                continue

                        # Handle numeric selection
                        selection_int = int(selection)
                        if 1 <= selection_int <= len(sorted_results):
                            selected = sorted_results[selection_int - 1]
                            imdb_id = await safe_get(selected, ["node", "title", "id"], "")
                            if imdb_id:
                                imdbID = int(imdb_id.replace('tt', '').strip())
                                return imdbID
                        elif selection_int == 0:
                            console.print("[bold red]Skipping IMDb[/bold red]")
                            return 0
                        else:
                            console.print("[bold red]Selection out of range. Please try again.[/bold red]")
                    except ValueError:
                        console.print("[bold red]Invalid input. Please enter a number or IMDb ID (tt1234567).[/bold red]")

        else:
            if not unattended:
                try:
                    selection = cli_ui.ask_string("No results found. Please enter a manual IMDb ID (tt1234567) or 0 to skip: ")
                except EOFError:
                    console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                    await cleanup()
                    reset_terminal()
                    sys.exit(1)
                if selection.lower().startswith('tt') and len(selection) >= 3:
                    try:
                        manual_imdb_id = selection.lower().replace('tt', '').strip()
                        if manual_imdb_id.isdigit():
                            console.print(f"[green]Using manual IMDb ID: {selection}[/green]")
                            return int(manual_imdb_id)
                        else:
                            console.print("[bold red]Invalid IMDb ID format. Please try again.[/bold red]")
                    except Exception as e:
                        console.print(f"[bold red]Error parsing IMDb ID: {e}. Please try again.[/bold red]")
            else:
                console.print("[bold red]No IMDb results found in unattended mode. Skipping IMDb.[/bold red]")

    return imdbID if imdbID else 0


async def get_imdb_from_episode(imdb_id, debug=False):
    if not imdb_id or imdb_id == 0:
        return None

    if not str(imdb_id).startswith("tt"):
        try:
            imdb_id_int = int(imdb_id)
            imdb_id = f"tt{imdb_id_int:07d}"
        except Exception:
            imdb_id = f"tt{str(imdb_id).zfill(7)}"

    query = {
        "query": f"""
            {{
                title(id: "{imdb_id}") {{
                    id
                    titleText {{ text }}
                    series {{
                        displayableEpisodeNumber {{
                            displayableSeason {{
                                id
                                season
                                text
                            }}
                            episodeNumber {{
                                id
                                text
                            }}
                        }}
                        nextEpisode {{
                            id
                            titleText {{ text }}
                        }}
                        previousEpisode {{
                            id
                            titleText {{ text }}
                        }}
                        series {{
                            id
                            titleText {{ text }}
                        }}
                    }}
                }}
            }}
        """
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.graphql.imdb.com/",
                json=query,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            if debug:
                print(f"[red]IMDb API error: {e}[/red]")
            return None

    title_data = await safe_get(data, ["data", "title"], {})
    if not title_data:
        return None

    result = {
        "id": await safe_get(title_data, ["id"]),
        "title": await safe_get(title_data, ["titleText", "text"]),
        "series": {},
        "next_episode": {},
        "previous_episode": {},
    }

    series_info = await safe_get(title_data, ["series"], {})
    if series_info:
        displayable = await safe_get(series_info, ["displayableEpisodeNumber"], {})
        season_info = await safe_get(displayable, ["displayableSeason"], {})
        episode_info = await safe_get(displayable, ["episodeNumber"], {})
        result["series"]["season_id"] = await safe_get(season_info, ["id"])
        result["series"]["season"] = await safe_get(season_info, ["season"])
        result["series"]["season_text"] = await safe_get(season_info, ["text"])
        result["series"]["episode_id"] = await safe_get(episode_info, ["id"])
        result["series"]["episode_text"] = await safe_get(episode_info, ["text"])

        # Next episode
        next_ep = await safe_get(series_info, ["nextEpisode"], {})
        result["next_episode"]["id"] = await safe_get(next_ep, ["id"])
        result["next_episode"]["title"] = await safe_get(next_ep, ["titleText", "text"])

        # Previous episode
        prev_ep = await safe_get(series_info, ["previousEpisode"], {})
        result["previous_episode"]["id"] = await safe_get(prev_ep, ["id"])
        result["previous_episode"]["title"] = await safe_get(prev_ep, ["titleText", "text"])

        # Series info
        series_obj = await safe_get(series_info, ["series"], {})
        result["series"]["series_id"] = await safe_get(series_obj, ["id"])
        result["series"]["series_title"] = await safe_get(series_obj, ["titleText", "text"])

    return result
