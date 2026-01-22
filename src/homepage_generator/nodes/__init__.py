from config.config import Settings, PromptsConfig
from nodes import nodes
from state import AdState
from typing import Dict, Any
import asyncio
from nodes.nodes import *
from nodes.image_generator import generate_images_with_llm


class Nodes:
    def __init__(self, settings: Settings, prompts: PromptsConfig) -> None:
        super().__init__()
        self.settings = settings
        self.prompts = prompts
        self.client = AsyncOpenAI(api_key=settings.openai_config.api_key)

    # Node 래퍼 함수들 (동기 -> 비동기 변환)
    def _node_brain_storm(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(create_brain_storm(state, self.settings, self.prompts))

    def _node_bs_parser(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            create_bs_parser(state, self.settings, self.prompts, self.client)
        )

    def _node_concept_designer(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            create_concept_designer(state, self.settings, self.prompts, self.client)
        )

    def _node_marketing_strategy(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            create_marketing_strategy(state, self.settings, self.prompts, self.client)
        )

    def _node_homepage_designer(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            create_homepage_designer(state, self.settings, self.prompts, self.client)
        )

    def _node_content_designer(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            create_content_designer(state, self.settings, self.prompts, self.client)
        )

    def _node_dom_contract(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            create_dom_contract(state, self.settings, self.prompts, self.client)
        )

    def _node_validate_consistency(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            validate_consistency(state, self.settings, self.prompts, self.client)
        )

    def _node_implementation_spec(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            create_implementation_spec(state, self.settings, self.prompts, self.client)
        )

    def _node_header_footer(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            generate_header_footer(state, self.settings, self.prompts, self.client)
        )

    def _node_html_code(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            generate_html_code(state, self.settings, self.prompts, self.client)
        )

    def _node_css_code(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(
            generate_css_code(state, self.settings, self.prompts, self.client)
        )

    def _node_generate_images(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(generate_images_with_llm(state, self.settings, self.prompts))

    def _node_package_output(self, state: AdState) -> Dict[str, Any]:
        return asyncio.run(package_output(state, self.settings, self.prompts))
