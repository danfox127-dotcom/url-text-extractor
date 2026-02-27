import streamlit as st
import requests
from bs4 import BeautifulSoup, NavigableString
from docx import Document
from io import BytesIO
import zipfile

# --- CORE LOGIC: SMART FORMATTING ---

def extract_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Grab Title
        page_title = soup.find('h1')
        title_text = page_title.get_text().strip() if page_title else "Extracted Content"
        
        # Clean the soup
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.decompose()
            
        # Target the main content area (usually <main> or <div> with specific classes)
        # If no main tag, we use the body
        content_area = soup.find('main') or soup.body
        
        # We will return a list of "formatted chunks"
        formatted_data = []
        
        # Tags we want to process
        tags_to_save = ['p', 'h2', 'h3', 'h4', 'li']
        
        for element in content_area.find_all(tags_to_save):
            chunk = {
                'tag': element.name,
                'content': []
            }
            # Look inside the tag for bold/strong styling
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
        tag = chunk['tag']
        
        # Create a paragraph based on tag type
        if tag == 'li':
            p = doc.add_paragraph(style='List Bullet')
        elif tag in ['h2', 'h3', 'h4']:
            p = doc.add_paragraph()
            # We'll make headers bold manually for simplicity
        else:
            p = doc.add_paragraph()

        # Add the text runs with styling
        for style_type, text in chunk['content']:
            run = p.add_run(text)
            if style_type == 'bold' or tag in ['h2', 'h3', 'h4']:
                run.bold = True
                
    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# --- THE REST OF YOUR UI CODE REMAINS THE SAME ---
