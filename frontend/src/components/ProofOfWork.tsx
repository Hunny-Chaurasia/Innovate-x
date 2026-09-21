import { useRef, useState } from 'react';
import { Card, Badge, Button } from './ui';
import { useToast } from './Toast';
import {
  useWorkflow, addProof, removeProof, timeAgo, CURRENT_STUDENT,
  type ProofAttachment, type ProofEntry,
} from '../store/workflow';

const MAX_IMAGE_MB = 2;
const MAX_VIDEO_MB = 100;

const readAsDataUrl = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });

const normalizeUrl = (v: string) => (/^https?:\/\//i.test(v.trim()) ? v.trim() : `https://${v.trim()}`);
function isValidUrl(v: string) {
  try {
    const u = new URL(normalizeUrl(v));
    return u.hostname.includes('.');
  } catch {
    return false;
  }
}
const hostOf = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } };

/** YouTube / Vimeo / Google Drive get an inline player. Direct files use <video>. Anything else is a link. */
function toEmbed(url: string): { type: 'iframe' | 'video' | 'link'; src: string } {
  if (url.startsWith('blob:')) return { type: 'video', src: url };
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^(www\.|m\.)/, '');
    if (host === 'youtube.com') {
      const id = u.searchParams.get('v') ?? (u.pathname.startsWith('/shorts/') ? u.pathname.split('/')[2] : null);
      if (id) return { type: 'iframe', src: `https://www.youtube.com/embed/${id}` };
    }
    if (host === 'youtu.be' && u.pathname.length > 1) return { type: 'iframe', src: `https://www.youtube.com/embed/${u.pathname.slice(1)}` };
    if (host === 'vimeo.com') {
      const id = u.pathname.split('/').filter(Boolean)[0];
      if (id && /^\d+$/.test(id)) return { type: 'iframe', src: `https://player.vimeo.com/video/${id}` };
    }
    if (host === 'drive.google.com') {
      const m = u.pathname.match(/\/file\/d\/([^/]+)/);
      if (m) return { type: 'iframe', src: `https://drive.google.com/file/d/${m[1]}/preview` };
    }
    if (/\.(mp4|webm|ogg|mov)$/i.test(u.pathname)) return { type: 'video', src: url };
  } catch { /* fall through */ }
  return { type: 'link', src: url };
}

const uid = () => Math.random().toString(36).slice(2, 10);

/* ────────────────────────────── Display ────────────────────────────── */

function AttachmentView({ a, onZoom }: { a: ProofAttachment; onZoom: (src: string) => void }) {
  if (a.kind === 'image') {
    return (
      <button onClick={() => onZoom(a.url)} className="rounded-lg overflow-hidden border" style={{ borderColor: 'var(--border)' }} title={a.name}>
        <img src={a.url} alt={a.name ?? 'Proof of work'} className="w-full h-28 object-cover" />
      </button>
    );
  }
  if (a.kind === 'video') {
    const e = toEmbed(a.url);
    if (e.type === 'iframe') {
      return (
        <div className="rounded-lg overflow-hidden border col-span-2" style={{ borderColor: 'var(--border)', aspectRatio: '16 / 9' }}>
          <iframe src={e.src} title={a.name ?? 'Video'} className="w-full h-full" allowFullScreen loading="lazy" />
        </div>
      );
    }
    if (e.type === 'video') {
      return (
        <div className="rounded-lg overflow-hidden border col-span-2" style={{ borderColor: 'var(--border)' }}>
          <video src={e.src} controls className="w-full max-h-64 bg-black" />
        </div>
      );
    }
  }
  return (
    <a
      href={a.url}
      target="_blank"
      rel="noreferrer"
      className="flex items-center gap-2 px-3 py-2 rounded-lg border text-xs hover:underline col-span-2"
      style={{ borderColor: 'var(--border)', color: 'var(--accent)' }}
    >
      <span>{a.kind === 'video' ? '🎬' : '🔗'}</span>
      <span className="truncate">{a.name || hostOf(a.url)}</span>
      <span className="ml-auto flex-shrink-0" style={{ color: 'var(--muted-foreground)' }}>{hostOf(a.url)} ↗</span>
    </a>
  );
}

