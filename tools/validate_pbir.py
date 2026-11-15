import hashlib
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin

import httpx
from jsonschema import Draft7Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools/pbir-schemas"
PREFIX = "https://developer.microsoft.com/json-schemas/"


def retrieve(uri):
    uri = urldefrag(uri)[0]
    if not uri.startswith(PREFIX):
        raise ValueError("Solo se admiten esquemas oficiales de Microsoft")
    file = CACHE / (hashlib.sha256(uri.encode()).hexdigest() + ".json")
    if not file.exists():
        response = httpx.get(uri, timeout=30, follow_redirects=True)
        response.raise_for_status()
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(response.text)
    contents = json.loads(file.read_text())
    return Resource.from_contents(contents)


def refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and not item.startswith("#"):
                yield item
            else:
                yield from refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from refs(item)


def main():
    files = (
        list((ROOT / "powerbi").rglob("*.json"))
        + list((ROOT / "powerbi").rglob("*.pbir"))
        + list((ROOT / "powerbi").rglob("*.pbism"))
    )
    validated = 0
    seen = set()
    for file in files:
        instance = json.loads(file.read_text())
        uri = instance.get("$schema")
        if not uri:
            continue
        pending = [uri]
        while pending:
            source = urldefrag(pending.pop())[0]
            if source in seen:
                continue
            seen.add(source)
            resource = retrieve(source)
            pending.extend(urljoin(source, ref) for ref in refs(resource.contents))
        registry = Registry(retrieve=retrieve)
        schema = dict(retrieve(uri).contents)
        schema["$id"] = uri
        Draft7Validator(schema, registry=registry).validate(instance)
        validated += 1
    if validated < 20:
        raise ValueError("Faltan páginas o visuales del informe")
    print(json.dumps({"validated_files": validated, "official_schemas": len(seen)}))


if __name__ == "__main__":
    main()
