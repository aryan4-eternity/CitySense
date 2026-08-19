"""
CitySense Chat Backend — OpenRouter Edition
===========================================
LLM-powered chat endpoint using OpenRouter API (OpenAI-compatible)
with function-calling and location resolution.

Tools available to the model:
  - get_city_stats            → city-wide aggregates
  - get_cell_details          → full data bundle for one cell
  - get_top_cells             → ranked cells, optionally filtered by priority
  - get_ward_summary          → ward-level aggregates
  - find_cell_by_coordinates  → lat/lng → cell_id (used for Google Maps links)
  - search_cells_by_condition → cells matching a detected condition
  - search_cells_by_location  → cells in/near a named locality (e.g. Bandra, Andheri)

Google Maps URL formats handled:
  https://maps.google.com/maps?q=19.05,72.88
  https://www.google.com/maps/@19.05,72.88,15z
  https://www.google.com/maps/place/Name/@19.05,72.88,15z/...
  Any text containing a bare lat,lng pair
"""

from __future__ import annotations

import json
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
- Use the provided tools to fetch real data — never invent or guess numbers under any circumstances.
- Grounding Rule: Always query system tools before stating numbers, ranks, or cell statistics.
- Location Rule: When the user mentions a locality, neighbourhood, or area name (e.g. Bandra, Andheri, Dadar, Kurla), ALWAYS use search_cells_by_location to find the relevant cells in that area first. Do NOT use get_top_cells or search_cells_by_condition without a location filter when the user specifies a place name.
- Out-of-Scope Rule: If a user asks non-environmental/non-urban questions (e.g., coding, recipes, general trivia, politics) or asks about locations outside Mumbai, politely decline and clarify your specific role as Mumbai's CitySense AI analyst.
- Be concise but insightful. Use clear structure with short paragraphs.
- Mumbai bounding box: lon 72.77–72.99°E, lat 18.89–19.27°N. If a location is outside this, state that it falls outside the system's 836-cell coverage area.
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


def _tool_get_top_cells(limit: int = 5, priority_filter: str | None = None, data: dict = {}) -> list[dict]:
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


def _matches_location(loc_query: str, geo: dict) -> bool:
    if not loc_query:
        return True
    q = loc_query.lower().strip()
    primary = (geo.get("primary_locality") or "").lower()
    secondaries = [s.lower() for s in geo.get("secondary_localities", [])]
    ward = (geo.get("ward") or "").lower()
    zone = (geo.get("zone") or "").lower()
    landmarks = [l.lower() for l in geo.get("nearest_landmarks", [])]

    return (
        q in primary or primary in q
        or any(q in s or s in q for s in secondaries)
        or q in ward or ward in q
        or q in zone
        or any(q in l or l in q for l in landmarks)
    )


def _matches_condition(cond_query: str, cell_id: str, data: dict) -> bool:
    if not cond_query:
        return True
    q = cond_query.lower().strip()
    ei = data.get("env_intel", {}).get(cell_id, {})
    fsi = data.get("fsi_data", {}).get(cell_id, {})
    iai = data.get("iai_data", {}).get(cell_id, {})
    burden = data.get("burden_data", {}).get(cell_id, {})
    plan = data.get("plans", {}).get(cell_id, {})

    detected = [c.lower() for c in ei.get("detected_conditions", [])]
    primary = (ei.get("primary_issue") or "").lower()
    secondary = (ei.get("secondary_issue") or "").lower()
    env_status = (ei.get("environmental_status") or "").lower()

    fsi_status = (fsi.get("flood_susceptibility_status") or "").lower()
    fsi_score = fsi.get("flood_susceptibility_score") or 0.0

    # 1. Flood / waterlogging check
    if any(term in q for term in ["flood", "waterlog", "drainage", "inundat", "fsi"]):
        return (
            fsi_status in ("severe", "high", "moderate")
            or fsi_score >= 50
            or "flood" in primary
            or any("flood" in d for d in detected)
        )

    # 2. Heat / UHI check
    if any(term in q for term in ["heat", "uhi", "hot", "temperature", "thermal"]):
        return (
            any("heat" in d or "uhi" in d for d in detected)
            or "heat" in primary
            or "heat" in secondary
        )

    # 3. Vegetation / Green check
    if any(term in q for term in ["veg", "green", "tree", "plant", "canopy", "park"]):
        return (
            any("veg" in d or "ecological" in d for d in detected)
            or "veg" in primary
            or "veg" in secondary
        )

    # 4. Built-up / Density check
    if any(term in q for term in ["built", "density", "concrete", "impervious"]):
        return (
            any("built" in d for d in detected)
            or "built" in primary
            or "built" in secondary
        )

    # 5. Generic substring matches across all metadata fields
    all_terms = (
        detected
        + [
            primary,
            secondary,
            env_status,
            fsi_status,
            (iai.get("iai_status") or "").lower(),
            (burden.get("burden_status") or "").lower(),
            (plan.get("planning_priority") or "").lower(),
            (plan.get("recommended_intervention") or "").lower(),
        ]
    )
    return any(q in t or t in q for t in all_terms if t)


