from src.console import console
from src.imdb import get_imdb_aka_api, get_imdb_info_api
from src.args import Args
from data.config import config
import tmdbsimple as tmdb
import re
import asyncio
from guessit import guessit
import cli_ui
import anitopy
from datetime import datetime
from difflib import SequenceMatcher
import requests


async def get_tmdb_from_imdb(meta, filename):
    if meta.get('tmdb_manual') is not None:
        meta['tmdb'] = meta['tmdb_manual']
        return meta
    imdb_id = meta['imdb']
    if str(imdb_id)[:2].lower() != "tt":
        imdb_id = f"tt{imdb_id}"
    find = tmdb.Find(id=imdb_id)
    info = find.info(external_source="imdb_id")
    if len(info['movie_results']) >= 1:
        meta['category'] = "MOVIE"
        meta['tmdb'] = info['movie_results'][0]['id']
        meta['original_language'] = info['movie_results'][0].get('original_language')
    elif len(info['tv_results']) >= 1:
        meta['category'] = "TV"
        meta['tmdb'] = info['tv_results'][0]['id']
        meta['original_language'] = info['tv_results'][0].get('original_language')
    else:
        imdb_info = await get_imdb_info_api(imdb_id.replace('tt', ''), meta)
        title = imdb_info.get("title")
        if title is None:
            title = filename
        year = imdb_info.get('year')
        if year is None:
            year = meta['search_year']
        console.print(f"[yellow]TMDb was unable to find anything with that IMDb, searching TMDb for {title}")
        meta = await get_tmdb_id(title, year, meta, meta['category'], imdb_info.get('original title', imdb_info.get('localized title', meta['uuid'])))
        if meta.get('tmdb') in ('None', '', None, 0, '0'):
            if meta.get('mode', 'discord') == 'cli':
                console.print('[yellow]Unable to find a matching TMDb entry')
                tmdb_id = console.input("Please enter tmdb id: ")
                parser = Args(config=config)
                meta['category'], meta['tmdb'] = parser.parse_tmdb_id(id=tmdb_id, category=meta.get('category'))
    await asyncio.sleep(2)
    return meta


async def get_tmdb_id(filename, search_year, meta, category, untouched_filename="", attempted=0):
    search = tmdb.Search()
    try:
        if category == "MOVIE":
            search.movie(query=filename, year=search_year)
        elif category == "TV":
            search.tv(query=filename, first_air_date_year=search_year)
        if meta.get('tmdb_manual') is not None:
            meta['tmdb'] = meta['tmdb_manual']
        else:
            meta['tmdb'] = search.results[0]['id']
            meta['category'] = category
    except IndexError:
        try:
            if category == "MOVIE":
                search.movie(query=filename)
            elif category == "TV":
                search.tv(query=filename)
            meta['tmdb'] = search.results[0]['id']
            meta['category'] = category
        except IndexError:
            if category == "MOVIE":
                category = "TV"
            else:
                category = "MOVIE"
            if attempted <= 1:
                attempted += 1
                meta = await get_tmdb_id(filename, search_year, meta, category, untouched_filename, attempted)
            elif attempted == 2:
                attempted += 1
                meta = await get_tmdb_id(anitopy.parse(guessit(untouched_filename, {"excludes": ["country", "language"]})['title'])['anime_title'], search_year, meta, meta['category'], untouched_filename, attempted)
            if meta['tmdb'] in (None, ""):
                console.print(f"[red]Unable to find TMDb match for {filename}")
                if meta.get('mode', 'discord') == 'cli':
                    tmdb_id = cli_ui.ask_string("Please enter tmdb id in this format: tv/12345 or movie/12345")
                    parser = Args(config=config)
                    meta['category'], meta['tmdb'] = parser.parse_tmdb_id(id=tmdb_id, category=meta.get('category'))
                    meta['tmdb_manual'] = meta['tmdb']
                    return meta

    return meta


