import { NavBar } from './NavBar';

export interface FlowDept {
  name: string;
  location: string;
}

interface Props {
  dept: FlowDept;
  onBack: () => void;
  onAppointment: () => void;
}

type StepState = 'done' | 'now' | 'todo';

interface Step {
  title: string;
  desc: string;
  state: StepState;
  where?: string;
}

const STEPS: Step[] = [
  {
    title: '在线预问诊',
    desc: '已提交症状描述，生成初步分诊建议，用时 3 分钟。',
    state: 'done',
  },
  {
    title: '预约挂号',
    desc: '选择就诊时段并支付挂号费，医保可直接线上结算。',
    state: 'now',
    where: '小程序 · 本次预约',
  },
  {
    title: '到院签到',
    desc: '到院后扫导诊屏二维码签到，或在自助机刷身份证取号。',
    state: 'todo',
    where: '门诊楼 1F 导诊台',
  },
  {
    title: '候诊叫号',
    desc: '在候诊区等候，叫号会同步推送到微信服务通知。',
    state: 'todo',
  },
  {
    title: '医生就诊',
    desc: '携带既往病历与检查报告进入诊室，向医生说明症状的具体时间。',
    state: 'todo',
    where: '3 号诊室',
  },
  {
    title: '检查与取药',
    desc: '如需抽血或心电图，按医嘱前往 2F 检查区；处方可在门诊药房窗口或线上取药。',
    state: 'todo',
  },
  {
    title: '复诊提醒',
    desc: '检查结果出来后，可在微信里收到复诊提醒并续约。',
    state: 'todo',
  },
];

function PinIcon() {
  return (
    <svg viewBox="0 0 24 24">
      <path d="M12 21s6.5-6 6.5-10.5A6.5 6.5 0 0 0 5.5 10.5C5.5 15 12 21 12 21Z" />
    </svg>
  );
}

export function FlowPage({ dept, onBack, onAppointment }: Props) {
  return (
    <>
      <NavBar title="就诊流程" onBack={onBack} showOnline={false} />

      <div className="content">
        <div className="detail-hero">
          <div className="dh-row">
            <div>
              <div className="dh-dept">{dept.name}</div>
              <div className="dh-type">
                <span>普通门诊</span>张明 · 副主任医师
              </div>
            </div>
            <div className="dh-no">
              今日余号<b>12</b>
            </div>
          </div>
          <div className="dh-meta">
            <div>
              预计等候<b>25 分钟</b>
            </div>
            <div>
              就诊地点<b>{dept.location || '门诊楼 3F · A 区'}</b>
            </div>
            <div>
              挂号费<b>¥15</b>
            </div>
          </div>
        </div>

        <div className="sec-title">
          <h3>到院就诊的 7 个步骤</h3>
          <span className="line" />
          <span>共约 45 分钟</span>
        </div>

        <div className="timeline">
          {STEPS.map((step, index) => (
            <div className={`step ${step.state === 'done' ? 'done' : ''} ${step.state === 'now' ? 'now' : ''}`} key={step.title}>
              <div className="bullet">
                {step.state === 'done' ? (
                  <svg viewBox="0 0 24 24">
                    <path d="m5 12.5 4.5 4.5L19 7" />
                  </svg>
                ) : (
                  index + 1
                )}
              </div>
              <h4>
                {step.title}
                {step.state === 'done' && <span className="pill">已完成</span>}
                {step.state === 'now' && <span className="pill">进行中</span>}
              </h4>
              <p>{step.desc}</p>
              {step.where && (
                <span className="where">
                  <PinIcon />
                  {step.where}
                </span>
              )}
            </div>
          ))}
        </div>

        <div className="tipcard">
          <h5>
            <svg fill="none" height="12" stroke="#B4571F" strokeLinecap="round" strokeWidth="2" viewBox="0 0 24 24" width="12">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 8v5M12 16.2v.1" />
            </svg>
            到院前请准备
          </h5>
          <ul>
            <li>身份证、医保卡（电子医保凭证同样有效）</li>
            <li>近期检查报告、正在服用的药物清单</li>
            <li>建议提前 15 分钟到院，空腹项目请勿进食</li>
          </ul>
        </div>
      </div>

      <div className="detail-cta">
        <div className="cta-row">
          <div className="price">
            挂号费<b><small>¥</small>15</b>
          </div>
          <button className="btn primary disabled" onClick={onAppointment} type="button">
            立即预约挂号
          </button>
        </div>
      </div>
      <div className="homebar">
        <i />
      </div>
    </>
  );
}
