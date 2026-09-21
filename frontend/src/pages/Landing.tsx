import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui';
import logo from '../assets/logo.png';

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--background)' }}>
      {/* Nav */}
      <header className="flex items-center justify-between px-8 h-14 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <div
            className="flex items-center justify-center w-7 h-7 rounded-lg font-bold text-xs"
           style={{ backgroundImage: `url(${logo})`,backgroundSize:'cover',backgroundPosition:'center',backgroundRepeat:'no-repeat'  }}
          >
           
          </div>
          <span className="font-semibold text-sm" style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}>InnovateX</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/auth/register/faculty')}
            className="text-sm"
            style={{ color: 'var(--muted-foreground)' }}
          >
            Register
          </button>
          <Button onClick={() => navigate('/auth/login')} size="sm">Sign In</Button>
        </div>
      </header>

      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <div className="max-w-2xl">
          <div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl font-bold text-2xl mb-8"
            style={{ backgroundImage: `url(${logo})`,backgroundSize:'cover',backgroundPosition:'center',backgroundRepeat:'no-repeat'  }}
          >
           
          </div>
          <h1
            className="text-6xl font-bold mb-4 leading-tight"
            style={{ fontFamily: 'DM Sans', color: 'var(--foreground)' }}
          >
            Build real projects.<br />
            <span style={{ color: 'var(--accent)' }}>Ship real impact.</span>
          </h1>
          <p className="text-lg mb-8 max-w-xl mx-auto" style={{ color: 'var(--muted-foreground)', lineHeight: 1.6 }}>
            InnovateX connects school and college students with mentors and industry partners
            to build, validate, and fund real-world projects.
          </p>
          <div className="flex items-center justify-center gap-3 flex-wrap">
            <Button onClick={() => navigate('/auth/login')} size="lg">
              Sign In → Dashboard
            </Button>
            <Button onClick={() => navigate('/auth/register/faculty')} variant="secondary" size="lg">
              Register as Faculty
            </Button>
            <Button onClick={() => navigate('/auth/register/industry')} variant="secondary" size="lg">
              Register as Industry
            </Button>
          </div>
        </div>
      </div>

      {/* Demo shortcuts — clearly labeled */}
      <div className="border-t px-6 py-5" style={{ borderColor: 'var(--border)' }}>
        <div className="max-w-3xl mx-auto">
          <p className="text-xs uppercase tracking-widest font-semibold text-center mb-4" style={{ color: 'var(--muted-foreground)' }}>
            Demo — Jump to a role dashboard
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { label: 'Student', path: '/student', id: 'STU-2024-0042', color: '#7c3aed' },
              { label: 'Faculty', path: '/faculty', id: 'FAC-2024-0011', color: '#0ea5e9' },
              { label: 'Industry', path: '/industry', id: 'IND-2024-0007', color: '#059669' },
              { label: 'Admin', path: '/admin', id: 'ADM-0001', color: '#f97316' },
            ].map(r => (
              <button
                key={r.id}
                onClick={() => navigate(r.path)}
                className="px-3 py-2 rounded-lg border text-xs font-medium"
                style={{ borderColor: 'var(--border)', color: 'var(--muted-foreground)' }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.borderColor = r.color;
                  (e.currentTarget as HTMLElement).style.color = r.color;
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)';
                  (e.currentTarget as HTMLElement).style.color = 'var(--muted-foreground)';
                }}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
