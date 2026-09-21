import { useMemo, useState } from 'react';
import { Card, StageBadge, Button, Badge } from './ui';
import { MOCK_PROJECTS } from '../data/mock';
import { useWorkflow } from '../store/workflow';
import ProofOfWork from './ProofOfWork';

export interface PortfolioProject {
  id: string;
  title: string;
  stage: string;
  description: string;
  proofOfWork: number;
  teamSize: number;
  category: string;
  institution: string;
}

// Deployed sample project that lived inside your old Portfolio.tsx.
const EDUBRIDGE: PortfolioProject = {
  id: 'proj3',
  title: 'EduBridge — Peer Learning Platform',
  stage: 'Deployed',
  description: 'Peer-to-peer learning app connecting students across institutions.',
  proofOfWork: 14,
  teamSize: 3,
  category: 'EdTech',
  institution: 'IIT Bombay',
};

const STAGE_ORDER = ['Ideation', 'Building', 'Prototype', 'Funded', 'Deployed'];

/** MOCK_PROJECTS + EduBridge + teams created in the app, with live proof-of-work counts. */
export function usePortfolioProjects(): PortfolioProject[] {
  const { projects, proofs } = useWorkflow();
  return useMemo(() => {
    const fromMock: PortfolioProject[] = MOCK_PROJECTS.map(p => ({
      id: p.id, title: p.title, stage: p.stage, description: p.description,
      proofOfWork: p.proofOfWork, teamSize: p.teamSize, category: p.category, institution: p.institution,
    }));
    const created: PortfolioProject[] = projects.map(p => ({
      id: p.id, title: p.title, stage: p.stage, description: p.description,
      proofOfWork: p.proofOfWork, teamSize: p.teamSize, category: p.category, institution: p.institution,
    }));
    return [...fromMock, EDUBRIDGE, ...created].map(p => ({
      ...p,
      proofOfWork: p.proofOfWork + proofs.filter(x => x.projectId === p.id).length,
    }));
  }, [projects, proofs]);
}

function DetailModal({ project, onClose }: { project: PortfolioProject; onClose: () => void }) {
  return (
    <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ background: 'rgba(0,0,0,0.75)' }}>
      <div className="w-full max-w-2xl rounded-2xl border flex flex-col max-h-[92vh]" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
        <div className="flex items-start justify-between p-5 border-b gap-3" style={{ borderColor: 'var(--border)' }}>
          <div className="min-w-0">
            <h3 className="font-bold" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>{project.title}</h3>
            <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
              {project.category} · {project.institution} · {project.teamSize} members
            </p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <StageBadge stage={project.stage} />
            <button onClick={onClose} aria-label="Close" style={{ color: 'var(--muted-foreground)' }}>✕</button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4">
          <p className="text-sm leading-relaxed" style={{ color: 'var(--foreground)' }}>{project.description}</p>
          <ProofOfWork projectId={project.id} editable={false} />
        </div>
        <div className="p-4 border-t flex justify-end" style={{ borderColor: 'var(--border)' }}>
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  );
}

export function PortfolioGrid({ projects }: { projects: PortfolioProject[] }) {
  const [filter, setFilter] = useState('All');
  const [selected, setSelected] = useState<PortfolioProject | null>(null);

  const stages = useMemo(() => {
    const present = new Set(projects.map(p => p.stage));
    return ['All', ...STAGE_ORDER.filter(s => present.has(s)), ...[...present].filter(s => !STAGE_ORDER.includes(s))];
  }, [projects]);

  const shown = projects.filter(p => filter === 'All' || p.stage === filter);
  const count = (s: string) => (s === 'All' ? projects.length : projects.filter(p => p.stage === s).length);

  return (
    <>
      <div className="flex gap-2 mb-6 flex-wrap">
        {stages.map(s => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className="px-3 py-1.5 text-xs rounded-lg border font-medium transition-all"
            style={{
              background: filter === s ? 'var(--primary)' : 'transparent',
              borderColor: filter === s ? 'var(--primary)' : 'var(--border)',
              color: filter === s ? 'white' : 'var(--muted-foreground)',
            }}
          >
            {s} <span style={{ opacity: 0.7 }}>{count(s)}</span>
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <p className="text-sm py-10 text-center" style={{ color: 'var(--muted-foreground)' }}>No {filter.toLowerCase()} projects yet.</p>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {shown.map(p => (
            <Card key={p.id} className="p-5 flex flex-col gap-3">
              <div className="flex items-start justify-between">
                <p className="font-semibold text-sm flex-1 mr-2" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>{p.title}</p>
                <StageBadge stage={p.stage} />
              </div>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>{p.description}</p>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  <span className="font-mono" style={{ color: 'var(--accent)' }}>{p.proofOfWork}</span> proof-of-work
                </span>
                {p.teamSize > 0 && <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>· {p.teamSize} members</span>}
                <Badge>{p.category}</Badge>
              </div>
              <div className="flex gap-2 mt-auto pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
                <Button variant="ghost" size="sm" onClick={() => setSelected(p)}>View Details</Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {selected && <DetailModal project={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
