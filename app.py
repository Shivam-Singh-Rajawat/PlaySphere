"""PlaySphere: accessible, single-origin FastAPI + SQLite sports discovery app."""

import hashlib
import json
import os
import secrets
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Annotated, Literal

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile, Response
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint, case, create_engine, func, or_, select, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parent
MAX_VIDEO_BYTES = 25 * 1024 * 1024
MAX_CLOUD_VIDEO_BYTES = 100 * 1024 * 1024
ROLES = {'player', 'coach', 'scout', 'club'}
SCOUT_ROLES = {'coach', 'scout', 'club'}


def load_local_env(root: Path) -> None:
    """Read Neon CLI env files locally; never override explicit process or Vercel config."""
    if os.environ.get('VERCEL'):
        return
    # Neon writes .env.local, so it takes precedence over a generic .env file.
    load_dotenv(root / '.env.local', override=False)
    load_dotenv(root / '.env', override=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    sport: Mapped[str] = mapped_column(String(60), default='')
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city: Mapped[str] = mapped_column(String(100), default='')
    position: Mapped[str] = mapped_column(String(100), default='')
    bio: Mapped[str] = mapped_column(Text, default='')
    stats_json: Mapped[str] = mapped_column(Text, default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Video(Base):
    __tablename__ = 'videos'
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(20))
    visibility: Mapped[str] = mapped_column(String(10), default='public')
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_name: Mapped[str | None] = mapped_column(String(240), unique=True, nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Achievement(Base):
    __tablename__ = 'achievements'
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(160))
    issuer: Mapped[str] = mapped_column(String(160))
    year: Mapped[int]
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Tournament(Base):
    __tablename__ = 'tournaments'
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(180))
    sport: Mapped[str] = mapped_column(String(60), index=True)
    location: Mapped[str] = mapped_column(String(160))
    level: Mapped[str] = mapped_column(String(60), default='Open')
    description: Mapped[str] = mapped_column(Text, default='')
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    registration_deadline: Mapped[date] = mapped_column(Date)
    capacity: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Registration(Base):
    __tablename__ = 'registrations'
    __table_args__ = (UniqueConstraint('tournament_id', 'player_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey('tournaments.id', ondelete='CASCADE'))
    player_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Evaluation(Base):
    __tablename__ = 'evaluations'
    __table_args__ = (UniqueConstraint('scout_id', 'player_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    scout_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    player_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    technique: Mapped[int]
    teamwork: Mapped[int]
    consistency: Mapped[int]
    potential: Mapped[int]
    notes: Mapped[str] = mapped_column(Text, default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Shortlist(Base):
    __tablename__ = 'shortlists'
    __table_args__ = (UniqueConstraint('scout_id', 'player_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    scout_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    player_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = __import__('hashlib').pbkdf2_hmac('sha256', password.encode(), salt, 310_000)
    return f'{salt.hex()}:{digest.hex()}'


def check_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, expected = encoded.split(':', 1)
        digest = __import__('hashlib').pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), 310_000)
        return secrets.compare_digest(digest, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


class RegisterInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: Literal['player', 'coach', 'scout', 'club']
    sport: str = Field(default='', max_length=60)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class PlayerUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sport: str | None = Field(default=None, max_length=60)
    age: int | None = Field(default=None, ge=13, le=100)
    city: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=1800)
    stats: dict[str, str] | None = None

    @field_validator('stats')
    @classmethod
    def valid_stats(cls, v):
        if v is not None and (len(v) > 20 or any(len(k) > 40 or len(str(val)) > 80 for k, val in v.items())):
            raise ValueError('Maximum 20 short statistical fields allowed')
        return v


class AchievementInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    issuer: str = Field(min_length=2, max_length=160)
    year: int = Field(ge=1950, le=2100)
    evidence_url: AnyHttpUrl | None = None


class VideoLinkInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    kind: Literal['highlight', 'match', 'training']
    url: AnyHttpUrl

    @field_validator('url')
    @classmethod
    def secure_url(cls, value):
        if value.scheme != 'https':
            raise ValueError('Use an HTTPS video URL')
        return value

    visibility: Literal['public', 'private'] = 'public'


class CloudUploadRequest(BaseModel):
    visibility: Literal['public', 'private'] = 'public'


class CloudAsset(BaseModel):
    model_config = ConfigDict(extra='forbid')
    public_id: str = Field(min_length=8, max_length=180)
    version: int = Field(ge=1)
    signature: str = Field(min_length=40, max_length=64)
    resource_type: Literal['video']
    type: Literal['upload', 'authenticated']
    format: Literal['mp4', 'webm', 'mov']
    bytes: int = Field(gt=0, le=MAX_CLOUD_VIDEO_BYTES)


class CompleteUploadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ticket: str
    title: str = Field(min_length=2, max_length=160)
    kind: Literal['highlight', 'match', 'training']
    asset: CloudAsset


def cloud_signature(params: dict[str, str | int], secret: str) -> str:
    # Cloudinary's SHA-1 signature format: alphabetical k=v pairs + API secret.
    message = '&'.join(f'{key}={params[key]}' for key in sorted(params)) + secret
    return hashlib.sha1(message.encode('utf-8')).hexdigest()


def cloud_config():
    config = {name: os.environ.get(f'CLOUDINARY_{name.upper()}', '').strip()
              for name in ('cloud_name', 'api_key', 'api_secret')}
    if not all(config.values()):
        raise HTTPException(503, 'Cloud video storage is not configured. Use a video link or configure Cloudinary.')
    return config


def configure_cloudinary(config):
    try:
        import cloudinary
    except ImportError as exc:
        raise HTTPException(503, 'Cloudinary SDK is missing from the deployment.') from exc
    cloudinary.config(cloud_name=config['cloud_name'], api_key=config['api_key'],
                      api_secret=config['api_secret'], secure=True)


class TournamentInput(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    sport: str = Field(min_length=2, max_length=60)
    location: str = Field(min_length=2, max_length=160)
    level: str = Field(default='Open', max_length=60)
    description: str = Field(default='', max_length=3000)
    start_date: date
    end_date: date
    registration_deadline: date
    capacity: int = Field(default=100, ge=1, le=5000)


class EvaluationInput(BaseModel):
    technique: int = Field(ge=1, le=5)
    teamwork: int = Field(ge=1, le=5)
    consistency: int = Field(ge=1, le=5)
    potential: int = Field(ge=1, le=5)
    notes: str = Field(default='', max_length=2000)


def public_user(user: User):
    return {'id': user.id, 'name': user.name, 'role': user.role, 'sport': user.sport,
            'age': user.age, 'city': user.city, 'position': user.position,
            'bio': user.bio, 'stats': json.loads(user.stats_json or '{}')}


def private_user(user: User):
    return {**public_user(user), 'email': user.email}


def public_video(video: Video):
    return {'id': video.id, 'player_id': video.player_id, 'title': video.title,
            'kind': video.kind, 'visibility': video.visibility,
            'url': video.url if video.url else f'/api/videos/{video.id}/file',
            'uploaded': bool(video.storage_name),
            'storage': ('cloud' if video.storage_name and video.storage_name.startswith('cloudinary:')
                        else 'local' if video.storage_name else 'link'),
            'created_at': video.created_at.isoformat()}


def public_achievement(item: Achievement):
    return {'id': item.id, 'title': item.title, 'issuer': item.issuer, 'year': item.year,
            'evidence_url': item.evidence_url, 'verified': item.verified}


def tournament_status(item: Tournament):
    today = date.today()
    if item.end_date < today:
        return 'recent'
    if item.start_date <= today:
        return 'live'
    return 'upcoming'


def tournament_json(db: Session, item: Tournament):
    count = db.scalar(select(func.count(Registration.id)).where(Registration.tournament_id == item.id)) or 0
    return {'id': item.id, 'title': item.title, 'sport': item.sport,
            'location': item.location, 'level': item.level, 'description': item.description,
            'start_date': item.start_date.isoformat(), 'end_date': item.end_date.isoformat(),
            'registration_deadline': item.registration_deadline.isoformat(),
            'capacity': item.capacity, 'participants_count': count,
            'status': tournament_status(item), 'owner_id': item.owner_id,
            'registration_open': (date.today() <= item.registration_deadline and
                                  date.today() <= item.start_date and count < item.capacity)}


def create_app(database_url: str | None = None, upload_dir: str | Path | None = None) -> FastAPI:
    load_local_env(ROOT)
    db_url = database_url or os.environ.get('PLAYSPHERE_DATABASE_URL') or os.environ.get('DATABASE_URL') or f'sqlite:///{ROOT / "playsphere.db"}'
    secret = os.environ.get('PLAYSPHERE_SECRET_KEY') or ''
    on_vercel = bool(os.environ.get('VERCEL'))
    # A filesystem DB vanishes between serverless executions. Fail visibly, never lose user data silently.
    if on_vercel and not (db_url.startswith('postgres://') or db_url.startswith('postgresql://') or db_url.startswith('postgresql+psycopg://')):
        raise RuntimeError('Vercel deployments require a persistent PostgreSQL PLAYSPHERE_DATABASE_URL (or DATABASE_URL).')
    if on_vercel and len(secret) < 32:
        raise RuntimeError('Set a persistent PLAYSPHERE_SECRET_KEY (32+ characters) in Vercel Environment Variables.')
    if not secret:
        secret = secrets.token_urlsafe(48)  # local developer convenience only
    if db_url.startswith('postgres://'):
        db_url = 'postgresql+psycopg://' + db_url[len('postgres://'):]
    elif db_url.startswith('postgresql://'):
        db_url = 'postgresql+psycopg://' + db_url[len('postgresql://'):]
    storage = Path(upload_dir or os.environ.get('PLAYSPHERE_UPLOAD_DIR', ROOT / 'uploads')).resolve()
    if not on_vercel:
        storage.mkdir(parents=True, exist_ok=True)
    engine_options = {'pool_pre_ping': True}
    if db_url.startswith('sqlite'):
        engine_options['connect_args'] = {'check_same_thread': False, 'timeout': 30}
    else:
        # Serverless instances each have a pool; use a small per-instance pool with a DB pooler.
        engine_options.update(pool_size=2, max_overflow=1, pool_timeout=15, pool_recycle=180)
    engine = create_engine(db_url, **engine_options)
    if db_url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def sqlite_pragmas(connection, record):
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.execute('PRAGMA busy_timeout=30000')
            cursor.close()
    # Bootstrap for a new database. Schema changes on an existing production DB require migrations.
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)
    app = FastAPI(title='PlaySphere API', version='2.0.0', docs_url='/api/docs', redoc_url=None)
    app.state.sessionmaker = SessionLocal
    app.state.upload_dir = storage
    app.state.db_url = db_url
    bearer = HTTPBearer(auto_error=False)

    def db_session():
        with SessionLocal() as db:
            yield db

    DB = Annotated[Session, Depends(db_session)]

    def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: DB):
        if not credentials or credentials.scheme.lower() != 'bearer':
            raise HTTPException(401, 'Authentication required', headers={'WWW-Authenticate': 'Bearer'})
        try:
            payload = jwt.decode(credentials.credentials, secret, algorithms=['HS256'])
            user_id = int(payload['sub'])
        except (jwt.PyJWTError, TypeError, ValueError, KeyError):
            raise HTTPException(401, 'Invalid or expired token')
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(401, 'Account no longer exists')
        return user

    Current = Annotated[User, Depends(current_user)]

    def only(*roles):
        def authorized(user: Current):
            if user.role not in roles:
                raise HTTPException(403, 'This action is not permitted for your role')
            return user
        return authorized

    Player = Annotated[User, Depends(only('player'))]
    Recruiter = Annotated[User, Depends(only('coach', 'scout', 'club'))]
    Organizer = Annotated[User, Depends(only('coach', 'club'))]

    def get_player(db, player_id):
        user = db.get(User, player_id)
        if not user or user.role != 'player':
            raise HTTPException(404, 'Player not found')
        return user

    def get_event(db, event_id):
        item = db.get(Tournament, event_id)
        if not item:
            raise HTTPException(404, 'Tournament not found')
        return item

    def player_portfolio(db, user):
        videos = db.scalars(select(Video).where(Video.player_id == user.id, Video.visibility == 'public').order_by(Video.created_at.desc())).all()
        items = db.scalars(select(Achievement).where(Achievement.player_id == user.id).order_by(Achievement.year.desc())).all()
        return {**public_user(user), 'videos': [public_video(v) for v in videos],
                'achievements': [public_achievement(a) for a in items]}

    @app.get('/api/config')
    def site_config():
        cloud_ready = all(os.environ.get(f'CLOUDINARY_{field.upper()}') for field in ('cloud_name','api_key','api_secret'))
        return {'upload_mode': 'cloud' if cloud_ready else ('link-only' if on_vercel else 'local'),
                'max_video_bytes': MAX_CLOUD_VIDEO_BYTES if cloud_ready else MAX_VIDEO_BYTES}

    @app.get('/api/ready')
    def readiness(db: DB):
        db.execute(select(1))
        return {'status': 'ready', 'database': 'connected'}

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'version': '2.0.0'}

    @app.post('/api/auth/register', status_code=201)
    def register(data: RegisterInput, db: DB):
        email = str(data.email).strip().lower()
        if db.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, 'An account already uses this email')
        user = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password),
                    role=data.role, sport=data.sport.strip())
        db.add(user)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(409, 'Account could not be created; email may already exist')
        db.refresh(user)
        token = jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(hours=12)}, secret, algorithm='HS256')
        return {'token': token, 'user': private_user(user)}

    @app.post('/api/auth/login')
    def login(data: LoginInput, db: DB):
        user = db.scalar(select(User).where(User.email == str(data.email).lower()))
        if not user or not check_password(data.password, user.password_hash):
            raise HTTPException(401, 'Invalid email or password')
        token = jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(hours=12)}, secret, algorithm='HS256')
        return {'token': token, 'user': private_user(user)}

    @app.get('/api/auth/me')
    def me(user: Current):
        return private_user(user)

    @app.get('/api/stats')
    def stats(db: DB):
        return {'players': db.scalar(select(func.count(User.id)).where(User.role == 'player')) or 0,
                'tournaments': db.scalar(select(func.count(Tournament.id))) or 0,
                'videos': db.scalar(select(func.count(Video.id)).where(Video.visibility == 'public')) or 0,
                'scouts': db.scalar(select(func.count(User.id)).where(User.role.in_(SCOUT_ROLES))) or 0}

    @app.get('/api/players')
    def players(db: DB, sport: str = Query(default='', max_length=60), search: str = Query(default='', max_length=100), limit: int = Query(default=50, ge=1, le=100)):
        query = select(User).where(User.role == 'player')
        if sport:
            query = query.where(func.lower(User.sport) == sport.lower())
        if search:
            query = query.where(or_(User.name.ilike(f'%{search}%'), User.city.ilike(f'%{search}%'), User.position.ilike(f'%{search}%')))
        return [public_user(p) for p in db.scalars(query.order_by(User.created_at.desc()).limit(limit))]

    @app.patch('/api/players/me')
    def update_profile(data: PlayerUpdate, user: Player, db: DB):
        for key, value in data.model_dump(exclude_unset=True).items():
            if key == 'stats':
                user.stats_json = json.dumps(value or {})
            else:
                setattr(user, key, value)
        db.commit()
        return private_user(user)

    @app.get('/api/players/{player_id}')
    def player_detail(player_id: int, db: DB):
        return player_portfolio(db, get_player(db, player_id))

    @app.post('/api/achievements', status_code=201)
    def add_achievement(data: AchievementInput, user: Player, db: DB):
        item = Achievement(player_id=user.id, title=data.title.strip(), issuer=data.issuer.strip(),
                           year=data.year, evidence_url=str(data.evidence_url) if data.evidence_url else None)
        db.add(item); db.commit(); db.refresh(item)
        return public_achievement(item)

    @app.delete('/api/achievements/{achievement_id}', status_code=204)
    def delete_achievement(achievement_id: int, user: Player, db: DB):
        item = db.get(Achievement, achievement_id)
        if not item or item.player_id != user.id:
            raise HTTPException(404, 'Achievement not found')
        db.delete(item); db.commit()

    @app.post('/api/videos/link', status_code=201)
    def add_link(data: VideoLinkInput, user: Player, db: DB):
        item = Video(player_id=user.id, title=data.title.strip(), kind=data.kind,
                     visibility=data.visibility, url=str(data.url))
        db.add(item); db.commit(); db.refresh(item)
        return public_video(item)

    @app.post('/api/videos/sign-upload')
    def sign_cloud_upload(data: CloudUploadRequest, user: Player):
        config = cloud_config()
        public_id = f'playsphere/u{user.id}/{uuid.uuid4().hex}'
        timestamp = int(time.time())
        delivery_type = 'authenticated' if data.visibility == 'private' else 'upload'
        params = {'public_id': public_id, 'timestamp': timestamp, 'type': delivery_type}
        ticket = jwt.encode({'sub': str(user.id), 'pid': public_id, 'type': delivery_type,
                             'exp': datetime.now(timezone.utc) + timedelta(minutes=20)},
                            secret, algorithm='HS256')
        return {'cloud_name': config['cloud_name'], 'api_key': config['api_key'], **params,
                'signature': cloud_signature(params, config['api_secret']), 'ticket': ticket}

    @app.post('/api/videos/complete-upload', status_code=201)
    def complete_cloud_upload(data: CompleteUploadRequest, user: Player, db: DB):
        config = cloud_config()
        try:
            claims = jwt.decode(data.ticket, secret, algorithms=['HS256'])
        except jwt.PyJWTError:
            raise HTTPException(422, 'Cloud upload ticket expired or invalid. Retry the upload.')
        if claims.get('sub') != str(user.id):
            raise HTTPException(403, 'This upload belongs to another player')
        asset = data.asset
        if (asset.public_id != claims.get('pid') or
                asset.type != claims.get('type') or
                not asset.public_id.startswith(f'playsphere/u{user.id}/')):
            raise HTTPException(422, 'Video does not match the authorized upload')
        expected = cloud_signature({'public_id': asset.public_id, 'version': asset.version}, config['api_secret'])
        if not secrets.compare_digest(expected, asset.signature):
            raise HTTPException(422, 'Cloud video response signature is invalid')
        storage_name = f'cloudinary:{asset.public_id}'
        if db.scalar(select(Video.id).where(Video.storage_name == storage_name)) is not None:
            raise HTTPException(409, 'This uploaded video is already in the portfolio')
        visibility = 'private' if asset.type == 'authenticated' else 'public'
        url = None
        if visibility == 'public':
            # Never trust the browser's secure_url: construct it from signed asset fields.
            safe_public_id = quote(asset.public_id, safe='/')
            url = (f'https://res.cloudinary.com/{config["cloud_name"]}/video/upload/'
                   f'v{asset.version}/{safe_public_id}.{asset.format}')
        video = Video(player_id=user.id, title=data.title.strip(), kind=data.kind,
                      visibility=visibility, storage_name=storage_name,
                      media_type=f'video/{asset.format}', url=url)
        db.add(video)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(409, 'This uploaded video was already saved')
        db.refresh(video)
        return public_video(video)

    @app.post('/api/videos/upload', status_code=201)
    async def upload_video(user: Player, db: DB, file: UploadFile = File(...),
                           title: str = Form(..., min_length=2, max_length=160),
                           kind: Literal['highlight', 'match', 'training'] = Form(...),
                           visibility: Literal['public', 'private'] = Form('public')):
        if os.environ.get('VERCEL'):
            raise HTTPException(503, 'Direct uploads on Vercel use /api/videos/sign-upload and Cloudinary.')
        types = {'video/mp4': '.mp4', 'video/webm': '.webm', 'video/quicktime': '.mov'}
        if file.content_type not in types:
            raise HTTPException(415, 'Only MP4, WebM and MOV videos are supported')
        prefix = await file.read(16)
        valid = (prefix[4:8] == b'ftyp') if file.content_type != 'video/webm' else prefix.startswith(b'\x1a\x45\xdf\xa3')
        if not valid:
            raise HTTPException(415, 'File does not appear to be a valid video')
        storage_name = f'{uuid.uuid4().hex}{types[file.content_type]}'
        path = storage / storage_name
        total = 0
        try:
            with path.open('wb') as out:
                out.write(prefix); total += len(prefix)
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_VIDEO_BYTES:
                        raise HTTPException(413, 'Video exceeds the 25 MB demo upload limit')
                    out.write(chunk)
            item = Video(player_id=user.id, title=title.strip(), kind=kind,
                         visibility=visibility, storage_name=storage_name, media_type=file.content_type)
            db.add(item); db.commit(); db.refresh(item)
            return public_video(item)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

    @app.get('/api/players/me/videos')
    def my_videos(user: Player, db: DB):
        return [public_video(v) for v in db.scalars(select(Video).where(Video.player_id == user.id).order_by(Video.created_at.desc()))]

    @app.get('/api/videos/{video_id}/access')
    def cloud_video_access(video_id: int, user: Current, db: DB):
        video = db.get(Video, video_id)
        if not video or not video.storage_name or not video.storage_name.startswith('cloudinary:'):
            raise HTTPException(404, 'Cloud video not found')
        if video.visibility == 'private' and video.player_id != user.id:
            raise HTTPException(403, 'Private video')
        if video.visibility == 'public':
            return {'url': video.url}
        config = cloud_config()
        configure_cloudinary(config)
        import cloudinary.utils
        public_id = video.storage_name.split(':', 1)[1]
        media_format = video.media_type.split('/')[-1]
        # Owner-only API returns a short-lived media URL, not a permanent public link.
        signed = cloudinary.utils.private_download_url(
            public_id, media_format, resource_type='video', type='authenticated',
            expires_at=int(time.time()) + 300)
        return {'url': signed}

    @app.get('/api/videos/{video_id}/file')
    def video_file(video_id: int, db: DB, authorization: str | None = Header(default=None)):
        video = db.get(Video, video_id)
        if not video or not video.storage_name:
            raise HTTPException(404, 'Video not found')
        if video.visibility == 'private':
            if not authorization or not authorization.lower().startswith('bearer '):
                raise HTTPException(403, 'Private video')
            try:
                payload = jwt.decode(authorization.split(' ', 1)[1], secret, algorithms=['HS256'])
                if int(payload['sub']) != video.player_id:
                    raise HTTPException(403, 'Private video')
            except (jwt.PyJWTError, KeyError, ValueError, IndexError):
                raise HTTPException(403, 'Private video')
        if video.storage_name.startswith('cloudinary:'):
            raise HTTPException(409, 'Cloud videos use /api/videos/{id}/access for signed access')
        # Storage name is server-generated, never a user-supplied path.
        path = storage / video.storage_name
        if not path.is_file():
            raise HTTPException(404, 'File missing')
        return FileResponse(path, media_type=video.media_type, filename=f'playsphere-{video.id}{path.suffix}', content_disposition_type='inline')

    @app.delete('/api/videos/{video_id}', status_code=204)
    def delete_video(video_id: int, user: Player, db: DB):
        video = db.get(Video, video_id)
        if not video or video.player_id != user.id:
            raise HTTPException(404, 'Video not found')
        stored = video.storage_name
        if stored and stored.startswith('cloudinary:'):
            config = cloud_config()
            configure_cloudinary(config)
            import cloudinary.uploader
            result = cloudinary.uploader.destroy(stored.split(':', 1)[1],
                resource_type='video', type='authenticated' if video.visibility == 'private' else 'upload',
                invalidate=True)
            if result.get('result') not in ('ok', 'not found'):
                raise HTTPException(502, 'Video could not be removed from cloud storage. Please retry.')
        db.delete(video); db.commit()
        if stored and not stored.startswith('cloudinary:'):
            (storage / stored).unlink(missing_ok=True)

    @app.get('/api/tournaments')
    def tournaments(db: DB, sport: str = Query(default='', max_length=60),
                    status_filter: Literal['upcoming', 'live', 'recent'] | None = Query(default=None, alias='status'),
                    search: str = Query(default='', max_length=100), limit: int = Query(default=150, ge=1, le=300)):
        today = date.today()
        query = select(Tournament)
        if sport:
            query = query.where(func.lower(Tournament.sport) == sport.lower())
        if search:
            query = query.where(or_(Tournament.title.ilike(f'%{search}%'), Tournament.location.ilike(f'%{search}%')))
        # Filter in SQL BEFORE limiting, otherwise old tournaments can crowd out discoverable events.
        if status_filter == 'upcoming':
            query = query.where(Tournament.start_date > today)
        elif status_filter == 'live':
            query = query.where(Tournament.start_date <= today, Tournament.end_date >= today)
        elif status_filter == 'recent':
            query = query.where(Tournament.end_date < today)

        if status_filter == 'recent':
            query = query.order_by(Tournament.start_date.desc(), Tournament.id.desc())
        else:
            # For the combined timeline, upcoming/live events take priority; historic events are newest-first.
            is_past = Tournament.end_date < today
            query = query.order_by(
                case((is_past, 1), else_=0).asc(),
                case((is_past, Tournament.start_date), else_=None).desc(),
                Tournament.start_date.asc(), Tournament.id.asc()
            )
        return [tournament_json(db, t) for t in db.scalars(query.limit(limit))]

    @app.get('/api/tournaments/me/registrations')
    def my_registrations(user: Player, db: DB):
        ids = db.scalars(select(Registration.tournament_id).where(Registration.player_id == user.id)).all()
        return [tournament_json(db, t) for t in db.scalars(select(Tournament).where(Tournament.id.in_(ids)).order_by(Tournament.start_date))]

    @app.post('/api/tournaments', status_code=201)
    def create_tournament(data: TournamentInput, user: Organizer, db: DB):
        if data.end_date < data.start_date or data.registration_deadline > data.start_date:
            raise HTTPException(422, 'Check tournament dates and registration deadline')
        item = Tournament(owner_id=user.id, **data.model_dump())
        db.add(item); db.commit(); db.refresh(item)
        return tournament_json(db, item)

    @app.get('/api/tournaments/{tournament_id}')
    def tournament_detail(tournament_id: int, db: DB):
        return tournament_json(db, get_event(db, tournament_id))

    @app.post('/api/tournaments/{tournament_id}/register', status_code=201)
    def register_tournament(tournament_id: int, user: Player, db: DB):
        # Lock event row on PostgreSQL to avoid oversubscribing the final spot.
        item = db.scalar(select(Tournament).where(Tournament.id == tournament_id).with_for_update())
        if item is None:
            raise HTTPException(404, 'Tournament not found')
        if db.scalar(select(Registration).where(Registration.tournament_id == item.id, Registration.player_id == user.id)):
            raise HTTPException(409, 'Already registered')
        if not tournament_json(db, item)['registration_open']:
            raise HTTPException(400, 'Registration is closed or tournament is full')
        db.add(Registration(tournament_id=item.id, player_id=user.id))
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(409, 'Registration could not be completed')
        return {'message': 'Registration confirmed', 'tournament_id': item.id}

    @app.delete('/api/tournaments/{tournament_id}/register', status_code=204)
    def withdraw(tournament_id: int, user: Player, db: DB):
        item = db.scalar(select(Registration).where(Registration.tournament_id == tournament_id, Registration.player_id == user.id))
        if not item:
            raise HTTPException(404, 'Registration not found')
        db.delete(item); db.commit()

    @app.get('/api/tournaments/{tournament_id}/registrations')
    def registrations(tournament_id: int, user: Current, db: DB):
        item = get_event(db, tournament_id)
        if item.owner_id != user.id:
            raise HTTPException(403, 'Only the organizer can view attendees')
        player_ids = db.scalars(select(Registration.player_id).where(Registration.tournament_id == item.id)).all()
        return [public_user(p) for p in db.scalars(select(User).where(User.id.in_(player_ids)))]

    def evaluation_json(e: Evaluation, db: DB):
        player = db.get(User, e.player_id)
        return {'id': e.id, 'player_id': e.player_id, 'player_name': player.name if player else '',
                'technique': e.technique, 'teamwork': e.teamwork,
                'consistency': e.consistency, 'potential': e.potential,
                'score': round((e.technique + e.teamwork + e.consistency + e.potential) / 4, 2),
                'notes': e.notes, 'updated_at': e.updated_at.isoformat()}

    @app.get('/api/scouting/my-evaluations')
    def my_evaluations(user: Recruiter, db: DB):
        return [evaluation_json(e, db) for e in db.scalars(select(Evaluation).where(Evaluation.scout_id == user.id))]

    @app.post('/api/scouting/{player_id}/evaluate')
    def evaluate(player_id: int, data: EvaluationInput, user: Recruiter, db: DB):
        get_player(db, player_id)
        item = db.scalar(select(Evaluation).where(Evaluation.player_id == player_id, Evaluation.scout_id == user.id))
        if not item:
            item = Evaluation(player_id=player_id, scout_id=user.id, **data.model_dump())
            db.add(item)
        else:
            for field, value in data.model_dump().items():
                setattr(item, field, value)
            item.updated_at = datetime.now(timezone.utc)
        db.commit(); db.refresh(item)
        return evaluation_json(item, db)

    @app.get('/api/scouting/shortlist')
    def my_shortlist(user: Recruiter, db: DB):
        ids = db.scalars(select(Shortlist.player_id).where(Shortlist.scout_id == user.id)).all()
        return [public_user(p) for p in db.scalars(select(User).where(User.id.in_(ids)))]

    @app.post('/api/scouting/{player_id}/shortlist')
    def shortlist(player_id: int, user: Recruiter, db: DB, response: Response):
        get_player(db, player_id)
        existing = db.scalar(select(Shortlist).where(Shortlist.player_id == player_id, Shortlist.scout_id == user.id))
        if existing:
            return {'message': 'Already shortlisted', 'player_id': player_id}
        db.add(Shortlist(player_id=player_id, scout_id=user.id)); db.commit()
        response.status_code = 201
        return {'message': 'Added to shortlist', 'player_id': player_id}

    @app.delete('/api/scouting/{player_id}/shortlist', status_code=204)
    def unshortlist(player_id: int, user: Recruiter, db: DB):
        existing = db.scalar(select(Shortlist).where(Shortlist.player_id == player_id, Shortlist.scout_id == user.id))
        if not existing:
            raise HTTPException(404, 'Player is not shortlisted')
        db.delete(existing); db.commit()

    web_dir = ROOT / 'web'
    if web_dir.is_dir():
        app.mount('/assets', StaticFiles(directory=web_dir), name='assets')

        @app.get('/', include_in_schema=False)
        def landing():
            return FileResponse(web_dir / 'index.html')

    return app


app = create_app()
