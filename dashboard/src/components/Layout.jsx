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
  `relative flex h-full items-center px-2.5 text-sm transition-colors sm:px-3 ${
    isActive
      ? 'text-fg after:absolute after:inset-x-2.5 after:bottom-0 after:h-0.5 after:rounded-full after:bg-accent sm:after:inset-x-3'
      : 'text-fg-muted hover:text-fg'
  }`

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="h-6 w-6" aria-hidden>
      <rect width="32" height="32" rx="7" className="fill-accent" />
      <circle cx="14" cy="14" r="6.5" fill="none" stroke="white" strokeWidth="2.6" />
      <path d="M19 19l5 5" stroke="white" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  )
}

export default function Layout() {
  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-20 border-b border-line bg-canvas">
        <div className="mx-auto flex h-13 max-w-7xl items-center gap-3 px-4 sm:gap-6 sm:px-6">
          <Link to="/" className="flex shrink-0 items-center gap-2.5 text-fg">
            <Logo />
            <span className="hidden text-[15px] font-semibold tracking-tight min-[420px]:inline">AgentLens</span>
          </Link>
          <nav className="flex h-full items-center">
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
      <main className="mx-auto max-w-7xl px-4 pb-16 pt-6 sm:px-6 sm:pt-8">
        <Outlet />
      </main>
    </div>
  )
}
