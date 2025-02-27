import requests
from bs4 import BeautifulSoup
import time
from typing import List, Dict

class MALScraper:
    def __init__(self):
        self.base_url = "https://myanimelist.net/recommendations.php"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_recent_recommendations(self) -> List[Dict]:
        """
        Scrape recent anime recommendations from MyAnimeList
        Returns a list of dictionaries containing recommendation pairs
        """
        params = {
            's': 'recentrecs',
            't': 'anime'
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            recommendations = []
            rec_units = soup.find_all('div', class_='spaceit')
            
            for unit in rec_units:
                try:
                    # Find anime titles
                    anime_links = unit.find_all('a', class_='hoverinfo_trigger')
                    if len(anime_links) < 2:
                        continue
                        
                    # Get anime IDs from URLs
                    anime1_id = int(anime_links[0]['href'].split('/')[4])
                    anime2_id = int(anime_links[1]['href'].split('/')[4])
                    
                    # Get anime titles
                    anime1_title = anime_links[0].text.strip()
                    anime2_title = anime_links[1].text.strip()
                    
                    # Get recommendation text if available
                    rec_text = ""
                    text_div = unit.find('div', class_='recommendations-user-recs-text')
                    if text_div:
                        rec_text = text_div.text.strip()
                    
                    recommendations.append({
                        'source_anime': {
                            'id': anime1_id,
                            'title': anime1_title
                        },
                        'recommended_anime': {
                            'id': anime2_id,
                            'title': anime2_title
                        },
                        'recommendation_text': rec_text
                    })
                    
                except (AttributeError, IndexError, ValueError) as e:
                    print(f"Error processing recommendation unit: {e}")
                    continue
                    
            return recommendations
            
        except requests.RequestException as e:
            print(f"Error fetching recommendations: {e}")
            return []

    def get_anime_details(self, anime_id: int) -> Dict:
        """
        Get additional details for a specific anime
        """
        url = f"https://myanimelist.net/anime/{anime_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Basic details
            details = {
                'id': anime_id,
                'image_url': soup.find('img', {'itemprop': 'image'})['data-src'] if soup.find('img', {'itemprop': 'image'}) else None,
                'rating': float(soup.find('span', {'itemprop': 'ratingValue'}).text) if soup.find('span', {'itemprop': 'ratingValue'}) else None,
                'genres': [genre.text for genre in soup.find_all('span', {'itemprop': 'genre'})],
            }
            
            return details
            
        except requests.RequestException as e:
            print(f"Error fetching anime details: {e}")
            return {}

if __name__ == "__main__":
    scraper = MALScraper()
    recommendations = scraper.get_recent_recommendations()
    print(f"Found {len(recommendations)} recommendations")
    for rec in recommendations[:3]:  # Print first 3 recommendations as example
        print(f"\nRecommendation:")
        print(f"If you liked: {rec['source_anime']['title']}")
        print(f"You might like: {rec['recommended_anime']['title']}")
        if rec['recommendation_text']:
            print(f"Why: {rec['recommendation_text']}")
