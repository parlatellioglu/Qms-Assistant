/* QMS Assistant — runtime config for the live app.
   Registers window.QMS_CONFIG. Documents are NOT defined here; they come from the
   backend /chat response. Conversation history is NOT here either — it is persisted
   by the backend (local SQLite) and reached through window.QMS_History in
   history.js; "New question" starts a fresh thread rather than clearing storage. */
(function () {
  // Example questions for the empty state — drawn from the indexed CMMI corpus,
  // so each returns a real grounded answer. Written in English: the assistant
  // answers in the language of the question, so an English starter question gets
  // an English answer citing the Turkish source documents.
  const SUGGESTIONS = [
    'Which test strategies will be used for the MSS project?',
    'What are the SAT acceptance criteria?',
    'Can production data be used unmasked in the UAT environment?',
    'What lessons were captured at project close-out?',
  ];

  const KB_LABEL = 'Knowledge base · CMMI';

  // Role-based views (soft personalization): the selected role only tailors which
  // starter questions the empty state shows — every role still searches all docs.
  // Suggestions are drawn from the department question set (docs/DEPARTMENT-QUESTIONS.md,
  // which keeps the Turkish originals). 'genel' is the neutral default.
  //
  // `id` is persisted in localStorage and keys into ROLE_MATCH below — do not
  // translate it. Only `label` and `suggestions` are shown to the user.
  const ROLES = [
    { id: 'genel', label: 'General', suggestions: SUGGESTIONS },
    { id: 'ik', label: 'Human Resources', suggestions: [
      'How should I explain the SDLC process to a new team member?',
      'What are the roles and responsibilities in the process?',
      'How does a document approval flow work?',
      'Which document types are produced in a project, and what is each one for?',
    ] },
    { id: 'kalite_guvence', label: 'Quality Assurance', suggestions: [
      'How does the review process work?',
      'What do the defect severity levels (Severity 1-4) mean?',
      'Under what condition is a deliverable considered baselined?',
      'When is a peer review used, and when an MPR review?',
    ] },
    { id: 'kalite_muh', label: 'Quality Engineering', suggestions: [
      'What does a revision history table record in a document?',
      'Which roles appear in the signature block?',
      'Which documents does the bi-directional traceability matrix link?',
      'Can the design (DSAD) phase begin before the SRS is approved?',
    ] },
    { id: 'muhendislik', label: 'Software Engineering', suggestions: [
      'Which sections must an SRS contain?',
      'What is the TRF for, and at which phase is it prepared?',
      'What is the difference between functional and non-functional requirements?',
      'Which design and architecture decisions does the DSAD document?',
    ] },
    { id: 'proje', label: 'Project Management', suggestions: [
      'Which sections must the Project Management Plan (PMP) include?',
      'How do the SDLC phases map to the MPR gates (G1-G6)?',
      'Which approvals are required for a process deviation?',
      'What information must a close-out report contain?',
    ] },
    { id: 'test', label: 'Test & Validation', suggestions: [
      'Which sections make up a SAT (System Acceptance Test) plan?',
      'What do SAT and UAT cases verify, and how do they differ?',
      'Which fields must a test case contain?',
      'How are acceptance criteria defined?',
    ] },
    { id: 'yonetim', label: 'Executive', suggestions: [
      'What does a project close-out report summarise?',
      'Which criteria must be met for a project to count as complete?',
      'Which decisions do the MPR gates (G1-G6) represent?',
      'Where are lessons learned recorded?',
    ] },
  ];

  // Role vocabulary: the labels the *documents* use for each UI role. Lets the
  // "Yeni Proje" view highlight the phase items that mention the selected role
  // (a lens on the process map — nothing is hidden, only emphasised).
  const ROLE_MATCH = {
    proje: ['Proje Yöneticisi', 'Project Manager', 'PM', 'PM/TL', 'PM and TL', 'IT Program Manager'],
    muhendislik: ['Yazılım Mimarı', 'Mimar', 'Geliştirici', 'Developer', 'Team Lead',
                  'Technical Lead', 'TL', 'Sistem Mühendisi', 'DBA', 'İş Analisti'],
    test: ['Test Uzmanı', 'Test Lideri', 'Test Mühendisi', 'Tester'],
    kalite_guvence: ['Kalite Güvence', 'QA', 'PQA', 'PQC', 'reviewer', 'Author and reviewers'],
    kalite_muh: ['Kalite Mühendisi', 'configuration manager'],
    yonetim: ['BT Direktörü', 'Direktör', 'Sponsor', 'PMO', 'ISG', 'Genel Müdür', 'Budget Controller'],
    ik: ['İnsan Kaynakları', 'İK', 'HR'],
  };

  const API_BASE = (window.location.port === '8080' || window.location.port === '5173')
    ? 'http://127.0.0.1:8013' : '';

  // Placeholder identity shown in the sidebar footer and on your own messages.
  // There is no login: the ROLE selector is what actually changes behaviour, so
  // the name is deliberately a stand-in. Defined here rather than in a view so the
  // two places that display it cannot drift apart.
  const CURRENT_USER = 'Demo User';

  window.QMS_CONFIG = { SUGGESTIONS, KB_LABEL, ROLES, ROLE_MATCH, API_BASE, CURRENT_USER };
})();
