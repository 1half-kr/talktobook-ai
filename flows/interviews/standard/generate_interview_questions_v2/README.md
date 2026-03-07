# generate_interview_question_v2 (standard)

LLM을 사용해 **(material, type, keywords)**를 입력으로 **한국어 후속 질문 1문장**을 생성하는 표준 워커.

## Inputs
- `material: str`
- `type: str` — one of `who|why|when|how|where|what|ex|con`
- `keywords: list[str]`
- `tone: str` (default: 따뜻하고 존중하는 어조)
- `max_len: int` (default: 120)
- `model: str` (default: gpt-4o-mini)
- `temperature: float` (default: 0.3)
- `api_key: str` (선택; Prompt Flow connection 주입)

## Outputs
- `text: str`
- `policyVersion: str`
- `templateVersion: str`

## 실행
- VS Code Prompt Flow 확장에서 `flow.dag.yaml` Test Run
- OpenAI 인증:
  - 방법 A: 환경변수 `OPENAI_API_KEY`
  - 방법 B: Prompt Flow connection `open_ai_connection`의 `api_key`를 `inputs.api_key`로 바인딩
