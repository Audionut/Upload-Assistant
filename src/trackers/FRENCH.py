# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# https://github.com/Audionut/Upload-Assistant/tree/master

import aiofiles
import httpx
from typing import Any, Optional, cast
from data.config import config
from unidecode import unidecode
#from src.console import console

async def build_audio_string(meta: dict[str, Any]) -> str:

    #        Priority Order:
    #        1. MULYi: Exactly 2 audio tracks Dual would be nice
    #        2. MULTi: 3 audio tracks
    #        3. VOSTFR: Single audio (original lang) + French subs + NO French audio
    #        4. VO: Single audio (original lang) + NO French subs + NO French audio

    audio_tracks = await get_audio_tracks(meta, True)
    if not audio_tracks:
        return ''

    audio_langs = await extract_audio_languages(audio_tracks, meta)
    if not audio_langs:
        return ''

    language = ""
    original_lang = await get_original_language(meta)
    has_french_audio = 'FRA' in audio_langs
    has_French_subs = await has_french_subs(meta)
    num_audio_tracks = len(audio_tracks)

    # DUAL - Exactly 2 audios
    if num_audio_tracks == 2 and has_french_audio:
        language = "MULTi"

    # MULTI - 3+ audios
    if num_audio_tracks >= 3 and has_french_audio:
        language = "MULTi"

    # VOSTFR - Single audio (original) + French subs + NO French audio
    if num_audio_tracks == 1 and original_lang and not has_french_audio and has_French_subs and audio_langs[0] == original_lang:
        language = "VOSTFR"

    # VO - Single audio (original) + NO French subs + NO French audio
    if num_audio_tracks == 1 and original_lang and not has_french_audio and not has_French_subs and audio_langs[0] == original_lang:
        language = "VO"

    # FRENCH. - Single audio FRENCH
    if num_audio_tracks == 1 and has_french_audio and audio_langs[0] == original_lang:
        language = "FRENCH"

    return language


async def get_extra_french_tag(meta: dict[str, Any], check_origin: bool) -> str:
    audio_track = await get_audio_tracks(meta, True)

    vfq = ""
    vff = ""
    vf = ""
    origincountry = meta.get("origin_country", "")

    for _, item in enumerate(audio_track):
        title = (item.get("Title") or "").lower()
        lang = item.get('Language', "").lower()

        if lang == "fr-ca" or "vfq" in title:
            vfq = True
        elif lang == "fr-fr" or "vff" in title:
            vff = True
        elif lang == "fr" or "vfi" in title:
            vf = True

    if vff and vfq:
        return 'VF2'
    elif vfq:
        if "CA" in origincountry and check_origin:
            return 'VOQ'
        else:
            return 'VFQ'
    elif vff:
        if "FR" in origincountry and check_origin:
            return 'VOF'
        else:
            return 'VFF'
    elif vf:
        if "FR" in origincountry and check_origin:
            return 'VOF'
        else:
            return 'VFI'
    else:
        return ""


async def get_audio_tracks(meta: dict[str, Any], filter: bool) -> list[dict[str, Any]]:

    if 'mediainfo' not in meta or 'media' not in meta['mediainfo']:
        return []

    media_info = meta['mediainfo']
    if not isinstance(media_info, dict):
        return []
    media_info_dict = cast(dict[str, Any], media_info)
    media = media_info_dict.get('media')
    if not isinstance(media, dict):
        return []

    media_dict = cast(dict[str, Any], media)
    tracks = media_dict.get('track', [])
    if not isinstance(tracks, list):
        return []

    audio_tracks: list[dict[str, Any]] = []
    tracks_list = cast(list[Any], tracks)
    for track in tracks_list:
        if isinstance(track, dict):
            track_dict = cast(dict[str, Any], track)
            if track_dict.get('@type') == 'Audio':
                if filter:
                    # or not "audio description" in str(track_dict.get('Title') or '').lower() #audio description, AD, description
                    if "commentary" not in str(track_dict.get('Title') or '').lower():
                        audio_tracks.append(track_dict)
                else:
                    audio_tracks.append(track_dict)

    return audio_tracks


