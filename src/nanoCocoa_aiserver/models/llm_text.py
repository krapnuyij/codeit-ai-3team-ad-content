import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents
sys.path.insert(0, str(project_root))

import io
import re
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Union, Dict

from PIL import Image
from playwright.async_api import async_playwright
from openai import OpenAI
from helper_dev_utils import get_auto_logger

from .qwen_analyzer import QwenAnalyzer

logger = get_auto_logger()


class LLMTexttoHTML:
    """
    QwenAnalyzer와 OpenAI LLM을 사용한 HTML 광고 생성기

    이미지와 광고 문구를 입력받아 LLM이 HTML 광고 템플릿을 생성하고,
    Playwright로 실제 이미지로 렌더링합니다.

    특징:
    - QwenAnalyzer로 이미지 상세 분석 (공간, 색감, 조명, 분위기)
    - 텍스트 기반 프롬프트로 토큰 효율 최적화
    - gpt-5-mini 모델 지원 (128K 출력 토큰)
    - 비동기 Playwright로 HTML 렌더링
    - 완전한 HTML 생성 보장 (finish_reason 검증)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5-mini",
        temperature: float = 1.0,
        max_completion_tokens: int = 16000,
    ):
        """
        LLMTexttoHTML 초기화

        Args:
            api_key: OpenAI API 키
            model: 사용할 모델 (기본값: gpt-5-mini, 128K 출력 지원)
            temperature: 생성 다양성 (0.0-2.0, 기본값: 0.7)
            max_completion_tokens: 최대 출력 토큰 (기본값: 16000)
        """
        self.openai_client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens

        logger.info(
            f"LLMTexttoHTML 초기화: model={model}, max_tokens={max_completion_tokens}"
        )

    def generate_html(
        self,
        image_path: str,
        ad_text: str,
        style_hint: Optional[str] = None,
    ) -> str:
        """
        이미지와 광고 문구를 분석하여 HTML 광고 템플릿 생성

        Args:
            image_path: 분석할 이미지 경로
            ad_text: 광고 문구 (예: "특가세일 2500원")
            style_hint: 스타일 힌트 (예: "modern", "elegant", "energetic")

        Returns:
            생성된 HTML 문자열
        """
        logger.info(f"HTML 생성 시작: image={image_path}, text={ad_text}")

        # QwenAnalyzer로 이미지 상세 분석
        logger.info("QwenAnalyzer로 이미지 분석 중...")
        qwen = QwenAnalyzer()
        image = Image.open(image_path)
        analysis = qwen.analyze_image_details(image, auto_unload=True)

        # 프롬프트 구성
        system_prompt = f"""당신은 전문 HTML 광고 디자이너입니다.
이미지를 분석하여 이미지와 어울리는 완전한 광고 HTML을 생성합니다.

[핵심 요구사항]
- 반드시 완전한 HTML 문서를 생성 (<!DOCTYPE html>부터 </html>까지)
- 인라인 CSS 스타일 포함
- 반응형 디자인 (width: 1024px, height:1024px)
- 제공된 jpg Base64 이미지는 html 제작을 위한 분석용으로 사용
- {image_path} 배경 이미지로 사용
- 이미지는 비율유지 full cover
- 텍스트 오버레이로 광고 문구 배치
- 깔끔한 타이포그래피와 적절한 여백
- 그라디언트나 그림자로 가독성 향상
- JavaScript 사용하지 않음

[중요]
- HTML을 끝까지 완성해야 합니다
- </html> 태그로 반드시 종료
- 중간에 생략하지 말 것"""

        user_prompt = f"""다음 이미지 분석 정보를 바탕으로 광고 문구가 포함된 완전한 HTML을 생성해주세요:

[이미지 분석 정보]
- 전체 장면: {analysis['overall']}
- 색감/재질: {analysis['color_material']}
- 조명/분위기: {analysis['lighting_mood']}
- 공간 배치: {analysis['spatial']}
- 이미지 크기: {analysis['image_size'][0]}x{analysis['image_size'][1]}px

[광고 정보]
- 광고 문구: "{ad_text}"
{f'- 스타일 힌트: {style_hint}' if style_hint else ''}

[요구사항]
- 위 이미지 분석 정보를 참고하여 조화로운 디자인 구성
- 광고 문구 레이어 투명
- 광고 문구를 눈에 띄게 배치
- 텍스트 크기와 색상은 배경과 대비되도록 설정
- {image_path} 백그라운드로 사용
- 백그라운드 크기 고정 width: 1024px, height:1024px

