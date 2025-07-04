#!/usr/bin/env python3
"""
Network Device Testing Framework using POD Containers

This framework creates isolated test environments for network device testing
using containers with specific VLAN configurations. Each container can simulate
different network endpoints for testing network devices like switches, routers, etc.

Usage:
    python network_device_test_framework.py --config test_scenarios.yaml
"""

import asyncio
import yaml
import json
import time
import logging
import argparse
import sys
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# Add the POD library to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
pod_root = os.path.join(script_dir, '..', '..')
sys.path.insert(0, pod_root)

from pod.connections.container import DockerConnection
from pod.os_abstraction.container import ContainerHandler
from pod.os_abstraction.base import NetworkConfig


@dataclass
class TestEndpoint:
    """Represents a network test endpoint (container)"""
    name: str
    vlan_id: int
    ip_address: str
    role: str  # "client", "server", "monitor"
    tools: List[str]  # Network tools to install
    test_commands: List[str]  # Commands to run for testing
    connection: Optional[DockerConnection] = None
    handler: Optional[ContainerHandler] = None
    status: str = "pending"


@dataclass
class NetworkTestScenario:
    """Defines a complete network testing scenario"""
    name: str
    description: str
    endpoints: List[TestEndpoint]
    test_matrix: List[Dict[str, Any]]  # Source->Target test definitions
    expected_results: Dict[str, Any]


