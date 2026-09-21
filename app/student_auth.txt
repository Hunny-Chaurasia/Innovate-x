import { useEffect, useState, type ComponentProps, type ReactNode, type FormEvent } from 'react';
import { Navigate, Link, useLocation, useNavigate } from 'react-router-dom';
import Shell from '../components/Shell';
import { all, authenticate, getUser, logout, restoreSession, roleHome, useSession, type Institution, type Role } from './api';
import { refresh, useRecords } from './records';
export const panel = 'rounded-xl border border-[var(--border)] bg-[var(--card)] p-5';
export const input = 'w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-indigo-500';
export const button = 'rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed';
export function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="flex flex-col gap-2 text-xs text-[var(--muted-foreground)]">{label}{children}</label>; }
export function AuthShell({ role, children }: { role: Exclude<Role, 'mentor'>; children: ReactNode }) {
  const session = useSession(); const data = useRecords(); const location = useLocation();
  useEffect(() => { void restoreSession(); }, []);
  if (session.loading) return <div className="p-8 text-[var(--foreground)]" role="status">Checking your session…</div>;
  if (!session.user && session.error) return <div className={panel}><p role="alert">{session.error}</p><button className={button} onClick={() => void restoreSession()}>Retry session</button><Link to="/login">Sign in</Link></div>;
  if (!session.user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (session.user.role !== role) return <Navigate to={roleHome(session.user.role)} replace />;
  const user = session.user;
  const institution = data.institutions.find(i => i.id === user.institution_id)?.name || user.organization || '';
  const shellUser = { ...user, name: user.display_name, virtualId: user.virtual_id, institution, avatar: user.avatar_url || user.display_name.slice(0, 2).toUpperCase(), department: user.department || '', email: user.email || '' } as unknown as ComponentProps<typeof Shell>['user'];
  return <Shell role={role} user={shellUser}><div className="flex items-center justify-between gap-3 mb-4 text-xs text-[var(--muted-foreground)]"><span>{user.virtual_id} · {institution}</span><button onClick={() => void logout().catch(() => undefined)}>Sign out</button></div>{children}</Shell>;
}
export function Status() {
  const data = useRecords();
  return <><div aria-live="polite" className="text-xs text-[var(--muted-foreground)] mb-3">{data.pending ? 'Saving…' : data.loading ? 'Refreshing records…' : ''}</div>{data.error && <div role="alert" className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">{data.error} <button className="underline ml-3" onClick={() => void refresh()}>Retry loading</button></div>}</>;
}
export function AuthPage({ registration = false }: { registration?: boolean }) {
  const navigate = useNavigate(); const session = useSession();
  const [mode, setMode] = useState<'login' | 'student' | 'admin'>(registration ? 'student' : 'login');
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const loadInstitutions = () => all<Institution>('/institutions').then(setInstitutions).catch(e => setError(e.message));
  useEffect(() => { void loadInstitutions(); }, []);
  useEffect(() => { if (session.user) navigate(roleHome(session.user.role), { replace: true }); }, [session.user, navigate]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError('');
    try {
      const credentials = { email: String(form.get('email')), password: String(form.get('password')) };
      const user = await authenticate(mode === 'login' ? '/auth/login' : '/auth/register', mode === 'login' ? credentials : { ...credentials, display_name: String(form.get('name')), role: mode, ...(mode === 'student' ? { institution_id: String(form.get('institution')) } : { organization: String(form.get('organization') || '') }) });
      navigate(roleHome(user.role), { replace: true });
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to sign in'); } finally { setBusy(false); }
  }
  return <main className="min-h-screen flex items-center justify-center p-6 bg-[var(--background)] text-[var(--foreground)] font-['DM_Sans']"><div className="w-full max-w-md"><Link to="/" className="text-xs text-[var(--muted-foreground)]">← InnovateX</Link><h1 className="text-2xl font-bold mt-5 mb-1">{mode === 'login' ? 'Welcome back' : mode === 'admin' ? 'Initialize InnovateX' : 'Student Access'}</h1><p className="text-sm text-[var(--muted-foreground)] mb-6">{mode === 'admin' ? 'Create the first administrator. Available only before any account exists.' : 'Your campus. Your team. Your next breakthrough.'}</p><form className={`${panel} flex flex-col gap-4`} onSubmit={submit}>
    {mode !== 'login' && <Field label="Full name"><input name="name" required maxLength={200} className={input} autoComplete="name" /></Field>}
    <Field label="Email address"><input name="email" type="email" required className={input} autoComplete="email" /></Field>
    <Field label="Password (12–128 characters)"><input name="password" type="password" required minLength={12} maxLength={128} className={input} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></Field>
    {mode === 'student' && <Field label="Institution"><select name="institution" required className={input}><option value="">Choose your institution</option>{institutions.map(i => <option key={i.id} value={i.id}>{i.name} · {i.kind}</option>)}</select>{!institutions.length && <span>No institutions available. Ask an administrator to add your institution. <button type="button" onClick={() => void loadInstitutions()}>Retry</button></span>}</Field>}
    {mode === 'admin' && <Field label="Organization"><input name="organization" maxLength={240} className={input} /></Field>}
    {mode !== 'login' && <p className="text-xs text-[var(--muted-foreground)]">Your role-based Virtual ID is assigned by the server after registration.</p>}
    {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
    <button disabled={busy || (mode === 'student' && !institutions.length)} className={button}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
    </form><div className="flex flex-wrap gap-4 mt-5 text-xs text-[var(--muted-foreground)]"><button onClick={() => { setMode(mode === 'login' ? 'student' : 'login'); setError(''); }}>{mode === 'login' ? 'Create a student account' : 'Already registered? Sign in'}</button><button onClick={() => { setMode('admin'); setError(''); }}>First administrator setup</button></div></div></main>;
}
export function MentorHome() { const { user } = useSession(); useEffect(() => { void restoreSession(); }, []); return <main className={panel}><h1>Mentor access</h1><p>{user ? `${user.display_name} · ${user.virtual_id}. Mentor workspace is not part of this release.` : 'Sign in to continue.'}</p><Link to="/login">Sign in</Link><button onClick={() => void logout()}>Sign out</button></main>; }
