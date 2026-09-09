"""JoongAng Ilbo news scraper."""

import time
import datetime
from typing import List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .base import BaseCrawler
from ..schemas import Article
from ..config import DATA_DIR


class JungangCrawler(BaseCrawler):
    """Scraper for JoongAng Ilbo (중앙일보)."""

    def __init__(self, max_articles: int = 15, headless: bool = True):
        super().__init__(outlet_name="JoongAng Ilbo", country="Korea", max_articles=max_articles)
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

    def scrape(self, keyword: Optional[str] = "한일") -> List[Article]:
        driver = None
        articles: List[Article] = []
        base_url = (
            f"https://www.joongang.co.kr/search/news?keyword={keyword}&startDate=&endDate=&searchin={keyword}"
            "&accurateWord=&stopword=&sourceCode=1%2C3&sfield=all&serviceCode=10%2C11%2C12%2C13%2C15%2C14%2C35%2C18"
        )

        try:
            driver = self._get_driver()
            driver.get(base_url)
            time.sleep(2)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            elements = soup.select("#container > section > div > section > ul > li > div > h2 > a")

            for element in elements:
                if len(articles) >= self.max_articles:
                    break
                try:
                    title = element.text.strip()
                    if title.startswith("[사진]") or not title:
                        continue

                    article_url = urljoin(base_url, element.get("href", ""))
                    driver.get(article_url)
                    time.sleep(1.5)

                    art_soup = BeautifulSoup(driver.page_source, "html.parser")
                    date_elem = art_soup.select(
                        "#container > section > article > header > div.datetime > div > p:nth-child(2)"
                    )
                    date_str = date_elem[0].text.strip() if date_elem else ""

                    content_elems = art_soup.select("div#article_body p")
                    if not content_elems:
                        content_elems = art_soup.select("div.p-main-contents p")
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
            filepath = str(DATA_DIR / "jungang_articles_converted.csv")

        data = [a.model_dump() for a in articles]
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        return filepath
