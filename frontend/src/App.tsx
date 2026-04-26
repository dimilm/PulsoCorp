import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

import { Protected } from "./components/Protected";
import { Spinner } from "./components/Spinner";
import { useAuth } from "./hooks/useAuth";
import { AppLayout } from "./layouts/AppLayout";
import { DialogHost } from "./lib/dialogs";
import { ToastHost } from "./lib/toast";

// Pages are split out via React.lazy so the initial bundle stays small. Recharts
// and the AI panel ship inside the StockDetailPage chunk (and only load when a
// user navigates to /stocks/:isin), which removes ~150 kB from the boot path.
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage }))
);
const LoginPage = lazy(() =>
  import("./pages/LoginPage").then((m) => ({ default: m.LoginPage }))
);
const RunsPage = lazy(() =>
  import("./pages/RunsPage").then((m) => ({ default: m.RunsPage }))
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage }))
);
const StockDetailPage = lazy(() =>
  import("./pages/StockDetailPage").then((m) => ({ default: m.StockDetailPage }))
);
const StockEditPage = lazy(() =>
  import("./pages/StockEditPage").then((m) => ({ default: m.StockEditPage }))
);
const WatchlistPage = lazy(() =>
  import("./pages/WatchlistPage").then((m) => ({ default: m.WatchlistPage }))
);

function PageFallback() {
  return (
    <div className="page">
      <Spinner label="Lade..." />
    </div>
  );
}

export default function App() {
  const { loading } = useAuth();

  if (loading) {
    return <PageFallback />;
  }

  return (
    <AppLayout>
      <DialogHost />
      <ToastHost />
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <Protected>
                <DashboardPage />
              </Protected>
            }
          />
          <Route
            path="/watchlist"
            element={
              <Protected>
                <WatchlistPage />
              </Protected>
            }
          />
          <Route
            path="/stocks/:isin"
            element={
              <Protected>
                <StockDetailPage />
              </Protected>
            }
          />
          <Route
            path="/stocks/:isin/edit"
            element={
              <Protected>
                <StockEditPage />
              </Protected>
            }
          />
          <Route
            path="/runs"
            element={
              <Protected>
                <RunsPage />
              </Protected>
            }
          />
          <Route
            path="/settings"
            element={
              <Protected>
                <SettingsPage />
              </Protected>
            }
          />
        </Routes>
      </Suspense>
    </AppLayout>
  );
}
