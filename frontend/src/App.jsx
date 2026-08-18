import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import Page1Bundles from "./pages/Page1Bundles";
import Page2Transports from "./pages/Page2Transports";
import Page3Locations from "./pages/Page3Locations";
import Page4Teams from "./pages/Page4Teams";
import Page5Schedule from "./pages/Page5Schedule";
import DataAdmin from "./pages/DataAdmin";

const PAGES = [
  { path: "/page1", num: "1", label: "Packages needed" },
  { path: "/page2", num: "2", label: "Capable transports" },
  { path: "/page3", num: "3", label: "Feasible locations" },
  { path: "/page4", num: "4", label: "Tasking authority" },
  { path: "/page5", num: "5", label: "Daily schedule" },
];

export default function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          Delivery Feasibility
          <small>Assessment Tool</small>
        </div>

        <div>
          <div className="nav-group-label">Assessment</div>
          <nav className="nav-links">
            {PAGES.map((p) => (
              <NavLink key={p.path} to={p.path} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
                <span className="nav-num">{p.num}</span> {p.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div>
          <div className="nav-group-label">Configuration</div>
          <nav className="nav-links">
            <NavLink to="/data" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              <span className="nav-num">⚙</span> Data
            </NavLink>
          </nav>
        </div>
      </aside>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/page1" replace />} />
          <Route path="/page1" element={<Page1Bundles />} />
          <Route path="/page2" element={<Page2Transports />} />
          <Route path="/page3" element={<Page3Locations />} />
          <Route path="/page4" element={<Page4Teams />} />
          <Route path="/page5" element={<Page5Schedule />} />
          <Route path="/data" element={<DataAdmin />} />
        </Routes>
      </main>
    </div>
  );
}
