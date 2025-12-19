# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
from datetime import datetime
from src.trackers.COMMON import COMMON
from src.trackers.AVISTAZ_NETWORK import AZTrackerBase


class CZ(AZTrackerBase):
    def __init__(self, config):
        super().__init__(config, tracker_name='CZ')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'CZ'
        self.source_flag = 'CinemaZ'
        self.banned_groups = ['']
        self.base_url = 'https://cinemaz.to'
        self.torrent_url = f'{self.base_url}/torrent/'
        self.requests_url = f'{self.base_url}/requests'

    async def rules(self, meta):
        warnings = []

        # This also checks the rule 'FANRES content is not allowed'
        if meta['category'] not in ('MOVIE', 'TV'):
            warnings.append(
                'The only allowed content to be uploaded are Movies and TV Shows.\n'
                'Anything else, like games, music, software and porn is not allowed!'
            )

        if meta.get('anime', False):
            warnings.append("Upload Anime content to our sister site AnimeTorrents.me instead. If it's on AniDB, it's an anime.")

        # https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes

        africa = [
            'AO', 'BF', 'BI', 'BJ', 'BW', 'CD', 'CF', 'CG', 'CI', 'CM', 'CV', 'DJ', 'DZ', 'EG', 'EH',
            'ER', 'ET', 'GA', 'GH', 'GM', 'GN', 'GQ', 'GW', 'IO', 'KE', 'KM', 'LR', 'LS', 'LY', 'MA',
            'MG', 'ML', 'MR', 'MU', 'MW', 'MZ', 'NA', 'NE', 'NG', 'RE', 'RW', 'SC', 'SD', 'SH', 'SL',
            'SN', 'SO', 'SS', 'ST', 'SZ', 'TD', 'TF', 'TG', 'TN', 'TZ', 'UG', 'YT', 'ZA', 'ZM', 'ZW'
        ]

        america = [
            'AG', 'AI', 'AR', 'AW', 'BB', 'BL', 'BM', 'BO', 'BQ', 'BR', 'BS', 'BV', 'BZ', 'CA', 'CL',
            'CO', 'CR', 'CU', 'CW', 'DM', 'DO', 'EC', 'FK', 'GD', 'GF', 'GL', 'GP', 'GS', 'GT', 'GY',
            'HN', 'HT', 'JM', 'KN', 'KY', 'LC', 'MF', 'MQ', 'MS', 'MX', 'NI', 'PA', 'PE', 'PM', 'PR',
            'PY', 'SR', 'SV', 'SX', 'TC', 'TT', 'US', 'UY', 'VC', 'VE', 'VG', 'VI'
        ]

        europe = [
            'AD', 'AL', 'AT', 'AX', 'BA', 'BE', 'BG', 'BY', 'CH', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
            'FO', 'FR', 'GB', 'GG', 'GI', 'GR', 'HR', 'HU', 'IE', 'IM', 'IS', 'IT', 'JE', 'LI', 'LT',
            'LU', 'LV', 'MC', 'MD', 'ME', 'MK', 'MT', 'NL', 'NO', 'PL', 'PT', 'RO', 'RS', 'RU', 'SE',
            'SI', 'SJ', 'SK', 'SM', 'SU', 'UA', 'VA', 'XC'
        ]

        # Countries that belong on PrivateHD (unless they are old)
        phd_countries = [
            'AG', 'AI', 'AU', 'BB', 'BM', 'BS', 'BZ', 'CA', 'CW', 'DM', 'GB', 'GD', 'IE',
            'JM', 'KN', 'KY', 'LC', 'MS', 'NZ', 'PR', 'TC', 'TT', 'US', 'VC', 'VG', 'VI',
        ]

        # Countries that belong on AvistaZ
        az_countries = [
            'BD', 'BN', 'BT', 'CN', 'HK', 'ID', 'IN', 'JP', 'KH', 'KP', 'KR', 'LA', 'LK',
            'MM', 'MN', 'MO', 'MY', 'NP', 'PH', 'PK', 'SG', 'TH', 'TL', 'TW', 'VN'
        ]

        # Countries normally allowed on CinemaZ
        set_phd = set(phd_countries)
        set_europe = set(europe)
        set_america = set(america)
        middle_east = [
            'AE', 'BH', 'CY', 'EG', 'IR', 'IQ', 'IL', 'JO', 'KW', 'LB', 'OM', 'PS', 'QA', 'SA', 'SY', 'TR', 'YE'
        ]

        # Combine all allowed regions for CinemaZ
        cz_allowed_countries = list(
            (set_europe - {'GB', 'IE'}) |  # Europe excluding UK and Ireland
            (set_america - set_phd) |      # All of America excluding the PHD countries
            set(africa) |                  # All of Africa
            set(middle_east) |             # Middle East countries
            {'RU'}                         # Russia
        )

        origin_countries_codes = meta.get('origin_country', [])
        year = meta.get('year')
        is_older_than_50_years = False

        if isinstance(year, int):
            current_year = datetime.now().year
            if (current_year - year) >= 50:
                is_older_than_50_years = True

        # Case 1: The content is from a major English-speaking country
        if any(code in phd_countries for code in origin_countries_codes):
            if is_older_than_50_years:
                # It's old, so it's ALLOWED on CinemaZ
                pass
            else:
                # It's new, so redirect to PrivateHD
                warnings.append(
                    'DO NOT upload recent mainstream English content. '
                    'Upload this to our sister site PrivateHD.to instead.'
                )

        # Case 2: The content is Asian, redirect to AvistaZ
        elif any(code in az_countries for code in origin_countries_codes):
            warnings.append(
                'DO NOT upload Asian content. '
                'Upload this to our sister site AvistaZ.to instead.'
            )

        # Case 3: The content is from one of the normally allowed CZ regions
        elif any(code in cz_allowed_countries for code in origin_countries_codes):
            # It's from a valid region, so it's ALLOWED on CinemaZ
            pass

        # Case 4: Fallback for any other case (e.g., country not in any list)
        else:
            warnings.append(
                'This content is not allowed. CinemaZ accepts content from Europe (excluding UK/IE), '
                'Africa, the Middle East, Russia, and the Americas (excluding recent mainstream English content).'
            )

        if warnings:
            all_warnings = '\n\n'.join(filter(None, warnings))
            return all_warnings

        return
