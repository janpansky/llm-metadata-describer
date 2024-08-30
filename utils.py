import re
from typing import List


def extract_ids_from_maql(maql: str) -> List[str]:
    pattern = r'\b(fact|attribute|metric|label|dataset)/([a-zA-Z0-9_]+)\b'
    matches = re.findall(pattern, maql)
    return [f"{type}/{id}" for type, id in matches]
