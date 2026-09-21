import { useState } from 'react';
import { StageBadge, Button } from './ui';
import { useToast } from './Toast';
import { getTeamLeader, submitFunding } from '../store/workflow';

export interface FundableProject {
  id: string;
  title: string;
  team: string;
  institution: string;
  stage: string;
}

/**
 * Industry funding flow.
 * Step 1: amount. Step 2: proof of transaction.
 * Submitting does NOT mark the project as Funded. It goes to the team leader,
 * and only the leader's approval (student side) flips it to Funded.
 */
export default function FundModal({ project, onClose }: { project: FundableProject; onClose: () => void }) {
  const { toast } = useToast();
  const leader = getTeamLeader(project.team);
  const [step, setStep] = useState<'amount' | 'proof'>('amount');
  const [amount, setAmount] = useState('');
  const [txnRef, setTxnRef] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [fileName, setFileName] = useState('');

  const amountNum = parseFloat(amount);
  const validAmount = Number.isFinite(amountNum) && amountNum > 0;

  const handleProofSubmit = () => {
    if (!txnRef.trim() || !confirmed || !validAmount) return;
    submitFunding({ project, amountLakh: amountNum, txnRef: txnRef.trim(), proofFile: fileName });
    toast(
      `Funding of ₹${amountNum}L recorded for "${project.title}". It becomes Funded once ${leader.name} (team leader) approves it.`,
      'success',
    );
    onClose();
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50 p-4" style={{ background: 'rgba(0,0,0,0.75)' }}>
      <div className="w-full max-w-md rounded-2xl border" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
        <div className="flex items-start justify-between p-5 border-b" style={{ borderColor: 'var(--border)' }}>
          <div>
            <h3 className="font-bold" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>
              {step === 'amount' ? 'Fund This Project' : 'Proof of Funding'}
            </h3>
            <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>{project.title}</p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--muted-foreground)' }}>✕</button>
        </div>

        <div className="p-5 flex flex-col gap-4">
          {step === 'amount' ? (
            <>
              <div className="p-3 rounded-lg" style={{ background: 'var(--muted)' }}>
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>{project.title}</p>
                    <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{project.team} · {project.institution}</p>
                  </div>
                  <StageBadge stage={project.stage} />
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>
                  Funding Amount (₹ Lakhs) <span className="text-red-400">*</span>
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>₹</span>
                  <input
                    type="number"
                    min="0"
                    step="0.5"
                    placeholder="e.g. 5"
                    value={amount}
                    onChange={e => setAmount(e.target.value)}
                    className="flex-1 px-3 py-2 text-sm rounded-lg border outline-none"
                    style={{ background: 'var(--muted)', borderColor: 'var(--border)', color: 'var(--foreground)' }}
                  />
                  <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>L</span>
                </div>
              </div>

              <div className="p-3 rounded-lg text-xs" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', color: '#fbbf24' }}>
                Funding needs the approval of the team leader, <strong>{leader.name}</strong>. After you upload proof,
                the project shows <strong>"Awaiting team leader approval"</strong> and turns <strong>Funded</strong> only when they confirm they received the money.
              </div>

              <div className="flex gap-2">
                <Button variant="secondary" onClick={onClose} className="flex-1">Cancel</Button>
                <Button onClick={() => validAmount && setStep('proof')} disabled={!validAmount} className="flex-1">
                  Continue →
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="p-3 rounded-lg text-sm" style={{ background: 'rgba(124,58,237,0.08)', border: '1px solid rgba(124,58,237,0.2)' }}>
                Funding amount: <strong style={{ color: 'var(--accent)' }}>₹{amountNum}L</strong> for {project.title}
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>
                  Transaction Reference Number <span className="text-red-400">*</span>
                </label>
                <input
                  placeholder="e.g. TXN-2024-INFOSYS-8821"
                  value={txnRef}
                  onChange={e => setTxnRef(e.target.value)}
                  className="px-3 py-2 text-sm rounded-lg border outline-none"
                  style={{ background: 'var(--muted)', borderColor: 'var(--border)', color: 'var(--foreground)' }}
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>
                  Upload Transaction Document (mock)
                </label>
                <div
                  className="flex items-center gap-2 px-3 py-3 rounded-lg border border-dashed cursor-pointer"
                  style={{ borderColor: 'var(--border)', color: 'var(--muted-foreground)' }}
                  onClick={() => setFileName('transaction_receipt.pdf')}
                >
                  <span className="text-base">📎</span>
                  <span className="text-sm">{fileName || 'Click to attach document'}</span>
                  {fileName && <span className="ml-auto text-xs" style={{ color: 'var(--accent)' }}>✓</span>}
                </div>
              </div>

              <label className="flex items-start gap-2.5 cursor-pointer" onClick={() => setConfirmed(c => !c)}>
                <div
                  className="w-4 h-4 rounded flex items-center justify-center text-xs flex-shrink-0 mt-0.5"
                  style={{ background: confirmed ? 'var(--primary)' : 'transparent', border: `1.5px solid ${confirmed ? 'var(--primary)' : 'var(--border)'}`, color: 'white' }}
                >
                  {confirmed ? '✓' : ''}
                </div>
                <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  I confirm that the above transaction details are accurate and the funds have been disbursed to the team.
                </p>
              </label>

              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setStep('amount')} className="flex-1">← Back</Button>
                <Button onClick={handleProofSubmit} disabled={!txnRef.trim() || !confirmed} className="flex-1">
                  Send for leader approval
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