async def get_subtitle_tracks(meta: dict[str, Any]) -> list[dict[str, Any]]:

    if 'mediainfo' not in meta or 'media' not in meta['mediainfo']:
        return []

    media_info = meta['mediainfo']
    if not isinstance(media_info, dict):
        return []
    media_info_dict = cast(dict[str, Any], media_info)
    media = media_info_dict.get('media')
    if not isinstance(media, dict):
        return []

    media_dict = cast(dict[str, Any], media)
    tracks = media_dict.get('track', [])
    if not isinstance(tracks, list):
        return []

    audio_tracks: list[dict[str, Any]] = []
    tracks_list = cast(list[Any], tracks)
    for track in tracks_list:
        if isinstance(track, dict):
            track_dict = cast(dict[str, Any], track)
            if track_dict.get('@type') == 'Text':
                audio_tracks.append(track_dict)

    return audio_tracks


async def get_video_tracks(meta: dict[str, Any]) -> list[dict[str, Any]]:

    if 'mediainfo' not in meta or 'media' not in meta['mediainfo']:
        return []

    media_info = meta['mediainfo']
    if not isinstance(media_info, dict):
        return []
    media_info_dict = cast(dict[str, Any], media_info)
    media = media_info_dict.get('media')
    if not isinstance(media, dict):
        return []

    media_dict = cast(dict[str, Any], media)
    tracks = media_dict.get('track', [])
    if not isinstance(tracks, list):
        return []

    audio_tracks: list[dict[str, Any]] = []
    tracks_list = cast(list[Any], tracks)
    for track in tracks_list:
        if isinstance(track, dict):
            track_dict = cast(dict[str, Any], track)
            if track_dict.get('@type') == 'Video':
                audio_tracks.append(track_dict)

    return audio_tracks


async def extract_audio_languages(audio_tracks: list[dict[str, Any]], meta: dict[str, Any]) -> list[str]:

    audio_langs: list[str] = []

    for track in audio_tracks:
        lang = track.get('Language', '')
        if lang:
            lang_code = await map_language(str(lang))
            if lang_code and lang_code not in audio_langs:
                audio_langs.append(lang_code)

    if not audio_langs and meta.get('audio_languages'):
        audio_languages = meta.get('audio_languages')
        audio_languages_list: list[Any] = cast(
            list[Any], audio_languages) if isinstance(audio_languages, list) else []
        for lang in audio_languages_list:
            lang_code = await map_language(str(lang))
            if lang_code and lang_code not in audio_langs:
                audio_langs.append(lang_code)

    return audio_langs


async def map_language(lang: str) -> str:
    if not lang:
        return ''

    lang_map = {
        'spa': 'ESP', 'es': 'ESP', 'spanish': 'ESP', 'español': 'ESP', 'castellano': 'ESP', 'es-es': 'ESP',
        'eng': 'ENG', 'en': 'ENG', 'english': 'ENG', 'en-us': 'ENG', 'en-gb': 'ENG',
        'lat': 'LAT', 'latino': 'LAT', 'latin american spanish': 'LAT', 'es-mx': 'LAT', 'es-419': 'LAT',
        'fre': 'FRA', 'fra': 'FRA', 'fr': 'FRA', 'french': 'FRA', 'français': 'FRA', 'fr-fr': 'FRA', 'fr-ca': 'FRA',
        'ger': 'ALE', 'deu': 'ALE', 'de': 'ALE', 'german': 'ALE', 'deutsch': 'ALE',
        'jpn': 'JAP', 'ja': 'JAP', 'japanese': 'JAP', '日本語': 'JAP',
        'kor': 'COR', 'ko': 'COR', 'korean': 'COR', '한국어': 'COR',
        'ita': 'ITA', 'it': 'ITA', 'italian': 'ITA', 'italiano': 'ITA',
        'por': 'POR', 'pt': 'POR', 'portuguese': 'POR', 'português': 'POR', 'pt-br': 'POR', 'pt-pt': 'POR',
        'chi': 'CHI', 'zho': 'CHI', 'zh': 'CHI', 'chinese': 'CHI', 'mandarin': 'CHI', '中文': 'CHI', 'zh-cn': 'CHI',
        'rus': 'RUS', 'ru': 'RUS', 'russian': 'RUS', 'русский': 'RUS',
        'ara': 'ARA', 'ar': 'ARA', 'arabic': 'ARA',
        'hin': 'HIN', 'hi': 'HIN', 'hindi': 'HIN',
        'tha': 'THA', 'th': 'THA', 'thai': 'THA',
        'vie': 'VIE', 'vi': 'VIE', 'vietnamese': 'VIE',
    }

    lang_lower = str(lang).lower().strip()
    mapped = lang_map.get(lang_lower)

    if mapped:
        return mapped

    return lang.upper()[:3] if len(lang) >= 3 else lang.upper()


