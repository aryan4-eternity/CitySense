# CitySense — React Command-Center Dashboard
## Implementation Guide

---

## Overview

This document describes the full implementation of the CitySense React frontend and FastAPI backend.
The Python pipeline (`processing/`, `environment/`, `planning/`) is **not modified**.
The new dashboard replaces Streamlit with a full-screen WebGL command-center UI.

---

## Architecture

```
CitySense/city_sense/
├── backend/                     ← FastAPI REST API
│   ├── main.py                  ← 4 endpoints, pure file serving
│   └── requirements.txt
├── frontend/                    ← Vite + React + TypeScript
│   ├── package.json
│   ├── vite.config.ts           ← proxy /api → localhost:8000
│   ├── tailwind.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx              ← root composition
│       ├── store/
│       │   └── useStore.ts      ← Zustand: selectedCellId, activeLayer
│       ├── api/
│       │   └── citysense.ts     ← React Query hooks
│       ├── types/
│       │   └── index.ts         ← TypeScript interfaces
│       ├── components/
│       │   ├── Map/
│       │   │   ├── DeckMap.tsx  ← Deck.gl WebGL map
│       │   │   └── layers.ts    ← Layer factory functions
│       │   ├── Header/
│       │   │   └── Header.tsx
│       │   ├── StatsPanel/
│       │   │   └── StatsPanel.tsx
│       │   ├── CellPanel/
│       │   │   ├── CellPanel.tsx
│       │   │   ├── EnvTab.tsx
│       │   │   ├── PlanningTab.tsx
│       │   │   └── RawTab.tsx
│       │   ├── LayerBar/
│       │   │   └── LayerBar.tsx
│       │   └── ui/
│       │       ├── GlowBadge.tsx
│       │       ├── IndicatorBar.tsx
│       │       └── ScanLine.tsx
│       └── styles/
│           └── globals.css
├── data/                        ← existing pipeline outputs (unchanged)
│   ├── cells_master.geojson
│   ├── environmental_intelligence.json
│   ├── planning_profiles.json
│   └── cell_explanations.json
└── IMPLEMENTATION.md            ← this file
```

---

## Tech Stack

| Layer | Library | Version | Purpose |
|---|---|---|---|
| Frontend bundler | Vite | 6.x | Fast dev server + build |
| UI framework | React | 19.x | Component tree |
| Language | TypeScript | 5.x | Type safety |
| Map | Deck.gl + react-map-gl | 9.x | WebGL choropleth |
| Base map tiles | MapLibre GL | 5.x | Free, no API key |
| State | Zustand | 5.x | Selected cell + active layer |
| Data fetching | TanStack React Query | 5.x | Caching + loading states |
| Styling | Tailwind CSS v4 | 4.x | Utility classes |
| Charts | Recharts | 2.x | Indicator bars + gauges |
| Icons | Lucide React | latest | Clean icon set |
| Backend | FastAPI + Uvicorn | latest | REST API |

---

## Design System

### Colour Palette

| Token | Hex | Usage |
|---|---|---|
| `--bg-base` | `#050d1a` | Full page background |
| `--bg-panel` | `rgba(8,20,40,0.85)` | Floating panel background |
| `--bg-card` | `rgba(12,30,60,0.9)` | Card background |
| `--border` | `rgba(0,180,255,0.15)` | Panel borders |
| `--glow-cyan` | `#00d4ff` | Primary accent, title, active states |
| `--glow-green` | `#00ff9f` | Healthy / low risk / good EHI |
| `--glow-red` | `#ff3b5c` | Critical / high risk |
| `--glow-amber` | `#ffb340` | Medium priority / warnings |
| `--text-primary` | `#e2f0ff` | Main body text |
| `--text-secondary` | `#7aa8cc` | Labels, captions |

### Typography
- Headers: `JetBrains Mono` / `Fira Code` / `monospace` — large, spaced, cyan glow
- Body: `Inter` / `system-ui` — readable, clean
- Numbers: monospace with `letter-spacing: 0.1em`

