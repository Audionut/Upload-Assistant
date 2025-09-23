import os
import urllib.parse
import requests
import glob
from src.console import console


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
                            description.write(template_desc + "\n")
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
                description_link_content = requests.get(raw_url).text
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
