from src.console import console
from data.config import config
import os
import pyimgbox
import asyncio
import requests
import glob
import base64
import time
from multiprocessing import get_context
from tqdm import tqdm
import sys


def upload_image_task(args):
    image, img_host, config, meta = args
    try:
        timeout = 60  # Default timeout
        img_url, raw_url, web_url = None, None, None

        if img_host == "imgbox":
            try:
                # Call the asynchronous imgbox_upload function
                loop = asyncio.get_event_loop()
                image_list = loop.run_until_complete(
                    imgbox_upload(os.getcwd(), [image], meta, return_dict={})
                )
                if image_list and all(
                    'img_url' in img and 'raw_url' in img and 'web_url' in img for img in image_list
                ):
                    img_url = image_list[0]['img_url']
                    raw_url = image_list[0]['raw_url']
                    web_url = image_list[0]['web_url']
                else:
                    return {
                        'status': 'failed',
                        'reason': "Imgbox upload failed. No valid URLs returned."
                    }
            except Exception as e:
                return {
                    'status': 'failed',
                    'reason': f"Error during Imgbox upload: {str(e)}"
                }

        elif img_host == "ptpimg":
            payload = {
                'format': 'json',
                'api_key': config['DEFAULT']['ptpimg_api']
            }
            files = [('file-upload[0]', open(image, 'rb'))]
            headers = {'referer': 'https://ptpimg.me/index.php'}
            response = requests.post(
                "https://ptpimg.me/upload.php", headers=headers, data=payload, files=files, timeout=timeout
            )
            response_data = response.json()
            if response_data:
                code = response_data[0]['code']
                ext = response_data[0]['ext']
                img_url = f"https://ptpimg.me/{code}.{ext}"
                raw_url = img_url
                web_url = img_url

        elif img_host == "imgbb":
            url = "https://api.imgbb.com/1/upload"
            try:
                with open(image, "rb") as img_file:
                    encoded_image = base64.b64encode(img_file.read()).decode('utf8')

                data = {
                    'key': config['DEFAULT']['imgbb_api'],
                    'image': encoded_image,
                }

                response = requests.post(url, data=data, timeout=timeout)

                if meta['debug']:
                    console.print(f"[yellow]Response status code: {response.status_code}")
                    console.print(f"[yellow]Response content: {response.content.decode('utf-8')}")

                response_data = response.json()
                if response.status_code != 200 or not response_data.get('success'):
                    console.print("[yellow]imgbb failed, trying next image host")
                    return {'status': 'failed', 'reason': 'imgbb upload failed'}

                img_url = response_data['data'].get('medium', {}).get('url') or response_data['data']['thumb']['url']
                raw_url = response_data['data']['image']['url']
                web_url = response_data['data']['url_viewer']

                if meta['debug']:
                    console.print(f"[green]Image URLs: img_url={img_url}, raw_url={raw_url}, web_url={web_url}")

                return {'status': 'success', 'img_url': img_url, 'raw_url': raw_url, 'web_url': web_url}

            except requests.exceptions.Timeout:
                console.print("[red]Request timed out. The server took too long to respond.")
                return {'status': 'failed', 'reason': 'Request timed out'}

            except ValueError as e:  # JSON decoding error
                console.print(f"[red]Invalid JSON response: {e}")
                return {'status': 'failed', 'reason': 'Invalid JSON response'}

            except requests.exceptions.RequestException as e:
                console.print(f"[red]Request failed with error: {e}")
                return {'status': 'failed', 'reason': str(e)}

        elif img_host == "ptscreens":
            url = "https://ptscreens.com/api/1/upload"
            try:
                files = {
                    'source': ('file-upload[0]', open(image, 'rb')),
                }
                headers = {
                    'X-API-Key': config['DEFAULT']['ptscreens_api']
                }
                response = requests.post(url, headers=headers, files=files, timeout=timeout)
                if meta['debug']:
                    console.print(f"[yellow]Response status code: {response.status_code}")
                    console.print(f"[yellow]Response content: {response.content.decode('utf-8')}")

                response_data = response.json()
                if response_data.get('status_code') != 200:
                    console.print("[yellow]ptscreens failed, trying next image host")
                    return {'status': 'failed', 'reason': 'ptscreens upload failed'}

                img_url = response_data['image']['medium']['url']
                raw_url = response_data['image']['url']
                web_url = response_data['image']['url_viewer']
                if meta['debug']:
                    console.print(f"[green]Image URLs: img_url={img_url}, raw_url={raw_url}, web_url={web_url}")

            except requests.exceptions.Timeout:
                console.print("[red]Request timed out. The server took too long to respond.")
                return {'status': 'failed', 'reason': 'Request timed out'}
            except requests.exceptions.RequestException as e:
                console.print(f"[red]Request failed with error: {e}")
                return {'status': 'failed', 'reason': str(e)}

        elif img_host == "oeimg":
            url = "https://imgoe.download/api/1/upload"
            try:
                data = {
                    'image': base64.b64encode(open(image, "rb").read()).decode('utf8')
                }
                headers = {
                    'X-API-Key': config['DEFAULT']['oeimg_api'],
                }
                response = requests.post(url, data=data, headers=headers, timeout=timeout)
                if meta['debug']:
                    console.print(f"[yellow]Response status code: {response.status_code}")
                    console.print(f"[yellow]Response content: {response.content.decode('utf-8')}")

                response_data = response.json()
                if response.status_code != 200 or not response_data.get('success'):
                    console.print("[yellow]OEimg failed, trying next image host")
                    return {'status': 'failed', 'reason': 'OEimg upload failed'}

                img_url = response_data['data']['image']['url']
                raw_url = response_data['data']['image']['url']
                web_url = response_data['data']['url_viewer']
                if meta['debug']:
                    console.print(f"[green]Image URLs: img_url={img_url}, raw_url={raw_url}, web_url={web_url}")

            except requests.exceptions.Timeout:
                console.print("[red]Request timed out. The server took too long to respond.")
                return {'status': 'failed', 'reason': 'Request timed out'}
            except requests.exceptions.RequestException as e:
                console.print(f"[red]Request failed with error: {e}")
                return {'status': 'failed', 'reason': str(e)}

        elif img_host == "pixhost":
            url = "https://api.pixhost.to/images"
            data = {
                'content_type': '0',
                'max_th_size': 350
            }
            files = {
                'img': ('file-upload[0]', open(image, 'rb'))
            }
            response = requests.post(url, data=data, files=files, timeout=timeout)
            response_data = response.json()
            if response.status_code == 200:
                raw_url = response_data['th_url'].replace('https://t', 'https://img').replace('/thumbs/', '/images/')
                img_url = response_data['th_url']
                web_url = response_data['show_url']

        elif img_host == "lensdump":
            url = "https://lensdump.com/api/1/upload"
            data = {
                'image': base64.b64encode(open(image, "rb").read()).decode('utf8')
            }
            headers = {
                'X-API-Key': config['DEFAULT']['lensdump_api']
            }
            response = requests.post(url, data=data, headers=headers, timeout=timeout)
            response_data = response.json()
            if response_data.get('status_code') == 200:
                img_url = response_data['data']['image']['url']
                raw_url = response_data['data']['image']['url']
                web_url = response_data['data']['url_viewer']

        if img_url and raw_url and web_url:
            return {
                'status': 'success',
                'img_url': img_url,
                'raw_url': raw_url,
                'web_url': web_url,
                'local_file_path': image
            }
        else:
            return {
                'status': 'failed',
                'reason': f"Failed to upload image to {img_host}. No URLs received."
            }

    except Exception as e:
        return {
            'status': 'failed',
            'reason': str(e)
        }