async def tmdb_other_meta(meta):

    if meta['tmdb'] == "0":
        try:
            title = guessit(meta['path'], {"excludes": ["country", "language"]})['title'].lower()
            title = title.split('aka')[0]
            meta = await get_tmdb_id(guessit(title, {"excludes": ["country", "language"]})['title'], meta['search_year'], meta)
            if meta['tmdb'] == "0":
                meta = await get_tmdb_id(title, "", meta, meta['category'])
        except Exception:
            if meta.get('mode', 'discord') == 'cli':
                console.print("[bold red]Unable to find tmdb entry. Exiting.")
                exit()
            else:
                console.print("[bold red]Unable to find tmdb entry")
                return meta
    if meta['category'] == "MOVIE":
        movie = tmdb.Movies(meta['tmdb'])
        response = movie.info()
        meta['title'] = response['title']
        if response['release_date']:
            meta['year'] = datetime.strptime(response['release_date'], '%Y-%m-%d').year
        else:
            console.print('[yellow]TMDB does not have a release date, using year from filename instead (if it exists)')
            meta['year'] = meta['search_year']
        external = movie.external_ids()
        if meta.get('imdb', None) is None:
            imdb_id = external.get('imdb_id', "0")
            if imdb_id == "" or imdb_id is None:
                meta['imdb_id'] = '0'
            else:
                meta['imdb_id'] = str(int(imdb_id.replace('tt', ''))).zfill(7)
        else:
            meta['imdb_id'] = str(meta['imdb']).replace('tt', '').zfill(7)
        if meta.get('tvdb_manual'):
            meta['tvdb_id'] = meta['tvdb_manual']
        else:
            if meta.get('tvdb_id', '0') in ['', ' ', None, 'None', '0']:
                meta['tvdb_id'] = external.get('tvdb_id', '0')
                if meta['tvdb_id'] in ["", None, " ", "None"]:
                    meta['tvdb_id'] = '0'
        try:
            videos = movie.videos()
            for each in videos.get('results', []):
                if each.get('site', "") == 'YouTube' and each.get('type', "") == "Trailer":
                    meta['youtube'] = f"https://www.youtube.com/watch?v={each.get('key')}"
                    break
        except Exception:
            console.print('[yellow]Unable to grab videos from TMDb.')

        meta['aka'], original_language = await get_imdb_aka_api(meta['imdb_id'], meta)
        if original_language is not None:
            meta['original_language'] = original_language
        else:
            meta['original_language'] = response['original_language']

        meta['original_title'] = response.get('original_title', meta['title'])
        meta['keywords'] = await get_keywords(movie)
        meta['genres'] = await get_genres(response)
        meta['tmdb_directors'] = await get_directors(movie)
        if meta.get('anime', False) is False:
            meta['mal_id'], meta['aka'], meta['anime'] = await get_anime(response, meta)
        if meta.get('mal') is not None:
            meta['mal_id'] = meta['mal']
        meta['poster'] = response.get('poster_path', "")
        meta['tmdb_poster'] = response.get('poster_path', "")
        meta['overview'] = response['overview']
        meta['tmdb_type'] = 'Movie'
        meta['runtime'] = response.get('episode_run_time', 60)
    elif meta['category'] == "TV":
        tv = tmdb.TV(meta['tmdb'])
        response = tv.info()
        meta['title'] = response['name']
        if response['first_air_date']:
            meta['year'] = datetime.strptime(response['first_air_date'], '%Y-%m-%d').year
        else:
            console.print('[yellow]TMDB does not have a release date, using year from filename instead (if it exists)')
            meta['year'] = meta['search_year']
        external = tv.external_ids()
        if meta.get('imdb', None) is None:
            imdb_id = external.get('imdb_id', "0")
            if imdb_id == "" or imdb_id is None:
                meta['imdb_id'] = '0'
            else:
                meta['imdb_id'] = str(int(imdb_id.replace('tt', ''))).zfill(7)
        else:
            meta['imdb_id'] = str(int(meta['imdb'].replace('tt', ''))).zfill(7)
        if meta.get('tvdb_manual'):
            meta['tvdb_id'] = meta['tvdb_manual']
        else:
            if meta.get('tvdb_id', '0') in ['', ' ', None, 'None', '0']:
                meta['tvdb_id'] = external.get('tvdb_id', '0')
                if meta['tvdb_id'] in ["", None, " ", "None"]:
                    meta['tvdb_id'] = '0'
        try:
            videos = tv.videos()
            for each in videos.get('results', []):
                if each.get('site', "") == 'YouTube' and each.get('type', "") == "Trailer":
                    meta['youtube'] = f"https://www.youtube.com/watch?v={each.get('key')}"
                    break
        except Exception:
            console.print('[yellow]Unable to grab videos from TMDb.')

        # meta['aka'] = f" AKA {response['original_name']}"
        meta['aka'], original_language = await get_imdb_aka_api(meta['imdb_id'], meta)
        if original_language is not None:
            meta['original_language'] = original_language
        else:
            meta['original_language'] = response['original_language']
        meta['original_title'] = response.get('original_name', meta['title'])
        meta['keywords'] = await get_keywords(tv)
        meta['genres'] = await get_genres(response)
        meta['tmdb_directors'] = await get_directors(tv)
        meta['mal_id'], meta['aka'], meta['anime'] = await get_anime(response, meta)
        if meta.get('mal') is not None:
            meta['mal_id'] = meta['mal']
        meta['poster'] = response.get('poster_path', '')
        meta['overview'] = response['overview']

        meta['tmdb_type'] = response.get('type', 'Scripted')
        runtime = response.get('episode_run_time', [60])
        if runtime == []:
            runtime = [60]
        meta['runtime'] = runtime[0]
    if meta['poster'] not in (None, ''):
        meta['poster'] = f"https://image.tmdb.org/t/p/original{meta['poster']}"

    difference = SequenceMatcher(None, meta['title'].lower(), meta['aka'][5:].lower()).ratio()
    if difference >= 0.9 or meta['aka'][5:].strip() == "" or meta['aka'][5:].strip().lower() in meta['title'].lower():
        meta['aka'] = ""
    if f"({meta['year']})" in meta['aka']:
        meta['aka'] = meta['aka'].replace(f"({meta['year']})", "").strip()

    return meta


