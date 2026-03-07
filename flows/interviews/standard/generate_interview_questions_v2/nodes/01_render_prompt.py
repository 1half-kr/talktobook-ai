from promptflow.core import tool
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from pathlib import Path
from typing import List, Dict

@tool
def render_prompt(material: str, qtype: str, keywords: List[str], tone: str, max_len: int) -> Dict:
    tpl_dir = Path(__file__).resolve().parent.parent / "prompts"
    env = Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        undefined=StrictUndefined,
        autoescape=select_autoescape()
    )
    tpl = env.get_template("generate_interview_questions_v2.jinja2")
    prompt = tpl.render(material=material, qtype=qtype, keywords=keywords, tone=tone, max_len=max_len)
    return {"prompt": prompt}
