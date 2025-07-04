#!/usr/bin/env python3
"""
Quick Test Script for POD Network Testing

This script demonstrates the basic network testing capabilities
by creating a small number of containers and testing connectivity.

Usage:
    python quick_test.py
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path to import POD
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from container_capacity_test import ContainerCapacityTester


async def quick_demo():
    """Run a quick demonstration of container network testing"""
    print("🚀 POD Network Testing Quick Demo")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Create tester instance
    tester = ContainerCapacityTester()
    
    try:
        # Generate small test configuration
        print("📋 Generating test configuration...")
        containers = tester.generate_container_configs(
            container_count=6,  # Small test
            vlan_count=3       # 3 VLANs: 100, 101, 102
        )
        
        print(f"   - {len(containers)} containers across 3 VLANs")
        for container in containers:
            print(f"   - {container.name}: VLAN {container.vlan_id} -> {container.ip_address}")
        
        # Deploy containers
        print("\n🏗️  Deploying containers...")
        deployment_stats = await tester.deploy_containers(containers, max_concurrent=3)
        
        print(f"   - Deployed: {deployment_stats['successful_deployments']}/{deployment_stats['total_containers']}")
        print(f"   - Rate: {deployment_stats['containers_per_second']:.2f} containers/second")
        print(f"   - Avg startup: {deployment_stats['average_startup_time']:.2f}s")
        
        if deployment_stats['successful_deployments'] < 2:
            print("❌ Insufficient containers deployed for testing")
            return
        
        # Start network test servers
        print("\n🌐 Starting network test servers...")
        server_stats = tester.start_iperf_servers()
        print(f"   - Started {server_stats['servers_started']} iperf3 servers")
        
        # Run network tests
        print("\n🔬 Running network throughput tests...")
        test_results = tester.run_throughput_matrix_test(test_duration=5, max_tests=10)
        
        successful_tests = [r for r in test_results if r.success]
        cross_vlan_tests = [r for r in successful_tests if r.source_vlan != r.target_vlan]
        same_vlan_tests = [r for r in successful_tests if r.source_vlan == r.target_vlan]
        
        print(f"   - Completed: {len(test_results)} tests")
        print(f"   - Successful: {len(successful_tests)}")
        print(f"   - Cross-VLAN: {len(cross_vlan_tests)}")
        print(f"   - Same-VLAN: {len(same_vlan_tests)}")
        
        # Show some results
        if successful_tests:
            avg_throughput = sum(r.throughput_mbps for r in successful_tests) / len(successful_tests)
            max_throughput = max(r.throughput_mbps for r in successful_tests)
            print(f"   - Average throughput: {avg_throughput:.2f} Mbps")
            print(f"   - Maximum throughput: {max_throughput:.2f} Mbps")
            
            # Show a few sample results
            print("\n📊 Sample Test Results:")
            for i, result in enumerate(successful_tests[:3]):
                vlan_type = "Cross-VLAN" if result.source_vlan != result.target_vlan else "Same-VLAN"
                print(f"   {i+1}. {result.source_container} -> {result.target_container}")
                print(f"      {vlan_type} (VLAN {result.source_vlan} -> {result.target_vlan})")
                print(f"      Throughput: {result.throughput_mbps:.2f} Mbps")
        
        # Generate report
        print("\n📄 Generating test report...")
        report = tester.generate_report(deployment_stats, server_stats)
        
        print("\n✅ Quick Demo Results Summary:")
        print(f"   - Container deployment success: {report['test_summary']['deployment_success_rate']:.1f}%")
        print(f"   - Network tests completed: {report['test_summary']['total_network_tests']}")
        print(f"   - Average throughput: {report['network_performance']['average_throughput_mbps']:.2f} Mbps")
        
        print(f"\n💾 Full results saved to: quick_demo_results.json")
        
        # Save minimal report
        import json
        with open("quick_demo_results.json", 'w') as f:
            json.dump(report, f, indent=2)
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up containers...")
        tester.cleanup_containers()
        print("✨ Demo complete!")


def check_prerequisites():
    """Check if system meets requirements for demo"""
    print("🔍 Checking prerequisites...")
    
    # Check Docker
    import subprocess
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ Docker: {result.stdout.strip()}")
        else:
            print("   ❌ Docker not found")
            return False
    except FileNotFoundError:
        print("   ❌ Docker not installed")
        return False
    
    # Check if we can run privileged containers
    try:
        result = subprocess.run(["docker", "run", "--rm", "--privileged", "busybox", "echo", "test"], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("   ✅ Privileged container support")
        else:
            print("   ❌ Cannot run privileged containers")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("   ❌ Docker container test failed")
        return False
    
    # Check VLAN support
    try:
        result = subprocess.run(["lsmod"], capture_output=True, text=True)
        if "8021q" in result.stdout:
            print("   ✅ VLAN (802.1q) module loaded")
        else:
            print("   ⚠️  VLAN module not loaded, attempting to load...")
            subprocess.run(["sudo", "modprobe", "8021q"], capture_output=True)
            result = subprocess.run(["lsmod"], capture_output=True, text=True)
            if "8021q" in result.stdout:
                print("   ✅ VLAN module loaded successfully")
            else:
                print("   ❌ Could not load VLAN module")
                return False
    except FileNotFoundError:
        print("   ❌ Cannot check VLAN support")
        return False
    
    return True


if __name__ == "__main__":
    print("🔬 POD Library Network Testing Demo")
    print("=" * 40)
    
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please ensure:")
        print("   - Docker is installed and running")
        print("   - User has Docker permissions (or run with sudo)")
        print("   - VLAN support is available (802.1q module)")
        sys.exit(1)
    
    print("✅ Prerequisites satisfied!")
    print("\n🚀 Starting network testing demo...")
    
    try:
        asyncio.run(quick_demo())
    except KeyboardInterrupt:
        print("\n\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        sys.exit(1)