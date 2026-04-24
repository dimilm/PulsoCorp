import { Route, Routes } from "react-router-dom";

import { Protected } from "./components/Protected";
import { Spinner } from "./components/Spinner";
import { useAuth } from "./hooks/useAuth";
import { AppLayout } from "./layouts/AppLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { RunsPage } from "./pages/RunsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StockDetailPage } from "./pages/StockDetailPage";
import { StockEditPage } from "./pages/StockEditPage";
import { WatchlistPage } from "./pages/WatchlistPage";

export default function App() {
  const { user, setUser, loading } = useAuth();

  if (loading) {
    return (
      <div className="page">
        <Spinner label="Lade..." />
      </div>
    );
  }

  return (
    <AppLayout user={user} onLoggedOut={() => setUser(null)}>
      <Routes>
        <Route path="/login" element={<LoginPage onLogin={setUser} />} />
        <Route
          path="/"
          element={
            <Protected user={user}>
              <DashboardPage />
            </Protected>
          }
        />
        <Route
          path="/watchlist"
          element={
            <Protected user={user}>
              <WatchlistPage />
            </Protected>
          }
        />
        <Route
          path="/stocks/:isin"
          element={
            <Protected user={user}>
              <StockDetailPage />
            </Protected>
          }
        />
        <Route
          path="/stocks/:isin/edit"
          element={
            <Protected user={user}>
              <StockEditPage />
            </Protected>
          }
        />
        <Route
          path="/runs"
          element={
            <Protected user={user}>
              <RunsPage />
            </Protected>
          }
        />
        <Route
          path="/settings"
          element={
            <Protected user={user}>
              <SettingsPage />
            </Protected>
          }
        />
      </Routes>
    </AppLayout>
  );
}
