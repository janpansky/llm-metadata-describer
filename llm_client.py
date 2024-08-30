import requests
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, api_token: str, model: str = "gpt-4o-mini"):
        self.api_token = api_token
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def call(self, prompt: str, max_tokens: int = 150) -> str:
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        response = requests.post(self.api_url, headers=headers, json=data)

        if response.status_code != 200:
            logger.error(f"Received status code {response.status_code} from OpenAI API: {response.text}")
            sys.exit(1)

        response_data = response.json()
        return response_data['choices'][0]['message']['content'].strip()
