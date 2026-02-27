import streamlit as st
import requests
from bs4 import BeautifulSoup, NavigableString
from docx import Document
from io import BytesIO
import zipfile
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# --- 1. INITIALIZE SESSION STATE ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'total_converted' not in st.session_state:
    st.session_state.total_converted = 0

# --- 2. STYLING ---
def apply_custom_style():
    st.markdown("""
        <style>
        .stApp { background-color: #f8f9fa; }
        h1 { color: #1C3F60 !important; font-family: 'Helvetica Neue', Arial, sans-serif; }
        div.stButton > button:first-child { background-color: #1C3F60; color: white; width: 100%; border-radius: 5px; }
        .stSidebar { background-color: #e9ecef; }
        </style>
    """, unsafe_allow_html=True)

# --- 3. CORE LOGIC ---
def extract_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        page_title = soup.find('h1')
        title_text = page_title.get_text().strip() if page_title else url.split('/')[-1]
        
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.decompose()
            
        content_area = soup.find('main') or soup.body
        formatted_data = []
        tags_to_save = ['p', 'h2', 'h3', 'h4', 'li']
        
        for element in content_area.find_all(tags_to_save):
            chunk = {'tag': element.name, 'content': []}
            for child in element.children:
                if isinstance(child, NavigableString):
                    chunk['content'].append(('text', child))
                elif child.name in ['b', 'strong']:
                    chunk['content'].append(('bold', child.get_text()))
                else:
                    chunk['content'].append(('text', child.get_text()))
            formatted_data.append(chunk)
        return title_text, formatted_data
    except Exception as e:
        return None, str(e)

def create_word_doc(title, formatted_data, add_toc=False):
    doc = Document()
    doc.add_heading(title, 0)
    for chunk in formatted_data:
        p = doc.add_paragraph(style='List Bullet') if chunk['tag'] == 'li' else doc.add_paragraph()
        for style_type, text in chunk['content']:
            run = p.add_run(text)
            if style_type == 'bold' or chunk['tag'] in ['h2', 'h3', 'h4']:
                run.bold = True
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# --- 4. UI LAYOUT ---
apply_custom_style()
st.title("🩺 CUIMC Web-to-Word Converter")

with st.sidebar:
    st.header("📊 Dashboard")
    st.metric("Total Processed", st.session_state.total_converted)
    st.divider()
    st.header("📜 Session History")
    for item in reversed(st.session_state.history):
        st.write(f"• {item}")
    if st.button("Clear History"):
        st.session_state.history = []
        st.rerun()

tabs = st.tabs(["Single URL", "Bulk & ZIP"])

with tabs[0]:
    single_url = st.text_input("Paste URL:")
    if st.button("Convert Single"):
        title, data = extract_content(single_url)
        if data and isinstance(data, list):
            doc_file = create_word_doc(title, data)
            st.session_state.total_converted += 1
            st.session_state.history.append(title)
            st.download_button("📥 Download Word Doc", data=doc_file, file_name=f"{title}.docx")

with tabs[1]:
    bulk_urls = st.text_area("URLs (one per line):")
    if st.button("Generate ZIP"):
        url_list = [u.strip() for u in bulk_urls.split('\n') if u.strip()]
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for url in url_list:
                title, data = extract_content(url)
                if data and isinstance(data, list):
                    doc_io = create_word_doc(title, data)
                    zip_file.writestr(f"{title}.docx", doc_io.getvalue())
                    st.session_state
