import requests
from bs4 import BeautifulSoup
import os
import re
from urllib.parse import urlparse
import time
import glob

def scrape_article(url, output_file=None):
    """
    Scrapes the given URL for title, subtitle, publication date and article content
    and saves the text to a markdown file.
    
    Args:
        url (str): The URL to scrape
        output_file (str, optional): Path to save the output. If None, generates a filename based on the URL.
    
    Returns:
        str: Path to the saved file
    """
    # Make the request
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None
    
    # Parse the HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract title and subtitle
    title_div = soup.find('div', class_="details-title")
    title = subtitle = ""
    if title_div:
        title_element = title_div.find('h1')
        if title_element:
            title = title_element.get_text().strip()
        
        # Subtitle is the p tag that's not the shoulder-text
        subtitle_element = title_div.find('p', class_=lambda x: x != "shoulder-text")
        if subtitle_element:
            subtitle = subtitle_element.get_text().strip()
    
    # Extract publication date
    pub_date = ""
    pub_div = soup.find('div', class_="pub-up")
    if pub_div:
        date_span = pub_div.find('span', string=lambda t: t and 'Published' not in t)
        if date_span:
            pub_date = date_span.get_text().strip()
    
    # Find the div with id="contentDetails"
    content_div = soup.find(id="contentDetails")
    if not content_div:
        print(f"No div with id='contentDetails' found at {url}")
        return None
    
    # Find all <p> tags within the div
    paragraphs = content_div.find_all('p')
    if not paragraphs:
        print(f"No <p> tags found within div#contentDetails at {url}")
        return None
    
    # Extract and combine text from all paragraphs
    article_paragraphs = [p.get_text().strip() for p in paragraphs]
    
    # Determine output filename if not provided
    if not output_file:
        parsed_url = urlparse(url)
        basename = os.path.basename(parsed_url.path)
        if not basename:
            basename = parsed_url.netloc.replace('.', '_')
        filename = f"{basename}.md"
        output_file = filename
    
    # Create markdown content
    markdown_content = f"# {title}\n\n"
    if subtitle:
        markdown_content += f"*{subtitle}*\n\n"
    if pub_date:
        markdown_content += f"**Published: {pub_date}**\n\n"
    markdown_content += f"**Source:** [{url}]({url})\n\n"
    markdown_content += "---\n\n"
    
    # Add article paragraphs
    for paragraph in article_paragraphs:
        if paragraph.strip():
            markdown_content += f"{paragraph}\n\n"
    
    
    return markdown_content
    # # Save to file
    # try:
    #     with open(output_file, 'w', encoding='utf-8') as f:
    #         f.write(markdown_content)
    #     print(f"Article saved to {output_file}")
    #     return output_file
    # except IOError as e:
    #     print(f"Error saving to file {output_file}: {e}")
    #     return None

def extract_url_components(url):
    """
    Extracts category and ID from a bdnews24 URL.
    
    Args:
        url (str): The URL to parse
    
    Returns:
        tuple: (category, id)
    """
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    
    if len(path_parts) >= 2:
        category = path_parts[0]
        article_id = path_parts[1]
        return category, article_id
    
    return None, None

def process_archive_files(archive_dir="bdnews_archive", output_base_dir="."):
    """
    Processes all archive files in the given directory, scraping articles and saving them.
    
    Args:
        archive_dir (str): Directory containing archive files
        output_base_dir (str): Base directory for output files
    """
    # Get list of all archive files
    archive_path = os.path.join(output_base_dir, archive_dir)
    archive_files = glob.glob(os.path.join(archive_path, "bdnews24_archive_*.txt"))
    
    if not archive_files:
        print(f"No archive files found in {archive_path}")
        return
    
    print(f"Found {len(archive_files)} archive files to process")
    
    # Process each archive file
    for archive_file in sorted(archive_files):
        # Extract date from filename
        date_match = re.search(r'bdnews24_archive_(\d{4}-\d{2}-\d{2})\.txt', os.path.basename(archive_file))
        if not date_match:
            print(f"Could not extract date from filename: {archive_file}, skipping")
            continue
        
        date = date_match.group(1)
        print(f"\nProcessing archive for date: {date}")
        
        # Create output directory for this date
        output_dir = os.path.join(output_base_dir, date)
        os.makedirs(output_dir, exist_ok=True)
        
        # Read and process each URL in the file
        try:
            with open(archive_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]
            
            print(f"Found {len(urls)} URLs to process in {archive_file}")
            
            for i, url in enumerate(urls):
                print(f"Processing URL {i+1}/{len(urls)}: {url}")
                
                # Extract category and ID from URL
                category, article_id = extract_url_components(url)
                
                if not category or not article_id:
                    print(f"Could not extract category and ID from URL: {url}, skipping")
                    continue
                
                # Create output filename
                output_file = os.path.join(output_dir, f"{category}.{date}.{article_id}.md")
                
                # Check if file already exists
                if os.path.exists(output_file):
                    print(f"File already exists: {output_file}, skipping")
                    continue
                
                # Scrape article
                result = scrape_article(url, output_file)
                
                # Add a small delay to avoid hammering the server
                time.sleep(1)
        
        except Exception as e:
            print(f"Error processing file {archive_file}: {e}")

def main():
    print("BDNews24 Article Scraper")
    print("1. Scrape a single article")
    print("2. Process archive files")
    choice = input("Enter your choice (1/2): ")
    
    if choice == '1':
        url = input("Enter the URL to scrape: ")
        output_file = input("Enter output filename (leave blank for automatic naming): ")
        
        if not output_file:
            output_file = None
            
        result = scrape_article(url, output_file)
        if result:
            print(f"Successfully scraped content from {url}")
    
    elif choice == '2':
        archive_dir = input("Enter archive directory (default: bdnews_archive): ") or "bdnews_archive"
        output_base_dir = input("Enter base output directory (default: current directory): ") or "."
        
        process_archive_files(archive_dir, output_base_dir)
        print("Archive processing complete")
    
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()