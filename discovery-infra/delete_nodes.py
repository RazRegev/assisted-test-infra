#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import json
import argparse
import shutil
from functools import partial

import assisted_service_api
import consts
import utils
import virsh_cleanup
from logger import log
from oc_login import oc_login


@utils.on_exception(message='Failed to delete cluster')
def try_to_delete_cluster(namespace, tfvars):
    """ Try to delete cluster if assisted-service is up and such cluster
        exists.
    """
    cluster_id = tfvars.get('cluster_inventory_id')
    if not cluster_id:
        return

    client = assisted_service_api.create_client(
        service_name=args.service_name,
        namespace=namespace,
        inventory_url=args.inventory_url,
        wait_for_url=False,
        target=args.target
    )
    client.delete_cluster(cluster_id=cluster_id)


def delete_nodes(cluster_name, namespace, tfvars):
    """ Runs terraform destroy and then cleans it with virsh cleanup to delete
        everything relevant.
    """
    tf_folder = os.path.join(consts.TF_FOLDER, cluster_name)

    def _on_exception():
        log.info('deleting %s', tf_folder)
        shutil.rmtree(tf_folder)

    @utils.on_exception(
        message='Failed to run terraform delete',
        callback=_on_exception,
        silent=True
    )
    def _try_to_delete_nodes():
        log.info('Start running terraform delete')
        cmd = f'cd {tf_folder} && ' \
              f'terraform destroy ' \
              f'-auto-approve ' \
              f'-input=false ' \
              f'-state=terraform.tfstate ' \
              f'-state-out=terraform.tfstate ' \
              f'-var-file=terraform.tfvars.json'
        utils.run_command_with_output(cmd)

    _try_to_delete_nodes()

    network_name = consts.NETWORK_NAME_PREFIX + namespace
    _delete_virsh_resources(
        tfvars.get('cluster_name', cluster_name),
        tfvars.get('libvirt_network_name', network_name),
    )


def _delete_virsh_resources(*filters):
    log.info('Deleting virsh resources (filters: %s)', filters)
    virsh_cleanup.clean_virsh_resources(
        skip_list=virsh_cleanup.DEFAULT_SKIP_LIST,
        resource_filter=filters
    )


def delete_clusters_from_all_namespaces():
    clusters = os.listdir(consts.TF_FOLDER)
    for cluster_name, namespace in _iter_clusters_by_namespaces(clusters):
        delete_cluster_by_name(cluster_name, namespace)


@utils.on_exception(message='Failed to iterate over clusters by namespaces')
def _iter_clusters_by_namespaces(clusters):
    namespaces = utils.run_command(
        'kubectl get namespace --output json --selector name',
        callback=_parse_get_namespace_cmd_output
    )

    for ns in namespaces:
        ns = ns['metadata']['name']
        for c in _filter_clusters_by_namespace(ns, clusters):
            yield c, ns


def _parse_get_namespace_cmd_output(cmd, out, err):
    utils.raise_error_if_occurred(cmd, out, err)

    try:
        return json.loads(out).get('items', [])
    except json.JSONDecodeError:
        log.exception(
            f'cmd {cmd}: failed to convert output to json: {out}'
        )
        raise


def _filter_clusters_by_namespace(namespace, clusters):
    return list(filter(lambda x: x.endswith(f'-{namespace}'), clusters))


@utils.on_exception(message='Failed to delete nodes', silent=True)
def delete_cluster_by_name(cluster_name, namespace):
    log.info('Deleting cluster: %s in namespace: %s', cluster_name, namespace)

    tfvars = utils.get_tfvars(cluster_name)
    if not args.only_nodes:
        try_to_delete_cluster(namespace, tfvars)
    delete_nodes(cluster_name, namespace, tfvars)


def main():
    if args.delete_all:
        _delete_virsh_resources()
        return

    if args.target in ('oc', 'oc-ingress'):
        oc_login(args.oc_server, args.oc_token)

    if args.namespace == 'all':
        delete_clusters_from_all_namespaces()
        return

    cluster_name = args.cluster_name or consts.CLUSTER_PREFIX
    cluster_name += f'-{args.namespace}'
    delete_cluster_by_name(cluster_name, args.namespace)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run delete nodes flow")
    parser.add_argument(
        "-iU",
        "--inventory-url",
        help="Full url of remote inventory",
        type=str,
        default="",
    )
    parser.add_argument(
        "-id", "--cluster-id", help="Cluster id to install", type=str, default=None
    )
    parser.add_argument(
        "-n",
        "--only-nodes",
        help="Delete only nodes, without cluster",
        action="store_true",
    )
    parser.add_argument(
        "-a",
        "--delete-all",
        help="Delete only nodes, without cluster",
        action="store_true",
    )
    parser.add_argument(
        "-ns",
        "--namespace",
        help="Delete under this namespace",
        type=str,
        default="assisted-installer",
    )
    parser.add_argument(
        '-cn',
        '--cluster-name',
        help='Cluster name',
        required=False,
    )
    parser.add_argument(
        '-t',
        '--target',
        help='Target inventory deployment (minikube/oc/oc-ingress)',
        type=utils.validate_target,
        default='minikube',
    )
    parser.add_argument(
        '--oc-token',
        help='Token for oc target that will be used for login',
        type=str,
        required=False
    )
    parser.add_argument(
        '--oc-server',
        help='Server for oc target that will be used for login',
        type=str,
        required=False,
        default='https://api.ocp.prod.psi.redhat.com:6443'
    )
    parser.add_argument(
        '--service-name',
        help='Assisted Service name',
        type=str,
        required=False,
        default='assisted-service'
    )
    args = parser.parse_args()
    main()
