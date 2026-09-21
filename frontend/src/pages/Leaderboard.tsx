import { useState } from 'react';
import { Card, Badge } from '../components/ui';
import { MOCK_LEADERBOARD } from '../data/mock';

const RANK_STYLES: Record<number, { bg: string; color: string; label: string }> = {
  1: { bg: 'rgba(251,191,36,0.15)', color: '#fbbf24', label: '🥇' },
  2: { bg: 'rgba(156,163,175,0.15)', color: '#9ca3af', label: '🥈' },
  3: { bg: 'rgba(180,83,9,0.15)', color: '#d97706', label: '🥉' },
};

function RankRow({ entry, isOwn }: { entry: typeof MOCK_LEADERBOARD.schools[0]; isOwn?: boolean }) {
  const rankStyle = RANK_STYLES[entry.rank];
  return (
    <div
      className="flex items-center gap-4 px-4 py-3 rounded-lg"
      style={{
        background: isOwn ? 'rgba(124,58,237,0.08)' : rankStyle ? rankStyle.bg : 'transparent',
        border: isOwn ? '1px solid rgba(124,58,237,0.25)' : rankStyle ? `1px solid ${rankStyle.color}30` : '1px solid transparent',
      }}
    >
      {/* Rank */}
      <div className="w-8 text-center flex-shrink-0">
        {rankStyle ? (
          <span className="text-xl">{rankStyle.label}</span>
        ) : (
          <span className="text-sm font-mono font-semibold" style={{ color: 'var(--muted-foreground)' }}>#{entry.rank}</span>
        )}
      </div>

      {/* Logo */}
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
        style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}
      >
        {entry.logo}
      </div>

      {/* Name */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate" style={{ color: 'var(--foreground)' }}>
          {entry.name}
          {isOwn && (
            <span className="ml-2 text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(124,58,237,0.2)', color: 'var(--accent)' }}>
              You
            </span>
          )}
        </p>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-6 flex-shrink-0 text-right">
        <div className="hidden sm:block">
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>Projects</p>
          <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>{entry.projects}</p>
        </div>
        <div className="hidden sm:block">
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>Students</p>
          <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>{entry.students}</p>
        </div>
        <div>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>Score</p>
          <p className="text-sm font-bold font-mono" style={{ color: rankStyle ? rankStyle.color : 'var(--accent)' }}>
            {entry.score.toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function Leaderboard() {
  const [tab, setTab] = useState<'schools' | 'colleges'>('colleges');
  const [period, setPeriod] = useState<'month' | 'all'>('all');

  const list = MOCK_LEADERBOARD[tab === 'schools' ? 'schools' : 'colleges'];

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6 flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold mb-1" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>
            Leaderboard
          </h1>
          <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
            Top institutions ranked by project activity and engagement.
          </p>
        </div>
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--secondary)' }}>
          {(['month', 'all'] as const).map(p => (
            <button key={p} onClick={() => setPeriod(p)}
              className="px-3 py-1 rounded-md text-xs font-medium"
              style={{ background: period === p ? 'var(--card)' : 'transparent', color: period === p ? 'var(--foreground)' : 'var(--muted-foreground)' }}>
              {p === 'month' ? 'This Month' : 'All Time'}
            </button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-lg mb-6 w-fit" style={{ background: 'var(--secondary)' }}>
        {(['schools', 'colleges'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className="px-4 py-1.5 rounded-md text-sm font-medium"
            style={{ background: tab === t ? 'var(--card)' : 'transparent', color: tab === t ? 'var(--foreground)' : 'var(--muted-foreground)' }}>
            {t === 'schools' ? 'Schools' : 'Colleges & Universities'}
          </button>
        ))}
      </div>

      {/* Column headers */}
      <div className="flex items-center gap-4 px-4 pb-2 mb-1">
        <div className="w-8" />
        <div className="w-8" />
        <div className="flex-1" />
        <div className="flex items-center gap-6 text-right">
          <p className="text-xs uppercase tracking-wide hidden sm:block w-14" style={{ color: 'var(--muted-foreground)' }}>Projects</p>
          <p className="text-xs uppercase tracking-wide hidden sm:block w-14" style={{ color: 'var(--muted-foreground)' }}>Students</p>
          <p className="text-xs uppercase tracking-wide w-16" style={{ color: 'var(--muted-foreground)' }}>Score</p>
        </div>
      </div>

      <div className="flex flex-col gap-1">
        {list.map((entry, i) => (
          <RankRow
            key={entry.rank}
            entry={entry}
            isOwn={tab === 'colleges' && entry.name === 'IIT Bombay'}
          />
        ))}
      </div>
    </div>
  );
}
