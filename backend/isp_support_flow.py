"""Flujo determinista: ningún texto del cliente se ejecuta como herramienta."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import re
import unicodedata

STEPS = [
    "¿El problema ocurre en TODOS tus dispositivos o solo en UNO? Responde TODOS o UNO.",
    "Revisa la alimentación del router y de la ONT, si tienes una. ¿Están encendidos? Responde SI o NO. Si hay olor a quemado o cables dañados, no los manipules y escribe TECNICO.",
    "Sin desconectar ni doblar la fibra, revisa las luces. ¿Hay una luz LOS roja? Responde SI, NO o NO SE.",
    "Comprueba que los cables de red estén firmes. Reinicia el equipo afectado quitando su alimentación 30 segundos y espera hasta 5 minutos. No pulses RESET ni restaures de fábrica. ¿Volvió internet? Responde SI o NO.",
]


def normalized(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', value.strip().upper()) if unicodedata.category(c) != 'Mn')


def _advance(state: dict, text: str, today: date | None = None) -> tuple[dict, str, bool]:
    """Devuelve estado, respuesta y orden de crear ticket tras confirmación explícita."""
    state = dict(state or {})
    answer = normalized(text)
    stage = state.get('stage', 'start')
    if state.get('ticket_id'):
        return state, f"Tu solicitud ya tiene el ticket {state['ticket_id']}. Para otra incidencia, contacta a atención.", False
    if stage in {'submitting', 'unknown'}:
        return state, "Estamos verificando el registro de tu solicitud. Un agente debe revisarlo antes de intentar crear otro ticket.", False
    if answer == 'CANCELAR':
        return {'stage': 'start'}, 'Solicitud cancelada. Escribe SOPORTE para comenzar otra consulta.', False
    if answer == 'TECNICO':
        state['stage'] = 'problem'
        return state, 'Describe brevemente el problema. Lo añadiremos a la solicitud de atención.', False
    if stage == 'start':
        return {'stage': 'step', 'step': 0, 'checks': []}, STEPS[0], False
    if stage == 'step':
        index = state['step']
        allowed = [{'TODOS', 'UNO'}, {'SI', 'NO'}, {'SI', 'NO', 'NO SE'}, {'SI', 'NO'}][index]
        if answer not in allowed:
            return state, STEPS[index], False
        state['checks'] = state.get('checks', []) + [f'Paso {index + 1}: {answer}']
        if index == 3 and answer == 'SI':
            return {'stage': 'start'}, 'Conexión recuperada. Si vuelve a fallar, escribe SOPORTE. No se ha creado un ticket.', False
        if (index == 1 and answer == 'NO') or (index == 2 and answer == 'SI') or index == 3:
            state['stage'] = 'problem'
            return state, 'Describe el problema para solicitar atención técnica. No necesitas seguir reiniciando el equipo.', False
        state['step'] = index + 1
        prefix = 'Prueba también otro dispositivo para comparar. ' if index == 0 and answer == 'UNO' else ''
        return state, prefix + STEPS[index + 1], False
    if stage == 'problem':
        if not 5 <= len(text.strip()) <= 2000:
            return state, 'Describe el problema en entre 5 y 2000 caracteres.', False
        state.update(stage='date', problem=text.strip())
        return state, '¿Qué fecha prefieres para una posible visita? Usa AAAA-MM-DD. Es una preferencia sujeta a confirmación del equipo.', False
    if stage == 'date':
        today = today or datetime.now(ZoneInfo('America/Santiago')).date()
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', text.strip()):
                raise ValueError()
            selected = date.fromisoformat(text.strip())
            if not 0 <= (selected - today).days <= 60:
                raise ValueError()
        except ValueError:
            return state, 'Indica una fecha válida, desde hoy y hasta 60 días, con formato AAAA-MM-DD.', False
        state.update(stage='shift', date=selected.isoformat())
        return state, '¿Qué turno prefieres: MAÑANA o TARDE? La visita aún no está confirmada.', False
    if stage == 'shift':
        if answer not in {'MANANA', 'TARDE'}:
            return state, 'Responde MAÑANA o TARDE.', False
        state.update(stage='confirm', shift='MAÑANA' if answer == 'MANANA' else 'TARDE')
        checks = '; '.join(state.get('checks', [])) or 'Derivación directa solicitada por cliente'
        return state, (f"Resumen: {state['problem']}\nComprobaciones: {checks}\nPreferencia de visita: {state['date']}, {state['shift']} (sin confirmar).\n¿Registro el ticket? Responde CONFIRMAR o CANCELAR."), False
    if stage == 'confirm':
        if answer != 'CONFIRMAR':
            return state, 'Responde CONFIRMAR para registrar el ticket o CANCELAR.', False
        state['stage'] = 'submitting'
        return state, '', True
    return {'stage': 'start'}, 'Escribe SOPORTE para comenzar.', False


def advance(state: dict, text: str, today: date | None = None) -> tuple[dict, str, bool]:
    next_state, reply, create = _advance(state, text, today)
    if (state or {}).get('reviews'):
        next_state['reviews'] = state['reviews']
    return next_state, reply, create
