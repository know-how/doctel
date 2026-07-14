import React, { useMemo } from "react";
import { AvatarState, avatarStates, type AvatarStateConfig } from "./avatarStates";
import { useTheme } from "../../context/ThemeContext";
import { getTokens, type ThemeTokens } from "../../theme/themeTokens";

interface AiAvatarProps {
  /** Current avatar state */
  state?: AvatarState;
  /** Size in pixels (default: 200) */
  size?: number;
  /** Optional class name */
  className?: string;
  /** Whether to show the label below */
  showLabel?: boolean;
}

/**
 * 7-State AI Avatar
 *
 * A sophisticated SVG robot avatar that transitions between 7 emotional/operational
 * states with distinct animations, colors, and visual effects.
 *
 * States: idle → thinking → searching → speaking → listening → processing → error
 */
export const AiAvatar: React.FC<AiAvatarProps> = ({
  state = "idle",
  size = 200,
  className,
  showLabel = false,
}) => {
  const { theme } = useTheme();
  const t: ThemeTokens = getTokens(theme);
  const cfg: AvatarStateConfig = avatarStates[state];
  const isDark = theme === "dark";

  // Derive colors from theme and state
  const headFill = isDark ? "#1A1F35" : "#E8EDF4";
  const headStroke = cfg.accentColor;
  const eyeBg = isDark ? "#0A0E1A" : "#D0D8E4";
  const eyeColor = cfg.accentColor;
  const bodyGlow = cfg.glowColor;

  // Generate unique keyframes ID to avoid collisions
  const uid = React.useId();

  const styles = useMemo(() => {
    const dotBounce = `
      @keyframes ai-dot-bounce-${uid} {
        0%, 80%, 100% { transform: translateY(0); opacity: 0.3; }
        40% { transform: translateY(-6px); opacity: 1; }
      }
    `;

    const floatAnim = `
      @keyframes ai-float-${uid} {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-12px); }
      }
    `;

    const floatSlowAnim = `
      @keyframes ai-float-slow-${uid} {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-8px); }
      }
    `;

    const shakeAnim = `
      @keyframes ai-shake-${uid} {
        0%, 100% { transform: translateX(0); }
        10% { transform: translateX(-4px) rotate(-1deg); }
        20% { transform: translateX(4px) rotate(1deg); }
        30% { transform: translateX(-4px); }
        40% { transform: translateX(4px); }
        50% { transform: translateX(-2px); }
        60% { transform: translateX(2px); }
        70% { transform: translateX(-1px); }
        80% { transform: translateX(1px); }
      }
    `;

    const blinkAnim = `
      @keyframes ai-blink-${uid} {
        0%, 45%, 55%, 100% { transform: scaleY(1); }
        50% { transform: scaleY(0.1); }
      }
    `;

    const scanAnim = `
      @keyframes ai-scan-${uid} {
        0%, 100% { height: 0; opacity: 0; }
        50% { height: 90px; opacity: 0.6; }
      }
    `;

    const pulseGlowAnim = `
      @keyframes ai-pulse-glow-${uid} {
        0%, 100% { opacity: 0.3; transform: scale(1); }
        50% { opacity: 0.8; transform: scale(1.05); }
      }
    `;

    const ringPulseAnim = `
      @keyframes ai-ring-pulse-${uid} {
        0% { r: 50; opacity: 0.5; stroke-width: 2; }
        100% { r: 85; opacity: 0; stroke-width: 1; }
      }
    `;

    const spinAnim = `
      @keyframes ai-spin-${uid} {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
    `;

    const glitchAnim = `
      @keyframes ai-glitch-${uid} {
        0%, 90%, 100% { opacity: 0; }
        92% { opacity: 0.8; transform: translate(3px, -2px); }
        94% { opacity: 0; transform: translate(-3px, 2px); }
        96% { opacity: 0.6; transform: translate(2px, 1px); }
        98% { opacity: 0; }
      }
    `;

    const waveAnim = `
      @keyframes ai-wave-${uid} {
        0%, 100% { transform: scaleY(0.3); opacity: 0.5; }
        50% { transform: scaleY(1); opacity: 1; }
      }
    `;

    const scanEyeAnim = `
      @keyframes ai-scan-eye-${uid} {
        0%, 100% { transform: translateX(-8px); }
        50% { transform: translateX(8px); }
      }
    `;

    const particleOrbitAnim = `
      @keyframes ai-particle-orbit-${uid} {
        0% { transform: rotate(0deg) translateX(55px) rotate(0deg); }
        100% { transform: rotate(360deg) translateX(55px) rotate(-360deg); }
      }
    `;

    return {
      dotBounce,
      floatAnim,
      floatSlowAnim,
      shakeAnim,
      blinkAnim,
      scanAnim,
      pulseGlowAnim,
      ringPulseAnim,
      spinAnim,
      glitchAnim,
      waveAnim,
      scanEyeAnim,
      particleOrbitAnim,
    };
  }, [uid]);

  const bodyAnimationName =
    state === "error" ? `ai-shake-${uid}` :
    state === "thinking" ? `ai-float-slow-${uid}` :
    `ai-float-${uid}`;

  const bodyAnimationDur =
    state === "error" ? "0.5s" :
    `${cfg.animationDuration}s`;

  return (
    <div
      className={className}
      role="img"
      aria-label={`AI Avatar: ${cfg.label}`}
      style={{
        position: "relative",
        width: size,
        height: size,
        flexShrink: 0,
      }}
    >
      <style>
        {styles.dotBounce}
        {styles.floatAnim}
        {styles.floatSlowAnim}
        {styles.shakeAnim}
        {styles.blinkAnim}
        {styles.scanAnim}
        {styles.pulseGlowAnim}
        {styles.ringPulseAnim}
        {styles.spinAnim}
        {styles.glitchAnim}
        {styles.waveAnim}
        {styles.scanEyeAnim}
        {styles.particleOrbitAnim}
      </style>

      {/* Glow backdrop */}
      <div
        style={{
          position: "absolute",
          inset: "-20px",
          borderRadius: "50%",
          background: `radial-gradient(circle, ${bodyGlow} 0%, transparent 70%)`,
          opacity: 0.8,
          pointerEvents: "none",
          animation: state === "thinking" ? `ai-pulse-glow-${uid} 2s ease-in-out infinite` : undefined,
        }}
      />

      {/* Ring Pulse (searching, listening) */}
      {cfg.ringPulse && (
        <svg
          width={size}
          height={size}
          viewBox="0 0 200 200"
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            pointerEvents: "none",
          }}
        >
          <circle
            cx="100"
            cy="100"
            r="50"
            fill="none"
            stroke={cfg.accentColor}
            strokeWidth="2"
            opacity="0.5"
            style={{
              animation: `ai-ring-pulse-${uid} 2.5s ease-out infinite`,
              transformOrigin: "center",
            }}
          />
          <circle
            cx="100"
            cy="100"
            r="50"
            fill="none"
            stroke={cfg.accentColor}
            strokeWidth="2"
            opacity="0.3"
            style={{
              animation: `ai-ring-pulse-${uid} 2.5s ease-out infinite`,
              animationDelay: "0.8s",
              transformOrigin: "center",
            }}
          />
        </svg>
      )}

      {/* Spinner (processing) */}
      {cfg.spinner && (
        <svg
          width={size}
          height={size}
          viewBox="0 0 200 200"
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            pointerEvents: "none",
          }}
        >
          <circle
            cx="100"
            cy="100"
            r="65"
            fill="none"
            stroke={cfg.accentColor + "20"}
            strokeWidth="3"
          />
          <circle
            cx="100"
            cy="100"
            r="65"
            fill="none"
            stroke={cfg.accentColor}
            strokeWidth="3"
            strokeDasharray="60 300"
            strokeLinecap="round"
            style={{
              animation: `ai-spin-${uid} 1.5s linear infinite`,
              transformOrigin: "center",
            }}
          />
          {/* Data flow dots on spinner */}
          {[0, 1, 2].map((i) => (
            <circle
              key={i}
              r="4"
              fill={cfg.accentColor}
              opacity="0.7"
              style={{
                animation: `ai-particle-orbit-${uid} 2s linear infinite`,
                animationDelay: `${i * 0.4}s`,
                transformOrigin: "100px 100px",
              }}
            />
          ))}
        </svg>
      )}

      {/* Main Robot SVG */}
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 200 200"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          position: "relative",
          zIndex: 2,
          animation: `${bodyAnimationName} ${bodyAnimationDur} ease-in-out infinite`,
          filter: state === "error"
            ? "none"
            : `drop-shadow(0 0 15px ${cfg.glowColor})`,
        }}
      >
        {/* === SOUND WAVES (speaking, listening) === */}
        {cfg.waves && (
          <g opacity="0.6">
            {/* Left waves */}
            <rect x="42" y="75" width="4" height="12" rx="2" fill={cfg.accentColor} style={{ animation: `ai-wave-${uid} 0.8s ease-in-out infinite`, transformOrigin: "bottom" }} />
            <rect x="35" y="72" width="4" height="18" rx="2" fill={cfg.accentColor} style={{ animation: `ai-wave-${uid} 0.8s ease-in-out infinite`, animationDelay: "0.15s", transformOrigin: "bottom" }} />
            <rect x="28" y="68" width="4" height="26" rx="2" fill={cfg.accentColor} style={{ animation: `ai-wave-${uid} 0.8s ease-in-out infinite`, animationDelay: "0.3s", transformOrigin: "bottom" }} />
            {/* Right waves */}
            <rect x="154" y="75" width="4" height="12" rx="2" fill={cfg.accentColor} style={{ animation: `ai-wave-${uid} 0.8s ease-in-out infinite`, transformOrigin: "bottom" }} />
            <rect x="161" y="72" width="4" height="18" rx="2" fill={cfg.accentColor} style={{ animation: `ai-wave-${uid} 0.8s ease-in-out infinite`, animationDelay: "0.15s", transformOrigin: "bottom" }} />
            <rect x="168" y="68" width="4" height="26" rx="2" fill={cfg.accentColor} style={{ animation: `ai-wave-${uid} 0.8s ease-in-out infinite`, animationDelay: "0.3s", transformOrigin: "bottom" }} />
          </g>
        )}

        {/* === SCANNER BEAM (thinking) === */}
        {cfg.scannerVisible && (
          <g>
            <path
              d="M100 85 L55 185 L145 185 Z"
              fill="url(#scanGradient)"
              style={{
                animation: `ai-scan-${uid} 3s ease-in-out infinite`,
                transformOrigin: "top",
              }}
            />
            {/* Scan line */}
            <line
              x1="60"
              y1="140"
              x2="140"
              y2="140"
              stroke={cfg.scannerColor}
              strokeWidth="2"
              opacity="0.6"
              style={{
                animation: `ai-scan-${uid} 3s ease-in-out infinite`,
                transformOrigin: "top",
              }}
            />
          </g>
        )}

        {/* === PARTICLES (thinking, searching, processing) === */}
        {cfg.particles && (
          <g>
            {/* Orbiting particles */}
            {[0, 1, 2, 3, 4].map((i) => (
              <circle
                key={i}
                r="3"
                fill={cfg.particleColor}
                opacity="0.7"
                style={{
                  animation: `ai-particle-orbit-${uid} ${3 + i * 0.5}s linear infinite`,
                  animationDelay: `${i * 0.3}s`,
                  transformOrigin: "100px 100px",
                }}
              />
            ))}
          </g>
        )}

        {/* === NECK === */}
        <rect x="85" y="100" width="30" height="15" rx="3" fill={headStroke} opacity="0.8" />

        {/* === HEAD === */}
        <rect
          x="55" y="35" width="90" height="70" rx="22"
          fill={headFill}
          stroke={headStroke}
          strokeWidth="3"
        />

        {/* Head interior subtle glow */}
        <rect
          x="55" y="35" width="90" height="70" rx="22"
          fill="none"
          stroke={cfg.accentColor}
          strokeWidth="1"
          opacity="0.15"
        />

        {/* === ANTENNA === */}
        <line
          x1="100" y1="35" x2="100" y2="15"
          stroke={headStroke}
          strokeWidth="3"
          strokeLinecap="round"
          opacity={cfg.antennaGlow ? 1 : 0.4}
        />
        <circle
          cx="100" cy="12" r="5"
          fill={cfg.antennaGlow ? cfg.accentColor : headStroke}
          opacity={cfg.antennaGlow ? 1 : 0.5}
        >
          {cfg.antennaGlow && (
            <animate
              attributeName="opacity"
              values="0.7;1;0.7"
              dur="2s"
              repeatCount="indefinite"
            />
          )}
        </circle>

        {/* Antenna glow ring */}
        {cfg.antennaGlow && (
          <circle
            cx="100" cy="12" r="9"
            fill="none"
            stroke={cfg.accentColor}
            strokeWidth="1"
            opacity="0.4"
          >
            <animate
              attributeName="r"
              values="7;12;7"
              dur="2s"
              repeatCount="indefinite"
            />
            <animate
              attributeName="opacity"
              values="0.5;0;0.5"
              dur="2s"
              repeatCount="indefinite"
            />
          </circle>
        )}

        {/* === EYE BACKGROUND === */}
        <rect
          x="70" y="52" width="60" height="24" rx="12"
          fill={eyeBg}
        />

        {/* === GLITCH OVERLAY (error) === */}
        {cfg.glitch && (
          <g style={{ animation: `ai-glitch-${uid} 3s infinite` }}>
            <rect x="55" y="35" width="90" height="70" rx="22" fill={cfg.accentColor} opacity="0.3" />
            <rect x="70" y="52" width="60" height="24" rx="12" fill={cfg.accentColor} opacity="0.5" />
          </g>
        )}

        {/* === EYES === */}
        {cfg.eyeStyle === "x" ? (
          /* X Eyes (error) */
          <>
            <line x1="78" y1="58" x2="90" y2="70" stroke={cfg.accentColor} strokeWidth="3" strokeLinecap="round" />
            <line x1="90" y1="58" x2="78" y2="70" stroke={cfg.accentColor} strokeWidth="3" strokeLinecap="round" />
            <line x1="110" y1="58" x2="122" y2="70" stroke={cfg.accentColor} strokeWidth="3" strokeLinecap="round" />
            <line x1="122" y1="58" x2="110" y2="70" stroke={cfg.accentColor} strokeWidth="3" strokeLinecap="round" />
          </>
        ) : cfg.eyeStyle === "scan" ? (
          /* Scanning Eyes (searching) */
          <>
            <circle
              cx="84" cy="64" r="5"
              fill={cfg.accentColor}
              style={{ animation: `ai-scan-eye-${uid} 2s ease-in-out infinite` }}
            />
            <circle
              cx="116" cy="64" r="5"
              fill={cfg.accentColor}
              style={{ animation: `ai-scan-eye-${uid} 2s ease-in-out infinite`, animationDelay: "0.2s" }}
            />
            {/* Pupils */}
            <circle cx="84" cy="64" r="2.5" fill={eyeBg} />
            <circle cx="116" cy="64" r="2.5" fill={eyeBg} />
          </>
        ) : cfg.eyeStyle === "pulse" ? (
          /* Pulse Eyes (thinking, processing) */
          <>
            <circle cx="84" cy="64" r="6" fill={cfg.accentColor}>
              <animate attributeName="r" values="4;7;4" dur="1.5s" repeatCount="indefinite" />
            </circle>
            <circle cx="116" cy="64" r="6" fill={cfg.accentColor}>
              <animate attributeName="r" values="4;7;4" dur="1.5s" repeatCount="indefinite" begin="0.2s" />
            </circle>
            <circle cx="84" cy="64" r="2" fill={eyeBg} />
            <circle cx="116" cy="64" r="2" fill={eyeBg} />
          </>
        ) : cfg.eyeStyle === "wave" ? (
          /* Wave Eyes (speaking) */
          <>
            <ellipse cx="80" cy="64" rx="4" ry="6" fill={cfg.accentColor}>
              <animate attributeName="ry" values="6;3;6" dur="0.8s" repeatCount="indefinite" />
            </ellipse>
            <ellipse cx="88" cy="64" rx="4" ry="6" fill={cfg.accentColor}>
              <animate attributeName="ry" values="6;3;6" dur="0.8s" repeatCount="indefinite" begin="0.2s" />
            </ellipse>
            <ellipse cx="112" cy="64" rx="4" ry="6" fill={cfg.accentColor}>
              <animate attributeName="ry" values="6;3;6" dur="0.8s" repeatCount="indefinite" />
            </ellipse>
            <ellipse cx="120" cy="64" rx="4" ry="6" fill={cfg.accentColor}>
              <animate attributeName="ry" values="6;3;6" dur="0.8s" repeatCount="indefinite" begin="0.2s" />
            </ellipse>
          </>
        ) : cfg.eyeStyle === "listening" ? (
          /* Listening Eyes — concentric (attentive) */
          <>
            <circle cx="84" cy="64" r="7" fill={cfg.accentColor} opacity="0.8" />
            <circle cx="84" cy="64" r="4" fill={eyeBg} />
            <circle cx="116" cy="64" r="7" fill={cfg.accentColor} opacity="0.8" />
            <circle cx="116" cy="64" r="4" fill={eyeBg} />
            {/* Glow pulses */}
            <circle cx="84" cy="64" r="10" fill="none" stroke={cfg.accentColor} strokeWidth="1" opacity="0.5">
              <animate attributeName="r" values="7;11;7" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.5;0;0.5" dur="2s" repeatCount="indefinite" />
            </circle>
            <circle cx="116" cy="64" r="10" fill="none" stroke={cfg.accentColor} strokeWidth="1" opacity="0.5">
              <animate attributeName="r" values="7;11;7" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.5;0;0.5" dur="2s" repeatCount="indefinite" />
            </circle>
          </>
        ) : (
          /* Normal Eyes (idle) */
          <>
            <circle cx="84" cy="64" r="4.5" fill={cfg.accentColor} className="ai-eye" />
            <circle cx="116" cy="64" r="4.5" fill={cfg.accentColor} className="ai-eye" />
            <circle cx="84" cy="64" r="2" fill={eyeBg} />
            <circle cx="116" cy="64" r="2" fill={eyeBg} />
          </>
        )}

        {/* === MOUTH / EXPRESSION === */}
        {cfg.eyeStyle === "x" ? (
          /* Frown (error) */
          <path d="M85 82 Q100 76 115 82" stroke={cfg.accentColor} strokeWidth="2" fill="none" strokeLinecap="round" />
        ) : cfg.eyeStyle === "listening" || cfg.eyeStyle === "wave" ? (
          /* Smile (speaking, listening) */
          <path d="M85 80 Q100 88 115 80" stroke={cfg.accentColor} strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.7" />
        ) : (
          /* Neutral (idle, thinking, searching, processing) */
          <line x1="88" y1="82" x2="112" y2="82" stroke={cfg.accentColor} strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        )}

        {/* === BODY / CHEST === */}
        <rect
          x="70" y="115" width="60" height="40" rx="10"
          fill={headFill}
          stroke={headStroke}
          strokeWidth="2"
          opacity="0.9"
        />

        {/* Chest indicator light */}
        <circle
          cx="100" cy="135" r="6"
          fill={cfg.accentColor}
          opacity="0.8"
        >
          {state !== "idle" && state !== "error" && (
            <animate
              attributeName="opacity"
              values="0.4;1;0.4"
              dur="1.5s"
              repeatCount="indefinite"
            />
          )}
        </circle>

        {/* Chest glow */}
        <circle
          cx="100" cy="135" r="10"
          fill="none"
          stroke={cfg.accentColor}
          strokeWidth="1"
          opacity="0.3"
        >
          {state === "thinking" && (
            <animate
              attributeName="r"
              values="8;14;8"
              dur="2s"
              repeatCount="indefinite"
            />
          )}
        </circle>

        {/* === THINKING DOTS (thinking state) — below body === */}
        {state === "thinking" && (
          <g transform="translate(0, 170)">
            {[0, 1, 2].map((i) => (
              <circle
                key={i}
                cx={85 + i * 15}
                cy="0"
                r="3"
                fill={cfg.accentColor}
                style={{
                  animation: `ai-dot-bounce-${uid} 1.5s ease-in-out infinite`,
                  animationDelay: `${i * 0.3}s`,
                }}
              />
            ))}
          </g>
        )}

        {/* === GRADIENTS === */}
        <defs>
          <linearGradient id="scanGradient" x1="100" y1="85" x2="100" y2="185" gradientUnits="userSpaceOnUse">
            <stop stopColor={cfg.scannerColor} stopOpacity="0.6" />
            <stop offset="1" stopColor={cfg.scannerColor} stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>

      {/* Label */}
      {showLabel && (
        <div
          style={{
            position: "absolute",
            bottom: -4,
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: 11,
            fontWeight: 600,
            color: cfg.accentColor,
            background: isDark ? "rgba(0,0,0,0.6)" : "rgba(255,255,255,0.8)",
            padding: "2px 10px",
            borderRadius: 8,
            whiteSpace: "nowrap",
            letterSpacing: "0.02em",
            backdropFilter: "blur(8px)",
            opacity: 0.85,
          }}
        >
          {cfg.label}
        </div>
      )}
    </div>
  );
};
