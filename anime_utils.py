import requests
from bs4 import BeautifulSoup
import json
from slugify import slugify
import aiohttp
import asyncio
import numpy as np
from jikanpy import Jikan
from data_manager import DataManager

class AnimeStreaming:
    def __init__(self):
        self.data_manager = DataManager()
        self.base_url = "https://api.consumet.org/anime/gogoanime"
        self.search_url = f"{self.base_url}/search"
        self.info_url = f"{self.base_url}/info"
        self.watch_url = f"{self.base_url}/watch"
        
    async def search_anime(self, query):
        try:
            # Use data manager for search
            results = self.data_manager.search_anime(query)
            
            # Process MAL results
            mal_processed = []
            for anime in results.get('mal_data', []):
                mal_processed.append({
                    'id': anime['mal_id'],
                    'title': anime['title'],
                    'image': anime.get('images', {}).get('jpg', {}).get('image_url', ''),
                    'synopsis': anime.get('synopsis', ''),
                    'type': anime.get('type', ''),
                    'episodes': anime.get('episodes', 0),
                    'score': anime.get('score', 0),
                    'source': 'mal'
                })
            
            # Process AniList results
            anilist_processed = []
            for anime in results.get('anilist_data', []):
                anilist_processed.append({
                    'id': anime.get('idMal'),  # Use MAL ID for consistency
                    'title': anime['title'].get('english') or anime['title'].get('romaji'),
                    'image': anime.get('coverImage', {}).get('large', ''),
                    'synopsis': anime.get('description', ''),
                    'type': anime.get('format', ''),
                    'episodes': anime.get('episodes', 0),
                    'score': anime.get('averageScore', 0) / 10,  # Convert to 10-point scale
                    'source': 'anilist'
                })
            
            # Combine and deduplicate results based on MAL ID
            seen_ids = set()
            combined_results = []
            
            for anime in mal_processed + anilist_processed:
                if anime['id'] and anime['id'] not in seen_ids:
                    seen_ids.add(anime['id'])
                    combined_results.append(anime)
            
            return combined_results[:20]  # Limit to top 20 results
            
        except Exception as e:
            print(f"Error searching anime: {e}")
            return []

    async def get_anime_info(self, anime_id):
        try:
            # Use data manager for detailed info
            info = self.data_manager.get_anime_info(anime_id)
            
            if not info:
                return None
            
            # Combine MAL and AniList data
            mal_data = info.get('mal_data', {})
            anilist_data = info.get('anilist_data', {})
            
            return {
                'id': mal_data.get('mal_id'),
                'title': mal_data.get('title'),
                'title_english': mal_data.get('title_english') or anilist_data.get('title', {}).get('english'),
                'title_japanese': mal_data.get('title_japanese') or anilist_data.get('title', {}).get('native'),
                'image': mal_data.get('images', {}).get('jpg', {}).get('large_image_url') or anilist_data.get('coverImage', {}).get('large'),
                'banner': anilist_data.get('bannerImage'),
                'synopsis': mal_data.get('synopsis') or anilist_data.get('description'),
                'type': mal_data.get('type'),
                'episodes': mal_data.get('episodes') or anilist_data.get('episodes'),
                'status': mal_data.get('status'),
                'aired': mal_data.get('aired', {}).get('string'),
                'duration': mal_data.get('duration'),
                'rating': mal_data.get('rating'),
                'score': mal_data.get('score'),
                'scored_by': mal_data.get('scored_by'),
                'rank': mal_data.get('rank'),
                'popularity': mal_data.get('popularity'),
                'genres': [genre.get('name') for genre in mal_data.get('genres', [])],
                'studios': [studio.get('name') for studio in mal_data.get('studios', [])],
                'source': mal_data.get('source'),
                'trailer_url': mal_data.get('trailer', {}).get('url') or anilist_data.get('trailerUrl'),
                'external_links': anilist_data.get('externalLinks', [])
            }
            
        except Exception as e:
            print(f"Error getting anime info: {e}")
            return None

    async def get_episode_url(self, anime_id, episode):
        try:
            # Get anime info for the title
            info = await self.get_anime_info(anime_id)
            if not info:
                return None
                
            # Try different title variations for better matching
            titles = [
                info['title'],
                info.get('title_english', ''),
                info.get('title_japanese', '')
            ]
            
            # Try each title until we find a match
            for title in titles:
                if not title:
                    continue
                    
                # Search for the anime on Gogoanime
                params = {'q': title}
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.search_url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data:
                                # Get the first matching anime
                                anime_data = data[0]
                                if anime_data:
                                    # Get the episode stream URL
                                    params = {'id': f"{anime_data['id']}-episode-{episode}", 'server': 'gogocdn'}
                                    async with session.get(self.watch_url, params=params) as stream_response:
                                        if stream_response.status == 200:
                                            stream_data = await stream_response.json()
                                            sources = stream_data.get('sources', [])
                                            if sources:
                                                # Get the highest quality source
                                                source = max(sources, key=lambda x: int(x.get('quality', '0').replace('p', '0')))
                                                return source.get('url')
            return None
            
        except Exception as e:
            print(f"Error getting episode URL: {e}")
            return None

class MLRecommender:
    def __init__(self):
        self.model = None
        self.vectorizer = None
        
    def preprocess_anime_data(self, anime_list):
        # Convert anime data into features
        features = []
        for anime in anime_list:
            feature = {
                'genres': anime.genres.split(','),
                'rating': float(anime.rating) if anime.rating else 0,
                'popularity': 0  # To be updated with actual popularity data
            }
            features.append(feature)
        return features
    
    def train_model(self, user_data, anime_data):
        """
        Train the recommendation model using user watch history and anime data
        """
        from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler
        from sklearn.compose import ColumnTransformer
        from sklearn.pipeline import Pipeline
        from sklearn.neighbors import NearestNeighbors
        
        # Prepare the data
        features = self.preprocess_anime_data(anime_data)
        
        # Create genre encoder
        mlb = MultiLabelBinarizer()
        genre_features = mlb.fit_transform([f['genres'] for f in features])
        
        # Create numerical features
        numerical_features = [[f['rating'], f['popularity']] for f in features]
        
        # Combine features
        X = np.hstack([genre_features, numerical_features])
        
        # Create and train the model
        self.model = NearestNeighbors(n_neighbors=10, metric='cosine')
        self.model.fit(X)
        
        return self.model
    
    def get_recommendations(self, user_history, anime_data, n_recommendations=10):
        """
        Get personalized recommendations based on user history
        """
        if not user_history or not self.model:
            return []
            
        # Get the average feature vector of user's watched anime
        watched_features = self.preprocess_anime_data([h.anime for h in user_history])
        if not watched_features:
            return []
            
        # Calculate average feature vector
        avg_features = np.mean([self.model.transform([f])[0] for f in watched_features], axis=0)
        
        # Find similar anime
        distances, indices = self.model.kneighbors([avg_features])
        
        # Get recommended anime objects
        recommendations = [anime_data[i] for i in indices[0] 
                         if anime_data[i].id not in [h.anime_id for h in user_history]]
        
        return recommendations[:n_recommendations]
