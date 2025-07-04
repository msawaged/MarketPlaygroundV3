// frontend/src/components/SimulatedChart.js

import React, { useRef } from 'react';
import { Line, Bar } from 'react-chartjs-2';
import Chart from 'chart.js/auto';

/**
 * SimulatedChart Component
 * Dynamically renders a simulation chart based on strategy type and asset class.
 * Supports options (call/put/straddle), bonds (allocation), stocks (pnl line),
 * and currencies (fluctuation). Falls back to a default chart if unsupported.
 */

const SimulatedChart = ({ ticker, strategyType, price, confidence, assetClass }) => {
  const chartRef = useRef(null);
  const currentPrice = parseFloat(price);

  // 🔁 Strategy simulation logic by asset class and strategy
  const generateData = () => {
    const x = [];
    const y = [];

    // ✅ Options Strategy Payoff Curve
    if (
      assetClass === 'option' ||
      strategyType.toLowerCase().includes('call') ||
      strategyType.toLowerCase().includes('put')
    ) {
      for (let p = currentPrice * 0.5; p <= currentPrice * 1.5; p += 1) {
        x.push(p.toFixed(2));
        let payoff = 0;

        if (strategyType === 'Long Call') {
          const strike = currentPrice * 1.05;
          payoff = Math.max(0, p - strike);
        } else if (strategyType === 'Long Put') {
          const strike = currentPrice * 0.95;
          payoff = Math.max(0, strike - p);
        } else if (strategyType === 'Long Straddle') {
          const strike = currentPrice;
          payoff = Math.max(0, p - strike) + Math.max(0, strike - p);
        } else {
          payoff = (p - currentPrice) * 0.5;
        }

        y.push(payoff.toFixed(2));
      }

      return {
        type: 'line',
        data: {
          labels: x,
          datasets: [{
            label: `${strategyType} Payoff`,
            data: y,
            fill: true,
            tension: 0.4,
            borderWidth: 2,
            pointRadius: 0,
          }],
        },
      };
    }

    // ✅ Bonds → Allocation bar chart for laddered ETFs
    if (assetClass === 'bond') {
      const ladders = ['SHY (Short)', 'IEF (Mid)', 'AGG (Broad)'];
      const weights = [33, 33, 34]; // Simulated equal ladder
      return {
        type: 'bar',
        data: {
          labels: ladders,
          datasets: [{
            label: 'Capital Allocation (%)',
            data: weights,
            backgroundColor: ['#a5d8ff', '#74c0fc', '#4dabf7'],
          }],
        },
      };
    }

    // ✅ Stocks → Simulated projected PnL
    if (assetClass === 'stock') {
      for (let p = currentPrice * 0.8; p <= currentPrice * 1.2; p += 1) {
        x.push(p.toFixed(2));
        const pnl = (p - currentPrice).toFixed(2);
        y.push(pnl);
      }

      return {
        type: 'line',
        data: {
          labels: x,
          datasets: [{
            label: `Projected PnL for ${ticker}`,
            data: y,
            fill: true,
            tension: 0.2,
            borderWidth: 2,
            pointRadius: 0,
          }],
        },
      };
    }

    // ✅ Currency → Simulated FX rate fluctuation
    if (assetClass === 'currency') {
      const mid = currentPrice;
      const range = 0.05 * mid;
      for (let i = -10; i <= 10; i++) {
        const p = (mid + (i * range) / 10).toFixed(4);
        x.push(p);
        y.push((Math.sin(i / 3) * 0.5).toFixed(3)); // Fake sine-wave fluctuation
      }

      return {
        type: 'line',
        data: {
          labels: x,
          datasets: [{
            label: `${ticker} Simulated FX Movement`,
            data: y,
            fill: false,
            borderWidth: 2,
            pointRadius: 1,
          }],
        },
      };
    }

    // ❓ Fallback Simulation for unsupported types
    return {
      type: 'line',
      data: {
        labels: ['No data'],
        datasets: [{
          label: 'No simulation available',
          data: [0],
        }],
      },
    };
  };

  const { type, data } = generateData();

  const options = {
    responsive: true,
    animation: {
      duration: 1500,
    },
    plugins: {
      title: {
        display: true,
        text: `${ticker} Simulation (${assetClass})`,
        font: { size: 18 },
      },
      tooltip: {
        callbacks: {
          label: (ctx) => `Value: ${ctx.raw}`,
        },
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: assetClass === 'bond' ? 'ETF Segment' : 'Price or Rate',
        },
      },
      y: {
        title: {
          display: true,
          text: assetClass === 'bond' ? 'Allocation (%)' : 'Profit / Loss',
        },
      },
    },
  };

  return (
    <div style={{ padding: '1rem' }}>
      {type === 'bar' ? (
        <Bar ref={chartRef} data={data} options={options} />
      ) : (
        <Line ref={chartRef} data={data} options={options} />
      )}
      <p style={{ textAlign: 'center', marginTop: '0.5rem' }}>
        📊 Confidence Level: <strong>{(confidence * 100).toFixed(1)}%</strong>
      </p>
    </div>
  );
};

export default SimulatedChart;