def _tool_search_cells_by_condition(condition: str, limit: int = 10, location: str | None = None, data: dict = {}) -> list[dict]:
    matched = []
    geo_meta = data.get("geo_meta", {})
    all_cell_ids = set(data.get("cell_props", {}).keys()) | set(geo_meta.keys()) | set(data.get("env_intel", {}).keys())

    for cell_id in all_cell_ids:
        geo = geo_meta.get(cell_id, {})
        if location and not _matches_location(location, geo):
            continue
        if not _matches_condition(condition, cell_id, data):
            continue

        ei     = data.get("env_intel", {}).get(cell_id, {})
        plan   = data.get("plans", {}).get(cell_id, {})
        master = data.get("cell_props", {}).get(cell_id, {})
        fsi    = data.get("fsi_data", {}).get(cell_id, {})
        iai    = data.get("iai_data", {}).get(cell_id, {})
        burden = data.get("burden_data", {}).get(cell_id, {})

        matched.append({
            "cell_id":                     cell_id,
            "primary_locality":            geo.get("primary_locality", "Unknown"),
            "ward":                        geo.get("ward", "Unknown"),
            "primary_issue":               ei.get("primary_issue"),
            "detected_conditions":         ei.get("detected_conditions", []),
            "environmental_health":        ei.get("environmental_health"),
            "planning_priority":           plan.get("planning_priority"),
            "recommended_intervention":    plan.get("recommended_intervention"),
            "risk_score":                  master.get("risk_score"),
            "flood_susceptibility_score":  fsi.get("flood_susceptibility_score"),
            "flood_susceptibility_status": fsi.get("flood_susceptibility_status"),
            "iai_score":                   iai.get("iai_score"),
            "burden_score":                burden.get("burden_score"),
        })

    cond_lower = (condition or "").lower()
    if any(term in cond_lower for term in ["flood", "waterlog"]):
        matched.sort(key=lambda r: r.get("flood_susceptibility_score") or 0, reverse=True)
    else:
        matched.sort(key=lambda r: r.get("risk_score") or 0, reverse=True)

    return matched[:min(limit, 20)]


