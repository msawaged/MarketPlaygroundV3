// 📁 FILE: frontend/src/components/ToolSelectorPage.jsx
import React from 'react';
import { useNavigate } from 'react-router-dom';

const ToolSelectorPage = () => {
  const navigate = useNavigate();

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(180deg, #0f172a 0%, #1e293b 100%)',
      color: '#f8fafc',
      display: 'flex',
      flexDirection: 'column',
      padding: '1.5rem',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      position: 'relative'
    }}>
      {/* Header Section */}
      <div style={{
        textAlign: 'center',
        marginTop: '2rem',
        marginBottom: '2rem'
      }}>
        <h1 style={{
          fontSize: '2.5rem',
          fontWeight: '700',
          marginBottom: '0.5rem',
          background: 'linear-gradient(to right, #3b82f6, #a855f7, #ec4899)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          letterSpacing: '-0.02em'
        }}>
          MarketPlayground
        </h1>
        <p style={{
          color: '#94a3b8',
          fontSize: '1rem',
          fontWeight: '400'
        }}>
          Choose how you want to explore the market today
        </p>
      </div>

      {/* Main Content - Scrollable if needed */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
        maxWidth: '100%',
        marginBottom: '2rem'
      }}>
        {/* AI Chat Assistant Card */}
        <button
          onClick={() => navigate('/chat')}
          style={{
            background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
            color: 'white',
            padding: '1.5rem',
            borderRadius: '20px',
            border: 'none',
            cursor: 'pointer',
            position: 'relative',
            minHeight: '140px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            boxShadow: '0 10px 25px rgba(139, 92, 246, 0.25)',
            transition: 'transform 0.2s',
            WebkitTapHighlightColor: 'transparent'
          }}
          onTouchStart={(e) => {
            e.currentTarget.style.transform = 'scale(0.98)';
          }}
          onTouchEnd={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
          }}
        >
          <div style={{
            position: 'absolute',
            top: '0.75rem',
            right: '1rem',
            background: 'rgba(255, 255, 255, 0.2)',
            padding: '0.25rem 0.5rem',
            borderRadius: '12px',
            fontSize: '0.65rem',
            fontWeight: '600',
            letterSpacing: '0.05em'
          }}>
            RECOMMENDED
          </div>
          <div style={{ fontSize: '2.5rem' }}>💬</div>
          <h2 style={{ 
            fontSize: '1.25rem', 
            fontWeight: '600',
            margin: 0
          }}>
            AI Chat Assistant
          </h2>
          <p style={{ 
            fontSize: '0.875rem', 
            opacity: 0.9,
            textAlign: 'center',
            margin: 0,
            lineHeight: '1.3'
          }}>
            Talk naturally about your market beliefs and get instant AI-powered strategy recommendations
          </p>
        </button>

        {/* Asset Basket Builder Card */}
        <button
          onClick={() => navigate('/basket-builder')}
          style={{
            background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
            color: 'white',
            padding: '1.5rem',
            borderRadius: '20px',
            border: 'none',
            cursor: 'pointer',
            minHeight: '140px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            boxShadow: '0 10px 25px rgba(16, 185, 129, 0.25)',
            transition: 'transform 0.2s',
            WebkitTapHighlightColor: 'transparent'
          }}
          onTouchStart={(e) => {
            e.currentTarget.style.transform = 'scale(0.98)';
          }}
          onTouchEnd={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
          }}
        >
          <div style={{ fontSize: '2.5rem' }}>📊</div>
          <h2 style={{ 
            fontSize: '1.25rem', 
            fontWeight: '600',
            margin: 0
          }}>
            Asset Basket Builder
          </h2>
          <p style={{ 
            fontSize: '0.875rem', 
            opacity: 0.9,
            textAlign: 'center',
            margin: 0,
            lineHeight: '1.3'
          }}>
            Create diversified portfolios with AI-powered asset allocation and risk management
          </p>
        </button>
      </div>

      {/* Bottom Navigation - Fixed */}
      <div style={{
        borderTop: '1px solid rgba(148, 163, 184, 0.1)',
        paddingTop: '1rem',
        paddingBottom: 'env(safe-area-inset-bottom, 1rem)'
      }}>
        <p style={{
          color: '#64748b',
          fontSize: '0.75rem',
          textAlign: 'center',
          marginBottom: '0.75rem',
          fontWeight: '500'
        }}>
          Advanced Tools
        </p>
        <div style={{
          display: 'flex',
          justifyContent: 'space-around',
          gap: '0.5rem'
        }}>
          <button
            onClick={() => navigate('/generator')}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              fontSize: '0.8rem',
              padding: '0.5rem',
              cursor: 'pointer',
              fontWeight: '500',
              WebkitTapHighlightColor: 'transparent'
            }}
          >
            Classic Generator
          </button>
          <button
            onClick={() => navigate('/strategy-ops')}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              fontSize: '0.8rem',
              padding: '0.5rem',
              cursor: 'pointer',
              fontWeight: '500',
              WebkitTapHighlightColor: 'transparent'
            }}
          >
            Strategy Ops
          </button>
          <button
            onClick={() => navigate('/hot-trades')}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              fontSize: '0.8rem',
              padding: '0.5rem',
              cursor: 'pointer',
              fontWeight: '500',
              WebkitTapHighlightColor: 'transparent'
            }}
          >
            Hot Trades
          </button>
        </div>
      </div>
    </div>
  );
};

export default ToolSelectorPage;