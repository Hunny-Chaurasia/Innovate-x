import { useMemo, useState } from 'react';
import { Badge, Button, StageBadge } from './ui';
import { useToast } from './Toast';
import {
  useWorkflow, addReview, addReply, timeAgo, getTeamLeader,
  CURRENT_INDUSTRY, CURRENT_STUDENT,
  type ProjectReview, type ReviewStatus,
} from '../store/workflow';

/* ───────────────────────── Review thread (both roles) ───────────────────────── */

const STATUS_BADGE: Record<ReviewStatus, { label: string; variant: 'warning' | 'info' | 'success' }> = {
  open: { label: 'Changes requested', variant: 'warning' },
  addressed: { label: 'Student replied', variant: 'info' },
  resolved: { label: 'Resolved', variant: 'success' },
};

function Block({ title, children }: { title: string; children: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--muted-foreground)' }}>{title}</p>
      <p className="text-sm leading-relaxed whitespace-pre-line" style={{ color: 'var(--foreground)' }}>{children}</p>
    </div>
  );
}

/**
 * viewer="industry": can follow up ("Request more changes") or "Mark resolved".
 * viewer="student":  can reply, or reply + mark that the requested changes are done.
 */
export function ReviewThread({
  review, viewer, onEngaged,
}: { review: ProjectReview; viewer: 'student' | 'industry'; onEngaged?: () => void }) {
  const { toast } = useToast();
  const [text, setText] = useState('');
  const authorName = viewer === 'student' ? CURRENT_STUDENT.name : CURRENT_INDUSTRY.name;
  const badge = STATUS_BADGE[review.status];

  const send = (next: ReviewStatus | undefined, msg: string, fallbackText?: string) => {
    const body = text.trim() || fallbackText || '';
    if (!body) return;
    addReply(review.id, { authorRole: viewer, authorName, text: body }, next);
    setText('');
    toast(msg, 'success');
    onEngaged?.();
  };

  return (
    <div className="rounded-xl border p-4 flex flex-col gap-3" style={{ borderColor: 'var(--border)', background: 'var(--muted)' }}>
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div>
          <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>
            {review.reviewerName} · {review.reviewerOrg}
          </p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            {review.projectTitle} · {timeAgo(review.createdAt)}
          </p>
        </div>
        <Badge variant={badge.variant}>{badge.label}</Badge>
      </div>

      <Block title="Overall assessment">{review.summary}</Block>
      {review.strengths && <Block title="What works">{review.strengths}</Block>}
      <Block title="Flaws">{review.flaws}</Block>
      <Block title="Improvements needed">{review.improvements}</Block>

      {review.replies.length > 0 && (
        <div className="flex flex-col gap-2 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
          {review.replies.map(r => (
            <div
              key={r.id}
              className="p-3 rounded-lg text-sm"
              style={{
                background: r.authorRole === 'student' ? 'rgba(124,58,237,0.08)' : 'var(--card)',
                border: '1px solid var(--border)',
              }}
            >
              <p className="text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
                <strong style={{ color: 'var(--foreground)' }}>{r.authorName}</strong>
                {' '}({r.authorRole === 'student' ? 'team' : 'reviewer'}) · {timeAgo(r.createdAt)}
              </p>
              <p className="whitespace-pre-line" style={{ color: 'var(--foreground)' }}>{r.text}</p>
            </div>
          ))}
        </div>
      )}

      {review.status !== 'resolved' && (
        <div className="flex flex-col gap-2 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
          <textarea
            rows={3}
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder={
              viewer === 'student'
                ? 'Describe the changes you made, or reply to the reviewer…'
                : 'Add a follow-up for the team…'
            }
            className="w-full px-3 py-2 text-sm rounded-lg border outline-none resize-none"
            style={{ background: 'var(--card)', borderColor: 'var(--border)', color: 'var(--foreground)' }}
          />
          <div className="flex gap-2 justify-end flex-wrap">
            {viewer === 'student' ? (
              <>
                <Button variant="secondary" size="sm" disabled={!text.trim()} onClick={() => send(undefined, 'Reply sent to the reviewer.')}>
                  Send reply
                </Button>
                <Button size="sm" disabled={!text.trim()} onClick={() => send('addressed', 'Changes sent to the reviewer for another look.')}>
                  Reply · changes done
                </Button>
              </>
            ) : (
              <>
                <Button variant="secondary" size="sm" disabled={!text.trim()} onClick={() => send('open', 'Follow-up sent. The team will see more changes are needed.')}>
                  Request more changes
                </Button>
                <Button size="sm" onClick={() => send('resolved', 'Review marked as resolved.', 'Changes look good. Marking this review as resolved.')}>
                  Mark resolved
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ───────────────────────── Industry: view project = must review ───────────────────────── */

export interface ReviewableProject {
  id: string;
  title: string;
  team: string;
  institution: string;
  stage: string;
  progress: number;
  members: number;
}

function Field({
  label, value, onChange, placeholder, required, rows = 3,
}: { label: string; value: string; onChange: (v: string) => void; placeholder: string; required?: boolean; rows?: number }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>
        {label} {required && <span className="text-red-400">*</span>}
      </label>
      <textarea
        rows={rows}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="px-3 py-2 text-sm rounded-lg border outline-none resize-none"
        style={{ background: 'var(--muted)', borderColor: 'var(--border)', color: 'var(--foreground)' }}
      />
    </div>
  );
}

/**
 * Opening a project as an industry partner requires leaving a review before you can leave:
 * overall assessment, flaws, improvements needed. The team replies with changes,
 * and you can follow up or mark it resolved from this same window.
 * Following up in an existing thread also counts as your review for this visit.
 */
export default function ProjectReviewModal({ project, onClose }: { project: ReviewableProject; onClose: () => void }) {
  const { toast } = useToast();
  const { reviews } = useWorkflow();
  const leader = getTeamLeader(project.team);
  const [form, setForm] = useState({ summary: '', strengths: '', flaws: '', improvements: '' });
  const [done, setDone] = useState(false);
  const [warn, setWarn] = useState(false);

  const history = useMemo(
    () => reviews.filter(r => r.projectId === project.id && r.reviewerId === CURRENT_INDUSTRY.id).sort((a, b) => b.createdAt - a.createdAt),
    [reviews, project.id],
  );

  const set = (k: keyof typeof form) => (v: string) => setForm(f => ({ ...f, [k]: v }));
  const valid = form.summary.trim().length >= 10 && form.flaws.trim().length >= 10 && form.improvements.trim().length >= 10;

  const submit = () => {
    if (!valid) return;
    addReview({
      projectId: project.id, projectTitle: project.title, teamName: project.team,
      summary: form.summary.trim(), strengths: form.strengths.trim(),
      flaws: form.flaws.trim(), improvements: form.improvements.trim(),
    });
    setDone(true);
    setWarn(false);
    toast(`Review sent to ${project.team}. They can reply with the changes they make.`, 'success');
  };

  const attemptClose = () => (done ? onClose() : setWarn(true));

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ background: 'rgba(0,0,0,0.75)' }}>
      <div className="w-full max-w-2xl rounded-2xl border flex flex-col max-h-[92vh]" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
        <div className="flex items-start justify-between p-5 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="min-w-0">
            <h3 className="font-bold" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>{project.title}</h3>
            <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
              {project.team} · {project.institution} · {project.members} members · Leader: {leader.name}
            </p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <StageBadge stage={project.stage} />
            <button onClick={attemptClose} aria-label="Close" style={{ color: 'var(--muted-foreground)' }}>✕</button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-5">
          <div className="grid grid-cols-3 gap-3">
            {[
              ['Stage', project.stage],
              ['Progress', `${project.progress}%`],
              ['Team size', String(project.members)],
            ].map(([k, v]) => (
              <div key={k} className="p-3 rounded-lg" style={{ background: 'var(--muted)' }}>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{k}</p>
                <p className="text-lg font-bold mt-0.5" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>{v}</p>
              </div>
            ))}
          </div>

          {/* Review form */}
          {done ? (
            <div className="p-3 rounded-lg text-sm" style={{ background: 'rgba(5,150,105,0.1)', border: '1px solid rgba(5,150,105,0.25)', color: '#34d399' }}>
              ✓ Your review for this visit is submitted. You can close this window.
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div>
                <p className="text-sm font-semibold" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>Review this project</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                  A review is required every time you open a project. Be specific, so the team knows what to fix.
                </p>
              </div>

              {warn && (
                <div className="p-3 rounded-lg text-xs" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', color: '#f87171' }}>
                  Submit your review before closing. Fill in the overall assessment, flaws and improvements (at least 10 characters each).
                </div>
              )}

              <Field label="Overall assessment" required value={form.summary} onChange={set('summary')}
                placeholder="What is your overall impression of the idea, execution and fit with the problem?" />
              <Field label="What works (optional)" value={form.strengths} onChange={set('strengths')} rows={2}
                placeholder="Strong parts the team should keep." />
              <Field label="Flaws" required value={form.flaws} onChange={set('flaws')}
                placeholder="Gaps, risks or mistakes you noticed: technical, market, data, scope…" />
              <Field label="Improvements needed" required value={form.improvements} onChange={set('improvements')}
                placeholder="What should the team change before you would consider funding or mentoring?" />
              <div className="flex justify-end">
                <Button onClick={submit} disabled={!valid}>Submit review</Button>
              </div>
            </div>
          )}

          {/* History */}
          {history.length > 0 && (
            <div className="flex flex-col gap-3">
              <p className="text-sm font-semibold" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>
                Review history ({history.length})
              </p>
              {history.map(r => (
                <ReviewThread key={r.id} review={r} viewer="industry" onEngaged={() => { setDone(true); setWarn(false); }} />
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 p-4 border-t" style={{ borderColor: 'var(--border)' }}>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            {done ? 'Review submitted.' : 'Review required to close.'}
          </p>
          <Button variant="secondary" onClick={attemptClose}>Close</Button>
        </div>
      </div>
    </div>
  );
}