def _tool_search_cells_by_location(location: str, limit: int = 10, condition: str | None = None, data: dict = {}) -> list[dict]:
    """Find cells matching a locality/area name, optionally filtered by condition."""
    matched = []
    geo_meta = data.get("geo_meta", {})
    all_cell_ids = set(data.get("cell_props", {}).keys()) | set(geo_meta.keys())

    for cell_id in all_cell_ids:
        geo = geo_meta.get(cell_id, {})
        if not _matches_location(location, geo):
            continue
        if condition and not _matches_condition(condition, cell_id, data):
            continue

        ei     = data.get("env_intel", {}).get(cell_id, {})
        plan   = data.get("plans", {}).get(cell_id, {})
        master = data.get("cell_props", {}).get(cell_id, {})
        fsi    = data.get("fsi_data", {}).get(cell_id, {})
        iai    = data.get("iai_data", {}).get(cell_id, {})
        burden = data.get("burden_data", {}).get(cell_id, {})

        matched.append({
            "cell_id":                     cell_id,
            "primary_locality":            geo.get("primary_locality", "Unknown"),
            "ward":                        geo.get("ward", "Unknown"),
            "primary_issue":               ei.get("primary_issue"),
            "detected_conditions":         ei.get("detected_conditions", []),
            "environmental_health":        ei.get("environmental_health"),
            "planning_priority":           plan.get("planning_priority"),
            "recommended_intervention":    plan.get("recommended_intervention"),
            "risk_score":                  master.get("risk_score"),
            "flood_susceptibility_score":  fsi.get("flood_susceptibility_score"),
            "flood_susceptibility_status": fsi.get("flood_susceptibility_status"),
            "iai_score":                   iai.get("iai_score"),
            "burden_score":                burden.get("burden_score"),
        })

    cond_lower = (condition or "").lower()
    if any(term in cond_lower for term in ["flood", "waterlog"]):
        matched.sort(key=lambda r: r.get("flood_susceptibility_score") or 0, reverse=True)
    else:
        matched.sort(key=lambda r: r.get("risk_score") or 0, reverse=True)

    return matched[:min(limit, 20)]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def dispatch_tool(name: str, args: dict, data: dict) -> Any:
    if name == "get_city_stats":
        return _tool_get_city_stats(data)
    if name == "get_cell_details":
        return _tool_get_cell_details(args.get("cell_id", ""), data)
    if name == "get_top_cells":
        return _tool_get_top_cells(args.get("limit", 5), args.get("priority_filter"), data)
    if name == "get_ward_summary":
        return _tool_get_ward_summary(args.get("ward_name", ""), data)
    if name == "find_cell_by_coordinates":
        return _tool_find_cell_by_coordinates(float(args.get("lat", 0)), float(args.get("lon", 0)), data)
    if name == "search_cells_by_condition":
        return _tool_search_cells_by_condition(args.get("condition", ""), args.get("limit", 10), args.get("location"), data)
    if name == "search_cells_by_location":
        return _tool_search_cells_by_location(args.get("location", ""), args.get("limit", 10), args.get("condition"), data)
    return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# OpenAI-compatible tool schemas for OpenRouter
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_city_stats",
            "description": "Get city-wide aggregate statistics for Mumbai: average EHI, risk score, priority distribution, top environmental issues and interventions.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cell_details",
            "description": "Get the complete data bundle for a specific grid cell by cell_id (format r{row}_c{col}, e.g. r15_c8). Returns environmental health, planning profile, flood susceptibility, infrastructure access, and SHAP explanation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cell_id": {
                        "type": "string",
                        "description": "Cell ID in format r{row}_c{col}",
                    },
                },
                "required": ["cell_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_cells",
            "description": "Get top N cells ranked by priority score, optionally filtered by planning priority level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of cells (max 20, default 5)",
                    },
                    "priority_filter": {
                        "type": "string",
                        "description": "Optional: 'Critical', 'High', 'Medium', 'Low', or 'Very Low'",
                    },
                },
                "required": ["limit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ward_summary",
            "description": "Get aggregated planning summary for a Mumbai ward by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ward_name": {
                        "type": "string",
                        "description": "Name of the Mumbai ward",
                    },
                },
                "required": ["ward_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_cell_by_coordinates",
            "description": "Find the CitySense grid cell at given geographic coordinates and return its full analysis. Use this when the user provides a Google Maps link or any lat/lng coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {
                        "type": "number",
                        "description": "Latitude in decimal degrees",
                    },
                    "lon": {
                        "type": "number",
                        "description": "Longitude in decimal degrees",
                    },
                },
                "required": ["lat", "lon"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_cells_by_condition",
            "description": "Find all cells matching a specific environmental condition (e.g. 'Urban Heat Island', 'Low Vegetation', 'Flood Susceptibility', 'High Built-up Density'). Optionally filter by location/area name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "condition": {
                        "type": "string",
                        "description": "Environmental condition to search for",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10, max 20)",
                    },
                    "location": {
                        "type": "string",
                        "description": "Optional: locality or area name to filter by (e.g. 'Bandra', 'Andheri', 'Dadar')",
                    },
                },
                "required": ["condition", "limit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_cells_by_location",
            "description": "Find all grid cells in or near a specific Mumbai locality/area/neighbourhood by name. Returns cells with their environmental data, flood susceptibility, and risk scores. Use this when the user mentions a place name like 'Bandra', 'Andheri', 'Dadar', 'Kurla', etc. Optionally filter by an environmental condition.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Locality or area name (e.g. 'Bandra', 'Andheri West', 'Kurla')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10, max 20)",
                    },
                    "condition": {
                        "type": "string",
                        "description": "Optional: environmental condition to filter by (e.g. 'Flood Susceptibility', 'Urban Heat Island')",
                    },
                },
                "required": ["location"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Main chat handler — OpenRouter / OpenAI SDK
# ---------------------------------------------------------------------------

def handle_chat(request: ChatRequest, app_data: dict) -> ChatResponse:
    """
    Process a chat request using OpenRouter with OpenAI-compatible function-calling.
    """
    from openai import OpenAI

    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    # Check for missing or placeholder keys
    if not api_key or "your-openrouter-key-here" in api_key or "your-key-here" in api_key:
        return ChatResponse(
            reply="⚠️ **OpenRouter API Key is not configured yet.**\n\nPlease open `backend/.env` and replace `OPENROUTER_API_KEY=sk-or-v1-your-openrouter-key-here` with your actual API key from [OpenRouter.ai](https://openrouter.ai/keys)."
        )

    model_name = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://citysense.app",
            "X-Title": "CitySense AI",
        },
    )

    # Pre-process last user message: extract coords from Maps URLs
    messages_input = request.messages
    last_msg_content = messages_input[-1].content
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

    # Build OpenAI message history
    history: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in messages_input[:-1]:
        history.append({"role": msg.role, "content": msg.content})
    history.append({"role": "user", "content": last_msg_content})

    resolved_cell_id: str | None = None

    # Agentic loop — keep calling until text response
    for _ in range(8):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=history,
                tools=TOOLS,
                temperature=0.3,
                max_tokens=1500,
            )
        except Exception as exc:
            err_str = str(exc)
            if "402" in err_str or "credits" in err_str.lower() or "payment" in err_str.lower():
                return ChatResponse(
                    reply="⚠️ **OpenRouter Credit Limit Reached (402)**\n\nYour OpenRouter account requires credits. Please check your balance or upgrade at [OpenRouter.ai Settings](https://openrouter.ai/settings/credits)."
                )
            if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower() or "resource_exhausted" in err_str.lower():
                return ChatResponse(
                    reply="⚠️ The AI assistant is currently experiencing a rate limit or high demand. Please wait a few seconds and try again."
                )
            if "401" in err_str or "unauthorized" in err_str.lower() or "invalid" in err_str.lower():
                return ChatResponse(
                    reply="⚠️ Invalid OpenRouter API Key. Please verify `OPENROUTER_API_KEY` in `backend/.env`."
                )
            return ChatResponse(
                reply="⚠️ The AI assistant service is temporarily unavailable. Please try your request again in a moment."
            )

        choice = response.choices[0]
        msg = choice.message

        # Append assistant message to history
        msg_dict = msg.model_dump(exclude_none=True)
        history.append(msg_dict)

        # Check for tool calls
        if not msg.tool_calls:
            break  # Final text reply

        # Execute tool calls and collect results
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except Exception:
                fn_args = {}

            result = dispatch_tool(fn_name, fn_args, app_data)

            # Track resolved cell
            if fn_name in ("find_cell_by_coordinates", "get_cell_details"):
                cid = result.get("cell_id") if isinstance(result, dict) else None
                if cid and "error" not in result:
                    resolved_cell_id = cid
            elif fn_name in ("get_top_cells", "search_cells_by_condition", "search_cells_by_location"):
                if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                    cid = result[0].get("cell_id")
                    if cid and not resolved_cell_id:
                        resolved_cell_id = cid

            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    reply_text = msg.content or ""
    if not reply_text:
        reply_text = "I encountered an issue generating a response. Please try again."

    # Fallback: if no resolved cell ID yet, check if reply mentions a cell ID like r16_c10
    if not resolved_cell_id and reply_text:
        cell_match = re.search(r"\br\d+_c\d+\b", reply_text)
        if cell_match:
            resolved_cell_id = cell_match.group(0)

    return ChatResponse(reply=reply_text, cell_id=resolved_cell_id)
