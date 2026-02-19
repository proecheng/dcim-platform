"""协议适配器公共工具函数"""
import re
from typing import Any, Callable


def build_json_extractor(path: str) -> Callable[[dict], Any]:
    """构建 JSON 路径提取器

    支持点分路径: "data.temperature" → payload["data"]["temperature"]
    支持数组索引: "sensors[0].value" → payload["sensors"][0]["value"]
    """
    parts: list[str | int] = []
    for segment in path.split("."):
        match = re.match(r"^(\w+)\[(\d+)\]$", segment)
        if match:
            parts.append(match.group(1))
            parts.append(int(match.group(2)))
        else:
            parts.append(segment)

    def extract(payload: dict) -> Any:
        current: Any = payload
        for part in parts:
            if isinstance(part, int):
                current = current[part]
            else:
                current = current[part]
        return current

    return extract
