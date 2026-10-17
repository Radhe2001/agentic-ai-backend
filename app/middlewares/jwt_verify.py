from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from jose import jwt, JWTError
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

PUBLIC_PATHS = {
    "/",
    "/users/login",
    "/users/create",
}


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        # Allow public endpoints
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Read Authorization header
        authorization = request.headers.get("Authorization")

        if not authorization or not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = authorization.split(" ", 1)[1].strip()

        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
            )
            print(f"Decoded JWT payload: {payload}")
            user_id = payload.get("sub")

            if not user_id:
                raise JWTError("Missing subject")

            request.state.user_id = int(user_id)
            request.state.user_role = payload.get("role")

        except (JWTError, ValueError, TypeError):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
