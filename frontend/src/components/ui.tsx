import type { ReactNode, CSSProperties } from 'react';

export function LinkedInLink({ url, compact }: { url: string; compact?: boolean }) {
  if (!url) return null;
  const href = url.startsWith('http') ? url : `https://${url}`;
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      title={url}
      className="inline-flex items-center gap-1 hover:opacity-80 transition-opacity"
      style={{ color: '#0A66C2', textDecoration: 'none' }}
      onClick={(e) => e.stopPropagation()}
    >
      <span
        className="flex items-center justify-center font-bold rounded text-white"
        style={{ background: '#0A66C2', fontSize: 9, width: 16, height: 16, flexShrink: 0 }}
      >
        in
      </span>
      {!compact && <span className="text-xs" style={{ color: '#0A66C2' }}>{url.replace('https://', '').replace('http://', '')}</span>}
    </a>
  );
}

export function Card({ children, className = '', style, onClick }: { children: ReactNode; className?: string; style?: CSSProperties; onClick?: () => void }) {
  return (
    <div
      className={`rounded-xl border ${className}`}
      style={{ background: 'var(--card)', borderColor: 'var(--border)', ...style }}
      onClick={onClick}
    >
      {children}
    </div>
  );
}

export function StatCard({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: boolean }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-medium uppercase tracking-wide mb-2" style={{ color: 'var(--muted-foreground)' }}>{label}</p>
      <p className="text-3xl font-bold" style={{ fontFamily: 'DM Sans', color: accent ? 'var(--accent)' : 'var(--foreground)' }}>{value}</p>
      {sub && <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>{sub}</p>}
    </Card>
  );
}

export function Badge({ children, variant = 'default' }: { children: ReactNode; variant?: 'default' | 'school' | 'college' | 'university' | 'success' | 'warning' | 'danger' | 'pending' | 'info' }) {
  const styles: Record<string, { bg: string; color: string }> = {
    default: { bg: 'rgba(113,113,122,0.15)', color: '#a1a1aa' },
    school: { bg: 'rgba(245,158,11,0.15)', color: '#fbbf24' },
    college: { bg: 'rgba(124,58,237,0.15)', color: '#a78bfa' },
    university: { bg: 'rgba(14,165,233,0.15)', color: '#38bdf8' },
    success: { bg: 'rgba(5,150,105,0.15)', color: '#34d399' },
    warning: { bg: 'rgba(245,158,11,0.15)', color: '#fbbf24' },
    danger: { bg: 'rgba(239,68,68,0.15)', color: '#f87171' },
    pending: { bg: 'rgba(251,146,60,0.15)', color: '#fb923c' },
    info: { bg: 'rgba(14,165,233,0.15)', color: '#38bdf8' },
  };
  const s = styles[variant] || styles.default;
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ background: s.bg, color: s.color }}
    >
      {children}
    </span>
  );
}

export function InstitutionBadge({ type }: { type: string }) {
  const v = type.toLowerCase() as 'school' | 'college' | 'university';
  return <Badge variant={v}>{type}</Badge>;
}

export function StageBadge({ stage }: { stage: string }) {
  const map: Record<string, 'default' | 'info' | 'warning' | 'success' | 'pending'> = {
    Ideation: 'default', Building: 'info', Proposal: 'warning', Funded: 'success', Deployed: 'success', Prototype: 'pending',
  };
  return <Badge variant={map[stage] || 'default'}>{stage}</Badge>;
}

export function VirtualIdCard({ id, label = 'Virtual ID' }: { id: string; label?: string }) {
  return (
    <div
      className="inline-flex flex-col gap-1 px-4 py-3 rounded-xl border"
      style={{ background: 'rgba(124,58,237,0.08)', borderColor: 'rgba(124,58,237,0.3)' }}
    >
      <span className="text-xs uppercase tracking-widest font-medium" style={{ color: 'var(--muted-foreground)' }}>{label}</span>
      <span className="font-mono text-lg font-semibold" style={{ color: 'var(--accent)', letterSpacing: '0.06em' }}>{id}</span>
    </div>
  );
}

