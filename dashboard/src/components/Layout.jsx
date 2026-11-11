import { useEffect, useState } from 'react'
import { NavLink, Outlet, Link } from 'react-router-dom'
import { getSource, subscribeSource, API_URL } from '../api.js'

function SourceIndicator() {
  const [source, setSource] = useState(getSource())
  useEffect(() => subscribeSource(setSource), [])
  const live = source === 'live'
  const mock = source === 'mock'
  const offline = source === 'offline'
  const label = live ? 'Live API' : mock ? 'Mock data' : offline ? 'API offline' : 'Connecting'
  const title = live
    ? `Connected to ${API_URL}`
    : mock
      ? 'VITE_USE_MOCK=1: showing a bundled snapshot of real API responses'
      : offline
        ? `No usable response from ${API_URL}`
        : 'Connecting…'
  return (
    <span title={title} className={`inline-flex items-center gap-2 text-xs ${mock || offline ? 'text-warn' : 'text-fg-muted'}`}>
      <span className={`h-2 w-2 rounded-full ${live ? 'bg-ok' : mock || offline ? 'bg-warn' : 'bg-fg-subtle'}`} />
      <span className="hidden sm:inline">{label}</span>
      <span className="sr-only sm:hidden">{label}</span>
    </span>
  )
}

const navCls = ({ isActive }) =>
  `relative flex h-full items-center text-[15px] transition-colors ${
    isActive
      ? 'font-medium text-fg after:absolute after:inset-x-0 after:bottom-0 after:h-[3px] after:bg-fg'
      : 'text-fg-muted hover:text-fg'
  }`

export default function Layout() {
  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b-2 border-fg-subtle">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-5 px-4 sm:gap-8 sm:px-6">
          <Link to="/" className="shrink-0 font-display text-xl font-semibold text-fg">
            AgentLens
          </Link>
          <nav className="flex h-full items-center gap-4 sm:gap-6">
            <NavLink to="/" end className={navCls}>
              Overview
            </NavLink>
            <NavLink to="/issues" className={navCls}>
              Issues
            </NavLink>
            <NavLink to="/sessions" className={navCls}>
              Sessions
            </NavLink>
          </nav>
          <div className="ml-auto">
            <SourceIndicator />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 pb-20 pt-8 sm:px-6 sm:pt-10">
        <Outlet />
      </main>
    </div>
  )
}
