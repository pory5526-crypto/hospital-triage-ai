# 医院智能导诊 AI 客服 · V1

照着 PRD 做出来的可运行版本：**网页端（微信小程序 375×812 版式）+ Python 后端 + 大模型 + 院内知识库**。
前端像素级对齐墨刀原型（配色 `#0EA5A5` 青绿 / `#FF8557` 橙、卡片圆角、7 步时间线、声波装饰线都保留了）。

---

## 一、现在能跑什么

| 模块 | 状态 | 说明 |
|---|---|---|
| 文字 AI 问答 | ✅ | 流式逐字返回、多轮上下文、异常重试 |
| 智能分诊 | ✅ | 输出「智能分析结果」卡片：首选科室 + 备选科室 + 匹配度进度条 + 分析说明 |
| 语音输入 | ✅ | 浏览器原生识别，说完自动发送；不支持的浏览器会提示改用文字 |
| 文件上传 OCR | ✅ | 图片（拍照/相册）、PDF、Word → 识别文字 → 带进对话问答 |
| 知识库问答 | ✅ | 76 条院内知识（医保/楼层/检查须知/挂号/取药/住院/停车/发票…），未覆盖时明确说「不清楚」 |
| 急症分流 | ✅ | 11 类高危规则（胸痛、呼吸困难、大出血、意识障碍、卒中、严重外伤等），命中即中断分诊直达急诊，且**锁定后续对话** |
| 轻量转人工 | ✅ | 底部常驻入口 + 系统主动触发（连续两轮没听懂 / 超边界），弹窗展示电话与服务时间，可一键拨打 |
| 就诊流程页 | ✅ | 7 步时间线（已完成/进行中/待办三态）、科室信息卡、到院前准备、底部挂号栏置灰（点击提示线下挂号） |
| 金刚区 4 入口 | ⬜ 占位 | 点击提示「功能即将上线」，保持页面结构完整 |
| 科室选择浮层 / 预约挂号 / 报告解读 / 复诊提醒 | ⬜ 后置 | V2，代码里预留了 `FEATURE_*` 开关 |

---

## 二、30 秒跑起来

**方式一（推荐）**：双击项目根目录的 **`启动.bat`**
首次会自动建 Python 环境、装依赖、构建前端，然后把**本机和局域网两个访问地址**都打印出来并打开浏览器。

**方式二（手动）**：

```powershell
# 1. 后端
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy ..\.env.example .env
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. 前端（另开一个窗口，开发模式热更新）
cd frontend
npm install
npm run dev            # http://127.0.0.1:5173，已配好 /api 代理
```

> 不配大模型 Key 也能跑：自动降级为「规则分诊 + 知识库原文直出」模式，所有演示流程照常走。

### 让手机 / 同事的电脑也能打开

后端绑 `0.0.0.0`（`启动.bat` 已经是），启动后会打印 `http://<局域网IP>:8000`，同一 WiFi 下手机直接打开即可，页面会自动全屏、去掉手机壳。

**但 Windows 防火墙默认拦入站**（网络是「公用」时），需要管理员执行一次：

```powershell
New-NetFirewallRule -DisplayName "医院智能客服 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Any
```

执行完，手机访问 `http://192.168.5.79:8000`（换成启动时打印的那个 IP）就能用了。

---

## 三、接真实大模型

编辑 `backend/.env`，任选一家（都是 OpenAI 兼容协议，换家只改三行）：

```ini
# DeepSeek（推荐）
HOSPITAL_LLM_BASE_URL=https://api.deepseek.com/v1
HOSPITAL_LLM_API_KEY=sk-你的Key
HOSPITAL_LLM_MODEL=deepseek-chat
```

其它可选：

| 模型 | BASE_URL | MODEL |
|---|---|---|
| 通义千问（百炼 dashscope） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 千问 AI 平台（qianwenai.com） | `https://maas.qianwenaiapi.com/compatible-mode/v1` | `qwen3.8-flash` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| 本地 Ollama | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` |

> 千问平台的域名是 `maas.qianwen**aiapi**.com`，中间多一个 `api`，写成 `maas.qianwenai.com` 会直接解析失败（NXDOMAIN）。

配置好重启后端，访问 `http://127.0.0.1:8000/api/health` 看 `llm.configured` 是否为 `true`。

