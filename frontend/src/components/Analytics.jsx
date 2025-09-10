// frontend/src/components/Analytics.jsx
import React from 'react';
import BottomNavigation from './BottomNavigation';

const AnalyticsPage = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white pb-20">
      <div className="p-6">
        <h1 className="text-3xl font-bold mb-4">📈 Stats</h1>
        <p className="text-gray-400">Performance analytics coming soon...</p>
      </div>
      <BottomNavigation />
    </div>
  );
};

export default AnalyticsPage;