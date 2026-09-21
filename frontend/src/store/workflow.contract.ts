/**
 * InnovateX shared workflow store.
 *
 * One tiny store (no provider needed) that lets the three roles talk to each other:
 *   industry  -> funding proof   -> student team leader approves
 *   industry  -> project review  -> student replies with changes -> industry resolves
 *   industry  -> posts problem   -> faculty portal + student Discover
 *   student   -> proof of work (images / links / videos) -> portfolio + public link
 *   student / faculty -> team formation + collaboration requests
 *
 * It is persisted to localStorage and synced across browser tabs, so you can demo
 * "industry in tab 1, student in tab 2". Replace the action functions with API calls
 * when the backend arrives; the components only depend on the exported names.
 *
 * NOTE for hooks: `useWorkflow()` returns the whole state object (stable reference
 * until something changes). Filter / map inside components with useMemo.
 */
import { useMemo, useSyncExternalStore } from 'react';
import { MOCK_PROBLEMS } from '../data/mock';

/* ────────────────────────────── Types ────────────────────────────── */

export type InstitutionType = 'School' | 'College'; // "College" also covers universities

export interface Party { id: string; name: string; avatar: string; institution: string }
export interface Person extends Party { type: InstitutionType; linkedin?: string }

export type FundingStatus = 'awaiting_leader' | 'confirmed' | 'declined';
export interface FundingRecord {
  id: string;
  projectId: string;
  projectTitle: string;
  teamName: string;
  leaderId: string;
  leaderName: string;
  amountLakh: number;
  txnRef: string;
  proofFile: string;
  funder: string;
  funderOrg: string;
  status: FundingStatus;
  declineNote?: string;
  createdAt: number;
  respondedAt?: number;
}

export type ReviewStatus = 'open' | 'addressed' | 'resolved';
export interface ReviewReply {
  id: string;
  authorRole: 'student' | 'industry';
  authorName: string;
  text: string;
  createdAt: number;
}
export interface ProjectReview {
  id: string;
  projectId: string;
  projectTitle: string;
  teamName: string;
  reviewerId: string;
  reviewerName: string;
  reviewerOrg: string;
  summary: string;      // overall description / assessment
  strengths: string;    // optional
  flaws: string;
  improvements: string;
  status: ReviewStatus;
  replies: ReviewReply[];
  createdAt: number;
}

export interface ProofAttachment {
  id: string;
  kind: 'image' | 'link' | 'video';
  url: string;          // data: URL (image), http(s) URL, or blob: URL (uploaded video, session only)
  name?: string;
}
export interface ProofEntry {
  id: string;
  projectId: string;
  title: string;
  description: string;
  attachments: ProofAttachment[];
  authorName: string;
  createdAt: number;
}

export interface ProblemStatement {
  id: string;
  title: string;
  company: string;
  logo: string;
  tags: string[];
  domain: string;
  applicants: number;
  postedDays: number;
  description?: string;
  csr?: boolean;
  createdAt?: number;
}

export interface TeamMember {
  id?: string;
  name: string;
  avatar: string;
  institution: string;
  type: string;
  role: string;
  linkedin?: string;
}
/** Same shape as the rows in MOCK_PROJECTS, plus a few extras for created teams. */
export interface StudentProject {
  id: string;
  title: string;
  stage: string;
  lastUpdated: string;
  proofOfWork: number;
  mentorStatus: string;
  mentorName?: string;
  teamSize: number;
  category: string;
  institution: string;
  description: string;
  activityLog: { text: string; date: string }[];
  team: TeamMember[];
  teamName?: string;
  leaderId: string;
  formedBy: 'student' | 'faculty';
}

export type RequestStatus = 'pending' | 'accepted' | 'declined';
export interface CollabRequest {
  id: string;
  kind: 'member' | 'mentor';
  direction: 'incoming' | 'outgoing';
  projectId: string;
  projectTitle: string;
  projectDescription?: string;
  from: Person;
  to: Party;
  reason: string;
  status: RequestStatus;
  createdAt: number;
}
export type NewCollabRequest = Omit<CollabRequest, 'id' | 'status' | 'createdAt'>;