**接上模型后会发生什么变化：**

- 分诊卡片仍然由**规则引擎**算（科室、匹配度是确定性的，模型改不了，保证不发散、可复现）；
- 模型负责把它**说成人话**、回答知识库问答、流式吐字；
- 结构化查询（"心内科在几楼""周四谁出诊"）走 **Function Call**，模型自己决定调哪个工具；
- 回答受系统提示词强约束：不许下诊断、不许开药、知识库没有就说不知道。

---

## 四、项目结构

```
医院智能客服项目/
├─ 启动.bat / start.ps1          ← 一键启动
├─ Dockerfile / docker-compose.yml
├─ .env.example                  ← 所有可配置项
│
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 ← FastAPI 路由（对话流/上传/配置/埋点）
│  │  ├─ pipeline.py             ← 对话编排：急症→转人工→边界→分诊/知识库
│  │  ├─ triage.py               ← 分诊打分引擎
│  │  ├─ emergency.py            ← 急症规则（带否定词识别）
│  │  ├─ rag.py                  ← 中文二元组 + BM25 检索
│  │  ├─ tools.py                ← Function Call 工具 + 确定性兜底路由
│  │  ├─ llm.py                  ← OpenAI 兼容流式客户端
│  │  ├─ ocr.py                  ← 图片/PDF/Word 解析
│  │  ├─ session.py / telemetry.py / store.py / config.py
│  │  └─ data/                   ← ★ 所有业务数据都是 JSON，改完 /api/admin/reload 热加载
│  │     ├─ departments.json     ← 32 个科室 + 楼层分布
│  │     ├─ triage_rules.json    ← 47 条症状→科室加权规则
│  │     ├─ emergency_rules.json ← 11 条急症规则
│  │     ├─ knowledge.json       ← 76 条院内知识
│  │     ├─ doctors.json         ← 30 位医生出诊表
│  │     └─ persona.md           ← ★ 系统提示词（改完热生效）
│  ├─ scripts/
│  │  ├─ smoke_test.py           ← 13 个对话场景冒烟测试
│  │  └─ test_upload.py          ← 上传/OCR 测试
│  └─ requirements.txt / requirements-ocr.txt
│
├─ frontend/                     ← 网页版（React + Vite）
│  └─ src/
│     ├─ App.tsx                 ← 页面路由 + 弹层/上传
│     ├─ components/             ← 对话页、流程页、分析卡、急症卡、转人工弹窗…
│     ├─ hooks/useChat.ts        ← SSE 流式解析
│     ├─ hooks/useSpeech.ts      ← 语音识别
│     └─ styles/app.css          ← 从原型搬过来的全部样式
│
├─ miniprogram/                  ← 微信小程序（原生，无构建）
│  ├─ app.js / app.json / app.wxss
│  ├─ base.wxss                  ← 由 app.css 自动转换生成
│  ├─ assets/ecg.png             ← 心电波形装饰线
│  ├─ pages/chat/                ← 对话主页
│  ├─ pages/flow/                ← 就诊流程页
│  └─ utils/                     ← 请求 / 流式解析 / 配置
│
└─ scripts/                      ← wxss 转换、图标生成
```

---

## 五、换一家医院 / 改内容

**不需要改代码**，只改 `backend/app/data/` 下的 JSON：

1. `departments.json` 里的 `hospital` 段改医院名、地址、电话、楼层分布；
2. `knowledge.json` 换成这家医院真实的医保政策、检查须知（格式：`title` + `content` + `keywords`）；
3. `doctors.json` 换成真实出诊表；
4. `backend/.env` 里改 `HOSPITAL_NAME` / `HOSPITAL_TRIAGE_PHONE` 等；
5. 改完调一下 `POST /api/admin/reload`，或重启后端。

分诊规则 `triage_rules.json` 是 `关键词 → {科室: 权重}` 的结构，加一条就是加一条数组元素，权重的相对大小决定匹配度百分比。

---

## 六、系统提示词（不用改代码）

提示词单独放在 **`backend/app/data/persona.md`**，按医院配置渲染后发给模型。改完**立刻生效**，不用重启（按文件改动时间自动重载）。

