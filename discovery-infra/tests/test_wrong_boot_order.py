import pytest
import time

from tests.base_test import BaseTest


class TestWrongBootOrder(BaseTest):
    @pytest.mark.regression
    def test_wrong_boot_order_one_node(self, nodes, cluster):
        # Define new cluster
        new_cluster = cluster()

        # Change boot order of a random node
        node = nodes.get_random_node()
        node.set_boot_order(cd_first=True)

        # Start cluster install
        new_cluster.prepare_for_install(nodes)
        new_cluster.start_install()
        new_cluster.wait_for_installing_in_progress()

        # Wait until wrong boot order
        new_cluster.wait_for_one_host_to_be_in_wrong_boot_order()
        new_cluster.wait_for_cluster_in_installing_pending_user_action_status()

        # Reboot required nodes into HD
        node.shutdown()
        node.set_boot_order(cd_first=False)
        node.start()

        # wait until all nodes are in Installed status, will fail in case one host in error
        new_cluster.wait_for_cluster_in_installing_in_progress_status()
        new_cluster.wait_for_hosts_to_install()
        new_cluster.wait_for_install()

    @pytest.mark.regression
    def test_wrong_boot_order_all_nodes(self, nodes, cluster):
        # Define new cluster
        new_cluster = cluster()

        # Change boot order of all the nodes
        for n in nodes:
            n.set_boot_order(cd_first=True)

        # Start cluster install
        new_cluster.prepare_for_install(nodes)
        new_cluster.start_install()
        new_cluster.wait_for_installing_in_progress()

        # Wait until wrong boot order - all hosts except bootstrap
        new_cluster.wait_for_hosts_to_be_in_wrong_boot_order(len(nodes)-1)
        new_cluster.wait_for_cluster_in_installing_pending_user_action_status()

        # Reboot required nodes into HD
        bootstrap = nodes.get_bootstrap_node()
        for n in nodes:
            if n.name == bootstrap.name:
                continue
            n.shutdown()
            n.set_boot_order(cd_first=False)
            n.start()

        # Wait until installation continued.
        new_cluster.wait_for_cluster_in_installing_in_progress_status()

        # Wait until bootstrap is in wrong boot order
        new_cluster.wait_for_one_host_to_be_in_wrong_boot_order()
        new_cluster.wait_for_cluster_in_installing_pending_user_action_status()

        # Reboot bootstrap into HD
        bootstrap.shutdown()
        bootstrap.set_boot_order(cd_first=False)
        bootstrap.start()

        new_cluster.wait_for_hosts_to_install()
        new_cluster.wait_for_install()

    @pytest.mark.regression
    def test_on_wrong_boot_order_ignore_hosts_timeout(self, nodes, cluster):
        # Define new cluster
        new_cluster = cluster()

        # Change boot order all the nodes
        for n in nodes:
            n.set_boot_order(cd_first=True)

        # Start cluster install
        new_cluster.prepare_for_install(nodes)
        new_cluster.start_install()
        new_cluster.wait_for_installing_in_progress()

        # Wait until wrong boot order - all hosts except bootstrap
        new_cluster.wait_for_hosts_to_be_in_wrong_boot_order(len(nodes)-1)
        new_cluster.wait_for_cluster_in_installing_pending_user_action_status()

        # Wait for an hour +
        time.sleep(65 * 60)

        # Reboot required into HD
        for n in nodes:
            n.shutdown()
            n.set_boot_order(cd_first=False)
            n.start()

        # Wait until installation continued.
        new_cluster.wait_for_cluster_in_installing_in_progress_status()
        new_cluster.wait_for_hosts_to_install()
        new_cluster.wait_for_install()
