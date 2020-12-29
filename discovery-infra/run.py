from typing import Union
from test_infra.consts import *


class ClusterConfig(object):

    def __init__(
            self,
            cluster_id: str,
            cluster_name: str,
            namespace: str,
            platform: Union[str, Platforms],
    ):
        self.id = cluster_id

        if not cluster_name.endswith(namespace):
            cluster_name += '-' + namespace

        self.name = cluster_name
        self.namespace = namespace

        if isinstance(platform, str):
            try:
                platform = getattr(Platforms, platform.upper())
            except AttributeError:
                raise ValueError(f'invalid platform: {platform}')

        self.platform = platform


def main(args):
    cluster_config = ClusterConfig(
        cluster_id=args.cluster_id,
        namespace=args.namespace,
