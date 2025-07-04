#!/usr/bin/env python3
"""
Container Capacity and Network Throughput Testing

This script tests how many containers can be deployed on a machine
and measures network throughput between containers on different VLANs.

Usage:
    python container_capacity_test.py --max-containers 50 --vlan-count 5
"""

import asyncio
import json
import time
import logging
import argparse
import sys
import os
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

# Add the POD library to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
pod_root = os.path.join(script_dir, '..', '..')
sys.path.insert(0, pod_root)

from pod.connections.container import DockerConnection
from pod.os_abstraction.container import ContainerHandler
from pod.os_abstraction.base import NetworkConfig


@dataclass
class ContainerInfo:
    """Information about a test container"""
    name: str
    vlan_id: int
    ip_address: str
    port: int
    connection: Optional[DockerConnection] = None
    handler: Optional[ContainerHandler] = None
    startup_time: float = 0.0
    network_config_time: float = 0.0
    status: str = "pending"


@dataclass
class NetworkTestResult:
    """Results from network throughput testing"""
    source_container: str
    target_container: str
    source_vlan: int
    target_vlan: int
    throughput_mbps: float
    latency_ms: float
    packet_loss_percent: float
    test_duration: float
    success: bool
    error_message: str = ""


class ContainerCapacityTester:
    """Test container capacity and network performance"""
    
    def __init__(self, base_image: str = "ubuntu:22.04", 
                 base_vlan_range: Tuple[int, int] = (100, 200)):
        self.base_image = base_image
        self.base_vlan_start, self.base_vlan_end = base_vlan_range
        self.containers: List[ContainerInfo] = []
        self.test_results: List[NetworkTestResult] = []
        self.logger = logging.getLogger(__name__)
        
    def generate_container_configs(self, container_count: int, 
                                 vlan_count: int) -> List[ContainerInfo]:
        """Generate container configurations with VLAN distribution"""
        containers = []
        containers_per_vlan = max(1, container_count // vlan_count)
        
        for i in range(container_count):
            vlan_id = self.base_vlan_start + (i % vlan_count)
            vlan_offset = i // vlan_count
            
            container = ContainerInfo(
                name=f"pod-test-{i:03d}",
                vlan_id=vlan_id,
                ip_address=f"192.168.{vlan_id % 256}.{10 + vlan_offset}",
                port=5000 + i
            )
            containers.append(container)
            
        return containers
    
    async def create_test_container(self, container_info: ContainerInfo) -> bool:
        """Create and configure a single test container"""
        start_time = time.time()
        
        try:
            # Create container with network tools
            connection = DockerConnection(container_info.name, runtime="docker")
            
            # Start container with network tools
            create_cmd = [
                "docker", "run", "-d", "--name", container_info.name,
                "--cap-add", "NET_ADMIN",  # Required for VLAN configuration
                "--privileged",  # Required for network namespace manipulation
                self.base_image,
                "sleep", "3600"  # Keep container running
            ]
            
            import subprocess
            result = subprocess.run(create_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"Failed to create container {container_info.name}: {result.stderr}")
                container_info.status = "failed"
                return False
            
            # Connect to container
            connection.connect()
            handler = ContainerHandler(connection)
            
            container_info.connection = connection
            container_info.handler = handler
            container_info.startup_time = time.time() - start_time
            
            # Install network tools
            self.logger.info(f"Installing network tools in {container_info.name}")
            handler.install_package("iproute2")
            handler.install_package("iputils-ping")
            handler.install_package("iperf3")
            
            # Configure VLAN network
            network_start = time.time()
            config = NetworkConfig(
                interface="eth0",
                vlan_id=container_info.vlan_id,
                ip_address=container_info.ip_address,
                netmask="255.255.255.0",
                gateway=f"192.168.{container_info.vlan_id % 256}.1"
            )
            
            result = handler.configure_network(config)
            container_info.network_config_time = time.time() - network_start
            
            if result.success:
                container_info.status = "ready"
                self.logger.info(f"Container {container_info.name} ready on VLAN {container_info.vlan_id}")
                return True
            else:
                container_info.status = "network_failed"
                self.logger.error(f"Network config failed for {container_info.name}: {result.stderr}")
                return False
                
        except Exception as e:
            container_info.status = "error"
            self.logger.error(f"Error setting up container {container_info.name}: {e}")
            return False
    
    async def deploy_containers(self, container_configs: List[ContainerInfo], 
                              max_concurrent: int = 5) -> Dict[str, Any]:
        """Deploy containers with concurrency control"""
        self.logger.info(f"Deploying {len(container_configs)} containers...")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def deploy_with_semaphore(container_info):
            async with semaphore:
                return await self.create_test_container(container_info)
        
        start_time = time.time()
        tasks = [deploy_with_semaphore(container) for container in container_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        deployment_time = time.time() - start_time
        successful = sum(1 for r in results if r is True)
        
        self.containers = container_configs
        
        return {
            "total_containers": len(container_configs),
            "successful_deployments": successful,
            "failed_deployments": len(container_configs) - successful,
            "deployment_time": deployment_time,
            "containers_per_second": len(container_configs) / deployment_time,
            "average_startup_time": sum(c.startup_time for c in container_configs if c.startup_time > 0) / max(1, successful),
            "average_network_config_time": sum(c.network_config_time for c in container_configs if c.network_config_time > 0) / max(1, successful)
        }
    
    def start_iperf_servers(self) -> Dict[str, Any]:
        """Start iperf3 servers in ready containers"""
        server_count = 0
        failed_servers = 0
        
        for container in self.containers:
            if container.status == "ready" and container.handler:
                try:
                    # Start iperf3 server
                    result = container.handler.execute_command(
                        f"iperf3 -s -p {container.port} -D"
                    )
                    if result.success:
                        server_count += 1
                        self.logger.info(f"iperf3 server started on {container.name}:{container.port}")
                    else:
                        failed_servers += 1
                        self.logger.error(f"Failed to start iperf3 server on {container.name}")
                except Exception as e:
                    failed_servers += 1
                    self.logger.error(f"Error starting iperf3 server on {container.name}: {e}")
        
        return {
            "servers_started": server_count,
            "server_failures": failed_servers
        }
    
    def run_network_test(self, source: ContainerInfo, target: ContainerInfo, 
                        duration: int = 10) -> NetworkTestResult:
        """Run network throughput test between two containers"""
        start_time = time.time()
        
        try:
            if not source.handler or not target.handler:
                raise Exception("Container handlers not available")
            
            # Run iperf3 client test
            cmd = f"iperf3 -c {target.ip_address} -p {target.port} -t {duration} -J"
            result = source.handler.execute_command(cmd, timeout=duration + 30)
            
            test_duration = time.time() - start_time
            
            if not result.success:
                return NetworkTestResult(
                    source_container=source.name,
                    target_container=target.name,
                    source_vlan=source.vlan_id,
                    target_vlan=target.vlan_id,
                    throughput_mbps=0.0,
                    latency_ms=0.0,
                    packet_loss_percent=100.0,
                    test_duration=test_duration,
                    success=False,
                    error_message=result.stderr
                )
            
            # Parse iperf3 JSON output
            try:
                iperf_data = json.loads(result.stdout)
                end_data = iperf_data["end"]["sum_received"]
                
                return NetworkTestResult(
                    source_container=source.name,
                    target_container=target.name,
                    source_vlan=source.vlan_id,
                    target_vlan=target.vlan_id,
                    throughput_mbps=end_data["bits_per_second"] / 1_000_000,
                    latency_ms=0.0,  # iperf3 doesn't provide latency directly
                    packet_loss_percent=0.0,  # Would need separate ping test
                    test_duration=test_duration,
                    success=True
                )
            except (json.JSONDecodeError, KeyError) as e:
                return NetworkTestResult(
                    source_container=source.name,
                    target_container=target.name,
                    source_vlan=source.vlan_id,
                    target_vlan=target.vlan_id,
                    throughput_mbps=0.0,
                    latency_ms=0.0,
                    packet_loss_percent=100.0,
                    test_duration=test_duration,
                    success=False,
                    error_message=f"Failed to parse iperf3 output: {e}"
                )
                
        except Exception as e:
            return NetworkTestResult(
                source_container=source.name,
                target_container=target.name,
                source_vlan=source.vlan_id,
                target_vlan=target.vlan_id,
                throughput_mbps=0.0,
                latency_ms=0.0,
                packet_loss_percent=100.0,
                test_duration=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    def run_throughput_matrix_test(self, test_duration: int = 10, 
                                 max_tests: int = 20) -> List[NetworkTestResult]:
        """Run network tests between containers on different VLANs"""
        ready_containers = [c for c in self.containers if c.status == "ready"]
        
        if len(ready_containers) < 2:
            self.logger.error("Need at least 2 ready containers for network testing")
            return []
        
        # Generate test pairs (different VLANs preferred)
        test_pairs = []
        
        # First, try cross-VLAN tests
        for i, source in enumerate(ready_containers):
            for target in ready_containers[i+1:]:
                if source.vlan_id != target.vlan_id:
                    test_pairs.append((source, target))
                    if len(test_pairs) >= max_tests // 2:
                        break
            if len(test_pairs) >= max_tests // 2:
                break
        
        # Then add some same-VLAN tests
        for i, source in enumerate(ready_containers):
            for target in ready_containers[i+1:]:
                if source.vlan_id == target.vlan_id:
                    test_pairs.append((source, target))
                    if len(test_pairs) >= max_tests:
                        break
            if len(test_pairs) >= max_tests:
                break
        
        self.logger.info(f"Running {len(test_pairs)} network throughput tests...")
        
        results = []
        for i, (source, target) in enumerate(test_pairs):
            self.logger.info(f"Test {i+1}/{len(test_pairs)}: {source.name} -> {target.name} "
                           f"(VLAN {source.vlan_id} -> {target.vlan_id})")
            
            result = self.run_network_test(source, target, test_duration)
            results.append(result)
            
            if result.success:
                self.logger.info(f"  Throughput: {result.throughput_mbps:.2f} Mbps")
            else:
                self.logger.error(f"  Test failed: {result.error_message}")
        
        self.test_results.extend(results)
        return results
    
    def cleanup_containers(self):
        """Clean up all test containers"""
        self.logger.info("Cleaning up test containers...")
        
        for container in self.containers:
            try:
                if container.connection:
                    container.connection.disconnect()
                
                # Remove container
                import subprocess
                subprocess.run(["docker", "rm", "-f", container.name], 
                             capture_output=True)
            except Exception as e:
                self.logger.error(f"Error cleaning up {container.name}: {e}")
    
    def generate_report(self, deployment_stats: Dict[str, Any], 
                       server_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        successful_tests = [r for r in self.test_results if r.success]
        failed_tests = [r for r in self.test_results if not r.success]
        
        cross_vlan_tests = [r for r in successful_tests if r.source_vlan != r.target_vlan]
        same_vlan_tests = [r for r in successful_tests if r.source_vlan == r.target_vlan]
        
        report = {
            "test_summary": {
                "total_containers_requested": len(self.containers),
                "successful_deployments": deployment_stats["successful_deployments"],
                "deployment_success_rate": deployment_stats["successful_deployments"] / len(self.containers) * 100,
                "total_network_tests": len(self.test_results),
                "successful_network_tests": len(successful_tests),
                "failed_network_tests": len(failed_tests)
            },
            "performance_metrics": {
                "deployment_time": deployment_stats["deployment_time"],
                "containers_per_second": deployment_stats["containers_per_second"],
                "average_startup_time": deployment_stats["average_startup_time"],
                "average_network_config_time": deployment_stats["average_network_config_time"]
            },
            "network_performance": {
                "cross_vlan_tests": len(cross_vlan_tests),
                "same_vlan_tests": len(same_vlan_tests),
                "average_throughput_mbps": sum(r.throughput_mbps for r in successful_tests) / max(1, len(successful_tests)),
                "max_throughput_mbps": max((r.throughput_mbps for r in successful_tests), default=0),
                "min_throughput_mbps": min((r.throughput_mbps for r in successful_tests), default=0)
            },
            "detailed_results": {
                "container_details": [asdict(c) for c in self.containers],
                "network_test_results": [asdict(r) for r in self.test_results]
            }
        }
        
        return report


async def main():
    """Main test execution function"""
    parser = argparse.ArgumentParser(description="Container capacity and network testing")
    parser.add_argument("--max-containers", type=int, default=20, 
                       help="Maximum number of containers to test")
    parser.add_argument("--vlan-count", type=int, default=4, 
                       help="Number of VLANs to distribute containers across")
    parser.add_argument("--test-duration", type=int, default=10, 
                       help="Duration for each network test in seconds")
    parser.add_argument("--max-concurrent", type=int, default=5, 
                       help="Maximum concurrent container deployments")
    parser.add_argument("--output", type=str, default="container_test_results.json", 
                       help="Output file for test results")
    parser.add_argument("--verbose", action="store_true", 
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    tester = ContainerCapacityTester()
    
    try:
        # Generate container configurations
        print(f"Generating configurations for {args.max_containers} containers across {args.vlan_count} VLANs...")
        container_configs = tester.generate_container_configs(
            args.max_containers, args.vlan_count
        )
        
        # Deploy containers
        print("Deploying containers...")
        deployment_stats = await tester.deploy_containers(
            container_configs, args.max_concurrent
        )
        
        print(f"Deployment complete: {deployment_stats['successful_deployments']}/{deployment_stats['total_containers']} containers ready")
        print(f"Deployment rate: {deployment_stats['containers_per_second']:.2f} containers/second")
        
        # Start iperf3 servers
        print("Starting network test servers...")
        server_stats = tester.start_iperf_servers()
        print(f"Started {server_stats['servers_started']} iperf3 servers")
        
        # Run network tests
        print("Running network throughput tests...")
        test_results = tester.run_throughput_matrix_test(args.test_duration)
        
        # Generate and save report
        report = tester.generate_report(deployment_stats, server_stats)
        
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print("\n" + "="*60)
        print("CONTAINER CAPACITY TEST RESULTS")
        print("="*60)
        print(f"Total containers deployed: {deployment_stats['successful_deployments']}/{args.max_containers}")
        print(f"Deployment success rate: {report['test_summary']['deployment_success_rate']:.1f}%")
        print(f"Average deployment time: {deployment_stats['average_startup_time']:.2f}s per container")
        print(f"Network tests completed: {len(test_results)}")
        print(f"Average throughput: {report['network_performance']['average_throughput_mbps']:.2f} Mbps")
        print(f"Results saved to: {args.output}")
        
    finally:
        # Cleanup
        print("\nCleaning up test containers...")
        tester.cleanup_containers()
        print("Cleanup complete.")


if __name__ == "__main__":
    asyncio.run(main())