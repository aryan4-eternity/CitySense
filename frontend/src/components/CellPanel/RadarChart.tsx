// ============================================================
// RadarChart.tsx — 6-Axis Multi-Hazard Visual Fingerprint
// Standardized [0-100] scale comparing Cell vs Citywide Average
// ============================================================

import { useState, useMemo } from 'react'
import type { CellBundle } from '@/types'

interface RadarAxis {
  key: string
  label: string
  shortLabel: string
  cellVal: number
  cityAvgVal: number
  unit: string
  rawCellText: string
  rawAvgText: string
}

interface RadarChartProps {
  cell: CellBundle
}

export function RadarChart({ cell }: RadarChartProps) {
  const [hoveredAxis, setHoveredAxis] = useState<RadarAxis | null>(null)

  const axes = useMemo<RadarAxis[]>(() => {
    const m = cell.master
    const lst = typeof m.mean_lst === 'number' ? m.mean_lst : 37.0
    const ndvi = typeof m.mean_ndvi === 'number' ? m.mean_ndvi : 0.18
    const ndbi = typeof m.mean_ndbi === 'number' ? m.mean_ndbi : 0.05
    const dem = typeof m.mean_dem === 'number' ? m.mean_dem : 15.0
    const fsi = cell.flood?.flood_susceptibility_score ?? 50.0
    const iai = cell.access?.iai_score ?? 55.0

    // Standardize 0 - 100 (where 100 = safest / most resilient / best access)
    // 1. Thermal Safety (28°C -> 100, 48°C -> 0)
    const normLst = Math.max(0, Math.min(100, (1 - (lst - 28) / (48 - 28)) * 100))
    // 2. Vegetation Buffer (-0.15 -> 0, 0.65 -> 100)
    const normNdvi = Math.max(0, Math.min(100, ((ndvi - (-0.15)) / (0.65 - (-0.15))) * 100))
    // 3. Perviousness / Low Density (-0.25 -> 100, 0.35 -> 0)
    const normNdbi = Math.max(0, Math.min(100, (1 - (ndbi - (-0.25)) / (0.35 - (-0.25))) * 100))
    // 4. Elevation (0m -> 0, 80m -> 100)
    const normDem = Math.max(0, Math.min(100, (dem / 80) * 100))
    // 5. Flood Resilience (0 -> 100, 100 -> 0)
    const normFsi = Math.max(0, Math.min(100, 100 - fsi))
    // 6. Civic Access (0 -> 0, 100 -> 100)
    const normIai = Math.max(0, Math.min(100, iai))

    return [
      {
        key: 'thermal',
        label: 'Thermal Safety',
        shortLabel: 'Thermal',
        cellVal: normLst,
        cityAvgVal: 55, // City avg LST ~37°C
        unit: '°C',
        rawCellText: `${lst.toFixed(1)}°C`,
        rawAvgText: '37.1°C',
      },
      {
        key: 'green',
        label: 'Green Cover',
        shortLabel: 'Canopy',
        cellVal: normNdvi,
        cityAvgVal: 41, // City avg NDVI ~0.18
        unit: 'NDVI',
        rawCellText: ndvi.toFixed(2),
        rawAvgText: '0.18',
      },
      {
        key: 'pervious',
        label: 'Perviousness',
        shortLabel: 'Pervious',
        cellVal: normNdbi,
        cityAvgVal: 50, // City avg NDBI ~0.05
        unit: 'NDBI',
        rawCellText: ndbi.toFixed(2),
        rawAvgText: '0.05',
      },
      {
        key: 'elevation',
        label: 'Elevation Buffer',
        shortLabel: 'Elevation',
        cellVal: normDem,
        cityAvgVal: 32, // City avg DEM ~18m
        unit: 'm',
        rawCellText: `${dem.toFixed(0)} m`,
        rawAvgText: '18 m',
      },
      {
        key: 'flood',
        label: 'Flood Resilience',
        shortLabel: 'Flood Safe',
        cellVal: normFsi,
        cityAvgVal: 52, // City avg FSI ~48
        unit: '/100',
        rawCellText: `${(100 - fsi).toFixed(0)}/100`,
        rawAvgText: '52/100',
      },
      {
        key: 'access',
        label: 'Civic Access',
        shortLabel: 'Access',
        cellVal: normIai,
        cityAvgVal: 54, // City avg IAI ~54
        unit: '/100',
        rawCellText: `${iai.toFixed(0)}/100`,
        rawAvgText: '54/100',
      },
    ]
  }, [cell])

  // SVG Geometry constants
  const size = 260
  const center = size / 2
  const maxRadius = 90
  const levels = [0.25, 0.5, 0.75, 1.0]

  // Calculate polygon points for a given dataset
  const getPoints = (getValue: (axis: RadarAxis) => number) => {
    return axes
      .map((axis, i) => {
        const angle = (Math.PI * 2 * i) / axes.length - Math.PI / 2
        const r = (getValue(axis) / 100) * maxRadius
        const x = center + r * Math.cos(angle)
        const y = center + r * Math.sin(angle)
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }

  const cellPoints = getPoints((a) => a.cellVal)
  const avgPoints = getPoints((a) => a.cityAvgVal)

  return (
    <div
      style={{
        borderRadius: 10,
        background: 'rgba(5, 16, 38, 0.65)',
        border: '1px solid rgba(0, 200, 255, 0.18)',
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        position: 'relative',
      }}
    >
      <div
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 4,
        }}
      >
        <span
          className="text-cyber"
          style={{ fontSize: 10, color: 'var(--glow-cyan)', letterSpacing: '0.08em' }}
        >
          6-AXIS MULTI-HAZARD FINGERPRINT
        </span>
        <span
          className="font-mono"
          style={{ fontSize: 9, color: 'var(--text-muted)' }}
        >
          Outer = 100% (Safest)
        </span>
      </div>

      {/* SVG Canvas */}
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ overflow: 'visible' }}
      >
        {/* Concentric Grid Hexagons */}
        {levels.map((lvl) => {
          const gridPoints = axes
            .map((_, i) => {
              const angle = (Math.PI * 2 * i) / axes.length - Math.PI / 2
              const r = lvl * maxRadius
              const x = center + r * Math.cos(angle)
              const y = center + r * Math.sin(angle)
              return `${x.toFixed(1)},${y.toFixed(1)}`
            })
            .join(' ')

          return (
            <polygon
              key={lvl}
              points={gridPoints}
              fill="none"
              stroke="rgba(0, 212, 255, 0.12)"
              strokeWidth="1"
              strokeDasharray={lvl === 1 ? 'none' : '2 2'}
            />
          )
        })}

        {/* Axis Spokes from center to outer vertex */}
        {axes.map((axis, i) => {
          const angle = (Math.PI * 2 * i) / axes.length - Math.PI / 2
          const x2 = center + maxRadius * Math.cos(angle)
          const y2 = center + maxRadius * Math.sin(angle)
          const labelDist = maxRadius + 18
          const lx = center + labelDist * Math.cos(angle)
          const ly = center + labelDist * Math.sin(angle) + 3

          const isHovered = hoveredAxis?.key === axis.key

          return (
            <g key={axis.key}>
              <line
                x1={center}
                y1={center}
                x2={x2}
                y2={y2}
                stroke="rgba(0, 212, 255, 0.16)"
                strokeWidth="1"
              />
              <text
                x={lx}
                y={ly}
                textAnchor="middle"
                fontSize="9"
                fontFamily="var(--font-mono)"
                fontWeight={isHovered ? 700 : 500}
                fill={isHovered ? 'var(--glow-cyan)' : 'var(--text-secondary)'}
                style={{ cursor: 'pointer', transition: 'fill 0.2s' }}
                onMouseEnter={() => setHoveredAxis(axis)}
                onMouseLeave={() => setHoveredAxis(null)}
              >
                {axis.shortLabel}
              </text>
            </g>
          )
        })}

        {/* 1. Mumbai Average Baseline Polygon (Amber Dashed) */}
        <polygon
          points={avgPoints}
          fill="rgba(255, 180, 50, 0.08)"
          stroke="rgba(255, 180, 50, 0.6)"
          strokeWidth="1.5"
          strokeDasharray="3 3"
        />

        {/* 2. Selected Cell Polygon (Cyan Filled & Glowing) */}
        <polygon
          points={cellPoints}
          fill="rgba(0, 212, 255, 0.28)"
          stroke="var(--glow-cyan)"
          strokeWidth="2"
          style={{ filter: 'drop-shadow(0 0 6px rgba(0, 212, 255, 0.4))' }}
        />

        {/* Vertex Markers */}
        {axes.map((axis, i) => {
          const angle = (Math.PI * 2 * i) / axes.length - Math.PI / 2
          const r = (axis.cellVal / 100) * maxRadius
          const cx = center + r * Math.cos(angle)
          const cy = center + r * Math.sin(angle)
          const isHovered = hoveredAxis?.key === axis.key

          return (
            <circle
              key={axis.key}
              cx={cx}
              cy={cy}
              r={isHovered ? 5 : 3.5}
              fill="var(--glow-cyan)"
              stroke="#041226"
              strokeWidth="1.5"
              style={{ cursor: 'pointer', transition: 'all 0.15s' }}
              onMouseEnter={() => setHoveredAxis(axis)}
              onMouseLeave={() => setHoveredAxis(null)}
            />
          )
        })}
      </svg>

      {/* Dynamic Hover Tooltip / Detail Box */}
      <div
        style={{
          width: '100%',
          marginTop: 6,
          padding: '6px 10px',
          borderRadius: 6,
          background: 'rgba(0, 212, 255, 0.06)',
          border: '1px solid rgba(0, 212, 255, 0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
        }}
      >
        {hoveredAxis ? (
          <>
            <span style={{ color: 'var(--glow-cyan)', fontWeight: 700 }}>
              {hoveredAxis.label}
            </span>
            <div style={{ display: 'flex', gap: 10 }}>
              <span style={{ color: 'var(--text-bright)' }}>
                Cell: <strong>{hoveredAxis.rawCellText}</strong> ({hoveredAxis.cellVal.toFixed(0)}%)
              </span>
              <span style={{ color: 'var(--glow-amber)' }}>
                City Avg: {hoveredAxis.rawAvgText}
              </span>
            </div>
          </>
        ) : (
          <div
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-around',
              fontSize: 10,
              color: 'var(--text-secondary)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 2,
                  background: 'var(--glow-cyan)',
                  display: 'inline-block',
                }}
              />
              <span style={{ color: 'var(--text-bright)', fontWeight: 600 }}>This Cell Profile</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span
                style={{
                  width: 12,
                  height: 2,
                  borderBottom: '2px dashed var(--glow-amber)',
                  display: 'inline-block',
                }}
              />
              <span style={{ color: 'var(--glow-amber)', fontWeight: 600 }}>Mumbai City Average</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
