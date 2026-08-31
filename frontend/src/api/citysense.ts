import { useQuery } from '@tanstack/react-query'
import type { CellBundle, CityStats, RankingRow, ChatRequest, ChatResponse, SatelliteStatusResponse, SatelliteSyncResponse } from '@/types'

const BASE = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL.replace(/\/$/, '') : '/api'

// ------------------------------------------------------------------
// Fetch helpers
// ------------------------------------------------------------------
async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

// ------------------------------------------------------------------
// City-wide statistics  (cached indefinitely — static for a session)
// ------------------------------------------------------------------
export function useCityStats() {
  return useQuery<CityStats>({
    queryKey: ['stats'],
    queryFn: () => fetchJSON<CityStats>('/stats'),
    staleTime: Infinity,
    retry: 3,
  })
}

// ------------------------------------------------------------------
// Full GeoJSON for Deck.gl  (large — cached indefinitely)
// ------------------------------------------------------------------
export function useCells() {
  return useQuery<GeoJSON.FeatureCollection>({
    queryKey: ['cells-landmass-only-v2'],
    queryFn: () => fetchJSON<GeoJSON.FeatureCollection>('/cells'),
    staleTime: Infinity,
    retry: 3,
  })
}

// ------------------------------------------------------------------
// Single cell bundle  (fetched on selection)
// ------------------------------------------------------------------
export function useCell(cellId: string | null) {
  return useQuery<CellBundle>({
    queryKey: ['cell', cellId],
    queryFn: () => fetchJSON<CellBundle>(`/cell/${cellId}`),
    enabled: cellId !== null,
    staleTime: Infinity,
    retry: 2,
  })
}

// ------------------------------------------------------------------
// Rankings  (sorted by priority_score desc)
// ------------------------------------------------------------------
export function useRankings() {
  return useQuery<RankingRow[]>({
    queryKey: ['rankings'],
    queryFn: () => fetchJSON<RankingRow[]>('/rankings'),
    staleTime: Infinity,
    retry: 3,
  })
}

// ------------------------------------------------------------------
// Health check  (used by Header to show API status)
// ------------------------------------------------------------------
export async function checkHealth(): Promise<boolean> {
  try {
    const healthUrl = BASE.endsWith('/api') ? `${BASE.slice(0, -4)}/health` : `${BASE}/health`
    const res = await fetch(healthUrl)
    return res.ok
  } catch {
    return false
  }
}

// ------------------------------------------------------------------
// Satellite feeds telemetry & resilient sync
// ------------------------------------------------------------------
export function useSatelliteStatus() {
  return useQuery<SatelliteStatusResponse>({
    queryKey: ['satellite-status'],
    queryFn: () => fetchJSON<SatelliteStatusResponse>('/satellite-status'),
    staleTime: 60_000,
    retry: 2,
  })
}

export async function syncSatelliteFeeds(): Promise<SatelliteSyncResponse> {
  const res = await fetch(`${BASE}/satellite-sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail ?? `Satellite sync failed: ${res.status}`)
  }
  return res.json() as Promise<SatelliteSyncResponse>
}

// ------------------------------------------------------------------
// Chat  (streaming-style: single POST, returns full reply)
// ------------------------------------------------------------------
export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail ?? `Chat API error: ${res.status}`)
  }
  return res.json() as Promise<ChatResponse>
}

