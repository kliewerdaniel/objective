import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Radio, Volume2, LayoutDashboard, Settings, Mic, FileText, Database, ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'

const mainNav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/broadcast', label: 'Broadcast', icon: Volume2 },
]

const configNav = [
  { to: '/sources', label: 'Sources', icon: Radio },
  { to: '/models', label: 'Models', icon: Database },
  { to: '/voices', label: 'Voice', icon: Mic },
  { to: '/prompts', label: 'Prompts', icon: FileText },
  { to: '/config', label: 'Advanced', icon: Settings },
]

export default function Layout() {
  const [configOpen, setConfigOpen] = useState(true)
  const location = useLocation()
  const isConfigActive = configNav.some((n) => location.pathname.startsWith(n.to))

  return (
    <div className="flex h-screen bg-[#0a0a0a]">
      {/* Sidebar */}
      <aside className="w-52 border-r border-[#1e1e1e] bg-[#111111] flex flex-col shrink-0">
        {/* macOS traffic light spacer + drag region */}
        <div
          className="w-full shrink-0 flex items-center"
          style={{
            height: 36,
            paddingLeft: 68,
            WebkitAppRegion: 'drag',
          } as React.CSSProperties}
        />

        {/* Logo */}
        <div className="px-4 py-3 border-b border-border">
          <h1 className="text-sm font-bold tracking-tight">objective03</h1>
          <p className="text-[10px] text-muted-foreground mt-0.5">synthetic epistemology</p>
        </div>

        {/* Main nav */}
        <nav className="flex-1 p-2 space-y-0.5">
          {mainNav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
                }`
              }
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </NavLink>
          ))}

          {/* Config section */}
          <div className="pt-2">
            <button
              onClick={() => setConfigOpen(!configOpen)}
              className={`flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm w-full transition-colors ${
                isConfigActive
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
              }`}
            >
              <Settings className="h-3.5 w-3.5" />
              Configure
              {configOpen ? (
                <ChevronDown className="h-3 w-3 ml-auto" />
              ) : (
                <ChevronRight className="h-3 w-3 ml-auto" />
              )}
            </button>
            {configOpen && (
              <div className="ml-2 mt-0.5 space-y-0.5 border-l border-border pl-2">
                {configNav.map(({ to, label, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    className={({ isActive }) =>
                      `flex items-center gap-2 px-2.5 py-1 rounded text-xs transition-colors ${
                        isActive
                          ? 'bg-accent text-accent-foreground'
                          : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
                      }`
                    }
                  >
                    <Icon className="h-3 w-3" />
                    {label}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
