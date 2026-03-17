import streamlit as st
import pandas as pd
import os
import io
import subprocess
from urllib.parse import urlparse
from scrapy.linkextractors import IGNORED_EXTENSIONS

# --- 1. SET PAGE CONFIG ---
st.set_page_config(page_title="Healthcare SEO Crawler", page_icon="🕷️", layout="wide")

# --- 2. DEFINE BANNED EXTENSIONS ---
# Stop the crawler from downloading raw data files, zips, or medical documents
banned_extensions = IGNORED_EXTENSIONS + ['gz', 'txt', 'zip', 'csv', 'pdf', 'docx', 'xlsx', 'tar']

# --- 3. SCRAPY SPIDER SCRIPT GENERATOR ---
# Because Streamlit and Scrapy's "Twisted" engine don't like running in the same thread,
# we generate the spider as a separate python file and run it safely.
def create_spider_script(start_url, max_pages, output_file):
    domain = urlparse(start_url).netloc
    
    # Safely handle the page count setting to prevent the "None" string crash
    page_limit_code = ""
    if max_pages and str(max_pages).lower() != "none" and int(max_pages) > 0:
        page_limit_code = f"'CLOSESPIDER_PAGECOUNT': {int(max_pages)},"
        
    script_content = f"""
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

class SEOSitemapSpider(CrawlSpider):
    name = 'seo_spider'
    allowed_domains = ['{domain}']
    start_urls = ['{start_url}']
    
    # 1. FILE DOWNLOAD FIX: Tell the LinkExtractor to ignore data files
    rules = (
        Rule(
            LinkExtractor(deny_extensions={banned_extensions}), 
            callback='parse_item', 
            follow=True
        ),
    )

    custom_settings = {{
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_MAXSIZE': 5242880, # Hard cap at 5MB to stop giant .gz file downloads
