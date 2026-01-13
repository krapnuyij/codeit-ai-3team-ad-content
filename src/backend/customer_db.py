import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime
from dotenv import load_dotenv

load_dotenv()

# Base 클래스 생성
Base = declarative_base()

# Customer 모델 정의
class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)

    # 매장 정보
    store_name = Column(String(255), nullable=False)
    store_type = Column(String(100), nullable=False)
    budget = Column(String(50), nullable=False)
    period = Column(String(50), nullable=False)

    # 광고 상세 정보
    advertising_goal = Column(Text, nullable=False)
    target_customer = Column(Text, nullable=False)
    advertising_media = Column(Text, nullable=False)
    store_strength = Column(Text, nullable=False)

    # 대표자 정보
    contact_name = Column(String(100), nullable=False)
    company_name = Column(String(255), nullable=True)  # 선택사항
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)

    # 개인정보 동의
    agree = Column(String(10), nullable=False)

    # 생성 시간
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Customer(id={self.id}, store_name='{self.store_name}', email='{self.email}')>"


# 데이터베이스 URL 설정 (PostgreSQL 사용)
# Docker에서는 docker-compose.yaml의 DATABASE_URL 환경변수 사용
# 로컬 개발 시 기본값: postgresql+asyncpg://postgres:postgres@localhost:5432/saas_ad
DATABASE_URL = os.getenv("DATABASE_URL")

# asyncpg 드라이버를 사용하도록 URL 변환
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 비동기 엔진 생성
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # SQL 쿼리 로깅
    future=True,
    pool_pre_ping=True  # 연결 상태 확인
)

# 비동기 세션 팩토리
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """데이터베이스 테이블 초기화"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 데이터베이스 테이블 생성 완료")


async def get_db():
    """데이터베이스 세션 의존성 주입용"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def save_customer(customer_data: dict):
    """고객 데이터를 데이터베이스에 저장"""
    async with async_session_maker() as session:
        try:
            customer = Customer(**customer_data)
            session.add(customer)
            await session.commit()
            await session.refresh(customer)
            print(f"✅ 고객 데이터 저장 완료: {customer.id}")
            return customer
        except Exception as e:
            await session.rollback()
            print(f"❌ 고객 데이터 저장 실패: {e}")
            raise


async def get_customer_by_id(customer_id: int):
    """고객 ID로 고객 데이터 조회"""
    async with async_session_maker() as session:
        try:
            customer = await session.get(Customer, customer_id)
            if not customer:
                raise ValueError(f"고객 ID {customer_id}를 찾을 수 없습니다.")
            return customer
        except Exception as e:
            print(f"❌ 고객 데이터 조회 실패: {e}")
            raise
