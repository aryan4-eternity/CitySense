"""
CitySense Chat Backend
======================
LLM-powered chat endpoint using Gemini (google-genai SDK) with function-calling.

Tools available to the model:
  - get_city_stats            → city-wide aggregates
  - get_cell_details          → full data bundle for one cell
  - get_top_cells             → ranked cells, optionally filtered by priority
  - get_ward_summary          → ward-level aggregates
  - find_cell_by_coordinates  → lat/lng → cell_id (used for Google Maps links)
  - search_cells_by_condition → cells matching a detected condition

Google Maps URL formats handled:
  https://maps.google.com/maps?q=19.05,72.88
  https://www.google.com/maps/@19.05,72.88,15z
  https://www.google.com/maps/place/Name/@19.05,72.88,15z/...
  Any text containing a bare lat,lng pair
"""

from __future__ import annotations

import math
import os
import re
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

class ChatResponse(BaseModel):
    reply: str
    cell_id: str | None = None   # resolved cell to highlight on the map


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are CitySense AI, an expert urban environmental analyst for Mumbai, India.

You have access to CitySense — a geospatial intelligence system that has analysed 836 grid cells
(~1 km² each) across Mumbai using satellite data: Land Surface Temperature (LST), Vegetation Index
(NDVI), Built-up Index (NDBI), Digital Elevation (DEM), Urban Heat Island intensity (UHI),
Flood Susceptibility Index (FSI), and Infrastructure Access Index (IAI).

Your job:
- Answer questions about Mumbai's environment, urban heat, flood risk, vegetation, and planning.
- When given a Google Maps URL or coordinates, find the matching cell and give a detailed analysis.
- Use the provided tools to fetch real data — never invent numbers.
- Be concise but insightful. Use clear structure with short paragraphs.
- Mumbai bounding box: lon 72.77–72.99°E, lat 18.89–19.27°N. If a location is outside this, say so.
- When quoting scores, always explain what they mean (e.g. "EHI 34/100 — Poor environmental health").
- Use emoji sparingly for readability (🔥 heat, 🌿 vegetation, 🌊 flood, 🏗️ built-up, ⚠️ risk).

Formatting rules (strictly follow):
- Use ## for main section headers and ### for sub-section headers.
- Do NOT include labels like "Mumbai Environmental Intelligence", "Phase 3", "Phase 2",
  "Planning Decision Engine", or any internal pipeline phase names in your responses.
