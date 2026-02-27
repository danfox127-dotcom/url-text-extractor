import streamlit as st
import requests
from bs4 import BeautifulSoup, NavigableString
from docx import Document
from io import BytesIO
import zipfile
import time
import random

# --- 1. INITIALIZE SESSION STATE ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'total_converted' not in st.session_state:
    st.session_state.total_converted = 0
if 'active_file' not in st.session_state:
    st.session_state.active_file = None
if 'active_name' not in st.session_state:
    st.session_state.active_name = ""
if 'bulk_zip' not in st.session_state:
    st.session_state.bulk_zip = None

# --- 2. CUIMC THEMING ---
def apply_custom_style():
    st.markdown("""
        <style>
        .stApp { background-color: #f8f9fa; }
        h1 { color: #1C3F60 !important; font-family: 'Helvetica Neue', Arial, sans-serif; font-weight: 700; }
        .stButton > button { background-color: #1C3F60; color: white; width: 100%; border-radius: 5px; border: none; font-weight: bold; }
        .stButton > button:hover { background-color: #2a5a8a; color: white; }
        .stSidebar { background-color: #e9ecef; }
        [data-testid="stMetricValue"] { color: #1C3F60; font-weight: bold; }
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px 5px 0 0; padding: 10px; }
        .stTabs [aria-selected="true"] { background-color: #1C3F60; color: white; }
        </style>
    """, unsafe_allow_html=True)

# --- 3. SCRAPING & FORMATTING LOGIC ---
def extract_content(url):
    try:
        # HUMAN SPOOFING HEADERS
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Add a "human" delay to prevent 429 errors
        time.sleep(random.uniform(1.0, 2.5))
        
        response = requests.get(url, headers=headers, timeout=15)
        
        # Specific handling for 429
        if response.status_code == 429:
            return None, "RATE_LIMIT_ERROR"
            
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Title Detection
        page_title = soup.find('h1')
        title_text = page_title.get_text().strip() if page_title else url.split('/')[-1]
        
        # Cleanup page noise
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
            element.decompose()
            
        content_area = soup.find('main') or soup.find('article') or soup.body
        formatted_data = []
        tags_to_save = ['p', 'h2', 'h3', 'h4', 'li']
        
        for element in content_area.find_all(tags_to_save):
            chunk = {'tag': element.name, 'content': []}
            for child in element.children:
                if isinstance(child, NavigableString):
                    chunk['content'].append(('text', str(child)))
                elif child.name in ['b', 'strong']:
                    chunk['content'].append(('bold', child.get_text()))
                else:
                    chunk['content'].append(('text', child.get_text()))
            formatted_data.append(chunk)
        return title_text, formatted_data

    except requests.exceptions.HTTPError as e:
        return None, f"HTTP Error: {e.response.status_code}"
    except Exception as e:
        return None, str(e)

def create_word_doc(title, formatted_data):
    doc = Document()
    doc.add_heading(title, 0)
    for chunk in formatted_data:
        p_style = 'List Bullet' if chunk['tag'] == 'li' else None
        p = doc.add_paragraph(style=p_style) if p_style else doc.add_paragraph()
        
        for style_type, text in chunk['content']:
            run = p.add_run(text)
            if style_type == 'bold' or chunk['tag'] in ['h2', 'h3', 'h4']:
                run.bold = True
    
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# --- 4. APP LAYOUT ---
st.set_page_config(page_title="CUIMC Web-to-Word", page_icon="🩺", layout="wide")
apply_custom_style()

st.title("🩺 CUIMC Web-to-Word Converter")

# Sidebar
with st.sidebar:
    st.header("📊 Dashboard")
    st.metric("Total Files Processed", st.session_state.total_converted)
    st.divider()
    st.header("📜 Session History")
    for item in reversed(st.session_state.history):
        st.write(f"• {item}")
    if st.button("Clear All Data"):
        st.session_state.history = []
        st.session_state.total_converted = 0
        st.session_state.active_file = None
        st.session_state.bulk_zip = None
        st.rerun()

# Main Tabs
tabs = st.tabs(["
