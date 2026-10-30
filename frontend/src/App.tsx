import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import { EmptyState, LoadingBlock } from "./design-system";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Experiments = lazy(() => import("./pages/Experiments"));
const ExperimentDetail = lazy(() => import("./pages/ExperimentDetail"));
const VideoAnalysis = lazy(() => import("./pages/VideoAnalysis"));
const FlameAnalytics = lazy(() => import("./pages/FlameAnalytics"));
const Prediction = lazy(() => import("./pages/Prediction"));
const Models = lazy(() => import("./pages/Models"));
const Datasets = lazy(() => import("./pages/Datasets"));
const Comparison = lazy(() => import("./pages/Comparison"));
const Reports = lazy(() => import("./pages/Reports"));
const SystemPage = lazy(() => import("./pages/System"));
const Settings = lazy(() => import("./pages/Settings"));
const Present = lazy(() => import("./pages/Present"));

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        {([
          ["/dashboard", <Dashboard />], ["/experiments", <Experiments />], ["/experiments/:id", <ExperimentDetail />],
          ["/video-analysis", <VideoAnalysis />], ["/analytics/flame", <FlameAnalytics />], ["/prediction", <Prediction />],
          ["/models", <Models />], ["/datasets", <Datasets />], ["/comparison", <Comparison />], ["/reports", <Reports />],
          ["/system", <SystemPage />], ["/settings", <Settings />], ["/present", <Present />],
        ] as const).map(([path, el]) => <Route key={path} path={path} element={<Suspense fallback={<LoadingBlock rows={4} label="Loading page" />}>{el}</Suspense>} />)}
        <Route path="*" element={<EmptyState eyebrow="404" title="This page does not exist." body="Use the navigation above." />} />
      </Route>
    </Routes>
  );
}
