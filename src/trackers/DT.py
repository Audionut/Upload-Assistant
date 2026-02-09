from src.trackers.UNIT3D import UNIT3D
from typing import Any, Optional

class DT(UNIT3D):
    """
    DesiTorrents (DT) Tracker Class
    """
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config, tracker_name='DT')
        self.tracker = 'DT'
        self.base_url = 'https://torrent.desi'
        self.upload_url = f'{self.base_url}/api/v1/torrents/upload'
        self.search_url = f'{self.base_url}/api/v1/torrents/filter'
        
        # Banned Groups
        self.banned_groups = [
            "DusIcTv", "PHDM", "PDHM", "Ranvijay", 
            "BWT", "DDH", "Telly", "YTS", "RARBG", 
            "BonsaiHD", "GalaxyRG", "-=!DrSTAR!=-"
        ]

    async def get_category_id(
        self,
        meta: dict[str, Any],
        category: str = "",
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        """
        Returns the category ID for the release.
        """
        
        # DT Category Map: Movie=1, TV=2, Music=3, Game=4
        category_id = {
            'MOVIE': '1',
            'TV': '2',
            'MUSIC': '3',
            'GAME': '4'
        }
        
        if mapping_only:
            return category_id
        elif reverse:
            return {v: k for k, v in category_id.items()}
        elif category:
            return {'category_id': category_id.get(category, '0')}
        else:
            meta_category = meta.get('category', '')
            resolved_id = category_id.get(meta_category, '0')
            return {'category_id': resolved_id}

    async def get_type_id(
        self,
        meta: dict[str, Any],
        type: str = "",
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        """
        Returns the type ID (source) for the release.
        """
        
        # Standard Mapping for reverse lookups
        type_id_map = {
            'DISC': '3',    # Defaulting to BD50
            'REMUX': '5',   # Defaulting to BD Remux
            'ENCODE': '12', # Defaulting to BD Encode
            'WEBDL': '11',
            'WEBRIP': '11',
            'HDTV': '13',
            'DVD': '8'
        }

        if mapping_only:
            return type_id_map
        elif reverse:
            return {v: k for k, v in type_id_map.items()}
        elif type:
            return {'type_id': type_id_map.get(type, '0')}
        else:
            # Dynamic Logic for DT specific IDs (UHD vs 1080p)
            meta_type = meta.get('type', '')
            is_uhd = meta.get('uhd', False)
            
            resolved_id = '0'
            
            if meta_type == 'DISC':
                resolved_id = '3' # BD50
                if meta.get('disctype') == 'BD25':
                    resolved_id = '4'
            elif meta_type == 'REMUX':
                resolved_id = '2' if is_uhd else '5'
            elif meta_type == 'ENCODE':
                resolved_id = '1' if is_uhd else '12'
            elif meta_type in ['WEBDL', 'WEBRIP']:
                resolved_id = '11'
            elif meta_type == 'DVD':
                resolved_id = '8'
            elif meta_type == 'HDTV':
                resolved_id = '13'
                
            return {'type_id': resolved_id}

    async def get_resolution_id(
        self,
        meta: dict[str, Any],
        resolution: str = "",
        reverse: bool = False,
        mapping_only: bool = False,
    ) -> dict[str, str]:
        """
        Returns the resolution ID for the release.
        """
        
        # DT Specific Resolutions
        resolution_id = {
            '4320p': '9', # 8k
            '2160p': '8',
            '1080p': '11',
            '1080i': '7',
            '720p': '6',
            '720i': '5',
            '576p': '4',
            '576i': '3',
            '540p': '12',
            '480p': '2',
            '480i': '1'
        }
        
        if mapping_only:
            return resolution_id
        elif reverse:
            return {v: k for k, v in resolution_id.items()}
        elif resolution:
            return {'resolution_id': resolution_id.get(resolution, '10')}
        else:
            meta_resolution = meta.get('resolution', '')
            resolved_id = resolution_id.get(meta_resolution, '10') # 10 is 'Other'
            return {'resolution_id': resolved_id}
