#!/usr/bin/env python3
"""
Habilita las conexiones de Foundry (AI Search + Function API) para todos los
usuarios del workshop. NO crea agentes.

Cada usuario recibe dos conexiones en el proyecto compartido de AI Foundry:
  - contoso-{alias}-ai-search   → CognitiveSearch / ApiKey
  - contoso-{alias}-function-api → GenericRest / None

Requisitos:
  pip install azure-identity requests

Uso:
  python3 scripts/provision_foundry_connections.py
  python3 scripts/provision_foundry_connections.py --csv otras_usuarios.csv
  python3 scripts/provision_foundry_connections.py --dry-run
  python3 scripts/provision_foundry_connections.py --only user01,user05
"""

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

import requests
from azure.identity import DefaultAzureCredential

# ── Constantes del entorno compartido ────────────────────────────────────────
# Estas vienen de workshop_config.json / connection IDs del proyecto user29.

SUBSCRIPTION_ID = "e5710503-e888-4064-b0fd-77eda19d3101"
FOUNDRY_RG       = "general"                   # RG donde vive aifoundryworkshopmj
FOUNDRY_ACCOUNT  = "aifoundryworkshopmj"
FOUNDRY_PROJECT  = "proj-default"
CONNECTIONS_API  = "2025-06-01"


# ── Helpers de autenticación ─────────────────────────────────────────────────

_cred = None

def _credential() -> DefaultAzureCredential:
    global _cred
    if _cred is None:
        _cred = DefaultAzureCredential()
    return _cred

def _arm_headers() -> dict:
    token = _credential().get_token("https://management.azure.com/.default").token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── URLs ARM ─────────────────────────────────────────────────────────────────

def _connection_url(name: str) -> str:
    return (
        f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}"
        f"/resourceGroups/{FOUNDRY_RG}"
        f"/providers/Microsoft.CognitiveServices/accounts/{FOUNDRY_ACCOUNT}"
        f"/projects/{FOUNDRY_PROJECT}/connections/{name}"
        f"?api-version={CONNECTIONS_API}"
    )

def _connection_id(name: str) -> str:
    return (
        f"/subscriptions/{SUBSCRIPTION_ID}"
        f"/resourceGroups/{FOUNDRY_RG}"
        f"/providers/Microsoft.CognitiveServices/accounts/{FOUNDRY_ACCOUNT}"
        f"/projects/{FOUNDRY_PROJECT}/connections/{name}"
    )


# ── Operaciones sobre conexiones ─────────────────────────────────────────────

def _get_connection(name: str) -> dict | None:
    r = requests.get(_connection_url(name), headers=_arm_headers(), timeout=30)
    if r.status_code == 404:
        return None
    if r.status_code >= 400:
        raise RuntimeError(f"GET connection error {r.status_code}: {r.text[:300]}")
    return r.json()


def _put_connection(name: str, body: dict, dry_run: bool) -> str:
    """PUT (crear/actualizar) una conexión. Devuelve 'creada', 'ya existia' o 'dry-run'."""
    existing = _get_connection(name)
    if existing:
        ex_props = existing.get("properties", {})
        new_target   = body["properties"]["target"]
        new_auth     = body["properties"]["authType"]
        # Si ya existe con mismas propiedades, no hace falta actualizar
        if ex_props.get("target") == new_target and ex_props.get("authType") == new_auth:
            return "ya existia"
    if dry_run:
        return "dry-run"
    r = requests.put(
        _connection_url(name),
        headers=_arm_headers(),
        json=body,
        timeout=30,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"PUT connection error {r.status_code}: {r.text[:400]}")
    return "creada"


# ── Admin key de Azure Search ─────────────────────────────────────────────────

def _get_search_admin_key(service_name: str, rg_name: str) -> str:
    result = subprocess.run(
        [
            "az", "search", "admin-key", "show",
            "--service-name", service_name,
            "--resource-group", rg_name,
            "--query", "primaryKey",
            "-o", "tsv",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(
            f"No se pudo obtener admin key para '{service_name}' en '{rg_name}':\n"
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


# ── Lógica principal por usuario ─────────────────────────────────────────────

def provision_user(alias: str, rg_name: str, dry_run: bool) -> dict:
    prefix        = f"contoso-{alias}"
    search_svc    = f"{alias}srch"
    search_ep     = f"https://{search_svc}.search.windows.net"
    function_url  = f"https://{alias}contosofunc.azurewebsites.net/api"
    conn_search   = f"{prefix}-ai-search"
    conn_function = f"{prefix}-function-api"

    # 1) AI Search connection (ApiKey)
    try:
        admin_key = _get_search_admin_key(search_svc, rg_name)
        search_body = {
            "properties": {
                "category": "CognitiveSearch",
                "authType": "ApiKey",
                "target": search_ep,
                "credentials": {"key": admin_key},
            }
        }
        status_search = _put_connection(conn_search, search_body, dry_run)
    except Exception as e:
        status_search = f"ERROR: {e}"

    # 2) Function API connection (sin credenciales)
    try:
        func_body = {
            "properties": {
                "category": "GenericRest",
                "authType": "None",
                "target": function_url,
            }
        }
        status_func = _put_connection(conn_function, func_body, dry_run)
    except Exception as e:
        status_func = f"ERROR: {e}"

    return {
        "alias":            alias,
        "ai_search_conn":   conn_search,
        "ai_search_status": status_search,
        "ai_search_id":     _connection_id(conn_search),
        "function_conn":    conn_function,
        "function_status":  status_func,
        "function_id":      _connection_id(conn_function),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Habilita conexiones de Foundry por usuario (sin crear agentes).")
    parser.add_argument(
        "--csv",
        default="usuarios_workshop_30.csv",
        help="Ruta al CSV de usuarios (default: usuarios_workshop_30.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra qué haría sin ejecutar cambios en Azure",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Lista de alias separados por coma para procesar solo esos (ej. user01,user02)",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Ruta opcional para guardar el reporte en JSON",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: No se encontro el CSV: {csv_path}", file=sys.stderr)
        sys.exit(1)

    only_set = {a.strip() for a in args.only.split(",") if a.strip()}

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        users = [row for row in reader]

    if only_set:
        users = [u for u in users if u["alias"] in only_set]

    mode = "[DRY-RUN] " if args.dry_run else ""
    print(f"{mode}Provisionando conexiones Foundry para {len(users)} usuario(s)...")
    print(f"  Foundry: {FOUNDRY_ACCOUNT}/{FOUNDRY_PROJECT} (RG: {FOUNDRY_RG})\n")

    results = []
    ok = errors = 0

    for user in users:
        alias   = user["alias"].strip()
        rg_name = user.get("rg_name", f"rg-foundry-demo-{alias}").strip()
        print(f"  [{alias}] ...", end="", flush=True)

        try:
            result = provision_user(alias, rg_name, args.dry_run)
            results.append(result)

            s_search = result["ai_search_status"]
            s_func   = result["function_status"]
            has_error = "ERROR" in s_search or "ERROR" in s_func
            if has_error:
                errors += 1
            else:
                ok += 1
            print(f" search={s_search}  function={s_func}")
        except Exception as e:
            print(f" FALLO: {e}")
            results.append({"alias": alias, "error": str(e)})
            errors += 1

        # Pequeña pausa para no saturar el ARM throttle
        time.sleep(0.3)

    print(f"\nResumen: {ok} OK | {errors} con errores | {len(users)} total")

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Reporte guardado en: {out_path}")


if __name__ == "__main__":
    main()
