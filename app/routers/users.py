from fastapi import FastAPI, Depends, HTTPException, Request, status, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pwdlib import PasswordHash
from app.db.database import get_db
from app.models.users.user import Users
from app.schemas.users import LoginResponse, UserCreate, UserLogin, UserResponse
from app.utils.jwt import create_access_token

router = APIRouter(prefix="/users", tags=["users"])

password_hash = PasswordHash.recommended()


@router.get("/")
def get_users():
    return {"message": "User list", "users": ["Radheshyam Jha"]}


@router.post(
    "/create",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    hashed_password = password_hash.hash(user_data.password)

    new_user = Users(
        name=user_data.name,
        email=user_data.email,
        password_hash=hashed_password,
        role="user",
        is_active=True,
    )
    try:
        db.add(new_user)  # Stage the new record
        db.commit()  # Save it to PostgreSQL
        db.refresh(new_user)  # Load generated ID and DB defaults

        access_token = create_access_token(user_id=new_user.id, role=new_user.role)

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=new_user,
        )

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already exists or a database constraint was violated",
        )


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = (
        db.query(Users)
        .filter(Users.email == user_data.email and Users.is_active == True)
        .first()
    )

    if not user or not password_hash.verify(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(user_id=user.id, role=user.role)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user,
    )


@router.get("/profile", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_user(request: Request, db: Session = Depends(get_db)):
    user = (
        db.query(Users)
        .filter(Users.id == request.state.user_id and Users.is_active == True)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
    )