async def get_original_language(meta: dict[str, Any]) -> Optional[str]:

    original_lang = None

    if meta.get('original_language'):
        original_lang = str(meta['original_language'])

    if not original_lang:
        imdb_info_raw = meta.get('imdb_info')
        imdb_info: dict[str, Any] = cast(
            dict[str, Any], imdb_info_raw) if isinstance(imdb_info_raw, dict) else {}
        imdb_lang: Any = imdb_info.get('language')

        if isinstance(imdb_lang, list):
            imdb_lang_list = cast(list[Any], imdb_lang)
            imdb_lang = imdb_lang_list[0] if imdb_lang_list else ''

        if imdb_lang:
            if isinstance(imdb_lang, dict):
                imdb_lang_dict = cast(dict[str, Any], imdb_lang)
                imdb_lang_text = imdb_lang_dict.get('text', '')
                original_lang = str(imdb_lang_text).strip()
            elif isinstance(imdb_lang, str):
                original_lang = imdb_lang.strip()
            else:
                original_lang = str(imdb_lang).strip()

    if original_lang:
        return await map_language(str(original_lang))

    return None


async def has_french_subs(meta: dict[str, Any]) -> bool:

    if 'mediainfo' not in meta or 'media' not in meta['mediainfo']:
        return False
    media_info = meta['mediainfo']
    if not isinstance(media_info, dict):
        return False
    media_info_dict = cast(dict[str, Any], media_info)
    media = media_info_dict.get('media')
    if not isinstance(media, dict):
        return False
    media_dict = cast(dict[str, Any], media)
    tracks = media_dict.get('track', [])
    if not isinstance(tracks, list):
        return False

    tracks_list = cast(list[Any], tracks)
    for track in tracks_list:
        if not isinstance(track, dict):
            continue
        track_dict = cast(dict[str, Any], track)
        if track_dict.get('@type') == 'Text':
            lang = track_dict.get('Language', '')
            lang = lang.lower() if isinstance(lang, str) else ''

            title = track_dict.get('Title', '')
            title = title.lower() if isinstance(title, str) else ''

            if lang in ["french", "fre", "fra", "fr", "français", "francais", 'fr-fr', 'fr-ca']:
                return True
            if 'french' in title or 'français' in title or 'francais' in title:
                return True

    return False


async def map_audio_codec(audio_track: dict[str, Any]) -> str:
    codec = str(audio_track.get('Format', '')).upper()

    if 'atmos' in str(audio_track.get('Format_AdditionalFeatures', '')).lower():
        return 'Atmos'

    codec_map = {
        'AAC LC': 'AAC LC', 'AAC': 'AAC', 'AC-3': 'AC3', 'AC3': 'AC3',
        'E-AC-3': 'EAC3', 'EAC3': 'EAC3', 'DTS': 'DTS',
        'DTS-HD MA': 'DTS-HD MA', 'DTS-HD HRA': 'DTS-HD HRA',
        'TRUEHD': 'TrueHD', 'MLP FBA': 'MLP', 'PCM': 'PCM',
        'FLAC': 'FLAC', 'OPUS': 'OPUS', 'MP3': 'MP3',
    }

    return codec_map.get(codec, codec)


