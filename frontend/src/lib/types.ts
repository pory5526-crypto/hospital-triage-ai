export interface TriageItem {
  dept: string;
  match: number;
  label: string;
  location?: string;
}

export interface TriageCard {
  type: 'triage';
  primary: TriageItem;
  alternatives: TriageItem[];
  note: string;
  matched: string[];
  population: string | null;
  confidence?: number;
}

export interface EmergencyCard {
  type: 'emergency';
  label: string;
  keyword: string;
  title: string;
  advice: string;
  location: string;
  phone: string;
  route: string[];
  disclaimer: string;
}

export type Card = TriageCard | EmergencyCard;

export interface ChatFile {
  name: string;
  status: 'uploading' | 'done' | 'error';
  note?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  card?: Card;
  file?: ChatFile;
  chips?: string[];
  streaming?: boolean;
}

export interface HospitalConfig {
  name: string;
  address: string;
  triagePhone: string;
  emergencyPhone: string;
  serviceHours: string;
  afterHoursTip: string;
  outpatientHours: string;
}

export interface WelcomeConfig {
  text: string;
  hospital: string;
  subtitle: string;
  chips: string[];
  disclaimer: string;
}

export interface ClientConfig {
  hospital: HospitalConfig;
  welcome: WelcomeConfig;
  disclaimer: string;
  features: {
    deptSheet: boolean;
    appointment: boolean;
    reportReading: boolean;
    reminder: boolean;
  };
  upload: { maxMb: number; accept: string };
  quickActions: string[];
  entries: string[];
}

export interface HandoffInfo {
  reason: string;
  phone: string;
  hours: string;
  afterHoursTip: string;
  title: string;
}

export type StreamEvent =
  | { type: 'meta'; sessionId: string }
  | { type: 'delta'; text: string }
  | { type: 'card'; card: Card }
  | { type: 'segment_end' }
  | { type: 'handoff'; handoff: HandoffInfo }
  | { type: 'done'; latencyMs: number }
  | { type: 'error'; message: string; silent?: boolean };

export interface UploadResult {
  ok: boolean;
  fileName: string;
  text: string;
  chars?: number;
  error: string | null;
  hint?: string;
}
