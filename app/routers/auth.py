from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas, security


router = APIRouter(
    prefix="/api/auth",
    tags=["Auth"]
)


@router.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate a user using OAuth2 password flow.

    Swagger UI sends:
        username=<username>
        password=<password>

    as application/x-www-form-urlencoded.
    """

    user = (
        db.query(models.User)
        .filter(models.User.username == form_data.username)
        .first()
    )

    # Invalid username/password
    if not user or not security.verify_password(
        form_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Account disabled
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account disabled"
        )

    # Create JWT
    token = security.create_access_token(
        subject=user.username,
        role=user.role.value
    )

    # Return token expected by OAuth2 / Swagger
    return schemas.Token(
        access_token=token,
        token_type="bearer",
        role=user.role.value,
        username=user.username,
    )


@router.get(
    "/me",
    response_model=schemas.UserOut
)
def me(
    current_user: models.User = Depends(
        security.get_current_user
    )
):
    """
    Return the currently authenticated user.
    """

    return current_user