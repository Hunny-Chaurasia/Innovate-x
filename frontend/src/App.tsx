import IndustryReview from './pages/industry/Review';
import { AuthShell, MentorHome } from './integration/auth';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ToastProvider } from './components/Toast';

// Auth
import Landing from './pages/Landing';
import Login from './pages/auth/Login';
import FacultyRegister from './pages/auth/FacultyRegister';
import StudentRegister from './pages/auth/StudentRegister';
import IndustryRegister from './pages/auth/IndustryRegister';

// Student
import StudentDashboard from './pages/student/StudentDashboard';
import Discover from './pages/student/Discover';
import MyProjects from './pages/student/MyProjects';
import Portfolio from './pages/student/Portfolio';
import Funding from './pages/student/Funding';
import StudentSettings from './pages/student/StudentSettings';

// Faculty
import FacultyDashboard from './pages/faculty/FacultyDashboard';
import Students from './pages/faculty/Students';
import ChangeRequests from './pages/faculty/ChangeRequests';
import ReviewPanel from './pages/faculty/ReviewPanel';

// Industry
import IndustryDashboard from './pages/industry/IndustryDashboard';
import PostProblem from './pages/industry/PostProblem';
import DiscoverProjects from './pages/industry/DiscoverProjects';
import CSRImpact from './pages/industry/CSRImpact';

// Admin
import AdminDashboard from './pages/admin/AdminDashboard';
import UserManagement from './pages/admin/UserManagement';
import FundingVerification from './pages/admin/FundingVerification';

// Shared
import Leaderboard from './pages/Leaderboard';
import NewProject from './pages/student/NewProject';
import Review from './pages/student/Review';
import StudentActions from './pages/student/StudentActions';
import ProblemStatements from './pages/faculty/ProblemStatements';
import PublicPortfolio from './pages/public/PublicPortfolio';

function StudentShell({ children }: { children: React.ReactNode }) {
  return <AuthShell role="student">{children}</AuthShell>;
}
function FacultyShell({ children }: { children: React.ReactNode }) {
  return <AuthShell role="faculty">{children}</AuthShell>;
}
function IndustryShell({ children }: { children: React.ReactNode }) {
  return <AuthShell role="industry">{children}</AuthShell>;
}
function AdminShell({ children }: { children: React.ReactNode }) {
  return <AuthShell role="admin">{children}</AuthShell>;
}

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/industry/reviews" element={<IndustryShell><IndustryReview /></IndustryShell>} />
          <Route path="/mentor" element={<MentorHome />} />
          {/* Public */}
          <Route path="/" element={<Landing />} />
          <Route path="/auth/login" element={<Login />} />
          <Route path="/auth/register/faculty" element={<FacultyRegister />} />
          <Route path="/auth/register/student" element={<StudentRegister />} />
          <Route path="/auth/register/industry" element={<IndustryRegister />} />

          {/* Student */}
          <Route path="/student" element={<StudentShell><StudentDashboard /></StudentShell>} />
          <Route path="/student/discover" element={<StudentShell><Discover /></StudentShell>} />
          <Route path="/student/projects" element={<StudentShell><MyProjects /></StudentShell>} />
          <Route path="/student/portfolio" element={<StudentShell><Portfolio /></StudentShell>} />
          <Route path="/student/funding" element={<StudentShell><Funding /></StudentShell>} />
          <Route path="/student/settings" element={<StudentShell><StudentSettings /></StudentShell>} />

          {/* Faculty */}
          <Route path="/faculty" element={<FacultyShell><FacultyDashboard /></FacultyShell>} />
          <Route path="/faculty/students" element={<FacultyShell><Students /></FacultyShell>} />
          <Route path="/faculty/change-requests" element={<FacultyShell><ChangeRequests /></FacultyShell>} />
          <Route path="/faculty/review" element={<FacultyShell><ReviewPanel /></FacultyShell>} />
          <Route path="/faculty/teams" element={<FacultyShell><FacultyDashboard /></FacultyShell>} />

          {/* Industry */}
          <Route path="/industry" element={<IndustryShell><IndustryDashboard /></IndustryShell>} />
          <Route path="/industry/post" element={<IndustryShell><PostProblem /></IndustryShell>} />
          <Route path="/industry/discover" element={<IndustryShell><DiscoverProjects /></IndustryShell>} />
          <Route path="/industry/csr" element={<IndustryShell><CSRImpact /></IndustryShell>} />

          {/* Admin */}
          <Route path="/admin" element={<AdminShell><AdminDashboard /></AdminShell>} />
          <Route path="/admin/users" element={<AdminShell><UserManagement /></AdminShell>} />
          <Route path="/admin/moderation" element={<AdminShell><AdminDashboard /></AdminShell>} />
          <Route path="/admin/analytics" element={<AdminShell><AdminDashboard /></AdminShell>} />
          <Route path="/admin/funding-verification" element={<AdminShell><FundingVerification /></AdminShell>} />

          {/* Leaderboard */}
          <Route path="/leaderboard" element={<StudentShell><Leaderboard /></StudentShell>} />
          {/* Student: new pages */}
          <Route path="/student/new-project" element={<StudentShell><NewProject /></StudentShell>} />
          <Route path="/student/reviews"     element={<StudentShell><Review /></StudentShell>} />
          <Route path="/student/actions"     element={<StudentShell><StudentActions /></StudentShell>} />

          {/* Faculty: problem statements portal */}
          <Route path="/faculty/problems"    element={<FacultyShell><ProblemStatements /></FacultyShell>} />

          {/* Public portfolio: no shell, no login guard, so the shared link opens for anyone */}
          <Route path="/u/:slug"             element={<PublicPortfolio />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
