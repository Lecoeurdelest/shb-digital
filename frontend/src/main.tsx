import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './fonts.css'; // Be Vietnam Pro self-host (D-53) — nạp TRƯỚC tokens (tokens dùng --font)
import './tokens.css';
import App from './App.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
