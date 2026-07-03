# Seguridad

## Gestión de secretos

- API keys solo en `.env` (excluido de Git vía `.gitignore`).
- n8n almacena credenciales cifradas en su base de datos.
- No escribir secretos en logs, prompts, bitácoras, handovers, OpenSpec, exports ni archivos versionados.
- No incluir valores reales de API keys en documentación ni ejemplos.
- Rotación periódica de claves.

## Reglas de no exposición

- HANDOVER.md: usar `***` para valores de API keys y contraseñas.
- Bitácoras de sesión: no incluir secretos.
- Prompts de LLM generados: no incluir API keys en el prompt.
- Metadata.json de jobs: no incluir API keys ni tokens.
- Logs de ejecución: sanitizar antes de guardar.

## Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Filtración de API key en documentación | Prohibición explícita en AGENTS.md. Revisión manual periódica. |
| Filtración de API key por log | Logs excluidos de Git. Scripts de logging sanitizan secretos. |
| Uso no autorizado de API | Claves con permisos mínimos. Monitorización de consumo. |
| Contenido generado inapropiado | Revisión humana obligatoria antes de publicación. |
| Licencias de imágenes | Solo usar APIs con licencia clara. Documentar atribución. |
| Dependencia de terceros | APIs intercambiables vía configuración. Fallback local planificado. |

## Buenas prácticas

- No compartir `.env` por canales no seguros.
- No comitear `.env` ni backups de BD de n8n.
- Preferir variables de entorno a valores hardcodeados en workflows.
- Revisar términos de servicio de cada API antes de integrarla.
- Antes de escribir documentación, comprobar que no contiene secretos.
- Si se detecta un secreto en un archivo versionado, rotar la clave inmediatamente.
