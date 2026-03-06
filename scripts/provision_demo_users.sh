#!/usr/bin/env bash
set -euo pipefail

# Provisiona resource groups por usuario y asigna RBAC para un workshop con Foundry compartido.
# Requisitos:
# - Azure CLI autenticado (az login)
# - Permisos para crear RG y role assignments
# - Usuarios de Entra ID ya existentes
#
# Uso:
# ./scripts/provision_demo_users.sh \
#   --subscription-id <subscription-id> \
#   --location eastus \
#   --users-file templates/demo_users.csv \
#   --rg-prefix rg-foundry-demo \
#   --shared-foundry-scope /subscriptions/<sub>/resourceGroups/<rg-foundry>

usage() {
  cat <<EOF
Uso:
  $0 --subscription-id <id> --location <region> --users-file <csv> --rg-prefix <prefix> --shared-foundry-scope <scope>

Parametros:
  --subscription-id       ID de la suscripcion
  --location              Region para RG de participantes (ej. eastus)
  --users-file            CSV con columnas: alias,upn
  --rg-prefix             Prefijo para RG por usuario (ej. rg-demo)
  --shared-foundry-scope  Scope RBAC del Foundry compartido
                          Ejemplo: /subscriptions/<sub>/resourceGroups/<rg-foundry>

Opcionales:
  --rg-role               Rol en RG por usuario (default: Contributor)
  --foundry-role          Rol en Foundry compartido (default: Azure AI Developer)
EOF
}

SUBSCRIPTION_ID=""
LOCATION=""
USERS_FILE=""
RG_PREFIX=""
SHARED_FOUNDRY_SCOPE=""
RG_ROLE="Contributor"
FOUNDRY_ROLE="Azure AI Developer"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription-id) SUBSCRIPTION_ID="$2"; shift 2 ;;
    --location) LOCATION="$2"; shift 2 ;;
    --users-file) USERS_FILE="$2"; shift 2 ;;
    --rg-prefix) RG_PREFIX="$2"; shift 2 ;;
    --shared-foundry-scope) SHARED_FOUNDRY_SCOPE="$2"; shift 2 ;;
    --rg-role) RG_ROLE="$2"; shift 2 ;;
    --foundry-role) FOUNDRY_ROLE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Parametro no reconocido: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "$SUBSCRIPTION_ID" || -z "$LOCATION" || -z "$USERS_FILE" || -z "$RG_PREFIX" || -z "$SHARED_FOUNDRY_SCOPE" ]]; then
  echo "Faltan parametros obligatorios."
  usage
  exit 1
fi

if [[ ! -f "$USERS_FILE" ]]; then
  echo "No existe el archivo de usuarios: $USERS_FILE"
  exit 1
fi

az account set --subscription "$SUBSCRIPTION_ID"

echo "Validando rol Foundry '$FOUNDRY_ROLE'..."
if ! az role definition list --name "$FOUNDRY_ROLE" --query "[0].name" -o tsv | grep -q .; then
  echo "No se encontro el rol '$FOUNDRY_ROLE'."
  echo "Prueba con: 'Cognitive Services OpenAI User' o 'Reader' segun tu governance."
  exit 1
fi

echo "Iniciando aprovisionamiento usando: $USERS_FILE"

# Saltar cabecera CSV
TAIL_CMD="tail -n +2"
$TAIL_CMD "$USERS_FILE" | while IFS=',' read -r ALIAS UPN; do
  ALIAS="$(echo "$ALIAS" | xargs)"
  UPN="$(echo "$UPN" | xargs)"

  if [[ -z "$ALIAS" || -z "$UPN" ]]; then
    echo "Fila invalida, se omite (alias/upn vacio)."
    continue
  fi

  USER_RG="${RG_PREFIX}-${ALIAS}"

  echo ""
  echo "=== Usuario: $UPN | RG: $USER_RG ==="

  USER_OBJECT_ID=$(az ad user show --id "$UPN" --query id -o tsv 2>/dev/null || true)
  if [[ -z "$USER_OBJECT_ID" ]]; then
    echo "No se encontro el usuario en Entra ID: $UPN. Se omite."
    continue
  fi

  az group create --name "$USER_RG" --location "$LOCATION" --output none
  echo "RG creado/verificado: $USER_RG"

  RG_SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${USER_RG}"

  az role assignment create \
    --assignee-object-id "$USER_OBJECT_ID" \
    --assignee-principal-type User \
    --role "$RG_ROLE" \
    --scope "$RG_SCOPE" \
    --output none 2>/dev/null || true
  echo "Rol '$RG_ROLE' aplicado en RG scope"

  az role assignment create \
    --assignee-object-id "$USER_OBJECT_ID" \
    --assignee-principal-type User \
    --role "$FOUNDRY_ROLE" \
    --scope "$SHARED_FOUNDRY_SCOPE" \
    --output none 2>/dev/null || true
  echo "Rol '$FOUNDRY_ROLE' aplicado en Foundry compartido"

done

echo ""
echo "Provision finalizado."
echo "Siguiente paso recomendado: validar acceso con 2 usuarios piloto antes de abrir a los 30."
