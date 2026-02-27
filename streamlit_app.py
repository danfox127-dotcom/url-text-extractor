import streamlit as st
import requests
from bs4 import BeautifulSoup, NavigableString
from docx import Document
from io import BytesIO
import zipfile

# --- 1. INITIALIZE SESSION STATE ---
# We use this to keep data alive across button clicks
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
        .stButton > button { background-color: #1C3F60; color: white; width: 100%; border-radius: 5px; border: none; }
        .stButton > button:hover { background-color: #2a5a8a; color: white; }
        .stSidebar { background-color: #e9ecef; }
        [data-testid="stMetricValue"] { color: #1C3F60; }
        </style>
    """, unsafe_allow_html=True)

# --- 3. SCRAPING & FORMATTING LOGIC ---
def extract_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Title Detection
        page_title = soup.find('h1')
        title_text = page_title.get_text().strip() if page_title else url.split('/')[-1]
        
        # Cleanup
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

def create_word_doc(title, formatted_data):
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
tabs = st.tabs(["Single URL", "Bulk ZIP Download"])

with tabs[0]:
    url_input = st.text_input("Paste target URL:", key="single_input")
    if st.button("Generate Word Document", key="btn_single"):
        with st.spinner("Processing..."):
            title, data = extract_content(url_input)
            if data and isinstance(data, list):
                st.session_state.active_file = create_word_doc(title, data)
                st.session_state.active_name = f"{title}.docx"
                st.session_state.total_converted += 1
                if title not in st.session_state.history:
                    st.session_state.history.append(title)
            else:
                st.error(f"Error: {data}")

    if st.session_state.active_file:
        st.success(f"Document Generated: {st.session_state.active_name}")
        st.download_button(
            label="📥 Download Word File",
            data=st.session_state.active_file,
            file_name=st.session_state.active_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

with tabs[1]:
    bulk_input = st.text_area("Paste URLs (one per line):", height=200)
    if st.button("Process Bulk List", key="btn_bulk"):
        url_list = [u.strip() for u in bulk_input.split('\n') if u.strip()]
        if url_list:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for url in url_list:
                    title, data = extract_content(url)
                    if data and isinstance(data, list):
                        doc_io = create_word_doc(title, data)
                        # Clean filename
                        clean_title = "".join([c for c in title if c.isalnum() or c==' ']).rstrip()
                        zip_file.writestr(f"{clean_title}.docx", doc_io.getvalue())
                        st.session_state.total_converted += 1
                        if title not in st.session_state.history:
                            st.session_state.history.append(title)
            
            st.session_state.bulk_zip = zip_buffer.getvalue()
            
    if st.session_state.bulk_zip:
        st.success("ZIP Archive Ready!")
        st.download_button(
            label="📥 Download ZIP Archive",
            data=st.session_state.bulk_zip,
            file_name="cuimc_batch_files.zip",
            mime="application/zip"
        )
