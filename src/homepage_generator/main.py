"""
LangGraph 기반 광고 캠페인 생성 워크플로우
Microsoft agent-framework의 GroupChat을 활용한 multi-agent 협업
"""

import asyncio
from pathlib import Path
from langgraph.graph import StateGraph, END
from typing import Dict, Any

from state import (
    AdState,
    StoreConcept,
    MarketingStrategy,
    ImplementationSpec,
    GeneratedCode,
    Strategy,
    HomePageDesign,
    DOMContract,
)
from config.config import Settings, StoreConfig

from nodes import Nodes
from db_client import get_customer_by_id, get_latest_customer


class AdGenGraph:
    """광고 생성 LangGraph 워크플로우"""

    def __init__(self, config_path: str = None, prompt_path: str = None):
        """
        Args:
            config_path: config.yaml 파일 경로 (기본값: config/config.yaml)
        """
        if config_path is None:
            config_path = str(Path(__file__).parent / "config" / "config.yaml")
        if prompt_path is None:
            prompt_path = str(Path(__file__).parent / "config" / "prompts.yaml")

        self.settings = Settings.load(config_path)
        self.prompts = Settings.load_prompts(prompt_path)
        self.nodes = Nodes(self.settings, self.prompts)
        self.workflow = self._build_graph()

    def init_state(self, store_cfg: StoreConfig = None) -> AdState:
        """
        초기 상태를 생성합니다.
        config의 store_config를 기반으로 state를 초기화합니다.

        Args:
            store_cfg: StoreConfig 객체 (None이면 config.yaml에서 로드)
        """
        if store_cfg is None:
            store_cfg = self.settings.store_config

        initial_state: AdState = {
            # 입력 정보
            "store_info":store_cfg,
            # 각 노드 출력 (초기값)
            "brainstorm_user_input": "",
            "brainstorm": "",
            "store_concept": StoreConcept(),
            "marketing_strategy": MarketingStrategy(),
            "homepage_design": HomePageDesign(),
            "content_design": HomePageDesign(),
            # 통합 및 검증
            "consistency_report": "",
            "final_strategy": "",
            # DOM Contract
            "dom_contract": DOMContract(),
            # 구현
            "implementation_spec": ImplementationSpec(),
            "header_html": "",  # 공통 헤더 HTML
            "footer_html": "",  # 공통 푸터 HTML
            "html_codes": {},  # MPA: 페이지별 main 콘텐츠
            "css_code": "",
            "generated_code": GeneratedCode(),
            # 이미지 생성
            "generated_images": {},  # LLM MCP로 생성된 이미지 (Base64)
            # 메타 정보
            "agent_discussions": [],
            "output_path": "",
            "errors": [],
            "logs": [],
        }

        return initial_state

    async def init_state_from_db(self, customer_id: int = None) -> AdState:
        """
        데이터베이스에서 고객 데이터를 가져와 초기 상태를 생성합니다.

        Args:
            customer_id: 고객 ID (None이면 가장 최근 고객 데이터 사용)

        Returns:
            AdState
        """
        # DB에서 고객 데이터 조회
        if customer_id is None:
            print("📊 DB에서 가장 최근 고객 데이터를 가져옵니다...")
            store_data = await get_latest_customer()
        else:
            print(f"📊 DB에서 고객 ID {customer_id} 데이터를 가져옵니다...")
            store_data = await get_customer_by_id(customer_id)

        # StoreConfig 객체 생성
        store_cfg = StoreConfig(**store_data)

        print(f"✅ 고객 데이터 로드 완료: {store_cfg.store_name}")

        # 기존 init_state 함수 재사용
        return self.init_state(store_cfg)

    def _build_graph(self) -> StateGraph:
        """
        LangGraph workflow를 구축합니다.

        Workflow:
        Node 0: 브레인 스토밍 노드 (Agent-framework의 groupchat사용)
        Node A: Campaign Core
        Node B: SNS 전략
        Node C: 블로그 전략
        Node D: 디자인 가이드
        Node E: 통합 / 일관성 검증
        Node F: 구현 명세 생성
        Node G: 프론트엔드 코드 생성
        Node H: 스타일 코드 생성
        Node I: 최종 패키징
        """
        workflow = StateGraph(AdState)


        # Node 등록
        workflow.add_node("brain_storm", self.nodes._node_brain_storm)
        workflow.add_node("bs_parser", self.nodes._node_bs_parser)
        workflow.add_node("concept_designer", self.nodes._node_concept_designer)
        workflow.add_node("marketing_strategy", self.nodes._node_marketing_strategy)
        workflow.add_node("homepage_designer", self.nodes._node_homepage_designer)
        workflow.add_node("content_designer", self.nodes._node_content_designer)
        # workflow.add_node("dom_contract", self.nodes._node_dom_contract)  # DEPRECATED: Tailwind 방식 사용
        workflow.add_node("generate_images", self.nodes._node_generate_images)  # LLM MCP 이미지 생성
        workflow.add_node("header_footer", self.nodes._node_header_footer)  # 공통 Header/Footer 생성
        workflow.add_node("html_code", self.nodes._node_html_code)  # Main 콘텐츠만 생성
        # workflow.add_node("css_code", self.nodes._node_css_code)  # DEPRECATED: Tailwind CDN 사용
        workflow.add_node("package_output", self.nodes._node_package_output)

        # Edge 정의 (workflow 흐름) - 이미지 생성 추가
        workflow.set_entry_point("concept_designer")
        workflow.add_edge("concept_designer", "marketing_strategy")
        workflow.add_edge("marketing_strategy", "homepage_designer")
        workflow.add_edge("homepage_designer", "content_designer")
        workflow.add_edge("content_designer", "generate_images")  # 콘텐츠 디자인 후 이미지 생성
        workflow.add_edge("generate_images", "header_footer")  # 이미지 생성 후 Header/Footer
        workflow.add_edge("header_footer", "html_code")  # 그 다음 Main 콘텐츠 생성
        workflow.add_edge("html_code", "package_output")  # 최종 조합
        workflow.add_edge("package_output", END)

        return workflow.compile()

    def _print_node_result(self, node_name: str, state: AdState):
        """중간 결과를 출력합니다."""
        print("\n" + "-" * 60)
        print(f"[NODE COMPLETE] {node_name}")
        print("-" * 60)

        if node_name == "campaign_core":
            core = state.get('campaign_core')
            if core:
                print(f"핵심 메시지: {core.core_message}")
                print(f"톤앤매너: {core.tone_and_manner}")

        elif node_name == "sns_strategy":
            sns = state.get('sns_strategy')
            if sns:
                print(f"플랫폼: {sns.platform}")
                print(f"콘텐츠 유형: {', '.join(sns.content_types[:3])}")

        elif node_name == "blog_strategy":
            blog = state.get('blog_strategy')
            if blog:
                print(f"주제: {', '.join(blog.topics[:3])}")
                print(f"SEO 키워드: {', '.join(blog.seo_keywords[:5])}")

        elif node_name == "design_guide":
            design = state.get('design_guide')
            if design:
                print(f"컬러: {', '.join(design.color_palette[:3])}")
                print(f"무드: {', '.join(design.mood_board[:3])}")


        elif node_name == "implementation_spec":
            spec = state.get('implementation_spec')
            if spec:
                print(f"프론트엔드 요구사항: {len(spec.frontend_requirements)}개")
                print(f"스타일 요구사항: {len(spec.style_requirements)}개")

        elif node_name == "html_code":
            html_codes = state.get('html_codes', {})
            if html_codes:
                total_length = sum(len(code) for code in html_codes.values())
                print(f"HTML 생성 완료 ({len(html_codes)}개 페이지, 총 길이: {total_length} 문자)")

        elif node_name == "css_code":
            css = state.get('css_code', '')
            if css:
                print(f"CSS 생성 완료 (길이: {len(css)} 문자)")

        elif node_name == "package_output":
            path = state.get('output_path')
            if path:
                print(f"출력 경로: {path}")

        # 로그 출력
        logs = state.get('logs', [])
        if logs:
            latest_log = logs[-1] if logs else ""
            print(f"로그: {latest_log}")

        print("-" * 60)

    def run(self, verbose: bool = True) -> AdState:
        """
        워크플로우를 실행합니다.

        Args:
            verbose: True이면 중간 결과를 출력합니다.

        Returns:
            최종 AdState
        """
        print("=" * 60)
        print("[START] 광고 캠페인 생성 워크플로우 시작")
        print("=" * 60)

        initial_state = self.init_state()
        print(f"\n매장: {initial_state["store_info"].store_name}")
        print(f"목표: {initial_state["store_info"].advertising_goal}")
        print(f"예산: {initial_state["store_info"].budget}만원 / 기간: {initial_state["store_info"].period}일\n")

        if verbose:
            print("[INFO] verbose 모드: 각 노드 실행 후 중간 결과를 출력합니다.\n")

        # 워크플로우 실행 (스트리밍 방식)
        final_state = initial_state.copy()
        if verbose:
            for step_output in self.workflow.stream(initial_state):
                # 각 스텝의 결과 출력
                if step_output:
                    for node_name, node_result in step_output.items():
                        self._print_node_result(node_name, node_result)
                    current_result = next(iter(step_output.values()))
                    final_state.update(current_result)

                # 최종 상태 업데이트
                # if step_output:
                #     for node_result in step_output.values():
                #         final_state = node_result if node_result else final_state
        # 워크프로우 실행(기본 방식)
        else:
            final_state = self.workflow.invoke(initial_state)



        print("\n" + "=" * 60)
        print("✅ 워크플로우 완료!")
        print("=" * 60)

        # 로그 출력
        if final_state.get('logs'):
            print("\n📋 실행 로그:")
            for log in final_state['logs']:
                print(f"  {log}")

        if final_state.get('errors'):
            print("\n❌ 에러:")
            for error in final_state['errors']:
                print(f"  {error}")

        print(f"\n📦 출력 경로: {final_state.get('output_path', 'N/A')}")

        return final_state

    async def run_async(self) -> AdState:
        """
        비동기 방식으로 워크플로우를 실행합니다.

        Returns:
            최종 AdState
        """
        print("=" * 60)
        print("🚀 광고 캠페인 생성 워크플로우 시작 (비동기)")
        print("=" * 60)

        initial_state = self.init_state()
        print(f"\n매장: {initial_state['store_name']}")
        print(f"목표: {initial_state['advertising_goal']}")
        print(f"예산: {initial_state['budget']}만원 / 기간: {initial_state['period']}일\n")

        # 워크플로우 실행 (비동기)
        final_state = await self.workflow.ainvoke(initial_state)

        print("\n" + "=" * 60)
        print("✅ 워크플로우 완료!")
        print("=" * 60)

        # 로그 출력
        if final_state.get('logs'):
            print("\n📋 실행 로그:")
            for log in final_state['logs']:
                print(f"  {log}")

        if final_state.get('errors'):
            print("\n❌ 에러:")
            for error in final_state['errors']:
                print(f"  {error}")

        print(f"\n📦 출력 경로: {final_state.get('output_path', 'N/A')}")

        return final_state


def main():
    """메인 실행 함수"""
    import sys

    # 커맨드라인 인자로 verbose 모드 제어
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    quiet = "--quiet" in sys.argv or "-q" in sys.argv

    try:
        graph = AdGenGraph()
        final_state = graph.run(verbose=verbose and not quiet)

        print("\n" + "=" * 60)
        print("📊 최종 결과 요약")
        print("=" * 60)
        # print(f"핵심 메시지: {final_state['campaign_core'].core_message}")
        import json
        # print(final_state.keys())
        # data = final_state['store_concept'].model_dump()
        # print(f"핵심 메시지: {json.dumps(data, indent=2, ensure_ascii=False)}")
        # print(f"마케팅 전략: {json.dumps(final_state['marketing_strategy'].model_dump(), indent=2, ensure_ascii=False)}")
        # print(f"홈페이지 디자인: {json.dumps(final_state['homepage_design'].model_dump(), indent=2, ensure_ascii=False)}")
        print(f"컨텐츠 추가: {json.dumps(final_state['content_design'].model_dump(), indent=2, ensure_ascii=False)}")
        # print(f"DOM Contract: {json.dumps(final_state['dom_contract'].model_dump(), indent=2, ensure_ascii=False)}")


    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
