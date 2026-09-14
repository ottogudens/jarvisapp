with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_code = """    try:
        _gc = get_gemini_client()
        contents = [prompt_con_contexto] + gemini_parts
        gr = _gc.models.generate_content(model="gemini-3.6-flash", contents=contents)
        respuesta_jarvis = gr.text or "Lo siento, no pude generar una respuesta."
    except Exception as e:
        respuesta_jarvis = f"Señor, he experimentado una anomalía: {str(e)}\""""

new_code = """    try:
        _gc = get_gemini_client()
        
        from backend.iot_service import IoTService
        import asyncio
        iot_service = IoTService(db, usuario["id_usuario"])
        
        def obtener_estado_dispositivo(entity_id: str) -> str:
            \"\"\"Obtiene el estado de un dispositivo en Home Assistant.\"\"\"
            try: loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(iot_service.obtener_estado_dispositivo(entity_id))
            
        def activar_dispositivo(entity_id: str, accion: str) -> str:
            \"\"\"Cambia estado de un dispositivo en Home Assistant (ej. turn_on, turn_off).\"\"\"
            try: loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(iot_service.activar_dispositivo(entity_id, accion))

        def enviar_mensaje_mqtt(topic: str, payload: str) -> str:
            \"\"\"Publica un mensaje JSON en MQTT para controlar dispositivos locales.\"\"\"
            return iot_service.publicar_mensaje_mqtt(topic, payload)

        contents = [prompt_con_contexto] + gemini_parts
        
        gr = _gc.models.generate_content(
            model="gemini-3.6-flash", 
            contents=contents,
            config=types.GenerateContentConfig(
                tools=[obtener_estado_dispositivo, activar_dispositivo, enviar_mensaje_mqtt],
                temperature=0.7
            )
        )
        
        respuesta_jarvis = "Ejecuté sus órdenes en los sistemas domésticos, señor." if gr.function_calls else (gr.text or "Entendido.")
        
        # En caso de tool call, procesar y re-invocar a Gemini para respuesta final
        if gr.function_calls:
            responses = []
            for function_call in gr.function_calls:
                fn_name = function_call.name
                args = function_call.args
                if fn_name == "obtener_estado_dispositivo":
                    res = obtener_estado_dispositivo(**args)
                elif fn_name == "activar_dispositivo":
                    res = activar_dispositivo(**args)
                elif fn_name == "enviar_mensaje_mqtt":
                    res = enviar_mensaje_mqtt(**args)
                else:
                    res = "Herramienta no encontrada"
                responses.append(types.Part.from_function_response(name=fn_name, response={"result": res}))
            
            # Segunda llamada
            contents.append(gr.candidates[0].content) # el call
            contents.append(types.Content(parts=responses, role="user")) # los resultados
            gr2 = _gc.models.generate_content(model="gemini-3.6-flash", contents=contents)
            respuesta_jarvis = gr2.text or respuesta_jarvis
            
    except Exception as e:
        respuesta_jarvis = f"Señor, he experimentado un fallo en la matriz de red: {str(e)}\""""

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('backend/main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Injection SUCCESS")
else:
    print("Old code NOT FOUND")
