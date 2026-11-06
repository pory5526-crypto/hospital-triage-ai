const IconSymptom = () => (
  <svg viewBox="0 0 24 24">
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
    <circle cx="12" cy="12" r="4.2" />
  </svg>
);

const IconDept = () => (
  <svg viewBox="0 0 24 24">
    <rect height="16" rx="2.4" width="17" x="3.5" y="4" />
    <path d="M7.5 9h9M7.5 13h6" />
  </svg>
);

const IconCalendar = () => (
  <svg viewBox="0 0 24 24">
    <rect height="15" rx="2.4" width="17" x="3.5" y="5" />
    <path d="M8 3v4M16 3v4M3.5 10h17" />
  </svg>
);

const IconReport = () => (
  <svg viewBox="0 0 24 24">
    <path d="M6 3.5h8.5L19 8v12.5H6z" />
    <path d="M14 3.5V8h5M9 13h6M9 16.5h4" />
  </svg>
);

const ENTRY_ICONS = [IconSymptom, IconDept, IconCalendar, IconReport];

interface WelcomeCardProps {
  hospital: string;
  subtitle: string;
  entries: string[];
  onEntry: (name: string) => void;
}

export function WelcomeCard({ hospital, subtitle, entries, onEntry }: WelcomeCardProps) {
  return (
    <div className="welcome">
      <div className="w-glow" />
      <div className="w-top">
        <div className="avatar">
          <span>医</span>
        </div>
        <div>
          <div className="w-name">
            <h2>小医助</h2>
            <span className="tag">AI 导诊</span>
          </div>
          <p className="w-desc">
            {hospital} · {subtitle}
          </p>
        </div>
      </div>
      <svg className="ecg" preserveAspectRatio="none" viewBox="0 0 343 26">
        <path d="M0 16 H74 l5 -9 l6 17 l5 -8 H148 l7 -11 l6 15 l5 -4 H232 l6 -8 l5 13 l5 -5 H343" />
      </svg>
      <div className="entries">
        {entries.map((name, index) => {
          const Icon = ENTRY_ICONS[index] ?? IconSymptom;
          return (
            <button className="entry" key={name} onClick={() => onEntry(name)} type="button">
              <i>
                <Icon />
              </i>
              <b>{name}</b>
            </button>
          );
        })}
      </div>
    </div>
  );
}
