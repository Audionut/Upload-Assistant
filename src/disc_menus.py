import asyncio
import json
import os
from collections.abc import MutableMapping, Sequence
from pathlib import Path
from typing import Any, cast

from typing_extensions import TypeAlias

from src.console import console
from src.uploadscreens import UploadScreensManager

Meta: TypeAlias = MutableMapping[str, Any]


class DiscMenus:
    """
    Handles the processing and uploading of disc menu images.
    """

    def __init__(self, meta: Meta, config: MutableMapping[str, Any]):
        self.config = config
        self.path_to_menu_screenshots = str(meta.get('path_to_menu_screenshots', '') or '')
        self.uploadscreens_manager = UploadScreensManager(cast(dict[str, Any], config))

    async def get_disc_menu_images(self, meta: Meta) -> None:
        """
        Processes disc menu images from a local directory and uploads them.
        """
        if not self.path_to_menu_screenshots:
            return

        if os.path.isdir(self.path_to_menu_screenshots):
            await self.get_local_images(meta)
        else:
            console.print(f"[red]Invalid disc menus path: {self.path_to_menu_screenshots}[/red]")

    async def get_local_images(self, meta: Meta) -> None:
        """
        Uploads disc menu images from a local directory.
        """
        image_paths = [
            os.path.join(self.path_to_menu_screenshots, file)
            for file in os.listdir(self.path_to_menu_screenshots)
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
        ]

        if not image_paths:
            console.print("[yellow]No local menu images found to upload.[/yellow]")
            return

        uploaded_images, _ = await self.uploadscreens_manager.upload_screens(
            cast(dict[str, Any], meta),
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

    async def save_images_to_json(self, meta: Meta, image_list: Sequence[dict[str, Any]]) -> None:
        """
        Saves the uploaded disc menu images to a JSON file.
        """
        if not image_list:
            console.print("[yellow]No menu images found.[/yellow]")
            return

        menu_images = {
            "menu_images": list(image_list)
        }

        base_dir = str(meta.get('base_dir', ''))
        uuid_value = str(meta.get('uuid', ''))
        json_path = os.path.join(base_dir, 'tmp', uuid_value, 'menu_images.json')
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        menu_json = json.dumps(menu_images, indent=4)
        await asyncio.to_thread(Path(json_path).write_text, menu_json)

        console.print(f"[green]Saved {len(image_list)} menu images to {json_path}[/green]")


async def process_disc_menus(meta: Meta, config: MutableMapping[str, Any]) -> None:
    """
    Main function to process disc menu images.
    """
    disc_menus = DiscMenus(meta, config)
    await disc_menus.get_disc_menu_images(meta)
