// frontend/src/components/SimulatedChart.js

import React, { useEffect, useRef } from 'react';
import { Line } from 'react-chartjs-2';
import Chart from 'chart.js/auto';

/**
 * This component renders a payoff curve simulation using Chart.js.
 * It assumes a profitable belief outcome and visualizes how the trade performs
 * across various price points around the current price.
 */
const SimulatedChart = ({ ticker, strategyType, price, confidence }) => {
  const chartRef = useRef(null);

  // Simulate payoff based on strategy type
  const generatePayoffData = () => {
    const currentPrice = parseFloat(price);
    const x = [];
    const y = [];

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
        // Default to linear gain
        payoff = (p - currentPrice) * 0.5;
      }

      y.push(payoff.toFixed(2));
    }

    return { x, y };
  };

  const { x, y } = generatePayoffData();

  const data = {
    labels: x,
    datasets: [
      {
        label: `${strategyType} Payoff Curve`,
        data: y,
        fill: true,
        tension: 0.4,
        borderWidth: 2,
        pointRadius: 0,
      },
    ],
  };

  const options = {
    responsive: true,
    animation: {
      duration: 1500,
    },
    plugins: {
      title: {
        display: true,
        text: `${ticker} Strategy Simulation`,
        font: { size: 20 },
      },
      tooltip: {
        callbacks: {
          label: (ctx) => `Payoff: $${ctx.raw}`,
        },
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Underlying Price',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Profit / Loss',
        },
      },
    },
  };

  return (
    <div style={{ padding: '1rem' }}>
      <Line ref={chartRef} data={data} options={options} />
      <p style={{ textAlign: 'center', marginTop: '0.5rem' }}>
        📈 Confidence Level: <strong>{(confidence * 100).toFixed(1)}%</strong>
      </p>
    </div>
  );
};

export default SimulatedChart;
