from promptflow.core import tool
from typing import Dict, List

BANNED = ["성적", "혐오", "차별", "욕설"]  # 필요시 확장

POLICY_VERSION = "v0.5.0"
TEMPLATE_VERSION = "ask_question_v2.0"

def _clean(text: str) -> str:
    # 새줄/공백 정리 & 끝문장부호 보정
    s = " ".join((text or "").split())
    if not s.endswith(("?", "요.")):
        s = s.rstrip(".") + "?"
    return s

@tool
def guard(raw_text: str, max_len: int = 120) -> Dict:
    t = _clean(raw_text)
    # 길이 제한
    if len(t) > max_len:
        t = t[:max_len].rstrip() + "?"
    # 금칙어 필터(단순)
    for w in BANNED:
        if w in t:
            t = t.replace(w, "부적절한 표현")
    # 더블질문 간단 차단
    if "?" in t[:-1]:
        t = t.replace("?", "…")
        if not t.endswith("?"):
            t += "?"
    return {
        "text": t,
        "policyVersion": POLICY_VERSION,
        "templateVersion": TEMPLATE_VERSION
    }
