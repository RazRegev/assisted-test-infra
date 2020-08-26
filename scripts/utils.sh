#!/usr/bin/env bash

set -o nounset

export KUBECONFIG=${KUBECONFIG:-$HOME/.kube/config}
export NAMESPACE=${NAMESPACE:-assisted-installer}

function print_log() {
    echo "$(basename $0): $1"
}

function url_reachable() {
    curl -s $1 --max-time 4 >/dev/null
    return $?
}

function spawn_port_forwarding_command() {
    service_name=$1
    external_port=$2
    namespace=$3
    namespace_index=$4
    profile=$5

    filename=${service_name}__${namespace}__${namespace_index}__assisted_installer

    cat <<EOF >build/xinetd-$filename
service ${service_name}
{
  flags		= IPv4
  bind		= 0.0.0.0
  type		= UNLISTED
  socket_type	= stream
  protocol	= tcp
  user		= root
  wait		= no
  redirect	= $(minikube -p $profile ip) $(kubectl --server $(get_profile_url $profile) --kubeconfig=${KUBECONFIG} get svc/${service_name} -n ${NAMESPACE} -o=jsonpath='{.spec.ports[0].nodePort}')
  port		= ${external_port}
  only_from	= 0.0.0.0/0
  per_source	= UNLIMITED
}
EOF
    sudo mv build/xinetd-$filename /etc/xinetd.d/$filename --force
    sudo systemctl restart xinetd
}

function run_in_background() {
    bash -c "nohup $1  >/dev/null 2>&1 &"
}

function kill_port_forwardings() {
    namespace=$1
    sudo systemctl stop xinetd
    for f in $(sudo ls /etc/xinetd.d/ | grep __${namespace}__); do
        sudo rm -f /etc/xinetd.d/$f
    done
}

function kill_all_port_forwardings() {
    sudo systemctl stop xinetd
    for f in $(sudo ls /etc/xinetd.d/ | grep __assisted_installer); do
        sudo rm -f /etc/xinetd.d/$f
    done
}

function get_main_ip() {
    echo "$(ip route get 1 | sed 's/^.*src \([^ ]*\).*$/\1/;q')"
}

function wait_for_url_and_run() {
    RETRIES=15
    RETRIES=$((RETRIES))
    STATUS=1
    url_reachable "$1" && STATUS=$? || STATUS=$?

    until [ $RETRIES -eq 0 ] || [ $STATUS -eq 0 ]; do

        RETRIES=$((RETRIES - 1))

        echo "Running given function"
        $2

        echo "Sleeping for 30 seconds"
        sleep 30s

        echo "Verifying URL and port are accessible"
        url_reachable "$1" && STATUS=$? || STATUS=$?
    done
    if [ $RETRIES -eq 0 ]; then
        echo "Timeout reached, URL $1 not reachable"
        exit 1
    fi
}

function close_external_ports() {
    sudo firewall-cmd --zone=public --remove-port=6000/tcp
    sudo firewall-cmd --zone=public --remove-port=6008/tcp
}

function validate_namespace() {
    namespace=$1
    if [[ $namespace =~ ^[0-9a-zA-Z\-]+$ ]]; then
        return
    fi
    echo "Invalid namespace '$namespace'"
    echo "It can contain only letters, numbers and '-'"
    exit 1
}

function get_profile_url() {
    profile=$1
    echo https://$(minikube ip --profile $profile):8443
}

function run_as_singleton() {
    target=$1

    lockfile="/tmp/$1.lock"

    while [ -e "$lockfile" ]; do
        echo "Can run only one instance of $target at a time"
        echo "Waiting for other instances of $target to be completed"
        sleep 15s
    done

    trap 'rm "$lockfile"; exit' EXIT INT TERM HUP
    touch "$lockfile"

    $target
}

"$@"
