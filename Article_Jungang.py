from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import datetime
from urllib.parse import urljoin
import pandas as pd
import streamlit as st

# Function to scrape articles from Jungang
def scrape_jungang_articles():
    st.write("Starting to scrape Jungang articles...")
    browser = webdriver.Chrome()
    base_url = 'https://www.joongang.co.kr/search/news?keyword=%ED%95%9C%EC%9D%BC&startDate=&endDate=&searchin=%ED%95%9C%EC%9D%BC&accurateWord=&stopword=&sourceCode=1%2C3&sfield=all&serviceCode=10%2C11%2C12%2C13%2C15%2C14%2C35%2C18'
    all_articles = []
    max_articles = 25  # 최대 수집 기사 수

    browser.get(base_url)
    time.sleep(2)
    soup = BeautifulSoup(browser.page_source, 'html.parser')
    articles_elements = soup.select('#container > section > div > section > ul > li > div > h2 > a')

    for idx, article in enumerate(articles_elements):
        if len(all_articles) >= max_articles:
            break
        try:
            if article.text.strip().startswith('[사진]'):
                continue
            title = article.text.strip()
            article_url = urljoin(base_url, article['href'])
            browser.get(article_url)
            time.sleep(2)
            browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            article_soup = BeautifulSoup(browser.page_source, 'html.parser')
            title_content_element = article_soup.select('#container > section > article > header > h1')
            title_content = title_content_element[0].text.strip() if title_content_element else 'No Title Content'
            date_element = article_soup.select('#container > section > article > header > div.datetime > div > p:nth-child(2)')
            date = date_element[0].text.strip() if date_element else 'No Date'
            content_elements = article_soup.select('div#article_body p')
            if not content_elements:
                content_elements = article_soup.select('div.p-main-contents p')
            content = [element.text.strip() for element in content_elements if element.text.strip()]
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
            st.write(f"Jungang Articles Collected: {len(all_articles)}")
            browser.back()
            time.sleep(2)
        except Exception as e:
            st.error(f"Error occurred while processing article at index {idx + 1}: {e}")
            continue

    df = pd.DataFrame(all_articles)
    df.to_csv('jungang_articles_converted.csv', index=False, encoding='utf-8-sig')
    st.success("Jungang articles collection complete.")
    browser.quit()