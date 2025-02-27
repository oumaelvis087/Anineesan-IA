import requests
from bs4 import BeautifulSoup
import logging
import time
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MiruroScraper:
    BASE_URL = "https://www.miruro.tv"
    API_URL = "https://api.miruro.tv"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Origin': self.BASE_URL,
            'Referer': self.BASE_URL
        })

    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        """Make a request to the given URL and return BeautifulSoup object."""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    def get_latest_anime(self, page: int = 1) -> List[Dict]:
        """Fetch latest anime from the API."""
        animes = []
        try:
            # Try different API endpoints
            endpoints = [
                f"{self.API_URL}/v1/anime/latest?page={page}",
                f"{self.API_URL}/anime/latest?page={page}",
                f"{self.API_URL}/anime/popular?page={page}"
            ]
            
            for endpoint in endpoints:
                try:
                    response = self.session.get(endpoint)
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, dict) and 'data' in data:
                            animes.extend(data['data'])
                        elif isinstance(data, list):
                            animes.extend(data)
                        break
                except Exception as e:
                    logger.debug(f"Failed to fetch from {endpoint}: {str(e)}")
                    continue

            # Format the anime data
            formatted_animes = []
            for anime in animes:
                formatted_anime = {
                    'title': anime.get('title', ''),
                    'url': f"{self.BASE_URL}/anime/{anime.get('id', '')}",
                    'image': anime.get('cover_image', '') or anime.get('image', ''),
                    'description': anime.get('description', '') or anime.get('synopsis', ''),
                    'rating': anime.get('rating', ''),
                    'episodes': anime.get('episodes', []),
                    'genres': anime.get('genres', []),
                    'status': anime.get('status', ''),
                    'type': anime.get('type', ''),
                    'year': anime.get('year', '')
                }
                formatted_animes.append(formatted_anime)

            return formatted_animes

        except Exception as e:
            logger.error(f"Error scraping latest anime: {str(e)}")
            return animes

    def get_anime_details(self, anime_url: str) -> Dict:
        """Fetch detailed information about a specific anime."""
        try:
            soup = self._make_request(anime_url)
            if not soup:
                return {}

            # Extract detailed anime information
            # Note: The actual implementation will need to be adjusted based on the website's HTML structure
            details = {
                'title': '',
                'synopsis': '',
                'genres': [],
                'episodes': [],
                'status': '',
                'rating': '',
            }

            # Implementation details will be added based on actual HTML structure
            return details

        except Exception as e:
            logger.error(f"Error scraping anime details: {str(e)}")
            return {}

    def search_anime(self, query: str) -> List[Dict]:
        """Search for anime using the API."""
        try:
            # Try different API endpoints
            endpoints = [
                f"{self.API_URL}/v1/anime/search?q={query}",
                f"{self.API_URL}/anime/search?q={query}"
            ]
            
            for endpoint in endpoints:
                try:
                    response = self.session.get(endpoint)
                    if response.status_code == 200:
                        data = response.json()
                        results = []
                        if isinstance(data, dict) and 'data' in data:
                            results = data['data']
                        elif isinstance(data, list):
                            results = data
                            
                        # Format the results
                        formatted_results = []
                        for anime in results:
                            formatted_anime = {
                                'title': anime.get('title', ''),
                                'url': f"{self.BASE_URL}/anime/{anime.get('id', '')}",
                                'image': anime.get('cover_image', '') or anime.get('image', ''),
                                'description': anime.get('description', '') or anime.get('synopsis', ''),
                                'rating': anime.get('rating', ''),
                                'episodes': anime.get('episodes', []),
                                'genres': anime.get('genres', []),
                                'status': anime.get('status', ''),
                                'type': anime.get('type', ''),
                                'year': anime.get('year', '')
                            }
                            formatted_results.append(formatted_anime)
                        return formatted_results
                except Exception as e:
                    logger.debug(f"Failed to search from {endpoint}: {str(e)}")
                    continue
            
            return []

        except Exception as e:
            logger.error(f"Error searching anime: {str(e)}")
            return []

# Example usage
if __name__ == "__main__":
    scraper = MiruroScraper()
    latest_anime = scraper.get_latest_anime()
    print(f"Found {len(latest_anime)} anime titles")