class NetworkDeviceTestFramework:
    """Framework for testing network devices using containerized endpoints"""
    
    def __init__(self, base_image: str = "rockylinux:9"):
        self.base_image = base_image
        self.scenarios: List[NetworkTestScenario] = []
        self.logger = logging.getLogger(__name__)
        
    def load_test_scenarios(self, config_file: str):
        """Load test scenarios from YAML configuration"""
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        for scenario_config in config.get('scenarios', []):
            endpoints = []
            for ep_config in scenario_config.get('endpoints', []):
                endpoint = TestEndpoint(
                    name=ep_config['name'],
                    vlan_id=ep_config['vlan_id'],
                    ip_address=ep_config['ip_address'],
                    role=ep_config.get('role', 'client'),
                    tools=ep_config.get('tools', ['iproute', 'iputils', 'iperf3']),
                    test_commands=ep_config.get('test_commands', [])
                )
                endpoints.append(endpoint)
            
            scenario = NetworkTestScenario(
                name=scenario_config['name'],
                description=scenario_config.get('description', ''),
                endpoints=endpoints,
                test_matrix=scenario_config.get('test_matrix', []),
                expected_results=scenario_config.get('expected_results', {})
            )
            self.scenarios.append(scenario)
    
    async def setup_test_endpoint(self, endpoint: TestEndpoint) -> bool:
        """Set up a single test endpoint container"""
        try:
            self.logger.info(f"Setting up endpoint: {endpoint.name}")
            
            # Create container with necessary capabilities
            import subprocess  # nosec B404
            create_cmd = [
                "docker", "run", "-d",
                "--name", endpoint.name,
                "--cap-add", "NET_ADMIN",
                "--cap-add", "SYS_ADMIN", 
                "--privileged",  # Required for advanced network testing
                self.base_image,
                "sleep", "7200"  # 2 hour runtime
            ]
            
            result = subprocess.run(create_cmd, capture_output=True, text=True)  # nosec B603
            if result.returncode != 0:
                self.logger.error(f"Failed to create container {endpoint.name}: {result.stderr}")
                endpoint.status = "failed"
                return False
            
            # Connect via POD
            connection = DockerConnection(endpoint.name)
            connection.connect()
            handler = ContainerHandler(connection)
            
            endpoint.connection = connection
            endpoint.handler = handler
            
            # Install required tools
            for tool in endpoint.tools:
                self.logger.info(f"Installing {tool} in {endpoint.name}")
                result = handler.install_package(tool)
                if not result.success:
                    self.logger.warning(f"Failed to install {tool}: {result.stderr}")
            
            # Configure network with VLAN
            network_config = NetworkConfig(
                interface="eth0",
                vlan_id=endpoint.vlan_id,
                ip_address=endpoint.ip_address,
                netmask="255.255.255.0",
                gateway=f"192.168.{endpoint.vlan_id % 256}.1"
            )
            
            result = handler.configure_network(network_config)
            if not result.success:
                self.logger.error(f"Network configuration failed for {endpoint.name}: {result.stderr}")
                endpoint.status = "network_failed"
                return False
            
            # Run any initialization commands
            for cmd in endpoint.test_commands:
                if cmd.startswith("init:"):
                    init_cmd = cmd[5:]  # Remove "init:" prefix
                    self.logger.info(f"Running init command in {endpoint.name}: {init_cmd}")
                    handler.execute_command(init_cmd)
            
            endpoint.status = "ready"
            self.logger.info(f"Endpoint {endpoint.name} ready on VLAN {endpoint.vlan_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up endpoint {endpoint.name}: {e}")
            endpoint.status = "error"
            return False
    
    async def setup_scenario(self, scenario: NetworkTestScenario) -> Dict[str, Any]:
        """Set up all endpoints for a test scenario"""
        self.logger.info(f"Setting up scenario: {scenario.name}")
        
        start_time = time.time()
        setup_tasks = [self.setup_test_endpoint(ep) for ep in scenario.endpoints]
        results = await asyncio.gather(*setup_tasks, return_exceptions=True)
        
        setup_time = time.time() - start_time
        successful = sum(1 for r in results if r is True)
        
        return {
            "scenario_name": scenario.name,
            "total_endpoints": len(scenario.endpoints),
            "successful_setups": successful,
            "setup_time": setup_time,
            "ready_endpoints": [ep.name for ep in scenario.endpoints if ep.status == "ready"]
        }
    
    def run_connectivity_test(self, source: TestEndpoint, target: TestEndpoint) -> Dict[str, Any]:
        """Test basic connectivity between two endpoints"""
        if not source.handler or not target.handler:
            return {"success": False, "error": "Handler not available"}
        
        try:
            # Ping test
            ping_result = source.handler.execute_command(
                f"ping -c 4 -W 2 {target.ip_address}"
            )
            
            # Parse ping results
            ping_success = ping_result.success and "0% packet loss" in ping_result.stdout
            
            # Extract latency if available
            avg_latency = 0.0
            if ping_success:
                import re
                latency_match = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)', ping_result.stdout)
                if latency_match:
                    avg_latency = float(latency_match.group(1))
            
            return {
                "source": source.name,
                "target": target.name,
                "source_vlan": source.vlan_id,
                "target_vlan": target.vlan_id,
                "ping_success": ping_success,
                "average_latency_ms": avg_latency,
                "ping_output": ping_result.stdout,
                "success": ping_success
            }
            
        except Exception as e:
            return {
                "source": source.name,
                "target": target.name,
                "success": False,
                "error": str(e)
            }
    
    def run_bandwidth_test(self, client: TestEndpoint, server: TestEndpoint, 
                          duration: int = 10) -> Dict[str, Any]:
        """Run bandwidth test between client and server"""
        if not client.handler or not server.handler:
            return {"success": False, "error": "Handler not available"}
        
        try:
            # Start iperf3 server on target
            server_port = 5000 + server.vlan_id
            server_cmd = f"iperf3 -s -p {server_port} -D"
            server_result = server.handler.execute_command(server_cmd)
            
            if not server_result.success:
                return {"success": False, "error": f"Failed to start iperf3 server: {server_result.stderr}"}
            
            # Give server time to start
            time.sleep(2)
            
            # Run client test
            client_cmd = f"iperf3 -c {server.ip_address} -p {server_port} -t {duration} -J"
            client_result = client.handler.execute_command(client_cmd, timeout=duration + 30)
            
            if not client_result.success:
                return {"success": False, "error": f"iperf3 client failed: {client_result.stderr}"}
            
            # Parse JSON results
            try:
                iperf_data = json.loads(client_result.stdout)
                end_data = iperf_data["end"]["sum_received"]
                
                return {
                    "client": client.name,
                    "server": server.name,
                    "client_vlan": client.vlan_id,
                    "server_vlan": server.vlan_id,
                    "throughput_mbps": end_data["bits_per_second"] / 1_000_000,
                    "bytes_transferred": end_data["bytes"],
                    "test_duration": duration,
                    "success": True
                }
            except (json.JSONDecodeError, KeyError) as e:
                return {"success": False, "error": f"Failed to parse iperf3 results: {e}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            # Clean up server process
            try:
                server.handler.execute_command("pkill iperf3")
            except Exception as e:
                # Cleanup operation - iperf3 may not be running
                self.logger.debug(f"Could not kill iperf3 processes: {e}")
    
    def run_scenario_tests(self, scenario: NetworkTestScenario) -> Dict[str, Any]:
        """Run all tests defined in a scenario"""
        self.logger.info(f"Running tests for scenario: {scenario.name}")
        
        ready_endpoints = [ep for ep in scenario.endpoints if ep.status == "ready"]
        if len(ready_endpoints) < 2:
            return {"error": "Need at least 2 ready endpoints for testing"}
        
        results = {
            "scenario_name": scenario.name,
            "connectivity_tests": [],
            "bandwidth_tests": [],
            "custom_tests": []
        }
        
        # Run connectivity matrix
        self.logger.info("Running connectivity tests...")
        for source in ready_endpoints:
            for target in ready_endpoints:
                if source != target:
                    result = self.run_connectivity_test(source, target)
                    results["connectivity_tests"].append(result)
        
        # Run bandwidth tests (servers vs clients)
        servers = [ep for ep in ready_endpoints if ep.role == "server"]
        clients = [ep for ep in ready_endpoints if ep.role == "client"]
        
        if servers and clients:
            self.logger.info("Running bandwidth tests...")
            for client in clients:
                for server in servers:
                    result = self.run_bandwidth_test(client, server)
                    results["bandwidth_tests"].append(result)
        
        # Run custom test matrix if defined
        for test_def in scenario.test_matrix:
            try:
                source_name = test_def["source"]
                target_name = test_def["target"] 
                test_type = test_def.get("type", "ping")
                
                source = next(ep for ep in ready_endpoints if ep.name == source_name)
                target = next(ep for ep in ready_endpoints if ep.name == target_name)
                
                if test_type == "ping":
                    result = self.run_connectivity_test(source, target)
                elif test_type == "bandwidth":
                    result = self.run_bandwidth_test(source, target)
                else:
                    result = {"error": f"Unknown test type: {test_type}"}
                
                result["test_definition"] = test_def
                results["custom_tests"].append(result)
                
            except Exception as e:
                self.logger.error(f"Error running custom test: {e}")
        
        return results
    
    def cleanup_scenario(self, scenario: NetworkTestScenario):
        """Clean up all containers for a scenario"""
        self.logger.info(f"Cleaning up scenario: {scenario.name}")
        
        for endpoint in scenario.endpoints:
            try:
                if endpoint.connection:
                    endpoint.connection.disconnect()
                
                import subprocess  # nosec B404
                subprocess.run(["docker", "rm", "-f", endpoint.name],  # nosec B603 B607 
                             capture_output=True)
                self.logger.info(f"Cleaned up container: {endpoint.name}")
            except Exception as e:
                self.logger.error(f"Error cleaning up {endpoint.name}: {e}")
    
    def generate_test_report(self, scenario_results: List[Dict[str, Any]], 
                           output_file: str = "network_device_test_report.json"):
        """Generate comprehensive test report"""
        report = {
            "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "framework_version": "1.0.0",
            "scenarios_tested": len(scenario_results),
            "scenarios": scenario_results,
            "summary": {
                "total_connectivity_tests": sum(len(s.get("connectivity_tests", [])) for s in scenario_results),
                "total_bandwidth_tests": sum(len(s.get("bandwidth_tests", [])) for s in scenario_results),
                "successful_connectivity_tests": sum(sum(1 for t in s.get("connectivity_tests", []) if t.get("success")) for s in scenario_results),
                "successful_bandwidth_tests": sum(sum(1 for t in s.get("bandwidth_tests", []) if t.get("success")) for s in scenario_results)
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report


def create_sample_config():
    """Create a sample configuration file"""
    sample_config = {
        "scenarios": [
            {
                "name": "basic_vlan_isolation_test",
                "description": "Test VLAN isolation between different network segments",
                "endpoints": [
                    {
                        "name": "vlan100-client",
                        "vlan_id": 100,
                        "ip_address": "192.168.100.10",
                        "role": "client",
                        "tools": ["iproute", "iputils", "iperf3", "tcpdump"],
                        "test_commands": [
                            "init:echo 'Client endpoint ready'"
                        ]
                    },
                    {
                        "name": "vlan100-server",
                        "vlan_id": 100,
                        "ip_address": "192.168.100.20",
                        "role": "server",
                        "tools": ["iproute", "iputils", "iperf3", "netcat"],
                        "test_commands": [
                            "init:echo 'Server endpoint ready'"
                        ]
                    },
                    {
                        "name": "vlan200-client",
                        "vlan_id": 200,
                        "ip_address": "192.168.200.10",
                        "role": "client",
                        "tools": ["iproute", "iputils", "iperf3"],
                        "test_commands": []
                    }
                ],
                "test_matrix": [
                    {
                        "source": "vlan100-client",
                        "target": "vlan100-server",
                        "type": "bandwidth",
                        "expected": "should_pass"
                    },
                    {
                        "source": "vlan100-client", 
                        "target": "vlan200-client",
                        "type": "ping",
                        "expected": "should_fail"  # VLAN isolation
                    }
                ],
                "expected_results": {
                    "vlan_isolation": True,
                    "intra_vlan_communication": True
                }
            }
        ]
    }
    
    with open("sample_network_test_config.yaml", 'w') as f:
        yaml.dump(sample_config, f, default_flow_style=False, indent=2)
    
    print("Created sample configuration: sample_network_test_config.yaml")


async def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Network Device Testing Framework")
    parser.add_argument("--config", type=str, 
                       help="YAML configuration file with test scenarios")
    parser.add_argument("--create-sample", action="store_true",
                       help="Create a sample configuration file")
    parser.add_argument("--output", type=str, default="network_test_results.json",
                       help="Output file for test results")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.create_sample:
        create_sample_config()
        return
    
    if not args.config:
        print("Error: --config is required (or use --create-sample to generate example)")
        return
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    framework = NetworkDeviceTestFramework()
    
    try:
        # Load test scenarios
        framework.load_test_scenarios(args.config)
        print(f"Loaded {len(framework.scenarios)} test scenarios")
        
        scenario_results = []
        
        for scenario in framework.scenarios:
            print(f"\n{'='*60}")
            print(f"RUNNING SCENARIO: {scenario.name}")
            print(f"{'='*60}")
            
            # Setup scenario
            setup_result = await framework.setup_scenario(scenario)
            print(f"Setup complete: {setup_result['successful_setups']}/{setup_result['total_endpoints']} endpoints ready")
            
            if setup_result['successful_setups'] < 2:
                print("Insufficient endpoints ready, skipping scenario tests")
                scenario_results.append({
                    "scenario_name": scenario.name,
                    "setup_result": setup_result,
                    "error": "Insufficient endpoints ready"
                })
                continue
            
            # Run tests
            test_results = framework.run_scenario_tests(scenario)
            test_results["setup_result"] = setup_result
            scenario_results.append(test_results)
            
            # Print summary
            connectivity_success = sum(1 for t in test_results.get("connectivity_tests", []) if t.get("success"))
            bandwidth_success = sum(1 for t in test_results.get("bandwidth_tests", []) if t.get("success"))
            
            print(f"Connectivity tests: {connectivity_success}/{len(test_results.get('connectivity_tests', []))}")
            print(f"Bandwidth tests: {bandwidth_success}/{len(test_results.get('bandwidth_tests', []))}")
            
            # Cleanup
            framework.cleanup_scenario(scenario)
        
        # Generate final report
        report = framework.generate_test_report(scenario_results, args.output)
        
        print(f"\n{'='*60}")
        print("FINAL RESULTS")
        print(f"{'='*60}")
        print(f"Scenarios tested: {report['scenarios_tested']}")
        print(f"Total connectivity tests: {report['summary']['total_connectivity_tests']}")
        print(f"Successful connectivity tests: {report['summary']['successful_connectivity_tests']}")
        print(f"Total bandwidth tests: {report['summary']['total_bandwidth_tests']}")
        print(f"Successful bandwidth tests: {report['summary']['successful_bandwidth_tests']}")
        print(f"Full report saved to: {args.output}")
        
    except Exception as e:
        print(f"Error: {e}")
        # Cleanup any remaining containers
        for scenario in framework.scenarios:
            framework.cleanup_scenario(scenario)


if __name__ == "__main__":
    asyncio.run(main())