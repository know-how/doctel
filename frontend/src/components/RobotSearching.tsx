import React from 'react';

export const RobotSearching: React.FC = () => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <style>
        {`
          @keyframes search-bob {
            0%, 100% { transform: translateY(0) rotate(0deg); }
            25% { transform: translateY(-2px) rotate(-5deg); }
            75% { transform: translateY(-2px) rotate(5deg); }
          }
          @keyframes search-pulse {
            0%, 100% { opacity: 0.5; transform: scale(0.9); }
            50% { opacity: 1; transform: scale(1.1); }
          }
          .bot-searching {
            animation: search-bob 2s ease-in-out infinite;
          }
          .bot-eye-search {
            animation: search-pulse 1.5s ease-in-out infinite;
          }
        `}
      </style>
      <svg width="24" height="24" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="bot-searching">
        <rect x="4" y="10" width="32" height="20" rx="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.3)" strokeWidth="2"/>
        <path d="M20 10 L20 4" stroke="rgba(255,255,255,0.3)" strokeWidth="2" strokeLinecap="round"/>
        <circle cx="20" cy="4" r="2" fill="#1FE7FF"/>
        <rect x="8" y="15" width="24" height="10" rx="4" fill="#0A0E1A"/>
        <circle cx="14" cy="20" r="3" fill="#1FE7FF" className="bot-eye-search"/>
        <circle cx="26" cy="20" r="3" fill="#1FE7FF" className="bot-eye-search" style={{ animationDelay: '0.75s' }}/>
      </svg>
      <span style={{ fontSize: '14px', color: 'rgba(255,255,255,0.7)', fontWeight: 500, letterSpacing: '0.02em' }}>AI is searching...</span>
    </div>
  );
};
