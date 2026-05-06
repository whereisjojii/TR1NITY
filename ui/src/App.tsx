import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { CasesPage } from "./pages/CasesPage";
import { HeatmapPage } from "./pages/HeatmapPage";
import { HelpPage } from "./pages/HelpPage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { QueuePage } from "./pages/QueuePage";

export default function App(): JSX.Element {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/queue" replace />} />
        <Route path="/queue" element={<QueuePage />} />
        <Route path="/incidents/:id" element={<IncidentDetailPage />} />
        <Route path="/heatmap" element={<HeatmapPage />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="*" element={<Navigate to="/queue" replace />} />
      </Routes>
    </Layout>
  );
}
