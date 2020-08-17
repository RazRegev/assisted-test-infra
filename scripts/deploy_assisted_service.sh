#!/usr/bin/env bash
set -euo pipefail

source scripts/utils.sh

export KUBECONFIG=${KUBECONFIG:-$HOME/.kube/config}
export SERVICE_NAME=assisted-service
export PROFILE=${PROFILE:-assisted-installer}
export NAMESPACE=${NAMESPACE:-assisted-installer}
export SERVICE_URL=$(get_main_ip)
export SERVICE_START_PORT=${SERVICE_START_PORT:-6000}
export SERVICE_BASE_URL="http://${SERVICE_URL}:${SERVICE_PORT}"

mkdir -p build

print_log "Updating assisted_service params"
skipper run discovery-infra/update_assisted_service_cm.py
skipper run "make -C assisted-service/ deploy-all" ${SKIPPER_PARAMS} DEPLOY_TAG=${DEPLOY_TAG} NAMESPACE=${NAMESPACE} PROFILE=${PROFILE}

print_log "Wait till ${SERVICE_NAME} api is ready"
wait_for_url_and_run "$(minikube service ${SERVICE_NAME} --url -p $PROFILE -n ${NAMESPACE})" "echo \"waiting for ${SERVICE_NAME}\""

export SERVICE_PORT=$(search_for_next_free_port $SERVICE_NAME $NAMESPACE $SERVICE_START_PORT)

print_log "Starting port forwarding for deployment/${SERVICE_NAME} on port $SERVICE_PORT"
wait_for_url_and_run ${SERVICE_BASE_URL} "spawn_port_forwarding_command ${SERVICE_NAME} ${SERVICE_PORT} $NAMESPACE $PROFILE"
print_log "${SERVICE_NAME} can be reached at ${SERVICE_BASE_URL} "
print_log "Done"
