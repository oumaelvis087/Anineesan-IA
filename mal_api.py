import requests
from typing import Dict, List, Optional
import os
from urllib.parse import urlencode

class MALClient:
    """MyAnimeList API v2 Client"""
    
    def __init__(self, client_id: str = None):
        """Initialize the MAL API client
        
        Args:
            client_id: Your MAL API client ID. If not provided, will look for MAL_CLIENT_ID env variable
        """
        self.client_id = client_id or os.getenv('MAL_CLIENT_ID')
        if not self.client_id:
            raise ValueError("MAL Client ID is required. Set it in constructor or MAL_CLIENT_ID environment variable")
            
        self.base_url = "https://api.myanimelist.net/v2"
        self.headers = {
            'X-MAL-CLIENT-ID': self.client_id
        }
    
    def get_anime_details(self, anime_id: int, fields: Optional[List[str]] = None) -> Dict:
        """Get detailed information about a specific anime
        
        Args:
            anime_id: The ID of the anime
            fields: List of fields to return. If None, returns all fields
            
        Returns:
            Dict containing anime details
        """
        if fields is None:
            fields = [
                'id', 'title', 'main_picture', 'alternative_titles', 'start_date',
                'end_date', 'synopsis', 'mean', 'rank', 'popularity', 'num_list_users',
                'num_scoring_users', 'nsfw', 'created_at', 'updated_at', 'media_type',
                'status', 'genres', 'num_episodes', 'start_season', 'broadcast',
                'source', 'average_episode_duration', 'rating', 'pictures',
                'background', 'related_anime', 'related_manga', 'recommendations',
                'studios', 'statistics'
            ]
            
        params = {
            'fields': ','.join(fields)
        }
        
        url = f"{self.base_url}/anime/{anime_id}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def search_anime(self, query: str, limit: int = 10, offset: int = 0, fields: Optional[List[str]] = None) -> Dict:
        """Search for anime by keyword
        
        Args:
            query: Search keyword
            limit: Number of results to return (max 100)
            offset: Number of results to skip for pagination
            fields: List of fields to return. If None, returns default fields
            
        Returns:
            Dict containing search results
        """
        if fields is None:
            fields = ['id', 'title', 'main_picture', 'synopsis', 'mean', 'genres', 'media_type', 'status']
            
        params = {
            'q': query,
            'limit': min(limit, 100),
            'offset': offset,
            'fields': ','.join(fields)
        }
        
        url = f"{self.base_url}/anime"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_seasonal_anime(self, year: Optional[int] = None, season: Optional[str] = None, 
                         sort: str = 'anime_score', limit: int = 10, 
                         offset: int = 0, fields: Optional[List[str]] = None) -> Dict:
        """Get seasonal anime
        
        Args:
            year: The year (optional, defaults to current year)
            season: One of 'winter', 'spring', 'summer', 'fall' (optional, defaults to current season)
            sort: Sort criteria ('anime_score' or 'anime_num_list_users')
            limit: Number of results to return (max 100)
            offset: Number of results to skip for pagination
            fields: List of fields to return. If None, returns default fields
            
        Returns:
            Dict containing seasonal anime
        """
        if fields is None:
            fields = ['id', 'title', 'main_picture', 'synopsis', 'mean', 'genres', 'media_type']
            
        # If no season specified, use current season
        if not season or not year:
            from datetime import datetime
            now = datetime.now()
            
            if not year:
                year = now.year
                
            if not season:
                # Determine season based on month
                month = now.month
                if month in [12, 1, 2]:
                    season = 'winter'
                elif month in [3, 4, 5]:
                    season = 'spring'
                elif month in [6, 7, 8]:
                    season = 'summer'
                else:
                    season = 'fall'
        
        if season.lower() not in ['winter', 'spring', 'summer', 'fall']:
            raise ValueError("Season must be one of: winter, spring, summer, fall")
            
        params = {
            'sort': sort,
            'limit': min(limit, 100),
            'offset': offset,
            'fields': ','.join(fields)
        }
        
        url = f"{self.base_url}/anime/season/{year}/{season.lower()}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_anime_ranking(self, ranking_type: str = 'all', 
                         limit: int = 10, offset: int = 0, 
                         fields: Optional[List[str]] = None) -> Dict:
        """Get anime ranking
        
        Args:
            ranking_type: One of 'all', 'airing', 'upcoming', 'tv', 'ova', 
                        'movie', 'special', 'bypopularity', 'favorite'
            limit: Number of results to return (max 100)
            offset: Number of results to skip for pagination
            fields: List of fields to return. If None, returns default fields
            
        Returns:
            Dict containing anime ranking
        """
        valid_types = ['all', 'airing', 'upcoming', 'tv', 'ova', 
                      'movie', 'special', 'bypopularity', 'favorite']
        if ranking_type.lower() not in valid_types:
            raise ValueError(f"Ranking type must be one of: {', '.join(valid_types)}")
            
        if fields is None:
            fields = ['id', 'title', 'main_picture', 'mean', 'rank', 'popularity']
            
        params = {
            'ranking_type': ranking_type.lower(),
            'limit': min(limit, 100),
            'offset': offset,
            'fields': ','.join(fields)
        }
        
        url = f"{self.base_url}/anime/ranking"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
