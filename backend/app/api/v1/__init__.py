"""Version 1 API router composition."""

from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    auth,
    destinations,
    itineraries,
    notifications,
    recommendations,
    reviews,
    shared,
    users,
    weather,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(destinations.router)
api_router.include_router(itineraries.router)
api_router.include_router(recommendations.router)
api_router.include_router(weather.router)
api_router.include_router(reviews.router)
api_router.include_router(notifications.router)
api_router.include_router(analytics.router)
api_router.include_router(shared.router)

__all__ = ["api_router"]
