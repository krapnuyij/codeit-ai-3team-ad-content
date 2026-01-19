from typing import TypedDict, Annotated, List, Dict, Any, Optional
from operator import add
from pydantic import BaseModel, Field, ConfigDict


class BSParser(BaseModel):
    sns: List[str]
    blog: List[str]
    design: List[str]
    dev: List[str]

class StoreConcept(BaseModel):
    """매장 컨셉"""
    model_config = ConfigDict(extra='forbid')
    core_message: str = Field(default='')
    key_visuals: List[str] = Field(default_factory=list)
    tone_and_manner: str = Field(default='')
    target_emotions: List[str]= Field(default_factory=list)

class Strategy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pages: List[str]= Field(default_factory=list)
    features: List[str]= Field(default_factory=list)
    marketing_focus: str = Field(default='')
    key_message: str = Field(default='')

class MarketingStrategy(BaseModel):
    model_config = ConfigDict(extra='forbid')

    strategy: Strategy = Field(default_factory=Strategy)

class ColorPalette(BaseModel):
    model_config = ConfigDict(extra='forbid')

    primary: str = Field(default='')
    accent: str = Field(default='')
    text: str = Field(default='')

class Fonts(BaseModel):
    model_config = ConfigDict(extra='forbid')

    heading: str = Field(default='')
    body: str = Field(default='')

class Header(BaseModel):
    model_config = ConfigDict(extra='forbid')

    layout: str = Field(default='')
    elements: List[str]= Field(default_factory=list)
    sticky: bool = False

class Footer(BaseModel):
    model_config = ConfigDict(extra='forbid')

    layout: str = Field(default='')
    elements: List[str]= Field(default_factory=list)

class DesignSystem(BaseModel):
    model_config = ConfigDict(extra='forbid')

    color_palette: ColorPalette = Field(default_factory=ColorPalette)
    fonts: Fonts = Field(default_factory=Fonts)
    style: str = Field(default='')
    header: Header = Field(default_factory=Header)
    footer: Footer = Field(default_factory=Footer)

class ImageBox(BaseModel):
    """이미지 박스 요소"""
    model_config = ConfigDict(extra='forbid')

    type: str = Field(default='', description="이미지 타입: hero_image, product_card, gallery_item 등")
    alt_text: str = Field(default='', description="이미지 대체 텍스트")
    description: str = Field(default='', description="AI 이미지 생성을 위한 상세 설명")
    aspect_ratio: str = Field(default='', description="이미지 비율: 16:9, 1:1, 4:3 등")

class ButtonElement(BaseModel):
    """버튼 요소"""
    model_config = ConfigDict(extra='forbid')

    label: str = Field(default='', description="버튼에 표시될 텍스트")
    type: str = Field(default='', description="버튼 스타일: primary, secondary, ghost 등")
    action: str = Field(default='', description="버튼 클릭 시 동작: navigate_to_menu, open_reservation_form 등")

class TextBlock(BaseModel):
    """텍스트 블록"""
    model_config = ConfigDict(extra='forbid')

    type: str = Field(default='', description="텍스트 타입: headline, subheading, body, tagline 등")
    content: str = Field(default='', description="실제 텍스트 내용")
    emphasis: str = Field(default='', description="강조 스타일: bold, italic, highlight 또는 빈 문자열")

class SectionContent(BaseModel):
    """섹션별 콘텐츠"""
    model_config = ConfigDict(extra='forbid')

    section_name: str = Field(default='', description="어느 섹션의 콘텐츠인지 (PageVariations의 sections와 매칭)")
    text_blocks: List[TextBlock] = Field(default_factory=list, description="섹션 내 텍스트 요소들")
    images: List[ImageBox] = Field(default_factory=list, description="섹션 내 이미지 요소들")
    buttons: List[ButtonElement] = Field(default_factory=list, description="섹션 내 버튼 요소들")

class PageContent(BaseModel):
    """페이지 콘텐츠 (섹션 기반만)"""
    model_config = ConfigDict(extra='forbid')

    sections: List[SectionContent] = Field(default_factory=list, description="섹션별 상세 콘텐츠")

class PageVariations(BaseModel):
    model_config = ConfigDict(extra='forbid')

    page_name: str = Field(default='')  # ← 페이지 이름 필드 추가
    layout: str = Field(default='')
    sections: List[str]= Field(default_factory=list)
    required_features: List[str] = Field(default_factory=list)  # ← 필요한 기능 목록
    content: Optional[PageContent] = None

