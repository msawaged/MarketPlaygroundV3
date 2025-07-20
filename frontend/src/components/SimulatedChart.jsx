// frontend/src/components/SimulatedChart.js

import React, { useRef } from 'react';
import { Line, Bar } from 'react-chartjs-2';
import Chart from 'chart.js/auto';

/**
 * SimulatedChart Component
 * ✅ Handles dynamic visualizations for:
 *    - Options (calls, puts, straddles)
 *    - Stocks
 *    - Bonds (ETF ladder)
 *    - Currencies (wave pattern)
 */

const SimulatedChart = ({ ticker, strategyType, price, confidence, assetClass }) => {
  const chartRef = useRef(null);
  const currentPrice = parseFloat(price);

  const generateData = () => {
    const x = [];
    const y = [];

    // ✅ Options Simulation
    if (
      assetClass === 'option' ||
      assetClass === 'options' ||  // fix for backend plural
      strategyType.toLowerCase().includes('call') ||
      strategyType.toLowerCase().includes('put') ||
      strategyType.toLowerCase().includes('straddle')
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

        y.push(payoff);
      }

      return {
        type: 'line',
        data: {
          labels: x,
          datasets: [
            {
              label: `${strategyType} Payoff`,
              data: y,
              fill: 'start',
              backgroundColor: 'rgba(0, 200, 255, 0.1)',
              borderColor: 'rgba(0, 200, 255, 1)',
              borderWidth: 2,
              tension: 0.4,
              pointRadius: 0,
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
              data: x.map(label => parseFloat(label) === parseFloat(currentPrice.toFixed(2)) ? 0.01 : null),
              backgroundColor: 'red',
              pointRadius: 5,
              type: 'line',
              borderWidth: 0,
            }
          ],
        },
      };
    }

    // ✅ Bonds Simulation
    if (assetClass === 'bond') {
      return {
        type: 'bar',
        data: {
          labels: ['SHY (Short)', 'IEF (Mid)', 'AGG (Broad)'],
          datasets: [{
            label: 'Capital Allocation (%)',
            data: [33, 33, 34],
            backgroundColor: ['#a5d8ff', '#74c0fc', '#4dabf7'],
          }],
        },
      };
    }

    // ✅ Stock PnL Simulation
    if (assetClass === 'stock') {
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
              label: `Projected PnL`,
              data: y,
              borderColor: 'limegreen',
              borderWidth: 2,
              tension: 0.3,
              pointRadius: 0,
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
              data: x.map(label => parseFloat(label) === parseFloat(currentPrice.toFixed(2)) ? 0.01 : null),
              backgroundColor: 'orange',
              pointRadius: 5,
              type: 'line',
              borderWidth: 0,
            }
          ],
        },
      };
    }

    // ✅ Currency Simulation
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
          datasets: [{
            label: 'Simulated FX Movement',
            data: y,
            borderColor: 'deepskyblue',
            borderWidth: 2,
            tension: 0.3,
            pointRadius: 0,
          }],
        },
      };
    }

    // ❓ Fallback
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
    maintainAspectRatio: false,
    animation: { duration: 1200 },
    plugins: {
      title: {
        display: true,
        text: `${ticker} Simulation (${assetClass})`,
        font: { size: 20 },
      },
      legend: {
        labels: {
          color: '#ddd',
          font: { size: 12 },
        },
      },
      tooltip: {
        callbacks: {
          label: ctx => `Value: ${ctx.raw}`,
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
      },
      y: {
        title: {
          display: true,
          text: assetClass === 'bond' ? 'Allocation (%)' : 'Profit / Loss',
          color: '#aaa',
        },
      },
    },
  };

  return (
    <div style={{ padding: '1rem', height: '400px' }}>
      {type === 'bar' ? (
        <Bar ref={chartRef} data={data} options={options} />
      ) : (
        <Line ref={chartRef} data={data} options={options} />
      )}
      <p style={{ textAlign: 'center', marginTop: '0.5rem', color: '#ccc' }}>
        📊 Confidence Level: <strong>{(confidence * 100).toFixed(1)}%</strong>
      </p>
    </div>
  );
};

export default SimulatedChart;
