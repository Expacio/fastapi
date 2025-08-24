from typing import Optional

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

app = FastAPI()
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os, requests
load_dotenv()
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
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
    if datetime.utcnow() > tokens["expires_at"]:
        refreshed = refresh_access_token(tokens["refresh_token"])
        tokens["access_token"] = refreshed["access_token"]
        tokens["expires_at"] = datetime.utcnow() + timedelta(seconds=refreshed["expires_in"])
        db.users.update_one({"user_id": user_id}, {"$set": {"access_token": tokens["access_token"], "expires_at": tokens["expires_at"]}})
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = requests.get("https://api.spotify.com/v1/me/top/tracks?limit=5", headers=headers)
    return [
    {
        "name": x["name"],
        "artists": [y["name"] for y in x["artists"]],
        "album": x["album"]["name"],
        "cover": x["album"]["images"][0]["url"] if x["album"]["images"] else None,
        "spotify_url": x["external_urls"]["spotify"]
    }
    for x in resp.json().get("items", [])
]

@app.get("/me/top-tracks")
def me(user_id: str):
    tokens = get_user_tokens(user_id)
    if not tokens:
        return {"error": "User not found"}, 404
    return get_user_profile(user_id)


def refresh_access_token(refresh_token):
    token_url = "https://accounts.spotify.com/api/token"
    response = requests.post(
        token_url,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    resp = response.json()
    return resp

@app.get("/ponger")
async def root():
    return {"message": "Thanks lmao."}

@app.get("/login")
async def login():
    print(SCOPE)
    url = (
        "https://accounts.spotify.com/authorize"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&scope={SCOPE}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return RedirectResponse(url)

@app.get("/callback")
def callback(code: str):
    token_url = "https://accounts.spotify.com/api/token"
    response = requests.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    tokens = response.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in")
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    tokens_c = db.users
    user_info = requests.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()
    user_id = user_info["id"]
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
    return RedirectResponse(url=f"http://localhost:3000/dashboard?user_id={user_id}")

