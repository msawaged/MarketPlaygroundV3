// frontend/src/components/PortfolioComponents.jsx
// Portfolio Integration Components (SAFE)
// - Summary + ActivePositions + Modal
// - Close confirmation (supports partial close if backend supports `qty`)
// - Cache-busting + optimistic UI + backend polling to reflect true state

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { API_BASE } from "../lib/api";

// Now uses centralized API base from Vite env
const BACKEND_URL = API_BASE;

/* =========================
   Portfolio Summary Card
========================= */
const PortfolioSummary = ({ refreshNonce = 0 }) => {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const fetchPortfolio = async () => {
    try {
      const response = await fetch(
        `${BACKEND_URL}/api/paper-trading/portfolio/demo_user?ts=${Date.now()}`,
        { headers: { "Cache-Control": "no-store" } }
      );
      const data = await response.json();
      setPortfolio(data);
      setLastUpdate(new Date());
    } catch (error) {
      console.error("Portfolio fetch error:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 30000);
    return () => clearInterval(interval);
  }, [refreshNonce]);

  // ... rest of the component remains the same
  if (loading) {
    return (
      <div className="bg-slate-800/50 rounded-lg p-4 animate-pulse">
        <div className="h-4 bg-slate-700 rounded w-1/3 mb-2"></div>
        <div className="h-8 bg-slate-700 rounded w-1/2"></div>
      </div>
    );
  }

  if (!portfolio) return null;

  const { account, summary } = portfolio;
  const totalReturn = (account?.total_return_pct ?? 0) * 100;
  const isProfit = totalReturn >= 0;

  return (
    <motion.div
      className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-xl p-4 border border-blue-500/30"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-bold text-white">Portfolio Summary</h3>
        <div className="text-xs text-slate-400">Updated: {lastUpdate.toLocaleTimeString()}</div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <motion.div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600" whileHover={{ scale: 1.02, borderColor: "#3b82f6" }}>
          <div className="text-xs text-slate-400 font-semibold">Total Value</div>
          <div className="text-xl font-bold text-white">
            ${(account?.total_value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
        </motion.div>

        <motion.div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600" whileHover={{ scale: 1.02, borderColor: isProfit ? "#22c55e" : "#ef4444" }}>
          <div className="text-xs text-slate-400 font-semibold">Total P&L</div>
          <div className={`text-xl font-bold ${isProfit ? "text-green-400" : "text-red-400"}`}>
            {isProfit ? "+" : ""}${(account?.total_pnl ?? 0).toFixed(2)}
          </div>
          <div className={`text-sm ${isProfit ? "text-green-300" : "text-red-300"}`}>
            ({isProfit ? "+" : ""}{totalReturn.toFixed(2)}%)
          </div>
        </motion.div>

        <motion.div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600" whileHover={{ scale: 1.02, borderColor: "#22c55e" }}>
          <div className="text-xs text-slate-400 font-semibold">Cash Balance</div>
          <div className="text-lg font-bold text-green-400">
            ${(account?.cash_balance ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
        </motion.div>

        <motion.div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600" whileHover={{ scale: 1.02, borderColor: "#8b5cf6" }}>
          <div className="text-xs text-slate-400 font-semibold">Positions</div>
          <div className="text-lg font-bold text-purple-400">{summary?.total_positions ?? 0}</div>
          <div className="text-sm text-slate-300">Grade: {summary?.performance_grade ?? "—"}</div>
        </motion.div>
      </div>

      <motion.button
        onClick={fetchPortfolio}
        className="w-full bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/50 rounded-lg py-2 text-blue-400 text-sm font-semibold transition-colors"
        whileTap={{ scale: 0.98 }}
      >
        Refresh Portfolio
      </motion.button>
    </motion.div>
  );
};

/* =========================
   Active Positions + Close
========================= */
const ActivePositions = ({ refreshNonce = 0, onChanged }) => {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);

  // Close dialog state
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [closing, setClosing] = useState(false);
  const [closeError, setCloseError] = useState(null);
  const [selected, setSelected] = useState(null); // { position, qty }

  const fetchPositions = async () => {
    try {
      const response = await fetch(
        `${BACKEND_URL}/api/paper-trading/portfolio/demo_user?ts=${Date.now()}`,
        { headers: { "Cache-Control": "no-store" } }
      );
      const data = await response.json();
      setPositions(Array.isArray(data?.positions) ? data.positions : []);
    } catch (error) {
      console.error("Positions fetch error:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPositions();
    const i = setInterval(fetchPositions, 30000);
    return () => clearInterval(i);
  }, [refreshNonce]);

  const openConfirm = (position) => {
    setSelected({
      position,
      qty: Number(position.quantity ?? position.qty ?? 0) || 0,
    });
    setCloseError(null);
    setConfirmOpen(true);
  };

  // Poll until the closed position disappears (or give up after 10 tries)
  async function pollUntilGone({ userId, closedId, tries = 10, intervalMs = 500 }) {
    for (let i = 0; i < tries; i++) {
      const resp = await fetch(
        `${BACKEND_URL}/api/paper-trading/portfolio/${encodeURIComponent(userId)}?ts=${Date.now()}&r=${Math.random()}`,
        { headers: { "Cache-Control": "no-store" } }
      );
      const data = await resp.json().catch(() => ({}));
      const list = Array.isArray(data?.positions) ? data.positions : [];
      const stillThere = list.some((p) => (p.position_id ?? p.id ?? p.strategy_id) === closedId);
      if (!stillThere) return list; // ✅ gone
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    return null; // ❌ backend never reflected the change in time
  }

  const handleClose = async () => {
    if (!selected) return;
    setClosing(true);
    setCloseError(null);
    try {
      // Resolve the position identifier your backend expects
      const positionId =
        selected.position.position_id ??
        selected.position.id ??
        selected.position.strategy_id;

      if (!positionId) throw new Error("Missing position_id on position payload");

      // If your backend needs a real user id, replace 'demo_user'
      const userId = "demo_user";

      // Optional partial close: only include qty if > 0
      const params = new URLSearchParams({
        user_id: String(userId),
        position_id: String(positionId),
      });
      const qtyNum = Number(selected.qty);
      if (qtyNum && qtyNum > 0) params.set("qty", String(qtyNum));

      // Send as QUERY PARAMS (backend expects query, not JSON)
      const url = `${BACKEND_URL}/api/paper-trading/close_position?${params.toString()}`;
      const response = await fetch(url, {
        method: "POST",
        headers: { "Cache-Control": "no-store" },
      });

      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `HTTP ${response.status}`);
      }

      // 🟣 Optimistic UI – drop it locally immediately
      setPositions((prev) =>
        prev.filter((p) => (p.position_id ?? p.id ?? p.strategy_id) !== positionId)
      );

      // Close the dialog + toast + clear selection
      setConfirmOpen(false);
      setSelected(null);
      setCloseError(null);
      toast("Position closed successfully!");

      // 🔍 Poll backend until it disappears (handles write lag)
      const fresh = await pollUntilGone({ userId, closedId: positionId });
      if (fresh) setPositions(fresh);

      // Tell Summary to refresh
      onChanged && onChanged();
    } catch (e) {
      setCloseError(e.message || "Failed to close position");
    } finally {
      setClosing(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-slate-800/50 rounded-lg p-4 animate-pulse">
            <div className="h-4 bg-slate-700 rounded w-1/4 mb-2"></div>
            <div className="h-6 bg-slate-700 rounded w-1/2"></div>
          </div>
        ))}
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="bg-slate-800/50 rounded-lg p-6 text-center">
        <div className="text-slate-400 text-lg mb-2">No active positions</div>
        <div className="text-sm text-slate-500">Execute a strategy to see positions here</div>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3">
        <h3 className="text-lg font-bold text-white mb-4">Active Positions</h3>
        <AnimatePresence>
          {positions.map((position, index) => {
            const pnlIsProfit = (position.unrealized_pnl ?? 0) >= 0;
            return (
              <motion.div
                key={position.strategy_id ?? position.position_id ?? position.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ delay: index * 0.05 }}
                className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-lg p-4 border border-slate-700"
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-lg font-bold text-white">{position.ticker}</span>
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold ${
                          position.position_type === "long"
                            ? "bg-green-500/20 text-green-400 border border-green-500/30"
                            : "bg-red-500/20 text-red-400 border border-red-500/30"
                        }`}
                      >
                        {String(position.position_type || "").toUpperCase()}
                      </span>
                    </div>
                    <div className="text-sm text-slate-400">
                      Qty: {position.quantity} @ ${position.avg_price}
                    </div>
                  </div>

                  <motion.button
                    onClick={() => openConfirm(position)}
                    className="bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 rounded-lg px-3 py-1 text-red-400 text-sm font-semibold"
                    whileTap={{ scale: 0.95 }}
                  >
                    Close
                  </motion.button>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center">
                    <div className="text-xs text-slate-400">Current Price</div>
                    <div className="text-sm font-bold text-white">${position.current_price}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-slate-400">Market Value</div>
                    <div className="text-sm font-bold text-blue-400">
                      ${Number(position.market_value ?? 0).toFixed(2)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-slate-400">P&L</div>
                    <div className={`text-sm font-bold ${pnlIsProfit ? "text-green-400" : "text-red-400"}`}>
                      {pnlIsProfit ? "+" : ""}${Number(position.unrealized_pnl ?? 0).toFixed(2)}
                    </div>
                    <div className={`text-xs ${pnlIsProfit ? "text-green-300" : "text-red-300"}`}>
                      ({pnlIsProfit ? "+" : ""}{Number((position.unrealized_pnl_pct ?? 0) * 100).toFixed(2)}%)
                    </div>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-slate-700">
                  <div className="text-xs text-slate-400">
                    Opened: {position.opened_at ? new Date(position.opened_at).toLocaleString() : "—"}
                  </div>
                  <div className="text-xs text-slate-500 mt-1">Belief: "{position.belief ?? "—"}"</div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Close confirmation dialog */}
      {confirmOpen && selected && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 text-white shadow-xl">
            <div className="px-4 py-3 border-b border-slate-700">
              <h4 className="text-base font-semibold">Close Position</h4>
              <p className="text-xs text-slate-400 mt-1">
                {selected.position.ticker} — current qty {selected.position.quantity}
              </p>
            </div>

            <div className="p-4 space-y-3">
              <label className="block text-xs text-slate-400">Quantity to close (optional)</label>
              <input
                type="number"
                min={0}
                max={Math.abs(Number(selected.position.quantity) || 0)}
                step={1}
                value={selected.qty}
                onChange={(e) => setSelected((s) => ({ ...s, qty: Number(e.target.value) }))}
                className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {closeError && <div className="text-red-400 text-sm">{closeError}</div>}
              <div className="text-xs text-slate-400">
                If your backend doesn't support partial closes, we'll close the full position.
              </div>
            </div>

            <div className="px-4 py-3 border-t border-slate-700 flex justify-end gap-2">
              <button onClick={() => setConfirmOpen(false)} className="px-3 py-2 text-sm rounded-lg bg-slate-700 hover:bg-slate-600">
                Cancel
              </button>
              <button
                onClick={handleClose}
                disabled={closing}
                className="px-3 py-2 text-sm rounded-lg bg-red-600 hover:bg-red-700 disabled:opacity-50"
              >
                {closing ? "Closing…" : "Confirm Close"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

/* =========================
   Portfolio Modal Wrapper
========================= */
const PortfolioModal = ({ isOpen, onClose }) => {
  // 🔄 children refetch when this bumps
  const [refreshNonce, setRefreshNonce] = useState(0);
  const refreshAll = () => setRefreshNonce((n) => n + 1);

  if (!isOpen) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-6 max-w-md w-full max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-white">Portfolio</h2>
          <motion.button
            onClick={onClose}
            className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-full flex items-center justify-center text-slate-400"
            whileTap={{ scale: 0.95 }}
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
            </svg>
          </motion.button>
        </div>

        <div className="space-y-6">
          <PortfolioSummary refreshNonce={refreshNonce} />
          <ActivePositions refreshNonce={refreshNonce} onChanged={refreshAll} />
        </div>
      </motion.div>
    </motion.div>
  );
};

/* =========================
   Floating Portfolio Button (optional)
========================= */
const PortfolioButton = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [portfolioSummary, setPortfolioSummary] = useState(null);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const response = await fetch(
          `${BACKEND_URL}/api/paper-trading/portfolio/demo_user?ts=${Date.now()}`,
          { headers: { "Cache-Control": "no-store" } }
        );
        const data = await response.json();
        setPortfolioSummary(data);
      } catch (error) {
        console.error("Portfolio summary fetch error:", error);
      }
    };

    fetchSummary();
    const interval = setInterval(fetchSummary, 60000);
    return () => clearInterval(interval);
  }, []);

  const totalValue = portfolioSummary?.account?.total_value ?? 0;
  const totalPnl = portfolioSummary?.account?.total_pnl ?? 0;
  const isProfit = totalPnl >= 0;

  return (
    <>
      <motion.button
        onClick={() => setIsModalOpen(true)}
        className="fixed top-20 left-4 z-40 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-xl p-3 shadow-lg border border-blue-500/30"
        whileHover={{ scale: 1.05, y: -2 }}
        whileTap={{ scale: 0.95 }}
      >
        <div className="text-left">
          <div className="text-xs font-semibold">Portfolio</div>
          <div className="text-sm font-bold">
            ${totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className={`text-xs ${isProfit ? "text-green-300" : "text-red-300"}`}>
            {isProfit ? "+" : ""}${totalPnl.toFixed(0)}
          </div>
        </div>
      </motion.button>

      <AnimatePresence>
        {isModalOpen && (
          <PortfolioModal
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
          />
        )}
      </AnimatePresence>
    </>
  );
};

/* =========================
   Tiny Toast Helper
========================= */
function toast(message = "Done!", timeout = 3000) {
  try {
    const t = document.createElement("div");
    t.className = "fixed top-20 right-4 bg-green-500 text-white px-4 py-2 rounded-lg z-[100] shadow-lg";
    t.textContent = message;
    document.body.appendChild(t);
    setTimeout(() => document.body.removeChild(t), timeout);
  } catch {}
}

export { PortfolioSummary, ActivePositions, PortfolioModal, PortfolioButton };