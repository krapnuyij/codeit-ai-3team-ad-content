"""
PostgreSQL 데이터베이스 클라이언트
homepage_generator가 customer_db에서 데이터를 가져옴
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Text, DateTime, select
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()


class Customer(Base):
    """Customer 테이블 모델 (backend/customer_db.py와 동일)"""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    store_name = Column(String(255), nullable=False)
    store_type = Column(String(100), nullable=False)
    budget = Column(String(50), nullable=False)
    period = Column(String(50), nullable=False)
    advertising_goal = Column(Text, nullable=False)
    target_customer = Column(Text, nullable=False)
    advertising_media = Column(Text, nullable=False)
    store_strength = Column(Text, nullable=False)
    contact_name = Column(String(100), nullable=False)
    company_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    agree = Column(String(10), nullable=False)
    created_at = Column(DateTime)


# 데이터베이스 URL 설정
DATABASE_URL = os.getenv("DATABASE_URL")

# asyncpg 드라이버를 사용하도록 URL 변환
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 비동기 엔진 생성
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # SQL 로깅 비활성화 (필요시 True로 변경)
    future=True,
    pool_pre_ping=True
)

# 비동기 세션 팩토리
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_customer_by_id(customer_id: int) -> dict:
    """
    customer_id로 고객 데이터 조회

    Args:
        customer_id: 고객 ID

    Returns:
        StoreConfig 형식의 dict

    Raises:
        ValueError: 고객을 찾을 수 없을 때
    """
    async with async_session_maker() as session:
        result = await session.get(Customer, customer_id)

        if not result:
            raise ValueError(f"Customer with ID {customer_id} not found in database")

        # StoreConfig 형식으로 변환
        return {
            "store_name": result.store_name,
            "store_type": result.store_type,
            "budget": int(result.budget),
            "period": int(result.period),
            "advertising_goal": result.advertising_goal,
            "target_customer": result.target_customer,
            "advertising_media": result.advertising_media,
            "store_strength": result.store_strength,
            "location": result.company_name or "정보 없음",
            "phone_number": result.phone
        }


async def get_latest_customer() -> dict:
    """
    가장 최근에 등록된 고객 데이터 조회

    Returns:
        StoreConfig 형식의 dict

    Raises:
        ValueError: 고객 데이터가 없을 때
    """
    async with async_session_maker() as session:
        stmt = select(Customer).order_by(Customer.created_at.desc()).limit(1)
        result = await session.execute(stmt)
        customer = result.scalar_one_or_none()

        if not customer:
            raise ValueError("No customer data found in database")

        # StoreConfig 형식으로 변환
        return {
            "store_name": customer.store_name,
            "store_type": customer.store_type,
            "budget": int(customer.budget),
            "period": int(customer.period),
            "advertising_goal": customer.advertising_goal,
            "target_customer": customer.target_customer,
            "advertising_media": customer.advertising_media,
            "store_strength": customer.store_strength,
            "location": customer.company_name or "정보 없음",
            "phone_number": customer.phone
        }
