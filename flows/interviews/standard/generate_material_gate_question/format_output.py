from promptflow.core import tool

@tool
def format_output(question_text: str) -> dict:
    """Format the gate question output"""
    return {
        "text": question_text.strip(),
        "type": "material_gate"
    }
