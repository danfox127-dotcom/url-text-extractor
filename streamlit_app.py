import streamlit as st
import requests
from bs4 import BeautifulSoup, NavigableString
from docx import Document
from io import BytesIO
import zipfile
import time
import random
from PIL import Image
from urllib.parse import urljoin
import io

# --- 1. SET PAGE CONFIG (Must be first) ---
st.set_page_config(page_title="CUIMC Web Extractor", page_icon="🩺", layout="wide")

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

# --- 3. CUIMC THEMING ---
def apply_custom_style():
    st.markdown("""
        <style>
        .stApp { background-color: #f8f9fa; }
        h1 { color: #1C3F60 !important; font-family: 'Helvetica Neue', Arial, sans-serif; font-weight: 700; }
        .stButton > button { background-color: #1C3F60; color: white; width: 100%; border-radius: 5px; border: none; font-weight: bold; }
        .stButton > button:hover { background-color: #2a5a8a; color: white; }
        .stSidebar { background-color: #e9ecef; }
        [data-testid="stMetricValue"] { color: #1C3F60; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

# --- 4. SCRAPING & FORMATTING LOGIC ---
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
            
            # Slightly longer delay for large batches to avoid firewalls
            time.sleep(random.uniform(1.5, 3.0))
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 429:
                if attempt < retries:
                    time.sleep(5)  # Wait 5 seconds and retry if rate limited
                    attempt += 1
                    continue
                return None, "RATE_LIMIT_ERROR"
                
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Better Title Detection to fix the "Trailing Slash" bug
            page_title = soup.find('h1')
            if page_title:
                title_text = page_title.get_text().strip()
            else:
                # Filter out empty strings from trailing slashes
                url_parts = [p for p in url.split('/') if p]
                title_text = url_parts[-1] if url_parts else "Columbia_Page"
            
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
            
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
                attempt += 1
            else:
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

# --- 5. APP LAYOUT ---
apply_custom_style()

st.title("🩺 CUIMC Web Extractor")

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

# --- ADDED TAB 3 FOR IMAGES ---
tab1, tab2, tab3 = st.tabs(["📄 Single URL (Word)", "📦 Bulk ZIP (Word)", "🖼️ Extract Images (ZIP)"])

with tab1:
    url_input = st.text_input("Paste target URL:", key="single_input")
    if st.button("Generate Word Document", key="btn_single"):
        with st.spinner("Processing..."):
            title, data = extract_content(url_input)
            if data == "RATE_LIMIT_ERROR":
                st.error("⚠️ Server is rate-limiting us. Please wait 60 seconds.")
            elif data and isinstance(data, list):
                st.session_state.active_file = create_word_doc(title, data)
                st.session_state.active_name = f"{title}.docx"
                st.session_state.total_converted += 1
                if title not in st.session_state.history:
                    st.session_state.history.append(title)
            else:
                st.error(f"Error: {data}")

    if st.session_state.active_file:
        st.success(f"✅ Ready: {st.session_state.active_name}")
        st.download_button(
            label="📥 Download Word File",
            data=st.session_state.active_file,
            file_name=st.session_state.active_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

with tab2:
    bulk_input = st.text_area("Paste URLs (one per line):", height=200)
    if st.button("Process Bulk List", key="btn_bulk"):
        url_list = [u.strip() for u in bulk_input.split('\n') if u.strip()]
        if url_list:
            zip_buffer = BytesIO()
            success_count = 0
            failed_urls = []
            
            progress_text = "Processing URLs... This takes a few moments to avoid server blocks."
            progress_bar = st.progress(0, text=progress_text)
            
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for idx, url in enumerate(url_list):
                    title, data = extract_content(url)
                    
                    if data and isinstance(data, list):
                        doc_io = create_word_doc(title, data)
                        
                        clean_title = "".join([c for c in title if c.isalnum() or c==' ']).rstrip()
                        if not clean_title: clean_title = "Document"
                        safe_filename = f"{idx + 1:02d}_{clean_title}.docx"
                        
                        zip_file.writestr(safe_filename, doc_io.getvalue())
                        st.session_state.total_converted += 1
                        if title not in st.session_state.history:
                            st.session_state.history.append(title)
                        success_count += 1
                    else:
                        failed_urls.append({'url': url, 'error': data})
                        
                    progress_bar.progress((idx + 1) / len(url_list), text=f"Processed {idx + 1} of {len(url_list)}")
            
            if success_count > 0:
                st.session_state.bulk_zip = zip_buffer.getvalue()
                st.success(f"✅ Successfully processed {success_count} files!")
            else:
                st.error("Bulk processing failed entirely.")
                
            if failed_urls:
                st.warning(f"⚠️ {len(failed_urls)} URLs could not be processed:")
                for fail in failed_urls:
                    st.write(f"- {fail['url']} ({fail['error']})")
            
    if st.session_state.bulk_zip:
        st.download_button(
            label="📥 Download ZIP Archive",
            data=st.session_state.bulk_zip,
            file_name="cuimc_batch_files.zip",
            mime="application/zip"
        )

# ==========================================
# TAB 3: INLINE IMAGE EXTRACTOR & ZIPPER
# ==========================================
with tab3:
    st.header("🖼️ Extract & Convert Images")
    st.markdown("Scrape all content images from a page, convert WebP/PNG to standard JPG, and download them as a ZIP.")

    target_url_img = st.text_input("Enter Page URL to Scrape:", key="img_input")
    
    with st.expander("⚙️ Adjust Scraping Filters", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            min_width = st.number_input("Minimum Width (px)", value=200, step=50, help="Filters out small UI icons.")
        with col2:
            min_height = st.number_input("Minimum Height (px)", value=150, step=50, help="Filters out small UI buttons.")

    if st.button("🔍 Extract Images", type="primary", key="btn_img"):
        if target_url_img:
            with st.spinner("Scraping page, filtering junk, and packing ZIP file..."):
                try:
                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                    response = requests.get(target_url_img, headers=headers, timeout=15)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    images = soup.find_all('img')
                    extracted_images_data = [] 
                    
                    st.subheader("Extracted Content Images")
                    
                    for img in images:
                        img_url = img.get('src')
                        if not img_url: continue
                            
                        # Nomenclature Filter
                        junk_keywords = ['logo', 'icon', 'social', 'facebook', 'twitter', 'instagram', 'svg', 'button', 'bg', 'footer']
                        if any(junk in img_url.lower() for junk in junk_keywords): continue
                            
                        img_url = urljoin(target_url_img, img_url)
                        
                        try:
                            img_response = requests.get(img_url, headers=headers, timeout=5)
                            img_response.raise_for_status()
                            image = Image.open(io.BytesIO(img_response.content))
                            
                            # Size Filter
                            width, height = image.size
                            if width >= min_width and height >= min_height:
                                
                                if image.mode in ("RGBA", "P"):
                                    image = image.convert("RGB")
                                
                                img_byte_arr = io.BytesIO()
                                image.save(img_byte_arr, format='JPEG', quality=90)
                                img_bytes = img_byte_arr.getvalue()
                                
                                file_name = f"extracted_{width}x{height}_{len(extracted_images_data)}.jpg"
                                extracted_images_data.append((file_name, img_bytes, image, img_url, width, height))
                                
                        except Exception:
                            pass 
                            
                    if len(extracted_images_data) == 0:
                        st.warning("No images found that match your minimum size criteria. Try lowering the px threshold.")
                    else:
                        st.success(f"✅ Successfully converted {len(extracted_images_data)} images.")
                        
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for file_name, img_bytes, _, _, _, _ in extracted_images_data:
                                zip_file.writestr(file_name, img_bytes)
                        
                        st.download_button(
                            label="📦 Download All Images (ZIP)",
                            data=zip_buffer.getvalue(),
                            file_name="migrated_images.zip",
                            mime="application/zip",
                            type="primary",
                            use_container_width=True
                        )
                        st.markdown("---")
                        
                        for file_name, img_bytes, img_obj, url, w, h in extracted_images_data:
                            st_col1, st_col2 = st.columns([1, 3])
                            with st_col1:
                                st.image(img_obj, use_container_width=True)
                            with st_col2:
                                st.markdown(f"**Source:** `{url.split('/')[-1]}`")
                                st.markdown(f"**Dimensions:** {w} x {h} px")
                            st.markdown("---")
                        
                except Exception as e:
                    st.error(f"Failed to scrape URL. Error: {e}")
