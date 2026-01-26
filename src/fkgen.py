import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup


class DoubanMovieGenerator:
    def __init__(self, movie_url: str) -> None:
        self.movie_url = movie_url
        self.movie_info: dict[str, Any] = {}

    def parse(self) -> None:
        if not self.movie_url:
            self.movie_info = {}
            return

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            )
        }
        response = httpx.get(self.movie_url, headers=headers, timeout=15.0)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        douban_id_match = re.search(r"/subject/(\d+)/?", self.movie_url)
        douban_id = douban_id_match.group(1) if douban_id_match else ""

        title = ""
        title_tag = soup.select_one('span[property="v:itemreviewed"]')
        if title_tag:
            title = title_tag.get_text(strip=True)
        if not title:
            title = soup.title.get_text(strip=True).replace("(豆瓣)", "") if soup.title else ""

        ld_json = {}
        ld_tag = soup.find("script", type="application/ld+json")
        if ld_tag and ld_tag.string:
            try:
                ld_json = json.loads(ld_tag.string.strip())
            except json.JSONDecodeError:
                ld_json = {}

        year = ""
        year_tag = soup.select_one("span.year")
        if year_tag:
            year_match = re.search(r"(\d{4})", year_tag.get_text())
            if year_match:
                year = year_match.group(1)
        if not year:
            year_value = ld_json.get("datePublished", "")
            year_match = re.search(r"(\d{4})", str(year_value))
            if year_match:
                year = year_match.group(1)

        genres = [tag.get_text(strip=True) for tag in soup.select('span[property="v:genre"]')]
        if not genres:
            ld_genres = ld_json.get("genre", [])
            if isinstance(ld_genres, str):
                genres = [ld_genres]
            elif isinstance(ld_genres, list):
                genres = [str(item).strip() for item in ld_genres if str(item).strip()]

        info_text = ""
        info_tag = soup.select_one("#info")
        if info_tag:
            info_text = info_tag.get_text("\n", strip=True)

        def extract_info_value(label: str) -> str:
            pattern = rf"^{re.escape(label)}\s*[:：]\s*(.+)$"
            for line in info_text.splitlines():
                match = re.match(pattern, line)
                if match:
                    return match.group(1).strip()
            return ""

        countries_raw = extract_info_value("制片国家/地区")
        countries = [item.strip() for item in re.split(r"\s*/\s*", countries_raw) if item.strip()]

        aka_raw = extract_info_value("又名")
        aka_titles = [item.strip() for item in re.split(r"\s*/\s*", aka_raw) if item.strip()]

        image_url = ""
        image_tag = soup.select_one('img[rel="v:image"]')
        if image_tag and image_tag.get("src"):
            image_url = image_tag.get("src")
        if not image_url:
            image_url = str(ld_json.get("image", ""))

        original_title = title
        if aka_titles:
            for aka in aka_titles:
                if not re.search(r"[\u4e00-\u9fff]", aka):
                    original_title = aka
                    break

        names = {
            "translatedTitle": title,
            "originalTitle": original_title or title,
            "akaTitles": aka_titles,
        }

        self.movie_info = {
            "names": names,
            "genres": genres,
            "countries": countries,
            "image_url": image_url,
            "year": year,
            "DoubanID": douban_id,
        }
