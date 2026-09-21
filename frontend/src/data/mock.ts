export type Role = 'student' | 'faculty' | 'industry' | 'admin';

export const MOCK_USERS = {
  student: { name: 'Arjun Mehta', role: 'student' as Role, institutionType: 'College', institution: 'IIT Bombay', virtualId: 'STU-2024-0042', avatar: 'AM' },
  faculty: { name: 'Dr. Priya Sharma', role: 'faculty' as Role, institutionType: 'University', institution: 'Delhi Technological University', virtualId: 'FAC-2024-0011', avatar: 'PS' },
  industry: { name: 'Rohan Kapoor', role: 'industry' as Role, company: 'Infosys', designation: 'Director of Innovation', virtualId: 'IND-2024-0007', avatar: 'RK' },
  admin: { name: 'System Admin', role: 'admin' as Role, avatar: 'SA' },
};

export const MOCK_PROBLEMS = [
  { id: 'p1', title: 'AI-Powered Supply Chain Optimization', company: 'Infosys', logo: 'IN', tags: ['AI/ML', 'Supply Chain', 'B2B'], domain: 'Technology', applicants: 14, postedDays: 3 },
  { id: 'p2', title: 'Rural Healthcare Diagnostic Tool', company: 'Apollo Hospitals', logo: 'AP', tags: ['HealthTech', 'IoT', 'Social Impact'], domain: 'Healthcare', applicants: 22, postedDays: 5 },
  { id: 'p3', title: 'Sustainable Packaging Tracker', company: 'Marico', logo: 'MA', tags: ['Sustainability', 'FMCG', 'ESG'], domain: 'Environment', applicants: 9, postedDays: 7 },
  { id: 'p4', title: 'EdTech Personalization Engine', company: 'BYJU\'S', logo: 'BY', tags: ['EdTech', 'ML', 'UX'], domain: 'Education', applicants: 31, postedDays: 2 },
  { id: 'p5', title: 'Smart Waste Segregation System', company: 'Tata Motors', logo: 'TM', tags: ['Hardware', 'IoT', 'Smart City'], domain: 'Environment', applicants: 17, postedDays: 10 },
  { id: 'p6', title: 'Financial Inclusion App for Rural India', company: 'HDFC Bank', logo: 'HD', tags: ['FinTech', 'Mobile', 'Social Impact'], domain: 'Finance', applicants: 28, postedDays: 4 },
];

export const MOCK_PROJECTS = [
  {
    id: 'proj1',
    title: 'MediAssist AI — Rural Diagnostics',
    stage: 'Building',
    lastUpdated: '2h ago',
    proofOfWork: 7,
    mentorStatus: 'accepted',
    mentorName: 'Dr. Priya Sharma',
    teamSize: 4,
    category: 'HealthTech',
    institution: 'IIT Bombay',
    description: 'An AI-powered diagnostic assistant for rural health workers with offline-first architecture.',
    activityLog: [
      { date: 'Sep 14', text: 'New proof-of-work added — model accuracy report' },
      { date: 'Sep 12', text: 'Milestone 3 marked complete' },
      { date: 'Sep 10', text: 'New proof-of-work added — prototype demo video' },
    ],
    team: [
      { name: 'Arjun Mehta', institution: 'IIT Bombay', type: 'College', role: 'Lead', avatar: 'AM', linkedin: 'linkedin.com/in/arjun-mehta' },
      { name: 'Sneha Patel', institution: 'BITS Pilani', type: 'College', role: 'Contributor', avatar: 'SP', linkedin: 'linkedin.com/in/sneha-patel' },
      { name: 'Karan Nair', institution: 'Delhi Public School', type: 'School', role: 'Contributor', avatar: 'KN', linkedin: 'linkedin.com/in/karan-nair' },
      { name: 'Ria Das', institution: 'IIT Bombay', type: 'College', role: 'Contributor', avatar: 'RD', linkedin: 'linkedin.com/in/ria-das' },
    ],
  },
  {
    id: 'proj2',
    title: 'GreenRoute — Carbon Footprint Navigator',
    stage: 'Ideation',
    lastUpdated: '1d ago',
    proofOfWork: 2,
    mentorStatus: 'pending',
    mentorName: null,
    teamSize: 2,
    category: 'ClimaTech',
    institution: 'IIT Bombay',
    description: 'Route optimization app that minimizes carbon emissions for urban logistics.',
    activityLog: [
      { date: 'Sep 13', text: 'New proof-of-work added — initial wireframes' },
    ],
    team: [
      { name: 'Arjun Mehta', institution: 'IIT Bombay', type: 'College', role: 'Lead', avatar: 'AM', linkedin: 'linkedin.com/in/arjun-mehta' },
      { name: 'Dev Rathi', institution: 'NIT Surat', type: 'College', role: 'Contributor', avatar: 'DR', linkedin: 'linkedin.com/in/dev-rathi' },
    ],
  },
];

