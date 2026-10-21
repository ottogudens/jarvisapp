"""Contratos estáticos del pipeline de voz, sin requerir una base de datos."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_voice_pipeline_loads_keys_before_transcription_and_tts():
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    transcription = source.index("# FIX #1 – Transcribir audio con Gemini")
    gemini_client = source.index("_gc = get_gemini_client()", transcription)
    assert "load_ai_keys(db)" in source[transcription:gemini_client]

    tts = source.index('audio_b64 = ""', gemini_client)
    elevenlabs_client = source.index("get_elevenlabs_client().generate", tts)
    assert "load_ai_keys(db)" in source[tts:elevenlabs_client]


def test_web_audio_keeps_a_webm_identity_end_to_end():
    frontend = (ROOT / "lib" / "screens" / "chat_screen.dart").read_text(encoding="utf-8")
    backend = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    assert "AudioEncoder.opus" in frontend
    assert "filename: 'audio.webm'" in frontend
    assert '".webm": "audio/webm"' in backend


def test_config_loader_includes_elevenlabs_key():
    source = (ROOT / "backend" / "ai_service.py").read_text(encoding="utf-8")
    assert '"ELEVENLABS_API_KEY"' in source


def test_gemini_configuration_uses_current_models_and_keeps_legacy_tenants_working():
    service = (ROOT / "backend" / "ai_service.py").read_text(encoding="utf-8")
    admin = (ROOT / "backend" / "admin.py").read_text(encoding="utf-8")
    frontend = (ROOT / "lib" / "screens" / "admin_screen.dart").read_text(encoding="utf-8")

    assert 'GEMINI_DEFAULT_CHAT_MODEL = "gemini-3.5-flash-lite"' in service
    assert '"gemini-1.5-flash"' in service  # Sólo para normalizar tenants antiguos.
    assert "client.models.list()" in admin
    assert "gemini-3.5-flash-lite" in frontend


def test_chat_uses_the_automatic_retrieval_path_without_a_legacy_second_search():
    service = (ROOT / "backend" / "ai_service.py").read_text(encoding="utf-8")
    chat = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    assert '"name": "buscar_conocimiento"' not in service
    assert "Estas fuentes fueron recuperadas correctamente" in chat
    assert "Nunca afirmes que no puedes acceder al documento" in chat


def test_mikrotik_tools_are_scoped_and_cannot_abort_a_document_query():
    service = (ROOT / "backend" / "ai_service.py").read_text(encoding="utf-8")
    chat = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    assert "def tools_for_request(enable_mikrotik_tools: bool)" in service
    assert "tools=available_tools" in service
    assert '"required": ["comando", "id_router"]' in service
    assert "Error: no fue posible ejecutar la herramienta {fn_name}." in service
    assert "enable_mikrotik_tools=has_available_mikrotik_router" in chat


def test_litellm_mcp_dependency_is_explicit_and_reproducible():
    requirements = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")

    assert "litellm==1.106.1" in requirements
    assert "mcp>=2.2.0,<3.0.0" in requirements
