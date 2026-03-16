import streamlit as st
import requests
from bs4 import BeautifulSoup, NavigableString
from docx import Document
from io import BytesIO
import zipfile
import time
import random
from urllib.parse import urljoin

# --- 1. SET PAGE CONFIG (Must be first) ---
st.set_page_config(page_title="CUIMC Web-to-Word", page_icon="🩺", layout="wide")

# --- 2. INITIALIZE SESSION STATE ---
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

# --- 3. CUIMC THEMING & UI TWEAKS ---
def apply_custom_style():
    st.markdown("""
        <style>
        .stApp { background-color: #ffffff; }
        h1, h2, h3 { color: #1C3F60 !important; font-family: 'Helvetica Neue', Arial, sans-serif; font-weight: 700; }
        div.stButton > button:first-child { 
            background-color: #1C3F60; color: white; width: 100%; border-radius: 5px; border: none; font-weight: bold; padding: 10px;
        }
        div.stButton > button:first-child:hover { background-color: #2a5a8a; color: white; }
        .stSidebar { background-color: #f0f2f6; }
        [data-testid="stMetricValue"] { color: #1C3F60; font-weight: bold; }
        div.row-widget.stRadio > div { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #e9ecef; }
        </style>
    """, unsafe_allow_html=True)

# --- 4. SCRAPING, FORMATTING, & IMAGE EXTRACTION ---
def extract_content(url, retries=2):
    attempt = 0
    while attempt <= retries:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive'
            }
            
            time.sleep(random.uniform(1.0, 2.0))
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 429:
                if attempt < retries:
                    time.sleep(5) 
                    attempt += 1
                    continue
                return None, None, "RATE_LIMIT_ERROR"
                
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # --- TITLE EXTRACTION ---
            page_title = soup.find('title')
            h1_title = soup.find('h1')
            
            if page_title and page_title.get_text().strip():
                title_text = page_title.get_text().strip()
            elif h1_title and h1_title.get_text().strip():
                title_text = h1_title.get_text().strip()
            else:
                url_parts = [p for p in url.split('/') if p]
                title_text = url_parts[-1] if url_parts else "Columbia_Page"
            
            clean_title = "".join([c for c in title_text if c.isalnum() or c in [' ', '-', '_']]).strip()[:50]
            if not clean_title: clean_title = "Document"
            
            # --- AGGRESSIVE CLEANUP FOR OLDER SITES ---
            # 1. Standard HTML5 noise
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
                element.decompose()
                
            # 2. Hunt down older menu/sidebar divs and tables
            junk_keywords = ['nav', 'menu', 'sidebar', 'foot', 'head', 'breadcrumb', 'search', 'widget']
            for tag in soup.find_all(['div', 'ul', 'table', 'td']):
                # SAFETY CHECK: If this tag was inside another tag that was already destroyed, skip it!
                if tag.attrs is None:
                    continue
                
                # Safely parse classes whether it's a list or a string
                raw_class = tag.get('class', [])
                css_classes = " ".join(raw_class).lower() if isinstance(raw_class, list) else str(raw_class).lower()
                css_id = str(tag.get('id') or "").lower()
                
                attrs_string = css_classes + " " + css_id
                
                if any(word in attrs_string for word in junk_keywords):
                    # Ensure we don't delete the main content box by accident
                    if 'content' not in attrs_string and 'main' not in attrs_string and 'body' not in attrs_string:
                        tag.decompose()
                
            # --- TARGET THE REAL CONTENT ---
            content_area = (
                soup.find('main') or 
                soup.find('article') or 
                soup.find(id=lambda x: x and 'content' in x.lower()) or 
                soup.find(class_=lambda x: x and 'content' in str(x).lower()) or 
                soup.body
            )
            
            # --- IMAGE EXTRACTION ---
            images_data = []
            if content_area:
                img_tags = content_area.find_all('img')
                for idx, img in enumerate(img_tags):
                    if img.attrs is None: continue # Safety check
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if not src or src.startswith('data:'): 
                        continue 
                    
                    abs_url = urljoin(url, src)
                    try:
                        time.sleep(0.1) 
                        img_res = requests.get(abs_url, headers=headers, timeout=10)
                        if img_res.status_code == 200:
                            ext = ".jpg"
                            if ".png" in abs_url.lower(): ext = ".png"
                            elif ".gif" in abs_url.lower(): ext = ".gif"
                            images_data.append((f"image_{idx + 1:02d}{ext}", img_res.content))
                    except Exception:
                        pass 

            # --- TEXT EXTRACTION ---
            formatted_data = []
            tags_to_save = ['p', 'h2', 'h3', 'h4', 'li']
            
            if content_area:
                for element in content_area.find_all(tags_to_save):
                    if element.attrs is None: continue # Safety check
                    if not element.get_text(strip=True): continue
                        
                    chunk = {'tag': element.name, 'content': []}
                    for child in element.children:
                        if isinstance(child, NavigableString):
                            text_content = str(child).strip()
                            if text_content:
                                chunk['content'].append(('text', text_content + ' '))
                        elif child.name in ['b', 'strong']:
                            bold_text = child.get_text(strip=True)
                            if bold_text:
                                chunk['content'].append(('bold', bold_text + ' '))
                        else:
                            other_text = child.get_text(strip=True)
                            if other_text:
                                chunk['content'].append(('text', other_text + ' '))
                    
                    if chunk['content']:
                        formatted_data.append(chunk)
                
            return clean_title, formatted_data, images_data
            
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
                attempt += 1
            else:
                return None, None, str(e)

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

