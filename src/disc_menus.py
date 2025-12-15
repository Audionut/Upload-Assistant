import os
import json
from src.console import console
from src.uploadscreens import upload_screens


class DiscMenus:
    """
    Handles the processing and uploading of disc menu images.
    """

    def __init__(self, meta, config):
        self.config = config
        self.path_to_menu_screenshots = meta.get('path_to_menu_screenshots', '')

    async def get_disc_menu_images(self, meta):
        """
        Processes disc menu images from a local directory and uploads them.
        """
        if not self.path_to_menu_screenshots:
            return

        if os.path.isdir(self.path_to_menu_screenshots):
            await self.get_local_images(meta)
        else:
            console.print(f"[red]Invalid disc menus path: {self.path_to_menu_screenshots}[/red]")

    async def get_local_images(self, meta):
        """
        Uploads disc menu images from a local directory.
        """
        image_paths = []
        for file in os.listdir(self.path_to_menu_screenshots):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                image_paths.append(os.path.join(self.path_to_menu_screenshots, file))

        if not image_paths:
            console.print("[yellow]No local menu images found to upload.[/yellow]")
            return

        uploaded_images, _ = await upload_screens(
            meta,
            screens=len(image_paths),
            img_host_num=1,
            i=0,
            total_screens=len(image_paths),
            custom_img_list=image_paths,
            return_dict={},
            retry_mode=False
        )

        meta['menu_images'] = uploaded_images

        await self.save_images_to_json(meta, uploaded_images)

    async def save_images_to_json(self, meta, image_list):
        """
        Saves the uploaded disc menu images to a JSON file.
        """
        if not image_list:
            console.print("[yellow]No menu images found.[/yellow]")
            return

        menu_images = {
            "menu_images": image_list
        }

        json_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], 'menu_images.json')
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        with open(json_path, 'w') as f:
            json.dump(menu_images, f, indent=4)

        console.print(f"[green]Saved {len(image_list)} menu images to {json_path}[/green]")


async def process_disc_menus(meta, config):
    """
    Main function to process disc menu images.
    """
    disc_menus = DiscMenus(meta, config)
    await disc_menus.get_disc_menu_images(meta)
