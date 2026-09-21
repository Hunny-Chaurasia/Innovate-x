import { all, getUser, resource, subscribeSession } from './api';
import { useSyncExternalStore } from 'react';
import type { Institution, User } from './api';
export interface Problem { id: string; title: string; description: string; domain: string; source: string; csr: boolean; tags: string[]; publisher_id: string; created_at: string; seen_at?: string; shortlisted_at?: string }
export interface Team { id: string; name: string; leader_id: string; formed_by: 'student' | 'faculty'; status: string }
export interface Member { id: string; user_id: string; display_name: string; virtual_id: string; status: string }
export interface Project { id: string; title: string; description?: string; category: string; stage: string; display_stage?: string; progress: number; team_id: string; team_name?: string; leader_id?: string; team_status?: string; institution_id: string; created_at: string; team?: Team; memberships?: Member[]; mentor_id?: string | null; problem_id?: string | null }
export interface Invite { id: string; project_id: string; sender_id: string; recipient_id: string; kind: 'member' | 'mentor'; reason: string; status: 'pending' | 'accepted' | 'declined'; created_at: string }
export interface Funding { id: string; project_id: string; leader_id: string; funder_id: string; amount_lakh: string; txn_ref: string; proof_file_name: string; proof_url?: string; status: 'awaiting_leader' | 'confirmed' | 'declined'; decline_note: string; created_at: string; responded_at?: string }
export interface Reply { id: string; author_id: string; author_role: 'student' | 'industry'; body: string; created_at: string }
export interface Review { id: string; project_id: string; reviewer_id: string; summary: string; strengths?: string; flaws?: string; improvements?: string; status: 'open' | 'addressed' | 'resolved'; created_at: string; replies: Reply[] }
export interface Attachment { id?: string; kind: 'link' | 'image' | 'video'; url: string; name?: string }
export interface Proof { id: string; project_id: string; author_id: string; title: string; description: string; attachments: Attachment[]; created_at: string }
export interface Share { id: string; slug: string; enabled: boolean; view_count?: number }
export interface Notice { id: string; title: string; body: string; read_at: string | null; project_id: string | null }
export interface InstitutionChange { id: string; student_id: string; faculty_id: string; from_institution_id: string; to_institution_id: string; status: 'pending' | 'approved' | 'declined'; reason: string; response_note: string }
export interface Milestone { id: string; project_id: string; title: string; description: string; status: 'pending' | 'in_progress' | 'submitted' | 'changes_requested' | 'approved' }
export interface PanelFeedback { id: string; project_id: string; faculty_id: string; milestone_id: string | null; body: string; decision: 'feedback' | 'changes_requested' | 'approved'; score: string | null; created_at: string }
export interface CSRSummary { projects_funded: number; confirmed_amount_lakh: string; awaiting_amount_lakh: string; students_reached: number; patents_incubated: null; startups_spun_off: null }
export interface Records { changes: InstitutionChange[]; milestones: Milestone[]; feedback: PanelFeedback[]; csr: CSRSummary | null; projects: Project[]; problems: Problem[]; requests: Invite[]; funding: Funding[]; reviews: Review[]; proofs: Proof[]; users: User[]; institutions: Institution[]; share: Share | null; notifications: Notice[]; loading: boolean; pending: boolean; error: string; ready: boolean }
const empty = (): Records => ({ changes: [], milestones: [], feedback: [], csr: null, projects: [], problems: [], requests: [], funding: [], reviews: [], proofs: [], users: [], institutions: [], share: null, notifications: [], loading: false, pending: false, error: '', ready: false });
let state = empty();
let generation = 0;
let activeUser = '';
const listeners = new Set<() => void>();
export function readRecords() { return state; }
function update(patch: Partial<Records>) { state = { ...state, ...patch }; listeners.forEach(fn => fn()); }
export function subscribeRecords(fn: () => void) { listeners.add(fn); return () => listeners.delete(fn); }
export function useRecords() { return useSyncExternalStore(subscribeRecords, readRecords); }
export async function refresh() {
  const user = getUser(); if (!user) return;
  const ticket = ++generation;
  update({ loading: true, error: '' });
  try {
    const [projects, problems, requests, funding, users, institutions, notifications] = await Promise.all([
      all<Project>('/projects'), all<Problem>('/problems'), all<Invite>('/requests'), all<Funding>('/funding'), all<User>('/users'), all<Institution>('/institutions'), all<Notice>('/notifications')
    ]);
    const share = user.role === 'student' ? await resource<Share | null>('/portfolio/share') : null;
    const inbox = await all<Review>('/reviews');
    const reviews = await Promise.all(inbox.map(async review => {
      const details = await all<Review>(`/projects/${review.project_id}/reviews`);
      return { ...review, ...details.find(r => r.id === review.id), replies: (await all<Reply>(`/reviews/${review.id}/replies`)).reverse() };
    }));
    const changes = ['student', 'faculty'].includes(user.role) ? await all<InstitutionChange>('/institution-changes') : [];
    const csr = user.role === 'industry' ? await resource<CSRSummary>('/csr/summary') : null;
    const milestones: Milestone[] = []; const feedback: PanelFeedback[] = [];
    const proofs: Proof[] = [];
    if (user.role === 'student' || user.role === 'faculty') {
      for (let i = 0; i < projects.length; i += 4) {
        await Promise.all(projects.slice(i, i + 4).map(async (project, j) => {
          try {
            const detail = await resource<Project>(`/projects/${project.id}`);
            projects[i + j] = { ...project, ...detail };
            proofs.push(...await all<Proof>(`/projects/${project.id}/proofs`));
            if (user.role === 'faculty' || user.role === 'student') {
              const [steps, comments] = await Promise.all([all<Milestone>(`/projects/${project.id}/milestones`), all<PanelFeedback>(`/projects/${project.id}/panel-feedback`)]);
              milestones.push(...steps); feedback.push(...comments);
            }
          } catch (error) {
            // Invited students can see the summary but cannot open a workspace yet.
            if (!(error instanceof Error && 'status' in error && error.status === 403)) throw error;
          }
        }));
      }
    }
    if (ticket === generation && getUser()?.id === user.id) update({ projects, problems, requests, funding, users, institutions, notifications, share, reviews, proofs, changes, milestones, feedback, csr, ready: true });
  } catch (error) { if (ticket === generation) update({ error: error instanceof Error ? error.message : 'Unable to load records' }); }
  finally { if (ticket === generation) update({ loading: false }); }
}
export async function mutate<T>(path: string, method: string, body?: unknown): Promise<T> {
  if (state.pending) throw new Error('Another action is still saving. Please wait.');
  const actor = getUser()?.id;
  update({ pending: true, error: '' });
  try {
    const result = await resource<T>(path, method, body);
    if (getUser()?.id !== actor) throw new Error('Your session changed. Reload the workspace.');
    await refresh();
    if (state.error) update({ error: `The action succeeded, but refreshing failed. Do not resubmit. ${state.error}` });
    return result;
  }
  catch (error) { if (getUser()?.id === actor) update({ error: error instanceof Error ? error.message : 'Could not save' }); throw error; }
  finally { if (getUser()?.id === actor) update({ pending: false }); }
}
subscribeSession(() => { const id = getUser()?.id || ''; if (id !== activeUser) { activeUser = id; generation++; state = empty(); update({}); if (id) void refresh(); } });
let activeUntil = Date.now() + 10 * 60_000;
let lastRefresh = 0;
function resume() { activeUntil = Date.now() + 10 * 60_000; void poll(); }
async function poll() {
  if (!getUser() || document.hidden || state.pending || state.loading || Date.now() > activeUntil || Date.now() - lastRefresh < 15_000) return;
  lastRefresh = Date.now(); await refresh();
}
window.addEventListener('focus', resume);
document.addEventListener('visibilitychange', () => { if (!document.hidden) resume(); });
window.addEventListener('pointerdown', () => { activeUntil = Date.now() + 10 * 60_000; }, { passive: true });
window.addEventListener('keydown', () => { activeUntil = Date.now() + 10 * 60_000; });
window.setInterval(() => { void poll(); }, 30_000);
