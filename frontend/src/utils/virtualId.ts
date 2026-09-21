/**
 * Role-based Virtual IDs.
 *   STU-2026-0043  -> student
 *   FAC-2026-0008  -> faculty
 *   IND-2026-0004  -> industry partner
 *   MEN-2026-0002  -> mentor
 *   ADM-2026-0001  -> admin
 *
 * Use `generateVirtualId(role, existingIds)` anywhere an account is created
 * (faculty registering a student, industry / faculty sign-up, admin invite ...).
 * The sequence number is per-role and always max(existing) + 1, so two people
 * never get the same ID, even across years.
 */
export type VirtualIdRole = 'student' | 'faculty' | 'industry' | 'mentor' | 'admin';

export const ROLE_PREFIX: Record<VirtualIdRole, string> = {
  student: 'STU',
  faculty: 'FAC',
  industry: 'IND',
  mentor: 'MEN',
  admin: 'ADM',
};

export const ROLE_LABEL: Record<VirtualIdRole, string> = {
  student: 'Student',
  faculty: 'Faculty',
  industry: 'Industry Partner',
  mentor: 'Mentor',
  admin: 'Admin',
};

const PATTERN = /^([A-Z]{3})-(\d{4})-(\d{4})$/;

export function generateVirtualId(
  role: VirtualIdRole,
  existingIds: string[] = [],
  year: number = new Date().getFullYear(),
): string {
  const prefix = ROLE_PREFIX[role];
  let max = 0;
  for (const id of existingIds) {
    const m = PATTERN.exec(id);
    if (m && m[1] === prefix) max = Math.max(max, Number(m[3]));
  }
  return `${prefix}-${year}-${String(max + 1).padStart(4, '0')}`;
}

export function parseVirtualId(id: string): { role: VirtualIdRole; year: number; seq: number } | null {
  const m = PATTERN.exec(id);
  if (!m) return null;
  const role = (Object.keys(ROLE_PREFIX) as VirtualIdRole[]).find(r => ROLE_PREFIX[r] === m[1]);
  return role ? { role, year: Number(m[2]), seq: Number(m[3]) } : null;
}
