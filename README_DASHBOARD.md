# CitySense — React Command-Center Dashboard

## Prerequisites

- **Node.js** v18+ (v24.x recommended)
- **Python** 3.10+ with project virtualenv active
- **pip packages**: `fastapi`, `uvicorn[standard]`

## Install

```bash
# Backend
pip install fastapi "uvicorn[standard]"

# Frontend
cd city_sense/frontend
npm install
```

## Development

Open **two terminals** from the `city_sense/` directory:

```bash
# Terminal 1 — Backend API (port 8000)
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Frontend dev server (port 5173)
cd frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

The Vite dev server proxies `/api` requests to the FastAPI backend automatically.

## Production Build

```bash
cd frontend
npm run build
# Output: frontend/dist/  (serve with any static file server)
```

## Architecture

```
frontend/src/
├── main.tsx                      ← Entry point
├── App.tsx                       ← Root composition + QueryClient
├── store/useStore.ts             ← Zustand: selectedCell, activeLayer, tooltip
├── api/citysense.ts              ← React Query hooks (useCells, useCell, etc.)
├── types/index.ts                ← TypeScript interfaces
├── styles/globals.css            ← Design system + animations
└── components/
    ├── Map/
    │   ├── DeckMap.tsx           ← Deck.gl WebGL map + tooltip + hotspots
    │   └── layers.ts            ← Layer factory functions + color scales
    ├── Header/Header.tsx         ← Top bar: title, clock, status
    ├── StatsPanel/StatsPanel.tsx ← Left panel: city stats + priority + issues
    ├── CellPanel/
    │   ├── CellPanel.tsx         ← Right panel: tabbed cell detail view
    │   ├── EnvTab.tsx            ← Environmental Health tab
    │   ├── PlanningTab.tsx       ← Planning Intelligence tab
    │   └── RawTab.tsx            ← Raw indicators + SHAP tab
    ├── LayerBar/LayerBar.tsx     ← Bottom layer switcher
    └── ui/ScanLine.tsx           ← Scan-line animation overlay
```

## Controls

| Action | Effect |
|---|---|
| Hover cell | Tooltip shows cell ID, EHI, priority, LST |
| Click cell | Right panel opens with full cell detail (3 tabs) |
| Click layer button | Map re-renders with new color scale |
| Click priority cell in left panel | Selects that cell on the map |
| × button on right panel | Closes cell detail view |
