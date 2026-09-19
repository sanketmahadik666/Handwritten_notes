import re

def validate_markdown_output(markdown_text: str) -> tuple[bool, str | None]:
    required = [
        (r'(?m)^#\s+.+$', 'Missing H1 title'),
        (r'(?m)^##\s+Summary\s*$', 'Missing ## Summary section'),
        (r'(?m)^##\s+Notes\s*$', 'Missing ## Notes section'),
        (r'(?m)^##\s+Uncertain readings\s*$', 'Missing ## Uncertain readings section'),
        (r'(?m)^##\s+Boilerplate omitted\s*$', 'Missing ## Boilerplate omitted section')
    ]
    for pattern, err in required:
        if not re.search(pattern, markdown_text):
            return False, err
    return True, None
