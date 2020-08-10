#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import json
import argparse
import shutil

import assisted_service_api
import consts
import utils
import virsh_cleanup
from logger import log
from oc_login import oc_login


# Try to delete cluster if assisted-service is up and such cluster exists
def try_to_delete_cluster(namespace, tfvars):
    try:
        cluster_id = tfvars.get("cluster_inventory_id")
        if cluster_id:
            client = assisted_service_api.create_client(
                namespace=namespace,
                inventory_url=args.inventory_url,
                wait_for_url=False,
                target=args.target
            )
            client.delete_cluster(cluster_id=cluster_id)
    # TODO add different exception validations
    except:
        log.exception("Failed to delete cluster")


# Runs terraform destroy and then cleans it with virsh cleanup to delete everything relevant
def delete_nodes(cluster_name, tfvars):
    tf_folder = os.path.join(consts.TF_FOLDER, cluster_name)

    try:
        log.info("Start running terraform delete")
        cmd = (
            "cd %s  && terraform destroy -auto-approve "
            "-input=false -state=terraform.tfstate -state-out=terraform.tfstate "
            "-var-file=terraform.tfvars.json" % tf_folder
        )
        utils.run_command_with_output(cmd)
    except:
        log.exception("Failed to run terraform delete, deleting %s", tf_folder)
        shutil.rmtree(tf_folder)
    finally:
        virsh_cleanup.clean_virsh_resources(
            virsh_cleanup.DEFAULT_SKIP_LIST,
            [
                tfvars.get("cluster_name", consts.TEST_INFRA),
                tfvars.get("libvirt_network_name", consts.TEST_INFRA),
            ],
        )


# Deletes every single virsh resource, leaves only defaults
def delete_all():
    log.info("Deleting all virsh resources")
    virsh_cleanup.clean_virsh_resources(virsh_cleanup.DEFAULT_SKIP_LIST, None)


def iter_clusters_namespaces(clusters):
    items = utils.run_command(
        'kubectl get namespace --output json --selector name',
        callback=_parse_get_namespace_cmd_output
    )

    for i in items:
        namespace = i['name']
        if _is_namespace_in_use(namespace, clusters):
            yield namespace


def _parse_get_namespace_cmd_output(cmd, out, err):
    utils.raise_error_if_occurred(cmd, out, err)

    try:
        return json.loads(out).get('items', [])
    except json.JSONDecodeError:
        log.exception(f'cmd {cmd}: unable to decode json output: {out}')
        raise


def _is_namespace_in_use(namespace, clusters):
    for c in clusters:
        if c.endswith(f'-{namespace}'):
            return True

    return False


def main():
    if args.target in ('oc', 'oc-ingress'):
        oc_login(args.oc_server, args.oc_token)

    clusters = os.listdir(consts.TF_FOLDER)

    if args.namespace == 'all':
        for namespace in iter_clusters_namespaces(clusters):
            delete_cluster_by_namespace(namespace)

    elif _is_namespace_in_use(args.namespace, clusters):
        delete_cluster_by_namespace(args.namespace)


def delete_cluster_by_namespace(namespace):
    cluster_name = args.cluster_name or consts.CLUSTER_PREFIX
    cluster_name += f'-{namespace}'
    log.info('deleting cluster: %s', cluster_name)

    if args.delete_all:
        delete_all()
    else:
        try:
            tfvars = utils.get_tfvars(cluster_name)
            if not args.only_nodes:
                try_to_delete_cluster(namespace, tfvars)
            delete_nodes(cluster_name, tfvars)
        except:
            log.exception("Failed to delete nodes")


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
    args = parser.parse_args()
    main()
