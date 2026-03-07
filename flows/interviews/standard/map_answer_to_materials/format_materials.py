from promptflow.core import tool
from typing import List


@tool
def format_materials_with_indices(materials_list: List[tuple]) -> List[tuple]:
    """
    materials_list를 인덱스와 함께 포맷팅
    입력: [([0,0,0], "카테고리 청크 소재"), ...]
    출력: [(0, "카테고리 청크 소재"), ...]
    """
    return [(idx, name) for idx, (_, name) in enumerate(materials_list)]