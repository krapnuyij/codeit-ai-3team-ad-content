from openai import OpenAI, AsyncOpenAI
from config.config import Settings, PromptsConfig

import os
from pydantic import BaseModel
from typing import Type
import json

from dotenv import load_dotenv
load_dotenv()

class OpenAIAgent:
    def __init__(self, client, agent_config, settings: Settings):
        self.name = agent_config.name
        self.role = agent_config.role
        self.system_message = agent_config.system_message
        self.client = client
        self.settings = settings

    async def create(self, message: str="system 메시지를 기반으로 대답해주세요."):
        messages = [{"role": "system", "content": self.system_message}]
        messages.append({"role": "user", "content": message})

        responses = await self.client.chat.completions.create(
            messages=messages,
            model= self.settings.openai_config.chat_model,
        )

        return responses
    #
    # async def create_structured(self, message: str, response_model: Type[BaseModel]):
    #     schema = response_model.model_json_schema()
    #
    #     response = await self.client.chat.completions.create(
    #         model=self.settings.openai_config.chat_model,
    #         messages=[
    #             {"role": "system", "content": self.system_message},
    #             {"role": "user", "content": message}
    #         ],
    #         response_format={
    #             "type": "json_schema",
    #             "json_schema": {
    #                 "name": response_model.__name__.lower(),
    #                 "schema": response_model.model_json_schema(),
    #                 "strict": True
    #             }
    #         }
    #     )
    #
    #     result = json.loads(response.choices[0].message.content)
    #     return response_model(**result)  # 100% 성공 보장
    async def create_structured(self, message: str, response_model: Type[BaseModel]):
        # .create 대신 .beta.chat.completions.parse를 사용하면
        # Pydantic 모델의 strict 설정과 additionalProperties를 SDK가 알아서 처리합니다.
        response = await self.client.beta.chat.completions.parse(
            model=self.settings.openai_config.chat_model,
            messages=[
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": message}
            ],
            response_format=response_model,  # dict가 아닌 모델 클래스를 직접 전달
        )

        return response.choices[0].message.parsed
if __name__ == "__main__":
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), )
    default_yaml_path = "D:/codeit/ad_langgraph/config/config.yaml"
    prompts_yaml_path = "D:/codeit/ad_langgraph/config/prompts.yaml"

    settings = Settings.load(default_yaml_path)
    prompts = Settings.load_prompts(prompts_yaml_path)
    agent_config = prompts.bs_agents["manager"]
    agent = OpenAIAgent(
        client=client,
        agent_config=agent_config,
        settings=settings,
    )
    print(agent.create(message="Hello, world!"))