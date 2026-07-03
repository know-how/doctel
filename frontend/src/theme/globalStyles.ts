/**
 * Global Styles for Modern Futuristic Design
 * Inject these as a <style> tag in your HTML or use a CSS-in-JS solution
 */

export const globalStyles = `
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  html {
    scroll-behavior: smooth;
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
    background: linear-gradient(135deg, #0F1117 0%, #1A1F35 100%);
    color: #E5E7EB;
    font-size: 14px;
    font-weight: 400;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    overflow-x: hidden;
  }

  #root {
    width: 100%;
    min-height: 100vh;
  }

  /* ===== ANIMATIONS ===== */
  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @keyframes slideInUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes slideInDown {
    from {
      opacity: 0;
      transform: translateY(-20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes slideInLeft {
    from {
      opacity: 0;
      transform: translateX(-20px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  @keyframes slideInRight {
    from {
      opacity: 0;
      transform: translateX(20px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }

  @keyframes shimmer {
    0% {
      background-position: -1000px 0;
    }
    100% {
      background-position: 1000px 0;
    }
  }

  @keyframes glow {
    0%, 100% {
      box-shadow: 0 0 20px rgba(95, 136, 255, 0.4);
    }
    50% {
      box-shadow: 0 0 40px rgba(95, 136, 255, 0.6);
    }
  }

  @keyframes float {
    0%, 100% {
      transform: translateY(0px);
    }
    50% {
      transform: translateY(-10px);
    }
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  @keyframes scaleIn {
    from {
      opacity: 0;
      transform: scale(0.95);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  /* ===== SCROLLBAR STYLING ===== */
  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  ::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 10px;
  }

  ::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, #5B88FF 0%, #1FE7FF 100%);
    border-radius: 10px;
  }

  ::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(180deg, #4A6FE8 0%, #00B8D4 100%);
  }

  /* ===== SELECTION STYLING ===== */
  ::selection {
    background: linear-gradient(135deg, #5B88FF 0%, #1FE7FF 100%);
    color: #FFFFFF;
  }

  ::-moz-selection {
    background: linear-gradient(135deg, #5B88FF 0%, #1FE7FF 100%);
    color: #FFFFFF;
  }

  /* ===== INPUT FOCUS STATES ===== */
  input:focus,
  textarea:focus,
  select:focus {
    outline: none;
  }

  /* ===== LINK STYLING ===== */
  a {
    text-decoration: none;
    color: #464feb;
    transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
  }

  a:hover {
    color: #1FE7FF;
    text-shadow: 0 0 10px rgba(31, 231, 255, 0.3);
  }

  /* ===== TABLE STYLING ===== */
  table {
    width: 100%;
    border-collapse: collapse;
  }

  tr th,
  tr td {
    border: 1px solid #e6e6e6;
  }

  tr th {
    background-color: #f5f5f5;
  }

  /* ===== PLACEHOLDER STYLING ===== */
  ::placeholder {
    color: rgba(255, 255, 255, 0.4);
  }

  :-ms-input-placeholder {
    color: rgba(255, 255, 255, 0.4);
  }

  ::-ms-input-placeholder {
    color: rgba(255, 255, 255, 0.4);
  }

  /* ===== SELECT/OPTION DROPDOWN STYLING ===== */
  select option {
    background-color: #1e2235;
    color: #e5e7eb;
    padding: 8px 12px;
  }

  select option:checked {
    background-color: #3b4568;
    color: #ffffff;
  }

  html[data-theme="light"] select option {
    background-color: #ffffff;
    color: #1f2937;
  }

  html[data-theme="light"] select option:checked {
    background-color: #e8eaee;
    color: #111827;
  }
`
