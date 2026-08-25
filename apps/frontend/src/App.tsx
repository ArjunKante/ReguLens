import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import { DashboardPage } from "./pages/DashboardPage";
import { InspectionDetailPage } from "./pages/InspectionDetailPage";
import { InspectionHistoryPage } from "./pages/InspectionHistoryPage";
import { LoginPage } from "./pages/LoginPage";
import { NewInspectionPage } from "./pages/NewInspectionPage";
import { RuleManagementPage } from "./pages/RuleManagementPage";
import { UserManagementPage } from "./pages/UserManagementPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        <Route path="/inspections" element={<ProtectedRoute><InspectionHistoryPage /></ProtectedRoute>} />
        <Route
          path="/inspections/new"
          element={
            <ProtectedRoute allow={["ADMIN", "INSPECTOR"]}>
              <NewInspectionPage />
            </ProtectedRoute>
          }
        />
        <Route path="/inspections/:id" element={<ProtectedRoute><InspectionDetailPage /></ProtectedRoute>} />
        <Route path="/rules" element={<ProtectedRoute><RuleManagementPage /></ProtectedRoute>} />
        <Route
          path="/users"
          element={
            <ProtectedRoute allow={["ADMIN"]}>
              <UserManagementPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  );
}
