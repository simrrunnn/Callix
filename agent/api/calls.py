"""
/api/token: generates a short-lived LiveKit access token server-side, so
the browser-based call UI (a separate React/TS project, deployed
independently) never needs the LIVEKIT_API_SECRET directly -- it only ever
sees the resulting scoped JWT.
"""

import os
import uuid

from fastapi import APIRouter
from livekit import api

router = APIRouter()


@router.get("/api/token")
async def get_token(identity: str = "caller") -> dict:
    room_name = f"call-{uuid.uuid4().hex[:8]}"
    token = (
        api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
        .with_identity(f"{identity}-{uuid.uuid4().hex[:6]}")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    return {"token": token, "url": os.environ["LIVEKIT_URL"], "room": room_name}