def upload_screens(meta, screens, img_host_num, i, total_screens, custom_img_list, return_dict, retry_mode=False, max_retries=3):
    def use_tqdm():
        """Check if the environment supports TTY (interactive progress bar)."""
        return sys.stdout.isatty()

    if meta['debug']:
        upload_start_time = time.time()

    import nest_asyncio
    nest_asyncio.apply()
    os.chdir(f"{meta['base_dir']}/tmp/{meta['uuid']}")
    initial_img_host = config['DEFAULT'][f'img_host_{img_host_num}']
    img_host = meta['imghost']
    using_custom_img_list = isinstance(custom_img_list, list) and bool(custom_img_list)

    if 'image_sizes' not in meta:
        meta['image_sizes'] = {}

    if using_custom_img_list:
        image_glob = custom_img_list
        existing_images = []
        existing_count = 0
    else:
        image_glob = glob.glob("*.png")
        if 'POSTER.png' in image_glob:
            image_glob.remove('POSTER.png')
        image_glob = list(set(image_glob))
        if meta['debug']:
            console.print("image globs:", image_glob)

        existing_images = [img for img in meta['image_list'] if img.get('img_url') and img.get('web_url')]
        existing_count = len(existing_images)

    if not retry_mode:
        images_needed = max(0, total_screens - existing_count)
    else:
        images_needed = total_screens

    if existing_count >= total_screens and not retry_mode and img_host == initial_img_host and not using_custom_img_list:
        console.print(f"[yellow]Skipping upload because enough images are already uploaded to {img_host}. Existing images: {existing_count}, Required: {total_screens}")
        return meta['image_list'], total_screens

    upload_tasks = [(image, img_host, config, meta) for image in image_glob[:images_needed]]

    host_limits = {
        "oeimg": 6,
        "ptscreens": 1,
        "lensdump": 1,
    }
    default_pool_size = int(meta.get('task_limit', os.cpu_count()))
    pool_size = host_limits.get(img_host, default_pool_size)

    try:
        with get_context("spawn").Pool(processes=max(1, min(len(upload_tasks), pool_size))) as pool:
            if use_tqdm():
                try:
                    results = list(
                        tqdm(
                            pool.imap_unordered(upload_image_task, upload_tasks),
                            total=len(upload_tasks),
                            desc=f"Uploading Images to {img_host}",
                            ascii=True,
                            dynamic_ncols=False
                        )
                    )
                finally:
                    pool.close()
                    pool.join()
            else:
                console.print(f"[blue]Non-TTY environment detected. Progress bar disabled. Uploading images to {img_host}.")
                results = []
                for i, result in enumerate(pool.imap_unordered(upload_image_task, upload_tasks), 1):
                    results.append(result)
                    console.print(f"Uploaded {i}/{len(upload_tasks)} images to {img_host}")
    except KeyboardInterrupt:
        console.print("[red]Upload process interrupted by user. Exiting...")
        pool.terminate()
        pool.join()
        return meta['image_list'], len(meta['image_list'])

    successfully_uploaded = []
    for result in results:
        if result['status'] == 'success':
            successfully_uploaded.append(result)
        else:
            console.print(f"[yellow]Failed to upload: {result.get('reason', 'Unknown error')}")

    if len(successfully_uploaded) < meta.get('cutoff') and not retry_mode and img_host == initial_img_host and not using_custom_img_list:
        img_host_num += 1
        if f'img_host_{img_host_num}' in config['DEFAULT']:
            meta['imghost'] = config['DEFAULT'][f'img_host_{img_host_num}']
            console.print(f"[cyan]Switching to the next image host: {meta['imghost']}")
            return upload_screens(meta, screens, img_host_num, i, total_screens, custom_img_list, return_dict, retry_mode=True)
        else:
            console.print("[red]No more image hosts available. Aborting upload process.")
            return meta['image_list'], len(meta['image_list'])

    new_images = []
    for upload in successfully_uploaded:
        raw_url = upload['raw_url']
        new_image = {
            'img_url': upload['img_url'],
            'raw_url': raw_url,
            'web_url': upload['web_url']
        }
        new_images.append(new_image)
        if not using_custom_img_list and raw_url not in {img['raw_url'] for img in meta['image_list']}:
            if meta['debug']:
                console.print(f"[blue]Adding {raw_url} to image_list")
            meta['image_list'].append(new_image)
            local_file_path = upload.get('local_file_path')
            if local_file_path:
                image_size = os.path.getsize(local_file_path)
                meta['image_sizes'][raw_url] = image_size

    console.print(f"[green]Successfully uploaded {len(new_images)} images.")
    if meta['debug']:
        upload_finish_time = time.time()
        print(f"Screenshot uploads processed in {upload_finish_time - upload_start_time:.4f} seconds")

    if using_custom_img_list:
        return new_images, len(new_images)

    return meta['image_list'], len(successfully_uploaded)


async def imgbox_upload(chdir, image_glob, meta, return_dict):
    try:
        os.chdir(chdir)
        image_list = []

        async with pyimgbox.Gallery(thumb_width=350, square_thumbs=False) as gallery:
            for image in image_glob:
                try:
                    async for submission in gallery.add([image]):
                        if not submission['success']:
                            console.print(f"[red]Error uploading to imgbox: [yellow]{submission['error']}[/yellow][/red]")
                        else:
                            web_url = submission.get('web_url')
                            img_url = submission.get('thumbnail_url')
                            raw_url = submission.get('image_url')
                            if web_url and img_url and raw_url:
                                image_dict = {
                                    'web_url': web_url,
                                    'img_url': img_url,
                                    'raw_url': raw_url
                                }
                                image_list.append(image_dict)
                            else:
                                console.print(f"[red]Incomplete URLs received for image: {image}")
                except Exception as e:
                    console.print(f"[red]Error during upload for {image}: {str(e)}")

        return_dict['image_list'] = image_list
        return image_list

    except Exception as e:
        console.print(f"[red]An error occurred while uploading images to imgbox: {str(e)}")
        return []
