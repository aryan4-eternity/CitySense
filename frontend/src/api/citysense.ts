import { useQuery } from '@tanstack/react-query'
import type { CellBundle, CityStats, RankingRow } from '@/types'

const BASE = '/api'

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
    const res = await fetch(`${BASE.replace('/api', '')}/health`)
    return res.ok
  } catch {
    return false
  }
}