### Animations

| Name | Effect | Duration | Trigger |
|---|---|---|---|
| `scanline` | Cyan line sweeps top→bottom | 8s loop | Always |
| `pulse-glow` | Red box-shadow oscillates | 2s loop | Critical cells |
| `border-glow` | Panel border brightens | 3s loop | Selected cell |
| `flicker` | Opacity flicker | 0.3s once | On data load |
| `slide-in-left` | Panel translates in from left | 0.6s once | StatsPanel mount |
| `slide-in-right` | Panel translates in from right | 0.4s once | CellPanel open |
| `fade-in` | Opacity 0→1 | 0.3s once | Any new content |

---

## Map Layers

| Layer key | Column | Colour scale | Description |
|---|---|---|---|
| `environmental_health` | EHI 0–100 | Red→Green | Default layer |
| `risk_score` | 0–100 | Green→Red | PCA risk |
| `mean_lst` | °C | Blue→Red | Surface temperature |
| `mean_ndvi` | -1–1 | Brown→Green | Vegetation |
| `mean_ndbi` | -1–1 | Green→Purple | Built-up density |
| `uhi_intensity` | °C | Blue→Orange | UHI intensity |
| `planning_priority_score` | 0–100 | Green→Red | Planning priority |
| `cluster` | categorical | Tab10 palette | Urban typologies |

---

## API Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/api/cells` | Full GeoJSON for Deck.gl |
| GET | `/api/cell/{cell_id}` | master + environment + planning + explanation bundle |
| GET | `/api/rankings` | All cells sorted by priority_score desc |
| GET | `/api/stats` | City-wide aggregates (avg EHI, priority counts, top issues) |

---

## How to Run

### Prerequisites
- Node.js v18+ (currently v24.15.0 ✓)
- Python 3.10+ with project virtualenv active

### Install

```bash
# Backend
pip install fastapi "uvicorn[standard]"

# Frontend
cd frontend
npm install
```

### Development

```bash
# Terminal 1 — backend (from project root)
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
# → http://localhost:5173
```

### Production build

```bash
cd frontend
npm run build
# Output: frontend/dist/  (serve with any static file server)
```

---

## How to Add a New Map Layer

1. Add the column to `cells_master.geojson` (via your pipeline)
2. Add an entry to `LAYER_CONFIG` in `frontend/src/components/Map/layers.ts`
3. Add the layer key and display name to `LAYERS` array in `frontend/src/components/LayerBar/LayerBar.tsx`

No other changes needed.

---

## How to Add a New Intervention

Edit `planning/intervention_catalog.yaml` only — no frontend or backend changes required.
The planning profiles JSON is regenerated by running:
```bash
python -m planning.generate_planning_profiles
```

---

## Phase Compatibility

| Data file | Producer | Consumer |
|---|---|---|
| `cells_master.geojson` | Pipeline (PCA/SHAP) | Backend `/api/cells`, `/api/cell/:id` |
| `environmental_intelligence.json` | Phase 2 | Backend `/api/cell/:id`, `/api/stats` |
| `planning_profiles.json` | Phase 3 | Backend `/api/cell/:id`, `/api/rankings`, `/api/stats` |
| `cell_explanations.json` | Pipeline | Backend `/api/cell/:id` |

---

## File Change Summary (implementation only)

| File | Status | Notes |
|---|---|---|
| `backend/main.py` | NEW | FastAPI server |
| `backend/requirements.txt` | NEW | fastapi, uvicorn |
| `frontend/*` | NEW | Full React app |
| `IMPLEMENTATION.md` | NEW | This file |
| `data/*` | UNCHANGED | Pipeline outputs |
| `processing/*` | UNCHANGED | ML pipeline |
| `environment/*` | UNCHANGED | Phase 2 |
| `planning/*` | UNCHANGED | Phase 3 |
| `dashboard/app.py` | UNCHANGED | Kept as fallback |
