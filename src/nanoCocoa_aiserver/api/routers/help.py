"""
help.py
Help 라우터 집합 (통합 라우터)
"""

from fastapi import APIRouter
from .help_overview import router as overview_router
from .help_parameters import router as parameters_router
from .help_examples import router as examples_router

router = APIRouter()

# 개별 라우터 통합
router.include_router(overview_router, tags=["Help"])
router.include_router(parameters_router, tags=["Help"])
router.include_router(examples_router, tags=["Help"])
