import streamlit as st
import requests
from bs4 import BeautifulSoup

def extract_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove navigation, scripts, and footers to keep only "body" content
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
            
        text = soup.get_text(separator='\n')
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        clean_text = '\n'.join(line for line in lines if line)
        return clean_text
    except Exception as e:
        return f"Error: {e}"

# --- Streamlit UI ---
st.set_page_config(page_title="Web Content Puller", page_icon="📄")
st.title("📄 Web Content Puller")
st.write("Enter a URL to grab the clean body text for your documents.")

url_input = st.text_input("Paste URL here:", placeholder="https://example.com")

if st.button("Extract Content"):
    if url_input:
        with st.spinner("Scraping..."):
            result = extract_content(url_input)
            st.text_area("Extracted Text (Copy from here):", result, height=400)
    else:
        st.warning("Please enter a valid URL.")