三种改法：

1. 直接编辑 `backend/app/data/persona.md`；
2. `GET /api/admin/prompt` 读当前生效的全文，`PUT /api/admin/prompt` 直接覆盖（body: `{"text": "..."}`）；
3. 调 `POST /api/admin/reload` 强制刷新。

`persona.md` 里可以写 `{hospital}`、`{triage_phone}`、`{emergency_phone}`、`{service_hours}` 占位符，运行时替换成 `.env` 里的值。

里面写了什么（这块是合规的核心，别随便删）：

- **能力三件事**：症状→科室、流程位置、院内规则；其余一律不接
- **六条红线**：不下诊断 / 不判轻重 / 不给用药 / 不predict预后 / 不解读报告 / 不编造院内信息
- **越界话术模板**：说明不做什么 → 给一个能做的替代 → 给电话
- **语气长度**：分诊引导语 ≤40 字，知识库回答 ≤120 字，一次只给一个动作
- **有情绪时**：先认情绪再给去处，不辩解不背规定
- **few-shot 示例**：6 组标准问答，把"该长什么样"直接示范给模型
- **兜底原则**：不确定就少说，宁可说查不到

安全性由**三层**共同保证，不靠提示词单打独斗：

| 层 | 负责 | 例子 |
|---|---|---|
| 规则引擎（代码） | 硬拦截 | 急症 11 类关键词命中即转急诊并锁定会话；问药/问诊断/问预后命中关键词直接返回固定话术 |
| 系统提示词 | 软约束 | 词表覆盖不到的问法（"你就说严不严重"、越狱改身份）由模型自己守住 |
| 输出后处理 | 兜底 | 分诊卡片内容由规则引擎生成，模型无权改科室与匹配度 |

---

## 七、技术方案（对齐 PRD 五·5）

| PRD 要求 | 本项目实现 |
|---|---|
| RAG 检索增强（必上） | 中文二元组切分 + BM25，零依赖、可离线；`rag.py` 里预留了换 Milvus/Qdrant 的接口 |
| Function Call（必上） | `tools.py` 定义 4 个工具（科室位置、出诊表、楼层分布、知识检索），模型自主调用；模型不可用时走确定性路由兜底 |
| Agent（V2） | 未上，V1 用「提示词 + 函数调用」即可满足 |
| 多模态（V3） | 未上，V1 只做 OCR 文字提取 |
| 前端 uni-app / Vue3 | 这里是 **React + Vite + TS**（浏览器可直接演示）；业务逻辑与样式已分层，迁到 uni-app 只需替换视图层（见下方「已知差异」） |
| 后端 FastAPI | ✅ 就是 FastAPI |
| 向量库 Milvus/Qdrant | V1 用 BM25，数据量上来后替换 `rag.py` 的 `KnowledgeBase` 即可 |
| OCR PaddleOCR | 用 RapidOCR（ONNX，同属开源、轻量、可内网部署），装不上会自动降级提示 |
| ASR | V1 用浏览器原生识别；正式环境接内网 ASR 只需替换 `useSpeech.ts` |

---

## 八、小程序端

`miniprogram/` 是**原生小程序**（WXML/WXSS/JS），没有用 Taro/uni-app，也没有构建步骤——用微信开发者工具直接打开就能跑。整个包 **78 KB**，离 2MB 主包限制很远。

### 怎么打开

1. 打开**微信开发者工具**，用微信扫码登录
2. 点左上角 **「+」→ 导入项目**
3. 目录选到 `E:\Desktop\医院智能客服项目\miniprogram`
4. AppID 选 **「测试号」**（没有企业 AppID 时用这个）
5. 确定，模拟器里就能看到小程序

后端要先起来（`启动.bat`），模拟器直接连 `http://127.0.0.1:8000`。

> `project.config.json` 里已经把 `urlCheck` 关掉了，所以模拟器可以直接请求本地 http 地址，不用配域名白名单。

### 和网页版的差异

