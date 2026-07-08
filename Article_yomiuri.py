from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import datetime
from urllib.parse import urljoin
import pandas as pd
import streamlit as st

# Function to scrape articles from Yomiuri
def scrape_yomiuri_articles():
    st.write("Starting to scrape Yomiuri articles...")
    browser = webdriver.Chrome()
    base_url = 'https://www.yomiuri.co.jp/web-search/?st=1&wo=%E6%97%A5%E9%9F%93&ac=srch&ar=1&fy=&fm=&fd=&ty=&tm=&td='
    all_articles = []
    current_page = 1
    max_articles = 25  # 최대 수집 기사 수

    while len(all_articles) < max_articles:
        page_url = f"{base_url}&paged={current_page}" if current_page > 1 else base_url
        browser.get(page_url)
        time.sleep(2)
        soup = BeautifulSoup(browser.page_source, 'html.parser')
        articles_elements = soup.select('div.search-article-list > ul > li article div.p-list-item__inner > h3 > a')

        for idx, article in enumerate(articles_elements):
            if len(all_articles) >= max_articles:
                break
            try:
                title = article.text.strip()
                article_url = urljoin(base_url, article['href'])
                browser.get(article_url)
                time.sleep(2)
                article_soup = BeautifulSoup(browser.page_source, 'html.parser')
                title_content_element = article_soup.select('body > div.layout-contents > div.layout-contents__main > div.uni-scrap > article > div.article-header > h1')
                title_content = title_content_element[0].text.strip() if title_content_element else 'No Title Content'
                date_element = article_soup.select('body > div.layout-contents > div.layout-contents__main > div.uni-scrap > article > div.article-header > div > div.c-article-header-date > time')
                date = date_element[0].text.strip() if date_element else 'No Date'
                content = []
                paragraph_idx = 1
                while True:
                    content_element = article_soup.select(f'body > div.layout-contents > div.layout-contents__main > div.uni-scrap > article > div.p-main-contents > p.par{paragraph_idx}')
                    if content_element:
                        content.append(content_element[0].text.strip())
                        paragraph_idx += 1
                    else:
                        break
                content = "\n".join(content) if content else 'No Content'
                collection_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                all_articles.append({
                    'title': title,
                    'url': article_url,
                    'date': date,
                    'title_content': title_content,
                    'content': content,
                    'collection_time': collection_time
                })
                st.write(f"Yomiuri Articles Collected: {len(all_articles)}")
                browser.back()
                time.sleep(2)
            except Exception as e:
                st.error(f"Error occurred while processing article at index {idx + 1}: {e}")
                continue
        current_page += 1

    df = pd.DataFrame(all_articles)
    df.to_csv('yomiuri_articles_converted.csv', index=False, encoding='utf-8-sig')
    st.success("Yomiuri articles collection complete.")
    browser.quit()
