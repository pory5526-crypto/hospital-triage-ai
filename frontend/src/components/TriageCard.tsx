import { useEffect, useState } from 'react';
import type { TriageCard as TriageCardType } from '../lib/types';

interface Props {
  card: TriageCardType;
  onViewFlow: () => void;
  onChangeDept?: () => void;
  showChangeDept?: boolean;
}

function Meter({ value }: { value: number }) {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(() => setWidth(value), 140);
    return () => window.clearTimeout(timer);
  }, [value]);

  return (
    <div className="meter">
      <i style={{ width: `${width}%` }} />
    </div>
  );
}

export function TriageCard({ card, onViewFlow, onChangeDept, showChangeDept }: Props) {
  return (
    <div className="analysis">
      <div className="an-head">
        <span className="spark">
          <svg viewBox="0 0 24 24">
            <path d="m12 3 2.2 5.4L20 10.5l-5.8 2.1L12 18l-2.2-5.4L4 10.5l5.8-2.1z" />
          </svg>
        </span>
        <b>智能分析结果</b>
        <span className="ok">已完成</span>
      </div>

      <div className="an-list">
        <div className="an-item">
          <div className="nm">
            {card.primary.dept}
            <small>建议优先就诊</small>
          </div>
          <Meter value={card.primary.match} />
          <div className="pct">{card.primary.match}%</div>
        </div>

        {card.alternatives.map((alt) => (
          <div className="an-item second" key={alt.dept}>
            <div className="nm">
              {alt.dept}
              <small>备选排查</small>
            </div>
            <Meter value={alt.match} />
            <div className="pct">{alt.match}%</div>
          </div>
        ))}
      </div>

      <div className="an-note">{card.note}</div>

      <div className="an-btns">
        <button className="btn primary" onClick={onViewFlow} type="button">
          查看就诊步骤
        </button>
        {showChangeDept && (
          <button className="btn ghost" onClick={onChangeDept} type="button">
            更换科室
          </button>
        )}
      </div>
    </div>
  );
}