export interface ShareProfile { ownerId: string; slug: string; enabled: boolean; name: string; institution: string }

export interface RegisteredStudent {
  id: string;
  name: string;
  email: string;
  avatar: string;
  virtualId: string;
  linkedin: string;
  status: string;
  projects: number;
  joinDate: string;
  institution: string;
  type: InstitutionType;
}

interface State {
  fundings: FundingRecord[];
  reviews: ProjectReview[];
  proofs: ProofEntry[];
  problems: ProblemStatement[];
  seenProblems: string[];
  shortlist: string[];
  projects: StudentProject[];
  requests: CollabRequest[];
  profiles: Record<string, ShareProfile>;
  students: RegisteredStudent[];
}

/* ────────────────────── Demo session (swap for auth) ────────────────────── */
// These mirror the hard-coded users in your dashboards. Replace with your auth hook later.

export const CURRENT_STUDENT: Person = {
  id: 'STU-2024-0042', name: 'Arjun Mehta', avatar: 'AM',
  institution: 'IIT Bombay', type: 'College', linkedin: 'linkedin.com/in/arjun-mehta',
};

/**
 * Faculty can form teams ONLY for school students of their own school.
 * College / university faculty don't form teams (students do, incl. cross-institution).
 * To demo the faculty "Form Team" flow, set institution to
 * 'Delhi Public School, R.K. Puram' and institutionType to 'School'.
 */
export const CURRENT_FACULTY: { id: string; name: string; institution: string; institutionType: InstitutionType } = {
  id: 'FAC-2024-0007', name: 'Dr. Priya Sharma',
  institution: 'Delhi Technological University', institutionType: 'College',
};

export const CURRENT_INDUSTRY = {
  id: 'IND-2024-0003', name: 'Rohan Kapoor', org: 'Infosys', title: 'Director of Innovation',
};

/** Demo contact list for "Find teammates". Replace with GET /contacts. */
export const CONTACTS: Person[] = [
  { id: 'STU-2024-0017', name: 'Ananya Iyer', avatar: 'AI', institution: 'IIT Madras', type: 'College', linkedin: 'linkedin.com/in/ananya-iyer' },
  { id: 'STU-2024-0031', name: 'Karan Malhotra', avatar: 'KM', institution: 'BITS Pilani', type: 'College', linkedin: 'linkedin.com/in/karan-malhotra' },
  { id: 'STU-2024-0058', name: 'Meera Nair', avatar: 'MN', institution: 'NIT Trichy', type: 'College', linkedin: 'linkedin.com/in/meera-nair' },
  { id: 'STU-2024-0066', name: 'Aditi Rao', avatar: 'AR', institution: 'IIT Bombay', type: 'College' },
  { id: 'STU-2024-0071', name: 'Rhea Kapoor', avatar: 'RK', institution: 'Delhi Public School, R.K. Puram', type: 'School' },
  { id: 'STU-2024-0072', name: 'Dev Arora', avatar: 'DA', institution: 'Delhi Public School, R.K. Puram', type: 'School' },
  { id: 'STU-2024-0073', name: 'Ishita Bansal', avatar: 'IB', institution: 'Delhi Public School, R.K. Puram', type: 'School' },
  { id: 'STU-2024-0081', name: 'Vihaan Singh', avatar: 'VS', institution: 'The Doon School', type: 'School' },
];

/** Who leads / belongs to the teams that industry sees. Replace with API data. */
export const TEAM_DIRECTORY: Record<string, { leader: Party; memberIds: string[] }> = {
  'Team Nova': { leader: CURRENT_STUDENT, memberIds: [CURRENT_STUDENT.id, 'STU-2024-0017'] },
  'Team Echo': { leader: CONTACTS[1], memberIds: ['STU-2024-0031', CURRENT_STUDENT.id, 'STU-2024-0058'] },
};

export function getTeamLeader(teamName: string): Party {
  return TEAM_DIRECTORY[teamName]?.leader ?? { id: `LEAD-${teamName}`, name: `${teamName} Lead`, avatar: 'TL', institution: '' };
}
export function isMemberOf(teamName: string, studentId: string): boolean {
  return !!TEAM_DIRECTORY[teamName]?.memberIds.includes(studentId);
}

