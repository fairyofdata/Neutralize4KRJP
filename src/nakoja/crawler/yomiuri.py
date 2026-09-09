"""Yomiuri Shimbun news scraper."""

import time
from typing import List, Optional
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .base import BaseCrawler
from ..schemas import Article
from ..config import DATA_DIR


class YomiuriCrawler(BaseCrawler):
    """Scraper for Yomiuri Shimbun (読売新聞)."""

    def __init__(self, max_articles: int = 15, headless: bool = True):
        super().__init__(outlet_name="Yomiuri Shimbun", country="Japan", max_articles=max_articles)
        self.headless = headless

    def _get_driver(self):
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        return webdriver.Chrome(options=chrome_options)

    def scrape(self, keyword: Optional[str] = "日韓") -> List[Article]:
        driver = None
        articles: List[Article] = []
        base_url = f"https://www.yomiuri.co.jp/search/?kwd={keyword}"

        try:
            driver = self._get_driver()
            driver.get(base_url)
            time.sleep(2)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            elements = soup.select("div.p-search-results div.p-list-item__body h3 a")

            for element in elements:
                if len(articles) >= self.max_articles:
                    break
                try:
                    title = element.text.strip()
                    article_url = element.get("href", "")
                    if not title or not article_url:
                        continue

                    driver.get(article_url)
                    time.sleep(1.5)

                    art_soup = BeautifulSoup(driver.page_source, "html.parser")
                    time_elem = art_soup.select("time")
                    date_str = time_elem[0].text.strip() if time_elem else ""

                    content_elems = art_soup.select("div.p-main-contents p")
                    if not content_elems:
                        content_elems = art_soup.select("div#article_body p")

                    body_paragraphs = [p.text.strip() for p in content_elems if p.text.strip()]
                    body_text = "\n".join(body_paragraphs)

                    if not body_text or len(body_text) < 50:
                        continue

                    articles.append(
                        Article(
                            title=title,
                            content=body_text,
                            outlet=self.outlet_name,
                            country=self.country,
                            url=article_url,
                            date=date_str,
                        )
                    )
                except Exception:
                    continue

        finally:
            if driver:
                driver.quit()

        return articles

    def save_to_csv(self, articles: List[Article], filepath: Optional[str] = None) -> str:
        """Saves scraped articles to CSV."""
        if not filepath:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            filepath = str(DATA_DIR / "yomiuri_articles_converted.csv")

        data = [a.model_dump() for a in articles]
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        return filepath