function EntryCard({ entry, editable, onZoom }: { entry: ProofEntry; editable: boolean; onZoom: (src: string) => void }) {
  const { toast } = useToast();
  const counts = {
    image: entry.attachments.filter(a => a.kind === 'image').length,
    link: entry.attachments.filter(a => a.kind === 'link').length,
    video: entry.attachments.filter(a => a.kind === 'video').length,
  };
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0">
          <p className="font-semibold text-sm" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>{entry.title}</p>
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            {entry.authorName} · {timeAgo(entry.createdAt)}
            {counts.image > 0 && ` · ${counts.image} image${counts.image > 1 ? 's' : ''}`}
            {counts.video > 0 && ` · ${counts.video} video${counts.video > 1 ? 's' : ''}`}
            {counts.link > 0 && ` · ${counts.link} link${counts.link > 1 ? 's' : ''}`}
          </p>
        </div>
        {editable && (
          <Button variant="ghost" size="sm" onClick={() => { removeProof(entry.id); toast('Proof of work removed.', 'info'); }}>
            Remove
          </Button>
        )}
      </div>
      {entry.description && (
        <p className="text-sm mb-3 whitespace-pre-line" style={{ color: 'var(--muted-foreground)' }}>{entry.description}</p>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {entry.attachments.map(a => <AttachmentView key={a.id} a={a} onZoom={onZoom} />)}
      </div>
    </Card>
  );
}

/* ────────────────────────────── Main ────────────────────────────── */

export default function ProofOfWork({ projectId, editable = true }: { projectId: string; editable?: boolean }) {
  const { toast } = useToast();
  const { proofs } = useWorkflow();
  const entries = proofs.filter(p => p.projectId === projectId);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [staged, setStaged] = useState<ProofAttachment[]>([]);
  const [mode, setMode] = useState<'image' | 'link' | 'video'>('image');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkLabel, setLinkLabel] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [zoom, setZoom] = useState<string | null>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const videoInput = useRef<HTMLInputElement>(null);

  const stage = (a: Omit<ProofAttachment, 'id'>) => setStaged(s => [...s, { ...a, id: uid() }]);

  const onImages = async (files: FileList | null) => {
    if (!files) return;
    for (const f of Array.from(files)) {
      if (!f.type.startsWith('image/')) { toast(`${f.name} is not an image.`, 'warning'); continue; }
      if (f.size > MAX_IMAGE_MB * 1024 * 1024) { toast(`${f.name} is over ${MAX_IMAGE_MB} MB. Compress it or share it as a link.`, 'warning'); continue; }
      try { stage({ kind: 'image', url: await readAsDataUrl(f), name: f.name }); }
      catch { toast(`Could not read ${f.name}.`, 'warning'); }
    }
    if (imageInput.current) imageInput.current.value = '';
  };

  const onVideoFile = (files: FileList | null) => {
    const f = files?.[0];
    if (!f) return;
    if (!f.type.startsWith('video/')) { toast(`${f.name} is not a video.`, 'warning'); return; }
    if (f.size > MAX_VIDEO_MB * 1024 * 1024) { toast(`Video is over ${MAX_VIDEO_MB} MB. Upload it to YouTube or Drive and paste the link.`, 'warning'); return; }
    stage({ kind: 'video', url: URL.createObjectURL(f), name: f.name });
    if (videoInput.current) videoInput.current.value = '';
  };

  const addLink = () => {
    if (!isValidUrl(linkUrl)) { toast('Enter a valid link, e.g. github.com/your-repo', 'warning'); return; }
    stage({ kind: 'link', url: normalizeUrl(linkUrl), name: linkLabel.trim() || undefined });
    setLinkUrl(''); setLinkLabel('');
  };
  const addVideoLink = () => {
    if (!isValidUrl(videoUrl)) { toast('Enter a valid video link (YouTube, Vimeo, Drive or a direct .mp4).', 'warning'); return; }
    stage({ kind: 'video', url: normalizeUrl(videoUrl) });
    setVideoUrl('');
  };

  const canSubmit = title.trim().length >= 3 && staged.length > 0;
  const submit = () => {
    if (!canSubmit) return;
    addProof({ projectId, title: title.trim(), description: description.trim(), attachments: staged, authorName: CURRENT_STUDENT.name });
    setTitle(''); setDescription(''); setStaged([]);
    toast('Proof of work added to your project and portfolio.', 'success');
  };

  const inputStyle = { background: 'var(--muted)', borderColor: 'var(--border)', color: 'var(--foreground)' };

  return (
    <div className="flex flex-col gap-4">
      {editable && (
        <Card className="p-4 flex flex-col gap-3">
          <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--muted-foreground)' }}>Add proof of work</p>

          <input
            placeholder="What did you build or achieve? e.g. Working prototype demo"
            value={title}
            onChange={e => setTitle(e.target.value)}
            className="px-3 py-2 text-sm rounded-lg border outline-none"
            style={inputStyle}
          />
          <textarea
            placeholder="Add context: what this shows, what changed since the last update…"
            value={description}
            onChange={e => setDescription(e.target.value)}
            rows={2}
            className="px-3 py-2 text-sm rounded-lg border outline-none resize-none"
            style={inputStyle}
          />

          <div className="flex gap-1 p-1 rounded-lg w-fit" style={{ background: 'var(--secondary)' }}>
            {(['image', 'link', 'video'] as const).map(m => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className="px-3 py-1.5 rounded-md text-sm font-medium"
                style={{ background: mode === m ? 'var(--card)' : 'transparent', color: mode === m ? 'var(--foreground)' : 'var(--muted-foreground)' }}
              >
                {m === 'image' ? '🖼 Images' : m === 'link' ? '🔗 Links' : '🎬 Videos'}
              </button>
            ))}
          </div>

          {mode === 'image' && (
            <div>
              <input ref={imageInput} type="file" accept="image/*" multiple hidden onChange={e => onImages(e.target.files)} />
              <button
                onClick={() => imageInput.current?.click()}
                className="w-full flex items-center justify-center gap-2 px-3 py-5 rounded-lg border border-dashed text-sm"
                style={{ borderColor: 'var(--border)', color: 'var(--muted-foreground)' }}
              >
                📎 Choose screenshots or photos (max {MAX_IMAGE_MB} MB each)
              </button>
            </div>
          )}

          {mode === 'link' && (
            <div className="flex gap-2 flex-wrap">
              <input
                placeholder="github.com/team/repo, figma link, live demo…"
                value={linkUrl}
                onChange={e => setLinkUrl(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addLink()}
                className="flex-1 min-w-48 px-3 py-2 text-sm rounded-lg border outline-none"
                style={inputStyle}
              />
              <input
                placeholder="Label (optional)"
                value={linkLabel}
                onChange={e => setLinkLabel(e.target.value)}
                className="w-40 px-3 py-2 text-sm rounded-lg border outline-none"
                style={inputStyle}
              />
              <Button variant="secondary" size="sm" onClick={addLink}>Add link</Button>
            </div>
          )}

          {mode === 'video' && (
            <div className="flex flex-col gap-2">
              <div className="flex gap-2 flex-wrap">
                <input
                  placeholder="YouTube, Vimeo, Google Drive or .mp4 link"
                  value={videoUrl}
                  onChange={e => setVideoUrl(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && addVideoLink()}
                  className="flex-1 min-w-48 px-3 py-2 text-sm rounded-lg border outline-none"
                  style={inputStyle}
                />
                <Button variant="secondary" size="sm" onClick={addVideoLink}>Add video link</Button>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <input ref={videoInput} type="file" accept="video/*" hidden onChange={e => onVideoFile(e.target.files)} />
                <Button variant="ghost" size="sm" onClick={() => videoInput.current?.click()}>Or upload a video file</Button>
                <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  Uploaded files only last for this session. Use a link to keep it permanently.
                </span>
              </div>
            </div>
          )}

          {staged.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {staged.map(a => (
                <div key={a.id} className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-full text-xs" style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}>
                  {a.kind === 'image'
                    ? <img src={a.url} alt="" className="w-6 h-6 rounded-full object-cover" />
                    : <span className="pl-1">{a.kind === 'video' ? '🎬' : '🔗'}</span>}
                  <span className="max-w-40 truncate">{a.name || hostOf(a.url)}</span>
                  <button onClick={() => setStaged(s => s.filter(x => x.id !== a.id))} aria-label="Remove attachment">✕</button>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between gap-3">
            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              {staged.length === 0 ? 'Add at least one image, link or video.' : `${staged.length} attachment${staged.length > 1 ? 's' : ''} ready`}
            </span>
            <Button onClick={submit} disabled={!canSubmit}>Submit proof of work</Button>
          </div>
        </Card>
      )}

      <div className="flex items-center gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--muted-foreground)' }}>Submitted proof</p>
        <Badge>{entries.length}</Badge>
      </div>

      {entries.length === 0 ? (
        <p className="text-sm py-6 text-center" style={{ color: 'var(--muted-foreground)' }}>
          {editable ? 'Nothing here yet. Add screenshots, a repo link or a demo video above.' : 'No proof of work has been shared for this project yet.'}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {entries.map(e => <EntryCard key={e.id} entry={e} editable={editable} onZoom={setZoom} />)}
        </div>
      )}

      {zoom && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 cursor-zoom-out" style={{ background: 'rgba(0,0,0,0.85)' }} onClick={() => setZoom(null)}>
          <img src={zoom} alt="Proof of work" className="max-w-full max-h-full rounded-lg" />
        </div>
      )}
    </div>
  );
}
