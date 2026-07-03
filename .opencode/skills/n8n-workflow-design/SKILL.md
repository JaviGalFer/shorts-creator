# Skill: n8n-workflow-design

## Cuándo usarla
Para diseñar un workflow de n8n.

## Entradas
- Especificación funcional del workflow.
- APIs a integrar.
- Formato de datos esperado.

## Salidas
- Descripción del workflow (nodos, conexiones, configuración).
- Variables de entorno necesarias.
- Estrategia de errores y reintentos.

## Procedimiento
1. Identificar nodos necesarios (Webhook, HTTP Request, Function, etc.).
2. Definir flujo de datos entre nodos.
3. Diseñar manejo de errores (Error Trigger, rutas alternativas).
4. Documentar credenciales necesarias (sin valores reales).
5. Especificar formato de entrada/salida esperado.

## Validaciones
- El flujo cubre el caso feliz y al menos un caso de error.
- Las credenciales se referencian por ID, no por valor.
- Los datos sensibles no se loggean.

## Límites
- No exportar JSON de workflow real sin especificación aprobada.
- No activar workflows en producción.
