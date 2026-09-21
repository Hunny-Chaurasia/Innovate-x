import { useState, createContext, useContext } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import type { Role } from '../data/mock';
import logo from '../assets/logo.png';

interface AppContextType {
  role: Role;
  user: { name: string; avatar: string; virtualId?: string };
}

const AppContext = createContext<AppContextType>({
  role: 'student',
  user: { name: 'Arjun Mehta', avatar: 'AM' },
});

export const useAppContext = () => useContext(AppContext);

const NAV_ITEMS: Record<Role, { label: string; icon: string; path: string }[]> = {
  student: [
    { label: 'Dashboard', icon: '⬡', path: '/student' },
    { label: 'Discover', icon: '◈', path: '/student/discover' },
    { label: 'My Projects', icon: '▣', path: '/student/projects' },
    { label: 'Portfolio', icon: '◉', path: '/student/portfolio' },
    { label: 'Funding', icon: '◇', path: '/student/funding' },
    { label: 'Leaderboard', icon: '◆', path: '/leaderboard' },
    { label: 'Settings', icon: '⚙', path: '/student/settings' },
  ],
  faculty: [
    { label: 'Dashboard', icon: '⬡', path: '/faculty' },
    { label: 'My Teams', icon: '◈', path: '/faculty/teams' },
    { label: 'Students', icon: '▣', path: '/faculty/students' },
    { label: 'Review Panel', icon: '◉', path: '/faculty/review' },
    { label: 'Change Requests', icon: '◇', path: '/faculty/change-requests' },
    { label: 'Leaderboard', icon: '◆', path: '/leaderboard' },
    { label: 'Student Actions', icon: '◆', path: '/faculty/student-actions' },
  ],
  industry: [
    { label: 'Dashboard', icon: '⬡', path: '/industry' },
    { label: 'Post Problem', icon: '◈', path: '/industry/post' },
    { label: 'Discover Projects', icon: '▣', path: '/industry/discover' },
    { label: 'CSR Impact', icon: '◉', path: '/industry/csr' },
    { label: 'Leaderboard', icon: '◆', path: '/leaderboard' },
  ],
  admin: [
    { label: 'Dashboard', icon: '⬡', path: '/admin' },
    { label: 'Users', icon: '◈', path: '/admin/users' },
    { label: 'Moderation', icon: '▣', path: '/admin/moderation' },
    { label: 'Analytics', icon: '◉', path: '/admin/analytics' },
    { label: 'Funding', icon: '◇', path: '/admin/funding-verification' },
    { label: 'Leaderboard', icon: '◆', path: '/leaderboard' },
  ],
};

const ROLE_COLORS: Record<Role, string> = {
  student: 'bg-violet-500/20 text-violet-300',
  faculty: 'bg-blue-500/20 text-blue-300',
  industry: 'bg-emerald-500/20 text-emerald-300',
  admin: 'bg-orange-500/20 text-orange-300',
};

interface ShellProps {
  children: React.ReactNode;
  role: Role;
  user: { name: string; avatar: string; virtualId?: string };
}

