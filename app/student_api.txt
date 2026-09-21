import { useSyncExternalStore } from 'react';

export type Role = 'student' | 'faculty' | 'industry' | 'mentor' | 'admin';
export interface User { id: string; display_name: string; virtual_id: string; role: Role; institution_id: string | null; organization: string; email?: string; bio?: string; department?: string; linkedin_url?: string | null; avatar_url?: string | null }
export interface Institution { id: string; name: string; kind: 'School' | 'College' }
export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
export interface Session { access_token: string; expires_at: string; user: User }
export class ApiError extends Error {
  constructor(public status: number, message: string, public code = '', public requestId = '') { super(message); }
}
const key = 'innovatex.session.token.v2';
let token = '';
try { token = localStorage.getItem(key) || ''; } catch { /* Storage may be disabled. */ }
let snapshot: { user: User | null; loading: boolean; error: string } = { user: null, loading: !!token, error: '' };
const listeners = new Set<() => void>();
function emit() { listeners.forEach(fn => fn()); }
export function getUser() { return snapshot.user; }
export function sessionToken() { return token; }
export function useSession() { return useSyncExternalStore(fn => { listeners.add(fn); return () => listeners.delete(fn); }, () => snapshot); }
export function subscribeSession(fn: () => void) { listeners.add(fn); return () => listeners.delete(fn); }
export function clearSession() {
  token = ''; try { localStorage.removeItem(key); } catch { /* Memory-only session. */ }
  snapshot = { user: null, loading: false, error: '' }; emit();
}
const base = (import.meta.env.VITE_API_URL || '/api/v1').replace(/\/$/, '');
export async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(`${base}${path}`, { method, signal: controller.signal, cache: 'no-store', headers: { ...(token && !path.startsWith('/public/') ? { Authorization: `Bearer ${token}` } : {}), ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) }, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });
    const payload = await response.json();
    if (!response.ok) {
      if (response.status === 401 && !path.startsWith('/auth/login') && !path.startsWith('/public/')) clearSession();
      const details = (payload.error?.details || []).map((d: { msg?: string; message?: string }) => d.msg || d.message || '').filter(Boolean).join('; ');
      throw new ApiError(response.status, `${payload.error?.message || 'Request failed'}${details ? `: ${details}` : ''}`, payload.error?.code, payload.request_id);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0, 'Connection failed or timed out. Check your connection and retry.');
  } finally { window.clearTimeout(timeout); }
}
export async function resource<T>(path: string, method = 'GET', body?: unknown): Promise<T> { return (await request<{ data: T }>(path, method, body)).data; }
export async function all<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  for (let offset = 0; offset <= 100000; offset += 100) {
    const page = await request<Page<T>>(`${path}${path.includes('?') ? '&' : '?'}limit=100&offset=${offset}`);
    items.push(...page.items);
    if (items.length >= page.total || !page.items.length) break;
  }
  return items;
}
export async function authenticate(path: '/auth/login' | '/auth/register', body: object) {
  const session = await resource<Session>(path, 'POST', body);
  token = session.access_token;
  try { localStorage.setItem(key, token); } catch { /* Continue with in-memory token. */ }
  snapshot = { user: session.user, loading: false, error: '' }; emit();
  return session.user;
}
let restoring: Promise<void> | null = null;
export function restoreSession(): Promise<void> {
  if (restoring) return restoring;
  if (!token) return Promise.resolve();
  snapshot = { ...snapshot, loading: true, error: '' }; emit();
  restoring = resource<User>('/auth/me').then(user => { snapshot = { user, loading: false, error: '' }; emit(); }).catch(error => {
    snapshot = { user: null, loading: false, error: error instanceof Error ? error.message : 'Session unavailable' }; emit();
  }).finally(() => { restoring = null; });
  return restoring;
}
export async function logout() { try { await resource('/auth/logout', 'POST'); } finally { clearSession(); } }
export const roleHome = (role: Role) => role === 'mentor' ? '/mentor' : `/${role}`;
window.addEventListener('storage', event => { if (event.key === key) { token = event.newValue || ''; snapshot = { user: null, loading: !!token, error: '' }; emit(); if (token) void restoreSession(); } });
