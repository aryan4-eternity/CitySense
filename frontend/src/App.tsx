// ============================================================
// App.tsx — Root composition for CitySense Command-Center
// ============================================================

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Header } from '@/components/Header/Header'
import { DeckMap } from '@/components/Map/DeckMap'
import { StatsPanel } from '@/components/StatsPanel/StatsPanel'
import { CellPanel } from '@/components/CellPanel/CellPanel'
import { LayerBar } from '@/components/LayerBar/LayerBar'
import { ScanLine } from '@/components/ui/ScanLine'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 2,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div
        id="citysense-app"
        style={{
          position: 'relative',
          width: '100vw',
          height: '100vh',
          overflow: 'hidden',
          background: 'var(--bg-base)',
        }}
      >
        {/* Full-screen map (z-index: 0) */}
        <DeckMap />

        {/* Header bar (z-index: 200) */}
        <Header />

        {/* Left stats panel (z-index: 100) */}
        <StatsPanel />

        {/* Right cell detail panel — conditional on selection (z-index: 100) */}
        <CellPanel />

        {/* Bottom layer switcher (z-index: 150) */}
        <LayerBar />

        {/* Scanline animation overlay (z-index: 9999) */}
        <ScanLine />
      </div>
    </QueryClientProvider>
  )
}

export default App
