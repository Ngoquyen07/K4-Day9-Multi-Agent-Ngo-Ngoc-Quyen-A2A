import os
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, Any

load_dotenv()

class LLMClient:
    """
    OpenRouter LLM Client for calling nvidia/nemotron-nano-9b-v2:free.
    Extracts both LLM reasoning chain and final content output.
    """

    def __init__(self, model_name: str = "nvidia/nemotron-nano-9b-v2:free"):
        self.model_name = model_name
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if self.api_key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
            )
        else:
            self.client = None

    def generate_reasoning(self, system_prompt: str, user_prompt: str, max_tokens: int = 512) -> Dict[str, str]:
        if not self.client:
            return {
                "content": "[LLM API Key missing]",
                "reasoning": "Skipped LLM call because OPENROUTER_API_KEY is not set."
            }

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
            )
            msg = response.choices[0].message
            content = msg.content.strip() if msg.content else ""
            reasoning = getattr(msg, "reasoning", "") or ""
            return {
                "content": content,
                "reasoning": reasoning,
            }
        except Exception as e:
            return {
                "content": f"[LLM Error: {e}]",
                "reasoning": f"Exception occurred during API call: {e}",
            }
