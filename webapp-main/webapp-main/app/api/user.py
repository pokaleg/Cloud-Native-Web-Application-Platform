import time
import uuid
import json
import boto3

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Response, Depends, HTTPException, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from botocore.exceptions import ClientError

from app.core.database import get_db
from app.core.security import hash_password
from app.core.config import settings
from app.models.user import User, EmailVerificationToken
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.core.logger import setup_logger
from app.core.metrics import record_api_call, record_api_time, record_db_query_time

router = APIRouter()
security = HTTPBasic()
logger = setup_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _publish_sns(email: str, first_name: str, token: str) -> None:
    """Publish a verification message to SNS. Silently logs on failure."""
    if not settings.SNS_TOPIC_ARN:
        logger.warning("SNS_TOPIC_ARN not set — skipping SNS publish")
        return
    try:
        sns = boto3.client("sns", region_name=settings.AWS_REGION)
        message = json.dumps({
            "email": email,
            "first_name": first_name,
            "token": token,
            "domain": settings.DOMAIN,
        })
        sns.publish(TopicArn=settings.SNS_TOPIC_ARN, Message=message)
        logger.info(f"SNS published for {email}")
    except ClientError as e:
        logger.error(f"SNS publish failed for {email}: {e}")


# ── Auth dependency ───────────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    db_start = time.time()
    user = db.query(User).filter(User.username == credentials.username.lower()).first()
    record_db_query_time("user_lookup", (time.time() - db_start) * 1000)

    if not user or not user.check_password(credentials.password):
        logger.warning(f"Authentication failed for username: {credentials.username}")
        raise HTTPException(
            status_code=401,
            detail="Authentication credentials are missing or invalid"
        )
    return user


def get_verified_user(current_user: User = Depends(get_current_user)) -> User:
    """Like get_current_user but also requires is_verified=True."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Account not verified. Please verify your email address."
        )
    return current_user


# ── User endpoints ────────────────────────────────────────────────────────────

@router.post("/v1/user", status_code=201, response_model=UserResponse)
async def create_user(
    request: Request,
    user_data: UserCreate,
    response: Response,
    db: Session = Depends(get_db)
):
    start = time.time()
    record_api_call("create_user")
    logger.info(f"create_user: request for {user_data.username}")

    # Check for duplicate
    db_start = time.time()
    existing = db.query(User).filter(User.username == user_data.username.lower()).first()
    record_db_query_time("user_exists_check", (time.time() - db_start) * 1000)

    if existing:
        logger.warning(f"create_user: duplicate email — {user_data.username}")
        record_api_time("create_user", (time.time() - start) * 1000)
        raise HTTPException(
            status_code=409,
            detail="A user with this email address already exists"
        )

    try:
        user = User(
            username=user_data.username.lower(),
            password=hash_password(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            is_verified=False,
        )
        db.add(user)

        db_start = time.time()
        db.commit()
        db.refresh(user)
        record_db_query_time("user_create", (time.time() - db_start) * 1000)

        # Create verification token (expires in 1 minute)
        token_str = str(uuid.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(minutes=1)
        token_obj = EmailVerificationToken(
            user_id=user.id,
            token=token_str,
            email=user.username,
            expires_at=expires,
        )
        db.add(token_obj)
        db.commit()

        # Publish to SNS (non-blocking — failure won't break user creation)
        _publish_sns(user.username, user.first_name, token_str)

        response.headers["Location"] = "/v1/user/self"
        logger.info(f"create_user: success — id={user.id}")
        record_api_time("create_user", (time.time() - start) * 1000)
        return user

    except IntegrityError:
        db.rollback()
        logger.warning(f"create_user: integrity error for {user_data.username}")
        record_api_time("create_user", (time.time() - start) * 1000)
        raise HTTPException(
            status_code=409,
            detail="A user with this email address already exists"
        )


@router.get("/v1/user/self", response_model=UserResponse)
def get_user(current_user: User = Depends(get_current_user)):
    start = time.time()
    record_api_call("get_user")
    logger.info(f"get_user: {current_user.username}")
    record_api_time("get_user", (time.time() - start) * 1000)
    return current_user


@router.put("/v1/user/self", status_code=204)
def update_user(
    request: Request,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    start = time.time()
    record_api_call("update_user")
    logger.info(f"update_user: {current_user.username}")

    update_data = user_update.model_dump(exclude_unset=True)

    if 'first_name' in update_data and update_data['first_name'] is not None:
        current_user.first_name = update_data['first_name']
    if 'last_name' in update_data and update_data['last_name'] is not None:
        current_user.last_name = update_data['last_name']
    if 'password' in update_data and update_data['password'] is not None:
        current_user.password = hash_password(update_data['password'])

    db_start = time.time()
    db.commit()
    record_db_query_time("user_update", (time.time() - db_start) * 1000)

    logger.info(f"update_user: success for {current_user.username}")
    record_api_time("update_user", (time.time() - start) * 1000)
    return Response(status_code=204)


# ── Email verification endpoint ───────────────────────────────────────────────

@router.get("/v1/user/verify-email", status_code=200)
def verify_email(
    email: str = Query(..., description="User email address"),
    token: str = Query(..., description="Verification token UUID"),
    db: Session = Depends(get_db)
):
    record_api_call("verify_email")
    logger.info(f"verify_email: request for {email}")

    # Look up the token
    db_start = time.time()
    token_obj = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token == token,
        EmailVerificationToken.email == email.lower(),
    ).first()
    record_db_query_time("token_lookup", (time.time() - db_start) * 1000)

    if not token_obj:
        logger.warning(f"verify_email: invalid token for {email}")
        raise HTTPException(status_code=400, detail="Invalid or unknown verification token")

    if token_obj.used:
        logger.warning(f"verify_email: token already used for {email}")
        raise HTTPException(status_code=400, detail="Verification token has already been used")

    # Check expiry
    now = datetime.now(timezone.utc)
    if now > token_obj.expires_at:
        logger.warning(f"verify_email: expired token for {email}")
        raise HTTPException(status_code=400, detail="Verification token has expired")

    # Mark token as used and verify user
    token_obj.used = True
    user = db.query(User).filter(User.id == token_obj.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_verified = True
    db.commit()

    logger.info(f"verify_email: success for {email}")
    return {"message": "Email verified successfully"}
