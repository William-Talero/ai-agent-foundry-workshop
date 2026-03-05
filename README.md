# Workshop Foundry - Orquestador y Especialistas

Este repositorio esta pensado para ejecutar el workshop en orden, de forma guiada por notebooks.

Objetivo del flujo:

1. Preparar configuracion base del laboratorio.
2. Crear AI Search con datos de ejemplo.
3. Publicar Function App con endpoints del taller.
4. Crear los agentes especialistas por herramienta.
5. Crear orquestador con routing hacia especialistas.

Cantidad de agentes en el workshop (definitivo):

- No son 6 especialistas.
- Son 3 especialistas: `conocimiento`, `cliente`, `soporte`.
- Y 1 orquestador que delega en esos 3.

Resumen rapido:

| Tipo | Cantidad |
| --- | --- |
| Especialistas | 3 |
| Orquestador | 1 |
| Total de agentes | 4 |

## Importante

Este README no incluye aprovisionamiento de usuarios. Solo cubre la ejecucion del workshop con los notebooks.

## Prerrequisitos minimos

1. Azure CLI autenticado (`az login`).
2. Archivo `config.env` creado desde `config.env.example`.
3. Variables minimas en `config.env`:

- `AZURE_OPENAI_ENDPOINT`
- `FOUNDRY_PROJECT_ENDPOINT`
- `FOUNDRY_AGENTS_API_VERSION`
- `USER_ALIAS`
- `USER_RG_NAME`
- `AZURE_SUBSCRIPTION_ID`

## Orden de ejecucion

1. `00_setup_configuracion.ipynb`
2. `01_ai_search_por_usuario.ipynb`
3. `02_function_app_por_usuario.ipynb`
4. `03_agentes_especializados_por_tools.ipynb`
5. `04_orquestador_con_routing.ipynb`

## Que resuelve cada notebook

1. `00_setup_configuracion.ipynb`
- Valida entorno.
- Carga variables desde `config.env`.
- Genera/actualiza `workshop_config.json`.

2. `01_ai_search_por_usuario.ipynb`
- Provisiona AI Search del participante.
- Crea indice y carga documentos para RAG.

3. `02_function_app_por_usuario.ipynb`
- Provisiona y despliega Function App.
- Publica endpoints usados por agentes.

4. `03_agentes_especializados_por_tools.ipynb`
- Crea/actualiza exactamente 3 especialistas (`conocimiento`, `cliente`, `soporte`).
- Configura tools (Search/OpenAPI) por especialidad.

5. `04_orquestador_con_routing.ipynb`
- Crea/actualiza orquestador.
- Define routing hacia especialistas.
- Ejecuta pruebas de punta a punta.

## Inicio rapido

```bash
cp config.env.example config.env
az login
```

Despues, ejecuta los notebooks en el orden `00 -> 04` sin saltar pasos.
