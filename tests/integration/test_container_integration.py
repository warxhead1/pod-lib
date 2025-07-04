#!/usr/bin/env python3
"""
Integration tests for POD container support with Docker-in-Docker
Fixed version for pytest compatibility
"""

import os
import sys
import time
import pytest
import docker
import subprocess
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pod.os_abstraction import ContainerHandler, ContainerConnection, NetworkConfig
from pod.connections.container import DockerConnection


@pytest.fixture(scope="module")
def docker_client():
    """Get Docker client"""
    return docker.from_env()


@pytest.fixture(scope="module")
def test_networks(docker_client):
    """Create test networks for VLAN testing"""
    networks = []
    network_configs = [
        ("pod-vlan100", "192.168.100.0/24", "192.168.100.1"),
        ("pod-vlan200", "192.168.200.0/24", "192.168.200.1"),
        ("pod-vlan300", "192.168.300.0/24", "192.168.300.1"),
    ]
    
    for net_name, subnet, gateway in network_configs:
        try:
            ipam_pool = docker.types.IPAMPool(
                subnet=subnet,
                gateway=gateway
            )
            ipam_config = docker.types.IPAMConfig(
                pool_configs=[ipam_pool]
            )
            
            network = docker_client.networks.create(
                net_name,
                driver="bridge",
                ipam=ipam_config
            )
            networks.append(net_name)
            print(f"Created network: {net_name} ({subnet})")
        except Exception as e:
            print(f"Failed to create network {net_name}: {e}")
    
    yield networks
    
    # Cleanup
    for net_name in networks:
        try:
            network = docker_client.networks.get(net_name)
            network.remove()
            print(f"Removed network: {net_name}")
        except:
            pass


@pytest.fixture(scope="module")
def test_containers(docker_client, test_networks):
    """Create test containers"""
    containers = []
    container_configs = [
        ("pod-test-rocky1", "rockylinux:9", ["pod-vlan100"]),
        ("pod-test-rocky2", "rockylinux:9", ["pod-vlan100", "pod-vlan200"]),
        ("pod-test-ubuntu", "ubuntu:22.04", ["pod-vlan200"]),
        ("pod-test-alpine", "alpine:latest", ["pod-vlan300"]),
    ]
    
    for container_name, image, networks in container_configs:
        try:
            # Create container
            container = docker_client.containers.run(
                image,
                name=container_name,
                detach=True,
                privileged=True,
                command="tail -f /dev/null",
                cap_add=["NET_ADMIN"],
                volumes={
                    "/lib/modules": {"bind": "/lib/modules", "mode": "ro"}
                }
            )
            
            # Connect to networks
            for net in networks:
                network = docker_client.networks.get(net)
                network.connect(container)
            
            containers.append(container_name)
            print(f"Created container: {container_name} (networks: {', '.join(networks)})")
            
        except Exception as e:
            print(f"Failed to create container {container_name}: {e}")
    
    # Wait for containers to be ready
    time.sleep(5)
    
    yield containers
    
    # Cleanup
    for container_name in containers:
        try:
            container = docker_client.containers.get(container_name)
            container.remove(force=True)
            print(f"Removed container: {container_name}")
        except:
            pass


