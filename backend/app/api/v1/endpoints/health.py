from fastapi import APIRouter
from datetime import datetime
from pydantic import BaseModel
import json
import urllib.error
import urllib.request
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


class ChatRequest(BaseModel):
    message: str = ''
    app: str = 'FORJA'
    context: str = ''


def utc_timestamp():
    return datetime.utcnow().isoformat() + 'Z'


def health_payload():
    return {
        'status': 'ok',
        'service': 'forja-backend',
        'app': settings.APP_NAME,
        'version': settings.APP_VERSION,
        'environment': settings.APP_ENV,
        'auth': 'configured' if settings.auth_configured else 'not_configured',
        'production_ready': settings.APP_ENV == 'production',
        'modules': {
            'backend': 'active',
            'auth': 'configured' if settings.auth_configured else 'not_configured',
            'runtime': 'active',
            'provenance': 'active',
            'traceability': 'metadata_only',
        },
        'timestamp': utc_timestamp(),
    }


def runtime_payload():
    return {
        'status': 'OPERATIONAL',
        'mode': 'metadata-only',
        'deploy_allowed': False,
        'freeze_allowed': False,
        'message': 'FORJA local runtime is available. Build execution, deploy, freeze and provider actions remain blocked until explicit backend actions are connected.',
        'snapshot': {
            'mode': 'metadata-only',
            'deployAllowed': False,
            'metrics': [
                {
                    'label': 'Apps en construccion',
                    'value': '0',
                    'detail': 'No construction queue store is connected.',
                    'status': 'UNKNOWN',
                },
                {
                    'label': 'Tareas activas',
                    'value': '0',
                    'detail': 'No task executor is connected to this runtime.',
                    'status': 'UNKNOWN',
                },
                {
                    'label': 'Bloqueos',
                    'value': '0',
                    'detail': 'No critical blockers registered by runtime.',
                    'status': 'OPERATIONAL',
                },
                {
                    'label': 'Aprobaciones pendientes',
                    'value': '0',
                    'detail': 'No human approvals are pending in runtime.',
                    'status': 'OPERATIONAL',
                },
                {
                    'label': 'Entregas listas',
                    'value': '0',
                    'detail': 'No delivery artifact is registered by runtime.',
                    'status': 'UNKNOWN',
                },
                {
                    'label': 'Ultima ejecucion',
                    'value': 'N/A',
                    'detail': 'No execution ledger is connected yet.',
                    'status': 'UNKNOWN',
                },
            ],
            'services': [
                {
                    'name': 'Backend',
                    'status': 'OPERATIONAL',
                    'detail': 'FastAPI service is responding.',
                },
                {
                    'name': 'Runtime',
                    'status': 'OPERATIONAL',
                    'detail': 'Runtime status endpoint is responding.',
                },
                {
                    'name': 'Auditoria',
                    'status': 'UNKNOWN',
                    'detail': 'Audit runner endpoint is not connected.',
                },
                {
                    'name': 'FORJA',
                    'status': 'DEGRADED',
                    'detail': 'Human cabin is available; execution actions are intentionally disabled.',
                },
                {
                    'name': 'Code',
                    'status': 'UNKNOWN',
                    'detail': 'Code execution agent is not connected to this backend.',
                },
                {
                    'name': 'Traceability',
                    'status': 'DEGRADED',
                    'detail': 'Provenance metadata exists; persistent ledger is not connected.',
                },
                {
                    'name': 'AI Chat',
                    'status': 'OPERATIONAL' if settings.OPENROUTER_API_KEY.strip() else 'UNKNOWN',
                    'detail': 'OpenRouter is configured server-side.' if settings.OPENROUTER_API_KEY.strip() else 'OPENROUTER_API_KEY is not configured.',
                },
            ],
            'constructionQueue': [],
            'flow': [
                {
                    'stage': 'AUDIT',
                    'status': 'UNKNOWN',
                    'detail': 'No audit runner connected.',
                },
                {
                    'stage': 'TASKS',
                    'status': 'UNKNOWN',
                    'detail': 'No task planner connected.',
                },
                {
                    'stage': 'FORJA',
                    'status': 'DEGRADED',
                    'detail': 'Human cabin can display state; execution actions are blocked.',
                },
                {
                    'stage': 'CODE',
                    'status': 'UNKNOWN',
                    'detail': 'No Code execution channel connected.',
                },
                {
                    'stage': 'RE-AUDIT',
                    'status': 'UNKNOWN',
                    'detail': 'No re-audit runner connected.',
                },
                {
                    'stage': 'CERTIFICATION',
                    'status': 'UNKNOWN',
                    'detail': 'No certification artifact registered.',
                },
            ],
            'approvals': [],
            'blockers': [],
            'activity': [
                {
                    'time': 'now',
                    'event': 'Runtime status requested',
                    'app': 'FORJA',
                    'result': 'Metadata snapshot returned',
                    'severity': 'OPERATIONAL',
                },
                {
                    'time': 'now',
                    'event': 'Execution actions checked',
                    'app': 'FORJA',
                    'result': 'Write/deploy/freeze actions blocked',
                    'severity': 'DEGRADED',
                },
            ],
            'deliveries': [],
        },
        'timestamp': utc_timestamp(),
    }


