// ============================================================
// SearchBar.tsx — Global Locality, Ward & Cell ID Autocomplete Search
// ============================================================

import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { Search, MapPin, Building, Target, X, ChevronRight } from 'lucide-react'
import { useCells } from '@/api/citysense'
import { useStore } from '@/store/useStore'

interface SearchItem {
  cellId: string
  locality: string
  ward: string
  landmarks: string[]
  ehi: number | null
  priority: string | null
  risk: number | null
  lng: number
  lat: number
}

function sanitizeLocality(rawLocality?: string | null, ward?: string | null, cellId?: string): string {
  if (!rawLocality || typeof rawLocality !== 'string') return ward ? `${ward} Area` : cellId || 'Mumbai'
  const trimmed = rawLocality.trim()
  if (
    trimmed.toLowerCase().includes('error') ||
    trimmed.toLowerCase() === 'unknown' ||
    trimmed.toLowerCase() === 'null' ||
    trimmed.toLowerCase() === 'undefined'
  ) {
    return ward ? `${ward} Area` : cellId || 'Mumbai'
  }
  return trimmed
}

export function SearchBar() {
  const { data: geojson } = useCells()
  const setSelectedCellId = useStore((s) => s.setSelectedCellId)
  const selectedCellId = useStore((s) => s.selectedCellId)

  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [highlightIndex, setHighlightIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Pre-process cells into searchable items
  const items = useMemo<SearchItem[]>(() => {
    if (!geojson) return []
    const result: SearchItem[] = []

    for (const f of geojson.features) {
      const p = f.properties
      if (!p || !p.cell_id || f.geometry.type !== 'Polygon') continue

      const coords = f.geometry.coordinates[0]
      const n = coords.length
      const lng = coords.reduce((s, c) => s + c[0], 0) / n
      const lat = coords.reduce((s, c) => s + c[1], 0) / n

      const cleanLocality = sanitizeLocality(p.primary_locality, p.ward, String(p.cell_id))

      result.push({
        cellId: String(p.cell_id),
        locality: cleanLocality,
        ward: String(p.ward || ''),
        landmarks: Array.isArray(p.nearest_landmarks) ? p.nearest_landmarks : [],
        ehi: typeof p.environmental_health === 'number' ? p.environmental_health : null,
        priority: typeof p.planning_priority === 'string' ? p.planning_priority : null,
        risk: typeof p.risk_score === 'number' ? p.risk_score : null,
        lng,
        lat,
      })
    }

    return result
  }, [geojson])

  // Filter items matching query
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []

    return items
      .filter((item) => {
        if (item.cellId.toLowerCase().includes(q)) return true
        if (item.locality.toLowerCase().includes(q) && !item.locality.toLowerCase().includes('error')) return true
        if (item.ward.toLowerCase().includes(q)) return true
        if (item.landmarks.some((lm) => lm.toLowerCase().includes(q))) return true
        return false
      })
      .slice(0, 8)
  }, [items, query])

  // Global keyboard shortcut '/' or 'Ctrl+K'
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        (e.key === '/' || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k')) &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault()
        inputRef.current?.focus()
      } else if (e.key === 'Escape' && isOpen) {
        setIsOpen(false)
        inputRef.current?.blur()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = useCallback(
    (item: SearchItem) => {
      setSelectedCellId(item.cellId)
      setQuery(item.locality && item.locality !== 'Unknown' ? `${item.locality} (${item.cellId})` : item.cellId)
      setIsOpen(false)
      inputRef.current?.blur()
    },
    [setSelectedCellId],
  )

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || filtered.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightIndex((prev) => (prev + 1) % filtered.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightIndex((prev) => (prev - 1 + filtered.length) % filtered.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filtered[highlightIndex]) {
        handleSelect(filtered[highlightIndex])
      }
    }
  }

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: 320,
        maxWidth: '100%',
        zIndex: 250,
      }}
    >
      {/* Input Field */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          padding: '4px 10px',
          borderRadius: 8,
          background: 'rgba(5, 16, 38, 0.85)',
          border: isOpen
            ? '1px solid var(--glow-cyan)'
            : '1px solid rgba(0, 200, 255, 0.22)',
          boxShadow: isOpen
            ? '0 0 14px rgba(0, 212, 255, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.05)'
            : '0 2px 8px rgba(0, 0, 0, 0.3)',
          transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <Search size={14} color={isOpen ? 'var(--glow-cyan)' : 'var(--text-muted)'} style={{ flexShrink: 0 }} />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setIsOpen(true)
            setHighlightIndex(0)
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search locality, ward, or cell ID…"
          style={{
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--text-primary)',
            fontSize: 11,
            fontFamily: 'var(--font-ui)',
            width: '100%',
          }}
        />

        {query ? (
          <button
            type="button"
            onClick={() => {
              setQuery('')
              setIsOpen(false)
              inputRef.current?.focus()
            }}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              padding: 2,
            }}
          >
            <X size={12} />
          </button>
        ) : (
          <kbd
            className="font-mono"
            style={{
              fontSize: 9,
              color: 'var(--text-muted)',
              padding: '1px 5px',
              borderRadius: 4,
              background: 'rgba(0, 212, 255, 0.06)',
              border: '1px solid rgba(0, 212, 255, 0.15)',
            }}
          >
            /
          </kbd>
        )}
      </div>

      {/* Autocomplete Dropdown */}
      {isOpen && filtered.length > 0 && (
        <div
          className="panel animate-fade-in"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            right: 0,
            borderRadius: 10,
            background: 'linear-gradient(135deg, rgba(6, 18, 42, 0.98) 0%, rgba(3, 10, 28, 0.98) 100%)',
            border: '1px solid rgba(0, 212, 255, 0.35)',
            boxShadow: '0 16px 40px rgba(0, 4, 16, 0.85), 0 0 20px rgba(0, 212, 255, 0.15)',
            backdropFilter: 'blur(20px)',
            overflow: 'hidden',
            maxHeight: 340,
            overflowY: 'auto',
          }}
        >
          <div
            style={{
              padding: '6px 10px',
              fontSize: 9,
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
              borderBottom: '1px solid rgba(0, 200, 255, 0.1)',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
            }}
          >
            Matching Locations ({filtered.length})
          </div>

          {filtered.map((item, idx) => {
            const isHighlighted = idx === highlightIndex
            const isCurrentSelected = selectedCellId === item.cellId
            const displayName = item.locality && item.locality !== 'Unknown' ? item.locality : item.cellId

            return (
              <div
                key={item.cellId}
                onClick={() => handleSelect(item)}
                onMouseEnter={() => setHighlightIndex(idx)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  cursor: 'pointer',
                  borderBottom: '1px solid rgba(0, 200, 255, 0.06)',
                  background: isHighlighted
                    ? 'rgba(0, 212, 255, 0.14)'
                    : isCurrentSelected
                      ? 'rgba(0, 212, 255, 0.08)'
                      : 'transparent',
                  transition: 'background 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                  <MapPin size={13} color="var(--glow-cyan)" style={{ flexShrink: 0 }} />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>
                        {displayName}
                      </span>
                      <span
                        className="font-mono"
                        style={{
                          fontSize: 10,
                          color: 'var(--glow-cyan)',
                          background: 'rgba(0, 212, 255, 0.08)',
                          padding: '0 4px',
                          borderRadius: 3,
                        }}
                      >
                        {item.cellId}
                      </span>
                    </div>

                    {item.ward && (
                      <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 2 }}>
                        {item.ward} {item.landmarks.length > 0 && `· ${item.landmarks[0]}`}
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {item.ehi !== null && (
                    <span
                      className="font-mono"
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: item.ehi >= 60 ? 'var(--glow-green)' : item.ehi >= 45 ? 'var(--glow-amber)' : 'var(--glow-red)',
                        background: 'rgba(0,0,0,0.3)',
                        padding: '1px 5px',
                        borderRadius: 3,
                      }}
                    >
                      EHI {item.ehi.toFixed(0)}
                    </span>
                  )}
                  <ChevronRight size={13} color="var(--text-muted)" />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
