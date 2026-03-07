from promptflow.core import tool
import requests
import json
import os

@tool
def generate_image(autobiography_content: str, style: str = "natural") -> str:
    """
    하드코딩된 프롬프트로 이미지 생성 (1024x1792 고정)
    """
    try:
        # 하드코딩된 프롬프트 템플릿
        prompt = f"Create a symbolic scene with a cover-like, centered composition and elegant typography-friendly negative space. IMPORTANT: Do NOT include any text, words, letters, numbers, or written characters in the image. Do NOT depict a book, book cover, or any text layout. The theme should be: {autobiography_content}"
        
        api_key = None
        
        # 1. PromptFlow 연결에서 API 키 가져오기 시도
        try:
            from promptflow import PFClient
            pf = PFClient()
            connection = pf.connections.get("open_ai_connection")
            api_key = getattr(connection, 'api_key', None)
        except Exception:
            pass
        
        # 2. 환경변수에서 API 키 가져오기
        if not api_key:
            api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            return "Error: No OpenAI API key found"
        
        # OpenAI API 직접 호출
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "dall-e-3",
            "prompt": prompt,
            "style": style,
            "size": "1024x1792",
            "quality": "standard",
            "n": 1
        }
        
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("data") and len(result["data"]) > 0:
                return result["data"][0]["url"]
            else:
                return "Error: No image generated"
        else:
            return f"Error: {response.status_code} - {response.text}"
        
    except Exception as e:
        return f"Error: {str(e)}"