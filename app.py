from flask import Flask, render_template, jsonify, request, flash, redirect, url_for
import os
import asyncio
from datetime import datetime
from anime_utils import AnimeStreaming, MLRecommender
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from jikanpy import Jikan
from mal_scraper import MALScraper
from mal_api import MALClient

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///anineesan.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
jikan = Jikan()
anime_streaming = AnimeStreaming()
ml_recommender = MLRecommender()
mal_scraper = MALScraper()
mal_client = MALClient(client_id="8a4287683e2c635726369a2dd1c086eb")

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    watch_history = db.relationship('WatchHistory', backref='user', lazy=True)
    preferences = db.relationship('UserPreferences', backref='user', uselist=False)

class UserPreferences(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    preferred_genres = db.Column(db.String(500))  # Store as comma-separated values
    min_rating = db.Column(db.Float, default=7.0)
    max_episodes = db.Column(db.Integer, default=0)  # 0 means no limit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Anime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mal_id = db.Column(db.Integer, unique=True)
    title = db.Column(db.String(200), nullable=False)
    genres = db.Column(db.String(500))
    rating = db.Column(db.Float)
    image_url = db.Column(db.String(500))
    gogoanime_id = db.Column(db.String(200))
    total_episodes = db.Column(db.Integer)

class WatchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    anime_id = db.Column(db.Integer, db.ForeignKey('anime.id'), nullable=False)
    watched_date = db.Column(db.DateTime, default=datetime.utcnow)
    rating = db.Column(db.Integer)
    last_episode = db.Column(db.Integer, default=1)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    try:
        # Get top rated anime
        fields = ['id', 'title', 'main_picture', 'mean', 'synopsis', 'rank']
        trending = mal_client.get_anime_ranking('all', limit=12, fields=fields)
        trending_anime = []
        for item in trending.get('data', []):
            node = item.get('node', {})
            if node:
                anime_data = {
                    'id': node.get('id'),
                    'title': node.get('title'),
                    'images': {
                        'jpg': {
                            'image_url': node.get('main_picture', {}).get('medium')
                        }
                    },
                    'score': node.get('mean'),
                    'synopsis': node.get('synopsis', '')[:200] + '...' if node.get('synopsis') else '',
                    'mal_id': node.get('id')
                }
                trending_anime.append(anime_data)
        
        return render_template('index.html', 
                           trending_anime=trending_anime,
                           recent_recommendations=[])
    except Exception as e:
        print(f"Error in index route: {e}")
        return render_template('index.html', 
                           trending_anime=[],
                           recent_recommendations=[])

@app.route('/recommendations')
@login_required
def recommendations():
    try:
        # Get user preferences
        user_prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
        fields = 'id,title,main_picture,mean,synopsis,genres,num_episodes,media_type,start_season,rating'
        
        # Get user's watch history for better recommendations
        watch_history = WatchHistory.query.filter_by(user_id=current_user.id).all()
        watched_ids = [w.anime_id for w in watch_history]
        
        # Initialize lists
        personalized = []
        trending_anime = []
        seasonal_anime = []
        
        # Get personalized recommendations based on user preferences and watch history
        if user_prefs and user_prefs.preferred_genres:
            try:
                preferred_genres = user_prefs.preferred_genres.split(',')
                for genre in preferred_genres:
                    # Search for each preferred genre
                    genre_results = mal_client.search_anime(
                        f"{genre.strip()} genre",
                        sort='anime_score',
                        limit=6,
                        fields=fields
                    )
                    
                    if genre_results and 'data' in genre_results:
                        for item in genre_results['data']:
                            anime = item.get('node', {})
                            if not anime or anime.get('id') in watched_ids:
                                continue
                                
                            # Apply user preferences filters
                            rating = float(anime.get('mean', 0) or 0)
                            episodes = int(anime.get('num_episodes', 0) or 0)
                            
                            if rating >= user_prefs.min_rating and \
                               (user_prefs.max_episodes == 0 or episodes <= user_prefs.max_episodes):
                                formatted = format_anime_data(anime)
                                if formatted and formatted not in personalized:
                                    personalized.append(formatted)
            except Exception as e:
                print(f"Error fetching personalized recommendations: {e}")
        
        # Get trending anime
        try:
            trending = mal_client.search_anime(
                '',
                sort='anime_score',
                limit=12,
                fields=fields
            )
            if trending and 'data' in trending:
                trending_anime = [format_anime_data(item['node']) 
                                for item in trending['data'] 
                                if item.get('node')]
        except Exception as e:
            print(f"Error fetching trending anime: {e}")
        
        # Get seasonal anime
        try:
            seasonal = mal_client.get_seasonal_anime(fields=fields)
            if seasonal and 'data' in seasonal:
                seasonal_anime = [format_anime_data(item['node']) 
                                for item in seasonal['data'] 
                                if item.get('node')][:12]
        except Exception as e:
            print(f"Error fetching seasonal anime: {e}")
        
        # If we have no recommendations at all, show an error
        if not any([personalized, trending_anime, seasonal_anime]):
            flash('Unable to load recommendations at this time. Please try again later.', 'warning')
            return redirect(url_for('index'))
        
        return render_template('recommendations.html',
                           personalized_anime=personalized,
                           trending_anime=trending_anime,
                           seasonal_anime=seasonal_anime)
    except Exception as e:
        print(f"Error in recommendations route: {e}")
        flash('Error loading recommendations. Please try again later.', 'danger')
        return redirect(url_for('index'))

def format_anime_data(anime):
    """Helper function to format anime data consistently"""
    if not anime:
        return None
    
    return {
        'id': anime.get('id'),
        'mal_id': anime.get('id'),
        'title': anime.get('title'),
        'images': {
            'jpg': {
                'image_url': anime.get('main_picture', {}).get('medium')
            }
        },
        'score': anime.get('mean'),
        'synopsis': anime.get('synopsis', '')[:200] + '...' if anime.get('synopsis') else '',
        'genres': anime.get('genres', []),
        'episodes': anime.get('num_episodes'),
        'type': anime.get('media_type')
    }

@app.route('/rate_anime/<int:anime_id>', methods=['POST'])
@login_required
def rate_anime(anime_id):
    rating = request.form.get('rating', type=int)
    if not rating or rating < 1 or rating > 10:
        flash('Invalid rating. Please rate between 1 and 10.', 'danger')
        return redirect(url_for('watch_anime', anime_id=anime_id))
    
    # Get or create watch history
    watch_history = WatchHistory.query.filter_by(
        user_id=current_user.id,
        anime_id=anime_id
    ).first()
    
    if watch_history:
        watch_history.rating = rating
    else:
        watch_history = WatchHistory(
            user_id=current_user.id,
            anime_id=anime_id,
            rating=rating
        )
        db.session.add(watch_history)
    
    db.session.commit()
    flash('Rating submitted successfully!', 'success')
    return redirect(url_for('watch_anime', anime_id=anime_id))

@app.route('/watch/<int:anime_id>')
@login_required
def watch_anime(anime_id):
    try:
        # Get anime details from MAL API with all necessary fields
        fields = 'id,title,main_picture,mean,synopsis,genres,num_episodes,media_type,start_season,rating,studios'
        anime = mal_client.get_anime_details(anime_id, fields=fields)
        
        if not anime:
            flash('Anime not found.', 'danger')
            return redirect(url_for('index'))
        
        # First, ensure the anime exists in our database
        local_anime = Anime.query.filter_by(mal_id=anime_id).first()
        if not local_anime:
            # Try to get streaming ID from AnimeStreaming utility
            gogoanime_id = anime_streaming.get_gogoanime_id(anime.get('title'))
            
            local_anime = Anime(
                mal_id=anime_id,
                title=anime.get('title'),
                genres=','.join([g.get('name', '') for g in anime.get('genres', [])]),
                rating=anime.get('mean'),
                image_url=anime.get('main_picture', {}).get('medium'),
                total_episodes=anime.get('num_episodes'),
                gogoanime_id=gogoanime_id
            )
            db.session.add(local_anime)
            db.session.commit()
        
        # Get or create user's watch history
        watch_history = WatchHistory.query.filter_by(
            user_id=current_user.id,
            anime_id=local_anime.id
        ).first()
        
        current_episode = watch_history.last_episode if watch_history else 1
        total_episodes = anime.get('num_episodes', 1)
        
        # Get streaming URL for current episode
        streaming_url = None
        if local_anime.gogoanime_id:
            streaming_url = anime_streaming.get_streaming_url(
                local_anime.gogoanime_id, 
                current_episode
            )
        
        return render_template('watch.html',
                           anime=anime,
                           current_episode=current_episode,
                           total_episodes=total_episodes,
                           streaming_url=streaming_url,
                           user_rating=watch_history.rating if watch_history else None)
                           
    except Exception as e:
        print(f"Detailed error in watch_anime route: {str(e)}")
        flash('Error loading anime. Please try again later.', 'danger')
        return redirect(url_for('index'))


@app.route('/update_episode/<string:anime_id>/<int:episode>')
@login_required
def update_episode(anime_id, episode):
    anime = Anime.query.filter_by(gogoanime_id=anime_id).first()
    if not anime:
        return jsonify({'error': 'Anime not found'}), 404
    
    watch_history = WatchHistory.query.filter_by(
        user_id=current_user.id,
        anime_id=anime.id
    ).first()
    
    if watch_history:
        watch_history.last_episode = episode
    else:
        watch_history = WatchHistory(
            user_id=current_user.id,
            anime_id=anime.id,
            last_episode=episode
        )
        db.session.add(watch_history)
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if not query:
        return render_template('search.html', results=[])
    
    try:
        # Search using MAL API
        results = mal_client.search_anime(query, limit=24)
        anime_list = []
        
        # Process the results to match our template format
        for item in results.get('data', []):
            anime = item.get('node', {})
            if anime:
                anime_list.append({
                    'id': anime.get('id'),
                    'title': anime.get('title'),
                    'main_picture': anime.get('main_picture', {}),
                    'mean': anime.get('mean'),
                    'synopsis': anime.get('synopsis', '')[:200] + '...' if anime.get('synopsis') else ''
                })
        
        return render_template('search.html', results=anime_list)
    except Exception as e:
        print(f"Error in search: {e}")
        flash('Error searching for anime. Please try again.', 'danger')
        return render_template('search.html', results=[])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:  # In production, use proper password hashing
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(username=username, password=password)  # In production, hash the password
        db.session.add(new_user)
        
        # Create default preferences
        preferences = UserPreferences(
            user=new_user,
            preferred_genres='Action,Adventure,Comedy',  # Default genres
            min_rating=7.0,
            max_episodes=0
        )
        db.session.add(preferences)
        db.session.commit()
        
        login_user(new_user)
        flash('Account created successfully! Update your anime preferences to get personalized recommendations.', 'success')
        return redirect(url_for('preferences'))
    return render_template('register.html')

@app.route('/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    if request.method == 'POST':
        # Get selected genres
        selected_genres = request.form.getlist('genres')
        min_rating = float(request.form.get('min_rating', 7.0))
        max_episodes = int(request.form.get('max_episodes', 0))
        
        # Update or create preferences
        preferences = UserPreferences.query.filter_by(user_id=current_user.id).first()
        if preferences:
            preferences.preferred_genres = ','.join(selected_genres)
            preferences.min_rating = min_rating
            preferences.max_episodes = max_episodes
        else:
            preferences = UserPreferences(
                user=current_user,
                preferred_genres=','.join(selected_genres),
                min_rating=min_rating,
                max_episodes=max_episodes
            )
            db.session.add(preferences)
        
        db.session.commit()
        flash('Preferences updated successfully!', 'success')
        return redirect(url_for('recommendations'))
    
    # Get current preferences
    preferences = UserPreferences.query.filter_by(user_id=current_user.id).first()
    genres = [
        'Action', 'Adventure', 'Comedy', 'Drama', 'Fantasy', 'Horror', 'Mystery',
        'Romance', 'Sci-Fi', 'Slice of Life', 'Sports', 'Supernatural', 'Thriller'
    ]
    
    return render_template('preferences.html',
                        genres=genres,
                        user_preferences=preferences)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def get_trending_anime():
    try:
        trending = jikan.top(type='anime', page=1)
        return trending['data'][:10]
    except:
        return []

def get_personalized_recommendations(user_id, limit=12):
    # Get user's watch history
    history = WatchHistory.query.filter_by(user_id=user_id).all()
    
    if not history:
        return get_trending_anime()[:limit]
    
    # Create user-anime rating matrix
    user_ratings = {}
    for watch in history:
        if watch.rating:
            user_ratings[watch.anime_id] = watch.rating
    
    if not user_ratings:
        return get_trending_anime()[:limit]
    
    # Get similar anime based on genres and ratings
    recommended_anime = []
    for anime_id, rating in user_ratings.items():
        anime = Anime.query.get(anime_id)
        if anime and anime.genres:
            genres = anime.genres.split(',')
            for genre in genres:
                genre = genre.strip()
                similar_anime = Anime.query.filter(
                    Anime.genres.like(f'%{genre}%'),
                    Anime.id != anime_id
                ).all()
                for similar in similar_anime:
                    if similar not in recommended_anime:
                        recommended_anime.append(similar)
    
    # Sort by rating and limit results
    recommended_anime.sort(key=lambda x: x.rating or 0, reverse=True)
    return recommended_anime[:limit]

@app.route('/mal_recommendations')
def mal_recommendations():
    """Get recent recommendations from MyAnimeList"""
    try:
        recommendations = mal_scraper.get_recent_recommendations()
        return jsonify({
            'status': 'success',
            'recommendations': recommendations
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/anime/search')
def search_anime():
    """Search for anime using MAL API v2"""
    try:
        query = request.args.get('q', '')
        limit = min(int(request.args.get('limit', 10)), 100)
        offset = int(request.args.get('offset', 0))
        
        if not query:
            return jsonify({
                'status': 'error',
                'message': 'Query parameter is required'
            }), 400
            
        results = mal_client.search_anime(query, limit, offset)
        return jsonify({
            'status': 'success',
            'results': results
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/anime/<int:anime_id>')
def get_anime_details(anime_id):
    """Get detailed information about a specific anime"""
    try:
        details = mal_client.get_anime_details(anime_id)
        return jsonify({
            'status': 'success',
            'anime': details
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/anime/seasonal')
def get_seasonal_anime():
    """Get seasonal anime"""
    try:
        year = int(request.args.get('year', datetime.now().year))
        season = request.args.get('season', 'winter')
        limit = min(int(request.args.get('limit', 10)), 100)
        offset = int(request.args.get('offset', 0))
        
        results = mal_client.get_seasonal_anime(year, season, limit=limit, offset=offset)
        return jsonify({
            'status': 'success',
            'results': results
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/anime/ranking')
def get_anime_ranking():
    """Get anime ranking"""
    try:
        ranking_type = request.args.get('type', 'all')
        limit = min(int(request.args.get('limit', 10)), 100)
        offset = int(request.args.get('offset', 0))
        
        results = mal_client.get_anime_ranking(ranking_type, limit, offset)
        return jsonify({
            'status': 'success',
            'results': results
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/preferences/update', methods=['POST'])
@login_required
def update_preferences_api():
    try:
        data = request.get_json()
        
        # Update preferences
        preferences = UserPreferences.query.filter_by(user_id=current_user.id).first()
        if preferences:
            if 'genres' in data:
                preferences.preferred_genres = ','.join(data['genres'])
            if 'min_rating' in data:
                preferences.min_rating = float(data['min_rating'])
            if 'max_episodes' in data:
                preferences.max_episodes = int(data['max_episodes'])
            
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Preferences updated successfully'
            })
        
        return jsonify({
            'status': 'error',
            'message': 'Preferences not found'
        }), 404
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    with app.app_context():
        # Drop all tables and recreate them
        db.drop_all()
        db.create_all()
    app.run(debug=True)