| 项 | 网页版 | 小程序端 |
|---|---|---|
| 导航栏 | 自己画的，含模拟胶囊 | **原生胶囊 + 自定义导航栏**（`navigationStyle: custom`） |
| 流式返回 | `fetch` + `ReadableStream` | `wx.request` + **`enableChunked` + `onChunkReceived`**，UTF-8 分块自己拼 |
| 中文分块 | 浏览器帮解 | 自带增量 UTF-8 解码器，处理一个汉字被切成两半 |
| 语音输入 | `MediaRecorder` 录音 → `POST /api/asr` | `RecorderManager` 录音 → `POST /api/asr`，同一个后端接口 |
| 上传 | `FormData` | 图片 `wx.chooseMedia`、文档 `wx.chooseMessageFile`、`wx.uploadFile` |
| 打电话 | `<a href="tel:">` | `wx.makePhoneCall` |
| 键盘遮挡 | 浏览器自动 | 监听 `onKeyboardHeightChange` 手动顶起输入框 |

**语音**：两端都是「录音 → 上传 `POST /api/asr` → 千问 `qwen-audio-3.1-asr-flash` 转文字 → 自动发送」，用的是同一个 Key，不用额外部署。

> ⚠️ **浏览器限制**：麦克风只在 **HTTPS 或 localhost** 下开放。手机上用 `http://192.168.x.x:8000` 打开网页时，浏览器会直接禁止录音——页面会明确提示，不会假装在听。手机端要试语音，用小程序版；网页端语音请在本机 `http://127.0.0.1:8000` 或部署成 https 后使用。

### 真机预览

模拟器用的是 `127.0.0.1`，真机要用电脑的局域网 IP：

1. 改 `miniprogram/utils/config.js` 里的 `BASE_URL`，例如 `http://192.168.1.8:8000`
2. 后端用 `--host 0.0.0.0` 启动
3. 手机和电脑连同一个 WiFi，开发者工具点「预览」扫码

### 样式怎么来的

`app.wxss` 里 `@import "base.wxss"`，而 `base.wxss` 是 `scripts/build-wxss.js` 从 `frontend/src/styles/app.css` **自动转换**的（px→rpx、去掉 @media/hover/桌面外壳）。所以改视觉只改网页那份 CSS，再跑一次：

```bash
node scripts/build-wxss.js
```

小程序特有的结构（导航栏、图标、时间线等）写在 `app.wxss` 和两个页面的 `index.wxss` 里。

---

## 九、接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查（科室数、知识库条数、LLM 状态） |
| GET | `/api/config` | 前端初始化配置（医院信息、欢迎语、功能开关） |
| POST | `/api/session` | 创建会话 |
| POST | `/api/chat/stream` | **主接口**，SSE 流式返回 |
| POST | `/api/upload` | 文件上传 + OCR，返回识别文字 |
| GET | `/api/kb/search?q=` | 知识库检索（调参用） |
| GET | `/api/metrics/summary` | 埋点汇总（会话数/分诊数/急症数/转人工率） |
| POST | `/api/admin/reload` | 热加载 JSON 数据与 persona.md |
| GET | `/api/admin/prompt` | 查看当前生效的系统提示词 |
| PUT | `/api/admin/prompt` | 替换系统提示词（立即生效） |
| GET | `/api/llm/health` | 模型连通性 |

**SSE 事件格式**（每行 `data: {json}`）：

```jsonc
{"type":"meta","sessionId":"..."}
{"type":"delta","text":"增量文字"}          // 逐字拼接
{"type":"card","card":{...}}                // 分诊卡 / 急症卡
{"type":"segment_end"}                      // 结束当前气泡，后续 delta 另起一条
{"type":"handoff","handoff":{...}}          // 弹出转人工弹窗
{"type":"done","latencyMs":1234}
{"type":"error","message":"...","silent":true}
```

---

## 十、埋点（PRD 六·1 的五类基础埋点）

后端自动写 `backend/runtime/logs/events-YYYY-MM-DD.jsonl`，一行一个事件：

| 事件 | 触发时机 |
|---|---|
| `session_start` / `session_end` | 会话开始 / 结束 |
| `message_sent` | 患者发消息（含是否带文件） |
| `triage_shown` | 展示分诊卡片（推荐科室、置信度、备选） |
| `emergency_triggered` | 命中急症规则（命中关键词） |
| `handoff` | 触发转人工（含原因） |
| `error` | 超时 / 接口异常 / 降级 |

