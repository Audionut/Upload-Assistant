import requests
from difflib import SequenceMatcher
from imdb import Cinemagoer
from src.console import console


async def get_imdb_aka_api(imdb_id, meta):
    if imdb_id == "0":
        return "", None
    if not imdb_id.startswith("tt"):
        imdb_id = f"tt{imdb_id}"
    url = "https://api.graphql.imdb.com/"
    query = {
        "query": f"""
            query {{
                title(id: "{imdb_id}") {{
                    id
                    titleText {{
                        text
                        isOriginalTitle
                    }}
                    originalTitleText {{
                        text
                    }}
                    countriesOfOrigin {{
                        countries {{
                            id
                        }}
                    }}
                }}
            }}
        """
    }

    headers = {
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=query)
    data = response.json()

    # Check if `data` and `title` exist
    title_data = data.get("data", {}).get("title")
    if title_data is None:
        console.print("Title data is missing from response")
        return "", None

    # Extract relevant fields from the response
    aka = title_data.get("originalTitleText", {}).get("text", "")
    is_original = title_data.get("titleText", {}).get("isOriginalTitle", False)
    if meta.get('manual_language'):
        original_language = meta.get('manual_language')
    else:
        original_language = None

    if not is_original and aka:
        aka = f" AKA {aka}"

    return aka, original_language


async def safe_get(data, path, default=None):
    for key in path:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data


async def get_imdb_info_api(imdbID, meta):
    imdb_info = {
        'title': meta['title'],
        'year': meta['year'],
        'aka': '',
        'type': None,
        'runtime': meta.get('runtime', '60'),
        'cover': meta.get('poster'),
    }
    if len(meta.get('tmdb_directors', [])) >= 1:
        imdb_info['directors'] = meta['tmdb_directors']

    if imdbID == "0":
        return imdb_info
    else:
        try:
            if not imdbID.startswith("tt"):
                imdbIDtt = f"tt{imdbID}"
            else:
                imdbIDtt = imdbID
        except Exception:
            return imdb_info
        query = {
            "query": f"""
            query GetTitleInfo {{
                title(id: "{imdbIDtt}") {{
                id
                titleText {{
                    text
                    isOriginalTitle
                }}
                originalTitleText {{
                    text
                }}
                releaseYear {{
                    year
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
                }}
            }}
            """
        }

        url = "https://api.graphql.imdb.com/"
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, json=query, headers=headers)
        data = response.json()

    if response.status_code != 200:
        return imdb_info

    title_data = await safe_get(data, ["data", "title"], {})
    if not data or "data" not in data or "title" not in data["data"]:
        return imdb_info

    imdb_info['imdbID'] = imdbID
    imdb_info['title'] = await safe_get(title_data, ['titleText', 'text'], meta['title'])
    imdb_info['year'] = await safe_get(title_data, ['releaseYear', 'year'], meta['year'])
    original_title = await safe_get(title_data, ['originalTitleText', 'text'], '')
    imdb_info['aka'] = original_title if original_title and original_title != imdb_info['title'] else imdb_info['title']
    imdb_info['type'] = await safe_get(title_data, ['titleType', 'id'], None)
    runtime_seconds = await safe_get(title_data, ['runtime', 'seconds'], 0)
    imdb_info['runtime'] = str(runtime_seconds // 60 if runtime_seconds else 60)
    imdb_info['cover'] = await safe_get(title_data, ['primaryImage', 'url'], meta.get('poster', ''))
    imdb_info['plot'] = await safe_get(title_data, ['plot', 'plotText', 'plainText'], 'No plot available')
    genres = await safe_get(title_data, ['titleGenres', 'genres'], [])
    genre_list = [await safe_get(g, ['genre', 'text'], '') for g in genres]
    imdb_info['genres'] = ', '.join(filter(None, genre_list))
    imdb_info['rating'] = await safe_get(title_data, ['ratingsSummary', 'aggregateRating'], 'N/A')
    imdb_info['directors'] = []
    principal_credits = await safe_get(title_data, ['principalCredits'], [])
    if isinstance(principal_credits, list):
        for pc in principal_credits:
            category_text = await safe_get(pc, ['category', 'text'], '')
            if 'Direct' in category_text:
                credits = await safe_get(pc, ['credits'], [])
                for c in credits:
                    name_id = await safe_get(c, ['name', 'id'], '')
                    if name_id.startswith('nm'):
                        imdb_info['directors'].append(name_id)
                break
        if meta.get('manual_language'):
            imdb_info['original_langauge'] = meta.get('manual_language')

    return imdb_info


async def search_imdb(filename, search_year):
    imdbID = '0'
    ia = Cinemagoer()
    search = ia.search_movie(filename)
    for movie in search:
        if filename in movie.get('title', ''):
            if movie.get('year') == search_year:
                imdbID = str(movie.movieID).replace('tt', '')
    return imdbID


async def imdb_other_meta(self, meta):
    imdb_info = meta['imdb_info'] = await self.get_imdb_info_api(meta['imdb_id'], meta)
    meta['title'] = imdb_info['title']
    meta['year'] = imdb_info['year']
    meta['aka'] = imdb_info['aka']
    meta['poster'] = imdb_info['cover']
    meta['original_language'] = imdb_info['original_language']
    meta['overview'] = imdb_info['plot']
    meta['imdb_rating'] = imdb_info['rating']

    difference = SequenceMatcher(None, meta['title'].lower(), meta['aka'][5:].lower()).ratio()
    if difference >= 0.9 or meta['aka'][5:].strip() == "" or meta['aka'][5:].strip().lower() in meta['title'].lower():
        meta['aka'] = ""
    if f"({meta['year']})" in meta['aka']:
        meta['aka'] = meta['aka'].replace(f"({meta['year']})", "").strip()
    return meta
