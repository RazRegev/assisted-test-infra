import os
import yaml

from logger import log
from utils import run_command


def _load_kube_config():
    config_file = os.path.join(os.environ['HOME'], '.kube', 'config')
    with open(config_file) as fp:
        return yaml.safe_load(fp)


def _build_oc_login_cmd(config, server, token):
    cmd = 'oc login --insecure-skip-tls-verify=true'

    cluster, server = _get_cluster_and_server(config, server)
    cmd += f' --server={server}'

    if not token:
        user = _get_user_by_cluster(config, cluster)
        token = _get_token_by_user(config, user)
    cmd += f' --token={token}'

    return cmd


def _get_cluster_and_server(config, server):
    clusters = config['clusters']
    if not config['clusters']:
        raise RuntimeError(f'no cluster was found in config: {config}')
    elif not server:
        return clusters[0]['name'], clusters[0]['cluster']['server']

    for c in clusters:
        if 'server' in c['cluster'] and c['cluster']['server'] == server:
            return c['name'], server

    raise RuntimeError(f'no matching cluster was found for server: {server}')


def _get_user_by_cluster(config, cluster):
    for ctx in config['contexts']:
        if ctx['context']['cluster'] == cluster:
            return ctx['context']['user']

    raise RuntimeError(f'no matching user was found for cluster: {cluster}')


def _get_token_by_user(config, user):
    for u in config['users']:
        if u['name'] == user and 'token' in u['user']:
            return u['user']['token']

    raise RuntimeError(f'no matching token was found for username: {user}')


def oc_login(server=None, token=None):
    log.info('performing oc-login')
    config = _load_kube_config()
    cmd = _build_oc_login_cmd(config, server, token)
    run_command(cmd)
