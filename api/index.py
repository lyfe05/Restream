from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os

app = FastAPI(title="Stream Relay", version="1.0")

# CORS for Stremio/web players
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# Base configuration URL (the long encoded config string)
BASE_CONFIG = "%7B%22multi%22%3A%22on%22%2C%22mediaFlowProxyUrl%22%3A%22%22%2C%22mediaFlowProxyPassword%22%3A%22%22%2C%22disableExtractor_doodstream%22%3A%22on%22%2C%22disableExtractor_dropload%22%3A%22on%22%2C%22disableExtractor_fastream%22%3A%22on%22%2C%22disableExtractor_filelions%22%3A%22on%22%2C%22disableExtractor_filemoon%22%3A%22on%22%2C%22disableExtractor_fsst%22%3A%22on%22%2C%22disableExtractor_hubcloud%22%3A%22on%22%2C%22disableExtractor_hubdrive%22%3A%22on%22%2C%22disableExtractor_kinoger%22%3A%22on%22%2C%22disableExtractor_lulustream%22%3A%22on%22%2C%22disableExtractor_mixdrop%22%3A%22on%22%2C%22disableExtractor_savefiles%22%3A%22on%22%2C%22disableExtractor_streamembed%22%3A%22on%22%2C%22disableExtractor_streamtape%22%3A%22on%22%2C%22disableExtractor_streamup%22%3A%22on%22%2C%22disableExtractor_supervideo%22%3A%22on%22%2C%22disableExtractor_uqload%22%3A%22on%22%2C%22disableExtractor_vidora%22%3A%22on%22%2C%22disableExtractor_voe%22%3A%22on%22%2C%22disableExtractor_youtube%22%3A%22on%22%7D"
BASE_URL = f"https://webstreamr.hayd.uk/{BASE_CONFIG}"

REQUEST_TIMEOUT = 30.0
client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True)

async def fetch_streams(target_url: str):
    """Helper to fetch and return JSON streams"""
    try:
        response = await client.get(target_url)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="No streams found")
        raise HTTPException(status_code=502, detail=f"Upstream error: {e.response.status_code}")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Stream service unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/movie/{imdb_id}")
async def get_movie_streams(
    imdb_id: str = Path(..., pattern=r"^tt\d+$", description="IMDB ID (e.g., tt6263850)")
):
    """
    Fetch movie streams
    /movie/tt6263850 → https://webstreamr.hayd.uk/.../stream/movie/tt6263850.json
    """
    target_url = f"{BASE_URL}/stream/movie/{imdb_id}.json"
    data = await fetch_streams(target_url)
    
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "public, max-age=3600", "X-Content-Type": "movie"}
    )

@app.get("/tv/{imdb_id}/{season}/{episode}")
async def get_tv_streams(
    imdb_id: str = Path(..., pattern=r"^tt\d+$", description="IMDB ID (e.g., tt14824792)"),
    season: int = Path(..., ge=1, description="Season number"),
    episode: int = Path(..., ge=1, description="Episode number")
):
    """
    Fetch TV episode streams
    /tv/tt14824792/1/1 → https://webstreamr.hayd.uk/.../stream/series/tt14824792:1:1.json
    """
    target_url = f"{BASE_URL}/stream/series/{imdb_id}:{season}:{episode}.json"
    data = await fetch_streams(target_url)
    
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "public, max-age=1800", "X-Content-Type": "episode"}
    )

@app.get("/")
async def root():
    return {
        "status": "Stream Relay Active",
        "endpoints": {
            "movie": "/movie/{imdb_id}",
            "tv_episode": "/tv/{imdb_id}/{season}/{episode}"
        },
        "examples": {
            "movie": "/movie/tt6263850",
            "tv": "/tv/tt14824792/1/1"
        }
    }

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
