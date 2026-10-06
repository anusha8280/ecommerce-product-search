from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

Base = declarative_base()


def get_engine():
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={"connect_timeout": 2}
        )
        # Test connection
        with engine.connect() as conn:
            pass
        return engine
    except Exception as e:
        print(f"[Info] PostgreSQL not available on {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}. Falling back to SQLite local database.")
        sqlite_url = "sqlite:///./ecommerce_dev.db"
        return create_engine(sqlite_url, connect_args={"check_same_thread": False})


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("[Database] Schema initialized successfully.")
    except Exception as e:
        print(f"[Warning] Error initializing database schema: {e}")
