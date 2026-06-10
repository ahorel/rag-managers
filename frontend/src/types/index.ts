export interface AnalyzeRequest {
  mission_text: string;
  required_availability?: string;
  priority_skills?: string[];
  max_results?: number;
  filter_domain?: string;
  filter_location?: string;
  filter_remote?: string;
  filter_languages?: string[];
  filter_intercontrat_only?: boolean;
}

export interface RewrittenOffer {
  title: string;
  mission_type: string;
  duration: string;
  technical_skills: string[];
  soft_skills: string[];
  client_context: string;
  start_date?: string | null;
  location?: string | null;
  remote?: string | null;
  languages?: string[];
  domain?: string | null;
}

export interface ScoreDetail {
  skills: number;
  domain: number;
  availability: number;
  location: number;
}

export interface ConsultantMatch {
  id: string;
  name: string;
  title: string;
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  explanation: string;
  available: boolean;
  cv_filename: string;
  availability_date?: string | null;
  location?: string | null;
  remote?: string | null;
  languages?: string[];
  domains?: string[];
  status?: string | null;
  email?: string | null;
  score_detail?: ScoreDetail | null;
}

export interface AnalyzeResponse {
  rewritten_offer: RewrittenOffer;
  consultants: ConsultantMatch[];
  total_cvs: number;
}

export interface SendResultsRequest {
  offer: RewrittenOffer;
  consultants: ConsultantMatch[];
  extra_recipients?: string[];
}

export interface SendResultsResponse {
  success: boolean;
  message: string;
  recipients: string[];
}

export interface EmailConfig {
  recipients: string[];
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password: string;
  sender_email: string;
  sender_name: string;
}

export interface AppConfig {
  groq_api_key: string;
  groq_model: string;
  anthropic_api_key: string;
  domain_list: string[];
  domain_similar: Record<string, string[]>;
}

export interface AdminConfig {
  app: AppConfig;
  email: EmailConfig;
}