async def get_audio_channels(audio_track: dict[str, Any]) -> str:
    channels = audio_track.get('Channels', '')
    channel_map = {
        '1': 'Mono', '2': '2.0', '3': '3.0',
        '4': '3.1', '5': '5.0', '6': '5.1', '8': '7.1',
    }
    return channel_map.get(str(channels), '0')


async def get_audio_name(meta: dict[str, Any]) -> str:
    audio_track = await get_audio_tracks(meta, True)
    if not audio_track:
        return ""
    has_french_audio = any(item.get('Language', '') in (
        'fr', 'fr-fr', 'fr-ca')for item in audio_track)
    audio_parts: list[str] = []
    if has_french_audio:
        for _, item in enumerate(audio_track):
            if item['Language'] == "fr" or item['Language'] == "fr-fr" or item['Language'] == "fr-ca":
                codec = await map_audio_codec(item)
                channels = await get_audio_channels(item)
                audio_parts.append(f"{codec} {channels}")
                audio = ' '.join(audio_parts)
                return audio
    else:
        for _, item in enumerate(audio_track):
            if item.get('Default') == "Yes":
                codec = await map_audio_codec(item)
                channels = await get_audio_channels(item)
                audio_parts.append(f"{codec} {channels}")
                audio = ' '.join(audio_parts)
                return audio
    return ""


async def translate_genre(text: str) -> str:
    mapping = {
        'Action': 'Action',
        'Adventure': 'Aventure',
        'Fantasy': 'Fantastique',
        'History': 'Histoire',
        'Horror': 'Horreur',
        'Music': 'Musique',
        'Romance': 'Romance',
        'Science Fiction': 'Science-fiction',
        'TV Movie': 'Téléfilm',
        'Thriller': 'Thriller',
        'War': 'Guerre',
        'Action & Adventure': 'Action & aventure',
        'Animation': 'Animation',
        'Comedy': 'Comédie',
        'Crime': 'Policier',
        'Documentary': 'Documentaire',
        'Drama': 'Drame',
        'Family': 'Famille',
        'Kids': 'Enfants',
        'Mystery': 'Mystère',
        'News': 'Actualités',
        'Reality': 'Réalité',
        'Sci-Fi & Fantasy': 'Science-fiction & fantastique',
        'Soap': 'Feuilletons',
        'Sport': 'Sport',
        'Talk': 'Débats',
        'War & Politics': 'Guerre & politique',
        'Western': 'Western'
    }
    result = []

    for word in map(str.strip, text.split(",")):
        if word in mapping:
            result.append(mapping[word])
        else:
            result.append(f"*{word}*")

    return ", ".join(result)


async def clean_name(input_str: str) -> str:
    ascii_str = unidecode(input_str)
    invalid_char = set('<>"/\\|?*')  # ! . , : ; @ # $ % ^ & */ \" '_
    result = []
    for char in ascii_str:
        if char in invalid_char:
            continue
        result.append(char)

    return "".join(result)


