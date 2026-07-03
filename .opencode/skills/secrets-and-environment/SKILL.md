# Skill: secrets-and-environment

## Cuándo usarla
Para gestionar .env, .env.example, secretos o rutas de configuración.

## Entradas
- Variables necesarias para el pipeline.
- Valores por defecto (si existen).
- Secciones de documentación a actualizar.

## Salidas
- .env.example actualizado.
- docs/project/environment.md actualizado.
- Verificación de .gitignore.

## Procedimiento
1. Definir variables necesarias con nombres claros y comentarios.
2. Añadir valores placeholder o por defecto en .env.example.
3. Actualizar documentación de entorno si cambian los requisitos.
4. Verificar que .gitignore excluye .env y directorios de datos.

## Validaciones
- No hay secretos reales en .env.example ni en archivos versionados.
- .env está en .gitignore.
- Las variables tienen nombres coherentes.

## Límites
- No generar claves criptográficas ni tokens sin aprobación.
- No modificar .env real (solo .env.example).
