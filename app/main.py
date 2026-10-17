from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import users
from app.routers import doc_reader
from app.middlewares.jwt_verify import JWTAuthMiddleware

app = FastAPI(title="My API", description="My FastAPI backend", version="1.0.0")

app.add_middleware(JWTAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(users.router)
app.include_router(doc_reader.router)


@app.get("/")
def home():
    return {"message": "Hello FastAPI"}