async def get_translation_fr(meta: dict[str, Any]) -> tuple[str, str]:

    fr_title = meta.get("frtitle")
    fr_overwiew = meta.get("froverview")
    if fr_title and fr_overwiew:
        return fr_title, fr_overwiew

    # Try to get from IMDb with priority: country match, then language match
    imdb_info_raw = meta.get('imdb_info')
    imdb_info: dict[str, Any] = cast(
        dict[str, Any], imdb_info_raw) if isinstance(imdb_info_raw, dict) else {}
    akas_raw = imdb_info.get('akas', [])
    akas: list[Any] = cast(list[Any], akas_raw) if isinstance(
        akas_raw, list) else []
    french_title = None
    country_match = None
    language_match = None

    for aka in akas:
        if isinstance(aka, dict):
            aka_dict = cast(dict[str, Any], aka)
            if aka_dict.get("country") in ["France", "FR"]:
                country_match = aka_dict.get("title")
                break  # Country match takes priority
            elif aka_dict.get("language") in ["France", "French", "FR"] and not language_match:
                language_match = aka_dict.get("title")

    french_title = country_match or language_match

    tmdb_id = int(meta["tmdb_id"])
    category = str(meta["category"])
    tmdb_title, tmdb_overview = await get_tmdb_translations(tmdb_id, category, "fr")
    meta["frtitle"] = french_title or tmdb_title
    meta["froverview"] = tmdb_overview

    if french_title is not None:
        return french_title, tmdb_overview
    else:    
        return tmdb_title, tmdb_overview


async def get_tmdb_translations(tmdb_id: int, category: str, target_language: str) -> tuple[str, str]:

    endpoint = "movie" if category == "MOVIE" else "tv"
    url = f"https://api.themoviedb.org/3/{endpoint}/{tmdb_id}/translations"
    tmdb_api_key = config['DEFAULT'].get('tmdb_api', False)
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(url, params={"api_key": tmdb_api_key})
            response.raise_for_status()
            data = response.json()

            # Look for target language translation
            for translation in data.get('translations', []):
                if translation.get('iso_639_1') == target_language:
                    translated_data = translation.get('data', {})
                    translated_desc = translated_data.get('overview')
                    translated_title = translated_data.get(
                        'title') or translated_data.get('name')

                    return translated_title or "", translated_desc or ""
            return "", ""

        except Exception:
            return "", ""

# unknow return type


