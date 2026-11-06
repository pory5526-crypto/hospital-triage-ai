import type { EmergencyCard as EmergencyCardType } from '../lib/types';

interface Props {
  card: EmergencyCardType;
  onCall: () => void;
}

export function EmergencyCard({ card, onCall }: Props) {
  return (
    <div className="emg-card">
      <div className="emg-head">
        <span className="dot">!</span>
        <b>{card.title}</b>
      </div>
      <div className="emg-body">
        <p>{card.advice}</p>
      </div>
      <div className="emg-loc">急诊位置：{card.location}</div>
      {card.route.length > 0 && (
        <ul className="emg-route">
          {card.route.slice(0, 3).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      <div className="emg-btns">
        <button className="btn danger" onClick={onCall} type="button">
          拨打急诊电话 {card.phone}
        </button>
      </div>
    </div>
  );
}
