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
import csv
import re

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
def extract_images(url, min_width=200, min_height=150, retries=2):
    attempt = 0
    while attempt <= retries:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            time.sleep(random.uniform(1.0, 2.0))
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 429:
                if attempt < retries:
                    time.sleep(3)
                    attempt += 1
                    continue
                return []
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            extracted_images = []
            
            for img in soup.find_all('img'):
                # Try multiple attributes for lazy loading
                img_url = img.get('data-src') or img.get('data-lazy-src') or img.get('src')
                
                # Check srcset if needed
                if not img_url and img.get('srcset'):
                    img_url = img.get('srcset').split(',')[0].split(' ')[0]
                    
                if not img_url: continue
                    
                junk_keywords = ['logo', 'icon', 'social', 'facebook', 'twitter', 'instagram', 'svg', 'button', 'bg', 'footer', 'avatar']
                if any(junk in img_url.lower() for junk in junk_keywords): continue
                    
                img_url = urljoin(url, img_url)
                try:
                    img_resp = requests.get(img_url, headers=headers, timeout=5)
                    image = Image.open(io.BytesIO(img_resp.content))
                    w, h = image.size
                    if w >= min_width and h >= min_height:
                        if image.mode in ("RGBA", "P", "LA"): image = image.convert("RGB")
                        img_bytes = io.BytesIO()
                        image.save(img_bytes, format='JPEG', quality=90)
                        file_name = f"extracted_{w}x{h}_{len(extracted_images)}.jpg"
                        extracted_images.append((file_name, img_bytes.getvalue()))
                except:
                    passtext_content = str(child).replace('\n', ' ')
                        chunk['content'].append(('text', text_content))
                    elif child.name in ['b', 'strong']:
                        chunk['content'].append(('bold', child.get_text(separator=' ') + " "))
                    else:
                        chunk['content'].append(('text', child.get_text(separator=' ') + " "
                attempt += 1
            else:
                return []

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
            
            time.sleep(random.uniform(1.5, 3.0))
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 429:
                if attempt < retries:
                    time.sleep(5)
                    attempt += 1
                    continue
                return None, "RATE_LIMIT_ERROR"
                
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            page_title = soup.find('h1')
            if page_title:
                title_text = page_title.get_text().strip()
            else:
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

def clean_filename(title):
    clean = "".join([c for c in title if c.isalnum() or c==' ']).strip().replace(' ', '_')
    return clean if clean else "extracted_content"

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

# --- 4 TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📄 Single URL (Word)", "📦 Bulk ZIP (Word)", "🖼️ Extract Images (ZIP)", "🗂️ Extract ALL (Word + Images)"])

with tab1:
    url_input = st.text_input("Paste target URL:", key="single_input")
    if st.button("Generate Word Document", key="btn_single"):
        with st.spinner("Processing..."):
            title, data = extract_content(url_input)
            if data == "RATE_LIMIT_ERROR":
                st.error("⚠️ Server is rate-limiting us. Please wait 60 seconds.")
            elif data and isinstance(data, list):
                st.session_state.active_file = create_word_doc(title, data)
                st.session_state.active_name = f"{clean_filename(title)}.docx"
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
    st.header("📦 Bulk Process (CSV or List)")
    st.markdown("Upload a CSV or paste URLs. Organizes into folders. Select 'Include Images' for God Mode Bulk.")
    
    col1, col2 = st.columns(2)
    with col1:
        bulk_csv = st.file_uploader("Upload CSV (Finds URLs automatically)", type=['csv'])
    with col2:
        bulk_input = st.text_area("Or paste URLs (one per line):", height=100)
        
    extract_images_also = st.checkbox("🖼️ Include Images (God Mode Bulk)", value=False)
    
    if st.button("Process Bulk List", key="btn_bulk"):
        url_list = []
        if bulk_csv:
            csv_text = bulk_csv.getvalue().decode('utf-8').splitlines()
            reader = csv.reader(csv_text)
            for row in reader:
                for cell in row:
                    if cell.strip().startswith('http://') or cell.strip().startswith('https://'):
                        url_list.append(cell.strip())
        
        url_list += [u.strip() for u in bulk_input.split('\n') if u.strip() and u.strip().startswith('http')]
        url_list = list(dict.fromkeys(url_list)) # Remove duplicates

        if url_list:
            zip_buffer = BytesIO()
            success_count = 0
            
            progress_bar = st.progress(0, text="Processing URLs...")
            
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for idx, url in enumerate(url_list):
                    progress_bar.progress(idx / len(url_list), text=f"Processing {idx + 1} of {len(url_list)}: {url[:30]}...")
                    
                    title, data = extract_content(url)
                    
                    if data and isinstance(data, list):
                        safe_title = clean_filename(title)
                        folder_name = f"{idx + 1:03d}_{safe_title}"
                        
                        doc_io = create_word_doc(title, data)
                        zip_file.writestr(f"{folder_name}/{safe_title}.docx", doc_io.getvalue())
                        
                        if extract_images_also:
                            images_data = extract_images(url)
                            for file_name, img_bytes in images_data:
                                zip_file.writestr(f"{folder_name}/images/{file_name}", img_bytes)
                                
                        st.session_state.total_converted += 1
                        if title not in st.session_state.history:
                            st.session_state.history.append(title)
                        success_count += 1
            
            progress_bar.progress(1.0, text="Done!")
            
            if success_count > 0:
                st.session_state.bulk_zip = zip_buffer.getvalue()
                st.success(f"✅ Successfully processed {success_count} URLs!")
            else:
                st.error("Bulk processing failed entirely.")
            
    if st.session_state.bulk_zip:
        st.download_button(
            label="📥 Download ZIP Archive",
            data=st.session_state.bulk_zip,
            file_name="cuimc_batch_files.zip",
            mime="application/zip"
        )

with tab3:
    st.header("🖼️ Extract & Convert Images")
    st.markdown("Scrape images, convert WebP/PNG to JPG, and download as a dynamically named ZIP.")

    target_url_img = st.text_input("Enter Page URL to Scrape:", key="img_input")
    
    with st.expander("⚙️ Adjust Scraping Filters", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            min_width = st.number_input("Minimum Width (px)", value=200, step=50)
        with col2:
            min_height = st.number_input("Minimum Height (px)", value=150, step=50)

    if st.button("🔍 Extract Images", type="primary", key="btn_img"):
        if target_url_img:
            with st.spinner("Scraping page, filtering junk, and packing ZIP file..."):
                try:
                    # Get page title for ZIP
                    title, _ = extract_content(target_url_img)
                    page_name = title if title else "Images"
                    zip_filename = f"{clean_filename(page_name)}.zip"
                    
                    extracted_images_data = extract_images(target_url_img, min_width, min_height)
                            
                    if not extracted_images_data:
                        st.warning("No images found matching criteria.")
                    else:
                        st.success(f"✅ Extracted {len(extracted_images_data)} images.")
                        
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for file_name, img_bytes in extracted_images_data:
                                zip_file.writestr(file_name, img_bytes)
                        
                        st.download_button(
                            label=f"📦 Download {zip_filename}",
                            data=zip_buffer.getvalue(),
                            file_name=zip_filename,
                            mime="application/zip",
                            type="primary",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"Failed to scrape URL. Error: {e}")

# ==========================================
# TAB 4: THE GOD MODE (WORD + IMAGES)
# ==========================================
with tab4:
    st.header("🗂️ Extract ALL (Word + Images)")
    st.markdown("Rip the formatted text AND all clinical images into a single, perfectly organized ZIP file.")
    
    target_url_all = st.text_input("Enter Page URL:", key="all_input")
    
    with st.expander("⚙️ Image Scraping Filters", expanded=False):
        colA, colB = st.columns(2)
        with colA:
            min_w = st.number_input("Minimum Image Width (px)", value=200, step=50, key="w_all")
        with colB:
            min_h = st.number_input("Minimum Image Height (px)", value=150, step=50, key="h_all")

    if st.button("🚀 Extract Full Page", type="primary", key="btn_all"):
        if target_url_all:
            with st.spinner("Scraping text, converting images, and building your master ZIP..."):
                try:
                    # 1. Grab the Text
                    title, data = extract_content(target_url_all)
                    if data == "RATE_LIMIT_ERROR" or not isinstance(data, list):
                        st.error("Text extraction failed or rate limited.")
                        st.stop()
                        
                    doc_io = create_word_doc(title, data)
                    safe_title = clean_filename(title)
                    master_zip_name = f"{safe_title}_Full_Export.zip"
                    
                    # 2. Grab the Images
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    response = requests.get(target_url_all, headers=headers, timeout=15)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    extracted_images = []
                    for img in soup.find_all('img'):
                        img_url = img.get('src')
                        if not img_url: continue
                        
                        junk_keywords = ['logo', 'icon', 'social', 'facebook', 'twitter', 'instagram', 'svg', 'button', 'bg', 'footer']
                        if any(junk in img_url.lower() for junk in junk_keywords): continue
                            
                        img_url = urljoin(target_url_all, img_url)
                        try:
                            img_resp = requests.get(img_url, headers=headers, timeout=5)
                            image = Image.open(io.BytesIO(img_resp.content))
                            w, h = image.size
                            if w >= min_w and h >= min_h:
                                if image.mode in ("RGBA", "P"): image = image.convert("RGB")
                                img_bytes = io.BytesIO()
                                image.save(img_bytes, format='JPEG', quality=90)
                                file_name = f"images/extracted_{w}x{h}_{len(extracted_images)}.jpg"
                                extracted_images.append((file_name, img_bytes.getvalue()))
                        except:
                            pass
                            
                    # 3. Build the Master ZIP
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        # Write the Word Doc
                        zip_file.writestr(f"{safe_title}.docx", doc_io.getvalue())
                        # Write the Images into an 'images' folder
                        for file_name, img_bytes in extracted_images:
                            zip_file.writestr(file_name, img_bytes)
                            
                    st.success(f"✅ Extracted '{title}' and {len(extracted_images)} images.")
                    st.session_state.total_converted += 1
                    extracted_images = extract_images(target_url_all, min_w, min_h)
                            
                    # 3. Build the Master ZIP
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        # Write the Word Doc
                        zip_file.writestr(f"{safe_title}.docx", doc_io.getvalue())
                        # Write the Images into an 'images' folder
                        for file_name, img_bytes in extracted_images:
                            zip_file.writestr(f"images/{file_name}"