import { useMemo, useSyncExternalStore } from 'react';
import type * as Legacy from './workflow.contract';
export type { InstitutionType, Party, Person, FundingStatus, FundingRecord, ReviewStatus, ReviewReply, ProjectReview, ProofAttachment, ProofEntry, RequestStatus, CollabRequest, NewCollabRequest, StudentProject, ShareProfile, ProblemStatement, TeamMember, RegisteredStudent } from './workflow.contract';
import { getUser, resource } from '../integration/api';
import { readRecords, subscribeRecords, mutate } from '../integration/records';
import type { Project, Share } from '../integration/records';
type Bag = Record<string, unknown>;
const bag = (value: unknown): Bag => value && typeof value === 'object' ? value as Bag : {};
const str = (value: unknown) => typeof value === 'string' ? value : '';
const date = (value: string) => Date.parse(value) || 0;
function identity(id?: string) {
  const data = readRecords(); const user = id ? data.users.find(u => u.id === id) : getUser();
  const institution = data.institutions.find(i => i.id === user?.institution_id);
  return { id: user?.id || '', name: user?.display_name || '', avatar: user?.display_name?.slice(0, 2).toUpperCase() || '', institution: institution?.name || user?.organization || '', type: institution?.kind || 'College', institutionType: institution?.kind || 'College', virtualId: user?.virtual_id || '', org: user?.organization || '', organization: user?.organization || '', linkedin: user?.linkedin_url || '', role: user?.role || '' };
}
export let CURRENT_STUDENT = identity() as typeof Legacy.CURRENT_STUDENT;
export let CURRENT_FACULTY = identity() as typeof Legacy.CURRENT_FACULTY;
export let CURRENT_INDUSTRY = identity() as typeof Legacy.CURRENT_INDUSTRY;
export let CONTACTS = [] as unknown as typeof Legacy.CONTACTS;
export let TEAM_DIRECTORY = {} as typeof Legacy.TEAM_DIRECTORY;
function project(p: Project) {
  const data = readRecords();
  return { ...p, teamName: p.team?.name || p.team_name || '', leaderId: p.team?.leader_id || p.leader_id || '', formedBy: p.team?.formed_by || 'student', stage: p.display_stage || p.stage, description: p.description || '', institution: data.institutions.find(i => i.id === p.institution_id)?.name || '', team: (p.memberships || []).map(m => ({ ...identity(m.user_id), role: m.user_id === p.team?.leader_id ? 'Leader' : m.status, status: m.status })), activityLog: [], tags: [], mentor: p.mentor_id ? identity(p.mentor_id) : null, createdAt: date(p.created_at) };
}
function snapshot() {
  const d = readRecords(); const owner = identity();
  const profiles = d.share ? [{ ownerId: owner.id, name: owner.name, institution: owner.institution, slug: d.share.slug, enabled: d.share.enabled }] : [];
  const projects = d.projects.map(project);
  const title = (id: string) => projects.find(p => p.id === id)?.title || '';
  const team = (id: string) => projects.find(p => p.id === id)?.teamName || '';
  const requests = d.requests.map(r => ({ ...r, projectId: r.project_id, projectTitle: title(r.project_id), from: identity(r.sender_id), to: identity(r.recipient_id), direction: r.recipient_id === owner.id ? 'incoming' : 'outgoing', createdAt: date(r.created_at) }));
  const proofs = d.proofs.map(p => ({ ...p, projectId: p.project_id, authorName: identity(p.author_id).name, createdAt: date(p.created_at) }));
  const fundings = d.funding.map(f => ({ ...f, projectId: f.project_id, projectTitle: title(f.project_id), teamName: team(f.project_id), leaderId: f.leader_id, leaderName: identity(f.leader_id).name, amountLakh: Number(f.amount_lakh), txnRef: f.txn_ref, proofFile: f.proof_file_name, funder: identity(f.funder_id).name, funderOrg: identity(f.funder_id).institution, declineNote: f.decline_note, createdAt: date(f.created_at), respondedAt: f.responded_at ? date(f.responded_at) : undefined }));
  const reviews = d.reviews.map(r => ({ ...r, projectId: r.project_id, projectTitle: title(r.project_id), teamName: team(r.project_id), reviewerId: r.reviewer_id, reviewerName: identity(r.reviewer_id).name, reviewerOrg: identity(r.reviewer_id).institution, strengths: r.strengths || '', flaws: r.flaws || '', improvements: r.improvements || '', replies: r.replies.map(a => ({ id: a.id, authorRole: a.author_role, authorName: identity(a.author_id).name, text: a.body, createdAt: date(a.created_at) })), createdAt: date(r.created_at) }));
  const problems = d.problems.map(p => ({ ...p, postedBy: identity(p.publisher_id).name, organization: identity(p.publisher_id).institution, createdAt: date(p.created_at), category: p.domain }));
  return { ...d, projects, studentProjects: projects, requests, collabRequests: requests, proofs, proofEntries: proofs, fundings, funding: fundings, reviews, problems, profiles, shareProfiles: profiles, students: [], registeredStudents: [], seenProblems: d.problems.filter(p => p.seen_at).map(p => p.id), shortlistedProblems: d.problems.filter(p => p.shortlisted_at).map(p => p.id), shortlists: d.problems.filter(p => p.shortlisted_at).map(p => p.id) };
}
let cached = snapshot();
subscribeRecords(() => {
  CURRENT_STUDENT = identity() as typeof Legacy.CURRENT_STUDENT;
  CURRENT_FACULTY = identity() as typeof Legacy.CURRENT_FACULTY;
  CURRENT_INDUSTRY = identity() as typeof Legacy.CURRENT_INDUSTRY;
  const contacts = readRecords().users.map(u => identity(u.id));
    CONTACTS = Object.assign(contacts, { students: contacts.filter(u => u.role === 'student'), mentors: contacts.filter(u => ['mentor', 'faculty', 'industry'].includes(u.role)) }) as unknown as typeof Legacy.CONTACTS;
  TEAM_DIRECTORY = Object.fromEntries(readRecords().projects.map(p => [p.team?.name || p.team_name || '', { leader: identity(p.team?.leader_id || p.leader_id), members: (p.memberships || []).filter(m => m.status === 'Member').map(m => identity(m.user_id)) }])) as unknown as typeof Legacy.TEAM_DIRECTORY;
  cached = snapshot();
});
export function useWorkflow() { return useSyncExternalStore(subscribeRecords, () => cached) as unknown as ReturnType<typeof Legacy.useWorkflow> & { loading: boolean; pending: boolean; error: string }; }
export function useAllProblems() { const value = useSyncExternalStore(subscribeRecords, () => cached); return useMemo(() => value.problems as unknown as ReturnType<typeof Legacy.useAllProblems>, [value]); }
export const slugify = (text: string) => text.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
export function timeAgo(time: number) { const n = Math.max(0, Math.floor((Date.now() - time) / 60000)); return n < 1 ? 'Just now' : n < 60 ? `${n}m ago` : n < 1440 ? `${Math.floor(n / 60)}h ago` : `${Math.floor(n / 1440)}d ago`; }
export const publicProfileUrl = (slug: string) => `${window.location.origin}${window.location.hash.startsWith('#/') ? '/#' : ''}/u/${encodeURIComponent(slug)}`;
export function latestFunding(...args: Parameters<typeof Legacy.latestFunding>) { return [...args[0]].filter(f => f.projectId === args[1]).sort((a, b) => b.createdAt - a.createdAt || b.id.localeCompare(a.id))[0]; }
export function getTeamLeader(...args: Parameters<typeof Legacy.getTeamLeader>) { const p = readRecords().projects.find(p => (p.team?.name || p.team_name) === args[0]); return identity(p?.team?.leader_id || p?.leader_id) as ReturnType<typeof Legacy.getTeamLeader>; }
export function isMemberOf(...args: Parameters<typeof Legacy.isMemberOf>) { return readRecords().projects.some(p => (p.team?.name || p.team_name) === args[0] && p.memberships?.some(m => m.user_id === args[1] && m.status === 'Member')); }
export function teamFormationRule(...args: Parameters<typeof Legacy.teamFormationRule>) { const members = args[0]; const sameSchool = members.length > 0 && members.every(m => m.type === 'School' && m.institution === members[0].institution); return { formedBy: sameSchool ? 'faculty' : 'student', note: sameSchool ? 'Same-school teams must be formed by faculty.' : 'Student-led team. School-only teams need a mentor.' } as ReturnType<typeof Legacy.teamFormationRule>; }
function command(path: string, method: string, body?: unknown) { void mutate(path, method, body).catch(() => undefined); }
export function respondFunding(...args: Parameters<typeof Legacy.respondFunding>) { command(`/funding/${args[0]}/respond`, 'POST', { status: args[1], receipt_confirmed: args[1] === 'confirmed', decline_note: args[2] || '' }); }
export function submitFunding(...args: Parameters<typeof Legacy.submitFunding>) { const a = bag(args[0]); command(`/projects/${str(bag(a.project).id)}/funding`, 'POST', { amount_lakh: String(a.amountLakh), txn_ref: a.txnRef, proof_file_name: a.proofFile || '', transfer_confirmed: true }); }
export function addReview(...args: Parameters<typeof Legacy.addReview>) { const a = bag(args[0]); command(`/projects/${str(a.projectId)}/reviews`, 'POST', { summary: a.summary, strengths: a.strengths || '', flaws: a.flaws, improvements: a.improvements }); }
export function addReply(...args: Parameters<typeof Legacy.addReply>) { const a = bag(args[1]); command(`/reviews/${args[0]}/replies`, 'POST', { body: a.text, action: args[2] === 'resolved' ? 'resolve' : args[2] === 'open' ? 'request_changes' : args[2] === 'addressed' ? 'changes_done' : 'comment' }); }
export function addProof(...args: Parameters<typeof Legacy.addProof>) { const a = bag(args[0]); command(`/projects/${str(a.projectId)}/proofs`, 'POST', { title: a.title, description: a.description || '', attachments: (Array.isArray(a.attachments) ? a.attachments : []).map(value => { const v = bag(value); return { kind: v.kind, url: v.url, name: v.name || '', source: 'external' }; }) }); }
export function removeProof(...args: Parameters<typeof Legacy.removeProof>) { command(`/proofs/${args[0]}`, 'DELETE'); }
export function publishProblem(...args: Parameters<typeof Legacy.publishProblem>) { const a = bag(args[0]); command('/problems', 'POST', { title: a.title, description: a.description, domain: a.domain, tags: a.tags, csr: a.csr, status: 'published' }); }
export function markProblemSeen(...args: Parameters<typeof Legacy.markProblemSeen>) { command(`/problems/${args[0]}`, 'GET'); }
export function toggleShortlist(...args: Parameters<typeof Legacy.toggleShortlist>) { command(`/problems/${args[0]}/shortlist`, 'PUT', { shortlisted: !readRecords().problems.find(p => p.id === args[0])?.shortlisted_at }); }
export function respondCollab(...args: Parameters<typeof Legacy.respondCollab>) { command(`/requests/${args[0]}/respond`, 'POST', { status: args[1] }); }
export async function createProject(...args: Parameters<typeof Legacy.createProject>) { const a = bag(args[0]); const members = Array.isArray(a.team) ? a.team.map(m => str(bag(m).id)) : []; const p = await mutate<Project>('/projects', 'POST', { name: a.teamName || a.title, title: a.title, description: a.description, category: a.category, leader_id: a.leaderId || getUser()?.id, student_ids: members, reason: a.reason || 'Please collaborate with our project team.', ...(a.mentorId ? { mentor_id: a.mentorId } : {}) }); return p.id; }
export async function addRequests(...args: Parameters<typeof Legacy.addRequests>) { for (const request of args[0]) { const r = bag(request); await mutate(`/projects/${str(r.projectId)}/requests`, 'POST', { recipient_id: bag(r.to).id, kind: r.kind, reason: r.reason }); } }
export function ensureProfile(..._args: Parameters<typeof Legacy.ensureProfile>) { const share = readRecords().share; const owner = identity(); return { ownerId: owner.id, name: owner.name, institution: owner.institution, slug: share?.slug || '', enabled: share?.enabled || false } as ReturnType<typeof Legacy.ensureProfile>; }
export function setProfileEnabled(...args: Parameters<typeof Legacy.setProfileEnabled>) { command('/portfolio/share', 'PUT', { enabled: args[1] }); }
export function regenerateSlug(...args: Parameters<typeof Legacy.regenerateSlug>): ReturnType<typeof Legacy.regenerateSlug> { command('/portfolio/share', 'PUT', { enabled: readRecords().share?.enabled || false, regenerate: true }); return ensureProfile(...args as Parameters<typeof Legacy.ensureProfile>) as unknown as ReturnType<typeof Legacy.regenerateSlug>; }
export async function registerStudent(...args: Parameters<typeof Legacy.registerStudent>): Promise<ReturnType<typeof Legacy.registerStudent>> { const a = bag(args[0]); const user = await resource<Bag>('/users', 'POST', { email: a.email, password: a.password, display_name: a.name, role: 'student', institution_id: getUser()?.institution_id }); return { ...user, id: user.id, virtualId: user.virtual_id, name: user.display_name, linkedin: user.linkedin_url, institution: identity().institution } as unknown as ReturnType<typeof Legacy.registerStudent>; }
