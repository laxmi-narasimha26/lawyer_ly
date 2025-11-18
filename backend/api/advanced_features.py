"""
Advanced Features API Endpoints
Exposes all new functionality through REST API
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel
import structlog

from services.web_search_service import web_search_service
from services.voice_service import voice_service
from services.smart_contract_analyzer import smart_contract_analyzer
from services.predictive_analytics import predictive_analytics
from services.legal_brief_generator import legal_brief_generator
from services.file_format_handler import file_format_handler
from services.export_service import export_service, ExportOptions
from services.multilanguage_service import multilanguage_service
from services.collaboration_service import collaboration_service
from services.billing_service import billing_service
from services.compliance_service import compliance_service
from services.client_portal_service import client_portal_service
from services.integrations_service import integrations_service
from services.knowledge_base_service import knowledge_base_service
from core.multi_document_analyzer import multi_doc_analyzer
from core.memory_system import unified_memory

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/advanced", tags=["Advanced Features"])


# ==================== WEB SEARCH ====================

class WebSearchRequest(BaseModel):
    query: str
    num_results: int = 10
    include_legal_databases: bool = True


@router.post("/search/web")
async def search_web(request: WebSearchRequest):
    """Perform web search"""
    results = await web_search_service.search_web(
        query=request.query,
        num_results=request.num_results
    )
    return {"results": results}


@router.post("/search/deep-research")
async def deep_research(request: WebSearchRequest):
    """Perform comprehensive deep research"""
    results = await web_search_service.deep_research(
        query=request.query,
        include_web=True,
        include_indian_legal=request.include_legal_databases,
        include_international=False
    )
    return results


# ==================== VOICE ====================

@router.post("/voice/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("en"),
    legal_context: bool = Form(True)
):
    """Transcribe audio to text"""
    audio_data = await audio.read()
    result = await voice_service.transcribe_audio(
        audio_data=audio_data,
        audio_format=audio.filename.split('.')[-1],
        language=language,
        legal_context=legal_context
    )
    return result


@router.post("/voice/synthesize")
async def synthesize_speech(
    text: str = Form(...),
    voice_id: str = Form("default")
):
    """Convert text to speech"""
    audio_data = await voice_service.synthesize_speech(
        text=text,
        voice_id=voice_id
    )
    return StreamingResponse(
        iter([audio_data]),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "attachment; filename=speech.mp3"}
    )


# ==================== SMART CONTRACTS ====================

class SmartContractRequest(BaseModel):
    contract_code: str
    contract_name: Optional[str] = None


@router.post("/smart-contract/analyze")
async def analyze_smart_contract(request: SmartContractRequest):
    """Analyze Solidity smart contract"""
    result = await smart_contract_analyzer.analyze_solidity_contract(
        contract_code=request.contract_code,
        contract_name=request.contract_name
    )
    return result


# ==================== PREDICTIVE ANALYTICS ====================

class CasePredictionRequest(BaseModel):
    case_type: str
    jurisdiction: str
    case_details: Dict[str, Any]


@router.post("/analytics/predict-outcome")
async def predict_case_outcome(request: CasePredictionRequest):
    """Predict case outcome using analytics"""
    prediction = await predictive_analytics.predict_case_outcome(
        case_type=request.case_type,
        jurisdiction=request.jurisdiction,
        case_details=request.case_details
    )
    return prediction


@router.get("/analytics/success-patterns/{case_type}/{jurisdiction}")
async def get_success_patterns(case_type: str, jurisdiction: str):
    """Get success patterns for case type"""
    patterns = await predictive_analytics.analyze_success_patterns(
        case_type=case_type,
        jurisdiction=jurisdiction
    )
    return {"patterns": patterns}


# ==================== LEGAL BRIEF GENERATOR ====================

class BriefGenerationRequest(BaseModel):
    template_id: str
    case_details: Dict[str, Any]
    style: str = "formal"


@router.post("/brief/generate")
async def generate_legal_brief(request: BriefGenerationRequest):
    """Generate legal brief from template"""
    brief = await legal_brief_generator.generate_brief(
        template_id=request.template_id,
        case_details=request.case_details,
        style=request.style
    )
    return brief


@router.get("/brief/templates")
async def list_brief_templates(jurisdiction: Optional[str] = None):
    """List available brief templates"""
    templates = legal_brief_generator.list_templates(jurisdiction=jurisdiction)
    return {"templates": templates}


# ==================== FILE FORMAT SUPPORT ====================

@router.get("/files/supported-formats")
async def get_supported_formats():
    """Get list of supported file formats"""
    formats = file_format_handler.list_supported_formats()
    return {
        "total_formats": len(formats),
        "formats": formats,
        "categories": file_format_handler.get_categories()
    }


# ==================== EXPORT SERVICE ====================

class ExportRequest(BaseModel):
    content: Dict[str, Any]
    format: str
    include_citations: bool = True
    firm_branding: Optional[Dict[str, Any]] = None


@router.post("/export")
async def export_document(request: ExportRequest):
    """Export document in specified format"""
    options = ExportOptions(
        format=request.format,
        include_citations=request.include_citations,
        firm_branding=request.firm_branding
    )

    result = await export_service.export_document(
        content=request.content,
        options=options
    )

    return StreamingResponse(
        iter([result.content]),
        media_type=f"application/{request.format}",
        headers={
            "Content-Disposition": f"attachment; filename={result.filename}"
        }
    )


# ==================== MULTI-LANGUAGE ====================

@router.get("/language/supported")
async def get_supported_languages():
    """Get supported languages"""
    languages = multilanguage_service.get_supported_languages()
    return {"languages": languages}


class TranslationRequest(BaseModel):
    text: str
    source_lang: str
    target_lang: str


@router.post("/language/translate")
async def translate_text(request: TranslationRequest):
    """Translate text"""
    translated = await multilanguage_service.translate_text(
        text=request.text,
        source_lang=request.source_lang,
        target_lang=request.target_lang
    )
    return {"translated_text": translated}


# ==================== MULTI-DOCUMENT ANALYSIS ====================

class MultiDocAnalysisRequest(BaseModel):
    document_ids: List[str]
    analysis_depth: str = "standard"


@router.post("/documents/multi-analyze")
async def analyze_multiple_documents(
    request: MultiDocAnalysisRequest,
    session=None  # Would inject database session
):
    """Analyze multiple documents together"""
    result = await multi_doc_analyzer.analyze_multiple_documents(
        document_ids=request.document_ids,
        session=session,
        analysis_depth=request.analysis_depth
    )
    return result


# ==================== COLLABORATION ====================

class CreateSessionRequest(BaseModel):
    document_id: str
    user_id: str


@router.post("/collaboration/session/create")
async def create_collaboration_session(request: CreateSessionRequest):
    """Create collaboration session"""
    session = await collaboration_service.create_session(
        document_id=request.document_id,
        user_id=request.user_id
    )
    return session


@router.get("/collaboration/sessions")
async def get_active_sessions(user_id: Optional[str] = None):
    """Get active collaboration sessions"""
    sessions = collaboration_service.get_active_sessions(user_id=user_id)
    return {"sessions": sessions}


# ==================== BILLING & TIME TRACKING ====================

class StartTimerRequest(BaseModel):
    user_id: str
    client_id: str
    case_id: str
    activity_type: str
    description: str = ""


@router.post("/billing/timer/start")
async def start_timer(request: StartTimerRequest):
    """Start time tracking"""
    result = await billing_service.start_timer(**request.dict())
    return result


@router.post("/billing/timer/stop/{user_id}/{case_id}")
async def stop_timer(user_id: str, case_id: str):
    """Stop timer and create entry"""
    entry = await billing_service.stop_timer(user_id, case_id)
    return entry


@router.get("/billing/entries")
async def get_time_entries(
    user_id: Optional[str] = None,
    case_id: Optional[str] = None,
    unbilled_only: bool = False
):
    """Get time entries"""
    entries = billing_service.get_time_entries(
        user_id=user_id,
        case_id=case_id,
        unbilled_only=unbilled_only
    )
    return {"entries": entries}


# ==================== COMPLIANCE & DEADLINES ====================

class DeadlineRequest(BaseModel):
    case_id: str
    title: str
    deadline_type: str
    due_date: datetime
    priority: str
    description: str
    assigned_to: List[str]


@router.post("/compliance/deadline/add")
async def add_deadline(request: DeadlineRequest):
    """Add deadline"""
    deadline = await compliance_service.add_deadline(**request.dict())
    return deadline


@router.get("/compliance/deadlines/upcoming")
async def get_upcoming_deadlines(days_ahead: int = 30):
    """Get upcoming deadlines"""
    deadlines = compliance_service.get_upcoming_deadlines(days_ahead=days_ahead)
    return {"deadlines": deadlines}


@router.get("/compliance/deadlines/overdue")
async def get_overdue_deadlines():
    """Get overdue deadlines"""
    deadlines = compliance_service.get_overdue_deadlines()
    return {"deadlines": deadlines}


@router.get("/compliance/status")
async def get_compliance_status():
    """Get compliance status"""
    status = compliance_service.get_compliance_status()
    return status


# ==================== CLIENT PORTAL ====================

class CreatePortalAccessRequest(BaseModel):
    client_id: str
    client_email: str
    case_ids: List[str]
    permissions: Optional[List[str]] = None


@router.post("/portal/access/create")
async def create_portal_access(request: CreatePortalAccessRequest):
    """Create client portal access"""
    access = await client_portal_service.create_client_access(**request.dict())
    return access


@router.get("/portal/dashboard/{client_id}")
async def get_client_dashboard(client_id: str):
    """Get client portal dashboard"""
    dashboard = await client_portal_service.get_client_dashboard(client_id)
    return dashboard


# ==================== INTEGRATIONS ====================

@router.get("/integrations/providers")
async def get_integration_providers():
    """Get supported integration providers"""
    providers = integrations_service.get_supported_providers()
    return {"providers": providers}


@router.get("/integrations/list")
async def list_integrations():
    """List configured integrations"""
    integrations = integrations_service.list_integrations()
    return {"integrations": integrations}


# ==================== KNOWLEDGE BASE ====================

class AddKnowledgeEntryRequest(BaseModel):
    title: str
    category: str
    jurisdiction: str
    practice_area: str
    content: str
    tags: List[str]
    author_id: str


@router.post("/knowledge-base/add")
async def add_knowledge_entry(request: AddKnowledgeEntryRequest):
    """Add knowledge base entry"""
    entry = await knowledge_base_service.add_entry(**request.dict())
    return entry


@router.get("/knowledge-base/search")
async def search_knowledge_base(
    query: Optional[str] = None,
    category: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    practice_area: Optional[str] = None
):
    """Search knowledge base"""
    results = await knowledge_base_service.search_entries(
        query=query,
        category=category,
        jurisdiction=jurisdiction,
        practice_area=practice_area
    )
    return {"results": results}


@router.get("/knowledge-base/entry/{entry_id}")
async def get_knowledge_entry(entry_id: str):
    """Get knowledge base entry"""
    entry = await knowledge_base_service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


logger.info("Advanced Features API initialized with all endpoints")
