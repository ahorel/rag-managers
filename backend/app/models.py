from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class AnalyzeRequest(BaseModel):
    mission_text: str = Field(..., min_length=20)
    required_availability: Optional[str] = None
    priority_skills: list[str] = []
    max_results: int = Field(default=10, ge=3, le=20)
    filter_domain: Optional[str] = None
    filter_location: Optional[str] = None
    filter_remote: Optional[str] = None
    filter_languages: list[str] = []
    filter_intercontrat_only: bool = False


class RewrittenOffer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    mission_type: str = ""
    duration: str = ""
    technical_skills: list[str] = []
    soft_skills: list[str] = []
    client_context: str = ""
    start_date: Optional[str] = None
    location: Optional[str] = None
    remote: Optional[str] = None
    languages: list[str] = []
    domain: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sanitize(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        str_fields = ("title", "mission_type", "duration", "client_context")
        list_fields = ("technical_skills", "soft_skills", "languages")
        # Valeurs placeholder que le LLM renvoie parfois litteralement
        _PLACEHOLDERS = {"softskill1", "softskill2", "compétence1", "compétence2",
                         "null", "none", "n/a", "na"}
        for f in str_fields:
            if data.get(f) is None:
                data[f] = ""
        for f in list_fields:
            val = data.get(f)
            if val is None:
                data[f] = []
            elif isinstance(val, list):
                data[f] = [v for v in val if isinstance(v, str) and v.lower() not in _PLACEHOLDERS]
        return data


class ScoreDetail(BaseModel):
    skills: int
    domain: int
    availability: int
    location: int


class ConsultantMatch(BaseModel):
    id: str
    name: str
    title: str
    score: int
    matched_skills: list[str]
    missing_skills: list[str]
    explanation: str
    available: bool
    cv_filename: str
    availability_date: Optional[str] = None
    location: Optional[str] = None
    remote: Optional[str] = None
    languages: list[str] = []
    domains: list[str] = []
    status: Optional[str] = None
    email: Optional[str] = None
    score_detail: Optional[ScoreDetail] = None


class AnalyzeResponse(BaseModel):
    rewritten_offer: RewrittenOffer
    consultants: list[ConsultantMatch]
    total_cvs: int


class HealthResponse(BaseModel):
    status: str
    cvs_loaded: int
    model_ready: bool


class SendResultsRequest(BaseModel):
    offer: RewrittenOffer
    consultants: list[ConsultantMatch]
    extra_recipients: list[str] = []


class SendResultsResponse(BaseModel):
    success: bool
    message: str
    recipients: list[str]


class EmailConfig(BaseModel):
    recipients: list[str] = []
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    sender_email: str = "matchconsult@orange.com"
    sender_name: str = "MatchConsult"


class AppConfig(BaseModel):
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    anthropic_api_key: str = ""
    domain_list: list[str] = [
        "industrie", "telecom", "innovation", "mobilite", "finance", "assurance"
    ]
    domain_similar: dict[str, list[str]] = {
        "finance":    ["assurance"],
        "assurance":  ["finance"],
        "telecom":    ["innovation"],
        "innovation": ["telecom"],
        "industrie":  ["mobilite"],
        "mobilite":   ["industrie"],
    }


class AdminConfig(BaseModel):
    app: AppConfig
    email: EmailConfig
