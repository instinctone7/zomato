"""Local HTTP API for restaurant discovery and Groq recommendations."""
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.data.loader import load_prepared_dataset
from src.service import get_options, get_discovery, recommend


@asynccontextmanager
async def lifespan(app):
    app.state.restaurants = load_prepared_dataset()
    yield


app = FastAPI(title='Zomato AI API', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000', 'http://127.0.0.1:3000'],
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


class Preferences(BaseModel):
    location: str = Field(default='Bangalore', min_length=1, max_length=100)
    budget: Literal['low', 'medium', 'high'] = 'medium'
    cuisine: str = Field(default='Any', max_length=100)
    min_rating: float = Field(default=3.5, ge=0, le=5)
    extra_prefs: str = Field(default='', max_length=200)


@app.get('/api/health')
def health():
    return {'status': 'ok', 'restaurants': len(app.state.restaurants)}


@app.get('/api/options')
def options():
    return get_options(app.state.restaurants)


@app.get('/api/restaurants')
def restaurants():
    return {'restaurants': get_discovery(app.state.restaurants)}


@app.post('/api/recommendations')
def recommendations(request: Preferences):
    try:
        return recommend(app.state.restaurants, request.model_dump())
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