[출력 형식]
- 완성된 HTML 코드만 출력 (설명 없이)
- 반드시 <!DOCTYPE html>부터 </html>까지 전체 코드 출력
- 코드 블록 마크다운(```) 사용하지 말고 순수 HTML만 출력"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # OpenAI API 호출
        logger.debug(
            f"OpenAI API 호출 시작: model={self.model}, max_tokens={self.max_completion_tokens}"
        )
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_completion_tokens=self.max_completion_tokens,
        )

        html_output = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason

        logger.debug(
            f"API 응답 완료: finish_reason={finish_reason}, 토큰 사용={response.usage.total_tokens}"
        )

        if not html_output:
            logger.error("OpenAI API가 빈 응답을 반환했습니다")
            raise ValueError("HTML 생성 실패: 빈 응답")

        # finish_reason이 length인 경우 경고
        if finish_reason == "length":
            logger.warning("HTML이 max_completion_tokens 제한으로 잘렸을 수 있습니다")
            logger.warning(
                f"현재 max_completion_tokens={self.max_completion_tokens}, 사용된 토큰={response.usage.completion_tokens}"
            )

        logger.info(
            f"HTML 생성 완료: {len(html_output)} 문자, finish_reason={finish_reason}"
        )

        # HTML 코드 블록 제거 (```html ... ``` 형식인 경우)
        if "```" in html_output:
            parts = html_output.split("```")
            for i, part in enumerate(parts):
                if part.strip().startswith("html"):
                    html_output = part[4:].strip()
                    break
                elif i % 2 == 1:  # 홀수 인덱스는 코드 블록 내부
                    html_output = part.strip()
                    break

        # HTML 유효성 간단 체크
        html_lower = html_output.lower()
        if not html_lower.startswith("<!doctype html") and not html_lower.startswith(
            "<html"
        ):
            logger.warning("HTML이 올바른 형식으로 시작하지 않습니다")

        if "</html>" not in html_lower:
            logger.warning("HTML이 </html> 태그로 종료되지 않았습니다 (잘렸을 가능성)")

        return html_output

    def generate_prompt_html(
        self,
        image_path: str,
        ad_text: str,
        text_prompt: Optional[str] = None,
        composition_prompt: Optional[str] = None,
    ) -> str:
        """
        이미지와 광고 문구를 분석하여 HTML 광고 템플릿 생성

        Args:
            image_path: 분석할 이미지 경로
            ad_text: 광고 문구 (예: "특가세일 2500원")
            text_prompt: 텍스트 프롬프트 (선택)
            composition_prompt: 구성 프롬프트 (선택)

        Returns:
            생성된 HTML 문자열
        """
        logger.info(f"HTML 생성 시작: image={image_path}, text={ad_text}")

        # QwenAnalyzer로 이미지 상세 분석
        logger.info("QwenAnalyzer로 이미지 분석 중...")
        qwen = QwenAnalyzer()
        image = Image.open(image_path)
        analysis = qwen.analyze_image_details(image, auto_unload=True)

        # 프롬프트 구성
        system_prompt = f"""당신은 전문 HTML 광고 디자이너입니다.
이미지 분석 정보를 바탕으로 이미지와 어울리는 완전한 광고 HTML을 생성합니다.

[핵심 요구사항]
- 반드시 완전한 HTML 문서를 생성 (<!DOCTYPE html>부터 </html>까지)
- 인라인 CSS 스타일 포함
- 반응형 디자인 (width: 1024px, height:1024px)
- {image_path} 배경 이미지로 사용
- 이미지는 비율유지 full cover
- 텍스트 오버레이로 광고 문구 배치
- 깔끔한 타이포그래피와 적절한 여백
- 그라디언트나 그림자로 가독성 향상
- JavaScript 사용하지 않음

[중요]
- HTML을 끝까지 완성해야 합니다
- </html> 태그로 반드시 종료
- 중간에 생략하지 말 것"""

        user_prompt = f"""다음 이미지 분석 정보를 바탕으로 광고 문구가 포함된 완전한 HTML을 생성해주세요:

[이미지 분석 정보]
- 전체 장면: {analysis['overall']}
- 색감/재질: {analysis['color_material']}
- 조명/분위기: {analysis['lighting_mood']}
- 공간 배치: {analysis['spatial']}
- 이미지 크기: {analysis['image_size'][0]}x{analysis['image_size'][1]}px

[광고 정보]
- 광고 문구: "{ad_text}"
{f'- 텍스트 프롬프트: {text_prompt}' if text_prompt else ''}
{f'- 구성 프롬프트: {composition_prompt}' if composition_prompt else ''}

[요구사항]
- 위 이미지 분석 정보를 참고하여 조화로운 디자인 구성
- 광고 문구 레이어 투명
- 광고 문구를 눈에 띄게 배치
- 텍스트 크기와 색상은 배경과 대비되도록 설정
- {image_path} 백그라운드로 사용
- 백그라운드 크기 고정 width: 1024px, height:1024px

[출력 형식]
- 완성된 HTML 코드만 출력 (설명 없이)
- 반드시 <!DOCTYPE html>부터 </html>까지 전체 코드 출력
- 코드 블록 마크다운(```) 사용하지 말고 순수 HTML만 출력"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # OpenAI API 호출
        logger.debug(
            f"OpenAI API 호출 시작: model={self.model}, max_tokens={self.max_completion_tokens}"
        )
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_completion_tokens=self.max_completion_tokens,
        )

        html_output = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason

        logger.debug(
            f"API 응답 완료: finish_reason={finish_reason}, 토큰 사용={response.usage.total_tokens}"
        )

        if not html_output:
            logger.error("OpenAI API가 빈 응답을 반환했습니다")
            raise ValueError("HTML 생성 실패: 빈 응답")

        # finish_reason이 length인 경우 경고
        if finish_reason == "length":
            logger.warning("HTML이 max_completion_tokens 제한으로 잘렸을 수 있습니다")
            logger.warning(
                f"현재 max_completion_tokens={self.max_completion_tokens}, 사용된 토큰={response.usage.completion_tokens}"
            )

        logger.info(
            f"HTML 생성 완료: {len(html_output)} 문자, finish_reason={finish_reason}"
        )

        # HTML 코드 블록 제거 (```html ... ``` 형식인 경우)
        if "```" in html_output:
            parts = html_output.split("```")
            for i, part in enumerate(parts):
                if part.strip().startswith("html"):
                    html_output = part[4:].strip()
                    break
                elif i % 2 == 1:  # 홀수 인덱스는 코드 블록 내부
                    html_output = part.strip()
                    break

        # HTML 유효성 간단 체크
        html_lower = html_output.lower()
        if not html_lower.startswith("<!doctype html") and not html_lower.startswith(
            "<html"
        ):
            logger.warning("HTML이 올바른 형식으로 시작하지 않습니다")

        if "</html>" not in html_lower:
            logger.warning("HTML이 </html> 태그로 종료되지 않았습니다 (잘렸을 가능성)")

        return html_output

    async def render_html_to_image(
        self,
        html_path: str,
        output_path: str,
        width: int = 1024,
        height: int = 1024,
        timeout: int = 30000,
    ) -> str:
        """
        Playwright로 HTML 파일을 이미지로 렌더링 (비동기)

        Args:
            html_path: 렌더링할 HTML 파일 경로
            output_path: 출력 이미지 경로
            width: 뷰포트 너비
            height: 뷰포트 높이
            timeout: 배경 이미지 로딩 대기 타임아웃 (밀리초, 기본값: 30000)

        Returns:
            저장된 이미지 경로
        """
        logger.info(
            f"HTML → 이미지 렌더링 시작: html={html_path}, output={output_path}, timeout={timeout}ms"
        )

        # HTML 파일을 file:// URL로 변환
        html_file_url = Path(html_path).resolve().as_uri()
        logger.debug(f"HTML 파일 URL: {html_file_url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": width, "height": height})

            # HTML 파일 로드 (file:// 프로토콜로 상대 경로 이미지 자동 해석)
            await page.goto(html_file_url, wait_until="domcontentloaded")

            # 배경 이미지 로딩 대기 (networkidle 또는 수동 체크)
            logger.info("배경 이미지 로딩 대기 중...")
            try:
                # 네트워크 유휴 상태까지 대기 (이미지 로드 포함)
                await page.wait_for_load_state("networkidle", timeout=timeout)
                logger.info("네트워크 유휴 상태 도달 (이미지 로드 완료)")
            except Exception as e:
                logger.warning(f"networkidle 타임아웃 ({timeout}ms): {e}")
                logger.info("수동 배경 이미지 로딩 체크 진행...")

            # 추가 검증: JavaScript로 배경 이미지 로딩 상태 확인
            try:
                bg_loaded = await page.evaluate(
                    """
                    async () => {
                        const checkBackgroundImage = () => {
                            const elements = document.querySelectorAll('*');
                            const bgElements = [];
                            
                            elements.forEach(el => {
                                const bgImage = window.getComputedStyle(el).backgroundImage;
                                if (bgImage && bgImage !== 'none' && bgImage.includes('url(')) {
                                    bgElements.push({
                                        element: el,
                                        bgImage: bgImage
                                    });
                                }
                            });
                            
                            return bgElements;
                        };
                        
                        // 배경 이미지 요소 찾기
                        const bgElements = checkBackgroundImage();
                        
                        if (bgElements.length === 0) {
                            return { loaded: false, count: 0, message: '배경 이미지 요소 없음' };
                        }
                        
                        // 각 배경 이미지 로딩 대기
                        const loadPromises = bgElements.map(({ element, bgImage }) => {
                            return new Promise((resolve) => {
                                // URL 추출
                                const urlMatch = bgImage.match(/url\\(['"]?([^'"()]+)['"]?\\)/);
                                if (!urlMatch) {
                                    resolve({ success: false, url: bgImage });
                                    return;
                                }
                                
                                const imageUrl = urlMatch[1];
                                
                                // Base64 이미지는 즉시 로드됨
                                if (imageUrl.startsWith('data:')) {
                                    resolve({ success: true, url: 'base64 image' });
                                    return;
                                }
                                
                                // 일반 URL 이미지 프리로드
                                const img = new Image();
                                img.onload = () => resolve({ success: true, url: imageUrl });
                                img.onerror = () => resolve({ success: false, url: imageUrl });
                                img.src = imageUrl;
                            });
                        });
                        
                        const results = await Promise.all(loadPromises);
                        const loadedCount = results.filter(r => r.success).length;
                        
                        return {
                            loaded: loadedCount > 0,
                            count: bgElements.length,
                            loadedCount: loadedCount,
                            results: results
                        };
                    }
                """
                )

                if bg_loaded["loaded"]:
                    logger.info(
                        f"배경 이미지 로딩 완료: {bg_loaded['loadedCount']}/{bg_loaded['count']}개"
                    )
                    for idx, result in enumerate(bg_loaded.get("results", [])[:3]):
                        status = "✓" if result["success"] else "✗"
                        url_display = (
                            result["url"][:60]
                            if len(result["url"]) > 60
                            else result["url"]
                        )
                        logger.debug(f"  {status} 이미지 {idx+1}: {url_display}...")
                else:
                    logger.warning(
                        f"배경 이미지 로딩 실패: {bg_loaded.get('message', '알 수 없는 오류')}"
                    )

            except Exception as e:
                logger.error(f"배경 이미지 로딩 확인 중 오류: {e}")

            # 추가 렌더링 대기
            await page.wait_for_timeout(1000)

            # 스크린샷
            await page.screenshot(path=output_path, full_page=True)

            await browser.close()

        logger.info(f"이미지 렌더링 완료: {output_path}")
        return output_path

    async def generate_prompt_png(
        self,
        image: Union[Image.Image, str],
        ad_text: str,
        text_prompt: Optional[str] = None,
        composition_prompt: Optional[str] = None,
    ) -> Image.Image:
        """
        이미지와 광고 문구를 분석하여 PNG 광고 이미지 생성

        Args:
            image: PIL Image 객체 또는 이미지 경로
            ad_text: 광고 문구
            text_prompt: 텍스트 프롬프트
            composition_prompt: 구성 프롬프트

        Returns:
            생성된 PIL Image 객체
        """
        temp_image_path = None
        temp_html_path = None
        temp_output_path = None

        try:
            # 임시 디렉토리 생성
            temp_dir = Path(tempfile.mkdtemp(prefix="llm_html_"))
            logger.debug(f"임시 디렉토리 생성: {temp_dir}")

            # PIL Image 객체인 경우 임시 파일로 저장
            if isinstance(image, Image.Image):
                temp_image_path = temp_dir / "input_image.png"
                image.save(temp_image_path)
                logger.debug(f"PIL Image를 임시 파일로 저장: {temp_image_path}")
                image_path = str(temp_image_path)
            else:
                # 문자열 경로인 경우 그대로 사용
                image_path = image
                logger.debug(f"이미지 경로 사용: {image_path}")

            # 임시 HTML 및 출력 경로 설정
            temp_html_path = temp_dir / "temp.html"
            temp_output_path = temp_dir / "output.png"

            # HTML 생성
            html_output = self.generate_prompt_html(
                image_path=image_path,
                ad_text=ad_text,
                text_prompt=text_prompt,
                composition_prompt=composition_prompt,
            )

            # HTML 저장
            logger.info("생성된 HTML 저장 중...")
            with open(temp_html_path, "w", encoding="utf-8") as f:
                f.write(html_output)
            logger.debug(f"임시 HTML 저장: {temp_html_path}")

            # HTML → 이미지 렌더링
            await self.render_html_to_image(
                html_path=str(temp_html_path),
                output_path=str(temp_output_path),
                width=1024,
                height=1024,
            )

            # 결과 이미지 로드
            result_image = Image.open(temp_output_path)
            # 메모리로 복사 (파일 핸들 해제를 위해)
            result_image.load()

            logger.info("PNG 광고 이미지 생성 완료")
            return result_image

        finally:
            # 임시 파일 정리

            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"임시 디렉토리 삭제: {temp_dir}")
                except Exception as e:
                    logger.warning(f"임시 디렉토리 삭제 실패: {e}")


logger.info("LLMTexttoHTML 클래스 정의 완료")
