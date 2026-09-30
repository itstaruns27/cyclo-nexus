import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { DataProvider } from './context/DataContext';
import SiteLayout from './components/site/SiteLayout';
import HomePage from './pages/HomePage';
import ExpertPage from './pages/ExpertPage';
import HistoricalPage from './pages/HistoricalPage';
import AlertsPage from './pages/AlertsPage';
import './index.css';
import './styles/site.css';

export default function App() {
  return (
    <DataProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<SiteLayout />}>
            <Route index element={<HomePage />} />
            <Route path="alerts" element={<div className="site-container page-pad"><AlertsPage /></div>} />
            <Route path="history" element={<div className="site-container page-pad"><HistoricalPage /></div>} />
            <Route path="expert" element={<ExpertPage />} />
            {/* Old URLs from the dashboard layout */}
            <Route path="historical" element={<Navigate to="/history" replace />} />
            <Route path="forecast" element={<Navigate to="/expert#forecast" replace />} />
            <Route path="status" element={<Navigate to="/expert#health" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DataProvider>
  );
}
