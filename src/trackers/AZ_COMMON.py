import asyncio
import httpx
from bs4 import BeautifulSoup
from src.console import console


class AZ_COMMON():
    def __init__(self, config):
        self.config = config

    def get_resolution(self, meta):
        resolution = ''
        width, height = None, None

        try:
            if meta.get('is_disc') == 'BDMV':
                resolution_str = meta.get('resolution', '')
                height_num = int(resolution_str.lower().replace('p', '').replace('i', ''))
                height = str(height_num)
                width = str(round((16 / 9) * height_num))
            else:
                tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
                if len(tracks) > 1:
                    video_mi = tracks[1]
                    width = video_mi.get('Width')
                    height = video_mi.get('Height')
        except (ValueError, TypeError, KeyError, IndexError):
            return ''

        if width and height:
            resolution = f'{width}x{height}'

        return resolution

    def get_video_quality(self, meta):
        resolution = meta.get('resolution')

        keyword_map = {
            '1080i': '7',
            '1080p': '3',
            '2160p': '6',
            '4320p': '8',
            '720p': '2',
        }

        return keyword_map.get(resolution.lower())

    async def get_media_code(self, meta, tracker, tracker_url, session, auth_token):
        self.media_code = ''

        if meta['category'] == 'MOVIE':
            category = '1'
        elif meta['category'] == 'TV':
            category = '2'
        else:
            return False

        search_term = ''
        imdb_info = meta.get('imdb_info', {})
        imdb_id = imdb_info.get('imdbID') if isinstance(imdb_info, dict) else None
        tmdb_id = meta.get('tmdb')
        title = meta['title']

        if imdb_id:
            search_term = imdb_id
        else:
            search_term = title

        ajax_url = f'{tracker_url}/ajax/movies/{category}?term={search_term}'

        headers = {
            'Referer': f"{tracker_url}/upload/{meta['category'].lower()}",
            'X-Requested-With': 'XMLHttpRequest'
        }

        for attempt in range(2):
            try:
                if attempt == 1:
                    console.print(f'{tracker}: Trying to search again by ID after adding to media to database...\n')
                    await asyncio.sleep(5)  # Small delay to ensure the DB has been updated

                response = await session.get(ajax_url, headers=headers)
                response.raise_for_status()
                data = response.json()

                if data.get('data'):
                    match = None
                    for item in data['data']:
                        if imdb_id and item.get('imdb') == imdb_id:
                            match = item
                            break
                        elif not imdb_id and item.get('tmdb') == str(tmdb_id):
                            match = item
                            break

                    if match:
                        self.media_code = str(match['id'])
                        if attempt == 1:
                            console.print(f"{tracker}: [green]Found new ID at:[/green] {self.base_url}/{meta['category'].lower()}/{self.media_code}")
                        return True

            except Exception as e:
                console.print(f'{tracker}: Error while trying to fetch media code in attempt {attempt + 1}: {e}')
                break

            if attempt == 0 and not self.media_code:
                console.print(f"\n[{tracker}] The media ([yellow]IMDB:{imdb_id}[/yellow] [blue]TMDB:{tmdb_id}[/blue]) appears to be missing from the site's database.")

                user_choice = input(f"{tracker}: Do you want to add '{title}' to the site database? (y/n): \n").lower()

                if user_choice in ['y', 'yes']:
                    console.print(f'{tracker}: Trying to add to database...')
                    added_successfully = await self.add_media_to_db(meta, title, category, imdb_id, tmdb_id, auth_token)
                    if not added_successfully:
                        console.print(f'{tracker}: Failed to add media. Aborting.')
                        break
                else:
                    console.print(f'{tracker}: User chose not to add media. Aborting.')
                    break

        if not self.media_code:
            console.print(f'{tracker}: Unable to get media code.')

        return bool(self.media_code)

    async def add_media_to_db(self, meta, title, category, imdb_id, tmdb_id, tracker, tracker_url, session, auth_token):
        data = {
            '_token': auth_token,
            'type_id': category,
            'title': title,
            'imdb_id': imdb_id if imdb_id else '',
            'tmdb_id': tmdb_id if tmdb_id else '',
        }

        if meta['category'] == 'TV':
            tvdb_id = meta.get('tvdb')
            if tvdb_id:
                data['tvdb_id'] = str(tvdb_id)

        url = f"{tracker_url}/add/{meta['category'].lower()}"

        headers = {
            'Referer': f'{tracker_url}/upload',
        }

        try:
            response = await session.post(url, data=data, headers=headers)
            if response.status_code == 302:
                console.print(f'{tracker}: The attempt to add the media to the database appears to have been successful..')
                return True
            else:
                console.print(f'{tracker}: Error adding media to the database. Status: {response.status}')
                return False
        except Exception as e:
            console.print(f'{tracker}: Exception when trying to add media to the database: {e}')
            return False

    async def search_existing(self, meta, tracker, tracker_url, media_code, session):
        if meta.get('resolution') == '2160p':
            resolution = 'UHD'
        elif meta.get('resolution') in ('720p', '1080p'):
            resolution = meta.get('resolution')
        else:
            resolution = 'all'

        page_url = f'{tracker_url}/movies/torrents/{media_code}?quality={resolution}'

        dupes = []

        visited_urls = set()

        while page_url and page_url not in visited_urls:

            visited_urls.add(page_url)

            try:
                response = await session.get(page_url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                torrent_links = soup.find_all('a', class_='torrent-filename')

                for link in torrent_links:
                    dupes.append(link.get_text(strip=True))

                # Finds the next page
                next_page_tag = soup.select_one('a[rel="next"]')
                if next_page_tag and 'href' in next_page_tag.attrs:
                    page_url = next_page_tag['href']
                else:
                    # if no rel="next", we are at the last page
                    page_url = None

            except httpx.RequestError as e:
                console.log(f'{tracker}: Failed to search for duplicates. {e.request.url}: {e}')
                return dupes

        return dupes

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    def language_map(self, tracker):
        self.all_lang_map = {
            ('Abkhazian', 'abk', 'ab'): '1',
            ('Afar', 'aar', 'aa'): '2',
            ('Afrikaans', 'afr', 'af'): '3',
            ('Akan', 'aka', 'ak'): '4',
            ('Albanian', 'sqi', 'sq'): '5',
            ('Amharic', 'amh', 'am'): '6',
            ('Arabic', 'ara', 'ar'): '7',
            ('Aragonese', 'arg', 'an'): '8',
            ('Armenian', 'hye', 'hy'): '9',
            ('Assamese', 'asm', 'as'): '10',
            ('Avaric', 'ava', 'av'): '11',
            ('Avestan', 'ave', 'ae'): '12',
            ('Aymara', 'aym', 'ay'): '13',
            ('Azerbaijani', 'aze', 'az'): '14',
            ('Bambara', 'bam', 'bm'): '15',
            ('Bashkir', 'bak', 'ba'): '16',
            ('Basque', 'eus', 'eu'): '17',
            ('Belarusian', 'bel', 'be'): '18',
            ('Bengali', 'ben', 'bn'): '19',
            ('Bihari languages', 'bih', 'bh'): '20',
            ('Bislama', 'bis', 'bi'): '21',
            ('Bokmål, Norwegian', 'nob', 'nb'): '22',
            ('Bosnian', 'bos', 'bs'): '23',
            ('Breton', 'bre', 'br'): '24',
            ('Bulgarian', 'bul', 'bg'): '25',
            ('Burmese', 'mya', 'my'): '26',
            ('Cantonese', 'yue', 'zh'): '27',
            ('Catalan', 'cat', 'ca'): '28',
            ('Central Khmer', 'khm', 'km'): '29',
            ('Chamorro', 'cha', 'ch'): '30',
            ('Chechen', 'che', 'ce'): '31',
            ('Chichewa', 'nya', 'ny'): '32',
            ('Chinese', 'zho', 'zh'): '33',
            ('Church Slavic', 'chu', 'cu'): '34',
            ('Chuvash', 'chv', 'cv'): '35',
            ('Cornish', 'cor', 'kw'): '36',
            ('Corsican', 'cos', 'co'): '37',
            ('Cree', 'cre', 'cr'): '38',
            ('Croatian', 'hrv', 'hr'): '39',
            ('Czech', 'ces', 'cs'): '40',
            ('Danish', 'dan', 'da'): '41',
            ('Dhivehi', 'div', 'dv'): '42',
            ('Dutch', 'nld', 'nl'): '43',
            ('Dzongkha', 'dzo', 'dz'): '44',
            ('English', 'eng', 'en'): '45',
            ('Esperanto', 'epo', 'eo'): '46',
            ('Estonian', 'est', 'et'): '47',
            ('Ewe', 'ewe', 'ee'): '48',
            ('Faroese', 'fao', 'fo'): '49',
            ('Fijian', 'fij', 'fj'): '50',
            ('Finnish', 'fin', 'fi'): '51',
            ('French', 'fra', 'fr'): '52',
            ('Fulah', 'ful', 'ff'): '53',
            ('Gaelic', 'gla', 'gd'): '54',
            ('Galician', 'glg', 'gl'): '55',
            ('Ganda', 'lug', 'lg'): '56',
            ('Georgian', 'kat', 'ka'): '57',
            ('German', 'deu', 'de'): '58',
            ('Greek', 'ell', 'el'): '59',
            ('Guarani', 'grn', 'gn'): '60',
            ('Gujarati', 'guj', 'gu'): '61',
            ('Haitian', 'hat', 'ht'): '62',
            ('Hausa', 'hau', 'ha'): '63',
            ('Hebrew', 'heb', 'he'): '64',
            ('Herero', 'her', 'hz'): '65',
            ('Hindi', 'hin', 'hi'): '66',
            ('Hiri Motu', 'hmo', 'ho'): '67',
            ('Hungarian', 'hun', 'hu'): '68',
            ('Icelandic', 'isl', 'is'): '69',
            ('Ido', 'ido', 'io'): '70',
            ('Igbo', 'ibo', 'ig'): '71',
            ('Indonesian', 'ind', 'id'): '72',
            ('Interlingua', 'ina', 'ia'): '73',
            ('Interlingue', 'ile', 'ie'): '74',
            ('Inuktitut', 'iku', 'iu'): '75',
            ('Inupiaq', 'ipk', 'ik'): '76',
            ('Irish', 'gle', 'ga'): '77',
            ('Italian', 'ita', 'it'): '78',
            ('Japanese', 'jpn', 'ja'): '79',
            ('Javanese', 'jav', 'jv'): '80',
            ('Kalaallisut', 'kal', 'kl'): '81',
            ('Kannada', 'kan', 'kn'): '82',
            ('Kanuri', 'kau', 'kr'): '83',
            ('Kashmiri', 'kas', 'ks'): '84',
            ('Kazakh', 'kaz', 'kk'): '85',
            ('Kikuyu', 'kik', 'ki'): '86',
            ('Kinyarwanda', 'kin', 'rw'): '87',
            ('Kirghiz', 'kir', 'ky'): '88',
            ('Komi', 'kom', 'kv'): '89',
            ('Kongo', 'kon', 'kg'): '90',
            ('Korean', 'kor', 'ko'): '91',
            ('Kuanyama', 'kua', 'kj'): '92',
            ('Kurdish', 'kur', 'ku'): '93',
            ('Lao', 'lao', 'lo'): '94',
            ('Latin', 'lat', 'la'): '95',
            ('Latvian', 'lav', 'lv'): '96',
            ('Limburgan', 'lim', 'li'): '97',
            ('Lingala', 'lin', 'ln'): '98',
            ('Lithuanian', 'lit', 'lt'): '99',
            ('Luba-Katanga', 'lub', 'lu'): '100',
            ('Luxembourgish', 'ltz', 'lb'): '101',
            ('Macedonian', 'mkd', 'mk'): '102',
            ('Malagasy', 'mlg', 'mg'): '103',
            ('Malay', 'msa', 'ms'): '104',
            ('Malayalam', 'mal', 'ml'): '105',
            ('Maltese', 'mlt', 'mt'): '106',
            ('Mandarin', 'cmn', 'zh'): '107',
            ('Manx', 'glv', 'gv'): '108',
            ('Maori', 'mri', 'mi'): '109',
            ('Marathi', 'mar', 'mr'): '110',
            ('Marshallese', 'mah', 'mh'): '111',
            ('Mongolian', 'mon', 'mn'): '112',
            ('Nauru', 'nau', 'na'): '113',
            ('Navajo', 'nav', 'nv'): '114',
            ('Ndebele, North', 'nde', 'nd'): '115',
            ('Ndebele, South', 'nbl', 'nr'): '116',
            ('Ndonga', 'ndo', 'ng'): '117',
            ('Nepali', 'nep', 'ne'): '118',
            ('Northern Sami', 'sme', 'se'): '119',
            ('Norwegian', 'nor', 'no'): '120',
            ('Norwegian Nynorsk', 'nno', 'nn'): '121',
            ('Occitan (post 1500)', 'oci', 'oc'): '122',
            ('Ojibwa', 'oji', 'oj'): '123',
            ('Oriya', 'ori', 'or'): '124',
            ('Oromo', 'orm', 'om'): '125',
            ('Ossetian', 'oss', 'os'): '126',
            ('Pali', 'pli', 'pi'): '127',
            ('Panjabi', 'pan', 'pa'): '128',
            ('Persian', 'fas', 'fa'): '129',
            ('Polish', 'pol', 'pl'): '130',
            ('Portuguese', 'por', 'pt'): '131',
            ('Pushto', 'pus', 'ps'): '132',
            ('Quechua', 'que', 'qu'): '133',
            ('Romanian', 'ron', 'ro'): '134',
            ('Romansh', 'roh', 'rm'): '135',
            ('Rundi', 'run', 'rn'): '136',
            ('Russian', 'rus', 'ru'): '137',
            ('Samoan', 'smo', 'sm'): '138',
            ('Sango', 'sag', 'sg'): '139',
            ('Sanskrit', 'san', 'sa'): '140',
            ('Sardinian', 'srd', 'sc'): '141',
            ('Serbian', 'srp', 'sr'): '142',
            ('Shona', 'sna', 'sn'): '143',
            ('Sichuan Yi', 'iii', 'ii'): '144',
            ('Sindhi', 'snd', 'sd'): '145',
            ('Sinhala', 'sin', 'si'): '146',
            ('Slovak', 'slk', 'sk'): '147',
            ('Slovenian', 'slv', 'sl'): '148',
            ('Somali', 'som', 'so'): '149',
            ('Sotho, Southern', 'sot', 'st'): '150',
            ('Spanish', 'spa', 'es'): '151',
            ('Sundanese', 'sun', 'su'): '152',
            ('Swahili', 'swa', 'sw'): '153',
            ('Swati', 'ssw', 'ss'): '154',
            ('Swedish', 'swe', 'sv'): '155',
            ('Tagalog', 'tgl', 'tl'): '156',
            ('Tahitian', 'tah', 'ty'): '157',
            ('Tajik', 'tgk', 'tg'): '158',
            ('Tamil', 'tam', 'ta'): '159',
            ('Tatar', 'tat', 'tt'): '160',
            ('Telugu', 'tel', 'te'): '161',
            ('Thai', 'tha', 'th'): '162',
            ('Tibetan', 'bod', 'bo'): '163',
            ('Tigrinya', 'tir', 'ti'): '164',
            ('Tongan', 'ton', 'to'): '165',
            ('Tsonga', 'tso', 'ts'): '166',
            ('Tswana', 'tsn', 'tn'): '167',
            ('Turkish', 'tur', 'tr'): '168',
            ('Turkmen', 'tuk', 'tk'): '169',
            ('Twi', 'twi', 'tw'): '170',
            ('Uighur', 'uig', 'ug'): '171',
            ('Ukrainian', 'ukr', 'uk'): '172',
            ('Urdu', 'urd', 'ur'): '173',
            ('Uzbek', 'uzb', 'uz'): '174',
            ('Venda', 'ven', 've'): '175',
            ('Vietnamese', 'vie', 'vi'): '176',
            ('Volapük', 'vol', 'vo'): '177',
            ('Walloon', 'wln', 'wa'): '178',
            ('Welsh', 'cym', 'cy'): '179',
            ('Western Frisian', 'fry', 'fy'): '180',
            ('Wolof', 'wol', 'wo'): '181',
            ('Xhosa', 'xho', 'xh'): '182',
            ('Yiddish', 'yid', 'yi'): '183',
            ('Yoruba', 'yor', 'yo'): '184',
            ('Zhuang', 'zha', 'za'): '185',
            ('Zulu', 'zul', 'zu'): '186',
        }

        if tracker == 'PHD':
            self.all_lang_map.update({
                ('Brazilian Portuguese', 'por', 'pt'): '187',
                ('Filipino', 'fil', 'fil'): '189',
                ('Mooré', 'mos', 'mos'): '188',
            })

        if tracker == 'AZ':
            self.all_lang_map.update({
                ('Brazilian Portuguese', 'por', 'pt'): '189',
                ('Filipino', 'fil', 'fil'): '188',
                ('Mooré', 'mos', 'mos'): '187',
            })

        if tracker == 'CZ':
            self.all_lang_map.update({
                ('Brazilian Portuguese', 'por', 'pt'): '187',
                ('Mooré', 'mos', 'mos'): '188',
                ('Filipino', 'fil', 'fil'): '189',
                ('Bissa', 'bib', 'bib'): '190',
                ('Romani', 'rom', 'rom'): '191',
            })

        self.lang_map = {}
        for key_tuple, lang_id in self.all_lang_map.items():
            lang_name, code3, code2 = key_tuple

            self.lang_map[lang_name.lower()] = lang_id

            if code3:
                self.lang_map[code3.lower()] = lang_id

            if code2:
                self.lang_map[code2.lower()] = lang_id
