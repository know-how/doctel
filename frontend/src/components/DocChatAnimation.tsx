import React from 'react';

export const DocChatAnimation: React.FC = () => {
  return (
    <div style={{ position: 'relative', width: '320px', height: '200px', alignSelf: 'center', margin: '20px 0' }}>
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
        @keyframes document-move-right {
          0% { transform: translateX(0); opacity: 1; }
          100% { transform: translateX(140px); opacity: 0; }
        }
        @keyframes answer-move-left {
          0% { transform: translateX(140px); opacity: 0; }
          100% { transform: translateX(0); opacity: 1; }
        }
        @keyframes typing-dots {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }
        @keyframes glass-shimmer {
          0%, 100% { opacity: 0.15; }
          50% { opacity: 0.3; }
        }
        @keyframes bolt-pulse {
          0%, 100% { filter: brightness(1); }
          50% { filter: brightness(1.3); }
        }
        .human-float { animation: float 3s ease-in-out infinite; }
        .bolt-float { animation: float 3s ease-in-out infinite 0.5s; }
        .glass-effect { animation: glass-shimmer 2s ease-in-out infinite; }
        .bolt-glow { animation: bolt-pulse 2s ease-in-out infinite; }
        .doc-to-bolt { animation: document-move-right 3s ease-in-out infinite; }
        .answer-to-human { animation: answer-move-left 3s ease-in-out infinite 1.5s; }
        .typing-dot { animation: typing-dots 1.4s ease-in-out infinite; }
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
      `}</style>
      <svg width="100%" height="100%" viewBox="0 0 320 200" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="humanGrad" x1="0" y1="0" x2="0" y2="200" gradientUnits="userSpaceOnUse">
            <stop stopColor="#6366F1" />
            <stop offset="1" stopColor="#818CF8" />
          </linearGradient>
          <linearGradient id="boltGrad" x1="0" y1="0" x2="0" y2="200" gradientUnits="userSpaceOnUse">
            <stop stopColor="#5B88FF" />
            <stop offset="1" stopColor="#1FE7FF" />
          </linearGradient>
          <linearGradient id="glassGrad" x1="0" y1="0" x2="0" y2="200" gradientUnits="userSpaceOnUse">
            <stop stopColor="#1FE7FF" stopOpacity="0.1" />
            <stop offset="1" stopColor="#5B88FF" stopOpacity="0.2" />
          </linearGradient>
          <linearGradient id="docGrad" x1="0" y1="0" x2="100" y2="0" gradientUnits="userSpaceOnUse">
            <stop stopColor="#F59E0B" />
            <stop offset="1" stopColor="#FBBF24" />
          </linearGradient>
          <linearGradient id="answerGrad" x1="0" y1="0" x2="100" y2="0" gradientUnits="userSpaceOnUse">
            <stop stopColor="#10B981" />
            <stop offset="1" stopColor="#34D399" />
          </linearGradient>
        </defs>

        <rect x="10" y="140" width="120" height="8" rx="2" fill="rgba(255,255,255,0.1)"/>
        <rect x="190" y="140" width="120" height="8" rx="2" fill="rgba(255,255,255,0.1)"/>

        <g className="human-float">
          <circle cx="50" cy="90" r="25" fill="#374151"/>
          <circle cx="42" cy="85" r="3" fill="#FFFFFF" opacity="0.9"/>
          <circle cx="58" cy="85" r="3" fill="#FFFFFF" opacity="0.9"/>
          <path d="M40 100 Q50 108 60 100" stroke="#E5E7EB" strokeWidth="2" strokeLinecap="round" fill="none"/>
          <ellipse cx="50" cy="130" rx="20" ry="15" fill="url(#humanGrad)"/>
        </g>

        <g className="bolt-float">
          <rect x="210" y="60" width="60" height="50" rx="12" fill="#1A1F35" stroke="url(#boltGrad)" strokeWidth="3" className="bolt-glow"/>
          <circle cx="230" cy="80" r="5" fill="#1FE7FF" className="bolt-glow"/>
          <circle cx="250" cy="80" r="5" fill="#1FE7FF" className="bolt-glow"/>
          <line x1="240" y1="60" x2="240" y2="45" stroke="#5B88FF" strokeWidth="3" strokeLinecap="round"/>
          <circle cx="240" cy="40" r="5" fill="#1FE7FF"/>
          <rect x="220" y="115" width="40" height="25" rx="5" fill="url(#boltGrad)"/>
        </g>

        <g>
          <rect x="155" y="30" width="4" height="120" rx="2" fill="url(#glassGrad)" className="glass-effect"/>
          <rect x="155" y="30" width="4" height="40" rx="2" fill="rgba(255,255,255,0.2)" className="glass-effect"/>
        </g>

        <g className="doc-to-bolt" style={{ transformBox: 'fill-box', transformOrigin: 'left' }}>
          <rect x="25" y="60" width="30" height="38" rx="3" fill="url(#docGrad)" stroke="#F59E0B" strokeWidth="1"/>
          <line x1="30" y1="70" x2="50" y2="70" stroke="#78350F" strokeWidth="1.5"/>
          <line x1="30" y1="76" x2="50" y2="76" stroke="#78350F" strokeWidth="1"/>
          <line x1="30" y1="82" x2="45" y2="82" stroke="#78350F" strokeWidth="1"/>
        </g>

        <g style={{ opacity: 0.7 }}>
          <circle cx="240" cy="100" r="15" fill="none" stroke="#1FE7FF" strokeWidth="2" strokeDasharray="60" strokeDashoffset="0">
            <animateTransform attributeName="transform" type="rotate" from="0 240 100" to="360 240 100" dur="2s" repeatCount="indefinite"/>
          </circle>
        </g>

        <g className="answer-to-human" style={{ transformBox: 'fill-box', transformOrigin: 'left' }}>
          <rect x="210" y="60" width="30" height="30" rx="6" fill="url(#answerGrad)" stroke="#10B981" strokeWidth="1"/>
          <path d="M222 72 L228 78 L238 68" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
        </g>

        <g>
          <path d="M25 45 Q20 45 20 55 Q20 65 30 65 L45 65 Q55 65 55 55 L55 50 L45 45 Z" fill="rgba(99,102,241,0.9)"/>
          <circle cx="30" cy="52" r="2" className="typing-dot" fill="#FFFFFF"/>
          <circle cx="37" cy="52" r="2" className="typing-dot" fill="#FFFFFF"/>
          <circle cx="44" cy="52" r="2" className="typing-dot" fill="#FFFFFF"/>
        </g>

        <g>
          <path d="M265 45 Q270 45 270 55 Q270 65 260 65 L245 65 Q235 65 235 55 L235 50 L245 45 Z" fill="rgba(31,231,255,0.9)"/>
          <circle cx="248" cy="52" r="1.5" fill="#FFFFFF"/>
          <circle cx="255" cy="52" r="1.5" fill="#FFFFFF"/>
          <circle cx="262" cy="52" r="1.5" fill="#FFFFFF"/>
        </g>

        <text x="50" y="170" fontFamily="Inter, sans-serif" fontSize="10" fill="rgba(255,255,255,0.6)" textAnchor="middle">User</text>
        <text x="240" y="170" fontFamily="Inter, sans-serif" fontSize="10" fill="rgba(255,255,0.6)" textAnchor="middle">DocIntel AI</text>
      </svg>
    </div>
  );
};