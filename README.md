# Arya Verse AI
### Autonomous API Integration & Orchestration Agent

A hackathon-ready prototype for PS-02. Arya Verse AI turns a natural-language goal into an executable API workflow by reading OpenAPI/Swagger specifications, planning the required operations, constructing requests, executing calls, handling retries, and synthesizing multi-source results.

## Core PS-02 coverage
- OpenAPI JSON/YAML file or URL ingestion
- Natural-language goal understanding
- Agentic operation planning
- Dynamic HTTP request construction
- Multi-step API chaining
- API-key / Bearer-token support
- OAuth2 scheme detection and token-ready execution
- Exponential backoff retry handling
- Schema-drift recovery pass
- Searchable execution/audit trail
- Interactive workflow visualization
- Multi-source response synthesis
- Professional Arya College branded UI

## Run
### Windows
```bat
run.bat
```

Or:
```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## Demo
1. Load `sample_specs/demo_api.json`.
2. Click **Load Demo Spec**.
3. Enter:
   `Get user 1 and then show all posts written by that user`
4. Click **Run Agent**.
5. Watch the Planner → API calls → synthesis trace.

The demo spec uses JSONPlaceholder, so internet access is needed for live calls.

## Optional Gemini planner
Copy `.env.example` to `.env` and add:
```env
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
```
If no key is present, Arya Verse AI uses its deterministic local planner so the prototype still works.

## Important hackathon note
The supplied hackathon brief says the final solution must be built during the six-hour event and a pre-built project cannot be submitted as the final solution. This repository is therefore intended as a structured prototype/starter for development during the event.
