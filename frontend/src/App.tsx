import { NavLink, Route, Routes } from 'react-router-dom'

import { BrandPage } from './pages/BrandPage'
import { HistoryPage } from './pages/HistoryPage'
import { PipelinePage } from './pages/PipelinePage'

function navClass({ isActive }: { isActive: boolean }): string {
  return `text-sm transition hover:text-slate-300 ${
    isActive ? 'font-medium text-white underline' : 'text-slate-500'
  }`
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <nav className="border-b border-slate-800 px-6 py-3">
        <div className="mx-auto flex max-w-7xl flex-wrap gap-6">
          <NavLink to="/" className={navClass} end>
            Pipeline
          </NavLink>
          <NavLink to="/brand" className={navClass}>
            Brand
          </NavLink>
          <NavLink to="/history" className={navClass}>
            History
          </NavLink>
        </div>
      </nav>

      <Routes>
        <Route path="/" element={<PipelinePage />} />
        <Route path="/brand" element={<BrandPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Routes>
    </div>
  )
}
