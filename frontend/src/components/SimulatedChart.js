// frontend/src/components/SimulatedChart.js

import React, { useRef } from 'react';
import { Line, Bar } from 'react-chartjs-2';
import Chart from 'chart.js/auto';

/**
 * Renders a dynamic simulation chart based on asset class and strategy type.
 * Supports options, bonds, stocks, and currency simulations using Chart.js.
 */
const SimulatedChart = ({ ticker, strategyType, price, confidence, assetClass }) => {
  const chartRef = useRef(null);
  const currentPrice = parseFloat(price);

  // Dynamic simulation logic based on asset class
  const generateData = () => {
    const x = [];
    const y = [];

    // ---- Options (e.g. Long Call, Long Put, etc.) ----
    if (assetClass === 'option' || strategyType.toLowerCase().includes('call') || strategyType.toLowerCase().includes('put')) {
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

    // ---- Bonds → Simulate ladder maturity buckets ----
    if (assetClass === 'bond') {
      const ladders = ['SHY (Short)', 'IEF (Mid)', 'AGG (Broad)'];
      const weights = [20, 30, 50]; // Adjust as needed
      return {
        type: 'bar',
        data: {
          labels: ladders,
          datasets: [{
            label: 'Capital Allocation (%)',
            data: weights,
            backgroundColor: ['#8cb9ff', '#7abfff', '#4a90e2'],
          }],
        },
      };
    }

    // ---- Stocks → Simulate linear price movement → projected gain/loss ----
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

    // ---- Currency → Simulate range-bound FX rate swing ----
    if (assetClass === 'currency') {
      const mid = currentPrice;
      const range = 0.05 * mid;
      for (let i = -10; i <= 10; i++) {
        const p = (mid + (i * range) / 10).toFixed(4);
        x.push(p);
        y.push((Math.sin(i / 3) * 0.5).toFixed(3)); // Fake fluctuation
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

    // ---- Default fallback ----
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

  // Render appropriate chart type
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