/* ────────────────────────── Team formation rule ────────────────────────── */
/**
 *  - Every member from the SAME school           -> the school's faculty forms the team.
 *  - Anything else (colleges, universities, or members from different institutions)
 *                                                -> students form it themselves, faculty not involved.
 */
export function teamFormationRule(members: Person[]): { formedBy: 'faculty' | 'student'; note: string } {
  const sameSchool =
    members.length > 0 && members.every(m => m.type === 'School' && m.institution === members[0].institution);
  if (sameSchool) return { formedBy: 'faculty', note: "Teams inside one school are formed by that school's faculty." };
  const cross = new Set(members.map(m => m.institution)).size > 1;
  return {
    formedBy: 'student',
    note: cross
      ? 'Cross-institution team: students form it themselves, no faculty approval needed.'
      : 'College / university teams are formed by students.',
  };
}

/* ─────────────────────────────── Helpers ─────────────────────────────── */

const uid = (p: string) => `${p}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

export function timeAgo(ts: number): string {
  const s = Math.max(1, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return d < 30 ? `${d}d ago` : new Date(ts).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

export const slugify = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

export function latestFunding(fundings: FundingRecord[], projectId: string): FundingRecord | undefined {
  return fundings.filter(f => f.projectId === projectId).sort((a, b) => b.createdAt - a.createdAt)[0];
}

/** Public portfolio link. Works with BrowserRouter and HashRouter. */
export function publicProfileUrl(slug: string): string {
  if (typeof window === 'undefined') return `/u/${slug}`;
  const { origin, pathname, hash } = window.location;
  return hash.startsWith('#/') ? `${origin}${pathname}#/u/${slug}` : `${origin}/u/${slug}`;
}

/* ─────────────────────────── Store internals ─────────────────────────── */

const KEY = 'innovatex.workflow.v1';

function seed(): State {
  return {
    fundings: [],
    reviews: [],
    proofs: [],
    problems: [],
    seenProblems: [],
    shortlist: [],
    projects: [],
    // One incoming invite so the accept / decline flow can be demoed.
    requests: [
      {
        id: 'req-seed-1', kind: 'member', direction: 'incoming',
        projectId: 'seed-agrisense', projectTitle: 'AgriSense: soil health alerts for small farms',
        projectDescription: 'SMS + WhatsApp alerts that tell small farmers when soil moisture or pH drifts out of range.',
        from: CONTACTS[0], to: CURRENT_STUDENT,
        reason: 'We need someone strong in dashboards and data viz. Your Portfolio work would fit right in.',
        status: 'pending', createdAt: Date.now() - 3 * 3600_000,
      },
    ],
    profiles: {},
    students: [],
  };
}

function load(): State {
  const base = seed();
  if (typeof window === 'undefined') return base;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return base;
    const parsed = JSON.parse(raw) as Partial<State>;
    const merged: State = { ...base, ...parsed };
    // Uploaded video files are blob: URLs that die with the tab, so drop them on reload.
    merged.proofs = merged.proofs
      .map(p => ({ ...p, attachments: p.attachments.filter(a => !a.url.startsWith('blob:')) }))
      .filter(p => p.attachments.length > 0);
    return merged;
  } catch {
    return base;
  }
}

let state: State = load();
const listeners = new Set<() => void>();
const emit = () => listeners.forEach(l => l());

function persist() {
  try { window.localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* quota / private mode: keep in memory */ }
}
function update(fn: (s: State) => State) {
  state = fn(state);
  persist();
  emit();
}

if (typeof window !== 'undefined') {
  // Keep other tabs in sync (handy for demoing two roles side by side).
  window.addEventListener('storage', e => {
    if (e.key === KEY) { state = load(); emit(); }
  });
}

