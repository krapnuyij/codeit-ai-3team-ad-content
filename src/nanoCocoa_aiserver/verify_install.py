"""
환경 설치 검증 스크립트
conda activate py311_ad 후 python verify_install.py 실행
"""

import sys
import importlib.util

def check_package(package_name, import_name=None):
    """패키지 설치 확인"""
    if import_name is None:
        import_name = package_name

    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✅ {package_name:25s} {version}")
        return True
    except ImportError:
        print(f"❌ {package_name:25s} NOT INSTALLED")
        return False

print("=" * 60)
print("환경 설치 검증")
print("=" * 60)

# Python 버전
print(f"\n🐍 Python: {sys.version.split()[0]}")
print(f"   경로: {sys.executable}")

print("\n📦 핵심 패키지:")
packages = [
    ("PyTorch", "torch"),
    ("TorchVision", "torchvision"),
    ("Transformers", "transformers"),
    ("Diffusers", "diffusers"),
    ("FastAPI", "fastapi"),
    ("Uvicorn", "uvicorn"),
    ("Gradio", "gradio"),
    ("Pydantic", "pydantic"),
    ("NumPy", "numpy"),
    ("Pandas", "pandas"),
    ("Pillow", "PIL"),
    ("OpenCV", "cv2"),
    ("Matplotlib", "matplotlib"),
    ("SciPy", "scipy"),
    ("HTTPx", "httpx"),
    ("MCP", "mcp"),
]

success_count = 0
for pkg_name, import_name in packages:
    if check_package(pkg_name, import_name):
        success_count += 1

print(f"\n📊 결과: {success_count}/{len(packages)} 패키지 설치됨")

# PyTorch 상세 정보
print("\n🔥 PyTorch 상세 정보:")
try:
    import torch
    print(f"   버전: {torch.__version__}")
    print(f"   CUDA 사용 가능: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA 버전: {torch.version.cuda}")
        print(f"   GPU 장치: {torch.cuda.get_device_name(0)}")
        print(f"   GPU 개수: {torch.cuda.device_count()}")
    else:
        print(f"   실행 모드: CPU")
        # MPS (Apple Silicon) 확인
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            print(f"   MPS (Apple Silicon) 사용 가능: True")
except Exception as e:
    print(f"   ❌ 에러: {e}")

print("\n" + "=" * 60)
if success_count == len(packages):
    print("✅ 모든 패키지가 정상적으로 설치되었습니다!")
elif success_count >= len(packages) * 0.8:
    print("⚠️  대부분의 패키지가 설치되었습니다. 일부 누락된 패키지를 확인하세요.")
else:
    print("❌ 많은 패키지가 설치되지 않았습니다. requirements.txt를 다시 확인하세요.")
print("=" * 60)