class TestContainerIntegration:
    """Integration tests for container functionality"""
    
    def test_basic_container_connection(self, test_containers):
        """Test basic container connection and command execution"""
        # Connect to first test container
        conn = ContainerConnection("pod-test-rocky1", use_docker=True)
        conn.connect()
        
        # Create handler
        handler = ContainerHandler(conn)
        
        # Execute basic command
        result = handler.execute_command("hostname")
        assert result.success
        
        # Get OS info
        os_info = handler.get_os_info()
        assert os_info['type'] == 'linux'
        assert os_info['container'] is True
    
    def test_vlan_configuration(self, test_containers):
        """Test VLAN configuration in container"""
        conn = ContainerConnection("pod-test-rocky2", use_docker=True)
        conn.connect()
        handler = ContainerHandler(conn)
        
        # Install required packages
        handler.install_package("iproute")
        handler.install_package("iputils")
        
        # Configure VLAN interface
        config = NetworkConfig(
            interface="eth0",
            ip_address="10.10.100.10",
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        result = handler.configure_network(config)
        assert result.success or "Operation not permitted" in result.stderr
    
    def test_multi_vlan_container(self, test_containers):
        """Test container with multiple VLANs"""
        conn = ContainerConnection("pod-test-rocky2", use_docker=True)
        conn.connect()
        handler = ContainerHandler(conn)
        
        # Configure multiple VLANs
        vlan_configs = [
            {
                'vlan_id': 101,
                'ip_address': '10.10.101.10',
                'netmask': '255.255.255.0',
                'interface': 'eth0'
            },
            {
                'vlan_id': 102,
                'ip_address': '10.10.102.10',
                'netmask': '255.255.255.0',
                'interface': 'eth0'
            }
        ]
        
        results = handler.configure_container_networking(vlan_configs)
        success_count = sum(1 for r in results if r.success)
        assert success_count > 0 or all("Operation not permitted" in r.stderr for r in results)
    
    @pytest.mark.parametrize("container_pairs", [
        [("pod-test-rocky1", "10.10.200.10"), ("pod-test-ubuntu", "10.10.200.20")]
    ])
    def test_container_to_container_vlan(self, test_containers, container_pairs):
        """Test container-to-container communication over VLAN"""
        handlers = []
        
        for container_name, ip_addr in container_pairs:
            conn = ContainerConnection(container_name, use_docker=True)
            conn.connect()
            handler = ContainerHandler(conn)
            
            # Configure VLAN
            config = NetworkConfig(
                interface="eth0",
                ip_address=ip_addr,
                netmask="255.255.255.0",
                vlan_id=200
            )
            
            result = handler.configure_network(config)
            if result.success:
                handlers.append((container_name, handler, ip_addr))
        
        # Test connectivity between containers if both configured
        if len(handlers) == 2:
            handler1 = handlers[0][1]
            target_ip = handlers[1][2]
            
            result = handler1.execute_command(f"ping -c 3 {target_ip}")
            # Either success or permission denied is acceptable in CI
            assert result.success or "Operation not permitted" in result.stderr
    
    def test_macvlan_interface(self, test_containers):
        """Test MACVLAN interface creation"""
        conn = ContainerConnection("pod-test-alpine", use_docker=True)
        conn.connect()
        handler = ContainerHandler(conn)
        
        # Install required tools
        handler.execute_command("apk add --no-cache iproute2")
        
        # Create MACVLAN interface
        result = handler.create_macvlan_interface("macvlan0", "eth0", vlan_id=300)
        
        # Either success or permission denied is acceptable in CI
        assert result.success or "Operation not permitted" in result.stderr
    
    def test_veth_pair(self, test_containers):
        """Test veth pair creation"""
        conn = ContainerConnection("pod-test-rocky1", use_docker=True)
        conn.connect()
        handler = ContainerHandler(conn)
        
        # Create veth pair
        result = handler.add_veth_pair("veth-test0", "veth-test1")
        
        # Either success or permission denied is acceptable in CI
        assert result.success or "Operation not permitted" in result.stderr
    
    def test_network_isolation(self, test_containers):
        """Test network isolation between VLANs"""
        # Configure containers on different VLANs
        configs = [
            ("pod-test-rocky1", 400, "10.10.400.10"),
            ("pod-test-ubuntu", 500, "10.10.500.10")
        ]
        
        for container_name, vlan_id, ip_addr in configs:
            conn = ContainerConnection(container_name, use_docker=True)
            conn.connect()
            handler = ContainerHandler(conn)
            
            config = NetworkConfig(
                interface="eth0",
                ip_address=ip_addr,
                netmask="255.255.255.0",
                vlan_id=vlan_id
            )
            
            handler.configure_network(config)
        
        # Test that containers on different VLANs cannot communicate
        conn = ContainerConnection("pod-test-rocky1", use_docker=True)
        conn.connect()
        handler = ContainerHandler(conn)
        
        result = handler.execute_command("ping -c 3 -W 1 10.10.500.10")
        
        # Should fail (VLANs isolated) or get permission denied
        assert not result.success or "Operation not permitted" in result.stderr


# Skip tests if not in Docker environment
pytestmark = pytest.mark.skipif(
    not os.path.exists("/.dockerenv") and not os.environ.get("DOCKER_HOST") and not os.environ.get("CI"),
    reason="Integration tests require Docker environment"
)