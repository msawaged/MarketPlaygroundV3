/*
================================================================================
FILE: BottomNavigation.jsx (SAFE COPY)
--------------------------------------------------------------------------------
- Drop‐in replacement for frontend/src/components/BottomNavigation.jsx
- Always visible on desktop + mobile (no hidden classes by default)
- Child‐route aware active state (prefix match)
- Safe‐area padding for iOS notch
- Optional onPortfolioClick() handler to open a modal/sheet instead of routing
- Accessible (aria-current, keyboard activation)
================================================================================
*/

import React, { useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Home, TrendingUp, BarChart3, User, Zap, Flame } from 'lucide-react';

/**
 * Props
 * -----
 * onPortfolioClick?: () => void   // Optional: intercept Portfolio to open a sheet/modal
 * hideOnDesktop?: boolean         // If true, hide on md+ screens (defaults to false)
 * items?: Array<{ id, label, icon, path, color? }>
 */
export default function BottomNavigation({ onPortfolioClick, hideOnDesktop = false, items }) {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = items?.length
    ? items
    : [
        { id: 'home',      label: 'Home',      icon: Home,       path: '/select-tool',   color: '#3b82f6' },
        { id: 'chat',      label: 'AI Trade',  icon: Zap,        path: '/chat',          color: '#8b5cf6' },
        { id: 'hot-trades', label: 'Hot Trades', icon: Flame,     path: '/hot-trades',    color: '#f97316' },
        { id: 'portfolio', label: 'Portfolio', icon: TrendingUp, path: '/paper-trading', color: '#22c55e' },
        { id: 'analytics', label: 'Stats',     icon: BarChart3,  path: '/analytics',     color: '#f59e0b' },
        { id: 'profile',   label: 'Profile',   icon: User,       path: '/profile',       color: '#ef4444' },
      ];

  // Prefix-based active detection so nested routes are highlighted
  const isActive = useCallback(
    (path) => {
      if (!path) return false;
      if (path === '/') return location.pathname === '/';
      return location.pathname === path || location.pathname.startsWith(`${path}/`);
    },
    [location.pathname]
  );

  const containerVisibility = hideOnDesktop ? 'md:hidden' : '';

  return (
    <nav
      role="navigation"
      aria-label="Primary"
      className={`fixed bottom-0 left-0 right-0 z-[60] ${containerVisibility}`}
    >
      {/* Background / border / blur layer */}
      <div className="absolute inset-0 bg-slate-950/90 backdrop-blur-xl border-t border-slate-800/60 shadow-[0_-8px_30px_rgba(0,0,0,0.45)]" />

      {/* Navigation content */}
      <ul
        className="relative flex justify-around items-stretch gap-1 px-2 py-2 select-none"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 0.5rem)' }}
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);

          const handlePress = () => {
            if (item.id === 'portfolio' && onPortfolioClick) {
              onPortfolioClick();
            } else {
              navigate(item.path);
            }
          };

          return (
            <li key={item.id} className="flex-1 min-w-0">
              <button
                type="button"
                onClick={handlePress}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handlePress();
                  }
                }}
                aria-label={item.label}
                aria-current={active ? 'page' : undefined}
                className="group relative w-full h-full flex flex-col items-center justify-center gap-1 rounded-xl p-2 outline-none focus-visible:ring-2 focus-visible:ring-offset-0 focus-visible:ring-blue-500 transition-all duration-200"
              >
                {/* Active background glow */}
                {active && (
                  <span
                    aria-hidden
                    className="absolute inset-0 rounded-xl opacity-20 blur-[6px]"
                    style={{ backgroundColor: item.color || '#60a5fa' }}
                  />
                )}

                {/* Icon */}
                <span className="relative inline-flex items-center justify-center">
                  <Icon
                    className={`w-5 h-5 transition-transform duration-200 ${
                      active ? 'scale-110' : 'scale-100 group-active:scale-95'
                    }`}
                    style={{
                      color: active ? (item.color || '#60a5fa') : '#94a3b8',
                      filter: active ? `drop-shadow(0 0 8px ${(item.color || '#60a5fa')}40)` : 'none',
                    }}
                    aria-hidden
                  />
                </span>

                {/* Label */}
                <span
                  className={`text-[11px] font-medium leading-none transition-opacity duration-200 ${
                    active ? 'opacity-100' : 'opacity-70 group-hover:opacity-90'
                  }`}
                  style={{ color: active ? (item.color || '#60a5fa') : '#94a3b8' }}
                >
                  {item.label}
                </span>

                {/* Active indicator dot */}
                {active && (
                  <span
                    aria-hidden
                    className="absolute -bottom-1 w-1.5 h-1.5 rounded-full"
                    style={{ backgroundColor: item.color || '#60a5fa' }}
                  />
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}