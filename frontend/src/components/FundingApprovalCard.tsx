import { useState } from 'react';
import { Card, Badge, Button } from './ui';
import { useToast } from './Toast';
import { CURRENT_STUDENT, respondFunding, timeAgo, type FundingRecord } from '../store/workflow';

/**
 * One funding record as the student sees it.
 * Only the team leader gets Approve / Decline. Everyone else sees who has to approve.
 */
export default function FundingApprovalCard({ record }: { record: FundingRecord }) {
  const { toast } = useToast();
  const isLeader = record.leaderId === CURRENT_STUDENT.id;
  const [received, setReceived] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [note, setNote] = useState('');

  const approve = () => {
    if (!received) return;
    respondFunding(record.id, 'confirmed');
    toast(`Funding of ₹${record.amountLakh}L from ${record.funderOrg} confirmed. "${record.projectTitle}" is now Funded.`, 'success');
  };
  const decline = () => {
    if (note.trim().length < 5) return;
    respondFunding(record.id, 'declined', note.trim());
    toast(`Funding declined. ${record.funderOrg} has been told why.`, 'warning');
  };

  return (
    <Card className="p-5">
      <div className="flex items-start gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <p className="font-semibold" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>{record.projectTitle}</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            {record.teamName} · from {record.funder}, {record.funderOrg} · {timeAgo(record.createdAt)}
          </p>
          <p className="text-xs mt-2 font-mono" style={{ color: 'var(--muted-foreground)' }}>
            Ref: {record.txnRef}{record.proofFile ? ` · 📎 ${record.proofFile}` : ''}
          </p>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-xl font-bold" style={{ fontFamily: 'DM Sans', color: 'var(--accent)' }}>₹{record.amountLakh}L</p>
          {record.status === 'confirmed' && <Badge variant="success">✓ Confirmed</Badge>}
          {record.status === 'declined' && <Badge variant="danger">✕ Declined</Badge>}
          {record.status === 'awaiting_leader' && <Badge variant="pending">Awaiting leader</Badge>}
        </div>
      </div>

      {record.status === 'awaiting_leader' && isLeader && !declining && (
        <div className="mt-4 pt-4 border-t flex flex-col gap-3" style={{ borderColor: 'var(--border)' }}>
          <label className="flex items-start gap-2.5 cursor-pointer" onClick={() => setReceived(r => !r)}>
            <div
              className="w-4 h-4 rounded flex items-center justify-center text-xs flex-shrink-0 mt-0.5"
              style={{ background: received ? 'var(--primary)' : 'transparent', border: `1.5px solid ${received ? 'var(--primary)' : 'var(--border)'}`, color: 'white' }}
            >
              {received ? '✓' : ''}
            </div>
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              I am the team leader and I confirm the team has received ₹{record.amountLakh}L against reference {record.txnRef}.
            </p>
          </label>
          <div className="flex gap-2 justify-end">
            <Button variant="danger" size="sm" onClick={() => setDeclining(true)}>Decline</Button>
            <Button size="sm" onClick={approve} disabled={!received}>Approve funding</Button>
          </div>
        </div>
      )}

      {record.status === 'awaiting_leader' && isLeader && declining && (
        <div className="mt-4 pt-4 border-t flex flex-col gap-2" style={{ borderColor: 'var(--border)' }}>
          <label className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>
            Why are you declining? (the funder will see this) <span className="text-red-400">*</span>
          </label>
          <textarea
            rows={3}
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="e.g. Amount not received yet, or the reference number does not match our bank statement."
            className="px-3 py-2 text-sm rounded-lg border outline-none resize-none"
            style={{ background: 'var(--muted)', borderColor: 'var(--border)', color: 'var(--foreground)' }}
          />
          <div className="flex gap-2 justify-end">
            <Button variant="secondary" size="sm" onClick={() => { setDeclining(false); setNote(''); }}>Back</Button>
            <Button variant="danger" size="sm" onClick={decline} disabled={note.trim().length < 5}>Confirm decline</Button>
          </div>
        </div>
      )}

      {record.status === 'awaiting_leader' && !isLeader && (
        <p className="mt-4 pt-3 border-t text-xs" style={{ borderColor: 'var(--border)', color: 'var(--muted-foreground)' }}>
          Only the team leader, <strong style={{ color: 'var(--foreground)' }}>{record.leaderName}</strong>, can approve this funding.
        </p>
      )}

      {record.status === 'declined' && record.declineNote && (
        <p className="mt-4 pt-3 border-t text-xs" style={{ borderColor: 'var(--border)', color: '#f87171' }}>
          Reason given: {record.declineNote}
        </p>
      )}
    </Card>
  );
}
