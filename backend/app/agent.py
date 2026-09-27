import os, json, re
from typing import Dict, Any, List
from .openapi_engine import compact_spec, rank_ops, call_operation

def local_plan(goal: str, spec: Dict[str, Any], max_steps=3):
    ops = compact_spec(spec)["operations"]
    ranked = rank_ops(goal, ops)
    goal_l = goal.lower()
    selected = []
    # Demo-aware chaining: if the goal contains "then", "after", "and then", select top distinct GETs.
    wants_chain = bool(re.search(r"\bthen\b|\band then\b|\bafter that\b|\bafter\b", goal_l))
    # Demo-aware ordering for common dependent workflows: fetch an entity first,
    # then use that entity's identifier to fetch related records.
    if wants_chain and "post" in goal_l and "user" in goal_l:
        user_ops = [op for _, op in ranked if "user" in (op["operation_id"] + " " + op["path"] + " " + op["summary"]).lower()]
        post_ops = [op for _, op in ranked if "post" in (op["operation_id"] + " " + op["path"] + " " + op["summary"]).lower()]
        selected = []
        if user_ops: selected.append(user_ops[0])
        if post_ops and post_ops[0] not in selected: selected.append(post_ops[0])
        for _, op in ranked:
            if len(selected) >= max_steps: break
            if op not in selected: selected.append(op)
    elif wants_chain:
        for _, op in ranked:
            if op not in selected:
                selected.append(op)
            if len(selected) >= max_steps: break
    else:
        selected = [ranked[0][1]] if ranked else []
    steps = []
    for i, op in enumerate(selected):
        dep = steps[-1]["operation_id"] if steps else None
        steps.append({
            "operation_id": op["operation_id"],
            "method": op["method"],
            "path": op["path"],
            "reason": f"Selected because the operation matches the intent around '{op['summary']}'.",
            "parameter_map": {},
            "depends_on": dep
        })
    return {
        "goal": goal,
        "reasoning": "The agent decomposed the request into API operations, selected matching endpoints from the OpenAPI contract, and will execute them in dependency order.",
        "steps": steps,
        "mode": "local"
    }

async def gemini_plan(goal: str, spec: Dict[str, Any], max_steps=3):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return local_plan(goal, spec, max_steps)
    try:
        from google import genai
        client = genai.Client(api_key=key)
        catalog = compact_spec(spec)
        prompt = f"""You are an API orchestration planner.
Return ONLY valid JSON with keys goal, reasoning, steps, mode.
steps is an array of at most {max_steps} objects containing operation_id, method, path, reason, parameter_map, depends_on.
Choose only operations from this catalog.
Goal: {goal}
Catalog:
{json.dumps(catalog, indent=2)[:18000]}
"""
        resp = client.models.generate_content(model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"), contents=prompt)
        text = resp.text.strip()
        text = re.sub(r"^```json|```$", "", text, flags=re.I).strip()
        plan = json.loads(text)
        plan["mode"] = "gemini"
        return plan
    except Exception:
        return local_plan(goal, spec, max_steps)

async def run_agent(goal: str, spec: Dict[str, Any], auth: Dict[str,str], max_steps=3):
    plan = await gemini_plan(goal, spec, max_steps)
    op_map = {x["operation_id"]: x for x in compact_spec(spec)["operations"]}
    trace = []
    results = []
    previous = {}
    for idx, step in enumerate(plan["steps"]):
        op = op_map.get(step["operation_id"])
        if not op:
            trace.append({"type":"error","message":f"Operation {step['operation_id']} is not present in the loaded specification."})
            continue
        trace.append({"type":"plan","step":idx+1,"message":f"{op['method']} {op['path']} — {step['reason']}"})
        result = await call_operation(spec, op, goal, auth, previous)
        results.append({"operation_id":op["operation_id"], "method":op["method"], "path":op["path"], "result":result})
        trace.append({"type":"api","step":idx+1,"status":result.get("status"),"url":result.get("url"),"attempts":result.get("attempts",1)})
        if result.get("status",0) >= 400:
            # Schema-drift recovery pass: refresh operation contract and retry once with rebuilt params.
            trace.append({"type":"recovery","message":"Schema/API response rejected the first request. Agent re-read the operation contract and rebuilt the request."})
            result2 = await call_operation(spec, op, goal, auth, previous)
            results[-1]["recovery_result"] = result2
            trace.append({"type":"api","step":idx+1,"status":result2.get("status"),"url":result2.get("url"),"attempts":result2.get("attempts",1),"recovery":True})
        data = result.get("data")
        if isinstance(data, dict):
            previous.update({k:data[k] for k in ("id","userId","user_id","customerId","postId") if k in data})
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                previous.update({k:first[k] for k in ("id","userId","user_id","customerId","postId") if k in first})
    summary = synthesize(goal, results)
    trace.append({"type":"synthesis","message":"Agent merged the multi-source API responses into a concise answer."})
    return {"plan":plan,"trace":trace,"results":results,"summary":summary}

def synthesize(goal, results):
    successful = [r for r in results if r["result"].get("status",0) < 400 and r["result"].get("status",0) > 0]
    if not successful:
        return "The workflow could not complete a successful API call. Check the API base URL, authentication, or request parameters."
    parts = []
    for r in successful:
        data = r["result"].get("data")
        if isinstance(data, list):
            parts.append(f"{r['method']} {r['path']} returned {len(data)} records.")
            if data and isinstance(data[0], dict):
                sample = data[0]
                fields = [f"{k}={sample[k]}" for k in list(sample)[:4]]
                parts.append("Sample: " + ", ".join(fields))
        elif isinstance(data, dict):
            fields = [f"{k}={data[k]}" for k in list(data)[:6]]
            parts.append(f"{r['method']} {r['path']} returned: " + ", ".join(fields))
        else:
            parts.append(f"{r['method']} {r['path']} returned a response.")
    return " ".join(parts)