const subscribe = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l); }; };
export function useWorkflow(): State {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

/** Posted problems (newest first) + your existing MOCK_PROBLEMS, one list. */
export function useAllProblems(): ProblemStatement[] {
  const { problems } = useWorkflow();
  return useMemo(
    () => [
      ...problems.map(p => ({
        ...p,
        postedDays: p.createdAt ? Math.floor((Date.now() - p.createdAt) / 86_400_000) : p.postedDays,
      })),
      ...(MOCK_PROBLEMS as unknown as ProblemStatement[]),
    ],
    [problems],
  );
}

/* ────────────────────────────── Funding ────────────────────────────── */

export function submitFunding(input: {
  project: { id: string; title: string; team: string };
  amountLakh: number; txnRef: string; proofFile: string;
}): FundingRecord {
  const leader = getTeamLeader(input.project.team);
  const rec: FundingRecord = {
    id: uid('fund'),
    projectId: input.project.id, projectTitle: input.project.title, teamName: input.project.team,
    leaderId: leader.id, leaderName: leader.name,
    amountLakh: input.amountLakh, txnRef: input.txnRef, proofFile: input.proofFile,
    funder: CURRENT_INDUSTRY.name, funderOrg: CURRENT_INDUSTRY.org,
    status: 'awaiting_leader', createdAt: Date.now(),
  };
  update(s => ({ ...s, fundings: [rec, ...s.fundings] }));
  return rec;
}

/** Only the team leader may call this (the UI enforces it; enforce on the server too). */
export function respondFunding(id: string, decision: 'confirmed' | 'declined', note?: string) {
  update(s => ({
    ...s,
    fundings: s.fundings.map(f =>
      f.id === id && f.status === 'awaiting_leader'
        ? { ...f, status: decision, declineNote: decision === 'declined' ? note : undefined, respondedAt: Date.now() }
        : f),
  }));
}

/* ────────────────────────────── Reviews ────────────────────────────── */

export function addReview(input: {
  projectId: string; projectTitle: string; teamName: string;
  summary: string; strengths: string; flaws: string; improvements: string;
}): ProjectReview {
  const review: ProjectReview = {
    id: uid('rev'), ...input,
    reviewerId: CURRENT_INDUSTRY.id, reviewerName: CURRENT_INDUSTRY.name, reviewerOrg: CURRENT_INDUSTRY.org,
    status: 'open', replies: [], createdAt: Date.now(),
  };
  update(s => ({ ...s, reviews: [review, ...s.reviews] }));
  return review;
}

export function addReply(
  reviewId: string,
  reply: { authorRole: 'student' | 'industry'; authorName: string; text: string },
  nextStatus?: ReviewStatus,
) {
  update(s => ({
    ...s,
    reviews: s.reviews.map(r =>
      r.id === reviewId
        ? { ...r, status: nextStatus ?? r.status, replies: [...r.replies, { ...reply, id: uid('rep'), createdAt: Date.now() }] }
        : r),
  }));
}

/* ──────────────────────────── Proof of work ──────────────────────────── */

export function addProof(entry: Omit<ProofEntry, 'id' | 'createdAt'>): ProofEntry {
  const full: ProofEntry = { ...entry, id: uid('pow'), createdAt: Date.now() };
  update(s => ({ ...s, proofs: [full, ...s.proofs] }));
  return full;
}
export function removeProof(id: string) {
  const target = state.proofs.find(p => p.id === id);
  target?.attachments.forEach(a => { if (a.url.startsWith('blob:')) URL.revokeObjectURL(a.url); });
  update(s => ({ ...s, proofs: s.proofs.filter(p => p.id !== id) }));
}

/* ─────────────────────────── Problem statements ─────────────────────────── */

export function publishProblem(input: {
  title: string; description: string; domain: string; tags: string[]; csr: boolean;
}): ProblemStatement {
  const p: ProblemStatement = {
    id: uid('prob'),
    title: input.title, description: input.description,
    domain: input.domain || 'General', tags: input.tags, csr: input.csr,
    company: CURRENT_INDUSTRY.org, logo: CURRENT_INDUSTRY.org.slice(0, 2).toUpperCase(),
    applicants: 0, postedDays: 0, createdAt: Date.now(),
  };
  update(s => ({ ...s, problems: [p, ...s.problems] }));
  return p;
}
export function markProblemSeen(id: string) {
  if (state.seenProblems.includes(id)) return;
  update(s => ({ ...s, seenProblems: [...s.seenProblems, id] }));
}
export function toggleShortlist(id: string) {
  update(s => ({
    ...s,
    shortlist: s.shortlist.includes(id) ? s.shortlist.filter(x => x !== id) : [...s.shortlist, id],
  }));
}

/* ───────────────────── Teams, projects, collaboration ───────────────────── */

export function createProject(project: Omit<StudentProject, 'id'>): string {
  const id = uid('proj');
  update(s => ({ ...s, projects: [...s.projects, { ...project, id }] }));
  return id;
}

export function addRequests(reqs: NewCollabRequest[]) {
  const full: CollabRequest[] = reqs.map(r => ({ ...r, id: uid('req'), status: 'pending', createdAt: Date.now() }));
  update(s => ({ ...s, requests: [...full, ...s.requests] }));
}

export function respondCollab(id: string, decision: 'accepted' | 'declined') {
  update(s => {
    const req = s.requests.find(r => r.id === id);
    if (!req || req.status !== 'pending') return s;
    let projects = s.projects;

    if (req.direction === 'incoming' && decision === 'accepted' && req.kind === 'member') {
      const from = req.from;
      projects = [
        ...projects,
        {
          id: `inv-${req.id}`, title: req.projectTitle, stage: 'Ideation', lastUpdated: 'Just now',
          proofOfWork: 0, mentorStatus: 'none', teamSize: 2, category: 'General',
          institution: from.institution, description: req.projectDescription ?? '',
          activityLog: [{ text: `You joined ${from.name}'s team`, date: 'Just now' }],
          team: [
            { id: from.id, name: from.name, avatar: from.avatar, institution: from.institution, type: from.type, role: 'Team Lead', linkedin: from.linkedin },
            { id: CURRENT_STUDENT.id, name: CURRENT_STUDENT.name, avatar: CURRENT_STUDENT.avatar, institution: CURRENT_STUDENT.institution, type: CURRENT_STUDENT.type, role: 'Member', linkedin: CURRENT_STUDENT.linkedin },
          ],
          leaderId: from.id, formedBy: 'student',
        },
      ];
    }

    if (req.direction === 'outgoing') {
      projects = projects.map(p => {
        if (p.id !== req.projectId) return p;
        if (req.kind === 'mentor') {
          return decision === 'accepted'
            ? { ...p, mentorStatus: 'accepted', mentorName: req.to.name }
            : { ...p, mentorStatus: 'none', mentorName: undefined };
        }
        return decision === 'accepted'
          ? { ...p, team: p.team.map(m => (m.id === req.to.id ? { ...m, role: 'Member' } : m)) }
          : { ...p, team: p.team.filter(m => m.id !== req.to.id), teamSize: Math.max(1, p.teamSize - 1) };
      });
    }

    return { ...s, projects, requests: s.requests.map(r => (r.id === id ? { ...r, status: decision } : r)) };
  });
}

/* ───────────────────────────── Public portfolio ───────────────────────────── */

const newSlug = (name: string) => `${slugify(name)}-${Math.random().toString(36).slice(2, 6)}`;

export function ensureProfile(owner: Person): ShareProfile {
  const existing = state.profiles[owner.id];
  if (existing) return existing;
  const profile: ShareProfile = { ownerId: owner.id, slug: newSlug(owner.name), enabled: true, name: owner.name, institution: owner.institution };
  update(s => ({ ...s, profiles: { ...s.profiles, [owner.id]: profile } }));
  return profile;
}
export function setProfileEnabled(ownerId: string, enabled: boolean) {
  update(s => (s.profiles[ownerId] ? { ...s, profiles: { ...s.profiles, [ownerId]: { ...s.profiles[ownerId], enabled } } } : s));
}
export function regenerateSlug(owner: Person) {
  update(s => (s.profiles[owner.id] ? { ...s, profiles: { ...s.profiles, [owner.id]: { ...s.profiles[owner.id], slug: newSlug(owner.name) } } } : s));
}

/* ─────────────────────────── Faculty: register student ─────────────────────────── */

export function registerStudent(s: RegisteredStudent) {
  update(st => ({ ...st, students: [...st.students, s] }));
}
