import { useMemo, useState } from 'react';
import { Badge, Button, Avatar } from './ui';
import { useToast } from './Toast';
import {
  CONTACTS, CURRENT_FACULTY, createProject, teamFormationRule, useWorkflow,
  type Person,
} from '../store/workflow';

/**
 * Faculty "Form Team".
 * Rule: faculty form teams only for SCHOOL students of their own school.
 * College / university faculty do not form teams, and nobody's faculty forms
 * cross-institution teams. Those are formed by students (Student > New Project).
 */
export default function FormTeamModal({ onClose }: { onClose: () => void }) {
  const { toast } = useToast();
  const { students } = useWorkflow();
  const [teamName, setTeamName] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const [leaderId, setLeaderId] = useState('');

  const isSchoolFaculty = CURRENT_FACULTY.institutionType === 'School';

  // Roster = students of this school (demo contacts + students this faculty registered).
  const roster: Person[] = useMemo(() => {
    const registered: Person[] = students
      .filter(s => s.institution === CURRENT_FACULTY.institution)
      .map(s => ({ id: s.virtualId, name: s.name, avatar: s.avatar, institution: s.institution, type: s.type, linkedin: s.linkedin || undefined }));
    const demo = CONTACTS.filter(c => c.type === 'School' && c.institution === CURRENT_FACULTY.institution);
    return [...demo, ...registered];
  }, [students]);

  const members = roster.filter(p => picked.includes(p.id));
  const rule = teamFormationRule(members);
  const canCreate = teamName.trim() && title.trim() && members.length >= 2 && leaderId && picked.includes(leaderId) && rule.formedBy === 'faculty';

  const toggle = (id: string) => {
    setPicked(p => (p.includes(id) ? p.filter(x => x !== id) : [...p, id]));
    if (leaderId === id) setLeaderId('');
  };

  const create = () => {
    if (!canCreate) return;
    createProject({
      title: title.trim(),
      description: description.trim(),
      stage: 'Ideation', lastUpdated: 'Just now', proofOfWork: 0, mentorStatus: 'none',
      teamSize: members.length, category: 'General', institution: CURRENT_FACULTY.institution,
      activityLog: [{ text: `Team formed by ${CURRENT_FACULTY.name}`, date: 'Just now' }],
      team: members.map(m => ({
        id: m.id, name: m.name, avatar: m.avatar, institution: m.institution, type: m.type,
        role: m.id === leaderId ? 'Team Lead' : 'Member', linkedin: m.linkedin,
      })),
      teamName: teamName.trim(), leaderId, formedBy: 'faculty',
    });
    toast(`Team "${teamName.trim()}" formed with ${members.length} students. ${members.find(m => m.id === leaderId)?.name} is the team leader.`, 'success');
    onClose();
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ background: 'rgba(0,0,0,0.75)' }}>
      <div className="w-full max-w-lg rounded-2xl border flex flex-col max-h-[92vh]" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
        <div className="flex items-start justify-between p-5 border-b" style={{ borderColor: 'var(--border)' }}>
          <div>
            <h3 className="font-bold" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>Form a team</h3>
            <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>{CURRENT_FACULTY.institution}</p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--muted-foreground)' }}>✕</button>
        </div>

        {!isSchoolFaculty ? (
          <>
            <div className="p-5 flex flex-col gap-3">
              <p className="text-sm" style={{ color: 'var(--foreground)' }}>
                Faculty form teams only for school students.
              </p>
              <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                Students at colleges and universities form their own teams, including teams across institutions, from
                their <strong>New Project</strong> page. You can still mentor those teams and review their milestones.
              </p>
            </div>
            <div className="p-4 border-t flex justify-end" style={{ borderColor: 'var(--border)' }}>
              <Button onClick={onClose}>Got it</Button>
            </div>
          </>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>Team name <span className="text-red-400">*</span></label>
                  <input value={teamName} onChange={e => setTeamName(e.target.value)} placeholder="Team Aurora"
                    className="px-3 py-2 text-sm rounded-lg border outline-none"
                    style={{ background: 'var(--muted)', borderColor: 'var(--border)', color: 'var(--foreground)' }} />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>Project title <span className="text-red-400">*</span></label>
                  <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Smart water tracker"
                    className="px-3 py-2 text-sm rounded-lg border outline-none"
                    style={{ background: 'var(--muted)', borderColor: 'var(--border)', color: 'var(--foreground)' }} />
                </div>
              </div>
              <textarea value={description} onChange={e => setDescription(e.target.value)} rows={2}
                placeholder="What will this team work on? (optional)"
                className="px-3 py-2 text-sm rounded-lg border outline-none resize-none"
                style={{ background: 'var(--muted)', borderColor: 'var(--border)', color: 'var(--foreground)' }} />

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>
                    Pick at least 2 students, then choose the team leader
                  </p>
                  <Badge>{picked.length} selected</Badge>
                </div>
                {roster.length === 0 ? (
                  <p className="text-xs py-4 text-center" style={{ color: 'var(--muted-foreground)' }}>
                    No students registered yet. Register students first from "My Institution's Students".
                  </p>
                ) : (
                  <div className="flex flex-col gap-2 max-h-56 overflow-y-auto">
                    {roster.map(p => {
                      const on = picked.includes(p.id);
                      return (
                        <div key={p.id} className="flex items-center gap-3 p-2.5 rounded-lg border"
                          style={{ background: on ? 'rgba(124,58,237,0.1)' : 'var(--muted)', borderColor: on ? 'var(--primary)' : 'transparent' }}>
                          <button onClick={() => toggle(p.id)} className="flex items-center gap-3 flex-1 min-w-0 text-left">
                            <Avatar initials={p.avatar} size="sm" />
                            <div className="min-w-0">
                              <p className="text-sm font-medium truncate" style={{ color: 'var(--foreground)' }}>{p.name}</p>
                              <p className="text-xs font-mono" style={{ color: 'var(--muted-foreground)' }}>{p.id}</p>
                            </div>
                          </button>
                          {on ? (
                            <button onClick={() => setLeaderId(p.id)} className="text-xs px-2 py-1 rounded-md border"
                              style={{
                                background: leaderId === p.id ? 'var(--primary)' : 'transparent',
                                borderColor: leaderId === p.id ? 'var(--primary)' : 'var(--border)',
                                color: leaderId === p.id ? 'white' : 'var(--muted-foreground)',
                              }}>
                              {leaderId === p.id ? '★ Leader' : 'Make leader'}
                            </button>
                          ) : (
                            <button onClick={() => toggle(p.id)} className="text-xs px-2 py-1 rounded-md border"
                              style={{ borderColor: 'var(--border)', color: 'var(--muted-foreground)' }}>Add</button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="p-3 rounded-lg text-xs" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', color: '#fbbf24' }}>
                The team leader is the one who approves any funding sent to this team. Cross-institution teams are formed by students, not faculty.
              </div>
            </div>
            <div className="flex gap-3 p-4 border-t" style={{ borderColor: 'var(--border)' }}>
              <Button variant="secondary" onClick={onClose} className="flex-1">Cancel</Button>
              <Button onClick={create} disabled={!canCreate} className="flex-1">Create team</Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
