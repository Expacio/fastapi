from typing import Optional

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os, requests
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from spotipy.exceptions import SpotifyException

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
uri = os.getenv("MONGODB_URI")
client = MongoClient(uri, server_api=ServerApi('1'))
db = client.goonify

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SCOPE = os.getenv("SPOTIFY_SCOPES")

def get_user_tokens(user_id):
    return db.users.find_one({"user_id": user_id})

def get_user_profile(user_id):
    tokens = get_user_tokens(user_id)
    if not tokens:
        return {"error": "User not found"}, 404

    # Use a mock Spotipy object for demonstration purposes
    # In a real application, you would initialize it with the tokens
    sp = spotipy.Spotify(auth=tokens["access_token"])

    # Handle token refresh
    if datetime.utcnow() > tokens["expires_at"]:
        auth_manager = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)
        try:
            refreshed = auth_manager.refresh_access_token(tokens["refresh_token"])
            tokens["access_token"] = refreshed["access_token"]
            tokens["expires_at"] = datetime.utcnow() + timedelta(seconds=refreshed["expires_in"])
            db.users.update_one({"user_id": user_id}, {"$set": {"access_token": tokens["access_token"], "expires_at": tokens["expires_at"]}})
            sp = spotipy.Spotify(auth=tokens["access_token"]) # Re-initialize with new token
        except SpotifyException as e:
            print(f"Error refreshing token: {e}")
            return {"error": "Failed to refresh token"}, 500

    # Get top tracks using spotipy
    try:
        results = sp.current_user_top_tracks(limit=10, time_range='medium_term')
        
        return [
            {
                "name": track["name"],
                "artists": [artist["name"] for artist in track["artists"]],
                "album": track["album"]["name"],
                "cover": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                "spotify_url": track["external_urls"]["spotify"]
            }
            for track in results["items"]
        ]
    except SpotifyException as e:
        print(f"Error fetching top tracks: {e}")
        return {"error": "Failed to fetch top tracks from Spotify"}, 500

@app.get("/me/top-tracks")
def me(user_id: str):
    tokens = get_user_tokens(user_id)
    if not tokens:
        return {"error": "User not found"}, 404
    return get_user_profile(user_id)

@app.get("/ponger")
async def root():
    return {"message": "Thanks lmao."}

@app.get("/login")
async def login():
    auth_manager = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)
    url = auth_manager.get_authorize_url()
    return RedirectResponse(url)

@app.get("/callback")
def callback(code: str):
    auth_manager = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)
    tokens = auth_manager.get_access_token(code)
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in")
    
    if expires_in is None:
        return {"error": "Failed to get token expiration time from Spotify"}
    
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    try:
        sp = spotipy.Spotify(auth=access_token)
        user_info = sp.me()
        user_id = user_info["id"]

        tokens_c = db.users
        tokens_c.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "display_name": user_info["display_name"],
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": expires_at
                }
            },
            upsert=True
        )
        return RedirectResponse(url=f"https://goonify-app.vercel.app/dashboard?user_id={user_id}")
    except SpotifyException as e:
        print(f"Error getting user info or updating database: {e}")
        return {"error": "Failed to get user info or save tokens"}, 500