随时看汇总：`GET /api/metrics/summary`。

---

## 十一、部署

```bash
# Docker（推荐）
cp .env.example .env      # 填 Key
docker compose up -d --build
# → http://服务器IP:8000
```

或直接跑：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000    # 在 backend 目录下
```

正式上线前记得：`HOSPITAL_CORS_ORIGINS` 写死域名、开机密鉴权、数据切到内网部署（PRD 六·2 的上线前置条件）。

---

## 十二、自测与验收

```powershell
cd backend
.venv\Scripts\python.exe scripts\acceptance_check.py  # ★ 上线前验收：5 组指标 → docs/验收报告.md
.venv\Scripts\python.exe scripts\diag_rules.py        # 只跑规则层（秒级，调规则时用）
.venv\Scripts\python.exe scripts\smoke_test.py        # 13 个对话场景（分诊/急症/知识库/工具/转人工）
.venv\Scripts\python.exe scripts\test_safety.py       # 14 个安全边界刁难测试（需配好模型）
.venv\Scripts\python.exe scripts\test_upload.py       # 上传 / OCR / 异常
```

`acceptance_check.py` 会跑 47 条分诊 + 20 条急症 + 10 条安全 + 8 条幻觉 + 多轮上下文，统计首字/完整响应时长，最后把结论写进 **`docs/验收报告.md`**。

**当前实测（2026-11-06）**

| 指标 | 目标 | 实测 | 状态 |
|---|---|---|---|
| 分诊准确率 | ≥ 85% | 100%（47/47） | ✅ |
| 急症识别率 | 100% | 100%（20/20） | ✅ |
| 安全边界 | 100% | 100%（10/10） | ✅ |
| 知识库外不编造 | ≥ 90% | 100%（8/8） | ✅ |
| 首字响应 | ≤ 2s | P95 1355 ms | ✅ |
| 完整回复 | ≤ 5s | P95 1762 ms | ✅ |

完整清单（含未完成项与放行条件）见 **[docs/上线前验收清单.md](docs/上线前验收清单.md)**。

> 分诊 100% 是在我构造的 47 条上跑出来的，样本小。PRD 要求数百条真实用例，上线前必须扩规模重跑。

### 调规则的两个快捷入口

- `node scripts/build-wxss.js` —— 网页 CSS → 小程序 WXSS
- `scripts/diag_rules.py --reload` —— 改完 `data/*.json` 秒级验证规则，不用起 HTTP

---

## 十三、已知差异与 V2 待办

| 项 | 说明 |
|---|---|
| 技术栈 | PRD 写 uni-app/Vue3，这里是 React。样式与业务已分离，迁小程序时视图层重写、`hooks/useChat.ts` 换成 `wx.request` 分块即可，后端一行不用改 |
| 就诊流程页数据 | V1 静态展示（PRD 也是这么定的），科室名/位置会跟着分诊结果变，余号医生是示例数据 |
| 语音 | 依赖浏览器识别，微信内置浏览器部分机型不支持；V2 换内网 ASR |
| 会话存储 | 内存 + TTL，重启即清空；V2 接 Redis |
| 鉴权 | 无登录态，V2 接医院微信授权 |
| 截图/演示参数 | `?q=患者问题` 自动发一条（方便截图）、`?view=flow` 直接看流程页 |

---

## 十四、和 PRD 的对照说明

- **V1 范围**：严格按 2026-11-06 那版收敛后的范围做的，预约挂号 / 科室浮层 / 报告解读 / 复诊提醒都没做，但入口都在（点击提示「即将上线」），符合 PRD「后置功能不删入口」。
- **分诊卡片**：按 PRD 隐藏了「更换科室」按钮（V2 随浮层上线）。想让它出现，把 `backend/.env` 里 `HOSPITAL_FEATURE_DEPT_SHEET=true` 打开，前端会渲染这个按钮。
- **急症规则不可被覆盖**：命中一次后，该会话后续消息持续引导急诊（PRD 五·3）。
- **统一免责话术**：`config.py` 里的 `DISCLAIMER`，分诊卡片与转人工弹窗都会带上。
