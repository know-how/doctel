import React from 'react';

export const AnimatedRobot: React.FC = () => {
  return (
    <div className="animated-robot-container" style={{ position: 'relative', width: '220px', height: '220px', alignSelf: 'center', margin: '20px 0' }}>
      <style>
        {`
          @keyframes float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-15px); }
          }
          @keyframes scan {
            0%, 100% { height: 0; opacity: 0; }
            50% { height: 120px; opacity: 0.5; }
          }
          @keyframes blink {
            0%, 45%, 55%, 100% { transform: scaleY(1); }
            50% { transform: scaleY(0.1); }
          }
          .robot-body {
            animation: float 4s ease-in-out infinite;
          }
          .robot-eye {
            animation: blink 4s infinite;
            transform-origin: center;
          }
          .scanner-beam {
            animation: scan 3s ease-in-out infinite;
          }
        `}
      </style>
      <svg width="100%" height="100%" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg" className="robot-body">
        {/* Document Hologram */}
        <path d="M70 120 L130 120 L130 160 L70 160 Z" fill="rgba(31, 231, 255, 0.1)" stroke="#1FE7FF" strokeWidth="2" strokeDasharray="4 4"/>
        <path d="M80 130 L120 130 M80 140 L120 140 M80 150 L100 150" stroke="#1FE7FF" strokeWidth="2" strokeLinecap="round"/>
        {/* Scanner Beam */}
        <path d="M100 85 L60 180 L140 180 Z" fill="url(#scanGradient)" className="scanner-beam" style={{ transformOrigin: 'top' }}/>
        {/* Head */}
        <rect x="60" y="40" width="80" height="60" rx="20" fill="#1A1F35" stroke="url(#blueGradient)" strokeWidth="4"/>
        {/* Antenna */}
        <path d="M100 40 L100 20" stroke="#5B88FF" strokeWidth="4" strokeLinecap="round"/>
        <circle cx="100" cy="15" r="6" fill="#1FE7FF" className="robot-eye"/>
        {/* Eyes */}
        <rect x="75" y="55" width="50" height="20" rx="10" fill="#0A0E1A"/>
        <circle cx="85" cy="65" r="4" fill="#1FE7FF" className="robot-eye" style={{boxShadow: '0 0 10px #1FE7FF'}}/>
        <circle cx="115" cy="65" r="4" fill="#1FE7FF" className="robot-eye" style={{boxShadow: '0 0 10px #1FE7FF'}}/>
        {/* Base / Neck */}
        <rect x="85" y="100" width="30" height="15" fill="#5B88FF"/>
        {/* Gradients */}
        <defs>
          <linearGradient id="blueGradient" x1="0" y1="0" x2="200" y2="200" gradientUnits="userSpaceOnUse">
            <stop stopColor="#5B88FF" />
            <stop offset="1" stopColor="#1FE7FF" />
          </linearGradient>
          <linearGradient id="scanGradient" x1="100" y1="85" x2="100" y2="180" gradientUnits="userSpaceOnUse">
            <stop stopColor="#1FE7FF" stopOpacity="0.8" />
            <stop offset="1" stopColor="#1FE7FF" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
};