export function Input({
  label, type = 'text', placeholder, value, onChange, error, prefix, required,
}: {
  label?: string; type?: string; placeholder?: string; value?: string; onChange?: (v: string) => void;
  error?: string; prefix?: ReactNode; required?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>
          {label}{required && <span className="text-red-400 ml-1">*</span>}
        </label>
      )}
      <div className="relative flex items-center">
        {prefix && (
          <span className="absolute left-3 text-sm" style={{ color: 'var(--muted-foreground)' }}>{prefix}</span>
        )}
        <input
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          className="w-full px-3 py-2 text-sm rounded-lg border outline-none"
          style={{
            background: 'var(--muted)',
            borderColor: error ? '#ef4444' : 'var(--border)',
            color: 'var(--foreground)',
            paddingLeft: prefix ? 32 : undefined,
          }}
          onFocus={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ring)'; }}
          onBlur={(e) => { (e.currentTarget as HTMLElement).style.borderColor = error ? '#ef4444' : 'var(--border)'; }}
        />
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}

export function Button({
  children, onClick, variant = 'primary', size = 'md', disabled, type = 'button', className = '',
}: {
  children: ReactNode; onClick?: () => void; variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg'; disabled?: boolean; type?: 'button' | 'submit'; className?: string;
}) {
  const sizes = { sm: 'px-3 py-1.5 text-xs', md: 'px-4 py-2 text-sm', lg: 'px-6 py-2.5 text-sm' };
  const variants = {
    primary: { background: 'var(--primary)', color: 'white', border: 'transparent' },
    secondary: { background: 'var(--secondary)', color: 'var(--foreground)', border: 'var(--border)' },
    ghost: { background: 'transparent', color: 'var(--muted-foreground)', border: 'transparent' },
    danger: { background: 'rgba(239,68,68,0.1)', color: '#f87171', border: 'rgba(239,68,68,0.3)' },
  };
  const v = variants[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-1.5 font-medium rounded-lg border transition-all ${sizes[size]} ${className}`}
      style={{
        background: v.background, color: v.color, borderColor: v.border,
        opacity: disabled ? 0.5 : 1, cursor: disabled ? 'not-allowed' : 'pointer',
      }}
      onMouseEnter={(e) => { if (!disabled && variant === 'primary') (e.currentTarget as HTMLElement).style.opacity = '0.9'; }}
      onMouseLeave={(e) => { if (!disabled && variant === 'primary') (e.currentTarget as HTMLElement).style.opacity = '1'; }}
    >
      {children}
    </button>
  );
}

export function EmptyState({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
      <div className="text-4xl mb-2">{icon}</div>
      <p className="font-semibold text-base" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>{title}</p>
      <p className="text-sm max-w-xs" style={{ color: 'var(--muted-foreground)' }}>{body}</p>
    </div>
  );
}

export function Avatar({ initials, size = 'md', color }: { initials: string; size?: 'sm' | 'md' | 'lg'; color?: string }) {
  const sizes = { sm: 'w-6 h-6 text-xs', md: 'w-8 h-8 text-xs', lg: 'w-10 h-10 text-sm' };
  return (
    <div
      className={`rounded-full flex items-center justify-center font-semibold flex-shrink-0 ${sizes[size]}`}
      style={{ background: color || 'var(--primary)', color: 'white' }}
    >
      {initials}
    </div>
  );
}

export function ProjectJourneyStepper({ currentStage }: { currentStage: string }) {
  const stages = ['Idea', 'Problem', 'Team', 'Proposal', 'Build', 'Milestones', 'Feedback', 'Industry', 'Funding', 'Prototype', 'Deployment'];
  const currentIdx = stages.indexOf(currentStage);
  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex items-center gap-0 min-w-max">
        {stages.map((s, i) => {
          const done = i < currentIdx;
          const active = i === currentIdx;
          return (
            <div key={s} className="flex items-center">
              <div className="flex flex-col items-center gap-1">
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-all"
                  style={{
                    background: done ? 'var(--primary)' : active ? 'var(--accent)' : 'transparent',
                    borderColor: done || active ? (done ? 'var(--primary)' : 'var(--accent)') : 'var(--border)',
                    color: done || active ? 'white' : 'var(--muted-foreground)',
                  }}
                >
                  {done ? '✓' : i + 1}
                </div>
                <span
                  className="text-xs whitespace-nowrap"
                  style={{ color: active ? 'var(--accent)' : done ? 'var(--foreground)' : 'var(--muted-foreground)' }}
                >
                  {s}
                </span>
              </div>
              {i < stages.length - 1 && (
                <div
                  className="h-0.5 w-8 mb-4 flex-shrink-0"
                  style={{ background: i < currentIdx ? 'var(--primary)' : 'var(--border)' }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
