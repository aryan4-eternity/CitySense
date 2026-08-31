// ============================================================
// ScanLine — Command-center scan-line effect
// A thin semi-transparent horizontal line that sweeps top → bottom
// every 8 seconds. Purely CSS, pointer-events: none.
// ============================================================

export function ScanLine() {
  return (
    <div className="scanline-container" aria-hidden="true">
      <div className="scanline animate-scanline" />
    </div>
  )
}