- Do NOT wrap section headers or cell IDs in asterisks (*). Use plain text for those.
- Keep responses focused — avoid repeating the city name as a section title.
"""


# ---------------------------------------------------------------------------
# Google Maps URL / coordinate parser
# ---------------------------------------------------------------------------

_GMAPS_PATTERNS = [
    r"@(-?\d+\.?\d*),(-?\d+\.?\d*)",            # @lat,lng,zoom
    r"[?&]q=(-?\d+\.?\d*),(-?\d+\.?\d*)",        # ?q=lat,lng
    r"maps\?.*ll=(-?\d+\.?\d*),(-?\d+\.?\d*)",   # ll=lat,lng
    r"search/.*?/@(-?\d+\.?\d*),(-?\d+\.?\d*)",  # search/@lat,lng
]

def extract_coords_from_text(text: str) -> tuple[float, float] | None:
    for pattern in _GMAPS_PATTERNS:
        m = re.search(pattern, text)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng

    # Bare coordinate pair
    m = re.search(r"(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)", text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if 18.0 <= a <= 20.0 and 72.0 <= b <= 74.0:
            return a, b
        if 18.0 <= b <= 20.0 and 72.0 <= a <= 74.0:
            return b, a

    return None


# ---------------------------------------------------------------------------
# Grid math — lat/lng → cell_id
# ---------------------------------------------------------------------------

GRID_LAT_MIN = 18.89
GRID_LON_MIN = 72.77
CELL_SIZE    = 0.01
GRID_ROWS    = 38
GRID_COLS    = 22

def coords_to_cell_id(lat: float, lon: float) -> str | None:
    if not (GRID_LAT_MIN <= lat <= GRID_LAT_MIN + GRID_ROWS * CELL_SIZE):
        return None
    if not (GRID_LON_MIN <= lon <= GRID_LON_MIN + GRID_COLS * CELL_SIZE):
        return None
    row = max(0, min(math.floor((lat - GRID_LAT_MIN) / CELL_SIZE), GRID_ROWS - 1))
    col = max(0, min(math.floor((lon - GRID_LON_MIN) / CELL_SIZE), GRID_COLS - 1))
    return f"r{row}_c{col}"


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _tool_get_city_stats(data: dict) -> dict:
    stats = data["stats"]
    return {
        "total_cells":       stats.get("total_cells"),
        "avg_ehi":           stats.get("avg_ehi"),
        "min_ehi":           stats.get("min_ehi"),
        "max_ehi":           stats.get("max_ehi"),
        "avg_risk":          stats.get("avg_risk"),
        "priority_counts":   stats.get("priority_counts", {}),
        "status_counts":     stats.get("status_counts", {}),
        "top_issues":        stats.get("top_issues", [])[:6],
        "top_interventions": stats.get("top_interventions", [])[:5],
    }


def _tool_get_cell_details(cell_id: str, data: dict) -> dict:
    if cell_id not in data["cell_props"]:
        return {"error": f"Cell '{cell_id}' not found. Format: r{{row}}_c{{col}}, e.g. r15_c8."}
    return {
        "cell_id":     cell_id,
        "master":      data["cell_props"].get(cell_id, {}),
        "environment": data["env_intel"].get(cell_id, {}),
        "planning":    data["plans"].get(cell_id, {}),
        "explanation": data["explanations"].get(cell_id, {}),
        "flood":       data["fsi_data"].get(cell_id, {}),
        "access":      data["iai_data"].get(cell_id, {}),
        "burden":      data["burden_data"].get(cell_id, {}),
    }


def _tool_get_top_cells(limit: int, priority_filter: str | None, data: dict) -> list[dict]:
    rows = []
    for cell_id, plan in data["plans"].items():
        if priority_filter and plan.get("planning_priority", "").lower() != priority_filter.lower():
            continue
        master = data["cell_props"].get(cell_id, {})
        ei     = data["env_intel"].get(cell_id, {})
        rows.append({
            "cell_id":                  cell_id,
            "planning_priority":        plan.get("planning_priority"),
            "priority_score":           plan.get("priority_score", 0),
            "recommended_intervention": plan.get("recommended_intervention"),
            "environmental_health":     plan.get("environmental_health", ei.get("environmental_health")),
            "risk_score":               master.get("risk_score"),
            "primary_issue":            ei.get("primary_issue"),
            "cluster":                  master.get("cluster"),
        })
    rows.sort(key=lambda r: r["priority_score"], reverse=True)
    return rows[:min(limit, 20)]


def _tool_get_ward_summary(ward_name: str, data: dict) -> dict:
    ward_profiles = data["ward_profiles"]
    if not ward_profiles:
        return {"error": "Ward profiles not yet generated."}
    for name, profile in ward_profiles.items():
        if name.lower() == ward_name.lower():
            return {"ward_name": name, **profile}
    return {"error": f"Ward '{ward_name}' not found.", "available_sample": list(ward_profiles.keys())[:10]}


def _tool_find_cell_by_coordinates(lat: float, lon: float, data: dict) -> dict:
    cell_id = coords_to_cell_id(lat, lon)
    if cell_id is None:
        return {"error": f"({lat}, {lon}) is outside Mumbai's coverage area (lat 18.89–19.27°N, lon 72.77–72.99°E)."}
    return {"cell_id": cell_id, "lat": lat, "lon": lon, **_tool_get_cell_details(cell_id, data)}


def _tool_search_cells_by_condition(condition: str, limit: int, data: dict) -> list[dict]:
    cond_lower = condition.lower()
    matched = []
    for cell_id, ei in data["env_intel"].items():
        detected = [c.lower() for c in ei.get("detected_conditions", [])]
        primary  = (ei.get("primary_issue") or "").lower()
        if cond_lower in detected or cond_lower in primary:
            plan   = data["plans"].get(cell_id, {})
            master = data["cell_props"].get(cell_id, {})
            matched.append({
                "cell_id":                  cell_id,
                "primary_issue":            ei.get("primary_issue"),
                "detected_conditions":      ei.get("detected_conditions", []),
                "environmental_health":     ei.get("environmental_health"),
                "planning_priority":        plan.get("planning_priority"),
                "recommended_intervention": plan.get("recommended_intervention"),
                "risk_score":               master.get("risk_score"),
            })
    matched.sort(key=lambda r: r.get("risk_score") or 0, reverse=True)
    return matched[:min(limit, 20)]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def dispatch_tool(name: str, args: dict, data: dict) -> Any:
    if name == "get_city_stats":
        return _tool_get_city_stats(data)
    if name == "get_cell_details":
        return _tool_get_cell_details(args["cell_id"], data)
    if name == "get_top_cells":
        return _tool_get_top_cells(args.get("limit", 5), args.get("priority_filter"), data)
    if name == "get_ward_summary":
        return _tool_get_ward_summary(args["ward_name"], data)
    if name == "find_cell_by_coordinates":
        return _tool_find_cell_by_coordinates(args["lat"], args["lon"], data)
    if name == "search_cells_by_condition":
        return _tool_search_cells_by_condition(args["condition"], args.get("limit", 10), data)
    return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Tool schemas for the new google-genai SDK
# ---------------------------------------------------------------------------

from google.genai import types as genai_types

TOOLS = [
    genai_types.Tool(
        function_declarations=[
            genai_types.FunctionDeclaration(
                name="get_city_stats",
                description="Get city-wide aggregate statistics for Mumbai: average EHI, risk score, priority distribution, top environmental issues and interventions.",
                parameters=genai_types.Schema(type=genai_types.Type.OBJECT, properties={}),
            ),
            genai_types.FunctionDeclaration(
                name="get_cell_details",
                description="Get the complete data bundle for a specific grid cell by cell_id (format r{row}_c{col}, e.g. r15_c8). Returns environmental health, planning profile, flood susceptibility, infrastructure access, and SHAP explanation.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "cell_id": genai_types.Schema(type=genai_types.Type.STRING, description="Cell ID in format r{row}_c{col}"),
                    },
                    required=["cell_id"],
                ),
            ),
            genai_types.FunctionDeclaration(
                name="get_top_cells",
                description="Get top N cells ranked by priority score, optionally filtered by planning priority level.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "limit": genai_types.Schema(type=genai_types.Type.INTEGER, description="Number of cells (max 20, default 5)"),
                        "priority_filter": genai_types.Schema(type=genai_types.Type.STRING, description="Optional: 'Critical', 'High', 'Medium', 'Low', or 'Very Low'"),
                    },
                    required=["limit"],
                ),
            ),
            genai_types.FunctionDeclaration(
                name="get_ward_summary",
                description="Get aggregated planning summary for a Mumbai ward by name.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "ward_name": genai_types.Schema(type=genai_types.Type.STRING, description="Name of the Mumbai ward"),
                    },
                    required=["ward_name"],
                ),
            ),
            genai_types.FunctionDeclaration(
                name="find_cell_by_coordinates",
                description="Find the CitySense grid cell at given geographic coordinates and return its full analysis. Use this when the user provides a Google Maps link or any lat/lng coordinates.",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "lat": genai_types.Schema(type=genai_types.Type.NUMBER, description="Latitude in decimal degrees"),
                        "lon": genai_types.Schema(type=genai_types.Type.NUMBER, description="Longitude in decimal degrees"),
                    },
                    required=["lat", "lon"],
                ),
            ),
            genai_types.FunctionDeclaration(
                name="search_cells_by_condition",
                description="Find all cells matching a specific environmental condition (e.g. 'Urban Heat Island', 'Low Vegetation', 'Flood Susceptibility', 'High Built-up Density').",
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "condition": genai_types.Schema(type=genai_types.Type.STRING, description="Environmental condition to search for"),
                        "limit": genai_types.Schema(type=genai_types.Type.INTEGER, description="Max results (default 10, max 20)"),
                    },
                    required=["condition", "limit"],
                ),
            ),
        ]
    )
]


# ---------------------------------------------------------------------------
# Main chat handler — uses new google-genai SDK
# ---------------------------------------------------------------------------

def handle_chat(request: ChatRequest, app_data: dict) -> ChatResponse:
    """
    Process a chat request using the new google-genai SDK with function-calling.
    """
    import google.genai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY not set. Add it to backend/.env",
        )

    client = genai.Client(api_key=api_key)

    # Pre-process last user message: extract coords from Maps URLs
    messages = request.messages
    last_msg_content = messages[-1].content
    coords = extract_coords_from_text(last_msg_content)

    if coords:
        lat, lng = coords
        cell_id = coords_to_cell_id(lat, lng)
        if cell_id:
            last_msg_content = (
                f"{last_msg_content}\n\n[System note: Detected coordinates ({lat}, {lng}). "
                f"Please call find_cell_by_coordinates with lat={lat}, lon={lng}.]"
            )
        else:
            last_msg_content = (
                f"{last_msg_content}\n\n[System note: Coordinates ({lat}, {lng}) are outside "
                f"Mumbai's coverage area. Inform the user.]"
            )

    # Build conversation history for the new SDK
    # New SDK uses Content objects with role "user" / "model"
    history = []
    for msg in messages[:-1]:
        role = "user" if msg.role == "user" else "model"
        history.append(
            genai_types.Content(
                role=role,
                parts=[genai_types.Part(text=msg.content)],
            )
        )

    # Add the (possibly augmented) last user message
    history.append(
        genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=last_msg_content)],
        )
    )

    config = genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=TOOLS,
        temperature=0.3,
    )

    resolved_cell_id: str | None = None

    # Agentic loop — keep calling until we get a text response
    for _ in range(8):
        # Retry up to 3 times on 503 (model overloaded)
        import time
        last_exc = None
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=history,
                    config=config,
                )
                last_exc = None
                break
            except Exception as exc:
                if "503" in str(exc) and attempt < 2:
                    time.sleep(4)
                    last_exc = exc
                else:
                    raise
        if last_exc:
            raise last_exc

        candidate = response.candidates[0] if response.candidates else None
        if candidate is None:
            break

        parts = candidate.content.parts if candidate.content else []

        # Check for function calls
        fn_calls = [p for p in parts if p.function_call is not None]
        if not fn_calls:
            break  # Text response — done

        # Append model's function-call turn to history
        history.append(candidate.content)

        # Execute all function calls and collect results
        result_parts = []
        for part in fn_calls:
            fc   = part.function_call
            name = fc.name
            args = dict(fc.args) if fc.args else {}

            result = dispatch_tool(name, args, app_data)

            # Track resolved cell
            if name in ("find_cell_by_coordinates", "get_cell_details"):
                cid = result.get("cell_id") if isinstance(result, dict) else None
                if cid and "error" not in result:
                    resolved_cell_id = cid

            result_parts.append(
                genai_types.Part(
                    function_response=genai_types.FunctionResponse(
                        name=name,
                        response={"result": result},
                    )
                )
            )

        # Append function results as a "user" turn (tool role)
        history.append(
            genai_types.Content(role="user", parts=result_parts)
        )

    # Extract final text reply
    reply_text = ""
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if part.text:
                reply_text += part.text

    if not reply_text:
        reply_text = "I encountered an issue generating a response. Please try again."

    return ChatResponse(reply=reply_text, cell_id=resolved_cell_id)
