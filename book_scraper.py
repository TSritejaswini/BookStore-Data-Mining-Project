import requests
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import time
import re
from tqdm import tqdm
import os

class BookScraper:
    def __init__(self):
        self.base_url = "http://books.toscrape.com/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.books_data = []
        self.session = requests.Session()
        
    def get_soup(self, url):
        """Make an HTTP request and return the BeautifulSoup object"""
        response = self.session.get(url, headers=self.headers)
        if response.status_code == 200:
            return BeautifulSoup(response.content, 'html.parser')
        else:
            print(f"Failed to fetch page: {url}, Status code: {response.status_code}")
            return None
    
    def extract_book_data(self, book_url):
        """Extract detailed data for a single book"""
        soup = self.get_soup(book_url)
        if not soup:
            return None
        
        # Extract book details
        title = soup.find('div', class_='product_main').h1.text.strip()
        price = soup.find('p', class_='price_color').text.strip()
        price = float(re.sub(r'[^0-9\.]', '', price))
        
        availability = soup.find('p', class_='availability').text.strip()
        in_stock = "In stock" in availability
        stock_text = soup.find('p', class_='instock availability').text.strip()
        stock_count = int(re.search(r'(\d+) available', stock_text).group(1)) if re.search(r'(\d+) available', stock_text) else 0
        
        # Extract rating
        rating_class = soup.find('p', class_='star-rating')['class'][1].lower()
        rating_map = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
        rating = rating_map.get(rating_class, 0)
        
        # Extract product description if available
        product_description = soup.select_one('#product_description ~ p')
        description = product_description.text.strip() if product_description else "No description available"
        
        # Extract category
        category = soup.select('ul.breadcrumb li')[2].text.strip()
        
        # Extract UPC
        upc = soup.find('th', text='UPC').find_next('td').text.strip()
        
        return {
            'title': title,
            'price': price,
            'rating': rating,
            'availability': in_stock,
            'stock_count': stock_count,
            'description': description,
            'category': category,
            'upc': upc,
            'url': book_url
        }
    
    def scrape_category(self, category_url, limit=None):
        """Scrape books from a specific category"""
        books_in_category = []
        page_num = 1
        books_count = 0
        
        while True:
            if page_num == 1:
                url = category_url
            else:
                url = category_url.replace('index.html', f'page-{page_num}.html')
            
            soup = self.get_soup(url)
            if not soup:
                break
                
            books = soup.select('article.product_pod')
            if not books:
                break
                
            for book in books:
                if limit and books_count >= limit:
                    break
                    
                from urllib.parse import urljoin

                book_url = book.h3.a['href']
                book_url = urljoin(url, book_url)  


                    
                book_data = self.extract_book_data(book_url)
                if book_data:
                    books_in_category.append(book_data)
                    books_count += 1
                    
                # Be nice to the server with a small delay
                time.sleep(0.5)
                
            if limit and books_count >= limit:
                break
                
            # Check if there's a next page
            next_button = soup.select_one('li.next a')
            if not next_button:
                break
                
            page_num += 1
            
        return books_in_category
    
    def scrape_all_categories(self, books_per_category=10):
        """Scrape books from all categories"""
        soup = self.get_soup(self.base_url)
        if not soup:
            return
            
        # Extract all category links
        category_links = []
        categories = soup.select('div.side_categories ul.nav-list li ul li a')
        
        for category in categories:
            category_url = category['href']
            if not category_url.startswith('http'):
                category_url = self.base_url + category_url
            category_links.append(category_url)
            
        print(f"Found {len(category_links)} categories")
        
        # Scrape books from each category with a progress bar
        for category_url in tqdm(category_links, desc="Scraping categories"):
            category_books = self.scrape_category(category_url, limit=books_per_category)
            self.books_data.extend(category_books)
            
        print(f"Total books scraped: {len(self.books_data)}")
        
    def save_to_csv(self, filename='books_data.csv'):
        """Save scraped data to CSV file"""
        if not self.books_data:
            print("No data to save")
            return
            
        df = pd.DataFrame(self.books_data)
        df.to_csv(filename, index=False)
        print(f"Data saved to {filename}")
        return df
        
    def analyze_data(self, df=None):
        """Analyze the scraped data and create visualizations"""
        if df is None:
            if not self.books_data:
                print("No data to analyze")
                return
            df = pd.DataFrame(self.books_data)
            
        print("\n--- Data Analysis ---")
        
        # Create output directory for visualizations
        os.makedirs('visualizations', exist_ok=True)
        
        # 1. Price Distribution
        plt.figure(figsize=(10, 6))
        sns.histplot(df['price'], bins=20, kde=True)
        plt.title('Price Distribution of Books')
        plt.xlabel('Price (£)')
        plt.ylabel('Count')
        plt.savefig('visualizations/price_distribution.png')
        
        # 2. Rating Distribution
        plt.figure(figsize=(10, 6))
        rating_counts = df['rating'].value_counts().sort_index()
        sns.barplot(x=rating_counts.index, y=rating_counts.values)
        plt.title('Rating Distribution')
        plt.xlabel('Rating (1-5 Stars)')
        plt.ylabel('Count')
        plt.xticks(range(5), ['1 ★', '2 ★', '3 ★', '4 ★', '5 ★'])
        plt.savefig('visualizations/rating_distribution.png')
        
        # 3. Top Categories by Average Rating
        category_ratings = df.groupby('category')['rating'].mean().sort_values(ascending=False).head(10)
        plt.figure(figsize=(12, 6))
        sns.barplot(x=category_ratings.values, y=category_ratings.index)
        plt.title('Top 10 Categories by Average Rating')
        plt.xlabel('Average Rating')
        plt.tight_layout()
        plt.savefig('visualizations/top_categories_by_rating.png')
        
        # 4. Price vs Rating Scatter Plot
        plt.figure(figsize=(10, 6))
        sns.scatterplot(data=df, x='price', y='rating', alpha=0.6)
        plt.title('Price vs Rating')
        plt.xlabel('Price (£)')
        plt.ylabel('Rating')
        plt.savefig('visualizations/price_vs_rating.png')
        
        # 5. Stock Count Distribution
        plt.figure(figsize=(10, 6))
        sns.histplot(df['stock_count'], bins=15)
        plt.title('Stock Count Distribution')
        plt.xlabel('Number of Books in Stock')
        plt.ylabel('Count')
        plt.savefig('visualizations/stock_distribution.png')
        
        # 6. Sentiment Analysis Visualization (Simple version based on ratings)
        df['sentiment'] = pd.cut(
            df['rating'], 
            bins=[0, 2, 3, 5], 
            labels=['Negative', 'Neutral', 'Positive']
        )
        
        sentiment_counts = df['sentiment'].value_counts()
        plt.figure(figsize=(10, 6))
        sns.barplot(x=sentiment_counts.index, y=sentiment_counts.values, palette=['red', 'gray', 'green'])
        plt.title('Sentiment Distribution Based on Ratings')
        plt.xlabel('Sentiment')
        plt.ylabel('Count')
        plt.savefig('visualizations/sentiment_distribution.png')
        
        print("Visualizations saved to 'visualizations' directory")
        
        # Generate summary statistics
        summary = {
            'total_books': len(df),
            'avg_price': df['price'].mean(),
            'avg_rating': df['rating'].mean(),
            'categories_count': df['category'].nunique(),
            'sentiment_breakdown': sentiment_counts.to_dict()
        }
        
        return summary

# Main execution
if __name__ == "__main__":
    print("Starting Book Scraper for Books.toscrape.com")
    
    scraper = BookScraper()
    
    # Option to scrape all categories or limit to a few for testing
    all_categories = input("Scrape all categories? (y/n): ").lower() == 'y'
    
    if all_categories:
        books_per_category = int(input("How many books per category to scrape? (recommended: 5-10): "))
        scraper.scrape_all_categories(books_per_category=books_per_category)
    else:
        # Scrape just the first page of books for a quick test
        print("Scraping just the main page for testing...")
        test_books = scraper.scrape_category(scraper.base_url, limit=20)
        scraper.books_data.extend(test_books)
    
    # Save data to CSV
    df = scraper.save_to_csv()
    
    # Analyze and visualize the data
    summary = scraper.analyze_data(df)
    
    print("\n--- Summary Statistics ---")
    for key, value in summary.items():
        print(f"{key}: {value}")
    
    print("\nWeb scraping project completed successfully!")