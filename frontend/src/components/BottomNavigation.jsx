/*
================================================================================
FILE PATH: frontend/src/components/BottomNavigation.jsx
================================================================================
DESCRIPTION: PERFECTED Mobile-first bottom navigation - sleek, modern, functional
AUTHOR: COWLabs - MarketPlayground Team  
PURPOSE: Professional mobile navigation that actually looks good and works
================================================================================
*/

import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Home, TrendingUp, BarChart3, User, Zap } from 'lucide-react';

/**
 * PROFESSIONAL MOBILE BOTTOM NAVIGATION
 * ====================================
 * - Sleek design that matches your app's aesthetic
 * - Proper mobile spacing and touch targets
 * - Smooth animations and visual feedback
 * - Dark theme integration
 */
const BottomNavigation = ({ onPortfolioClick }) => {
  const navigate = useNavigate();
  const location = useLocation();

  // NAVIGATION ITEMS - Streamlined for mobile
  const navItems = [
    {
      id: 'home',
      label: 'Home',
      icon: Home,
      path: '/select-tool',
      color: '#3b82f6'
    },
    {
      id: 'chat',
      label: 'AI Trade',
      icon: Zap,
      path: '/chat',
      color: '#8b5cf6'
    },
    {
      id: 'portfolio',
      label: 'Portfolio',
      icon: TrendingUp,
      path: '/paper-trading',
      color: '#22c55e'
    },
    {
      id: 'analytics',
      label: 'Stats',
      icon: BarChart3,
      path: '/analytics',
      color: '#f59e0b'
    },
    {
      id: 'profile',
      label: 'Profile',
      icon: User,
      path: '/profile',
      color: '#ef4444'
    }
  ];

  return (
    // MAIN CONTAINER - Sleek and minimal
    <div className="fixed bottom-0 left-0 right-0 z-50">
      {/* BACKGROUND BLUR LAYER */}
      <div className="absolute inset-0 bg-slate-900/90 backdrop-blur-xl border-t border-slate-700/50" />
      
      {/* NAVIGATION CONTENT */}
      <div className="relative flex justify-around items-center px-2 py-2 safe-area-pb">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          
          return (
            <button
              key={item.id}
              onClick={() => {
                if (item.id === 'portfolio' && onPortfolioClick) {
                  onPortfolioClick();
                } else {
                  navigate(item.path);
                }
              }}
              className="flex flex-col items-center justify-center p-2 rounded-lg transition-all duration-200 min-w-0 flex-1 group relative"
            >
              {/* ACTIVE BACKGROUND GLOW */}
              {isActive && (
                <div 
                  className="absolute inset-0 rounded-lg opacity-20 blur-sm"
                  style={{ backgroundColor: item.color }}
                />
              )}
              
              {/* ICON CONTAINER */}
              <div className="relative mb-1">
                <Icon 
                  className={`w-5 h-5 transition-all duration-200 ${
                    isActive 
                      ? 'scale-110' 
                      : 'scale-100 group-hover:scale-105'
                  }`}
                  style={{ 
                    color: isActive ? item.color : '#94a3b8',
                    filter: isActive ? `drop-shadow(0 0 8px ${item.color}40)` : 'none'
                  }}
                />
              </div>
              
              {/* LABEL */}
              <span 
                className={`text-xs font-medium transition-all duration-200 ${
                  isActive ? 'opacity-100' : 'opacity-60 group-hover:opacity-80'
                }`}
                style={{ color: isActive ? item.color : '#94a3b8' }}
              >
                {item.label}
              </span>
              
              {/* ACTIVE INDICATOR DOT */}
              {isActive && (
                <div 
                  className="absolute -bottom-1 w-1 h-1 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default BottomNavigation;