import os
import urllib.parse
import requests
import glob
from src.console import console


async def gen_desc(meta):
    def clean_text(text):
        return text.replace('\r\n', '').replace('\n', '').strip()

    desclink = meta.get('desclink')
    descfile = meta.get('descfile')
    scene_nfo = False
    bhd_nfo = False

    with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
        description.seek(0)
        content_written = False

        if meta.get('desc_template'):
            from jinja2 import Template
            try:
                with open(f"{meta['base_dir']}/data/templates/{meta['desc_template']}.txt", 'r') as f:
                    template = Template(f.read())
                    template_desc = template.render(meta)
                    if clean_text(template_desc):
                        if len(template_desc) > 0:
                            description.write(template_desc + "\n")
                        content_written = True
            except FileNotFoundError:
                console.print(f"[ERROR] Template '{meta['desc_template']}' not found.")

        base_dir = meta['base_dir']
        uuid = meta['uuid']
        path = meta['path']
        specified_dir_path = os.path.join(base_dir, "tmp", uuid, "*.nfo")
        source_dir_path = os.path.join(path, "*.nfo")
        if meta.get('nfo') and not content_written:
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

                if scene_nfo is True:
                    description.write(f"[center][spoiler=Scene NFO:][code]{nfo_content}[/code][/spoiler][/center]\n")
                elif bhd_nfo is True:
                    description.write(f"[center][spoiler=FraMeSToR NFO:][code]{nfo_content}[/code][/spoiler][/center]\n")
                else:
                    description.write(f"[code]{nfo_content}[/code]\n")
                meta['description'] = "CUSTOM"
                content_written = True

        if desclink and not content_written:
            try:
                parsed = urllib.parse.urlparse(desclink.replace('/raw/', '/'))
                split = os.path.split(parsed.path)
                raw = parsed._replace(path=f"{split[0]}/raw/{split[1]}" if split[0] != '/' else f"/raw{parsed.path}")
                raw_url = urllib.parse.urlunparse(raw)
                desclink_content = requests.get(raw_url).text
                if clean_text(desclink_content):
                    description.write(desclink_content + "\n")
                    meta['description'] = "CUSTOM"
                    content_written = True
            except Exception as e:
                console.print(f"[ERROR] Failed to fetch description from link: {e}")

        if descfile and os.path.isfile(descfile) and not content_written:
            with open(descfile, 'r') as f:
                file_content = f.read()
            if clean_text(file_content):
                description.write(file_content)
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
