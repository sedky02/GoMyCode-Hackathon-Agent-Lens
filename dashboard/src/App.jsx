import { Routes, Route, Link } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Overview from './pages/Overview.jsx'
import Issues from './pages/Issues.jsx'
import IssueDetail from './pages/IssueDetail.jsx'
import Sessions from './pages/Sessions.jsx'
import SessionDetail from './pages/SessionDetail.jsx'
import { EmptyState, buttonCls } from './components/ui.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/issues" element={<Issues />} />
        <Route path="/issues/:id" element={<IssueDetail />} />
        <Route path="/sessions" element={<Sessions />} />
        <Route path="/sessions/:id" element={<SessionDetail />} />
        <Route
          path="*"
          element={
            <EmptyState
              title="Page not found"
              hint="This page doesn’t exist."
              action={
                <Link to="/" className={buttonCls('secondary')}>
                  Go to Overview
                </Link>
              }
            />
          }
        />
      </Route>
    </Routes>
  )
}