async def get_desc_full(meta: dict[str, Any], tracker) -> str:
    """Return a full tracker description.

    The function used to build the description piece by piece, but now we prefer
    to render a Jinja2 template.  A few points:

    * If ``meta['description_template']`` is set it will be used first.
    * Otherwise a default template named after the tracker (e.g. ``C411``) is
      looked up under ``data/templates``.  A generic ``FRENCH`` template is also
      provided for shared structure.
    * If no template is found we fall back to the original hard‑coded logic so
      existing behaviour remains unchanged.
    """
    import os
    from jinja2 import Template

    # gather information that will be useful to both the template and the
    # legacy builder
    video_track = await get_video_tracks(meta)
    if not video_track:
        return ''

    mbps = 0.0
    if video_track and video_track[0].get('BitRate'):
        try:
            mbps = int(video_track[0]['BitRate']) / 1_000_000
        except (ValueError, TypeError):
            pass

    title, description = await get_translation_fr(meta)
    genre = await translate_genre(meta['combined_genres'])
    audio_tracks = await get_audio_tracks(meta, False)
    if not audio_tracks:
        return ''

    subtitle_tracks = await get_subtitle_tracks(meta)
    size_bytes = int(meta.get('source_size') or 0)
    size_gib = size_bytes / (1024 ** 3)
    poster = str(meta.get('poster', ""))
    year = str(meta.get('year', ""))
    original_title = str(meta.get('original_title', ""))
    pays = str(meta.get('imdb_info', {}).get('country', ''))
    release_date = str(meta.get('release_date', ""))
    video_duration = str(meta.get('video_duration', ""))
    source = str(meta.get('source', ""))
    type = str(meta.get('type', ""))
    resolution = str(meta.get('resolution', ""))
    container = str(meta.get('container', ""))
    video_codec = str(meta.get('video_codec', ""))
    hdr = str(meta.get('hdr', ""))
    if "DV" in hdr:
        if video_track and video_track[0].get('HDR_Format_Profile'):
            try:
                dv = str(video_track[0]['HDR_Format_Profile']).replace('dvhe.0', '').replace('/', '').strip()
                hdr = hdr.replace('DV', '')
                hdr = f"{hdr} DV{dv}"
            except (ValueError, TypeError):
                pass

    tag = str(meta.get('tag', "")).replace('-', '')
    service_longname = str(meta.get('service_longname', ""))
    season = str(meta.get('season_int', ''))
    episode = str(meta.get('episode_int', ''))

    # pre‑compute the lines that were previously appended to ``desc_parts``
    audio_lines: list[str] = []
    for obj in audio_tracks:
        if isinstance(obj, dict):
            bitrate = obj.get('BitRate')
            kbps = int(bitrate) / 1_000 if bitrate else 0

            flags: list[str] = []
            if obj.get("Forced") == "Yes":
                flags.append("Forced")
            if obj.get("Default") == "Yes":
                flags.append("Default")
            if "commentary" in str(obj.get('Title')).lower():
                flags.append("Commentary")
            if " ad" in str(obj.get('Title')).lower():
                flags.append("Audio Description")

            line = f"{obj['Language']} / {obj['Format']} / {obj['Channels']}ch / {kbps:.2f}KB/s"
            if flags:
                line += " / " + " / ".join(flags)
            audio_lines.append(line)
        else:
            audio_lines.append(f"*{obj}*")

    subtitle_lines: list[str] = []
    if subtitle_tracks:
        for obj in subtitle_tracks:
            if isinstance(obj, dict):
                flags: list[str] = []
                if obj.get("Forced") == "Yes":
                    flags.append("Forced")
                if obj.get("Default") == "Yes":
                    flags.append("Default")
                line = f"{obj['Language']} / {obj['Format']}"
                if flags:
                    line += " / " + " / ".join(flags)
                subtitle_lines.append(line)
            else:
                subtitle_lines.append(f"*{obj}*")

    images = meta[f'{tracker}_images_key'] if f'{tracker}_images_key' in meta else meta['image_list']

    context = {
        'poster': poster,
        'title': title,
        'year': year,
        'season': season,
        'episode': episode,
        'original_title': original_title,
        'pays': pays,
        'genre': genre,
        'release_date': release_date,
        'video_duration': video_duration,
        'imdb_url': meta.get('imdb_info', {}).get('imdb_url', ''),
        'tmdb': meta.get('tmdb', ''),
        'category': meta.get('category', ''),
        'tvdb_id': meta.get('tvdb_id', ''),
        'tvmaze_id': meta.get('tvmaze_id', ''),
        'mal_id': meta.get('mal_id', ''),
        'description': description,
        'audio_lines': audio_lines,
        'subtitle_lines': subtitle_lines,
        'source': source,
        'service_longname': service_longname,
        'type': type,
        'resolution': resolution,
        'container': container,
        'video_codec': video_codec,
        'hdr': hdr,
        'mbps': mbps,
        'tag': tag,
        'size_gib': size_gib,
        'images': images,
        'signature': meta.get('ua_signature', ''),
    }

    # try to render a template if one exists
    # determine which template to use; prefer explicit setting, then
    # tracker-specific file, then fall back to a generic "FRENCH" template.
    description_text = ''
    primary = meta.get('description_template') or tracker
    template_path = os.path.abspath(f"{meta['base_dir']}/data/templates/{primary}.txt")

    if not os.path.exists(template_path):
        # try the shared french template
        template_path = os.path.abspath(f"{meta['base_dir']}/data/templates/FRENCH.txt")

    if os.path.exists(template_path):
        
        async with aiofiles.open(template_path, 'r', encoding='utf-8') as description_file:
            template_content = await description_file.read()
        try:
            description_text = Template(template_content).render(**context)
        except Exception:
            # if rendering fails fall back to the old builder below
            description_text = ''

    if not description_text:
        # fallback to the original behaviour (preserve before change)
        desc_parts: list[str] = []
        desc_parts.append(f"[img]{poster}[/img]")
        desc_parts.append(
            f"[b][font=Verdana][color=#3d85c6][size=29]{title}[/size][/font]")
        desc_parts.append(f"[size=18]{year}[/size][/color][/b]")

        if meta['category'] == "TV":
            season = f"S{season}" if season else ""
            episode = f"E{episode}" if episode else ""
            desc_parts.append(f"[b][size=18]{season}{episode}[/size][/b]")

        desc_parts.append(
            f"[font=Verdana][size=13][b][color=#3d85c6]Titre original :[/color][/b] [i]{original_title}[/i][/size][/font]")
        desc_parts.append(
            f"[b][color=#3d85c6]Pays :[/color][/b] [i]{pays}[/i]")
        desc_parts.append(f"[b][color=#3d85c6]Genres :[/color][/b] [i]{genre}[/i]")
        desc_parts.append(
            f"[b][color=#3d85c6]Date de sortie :[/color][/b] [i]{release_date}[/i]")

        if meta['category'] == 'MOVIE':
            desc_parts.append(
                f"[b][color=#3d85c6]Durée :[/color][/b] [i]{video_duration} Minutes[/i]")

        if meta['imdb_id']:
            desc_parts.append(f"[url={meta.get('imdb_info', {}).get('imdb_url', '')}]IMDb[/url]")
        if meta['tmdb']:
            desc_parts.append(
                f"[url=https://www.themoviedb.org/{str(meta['category'].lower())}/{str(meta['tmdb'])}]TMDB[/url]")
        if meta['tvdb_id']:
            desc_parts.append(
                f"[url=https://www.thetvdb.com/?id={str(meta['tvdb_id'])}&tab=series]TVDB[/url]")
        if meta['tvmaze_id']:
            desc_parts.append(
                f"[url=https://www.tvmaze.com/shows/{str(meta['tvmaze_id'])}]TVmaze[/url]")
        if meta['mal_id']:
            desc_parts.append(
                f"[url=https://myanimelist.net/anime/{str(meta['mal_id'])}]MyAnimeList[/url]")

        desc_parts.append("[img]https://i.imgur.com/W3pvv6q.png[/img]")
        desc_parts.append(f"{description}")
        desc_parts.append("[img]https://i.imgur.com/KMZsqZn.png[/img]")
        desc_parts.append(
            f"[b][color=#3d85c6]Source :[/color][/b] [i]{source}   {service_longname}[/i]")
        desc_parts.append(
            f"[b][color=#3d85c6]Type :[/color][/b] [i]{type}[/i]")
        desc_parts.append(
            f"[b][color=#3d85c6]Résolution vidéo :[/color][/b][i]{resolution}[/i]")
        desc_parts.append(
            f"[b][color=#3d85c6]Format vidéo :[/color][/b] [i]{container}[/i]")
        desc_parts.append(
            f"[b][color=#3d85c6]Codec vidéo :[/color][/b] [i]{video_codec}   {hdr}[/i]")
        desc_parts.append(
            f"[b][color=#3d85c6]Débit vidéo :[/color][/b] [i]{mbps:.2f} MB/s[/i]")
        desc_parts.append("[b][color=#3d85c6] Audio(s) :[/color][/b]")
        desc_parts.extend(audio_lines)
        if subtitle_lines:
            desc_parts.append("[b][color=#3d85c6]Sous-titres :[/color][/b]")
            desc_parts.extend(subtitle_lines)
        desc_parts.append(f"[b][color=#3d85c6]Team :[/color][/b] [i]{tag}[/i]")
        desc_parts.append(f"[b][color=#3d85c6]  Taille totale :[/color][/b] {size_gib:.2f} GB")
        if images:
            screenshots_block = ''
            for image in images:
                screenshots_block += f"[img]{image['raw_url']}[/img]\n"
            desc_parts.append(screenshots_block)
        desc_parts.append(
            f"[url=https://github.com/Audionut/Upload-Assistant]{meta['ua_signature']}[/url]")
        description_text = '\n'.join(part for part in desc_parts if part.strip())

    # persist to disk for debugging/inspection
    async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]DESCRIPTION.json", 'w', encoding='utf-8') as description_file:
        await description_file.write(description_text)

    return description_text
