import os

from waiting import wait
from typing import Optional, Union

from kubernetes import client, config
from kubernetes.config.kube_config import Configuration

from test_infra.consts import *
from test_infra.utils import get_random_name

WAIT_FOR_CRD_STATUS_TIMEOUT = 5

_GROUP = 'adi.io.my.domain'
_VERSION = 'v1alpha1'
_NAMESPACE = os.environ.get('NAMESPACE', 'assisted-installer')


def _get_kube_api_client():
    return client.ApiClient(_get_kube_api_configuration())


def _get_kube_api_configuration():
    configuration = Configuration()
    config.load_kube_config(
        config_file=os.environ.get('KUBECONFIG'),
        client_configuration=configuration
    )
    return configuration


class ClusterDeploymentCRD(object):

    def __init__(self):
        self.openshift_version = None
        self.provision_requirements = None
        self.pull_secret = None

        self.__name = None

        self._crds_api = client.CustomObjectsApi(_get_kube_api_client())

    @property
    def id(self) -> str:
        return self.status()['id']

    @property
    def name(self) -> str:
        return self.__name

    def spec(self) -> dict:
        if self.__name is None:
            return {}

        return self.get()['spec']

    def status(
        self,
        timeout: Optional[Union[int, float]] = WAIT_FOR_CRD_STATUS_TIMEOUT
    ) -> dict:

        assert self.name is not None, 'cluster name must be set'

        return wait(
            self._get_status,
            timeout_seconds=timeout,
            expected_exceptions=[KeyError],
            sleep_seconds=0.5,
            waiting_for=f'cluster {self.name} status'
        )

    def _get_status(self) -> dict:
        return self.get()['status']

    def create(self, **kwargs) -> 'ClusterDeploymentCRD':
        self.__name = kwargs.pop('name', get_random_name(length=10))
        self.openshift_version = kwargs.pop(
            'openshiftVersion', DEFAULT_OPENSHIFT_VERSION
        )
        self._set_provision_requirements(
            control_plane_agents=kwargs.pop('controlPlaneAgents', 3),
            agent_selector=kwargs.pop('agentSelector', None)
        )
        self._set_pull_secret(secret=kwargs.pop('secret', None))
        body = {
            'apiVersion': f'{_GROUP}/{_VERSION}',
            'kind': 'Cluster',      # todo: update to cluster deployment
            'metadata': {
                'name': self.name,
                'namespace': _NAMESPACE
            },
            'spec': {
                'name': self.name,
                'openshiftVersion': self.openshift_version,
                'pullSecretRef': self.pull_secret.ref,
                'provisionRequirements': self.provision_requirements
            },
        }
        body['spec'].update(kwargs)
        self._crds_api.create_namespaced_custom_object(
            group=_GROUP,
            version=_VERSION,
            namespace=_NAMESPACE,
            plural='clusters',
            body=body
        )
        return self

    def _set_provision_requirements(
        self,
        control_plane_agents: Optional[int] = 3,
        agent_selector: Optional[dict] = None
    ) -> None:

        self.provision_requirements = {
            'controlPlaneAgents': control_plane_agents,
            'agentSelector': agent_selector or {'matchLabels': {}}
        }

    def _set_pull_secret(self, secret: Optional[str] = None) -> None:
        if isinstance(self.pull_secret, PullSecretCRD):
            return
        self.pull_secret = PullSecretCRD(self.name, secret)
        self.pull_secret.create_if_not_exist()

    def get(self) -> dict:
        return self._crds_api.get_namespaced_custom_object(
            group=_GROUP,
            version=_VERSION,
            namespace=_NAMESPACE,
            plural='clusters',
            name=self.name
        )

    def delete(self) -> None:
        if self.__name is None:
            return

        self._crds_api.delete_namespaced_custom_object(
            group=_GROUP,
            version=_VERSION,
            namespace=_NAMESPACE,
            plural='clusters',
            name=self.name
        )


class PullSecretCRD(object):

    all_secrets = {}

    def __init__(self, name: str, secret: Optional[str] = None):
        self.__name = name

        if not secret:
            secret = os.environ['PULL_SECRET']
        self.secret = secret

        self._v1_api = client.CoreV1Api(_get_kube_api_client())

    @property
    def name(self) -> str:
        return self.__name

    @property
    def ref(self) -> dict:
        return {
            'name': self.name,
            'namespace': _NAMESPACE
        }

    def create_if_not_exist(self) -> None:
        if self.name in self.all_secrets:
            return

        self._v1_api.create_namespaced_secret(
            namespace=_NAMESPACE,
            body={
                'apiVersion': 'v1',
                'kind': 'Secret',
                'metadata': {
                    'name': self.name,
                    'namespace': _NAMESPACE,
                },
                'stringData': {
                    'pullSecret': self.secret
                }
            }
        )
        self.all_secrets[self.name] = self

    def delete(self) -> None:
        if self.name not in self.all_secrets:
            return

        self._v1_api.delete_namespaced_secret(
            namespace=_NAMESPACE,
            name=self.name
        )
        self.all_secrets.pop(self.name)
