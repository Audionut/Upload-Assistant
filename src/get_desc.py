# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
import aiofiles
import glob
import os
import requests
import urllib.parse
from src.console import console
from src.trackers.COMMON import COMMON
from pymediainfo import MediaInfo


async def gen_desc(meta):
    def clean_text(text):
        return text.replace('\r\n', '\n').strip()

    description_link = meta.get('description_link')
    description_file = meta.get('description_file')
    scene_nfo = False
    bhd_nfo = False

    with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
        description.seek(0)
        content_written = False

        if meta.get('description_template'):
            from jinja2 import Template
            try:
                with open(f"{meta['base_dir']}/data/templates/{meta['description_template']}.txt", 'r') as f:
                    template = Template(f.read())
                    template_desc = template.render(meta)
                    cleaned_content = clean_text(template_desc)
                    if cleaned_content:
                        if not content_written:
                            description.write
                        if len(template_desc) > 0:
                            description.write(cleaned_content + "\n")
                            meta['description_template_content'] = cleaned_content
                        content_written = True
            except FileNotFoundError:
                console.print(f"[ERROR] Template '{meta['description_template']}' not found.")

        base_dir = meta['base_dir']
        uuid = meta['uuid']
        path = meta['path']
        specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
        source_dir_path = os.path.join(path, "*.nfo")
        if meta.get('nfo'):
            if meta['debug']:
                console.print(f"specified_dir_path: {specified_dir_path}")
                console.print(f"sourcedir_path: {source_dir_path}")
            if 'auto_nfo' in meta and meta['auto_nfo'] is True:
                nfo_files = glob.glob(specified_dir_path)
                scene_nfo = True
            elif 'bhd_nfo' in meta and meta['bhd_nfo'] is True:
                nfo_files = glob.glob(specified_dir_path)
                bhd_nfo = True
            else:
                nfo_files = glob.glob(source_dir_path)
            if not nfo_files:
                console.print("NFO was set but no nfo file was found")
                if not content_written:
                    description.write("\n")
                return meta

            if nfo_files:
                nfo = nfo_files[0]
                try:
                    with open(nfo, 'r', encoding="utf-8") as nfo_file:
                        nfo_content = nfo_file.read()
                    if meta['debug']:
                        console.print("NFO content read with utf-8 encoding.")
                except UnicodeDecodeError:
                    if meta['debug']:
                        console.print("utf-8 decoding failed, trying latin1.")
                    with open(nfo, 'r', encoding="latin1") as nfo_file:
                        nfo_content = nfo_file.read()

                if not content_written:
                    if scene_nfo is True:
                        description.write(f"[center][spoiler=Scene NFO:][code]{nfo_content}[/code][/spoiler][/center]\n")
                    elif bhd_nfo is True:
                        description.write(f"[center][spoiler=FraMeSToR NFO:][code]{nfo_content}[/code][/spoiler][/center]\n")
                    else:
                        description.write(f"[code]{nfo_content}[/code]\n")

                    meta['description'] = "CUSTOM"
                    content_written = True

                nfo_content_utf8 = nfo_content.encode('utf-8', 'ignore').decode('utf-8')
                meta['description_nfo_content'] = nfo_content_utf8

        if description_link:
            try:
                parsed = urllib.parse.urlparse(description_link.replace('/raw/', '/'))
                split = os.path.split(parsed.path)
                raw = parsed._replace(path=f"{split[0]}/raw/{split[1]}" if split[0] != '/' else f"/raw{parsed.path}")
                raw_url = urllib.parse.urlunparse(raw)
                description_link_content = requests.get(raw_url, timeout=10).text
                cleaned_content = clean_text(description_link_content)
                if cleaned_content:
                    if not content_written:
                        description.write(cleaned_content + '\n')
                    meta['description_link_content'] = cleaned_content
                    meta['description'] = 'CUSTOM'
                    content_written = True
            except Exception as e:
                console.print(f"[ERROR] Failed to fetch description from link: {e}")

        if description_file and os.path.isfile(description_file):
            with open(description_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
                cleaned_content = clean_text(file_content)
                if cleaned_content:
                    if not content_written:
                        description.write(file_content)
                meta['description_file_content'] = cleaned_content
                meta['description'] = "CUSTOM"
                content_written = True

        if not content_written:
            if meta.get('description'):
                description_text = meta.get('description', '').strip()
            else:
                description_text = ""
            if description_text:
                description.write(description_text + "\n")

        if description.tell() != 0:
            description.write("\n")

    # Fallback if no description is provided
    if not meta.get('skip_gen_desc', False) and not content_written:
        description_text = meta['description'] if meta.get('description', '') else ""
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
            if len(description_text) > 0:
                description.write(description_text + "\n")

    if meta.get('description') in ('None', '', ' '):
        meta['description'] = None

    return meta


class DescriptionBuilder:
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)

    async def get_custom_header(self, tracker):
        """Returns a custom header if configured."""
        custom_description_header = self.config['TRACKERS'][tracker].get('custom_description_header', self.config['DEFAULT'].get('custom_description_header', False))
        if custom_description_header:
            return custom_description_header
        return ''

    async def get_tonemapped_header(self, meta, tracker):
        tonemapped_description_header = self.config['TRACKERS'][tracker].get('tonemapped_header', self.config['DEFAULT'].get('tonemapped_header', ''))
        if tonemapped_description_header and meta.get('tonemapped', False):
            return tonemapped_description_header
        return ''

    async def get_logo_section(self, meta, tracker):
        """Returns the logo URL and size if applicable."""
        if not self.config['TRACKERS'][tracker].get('add_logo', self.config['DEFAULT'].get('add_logo', False)):
            return None, None

        logo = meta.get('logo', '')
        logo_size = self.config['DEFAULT'].get('logo_size', '300')

        if logo:
            return logo, logo_size
        return None, None

    async def _get_episode_name(self, meta):
        tvmaze_episode_data = meta.get('tvmaze_episode_data')
        if tvmaze_episode_data and tvmaze_episode_data.get('episode_name'):
            return tvmaze_episode_data['episode_name']
        return ''

    async def _get_episode_image(self, meta):
        tvmaze_episode_data = meta.get('tvmaze_episode_data')
        if tvmaze_episode_data and tvmaze_episode_data.get('image'):
            return tvmaze_episode_data['image']
        return ''

    async def get_tv_info(self, meta, tracker, resize=False):
        if not self.config['TRACKERS'][tracker].get('episode_overview', self.config['DEFAULT'].get('episode_overview', False)) or meta['category'] != 'TV':
            return '', '', ''

        tvmaze_episode_data = meta.get('tvmaze_episode_data', {})

        name = tvmaze_episode_data.get('season_name', '') or meta.get('title')
        season_number = meta.get('season', '')
        episode_number = meta.get('episode', '')
        episode_title = tvmaze_episode_data.get('episode_name', '')
        overview = tvmaze_episode_data.get('overview', '') or meta.get('overview_meta', '')

        image = ''
        if meta.get('tv_pack', False):
            image = tvmaze_episode_data.get('series_image', '')
            if resize:
                image = tvmaze_episode_data.get('series_image_medium', '')
        else:
            image = tvmaze_episode_data.get('image', '')
            if resize:
                image = tvmaze_episode_data.get('image_medium', '')

        title = f'{name}'
        if season_number:
            title += f' {season_number}{episode_number}'

        if episode_title:
            title += f':\n{episode_title}'

        return title, image, overview

    async def get_episode_overview(self, meta):
        """Returns True if episode overview should be included."""
        tvmaze_episode_data = meta.get('tvmaze_episode_data')

        if self.config['DEFAULT'].get('episode_overview', False) and tvmaze_episode_data:
            return True
        return False

    async def get_mediainfo_section(self, meta, tracker):
        """Returns the mediainfo/bdinfo section, using a cache file if available."""
        if meta.get('is_disc') == 'BDMV':
            return ''

        if self.config['TRACKERS'][tracker].get(
            'full_mediainfo',
            self.config['DEFAULT'].get('full_mediainfo', False)
        ):
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
            if await self.common.path_exists(mi_path):
                async with aiofiles.open(mi_path, 'r', encoding='utf-8') as mi:
                    return await mi.read()

        cache_file_dir = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
        cache_file_path = os.path.join(cache_file_dir, 'MEDIAINFO_SHORT.txt')

        file_exists = os.path.exists(cache_file_path)
        file_size = os.path.getsize(cache_file_path) if file_exists else 0

        if file_exists and file_size > 0:
            try:
                async with aiofiles.open(cache_file_path, mode='r', encoding='utf-8') as f:
                    media_info_content = await f.read()
                return media_info_content
            except Exception:
                pass

        video_file = meta['filelist'][0]
        mi_template = os.path.join(meta['base_dir'], 'data', 'templates', 'MEDIAINFO.txt')
        mi_file_path = os.path.join(cache_file_dir, 'MEDIAINFO_CLEANPATH.txt')

        template_exists = await self.common.path_exists(mi_template)

        if template_exists:
            try:
                media_info_result = MediaInfo.parse(
                    video_file,
                    output='STRING',
                    full=False,
                    mediainfo_options={'inform': f'file://{mi_template}'}
                )
                media_info_content = str(media_info_result)

                if media_info_content:
                    media_info_content = media_info_content.replace('\r\n', '\n')
                    try:
                        await self.common.makedirs(cache_file_dir)
                        async with aiofiles.open(cache_file_path, mode='w', encoding='utf-8') as f:
                            await f.write(media_info_content)
                    except Exception:
                        pass

                    return media_info_content

            except Exception:
                cleanpath_exists = await self.common.path_exists(mi_file_path)
                if cleanpath_exists:
                    async with aiofiles.open(mi_file_path, 'r', encoding='utf-8') as f:
                        return await f.read()

        else:
            cleanpath_exists = await self.common.path_exists(mi_file_path)
            if cleanpath_exists:
                async with aiofiles.open(mi_file_path, 'r', encoding='utf-8') as f:
                    tech_info = await f.read()
                    return tech_info

        return ''

    async def get_bdinfo_section(self, meta):
        """Returns the bdinfo section if applicable."""
        if meta.get('is_disc') == 'BDMV':
            bdinfo_sections = []
            if meta.get('discs'):
                for disc in meta['discs']:
                    file_info = disc.get('summary', '')
                    if file_info:
                        bdinfo_sections.append(file_info)
            return '\n\n'.join(bdinfo_sections)
        return ''

    async def screenshot_header(self, tracker):
        """Returns the screenshot header if applicable."""
        screenheader = self.config['TRACKERS'][tracker].get('custom_screenshot_header', self.config['DEFAULT'].get('screenshot_header', None))
        if screenheader:
            return screenheader
        return ''

    async def get_user_description(self, meta):
        """Returns the user-provided description (file or link)"""
        description_file_content = meta.get('description_file_content', '').strip()
        description_link_content = meta.get('description_link_content', '').strip()

        if description_file_content or description_link_content:
            if description_file_content:
                return description_file_content
            elif description_link_content:
                return description_link_content
        return ''