export default function Shell({ children, role, user }: ShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const navItems = NAV_ITEMS[role];

  return (
    <AppContext.Provider value={{ role, user }}>
      <div className="flex h-screen overflow-hidden" style={{ background: 'var(--background)' }}>
        {/* Sidebar */}
        <aside
          className="flex flex-col border-r transition-all duration-300"
          style={{
            width: sidebarOpen ? 220 : 60,
            background: 'var(--card)',
            borderColor: 'var(--border)',
            flexShrink: 0,
          }}
        >
          {/* Logo */}
          <div className="flex items-center gap-3 px-4 h-14 border-b" style={{ borderColor: 'var(--border)' }}>
            <div
              className="flex items-center justify-center rounded-lg font-bold text-sm flex-shrink-0"
              style={{ width: 28, height: 28, backgroundImage: `url(${logo})`,backgroundSize:'cover',backgroundPosition:'center',backgroundRepeat:'no-repeat' }}
            >
              
            </div>
            {sidebarOpen && (
              <span className="font-semibold text-sm tracking-tight" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>
                InnovateX
              </span>
            )}
          </div>

          {/* Nav */}
          <nav className="flex-1 overflow-y-auto py-3 px-2">
            {navItems.map((item) => {
              const active = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path) && item.path !== '/student' && item.path !== '/faculty' && item.path !== '/industry' && item.path !== '/admin') || location.pathname === item.path;
              const isExact = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  title={!sidebarOpen ? item.label : undefined}
                  className="flex items-center gap-3 px-2 py-2 rounded-lg mb-0.5 text-sm group"
                  style={{
                    background: isExact ? 'var(--primary)' : 'transparent',
                    color: isExact ? 'white' : 'var(--muted-foreground)',
                  }}
                  onMouseEnter={(e) => { if (!isExact) (e.currentTarget as HTMLElement).style.background = 'var(--secondary)'; (e.currentTarget as HTMLElement).style.color = 'var(--foreground)'; }}
                  onMouseLeave={(e) => { if (!isExact) { (e.currentTarget as HTMLElement).style.background = 'transparent'; (e.currentTarget as HTMLElement).style.color = 'var(--muted-foreground)'; } }}
                >
                  <span className="flex-shrink-0 text-xs">{item.icon}</span>
                  {sidebarOpen && <span>{item.label}</span>}
                </Link>
              );
            })}
          </nav>

          {/* Bottom: collapse + role badge */}
          <div className="px-2 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
            {sidebarOpen && (
              <div className={`mb-2 px-2 py-1 rounded text-xs font-medium text-center ${ROLE_COLORS[role]}`}>
                {role.charAt(0).toUpperCase() + role.slice(1)}
              </div>
            )}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="w-full flex items-center justify-center px-2 py-1.5 rounded-lg text-xs"
              style={{ color: 'var(--muted-foreground)' }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--secondary)'; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
            >
              {sidebarOpen ? '← collapse' : '→'}
            </button>
          </div>
        </aside>

        {/* Main area */}
        <div className="flex flex-col flex-1 overflow-hidden">
          {/* Top nav */}
          <header
            className="flex items-center justify-between px-6 h-14 border-b flex-shrink-0"
            style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
          >
            {/* Breadcrumb / page title */}
            <div className="flex items-center gap-2">
              <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                {role.charAt(0).toUpperCase() + role.slice(1)}
              </span>
              <span style={{ color: 'var(--border)' }}>/</span>
              <span className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
                {navItems.find(n => location.pathname === n.path)?.label || 'Dashboard'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              {/* Notifications */}
              <div className="relative">
                <button
                  onClick={() => setNotifOpen(!notifOpen)}
                  className="relative flex items-center justify-center w-8 h-8 rounded-lg text-sm"
                  style={{ color: 'var(--muted-foreground)' }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--secondary)'; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                >
                  🔔
                  <span
                    className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full"
                    style={{ background: 'var(--primary)' }}
                  />
                </button>
                {notifOpen && (
                  <div
                    className="absolute right-0 top-10 w-72 rounded-xl border shadow-2xl z-50 p-2"
                    style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
                  >
                    <p className="text-xs font-semibold px-2 py-1.5" style={{ color: 'var(--muted-foreground)' }}>NOTIFICATIONS</p>
                    {[
                      { text: 'Mentor request accepted by Dr. Priya', time: '2h ago', dot: 'var(--primary)' },
                      { text: 'New milestone feedback from IIT Bombay team', time: '5h ago', dot: 'var(--primary)' },
                      { text: 'Funding opportunity: Startup India Grant', time: '1d ago', dot: '#71717a' },
                    ].map((n, i) => (
                      <div key={i} className="flex items-start gap-2.5 px-2 py-2 rounded-lg cursor-pointer"
                        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--secondary)'; }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
                        <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: n.dot }} />
                        <div>
                          <p className="text-xs" style={{ color: 'var(--foreground)' }}>{n.text}</p>
                          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{n.time}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Profile */}
              <div className="relative">
                <button
                  onClick={() => setProfileOpen(!profileOpen)}
                  className="flex items-center gap-2 px-2 py-1 rounded-lg"
                  onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--secondary)'; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                >
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0"
                    style={{ background: 'var(--primary)', color: 'white' }}
                  >
                    {user.avatar}
                  </div>
                  <span className="text-sm font-medium hidden sm:block" style={{ color: 'var(--foreground)' }}>
                    {user.name.split(' ')[0]}
                  </span>
                  <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>▾</span>
                </button>
                {profileOpen && (
                  <div
                    className="absolute right-0 top-10 w-52 rounded-xl border shadow-2xl z-50 py-1"
                    style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
                  >
                    <div className="px-3 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
                      <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>{user.name}</p>
                      {user.virtualId && (
                        <p className="text-xs font-mono" style={{ color: 'var(--muted-foreground)' }}>{user.virtualId}</p>
                      )}
                    </div>
                    {[
                      { label: 'Settings', path: role === 'student' ? '/student/settings' : null },
                      { label: 'Help', path: null },
                    ].map(item => (
                      <button key={item.label} className="w-full text-left px-3 py-2 text-sm"
                        style={{ color: 'var(--muted-foreground)' }}
                        onClick={() => { if (item.path) { navigate(item.path); setProfileOpen(false); } }}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--secondary)'; (e.currentTarget as HTMLElement).style.color = 'var(--foreground)'; }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; (e.currentTarget as HTMLElement).style.color = 'var(--muted-foreground)'; }}>
                        {item.label}
                      </button>
                    ))}
                    <div className="border-t mt-1 pt-1" style={{ borderColor: 'var(--border)' }}>
                      <button className="w-full text-left px-3 py-2 text-sm text-red-400"
                        onClick={() => navigate('/')}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--secondary)'; }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
                        Sign out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </header>

          {/* Page content */}
          <main className="flex-1 overflow-y-auto" style={{ background: 'var(--background)' }}>
            {children}
          </main>
        </div>
      </div>
    </AppContext.Provider>
  );
}