async def get_keywords(tmdb_info):
    if tmdb_info is not None:
        tmdb_keywords = tmdb_info.keywords()
        if tmdb_keywords.get('keywords') is not None:
            keywords = [f"{keyword['name'].replace(',', ' ')}" for keyword in tmdb_keywords.get('keywords')]
        elif tmdb_keywords.get('results') is not None:
            keywords = [f"{keyword['name'].replace(',', ' ')}" for keyword in tmdb_keywords.get('results')]
        return (', '.join(keywords))
    else:
        return ''


async def get_genres(tmdb_info):
    if tmdb_info is not None:
        tmdb_genres = tmdb_info.get('genres', [])
        if tmdb_genres is not []:
            genres = [f"{genre['name'].replace(',', ' ')}" for genre in tmdb_genres]
        return (', '.join(genres))
    else:
        return ''


async def get_directors(tmdb_info):
    if tmdb_info is not None:
        tmdb_credits = tmdb_info.credits()
        directors = []
        if tmdb_credits.get('cast', []) != []:
            for each in tmdb_credits['cast']:
                if each.get('known_for_department', '') == "Directing":
                    directors.append(each.get('original_name', each.get('name')))
        return directors
    else:
        return ''


async def get_anime(response, meta):
    tmdb_name = meta['title']
    if meta.get('aka', "") == "":
        alt_name = ""
    else:
        alt_name = meta['aka']
    anime = False
    animation = False
    for each in response['genres']:
        if each['id'] == 16:
            animation = True
    if response['original_language'] == 'ja' and animation is True:
        romaji, mal_id, eng_title, season_year, episodes = await get_romaji(tmdb_name, meta.get('mal', None))
        alt_name = f" AKA {romaji}"

        anime = True
        # mal = AnimeSearch(romaji)
        # mal_id = mal.results[0].mal_id
    else:
        mal_id = 0
    if meta.get('mal_id', 0) != 0:
        mal_id = meta.get('mal_id')
    if meta.get('mal') is not None:
        mal_id = meta.get('mal')
    return mal_id, alt_name, anime


