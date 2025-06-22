from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import os
import time
import json
import random
from datetime import datetime, timedelta

# Get current directory where the script is running
current_dir = os.path.dirname(os.path.abspath(__file__))

# Path to geckodriver in the same directory
geckodriver_path = os.path.join(current_dir, 'geckodriver')

# Define date range for extraction (YYYY-MM-DD format)
start_date = "2024-08-01"  # Start date
end_date = "2025-04-08"    # End date (inclusive)

# Maximum number of retries
MAX_RETRIES = 7

# Progress tracking file
PROGRESS_FILE = os.path.join(current_dir, 'scraping_progress.json')

def save_progress(date):
    """Save the current progress to resume later if needed"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({'last_completed_date': date}, f)
    print(f"Progress saved: completed up to {date}")

def load_progress():
    """Load the saved progress to resume scraping"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            data = json.load(f)
            return data.get('last_completed_date')
    return None

def setup_driver():
    """Setup and return a new WebDriver instance"""
    service = Service(executable_path=geckodriver_path)
    options = Options()
    # Add options for better stability
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    driver = webdriver.Firefox(service=service, options=options)
    wait = WebDriverWait(driver, 15)  # Increased timeout for network issues
    return driver, wait

def extract_subcatwrapper_urls(html_content, output_file=None):
    # Extracts urls from html
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all SubCat-wrapper divs
    wrappers = soup.find_all('div', class_='SubCat-wrapper')

    # Extract URLs from each wrapper
    urls = []
    for wrapper in wrappers:
        # Find the anchor tag inside the wrapper
        link = wrapper.find('a')
        if link and link.has_attr('href'):
            urls.append(link['href'])

    # Save the URLs to a file if specified
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(f"{url}\n")
        print(f"Extracted {len(urls)} URLs and saved to {output_file}")
        
    return urls

def extract_links_for_date(date, driver, wait, retry_count=0):
    """Extract links for a specific date range with retry logic"""
    try:
        print(f"\n===== Processing date: {date} =====")
        
        # Navigate to the archive page
        url = 'https://bangla.bdnews24.com/archive'
        print(f"Navigating to {url}...")
        driver.get(url)
        
        # Wait for date fields to be present
        wait.until(EC.presence_of_element_located((By.ID, "from_date")))
        
        # Use JavaScript to set date values directly through flatpickr's API
        js_input_script = f"""
            // Set the from date
            document.querySelector("#from_date")._flatpickr.setDate("{date}");
            
            // Set the to date
            document.querySelector("#to_date")._flatpickr.setDate("{date}");
        """
        driver.execute_script(js_input_script)
        
        # Give a moment for the flatpickr to update the UI
        time.sleep(2)  # Increased slightly for more reliability
        
        # Click the search button
        print("Clicking search button...")
        search_button = wait.until(EC.element_to_be_clickable((By.ID, "archive_search")))
        search_button.click()
        
        # Wait for search results to load
        print("Waiting for results to load...")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "SubCat-wrapper")))
        
        # Keep clicking the "Load More" button until it's not available
        print("Loading all content...")
        page_num = 1
        while True:
            try:
                # Check if the load more button exists and is not hidden
                load_more_btn = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".load-more-data:not(.d-none)"))
                )
                
                # If the button's parent div has d-none class, we're done
                parent_div = load_more_btn.find_element(By.XPATH, "./parent::div")
                if "d-none" in parent_div.get_attribute("class"):
                    print("No more content to load")
                    break
                    
                # Click the button
                print(f"Clicking 'Load More' button (page {page_num})...")
                driver.execute_script("arguments[0].click();", load_more_btn)
                page_num += 1
                
                # Wait for new content to load with a randomized delay to avoid detection
                sleep_time = 2 + random.uniform(0.5, 1.5)
                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"No more 'Load More' button found or error: {e}")
                break
        
        # Get the page source after all content is loaded
        print("All content loaded, extracting data...")
        html_content = driver.page_source
        
        # Create directory for storing archives if it doesn't exist
        archive_dir = os.path.join(current_dir, 'bdnews_archive')
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
            print(f"Created directory: {archive_dir}")
        
        # Save to the archive directory
        output_file = os.path.join(archive_dir, f'bdnews24_archive_{date}.txt')
        
        # Extract and save URLs
        urls = extract_subcatwrapper_urls(html_content, output_file)
        print(f"Extracted {len(urls)} URLs for {date}")
        
        # Save progress after successful extraction
        save_progress(date)
        
        return urls
        
    except Exception as e:
        print(f"Error processing date {date}: {e}")
        if retry_count < MAX_RETRIES:
            retry_count += 1
            wait_time = retry_count * 10  # Progressive backoff
            print(f"Retrying {date} in {wait_time} seconds... (Attempt {retry_count}/{MAX_RETRIES})")
            time.sleep(wait_time)
            
            # Check if driver is still responsive, if not create a new one
            try:
                driver.current_url  # Test if driver is responsive
            except:
                print("WebDriver not responsive, creating a new session...")
                driver.quit()
                driver, wait = setup_driver()
                
            return extract_links_for_date(date, driver, wait, retry_count)
        else:
            print(f"Failed to process date {date} after {MAX_RETRIES} attempts")
            return []

def main():
    driver = None
    try:
        # Check for saved progress
        last_completed = load_progress()
        if last_completed:
            print(f"Resuming from {last_completed}")
            current_date = datetime.strptime(last_completed, "%Y-%m-%d") + timedelta(days=1)
            if current_date > datetime.strptime(end_date, "%Y-%m-%d"):
                print("All dates already processed!")
                return
        else:
            current_date = datetime.strptime(start_date, "%Y-%m-%d")
        
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Set up Firefox WebDriver
        driver, wait = setup_driver()
        
        # Iterate through each day in the range
        while current_date <= end_date_obj:
            current_date_str = current_date.strftime("%Y-%m-%d")
            
            # Extract links for the current date
            extract_links_for_date(current_date_str, driver, wait)
            
            # Move to the next day
            current_date += timedelta(days=1)
        
        print("\nAll dates processed successfully!")
    
    except Exception as e:
        print(f"A critical error occurred: {e}")
    
    finally:
        # Close the browser
        if driver:
            try:
                driver.quit()
                print("Browser closed")
            except:
                print("Browser already closed")

if __name__ == "__main__":
    main()
