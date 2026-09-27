import json, re, yaml
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin
import httpx

METHODS = {"get", "post", "put", "patch", "delete"}

def parse_spec(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        r = httpx.get(raw, timeout=15, follow_redirects=True)
        r.raise_for_status()
        raw = r.text
    try:
        return json.loads(raw)
    except Exception:
        return yaml.safe_load(raw)

def base_url(spec: Dict[str, Any]) -> str:
    if spec.get("servers"):
        return spec["servers"][0].get("url", "")
    host = spec.get("host")
    if host:
        scheme = (spec.get("schemes") or ["https"])[0]
        base = f"{scheme}://{host}"
        prefix = spec.get("basePath", "")
        return base.rstrip("/") + "/" + prefix.strip("/")
    return ""

def operations(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for path, item in spec.get("paths", {}).items():
        for method, op in item.items():
            if method.lower() not in METHODS or not isinstance(op, dict):
                continue
            out.append({
                "operation_id": op.get("operationId", f"{method}_{path}".replace("/", "_")),
                "method": method.upper(),
                "path": path,
                "summary": op.get("summary") or op.get("description") or f"{method.upper()} {path}",
                "parameters": op.get("parameters", []),
                "requestBody": op.get("requestBody"),
                "tags": op.get("tags", []),
            })
    return out

def compact_spec(spec):
    return {
        "title": spec.get("info", {}).get("title", "Untitled API"),
        "version": spec.get("info", {}).get("version", ""),
        "base_url": base_url(spec),
        "operations": operations(spec),
        "security_schemes": spec.get("components", {}).get("securitySchemes", {}),
    }

def resolve_path_params(path: str, params: Dict[str, Any]) -> str:
    return re.sub(r"\{([^}]+)\}", lambda m: str(params.get(m.group(1), m.group(0))), path)

def choose_value(name: str, goal: str, previous: Dict[str, Any] | None = None):
    text = goal.lower()
    if previous:
        for k in ("id", "userId", "user_id", "customerId", "postId"):
            if k in previous:
                if name.lower() in {k.lower(), "id"}:
                    return previous[k]
    # pull first explicit number after id/user/customer
    patterns = [
        rf"{re.escape(name.lower())}\s*(?:is|=|:)?\s*(\d+)",
        r"\b(?:user|customer|post|product|order)\s*(?:id\s*)?(?:is|=|#)?\s*(\d+)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m: return int(m.group(1))
    return 1

def build_request(op: Dict[str, Any], goal: str, previous: Dict[str, Any] | None = None):
    params = {}
    query = {}
    headers = {}
    body = {}
    for p in op.get("parameters", []):
        name = p.get("name")
        if not name: continue
        val = choose_value(name, goal, previous)
        if p.get("in") == "path": params[name] = val
        elif p.get("in") == "query": query[name] = val
        elif p.get("in") == "header": headers[name] = val
    return params, query, headers, body

def rank_ops(goal: str, ops: List[Dict[str, Any]]) -> List[Tuple[float, Dict[str, Any]]]:
    words = set(re.findall(r"[a-zA-Z0-9]+", goal.lower()))
    ranked = []
    for op in ops:
        hay = " ".join([op["operation_id"], op["path"], op["summary"], " ".join(op["tags"])]).lower()
        score = sum(1 for w in words if len(w) > 2 and w in hay)
        if op["method"] == "GET": score += 0.15
        ranked.append((score, op))
    return sorted(ranked, key=lambda x: x[0], reverse=True)

async def call_operation(spec, op, goal, auth, previous=None):
    base = base_url(spec).rstrip("/")
    path_params, query, headers, body = build_request(op, goal, previous)
    path = resolve_path_params(op["path"], path_params)
    url = urljoin(base + "/", path.lstrip("/"))
    security = spec.get("components", {}).get("securitySchemes", {})
    auth_type = auth.get("type", "")
    token = auth.get("token", "")
    if token:
        if auth_type == "api_key":
            headers[auth.get("header", "X-API-Key")] = token
        else:
            headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    if "requestBody" in op and op.get("requestBody"):
        body = body or {}
    return await resilient_request(op["method"], url, query, headers, body)

async def resilient_request(method, url, query=None, headers=None, body=None, retries=2):
    query, headers, body = query or {}, headers or {}, body or None
    last = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.request(method, url, params=query, headers=headers, json=body if method in {"POST","PUT","PATCH"} else None)
            if r.status_code in {429, 500, 502, 503, 504} and attempt < retries:
                import asyncio
                await asyncio.sleep(0.6 * (2 ** attempt))
                continue
            return {
                "status": r.status_code,
                "url": str(r.url),
                "headers": dict(r.headers),
                "data": safe_json(r),
                "attempts": attempt + 1,
            }
        except Exception as e:
            last = str(e)
            if attempt < retries:
                import asyncio
                await asyncio.sleep(0.6 * (2 ** attempt))
    return {"status": 0, "url": url, "error": last or "request failed", "attempts": retries + 1}

def safe_json(r):
    try:
        return r.json()
    except Exception:
        return r.text[:5000]