export const MOCK_STUDENTS_FACULTY = [
  { id: 's1', name: 'Arjun Mehta', email: 'arjun@iitb.ac.in', virtualId: 'STU-2024-0042', status: 'Active', projects: 2, joinDate: 'Aug 2024', avatar: 'AM', linkedin: 'linkedin.com/in/arjun-mehta' },
  { id: 's2', name: 'Sneha Patel', email: 'sneha@bits.ac.in', virtualId: 'STU-2024-0051', status: 'Active', projects: 1, joinDate: 'Aug 2024', avatar: 'SP', linkedin: 'linkedin.com/in/sneha-patel' },
  { id: 's3', name: 'Mihir Joshi', email: 'mihir@dtu.ac.in', virtualId: 'STU-2024-0063', status: 'Invited', projects: 0, joinDate: 'Sep 2024', avatar: 'MJ', linkedin: '' },
  { id: 's4', name: 'Tanvi Shah', email: 'tanvi@iitb.ac.in', virtualId: 'STU-2024-0071', status: 'Active', projects: 3, joinDate: 'Jul 2024', avatar: 'TS', linkedin: 'linkedin.com/in/tanvi-shah' },
  { id: 's5', name: 'Rohan Verma', email: 'rohan@iitb.ac.in', virtualId: 'STU-2024-0088', status: 'Invited', projects: 0, joinDate: 'Sep 2024', avatar: 'RV', linkedin: '' },
];

export const MOCK_CHANGE_REQUESTS = [
  { id: 'cr1', studentName: 'Priya Menon', virtualId: 'STU-2023-0099', currentInstitution: 'NIT Trichy', requestDate: 'Sep 13, 2024', linkedIn: 'linkedin.com/in/priya-menon', avatar: 'PM' },
  { id: 'cr2', studentName: 'Aarav Singh', virtualId: 'STU-2024-0022', currentInstitution: 'Manipal University', requestDate: 'Sep 10, 2024', linkedIn: 'linkedin.com/in/aarav-singh', avatar: 'AS' },
];

export const MOCK_FACULTY_PROJECTS = [
  { id: 'fp1', title: 'MediAssist AI', team: 'Team Nova', stage: 'Building', lastActivity: '2h ago', milestones: 5, completed: 3 },
  { id: 'fp2', title: 'GreenRoute Navigator', team: 'Team Echo', stage: 'Proposal', lastActivity: '1d ago', milestones: 5, completed: 1 },
  { id: 'fp3', title: 'EdConnect Bridge', team: 'Team Apex', stage: 'Funded', lastActivity: '3d ago', milestones: 8, completed: 8 },
  { id: 'fp4', title: 'WasteWise IoT', team: 'Team Vortex', stage: 'Prototype', lastActivity: '5d ago', milestones: 6, completed: 5 },
];

export const MOCK_FACULTY_CHARTS = {
  projectsOverTime: [
    { month: 'Jan', count: 2 }, { month: 'Feb', count: 3 }, { month: 'Mar', count: 3 },
    { month: 'Apr', count: 5 }, { month: 'May', count: 4 }, { month: 'Jun', count: 6 },
    { month: 'Jul', count: 7 }, { month: 'Aug', count: 8 }, { month: 'Sep', count: 9 },
  ],
  projectsByStage: [
    { name: 'Ideation', value: 3, color: '#71717a' },
    { name: 'Building', value: 5, color: '#7c3aed' },
    { name: 'Funded', value: 2, color: '#059669' },
    { name: 'Deployed', value: 1, color: '#0ea5e9' },
  ],
};

export const MOCK_INDUSTRY_PROJECTS = [
  { id: 'ip1', title: 'MediAssist AI', team: 'Team Nova', institution: 'IIT Bombay', stage: 'Building', progress: 65, lastActivity: '2h ago', members: 4 },
  { id: 'ip2', title: 'SupplySync AI', team: 'Team Orbit', institution: 'BITS Pilani', stage: 'Prototype', progress: 88, lastActivity: '1d ago', members: 3 },
  { id: 'ip3', title: 'AgriSense Platform', team: 'Team Delta', institution: 'IIT Delhi', stage: 'Ideation', progress: 22, lastActivity: '3d ago', members: 5 },
];

