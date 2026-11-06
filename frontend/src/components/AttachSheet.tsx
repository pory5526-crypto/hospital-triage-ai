import { useRef } from 'react';

interface Props {
  accept: string;
  maxMb: number;
  onFile: (file: File) => void;
  onClose: () => void;
}

export function AttachSheet({ accept, maxMb, onFile, onClose }: Props) {
  const imageRef = useRef<HTMLInputElement>(null);
  const docRef = useRef<HTMLInputElement>(null);

  const handle = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) {
      onFile(file);
      onClose();
    }
  };

  return (
    <>
      <div className="mask" onClick={onClose} />
      <div className="sheet">
        <div className="grab" />
        <div className="sheet-head">
          <div>
            <h3>上传资料</h3>
            <p>支持病历、药单、检查单，单个文件不超过 {maxMb}MB</p>
          </div>
          <button className="close" onClick={onClose} aria-label="关闭">
            <svg fill="none" viewBox="0 0 24 24">
              <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="attach-grid">
          <button
            className="attach-item"
            type="button"
            onClick={() => imageRef.current?.click()}
          >
            <span className="ai">
              <svg viewBox="0 0 24 24">
                <path d="M3.5 7.5h3l1.5-2h8l1.5 2h3v11h-17z" />
                <circle cx="12" cy="12.5" r="3.6" />
              </svg>
            </span>
            <b>拍照 / 相册</b>
            <small>病历本、药盒、检查单</small>
          </button>

          <button className="attach-item" type="button" onClick={() => docRef.current?.click()}>
            <span className="ai">
              <svg viewBox="0 0 24 24">
                <path d="M6 3.5h8.5L19 8v12.5H6z" />
                <path d="M14 3.5V8h5" />
              </svg>
            </span>
            <b>上传文档</b>
            <small>PDF / Word 检查报告</small>
          </button>

          <button className="attach-item" type="button" onClick={onClose}>
            <span className="ai">
              <svg viewBox="0 0 24 24">
                <path d="M4 12a8 8 0 1 1 8 8H4v-4" />
              </svg>
            </span>
            <b>暂不上传</b>
            <small>直接用文字描述</small>
          </button>
        </div>

        <p className="attach-note">
          文件仅用于本次导诊识别，不会外发到第三方。V1 不支持视频与旧版 .doc 格式。
        </p>

        <input ref={imageRef} type="file" accept="image/*" hidden onChange={handle} />
        <input
          ref={docRef}
          type="file"
          accept=".pdf,.docx,.doc,application/pdf"
          hidden
          onChange={handle}
        />
      </div>
    </>
  );
}