async def get_romaji(tmdb_name, mal):
    if mal is None:
        mal = 0
        tmdb_name = tmdb_name.replace('-', "").replace("The Movie", "")
        tmdb_name = ' '.join(tmdb_name.split())
        query = '''
            query ($search: String) {
                Page (page: 1) {
                    pageInfo {
                        total
                    }
                media (search: $search, type: ANIME, sort: SEARCH_MATCH) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    seasonYear
                    episodes
                }
            }
        }
        '''
        # Define our query variables and values that will be used in the query request
        variables = {
            'search': tmdb_name
        }
    else:
        query = '''
            query ($search: Int) {
                Page (page: 1) {
                    pageInfo {
                        total
                    }
                media (idMal: $search, type: ANIME, sort: SEARCH_MATCH) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    seasonYear
                    episodes
                }
            }
        }
        '''
        # Define our query variables and values that will be used in the query request
        variables = {
            'search': mal
        }

    # Make the HTTP Api request
    url = 'https://graphql.anilist.co'
    try:
        response = requests.post(url, json={'query': query, 'variables': variables})
        json = response.json()
        media = json['data']['Page']['media']
    except Exception:
        console.print('[red]Failed to get anime specific info from anilist. Continuing without it...')
        media = []
    if media not in (None, []):
        result = {'title': {}}
        difference = 0
        for anime in media:
            search_name = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", tmdb_name.lower().replace(' ', ''))
            for title in anime['title'].values():
                if title is not None:
                    title = re.sub(u'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]+ (?=[A-Za-z ]+–)', "", title.lower().replace(' ', ''), re.U)
                    diff = SequenceMatcher(None, title, search_name).ratio()
                    if diff >= difference:
                        result = anime
                        difference = diff

        romaji = result['title'].get('romaji', result['title'].get('english', ""))
        mal_id = result.get('idMal', 0)
        eng_title = result['title'].get('english', result['title'].get('romaji', ""))
        season_year = result.get('season_year', "")
        episodes = result.get('episodes', 0)
    else:
        romaji = eng_title = season_year = ""
        episodes = mal_id = 0
    if mal_id in [None, 0]:
        mal_id = mal
    if not episodes:
        episodes = 0
    return romaji, mal_id, eng_title, season_year, episodes


async def get_tmdb_imdb_from_mediainfo(mediainfo, category, is_disc, tmdbid, imdbid):
    if not is_disc:
        if mediainfo['media']['track'][0].get('extra'):
            extra = mediainfo['media']['track'][0]['extra']
            for each in extra:
                if each.lower().startswith('tmdb'):
                    parser = Args(config=config)
                    category, tmdbid = parser.parse_tmdb_id(id=extra[each], category=category)
                if each.lower().startswith('imdb'):
                    try:
                        imdbid = str(int(extra[each].replace('tt', ''))).zfill(7)
                    except Exception:
                        pass
    return category, tmdbid, imdbid


async def daily_to_tmdb_season_episode(tmdbid, date):
    show = tmdb.TV(tmdbid)
    seasons = show.info().get('seasons')
    season = 1
    episode = 1
    date = datetime.fromisoformat(str(date))
    for each in seasons:
        air_date = datetime.fromisoformat(each['air_date'])
        if air_date <= date:
            season = int(each['season_number'])
    season_info = tmdb.TV_Seasons(tmdbid, season).info().get('episodes')
    for each in season_info:
        if str(each['air_date']) == str(date.date()):
            episode = int(each['episode_number'])
            break
    else:
        console.print(f"[yellow]Unable to map the date ([bold yellow]{str(date)}[/bold yellow]) to a Season/Episode number")
    return season, episode