export const MOCK_ADMIN_USERS = [
  { id: 'u1', name: 'Dr. Priya Sharma', role: 'Faculty', institution: 'DTU', status: 'Active', registeredVia: 'Self-registered', joinDate: 'Aug 2024', avatar: 'PS' },
  { id: 'u2', name: 'Arjun Mehta', role: 'Student', institution: 'IIT Bombay', status: 'Active', registeredVia: 'Faculty-provisioned', joinDate: 'Aug 2024', avatar: 'AM' },
  { id: 'u3', name: 'Rohan Kapoor', role: 'Industry', institution: 'Infosys', status: 'Active', registeredVia: 'Self-registered', joinDate: 'Sep 2024', avatar: 'RK' },
  { id: 'u4', name: 'Mihir Joshi', role: 'Student', institution: 'DTU', status: 'Invited', registeredVia: 'Faculty-provisioned', joinDate: 'Sep 2024', avatar: 'MJ' },
  { id: 'u5', name: 'Dr. Anita Roy', role: 'Faculty', institution: 'IIM Ahmedabad', status: 'Suspended', registeredVia: 'Self-registered', joinDate: 'Jul 2024', avatar: 'AR' },
];

export const MOCK_LEADERBOARD = {
  schools: [
    { rank: 1, name: 'Delhi Public School, R.K. Puram', logo: 'DP', projects: 18, students: 42, score: 9820 },
    { rank: 2, name: 'The Doon School', logo: 'DS', projects: 14, students: 31, score: 8450 },
    { rank: 3, name: 'Kendriya Vidyalaya IIT Campus', logo: 'KV', projects: 11, students: 28, score: 7200 },
    { rank: 4, name: 'St. Xavier\'s School, Mumbai', logo: 'SX', projects: 9, students: 22, score: 6100 },
    { rank: 5, name: 'Delhi Public School, Noida', logo: 'DN', projects: 8, students: 19, score: 5400 },
  ],
  colleges: [
    { rank: 1, name: 'IIT Bombay', logo: 'IB', projects: 67, students: 142, score: 38400 },
    { rank: 2, name: 'BITS Pilani', logo: 'BP', projects: 54, students: 118, score: 31200 },
    { rank: 3, name: 'Delhi Technological University', logo: 'DT', projects: 48, students: 103, score: 27800 },
    { rank: 4, name: 'NIT Trichy', logo: 'NT', projects: 41, students: 89, score: 24100 },
    { rank: 5, name: 'IIT Delhi', logo: 'ID', projects: 38, students: 82, score: 22600 },
    { rank: 6, name: 'VIT Vellore', logo: 'VV', projects: 35, students: 76, score: 20900 },
    { rank: 7, name: 'Manipal Institute of Technology', logo: 'MI', projects: 29, students: 64, score: 17300 },
  ],
};

export const STAGES = ['Idea', 'Problem', 'Team', 'Proposal', 'Build', 'Milestones', 'Feedback', 'Industry', 'Funding', 'Prototype', 'Deployment'];

export const MOCK_MILESTONES = [
  { id: 'm1', title: 'Submit Project Proposal', done: true, dueDate: 'Aug 20' },
  { id: 'm2', title: 'Initial Prototype (MVP)', done: true, dueDate: 'Sep 1' },
  { id: 'm3', title: 'User Research & Validation', done: true, dueDate: 'Sep 10' },
  { id: 'm4', title: 'Integrate AI Model v1', done: false, dueDate: 'Sep 25' },
  { id: 'm5', title: 'Pilot Deployment — 3 Clinics', done: false, dueDate: 'Oct 10' },
  { id: 'm6', title: 'Full Demo to Industry Sponsor', done: false, dueDate: 'Oct 30' },
];

export const MOCK_MENTORS = [
  { id: 'men1', name: 'Dr. Priya Sharma', institution: 'DTU', domain: 'AI/ML, HealthTech', avatar: 'PS', projects: 9, linkedin: 'linkedin.com/in/dr-priya-sharma' },
  { id: 'men2', name: 'Prof. Rahul Bose', institution: 'IIT Kharagpur', domain: 'IoT, Hardware', avatar: 'RB', projects: 6, linkedin: 'linkedin.com/in/prof-rahul-bose' },
  { id: 'men3', name: 'Dr. Anita Roy', institution: 'IIM Ahmedabad', domain: 'FinTech, Strategy', avatar: 'AR', projects: 12, linkedin: 'linkedin.com/in/dr-anita-roy' },
  { id: 'men4', name: 'Prof. Suresh Kumar', institution: 'BITS Hyderabad', domain: 'SaaS, Cloud', avatar: 'SK', projects: 7, linkedin: 'linkedin.com/in/prof-suresh-kumar' },
];

export const ADMIN_ANALYTICS = {
  activeUsers: 1247,
  projectsByStage: [
    { stage: 'Ideation', count: 142 }, { stage: 'Building', count: 89 },
    { stage: 'Funded', count: 31 }, { stage: 'Deployed', count: 18 },
  ],
  crossInstitutionPct: 68,
  fundingDisbursed: '₹42.6L',
  growth: [
    { month: 'Apr', users: 340 }, { month: 'May', users: 520 }, { month: 'Jun', users: 690 },
    { month: 'Jul', users: 820 }, { month: 'Aug', users: 1050 }, { month: 'Sep', users: 1247 },
  ],
};
