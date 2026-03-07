import json
import logging

logger = logging.getLogger(__name__)

def generate_material_id_mapping():
    """material.json을 기반으로 material_id 매핑을 생성"""
    
    # material.json 로드
    with open('data/material.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    mapping = {}
    
    # 각 카테고리, 청크, 소재에 대해 ID 매핑 생성
    for cat_idx, category in enumerate(data['category']):
        cat_name = category['name']
        
        for chunk_idx, chunk in enumerate(category['chunk']):
            chunk_name = chunk['name']
            
            for mat_idx, material in enumerate(chunk['material']):
                # material이 이제 {"order": 1, "name": "소재명"} 형태
                material_name = material.get('name', '') if isinstance(material, dict) else material
                
                # 소재명 형식: "카테고리 청크 소재명"
                full_material_name = f"{cat_name} {chunk_name} {material_name}"
                
                # ID는 [카테고리order, 청크order, 소재order] (실제 order 값 사용)
                cat_order = category.get('order', cat_idx + 1)
                chunk_order = chunk.get('order', chunk_idx + 1)
                mat_order = material.get('order', mat_idx + 1) if isinstance(material, dict) else mat_idx + 1
                
                material_id = [cat_order, chunk_order, mat_order]
                
                mapping[full_material_name] = material_id
    
    # 매핑 파일 저장
    with open('data/material_id_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Generated {len(mapping)} material mappings")
    return mapping

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mapping = generate_material_id_mapping()
    
    # 샘플 출력
    logger.info("Sample mappings:")
    for i, (material, id_) in enumerate(mapping.items()):
        if i < 5:  # 처음 5개만 출력
            logger.info(f"{material} -> {id_}")
        else:
            break