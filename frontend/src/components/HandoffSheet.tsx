import type { HandoffInfo } from '../lib/types';

interface Props {
  info: HandoffInfo;
  hospitalName: string;
  onClose: () => void;
}

export function HandoffSheet({ info, hospitalName, onClose }: Props) {
  return (
    <>
      <div className="mask" onClick={onClose} />
      <div className="sheet">
        <div className="grab" />
        <div className="sheet-head">
          <div>
            <h3>{info.title}</h3>
            <p>{hospitalName} · 人工导诊台</p>
          </div>
          <button className="close" onClick={onClose} aria-label="关闭">
            <svg fill="none" viewBox="0 0 24 24">
              <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="handoff-body">
          <div className="ho-phone">
            <div className="ico">
              <svg viewBox="0 0 24 24">
                <path d="M6.5 3.5h3l1.5 4-2 1.5a12 12 0 0 0 6 6l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A17 17 0 0 1 4.5 5.7 2 2 0 0 1 6.5 3.5Z" />
              </svg>
            </div>
            <div>
              <div className="num">{info.phone}</div>
              <div className="lbl">点击下方按钮可直接拨打</div>
            </div>
          </div>

          <div className="ho-rows">
            <div className="ho-row">
              <span>人工服务时间</span>
              <span>{info.hours}</span>
            </div>
            <div className="ho-row">
              <span>转接原因</span>
              <span>
                {info.reason === 'user_request'
                  ? '您主动要求人工协助'
                  : info.reason === 'out_of_scope'
                    ? '问题超出导诊范围'
                    : info.reason === 'fail_streak'
                      ? '连续未识别您的问题'
                      : '系统建议转人工'}
              </span>
            </div>
          </div>

          <div className="ho-tip">{info.afterHoursTip}</div>
        </div>

        <div className="sheet-foot">
          <button className="btn ghost" onClick={onClose} type="button">
            稍后再说
          </button>
          <a className="btn primary" href={`tel:${info.phone}`} style={{ textDecoration: 'none' }}>
            拨打 {info.phone}
          </a>
        </div>
      </div>
    </>
  );
}
