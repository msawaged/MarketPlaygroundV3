import React from "react";
import { Outlet } from "react-router-dom";
import BottomNavigation from "./BottomNavigation";

export default function LayoutWithNav() {
  return (
    <div className="min-h-screen relative bg-black text-white">
      {/* Page content */}
      <div className="pb-24"> {/* padding so content isn't hidden behind nav */}
        <Outlet />
      </div>

      {/* Persistent bottom nav */}
      <div className="fixed inset-x-0 bottom-0 z-50">
        <BottomNavigation />
        {/* iOS safe-area */}
        <div className="h-2" style={{ paddingBottom: "env(safe-area-inset-bottom)" }} />
      </div>
    </div>
  );
}
