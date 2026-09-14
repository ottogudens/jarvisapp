with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add VoiceSettings import if not present
if "from elevenlabs import VoiceSettings" not in content:
    content = content.replace("from elevenlabs.client import ElevenLabs as ElevenLabsClient", 
                              "from elevenlabs.client import ElevenLabs as ElevenLabsClient\nfrom elevenlabs import VoiceSettings")

# Patch _pipeline_ia generate
old_generate_1 = """            audio_response = get_elevenlabs_client().generate(
                text=respuesta_texto,
                voice=voice_id,
                model="eleven_multilingual_v2",
            )"""

new_generate_1 = """            audio_response = get_elevenlabs_client().generate(
                text=respuesta_texto,
                voice=voice_id,
                model="eleven_multilingual_v2",
                voice_settings=VoiceSettings(stability=0.30, similarity_boost=0.75, style=0.0, use_speaker_boost=True)
            )"""
content = content.replace(old_generate_1, new_generate_1)

# Patch enviar_mensaje_chat generate
old_generate_2 = 'ar = get_elevenlabs_client().generate(text=respuesta_jarvis, voice=vid, model="eleven_multilingual_v2")'
new_generate_2 = 'ar = get_elevenlabs_client().generate(text=respuesta_jarvis, voice=vid, model="eleven_multilingual_v2", voice_settings=VoiceSettings(stability=0.30, similarity_boost=0.75, style=0.0, use_speaker_boost=True))'
content = content.replace(old_generate_2, new_generate_2)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated VoiceSettings in main.py")
