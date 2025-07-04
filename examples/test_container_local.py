#!/usr/bin/env python3
"""
Local test script for POD container functionality
This can run on your local machine with Docker installed
"""

import os
import sys
import time
import subprocess
import docker

# Add POD to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pod.os_abstraction import ContainerHandler, ContainerConnection, NetworkConfig


def run_command(cmd):
    """Run a shell command"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def test_local_containers():
    """Test POD with local Docker containers"""
    print("POD Container Support - Local Test")
    print("="*50)
    
    docker_client = docker.from_env()
    
    # 1. Create test containers
    print("\n1. Creating test containers...")
    
    containers = []
    try:
        # Create a Rocky Linux container
        print("   Creating Rocky Linux container...")
        rocky = docker_client.containers.run(
            "rockylinux:9",
            name="pod-test-rocky",
            detach=True,
            remove=True,
            privileged=True,
            command="tail -f /dev/null",
            cap_add=["NET_ADMIN"]
        )
        containers.append(rocky)
        print("   ✓ Rocky Linux container created")
        
        # Create an Alpine container
        print("   Creating Alpine container...")
        alpine = docker_client.containers.run(
            "alpine:latest",
            name="pod-test-alpine",
            detach=True,
            remove=True,
            privileged=True,
            command="tail -f /dev/null",
            cap_add=["NET_ADMIN"]
        )
        containers.append(alpine)
        print("   ✓ Alpine container created")
        
    except docker.errors.APIError as e:
        print(f"   ✗ Failed to create containers: {e}")
        return False
        
    # Wait for containers to start
    time.sleep(3)
    
    try:
        # 2. Test basic container operations
        print("\n2. Testing basic container operations...")
        
        # Connect to Rocky container
        conn = ContainerConnection("pod-test-rocky", use_docker=True)
        conn.connect()
        handler = ContainerHandler(conn)
        
        # Execute command
        result = handler.execute_command("cat /etc/os-release | grep PRETTY_NAME")
        print(f"   OS: {result.stdout.strip()}")
        
        # Get network interfaces
        interfaces = handler.get_network_interfaces()
        print(f"   Network interfaces: {len(interfaces)} found")
        for iface in interfaces:
            if iface.ip_addresses:
                print(f"     - {iface.name}: {', '.join(iface.ip_addresses)}")
                
        # 3. Test package installation
        print("\n3. Testing package installation...")
        
        # Install network tools
        print("   Installing iproute...")
        result = handler.install_package("iproute")
        if result.success:
            print("   ✓ Package installed successfully")
        else:
            print(f"   ✗ Package installation failed: {result.stderr}")
            
        # 4. Test VLAN configuration (will work if host supports it)
        print("\n4. Testing VLAN configuration...")
        
        # First check if we can load 8021q module
        result = handler.execute_command("modprobe 8021q")
        if result.success:
            print("   ✓ 8021q module loaded")
            
            # Try to create a VLAN interface
            config = NetworkConfig(
                interface="eth0",
                ip_address="192.168.100.10",
                netmask="255.255.255.0",
                vlan_id=100
            )
            
            result = handler.configure_network(config)
            if result.success:
                print(f"   ✓ VLAN {config.vlan_id} configured")
                
                # Check if VLAN interface exists
                result = handler.execute_command("ip addr show eth0.100")
                if result.success:
                    print("   ✓ VLAN interface created successfully")
                    print(f"     {result.stdout.strip()[:100]}...")
            else:
                print(f"   ℹ VLAN configuration not supported in this environment")
        else:
            print("   ℹ 8021q module not available (expected in containers)")
            
        # 5. Test Alpine container with different package manager
        print("\n5. Testing Alpine container...")
        
        conn2 = ContainerConnection("pod-test-alpine", use_docker=True)
        conn2.connect()
        handler2 = ContainerHandler(conn2)
        
        # Alpine uses apk
        result = handler2.execute_command("apk --version")
        print(f"   Package manager: {result.stdout.strip()}")
        
        # Get OS info
        os_info = handler2.get_os_info()
        print(f"   Container OS: {os_info.get('distribution', 'Unknown')}")
        print(f"   Container ID: {os_info.get('container_id', 'Unknown')}")
        
        # 6. Test inter-container operations
        print("\n6. Testing container networking...")
        
        # Get Rocky container IP
        rocky_ip = None
        interfaces = handler.get_network_interfaces()
        for iface in interfaces:
            if iface.name == "eth0" and iface.ip_addresses:
                rocky_ip = iface.ip_addresses[0]
                break
                
        if rocky_ip:
            print(f"   Rocky container IP: {rocky_ip}")
            
            # Try to ping from Alpine to Rocky
            result = handler2.execute_command(f"ping -c 3 {rocky_ip}")
            if result.success:
                print("   ✓ Containers can communicate")
            else:
                print("   ✗ Container communication failed")
                
        # 7. Test file operations
        print("\n7. Testing file operations...")
        
        # Create a test file locally
        test_content = "Hello from POD library!"
        with open("/tmp/pod_test.txt", "w") as f:
            f.write(test_content)
            
        # Upload to container
        if handler.upload_file("/tmp/pod_test.txt", "/tmp/pod_uploaded.txt"):
            print("   ✓ File uploaded successfully")
            
            # Verify content
            result = handler.execute_command("cat /tmp/pod_uploaded.txt")
            if result.stdout.strip() == test_content:
                print("   ✓ File content verified")
            else:
                print("   ✗ File content mismatch")
        else:
            print("   ✗ File upload failed")
            
        # Clean up local test file
        os.remove("/tmp/pod_test.txt")
        
        print("\n" + "="*50)
        print("✓ Local container tests completed!")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        print("\nCleaning up containers...")
        for container in containers:
            try:
                container.stop()
                container.remove()
            except:
                pass
        print("✓ Cleanup complete")
        
    return True


def test_docker_compose_setup():
    """Test the Docker Compose setup"""
    print("\nDocker Compose Setup Test")
    print("="*50)
    
    if not os.path.exists("docker-compose.yml"):
        print("✗ docker-compose.yml not found")
        return False
        
    print("✓ docker-compose.yml exists")
    
    # Check if we can parse it
    success, stdout, stderr = run_command("docker-compose config")
    if success:
        print("✓ Docker Compose configuration is valid")
    else:
        print(f"✗ Docker Compose configuration error: {stderr}")
        return False
        
    print("\nTo run full integration tests with Docker-in-Docker:")
    print("  ./run_integration_tests.sh")
    
    return True


def main():
    """Main entry point"""
    print("POD Container Support Testing")
    print("="*50)
    
    # Check Docker
    try:
        client = docker.from_env()
        client.ping()
        print("✓ Docker is running")
    except:
        print("✗ Docker is not running or not installed")
        print("  Please ensure Docker is installed and running")
        return 1
        
    # Run local tests
    if test_local_containers():
        test_docker_compose_setup()
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())