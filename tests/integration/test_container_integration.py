#!/usr/bin/env python3
"""
Integration tests for POD container support with Docker-in-Docker
"""

import os
import sys
import time
import docker
import subprocess
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pod.os_abstraction import ContainerHandler, ContainerConnection, NetworkConfig
from pod.connections.container import DockerConnection


class TestContainerIntegration:
    """Integration tests for container functionality"""
    
    def __init__(self):
        self.docker_client = docker.from_env()
        self.test_containers = []
        self.test_networks = []
        
    def setup(self):
        """Set up test environment"""
        print("Setting up test environment...")
        
        # Clean up any existing test containers
        self.cleanup()
        
        # Create test networks with VLAN tags
        self.create_test_networks()
        
        # Create test containers
        self.create_test_containers()
        
        # Wait for containers to be ready
        time.sleep(5)
        
    def cleanup(self):
        """Clean up test resources"""
        print("Cleaning up test resources...")
        
        # Remove test containers
        for container_name in self.test_containers:
            try:
                container = self.docker_client.containers.get(container_name)
                container.remove(force=True)
                print(f"  Removed container: {container_name}")
            except:
                pass
                
        # Remove test networks
        for network_name in self.test_networks:
            try:
                network = self.docker_client.networks.get(network_name)
                network.remove()
                print(f"  Removed network: {network_name}")
            except:
                pass
                
    def create_test_networks(self):
        """Create Docker networks for VLAN testing"""
        networks = [
            ("pod-vlan100", "192.168.100.0/24", "192.168.100.1"),
            ("pod-vlan200", "192.168.200.0/24", "192.168.200.1"),
            ("pod-vlan300", "192.168.300.0/24", "192.168.300.1"),
        ]
        
        for net_name, subnet, gateway in networks:
            try:
                ipam_pool = docker.types.IPAMPool(
                    subnet=subnet,
                    gateway=gateway
                )
                ipam_config = docker.types.IPAMConfig(
                    pool_configs=[ipam_pool]
                )
                
                network = self.docker_client.networks.create(
                    net_name,
                    driver="bridge",
                    ipam=ipam_config
                )
                self.test_networks.append(net_name)
                print(f"  Created network: {net_name} ({subnet})")
            except Exception as e:
                print(f"  Failed to create network {net_name}: {e}")
                
    def create_test_containers(self):
        """Create test containers"""
        containers = [
            ("pod-test-rocky1", "rockylinux:9", ["pod-vlan100"]),
            ("pod-test-rocky2", "rockylinux:9", ["pod-vlan100", "pod-vlan200"]),
            ("pod-test-ubuntu", "ubuntu:22.04", ["pod-vlan200"]),
            ("pod-test-alpine", "alpine:latest", ["pod-vlan300"]),
        ]
        
        for container_name, image, networks in containers:
            try:
                # Create container
                container = self.docker_client.containers.run(
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
                    network = self.docker_client.networks.get(net)
                    network.connect(container)
                    
                self.test_containers.append(container_name)
                print(f"  Created container: {container_name} (networks: {', '.join(networks)})")
                
            except Exception as e:
                print(f"  Failed to create container {container_name}: {e}")
                
    def test_basic_container_connection(self):
        """Test basic container connection and command execution"""
        print("\n=== Test: Basic Container Connection ===")
        
        # Connect to first test container
        conn = ContainerConnection("pod-test-rocky1", use_docker=True)
        conn.connect()
        
        # Create handler
        handler = ContainerHandler(conn)
        
        # Execute basic command
        result = handler.execute_command("hostname")
        print(f"Hostname: {result.stdout.strip()}")
        assert result.success
        
        # Get OS info
        os_info = handler.get_os_info()
        print(f"OS: {os_info['distribution']} {os_info['version']}")
        assert os_info['type'] == 'linux'
        assert os_info['container'] is True
        
        return True
        
    def test_vlan_configuration(self):
        """Test VLAN configuration in container"""
        print("\n=== Test: VLAN Configuration ===")
        
        conn = ContainerConnection("pod-test-rocky2", use_docker=True)
        conn.connect()
        handler = ContainerHandler(conn)
        
        # Install required packages
        print("Installing network tools...")
        handler.install_package("iproute")
        handler.install_package("iputils")
        
        # Configure VLAN interface
        config = NetworkConfig(
            interface="eth0",
            ip_address="10.10.100.10",
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        print(f"Configuring VLAN {config.vlan_id}...")
        result = handler.configure_network(config)
        
        if result.success:
            print("VLAN configured successfully")
            
            # Verify VLAN interface exists
            ifaces = handler.get_network_interfaces()
            vlan_iface = None
            for iface in ifaces:
                if f"eth0.{config.vlan_id}" in iface.name:
                    vlan_iface = iface
                    break
                    
            if vlan_iface:
                print(f"VLAN interface found: {vlan_iface.name}")
                print(f"IP addresses: {vlan_iface.ip_addresses}")
            else:
                print("Warning: VLAN interface not found in interface list")
        else:
            print(f"VLAN configuration failed: {result.stderr}")
            
        return result.success
        
    def test_multi_vlan_container(self):
        """Test container with multiple VLANs"""
        print("\n=== Test: Multi-VLAN Container ===")
        
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
        
        print("Configuring multiple VLANs...")
        results = handler.configure_container_networking(vlan_configs)
        
        success_count = sum(1 for r in results if r.success)
        print(f"Successfully configured {success_count}/{len(vlan_configs)} VLANs")
        
        # List all interfaces
        interfaces = handler.get_network_interfaces()
        print("\nNetwork interfaces:")
        for iface in interfaces:
            if iface.ip_addresses:
                print(f"  {iface.name}: {', '.join(iface.ip_addresses)}")
                if iface.vlan_id:
                    print(f"    VLAN ID: {iface.vlan_id}")
                    
        return success_count > 0
        
    def test_container_to_container_vlan(self):
        """Test container-to-container communication over VLAN"""
        print("\n=== Test: Container-to-Container VLAN Communication ===")
        
        # Set up two containers on same VLAN
        containers = [
            ("pod-test-rocky1", "10.10.200.10"),
            ("pod-test-ubuntu", "10.10.200.20")
        ]
        
        handlers = []
        for container_name, ip_addr in containers:
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
            
            print(f"Configuring {container_name} with IP {ip_addr} on VLAN 200...")
            result = handler.configure_network(config)
            
            if result.success:
                handlers.append((container_name, handler, ip_addr))
            else:
                print(f"Failed to configure {container_name}")
                
        # Test connectivity between containers
        if len(handlers) == 2:
            print("\nTesting connectivity between containers...")
            
            # From first container, ping second
            handler1 = handlers[0][1]
            target_ip = handlers[1][2]
            
            result = handler1.execute_command(f"ping -c 3 {target_ip}")
            
            if result.success:
                print(f"✓ Containers can communicate over VLAN 200")
                print(f"  Ping output: {result.stdout.strip()}")
                return True
            else:
                print(f"✗ Communication failed: {result.stderr}")
                return False
        else:
            print("Not enough containers configured for test")
            return False
            
    def test_macvlan_interface(self):
        """Test MACVLAN interface creation"""
        print("\n=== Test: MACVLAN Interface ===")
        
        conn = ContainerConnection("pod-test-alpine", use_docker=True)
        conn.connect()
        handler = ContainerHandler(conn)
        
        # Install required tools
        handler.execute_command("apk add --no-cache iproute2")
        
        # Create MACVLAN interface
        print("Creating MACVLAN interface...")
        result = handler.create_macvlan_interface("macvlan0", "eth0", vlan_id=300)
        
        if result.success:
            print("MACVLAN interface created successfully")
            
            # Configure IP on MACVLAN
            handler.execute_command("ip addr add 10.10.300.50/24 dev macvlan0")
            handler.execute_command("ip link set macvlan0 up")
            
            # Verify interface
            result = handler.execute_command("ip addr show macvlan0")
            print(f"MACVLAN interface details:\n{result.stdout}")
            
            return True
        else:
            print(f"MACVLAN creation failed: {result.stderr}")
            return False
            
    def test_veth_pair(self):
        """Test veth pair creation"""
        print("\n=== Test: Veth Pair Creation ===")
        
        conn = ContainerConnection("pod-test-rocky1", use_docker=True)
        conn.connect()
        handler = ContainerHandler(conn)
        
        # Create veth pair
        print("Creating veth pair...")
        result = handler.add_veth_pair("veth-test0", "veth-test1")
        
        if result.success:
            print("Veth pair created successfully")
            
            # Configure veth interfaces
            handler.execute_command("ip addr add 10.20.0.1/24 dev veth-test0")
            handler.execute_command("ip addr add 10.20.0.2/24 dev veth-test1")
            handler.execute_command("ip link set veth-test0 up")
            handler.execute_command("ip link set veth-test1 up")
            
            # Verify interfaces
            result = handler.execute_command("ip link show | grep veth-test")
            print(f"Veth interfaces:\n{result.stdout}")
            
            return True
        else:
            print(f"Veth creation failed: {result.stderr}")
            return False
            
    def test_network_isolation(self):
        """Test network isolation between VLANs"""
        print("\n=== Test: Network Isolation Between VLANs ===")
        
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
            
            print(f"Configuring {container_name} on VLAN {vlan_id}...")
            handler.configure_network(config)
            
        # Test that containers on different VLANs cannot communicate
        conn = ContainerConnection("pod-test-rocky1", use_docker=True)
        conn.connect()
        handler = ContainerHandler(conn)
        
        print("\nTesting isolation: VLAN 400 -> VLAN 500...")
        result = handler.execute_command("ping -c 3 -W 1 10.10.500.10")
        
        if result.success:
            print("✗ VLANs are NOT isolated (unexpected)")
            return False
        else:
            print("✓ VLANs are properly isolated")
            return True
            
    def run_all_tests(self):
        """Run all integration tests"""
        print("\n" + "="*60)
        print("POD Container Integration Tests")
        print("="*60)
        
        self.setup()
        
        tests = [
            ("Basic Container Connection", self.test_basic_container_connection),
            ("VLAN Configuration", self.test_vlan_configuration),
            ("Multi-VLAN Container", self.test_multi_vlan_container),
            ("Container-to-Container VLAN", self.test_container_to_container_vlan),
            ("MACVLAN Interface", self.test_macvlan_interface),
            ("Veth Pair Creation", self.test_veth_pair),
            ("Network Isolation", self.test_network_isolation)
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                print(f"\nRunning: {test_name}")
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"ERROR in {test_name}: {e}")
                import traceback
                traceback.print_exc()
                results.append((test_name, False))
                
        # Print summary
        print("\n" + "="*60)
        print("Test Summary")
        print("="*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status}: {test_name}")
            
        print(f"\nTotal: {passed}/{total} tests passed")
        
        self.cleanup()
        
        return passed == total


def main():
    """Main entry point"""
    # Check if running in Docker
    if not os.path.exists("/.dockerenv") and not os.environ.get("DOCKER_HOST"):
        print("WARNING: This test should be run inside the Docker environment")
        print("Run: docker-compose up pod-controller")
        
    tester = TestContainerIntegration()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()