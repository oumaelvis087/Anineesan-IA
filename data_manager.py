from datetime import datetime
import json
import os
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from scrapers import MiruroScraper

class DataManager:
    def __init__(self):
        self.base_url = "https://zoro.bid"  # Using zoro.bid as the source
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.data_dir = "data"
        self.seasonal_file = os.path.join(self.data_dir, "seasonal.json")
        self.top_anime_file = os.path.join(self.data_dir, "top_anime.json")
        self.miruro_file = os.path.join(self.data_dir, "miruro_anime.json")
        
        # Initialize scrapers
        self.miruro_scraper = MiruroScraper()
        
        # Create data directory if it doesn't exist
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
    def fetch_miruro_anime(self, pages=5):
        """Fetch anime data from Miruro and save it to file."""
        all_anime = []
        for page in range(1, pages + 1):
            anime_list = self.miruro_scraper.get_latest_anime(page)
            if not anime_list:
                break
            all_anime.extend(anime_list)
            
        # Save to file
        with open(self.miruro_file, 'w', encoding='utf-8') as f:
            json.dump(all_anime, f, indent=4, ensure_ascii=False)
            
        return all_anime
    
    def get_miruro_anime(self):
        """Get anime data from Miruro cache file."""
        if not os.path.exists(self.miruro_file):
            return self.fetch_miruro_anime()
            
        with open(self.miruro_file, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    def search_miruro_anime(self, query):
        """Search for anime in Miruro."""
        return self.miruro_scraper.search_anime(query)
            
        # Initialize cache
        self.seasonal_anime = self.load_json_file(self.seasonal_file)
        self.top_anime = self.load_json_file(self.top_anime_file)

    def load_json_file(self, file_path):
        """Load data from a JSON file"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
        return {}

    def save_json_file(self, file_path, data):
        """Save data to a JSON file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving {file_path}: {e}")

    def _make_request(self, url, params=None):
        """Make a request with error handling and retries"""
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text[:500]}")  # Print first 500 chars
            return response
        except requests.RequestException as e:
            print(f"Error making request to {url}: {e}")
            return None

    def _parse_anime_card(self, card):
        """Parse an anime card element to extract info"""
        try:
            # Extract title and ID
            title_elem = card.find('h3', class_='title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            link = card.find('a', class_='link')
            anime_id = link['href'].split('/')[-1] if link and 'href' in link.attrs else ""
            
            # Extract image
            img = card.find('img', class_='poster')
            image_url = img['src'] if img and 'src' in img.attrs else ""
            if image_url and not image_url.startswith('http'):
                image_url = urljoin(self.base_url, image_url)
            
            # Extract description
            description = ""
            desc_elem = card.find('p', class_='synopsis')
            if desc_elem:
                description = desc_elem.get_text(strip=True)
            
            # Extract score
            score = None
            score_elem = card.find('span', class_='rating')
            if score_elem:
                score_text = score_elem.get_text(strip=True)
                score_match = re.search(r'\d+\.?\d*', score_text)
                if score_match:
                    score = float(score_match.group())
            
            return {
                'title': title,
                'id': anime_id,
                'image_url': image_url,
                'description': description,
                'score': score
            }
        except Exception as e:
            print(f"Error parsing anime card: {e}")
            return None

    def update_seasonal_anime(self):
        """Update seasonal anime data"""
        try:
            url = f"{self.base_url}/seasonal"
            response = self._make_request(url)
            if not response:
                return {'data': []}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            anime_cards = soup.find_all('div', class_=['anime-card', 'seasonal-anime'])
            
            seasonal_data = []
            for card in anime_cards:
                anime_info = self._parse_anime_card(card)
                if anime_info:
                    seasonal_data.append(anime_info)
            
            data = {
                'last_updated': datetime.now().isoformat(),
                'data': seasonal_data
            }
            
            self.seasonal_anime = data
            self.save_json_file(self.seasonal_file, data)
            return data
            
        except Exception as e:
            print(f"Error updating seasonal anime: {e}")
            return {'data': []}

    def update_top_anime(self):
        """Update top anime data"""
        try:
            url = f"{self.base_url}/popular"
            response = self._make_request(url)
            if not response:
                return {'data': []}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            anime_cards = soup.find_all('div', class_=['anime-card', 'popular-anime'])
            
            top_data = []
            for card in anime_cards:
                anime_info = self._parse_anime_card(card)
                if anime_info:
                    top_data.append(anime_info)
            
            data = {
                'last_updated': datetime.now().isoformat(),
                'data': top_data
            }
            
            self.top_anime = data
            self.save_json_file(self.top_anime_file, data)
            return data
            
        except Exception as e:
            print(f"Error updating top anime: {e}")
            return {'data': []}

    def _make_graphql_request(self, query, variables=None):
        """Make a GraphQL request"""
        try:
            url = f"{self.base_url}/graphql"
            payload = {
                'query': query,
                'variables': variables or {}
            }
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error making GraphQL request: {e}")
            return None

    def _get_sitemap_urls(self):
        """Get list of URLs from sitemap"""
        try:
            url = f"{self.base_url}/sitemap.xml"
            response = self._make_request(url)
            if not response:
                return []
            
            soup = BeautifulSoup(response.text, 'xml')
            urls = []
            for url in soup.find_all('url'):
                loc = url.find('loc')
                if loc:
                    urls.append(loc.text)
            return urls
        except Exception as e:
            print(f"Error getting sitemap: {e}")
            return []

    def search_anime(self, query):
        """Search for anime"""
        try:
            url = f"{self.base_url}/search.html"
            params = {'keyword': query}
            response = self._make_request(url, params)
            if not response:
                return {'data': []}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            anime_items = soup.find_all('div', class_='last_episodes')
            
            search_data = []
            for item in anime_items:
                anime_info = self._parse_search_item(item)
                if anime_info:
                    search_data.append(anime_info)
            
            return {'data': search_data}
            
        except Exception as e:
            print(f"Error searching anime: {e}")
            return {'data': []}

    def _parse_search_item(self, item):
        """Parse a search result item"""
        try:
            # Get title and ID
            title_elem = item.find('p', class_='name')
            if not title_elem:
                return None
            
            link = title_elem.find('a')
            if not link:
                return None
            
            title = link.get_text(strip=True)
            anime_id = link['href'].split('/')[-1]
            
            # Get image
            img = item.find('div', class_='img').find('img')
            image_url = img['src'] if img and 'src' in img.attrs else ""
            if image_url and not image_url.startswith('http'):
                image_url = urljoin(self.base_url, image_url)
            
            # Get released info
            released = ""
            released_elem = item.find('p', class_='released')
            if released_elem:
                released = released_elem.get_text(strip=True)
            
            return {
                'title': title,
                'id': anime_id,
                'image_url': image_url,
                'description': released,
                'score': None
            }
        except Exception as e:
            print(f"Error parsing search item: {e}")
            return None

    def get_anime_details(self, anime_id):
        """Get detailed information about an anime"""
        try:
            url = f"{self.base_url}/category/{anime_id}"
            response = self._make_request(url)
            if not response:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Get title
            title = ""
            title_elem = soup.find('div', class_='anime_info_body_bg').find('h1')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # Get description
            description = ""
            desc_elem = soup.find('p', class_='type')
            if desc_elem and desc_elem.find('span', text='Plot Summary:'):
                description = desc_elem.get_text(strip=True).replace('Plot Summary:', '').strip()
            
            # Get image
            image_url = ""
            img = soup.find('div', class_='anime_info_body_bg').find('img')
            if img:
                image_url = img['src']
                if not image_url.startswith('http'):
                    image_url = urljoin(self.base_url, image_url)
            
            # Get metadata
            metadata = {}
            info_divs = soup.find_all('p', class_='type')
            for div in info_divs:
                label = div.find('span')
                if label:
                    key = label.get_text(strip=True).lower().replace(':', '')
                    value = div.get_text(strip=True).replace(label.get_text(strip=True), '').strip()
                    metadata[key] = value
            
            # Get episodes
            episodes = []
            ep_start = soup.find('ul', id='episode_page')
            if ep_start:
                ep_end = ep_start.find_all('a')[-1]
                if ep_end and 'ep_end' in ep_end['class']:
                    total_eps = int(ep_end.get_text(strip=True))
                    for i in range(1, total_eps + 1):
                        episodes.append({
                            'number': str(i),
                            'title': f'Episode {i}',
                            'id': f'{anime_id}-episode-{i}'
                        })
            
            return {
                'title': title,
                'description': description,
                'image_url': image_url,
                'metadata': metadata,
                'episodes': episodes
            }
            
        except Exception as e:
            print(f"Error getting anime details: {e}")
            return None

    def get_episode_sources(self, anime_id, episode_number):
        """Get episode streaming sources"""
        try:
            url = f"{self.base_url}/{anime_id}-episode-{episode_number}"
            response = self._make_request(url)
            if not response:
                return {'sources': []}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            sources = []
            
            # Get the download links as sources
            download_div = soup.find('div', class_='download-anime')
            if download_div:
                links = download_div.find_all('a')
                for link in links:
                    quality = link.get_text(strip=True)
                    url = link['href']
                    sources.append({
                        'name': f'Download ({quality})',
                        'id': url,
                        'url': url
                    })
            
            # Get the streaming iframe as a source
            iframe = soup.find('iframe', class_='embed-responsive-item')
            if iframe and 'src' in iframe.attrs:
                src = iframe['src']
                if not src.startswith('http'):
                    src = urljoin(self.base_url, src)
                sources.append({
                    'name': 'Stream',
                    'id': src,
                    'url': src
                })
            
            return {'sources': sources}
            
        except Exception as e:
            print(f"Error getting episode sources: {e}")
            return {'sources': []}