def provenance_payload():
    return {
        'app_name': 'FORJA',
        'runtime_version': settings.APP_VERSION,
        'phase_status': 'LOCAL_FULL_REMEDIATION',
        'source': 'C:/Users/admin/Desktop/forja',
        'deployment_target': 'local validation only; deploy not approved',
        'data_state': 'NO_SECRETS_EXPOSED',
        'governance_state': 'human approval required for write, deploy, freeze and provider actions',
        'endpoints': {
            'health': '/health',
            'runtime': '/runtime/status',
            'provenance': '/provenance',
            'chat': '/api/chat',
            'versioned_health': '/api/v1/health',
            'versioned_runtime': '/api/v1/runtime/status',
            'versioned_provenance': '/api/v1/provenance',
            'versioned_chat': '/api/v1/chat',
        },
        'ai_chat': {
            'provider': 'openrouter',
            'status': 'configured' if settings.OPENROUTER_API_KEY.strip() else 'not_configured',
            'key_exposed': False,
        },
        'timestamp': utc_timestamp(),
    }


def chat_status_payload():
    configured = bool(settings.OPENROUTER_API_KEY.strip())
    return {
        'reply': 'OPENROUTER_CONFIGURED' if configured else 'AI_CHAT_NOT_CONFIGURED',
        'status': 'ok' if configured else 'not_configured',
        'provider': 'openrouter',
    }


def openrouter_system_prompt(context: str):
    return (
        'Eres FORJA, Directora de Construccion Controlada del Ecosistema. '
        'Hablas con el CEO en primera persona, con criterio ejecutivo, claro y responsable. '
        'No inventes tareas, aprobaciones, deploys, entregas, estados ni memoria operacional. '
        'Si falta evidencia, dilo y recomienda el siguiente paso seguro. '
        f'Contexto verificable: {context or "sin contexto verificable"}'
    )


def call_openrouter(message: str, context: str):
    if not settings.OPENROUTER_API_KEY.strip():
        return chat_status_payload()

    payload = json.dumps({
        'model': settings.OPENROUTER_MODEL,
        'temperature': 0.18,
        'max_tokens': 520,
        'messages': [
            {'role': 'system', 'content': openrouter_system_prompt(context)},
            {'role': 'user', 'content': message},
        ],
    }).encode('utf-8')

    request = urllib.request.Request(
        'https://openrouter.ai/api/v1/chat/completions',
        data=payload,
        method='POST',
        headers={
            'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode('utf-8')
            data = json.loads(raw)
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='ignore')[:320]
        return {
            'reply': f'OPENROUTER_ERROR: HTTP {error.code}. {detail}',
            'status': 'error',
            'provider': 'openrouter',
        }
    except Exception as error:
        return {
            'reply': f'OPENROUTER_ERROR: {str(error)}',
            'status': 'error',
            'provider': 'openrouter',
        }

    reply = (
        data.get('choices', [{}])[0]
        .get('message', {})
        .get('content')
        or 'No recibi respuesta util de OpenRouter.'
    )

    return {
        'reply': reply,
        'status': 'ok',
        'provider': 'openrouter',
    }


@router.get('/health')
def health_check():
    return health_payload()


@router.get('/runtime/status')
def runtime_status():
    return runtime_payload()


@router.get('/provenance')
def provenance():
    return provenance_payload()


@router.get('/chat')
def chat_status():
    return chat_status_payload()


@router.post('/chat')
def chat(request: ChatRequest):
    message = request.message.strip()
    if not message:
        return {
            'reply': 'FORJA necesita un mensaje real para responder.',
            'status': 'error',
            'provider': 'validation',
        }

    if request.app.upper() != 'FORJA':
        return {
            'reply': 'Este endpoint solo responde por FORJA.',
            'status': 'error',
            'provider': 'validation',
        }

    return call_openrouter(message, request.context)
