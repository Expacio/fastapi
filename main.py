from typing import Optional

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

app = FastAPI()
from dotenv import load_dotenv
import os
load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SCOPE = os.getenv("SPOTIFY_SCOPES")

@app.get("/ponger")
async def root():
    return {"message": "Thanks lmao."}

@app.get("/login")
async def login():
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
    print(tokens)