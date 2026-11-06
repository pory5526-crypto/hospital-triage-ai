import { useEffect, useState } from 'react';

export function StatusBar() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');

  return (
    <div className="status">
      <span>
        {hh}:{mm}
      </span>
      <span className="icons">
        <svg height="11" viewBox="0 0 17 11" width="17">
          <rect fill="#0E2A31" height="4" rx="1" width="3" x="0" y="7" />
          <rect fill="#0E2A31" height="6" rx="1" width="3" x="4.5" y="5" />
          <rect fill="#0E2A31" height="8.5" rx="1" width="3" x="9" y="2.5" />
          <rect fill="#0E2A31" height="11" opacity=".35" rx="1" width="3" x="13.5" y="0" />
        </svg>
        <svg height="11" viewBox="0 0 15 11" width="15">
          <path d="M7.5 9.4 5.2 7.1a3.3 3.3 0 0 1 4.6 0L7.5 9.4Z" fill="#0E2A31" />
          <path
            d="M3 4.9a6.4 6.4 0 0 1 9 0"
            fill="none"
            stroke="#0E2A31"
            strokeLinecap="round"
            strokeWidth="1.5"
          />
          <path
            d="M.9 2.7a9.4 9.4 0 0 1 13.2 0"
            fill="none"
            opacity=".35"
            stroke="#0E2A31"
            strokeLinecap="round"
            strokeWidth="1.5"
          />
        </svg>
        <svg height="11" viewBox="0 0 24 11" width="24">
          <rect
            fill="none"
            height="10"
            rx="3"
            stroke="#0E2A31"
            strokeOpacity=".35"
            width="19"
            x="0.5"
            y="0.5"
          />
          <rect fill="#0E2A31" height="7" rx="1.8" width="15" x="2" y="2" />
          <path d="M21.5 4v3.2a2 2 0 0 0 0-3.2Z" fill="#0E2A31" opacity=".4" />
        </svg>
      </span>
    </div>
  );
}

export function Capsule() {
  return (
    <div className="capsule">
      <span className="dot3">
        <i />
        <i />
        <i />
      </span>
      <span className="sep" />
      <span className="ring" />
    </div>
  );
}
