import os
import re

def build_notes_payload(doc_data: dict, raw_text: str) -> dict:
    image_meta = doc_data.get('image_metadata', {})
    h = image_meta.get('height', 1)
    w = image_meta.get('width', 1)
    
    regions = doc_data.get('regions', [])
    sorted_lines = sorted(regions, key=lambda r: r.get('sorted_index', 0))
    
    formatted_lines = []
    has_form_label = False
    for r in sorted_lines:
        text = r.get('raw_text', '')
        if re.match(r'^(Name|Date|Signed|Total|Page):?\s*$', text, re.I):
            has_form_label = True
            
        poly = r.get('sorted_polygon', [])
        near_bottom = False
        if poly and len(poly) >= 4:
            avg_y = sum(pt[1] for pt in poly) / len(poly)
            near_bottom = (avg_y / h) > 0.90
            
        formatted_lines.append({
            'region_id': r.get('region_id'),
            'sorted_index': r.get('sorted_index'),
            'raw_text': text,
            'detector_score': r.get('detector_score'),
            'recognition_score': r.get('recognition_score'),
            'crop_status': r.get('crop_provenance', {}).get('status', 'missing'),
            'near_bottom': near_bottom
        })
        
    hint = "trailing form fields detected (e.g. 'Name:') - exclude from body notes" if has_form_label else None
    
    return {
        'document_id': doc_data['document_id'],
        'source_image': os.path.basename(doc_data.get('source_image', '')),
        'source_image_sha256': doc_data.get('source_image_sha256'),
        'page_status': doc_data.get('status', 'success'),
        'image': {'width': w, 'height': h},
        'document_text_raw': raw_text,
        'form_label_hint': hint,
        'lines': formatted_lines
    }
