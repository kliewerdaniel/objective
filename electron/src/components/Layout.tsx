import { NavLink, Outlet } from 'react-router-dom'
import { Radio, Volume2, Mic, FileText, Settings } from 'lucide-react'

const navItems = [
  { to: '/', label: 'Dashboard', icon: Radio },
  { to: '/broadcast', label: 'Broadcast', icon: Volume2 },
  { to: '/voices', label: 'Voices', icon: Mic },
  { to: '/prompts', label: 'Prompts', icon: FileText },
  { to: '/config', label: 'Config', icon: Settings },
]

export default function Layout() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-48 border-r border-border bg-card flex flex-col">
        <div className="px-4 py-3 border-b border-border">
          <h1 className="text-sm font-bold tracking-tight">objective03</h1>
          <p className="text-[10px] text-muted-foreground mt-0.5">news broadcast daemon</p>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {navItems.map(({ to, label, icon: Icon }) => (
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
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-5">
        <Outlet />
      </main>
    </div>
  )
}
