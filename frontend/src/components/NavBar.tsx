interface NavBarProps {
  title: string;
  onBack?: () => void;
  showOnline?: boolean;
}

export function NavBar({ title, onBack, showOnline = true }: NavBarProps) {
  return (
    <div className="nav">
      <button className="back" onClick={onBack} aria-label="返回">
        <svg height="16" viewBox="0 0 10 16" width="10">
          <path
            d="M8 1 2 8l6 7"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.9"
          />
        </svg>
      </button>
      <h1>{title}</h1>
      {showOnline && (
        <span className="st">
          <i />
          在线
        </span>
      )}
    </div>
  );
}
