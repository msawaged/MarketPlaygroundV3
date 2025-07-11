// frontend/src/components/SimulatedChart3D.js

import React from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import { a, useSpring } from '@react-spring/three';

/**
 * SimulatedChart3D Component
 * 🎯 Multi-Asset 3D Visualizer for MarketPlayground
 * 
 * This advanced 3D visualization dynamically reflects:
 * - Geometry based on asset class
 * - Trade structure via number of legs
 * - Animated glow based on AI confidence
 * - Interactive orbit camera
 * 
 * Props:
 * - ticker (string)
 * - strategyType (string)
 * - price (number)
 * - confidence (number from 0 to 1)
 * - assetClass (string)
 * - trade_legs (array of strings) ← ✅ now used to scale complexity
 */

const SimulatedChart3D = ({
  ticker,
  strategyType,
  price,
  confidence,
  assetClass,
  trade_legs = []
}) => {
  const parsedPrice = parseFloat(price);

  // ✅ Animated glow and bounce using react-spring
  const { scale } = useSpring({
    from: { scale: 0.85 },
    to: { scale: 1.1 },
    config: { duration: 2200 },
    loop: true,
  });

  /**
   * 🔷 Select geometry based on asset class
   * Can evolve to include curve shapes, risk surfaces, or payoff maps
   */
  const getGeometry = () => {
    switch (assetClass) {
      case 'option':
        return <torusKnotGeometry args={[0.7, 0.2, 128, 16]} />;
      case 'stock':
        return <sphereGeometry args={[0.9, 64, 64]} />;
      case 'etf':
        return <boxGeometry args={[1, 1, 1]} />;
      case 'bond':
        return <cylinderGeometry args={[0.4, 0.4, 1.5, 32]} />;
      case 'futures':
        return <coneGeometry args={[0.6, 1.5, 32]} />;
      case 'crypto':
        return <icosahedronGeometry args={[0.9, 1]} />;
      case 'currency':
      case 'swaptions':
      case 'swap':
        return <torusGeometry args={[0.6, 0.15, 16, 100]} />;
      default:
        return <octahedronGeometry args={[0.9, 0]} />;
    }
  };

  /**
   * 🎨 Set color based on asset class — reflects category and risk tone
   */
  const getColor = () => {
    switch (assetClass) {
      case 'option':
        return '#00ffff'; // cyan
      case 'stock':
        return 'limegreen';
      case 'etf':
        return '#ffc107'; // yellow
      case 'bond':
        return '#74c0fc'; // blue
      case 'futures':
        return '#ff6b6b'; // red
      case 'crypto':
        return '#ff8b00'; // orange
      case 'currency':
      case 'swaptions':
      case 'swap':
        return '#9c36b5'; // purple
      default:
        return '#999'; // neutral
    }
  };

  /**
   * 🔁 Create multiple animated meshes if multiple trade legs
   * Adds visual complexity based on how intricate the strategy is
   */
  const renderMeshes = () => {
    const count = Math.max(1, trade_legs.length || 1);

    return Array.from({ length: count }).map((_, idx) => (
      <a.mesh
        key={idx}
        position={[idx * 1.2 - (count * 0.6), 0, 0]}
        scale={scale}
      >
        {getGeometry()}
        <meshStandardMaterial
          color={getColor()}
          roughness={0.25}
          metalness={0.85}
          emissive={'#111'}
          emissiveIntensity={confidence}
        />
      </a.mesh>
    ));
  };

  return (
    <div style={{ width: '100%', height: '400px' }}>
      <Canvas camera={{ position: [0, 1.5, 4], fov: 50 }}>
        {/* 💡 Basic lighting + orbit camera for interactive view */}
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 5, 5]} intensity={1.2} />
        <OrbitControls />

        {/* 🎯 Dynamic mesh (one per trade leg) */}
        {renderMeshes()}

        {/* 🏷️ Floating text with strategy context */}
        <Html position={[0, 1.5, 0]} center>
          <div style={{
            backgroundColor: '#111',
            color: '#eee',
            padding: '6px 12px',
            borderRadius: '10px',
            fontSize: '14px',
            border: '1px solid #444',
          }}>
            {ticker} • {strategyType}<br />
            Legs: {trade_legs.length} • Confidence: {(confidence * 100).toFixed(1)}%
          </div>
        </Html>
      </Canvas>
    </div>
  );
};

export default SimulatedChart3D;