# --- 5. APP LAYOUT ---
apply_custom_style()

st.title("🩺 CUIMC Web-to-Word & Media Packager")
st.write("Extract clean text and images from URLs. All outputs are packaged into standard ZIP archives.")

# Dashboard Sidebar
with st.sidebar:
    st.header("📊 Dashboard")
    st.metric("Total Processed", st.session_state.total_converted)
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

# UNMISSABLE MODE SELECTOR
st.divider()
mode = st.radio(
    "**Choose Extraction Mode:**", 
    ["📄 Single URL Packager", "📦 Bulk List (Folders & Files)"], 
    horizontal=True
)
st.divider()

# --- SINGLE URL MODE ---
if mode == "📄 Single URL Packager":
    st.subheader("📄 Single Page Extraction")
    url_input = st.text_input("Paste target URL:", key="single_input")
    
    if st.button("Package Document & Media", key="btn_single"):
        with st.spinner("Scraping text and downloading images..."):
            clean_title, data, images = extract_content(url_input)
            
            if data == "RATE_LIMIT_ERROR":
                st.error("⚠️ Server is rate-limiting us. Please wait 60 seconds.")
            elif data is not None and isinstance(data, list):
                doc_io = create_word_doc(clean_title, data)
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                    zip_file.writestr(f"{clean_title}.docx", doc_io.getvalue())
                    for img_name, img_bytes in images:
                        zip_file.writestr(img_name, img_bytes)
                
                st.session_state.active_file = zip_buffer.getvalue()
                st.session_state.active_name = f"{clean_title}_Export.zip"
                st.session_state.total_converted += 1
                if clean_title not in st.session_state.history:
                    st.session_state.history.append(clean_title)
            else:
                st.error(f"Error: {images}")

    if st.session_state.active_file:
        st.success(f"✅ Ready: {st.session_state.active_name}")
        st.download_button(
            label="📥 Download ZIP Package",
            data=st.session_state.active_file,
            file_name=st.session_state.active_name,
            mime="application/zip"
        )

# --- BULK URL MODE ---
elif mode == "📦 Bulk List (Folders & Files)":
    st.subheader("📦 Bulk Batch Extraction")
    bulk_input = st.text_area("Paste URLs here (one per line):", height=200)
    
    if st.button("Process Bulk List", key="btn_bulk"):
        url_list = [u.strip() for u in bulk_input.split('\n') if u.strip()]
        if url_list:
            zip_buffer = BytesIO()
            success_count = 0
            failed_urls = []
            
            progress_bar = st.progress(0, text="Processing batch... Fetching images takes time to avoid firewalls.")
            
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for idx, url in enumerate(url_list):
                    clean_title, data, images = extract_content(url)
                    
                    if data is not None and isinstance(data, list):
                        folder_name = f"{idx + 1:02d}_{clean_title}"
                        doc_io = create_word_doc(clean_title, data)
                        zip_file.writestr(f"{folder_name}/{clean_title}.docx", doc_io.getvalue())
                        
                        for img_name, img_bytes in images:
                            zip_file.writestr(f"{folder_name}/{img_name}", img_bytes)
                            
                        st.session_state.total_converted += 1
                        if clean_title not in st.session_state.history:
                            st.session_state.history.append(clean_title)
                        success_count += 1
                    else:
                        failed_urls.append({'url': url, 'error': images}) 
                        
                    progress_bar.progress((idx + 1) / len(url_list), text=f"Processed {idx + 1} of {len(url_list)}")
            
            if success_count > 0:
                st.session_state.bulk_zip = zip_buffer.getvalue()
                st.success(f"✅ Successfully packaged {success_count} sites into folders!")
            else:
                st.error("Bulk processing failed entirely.")
                
            if failed_urls:
                st.warning(f"⚠️ {len(failed_urls)} URLs could not be processed:")
                for fail in failed_urls:
                    st.write(f"- {fail['url']} ({fail['error']})")
            
    if st.session_state.bulk_zip:
        st.download_button(
            label="📥 Download Master ZIP",
            data=st.session_state.bulk_zip,
            file_name="CUIMC_Master_Export.zip",
            mime="application/zip"
        )