class HomePageDesign(BaseModel):
    model_config = ConfigDict(extra='forbid')

    design_system: DesignSystem = Field(default_factory=DesignSystem)
    page_variations: List[PageVariations]= Field(default_factory=list)  # ← List로 변경


class DOMContract(BaseModel):
    """
    DOM 구조 계약서

    ⚠️ DEPRECATED: CSS 생성 방식에서 Tailwind CDN 방식으로 전환하면서 더 이상 사용되지 않습니다.
    이 클래스는 하위 호환성을 위해 유지되지만, 새로운 코드에서는 사용하지 마세요.
    """
    model_config = ConfigDict(extra='forbid')

    # 기본 래퍼 구조
    page_wrapper: str = Field(
        default="div.page[data-page='{page_name}']",
        description="페이지 최상위 래퍼"
    )
    section_wrapper: str = Field(
        default="section.section.section--{section_name}[data-section='{section_name}']",
        description="섹션 래퍼"
    )

    # 텍스트 요소 매핑
    text_mappings: Dict[str, str] = Field(
        default_factory=lambda: {
            "headline": "h1.text.text--headline",
            "subheading": "h2.text.text--subheading",
            "body": "p.text.text--body",
            "tagline": "p.text.text--tagline"
        },
        description="텍스트 타입별 HTML 태그/클래스"
    )

    # 이미지 템플릿
    image_template: str = Field(
        default="figure.image.image--{type} > img[alt='{alt_text}'][data-aspect='{aspect_ratio}'][data-ai-prompt='{description}']",
        description="이미지 요소 구조"
    )

    # 버튼 템플릿
    button_template: str = Field(
        default="button.btn.btn--{type}[data-action='{action}']",
        description="버튼 요소 구조"
    )

    # CSS 변수 매핑
    css_variables: Dict[str, str] = Field(
        default_factory=lambda: {
            "primary": "--color-primary",
            "accent": "--color-accent",
            "text": "--color-text",
            "heading": "--font-heading",
            "body": "--font-body"
        },
        description="디자인 시스템 → CSS 변수 매핑"
    )

    # 추가 규칙
    bem_convention: bool = Field(default=True, description="BEM 네이밍 사용 여부")
    semantic_html: bool = Field(default=True, description="시맨틱 HTML 우선 사용")
    accessibility_attrs: bool = Field(default=True, description="ARIA 속성 포함 여부")


class ImplementationSpec(BaseModel):
    """구현 명세"""
    frontend_requirements: List[str] = Field(default_factory=list)
    style_requirements: List[str] = []
    asset_requirements: List[str] = []
    technical_constraints: List[str] = []


class GeneratedCode(BaseModel):
    """생성된 코드"""
    html: str = ""
    css: str = ""
    assets: Dict[str, str] = {}


class StoreInfo(BaseModel):
    store_name: str
    store_type: str
    budget: int
    period: int
    advertising_goal: str
    target_customer: str
    store_strength: str
    advertising_media: str
    location: str
    phone_number: str

class AdState(TypedDict):
    """LangGraph 상태 정의"""

    # 입력 정보 (config에서 로드)

    store_info: StoreInfo
    # 브레인 스토밍 input
    brainstorm_user_input: str
    # 브레인 스토밍 결과
    brainstorm: str

    # 각 노드의 출력
    bs_parser: BSParser
    store_concept: StoreConcept
    marketing_strategy: MarketingStrategy
    homepage_design: HomePageDesign
    content_design: HomePageDesign

    # 통합 및 검증 결과
    consistency_report: str
    final_strategy: str

    # DOM Contract (DEPRECATED: Tailwind 방식 사용으로 불필요)
    dom_contract: DOMContract

    # 구현 명세 및 코드
    implementation_spec: ImplementationSpec
    header_html: str  # 공통 헤더 HTML
    footer_html: str  # 공통 푸터 HTML
    html_codes: Dict[str, str]  # 페이지별 main 콘텐츠 (Tailwind 포함)
    css_code: str  # DEPRECATED: Tailwind CDN 사용으로 불필요
    generated_code: GeneratedCode  # 최종 통합된 코드

    # Agent 토론 히스토리 (각 GroupChat의 대화 내용 저장)
    agent_discussions: Annotated[List[Dict[str, Any]], add]

    # 최종 패키지 경로
    output_path: str

    # 에러 및 로그
    errors: Annotated[List[str], add]
    logs: Annotated[List[str], add]
