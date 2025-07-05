// frontend/src/components/SimulatedChart.js

import React, { useRef } from 'react';
import { Line, Bar } from 'react-chartjs-2';
import { motion } from 'framer-motion';
import Chart from 'chart.js/auto';

/**
 * SimulatedChart Component
 * ✅ Handles simulation visuals for options, stocks, bonds, currencies, ETFs
 * ✅ Bond ladder aware using `tradeLegs` prop
 * ✅ Uses color-coded profit/loss and confidence bar
 */

const SimulatedChart = ({ ticker, strategyType, price, confidence, assetClass, tradeLegs = [] }) => {
  const chartRef = useRef(null);
  const currentPrice = parseFloat(price);

  const generateData = () => {
    const x = [];
    const y = [];
    const strategy = strategyType?.toLowerCase() || '';
    const strike = currentPrice;

    // ✅ Option Strategy Payoff
    if (
      assetClass === 'option' || assetClass === 'options' ||
      strategy.includes('call') || strategy.includes('put') || strategy.includes('straddle')
    ) {
      for (let p = currentPrice * 0.5; p <= currentPrice * 1.5; p += 1) {
        x.push(p.toFixed(2));
        let payoff = 0;

        if (strategy.includes('call')) payoff = Math.max(0, p - strike);
        else if (strategy.includes('put')) payoff = Math.max(0, strike - p);
        else if (strategy.includes('straddle')) payoff = Math.abs(p - strike);
        else payoff = (p - currentPrice) * 0.5;

        y.push(payoff.toFixed(2));
      }

      return {
        type: 'line',
        data: {
          labels: x,
          datasets: [
            {
              label: `${strategyType} Payoff`,
              data: y,
              borderColor: '#00e0ff',
              backgroundColor: (ctx) =>
                ctx.chart.data.labels.map((price, i) =>
                  y[i] > 0 ? 'rgba(0,255,0,0.1)' : 'rgba(255,0,0,0.1)'
                ),
              borderWidth: 2,
              tension: 0.3,
              pointRadius: 0,
              fill: true,
            },
            {
              label: 'Break-even Line',
              data: Array(x.length).fill(0),
              borderColor: 'gray',
              borderDash: [6, 6],
              pointRadius: 0,
            },
            {
              label: 'Strike Price',
              data: x.map(label =>
                parseFloat(label).toFixed(2) === strike.toFixed(2) ? 0.01 : null
              ),
              type: 'line',
              backgroundColor: 'red',
              borderWidth: 0,
              pointRadius: 6,
              hoverRadius: 6,
            },
          ],
        },
      };
    }

    // ✅ Smart Bond Ladder (multi-ETF from tradeLegs)
    if (assetClass === 'bond' && Array.isArray(tradeLegs) && tradeLegs.length > 1) {
      // Extract bond tickers and count weights
      const ladderTickers = ['SHY', 'IEF', 'AGG'];
      const weights = { SHY: 0, IEF: 0, AGG: 0 };

      tradeLegs.forEach((leg) => {
        const t = leg.ticker?.toUpperCase();
        if (ladderTickers.includes(t)) weights[t] += leg.weight || 1;
      });

      const total = Object.values(weights).reduce((sum, val) => sum + val, 0) || 1;
      const percentages = ladderTickers.map((t) => ((weights[t] / total) * 100).toFixed(1));

      return {
        type: 'bar',
        data: {
          labels: ladderTickers,
          datasets: [
            {
              label: 'Bond Ladder Allocation (%)',
              data: percentages,
              backgroundColor: ['#a5d8ff', '#74c0fc', '#4dabf7'],
            },
          ],
        },
      };
    }

    // ✅ Stock / ETF PnL
    if (assetClass === 'stock' || assetClass === 'etf') {
      for (let p = currentPrice * 0.8; p <= currentPrice * 1.2; p += 1) {
        x.push(p.toFixed(2));
        y.push((p - currentPrice).toFixed(2));
      }

      return {
        type: 'line',
        data: {
          labels: x,
          datasets: [
            {
              label: 'Projected Profit / Loss',
              data: y,
              borderColor: '#00ff88',
              backgroundColor: (ctx) =>
                ctx.chart.data.labels.map((_, i) =>
                  y[i] > 0 ? 'rgba(0,255,0,0.1)' : 'rgba(255,0,0,0.1)'
                ),
              borderWidth: 2,
              tension: 0.3,
              pointRadius: 0,
              fill: true,
            },
            {
              label: 'Break-even',
              data: Array(x.length).fill(0),
              borderColor: 'gray',
              borderDash: [5, 5],
              pointRadius: 0,
            },
            {
              label: 'Current Price',
              data: x.map(label =>
                parseFloat(label).toFixed(2) === currentPrice.toFixed(2) ? 0.01 : null
              ),
              backgroundColor: 'orange',
              type: 'line',
              borderWidth: 0,
              pointRadius: 5,
            },
          ],
        },
      };
    }

    // ✅ Currency Sim
    if (assetClass === 'currency') {
      for (let i = -10; i <= 10; i++) {
        const p = (currentPrice + i * (currentPrice * 0.01)).toFixed(4);
        x.push(p);
        y.push((Math.sin(i / 3) * 0.5).toFixed(3));
      }

      return {
        type: 'line',
        data: {
          labels: x,
          datasets: [
            {
              label: 'Simulated FX Movement',
              data: y,
              borderColor: 'deepskyblue',
              borderWidth: 2,
              tension: 0.4,
              pointRadius: 0,
            },
          ],
        },
      };
    }

    // ❓ Unknown class fallback
    return {
      type: 'line',
      data: {
        labels: ['No data'],
        datasets: [
          {
            label: 'Unsupported asset class',
            data: [0],
          },
        ],
      },
    };
  };

  const { type, data } = generateData();

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 1000 },
    plugins: {
      title: {
        display: true,
        text: `${ticker} Simulation (${assetClass})`,
        font: { size: 18 },
        color: '#fff',
      },
      legend: {
        labels: { color: '#ccc', font: { size: 12 } },
      },
      tooltip: {
        callbacks: {
          label: ctx => `📍 Value: ${ctx.raw}`,
        },
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: assetClass === 'bond' ? 'ETF' : 'Price',
          color: '#aaa',
        },
        ticks: { color: '#ccc' },
      },
      y: {
        title: {
          display: true,
          text: assetClass === 'bond' ? 'Allocation (%)' : 'Profit / Loss',
          color: '#aaa',
        },
        ticks: { color: '#ccc' },
      },
    },
  };

  return (
    <motion.div
      className="p-4 h-[420px] bg-[#111] rounded-xl shadow-lg"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8 }}
    >
      {type === 'bar' ? (
        <Bar ref={chartRef} data={data} options={options} />
      ) : (
        <Line ref={chartRef} data={data} options={options} />
      )}

      {/* 🔵 Confidence Meter */}
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${confidence * 100}%` }}
        transition={{ duration: 1.2 }}
        className="h-2 bg-blue-400 mt-3 rounded-full"
      />
      <p className="text-center mt-2 text-gray-300">
        📊 Confidence Level: <strong>{(confidence * 100).toFixed(1)}%</strong>
      </p>
    </motion.div>
  );
};

export default SimulatedChart;
