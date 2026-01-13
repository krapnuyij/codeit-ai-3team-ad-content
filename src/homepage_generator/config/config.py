import os
from pydantic import BaseModel, Field, model_validator
import re
import yaml
from pydantic_settings import SettingsConfigDict, BaseSettings
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from pathlib import Path

class StoreConfig(BaseModel):
    store_name: str
    store_type: str
    budget: int # 만원단위
    period: int # 일
    advertising_goal: str
    target_customer: str
    store_strength: str
    advertising_media: str
    location: str
    phone_number: str

class OpenAIConfig(BaseModel):
    chat_model: str
    api_key: str = None

class PathConfig(BaseModel):
    generated_path: str

class AgentConfig(BaseModel):
    name: str
    role: str
    system_message: str
    user_message: str = ""

class GroupChatConfig(BaseModel):
    """GroupChat 설정"""
    max_turns: int = 10
    select_speaker_auto_mode: str = "auto"

class PromptsConfig(BaseModel):
    user_prompt: str
    bs_agents: Dict[str, AgentConfig]
    agents: Dict[str, AgentConfig]


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    root_marker: str =".env"
    project_root: Optional[Path] = None

    store_config: StoreConfig
    openai_config: OpenAIConfig
    paths: PathConfig

    OPENAI_API_KEY: Optional[str] = Field(None, alias="OPENAI_API_KEY")

    @model_validator(mode='after')
    def resolve_logic(self) -> 'Settings':
        """프로젝트 루트 탐색, 경로 변환 및 API 키 동기화"""
        # 1. 프로젝트 루트 탐색
        if self.project_root is None:
            current = Path(__file__).resolve()
            for parent in [current, *current.parents]:
                if (parent / self.root_marker).exists():
                    self.project_root = parent
                    break
            if not self.project_root:
                # 폴백: 현재 작업 디렉토리
                self.project_root = Path.cwd()

        # 2. 모든 경로를 프로젝트 루트 기준 절대 경로로 변환
        self.paths.generated_path = str(self.project_root / self.paths.generated_path)

        # 3. 환경 변수와 내부 객체 API 키 동기화 (YAML 치환 실패 시 보충)
        if not self.openai_config.api_key or self.openai_config.api_key == "":
            self.openai_config.api_key = self.OPENAI_API_KEY
        # if not self.huggingface.token or self.huggingface.token == "":
        #     self.huggingface.token = self.HUGGINGFACE_TOKEN

        return self

    @classmethod
    def load(cls, yaml_path: str):
        """YAML 파일 로드 및 환경 변수(${VAR}) 치환 실행"""
        # .env 파일 위치를 명시적으로 지정하여 로드
        # src_new/config.py 기준 상위 디렉토리에서 .env 탐색
        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=env_path)

        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"지정한 YAML 경로를 찾을 수 없습니다: {yaml_path}")

        with open(yaml_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 정규식을 이용해 ${VAR_NAME} 패턴을 실제 환경 변수로 치환
        def replace_env_var(match):
            var_name = match.group(1)
            # HUGGINGFACE_HUG_TOKEN 등 구 버전 변수명 대응 폴백 로직
            val = os.getenv(var_name)
            if val is None and "HUGGINGFACE" in var_name:
                val = os.getenv("HUGGINGFACE_TOKEN")
            return val if val is not None else ""

        content = re.sub(r'\$\{(\w+)\}', replace_env_var, content)
        data = yaml.safe_load(content)

        # Pydantic 인스턴스 생성 및 검증
        return cls(**data)

    @classmethod
    def load_prompts(cls, prompts_path: str) -> PromptsConfig:
        """prompts.yaml 로드"""
        with open(prompts_path, 'r', encoding='utf-8') as f:
            content = f.read()
        data = yaml.safe_load(content)
        return PromptsConfig(**data)

if __name__ == "__main__":
    # 실행 시 config_new.yaml의 경로를 정확히 지정하세요.
    # 예: src_new 폴더 내에서 실행 시 ../config/config_new.yaml
    try:
        current_file = Path(__file__).resolve()
        # 프로젝트 구조에 맞춘 기본 경로 설정
        default_yaml_path = current_file.parent.parent / "config" / "config.yaml"
        print(default_yaml_path)
        settings = Settings.load(str(default_yaml_path))
        prompts_settings = Settings.load_prompts(str(current_file.parent.parent / "config" / "prompts.yaml"))
        print(type(settings))
        print(type(prompts_settings))

        print("✅ Config 로드 완료")
        print(f"루트 경로: {settings.project_root}")
        print(f"OpenAI 모델: {settings.openai_config.chat_model}")
        print(f"api_key: {settings.OPENAI_API_KEY[:5]}***")
        # print(prompts_settings.user_prompt)

    except Exception as e:
        print(f"❌ 에러 발생: {e}")