"""
CNI (Container Network Interface) integration utilities
Supports advanced networking with Calico, Cilium, Multus, and other CNI plugins
"""

import json
import yaml
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from kubernetes.client.rest import ApiException
from ..connections.kubernetes import KubernetesConnection


@dataclass
class CNIConfig:
    """CNI configuration for advanced networking"""
    name: str
    type: str
    vlan_id: Optional[int] = None
    bridge: Optional[str] = None
    subnet: Optional[str] = None
    gateway: Optional[str] = None
    master_interface: Optional[str] = None
    mtu: int = 1500
    dns_servers: List[str] = None
    routes: List[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.dns_servers is None:
            self.dns_servers = ["8.8.8.8", "8.8.4.4"]
        if self.routes is None:
            self.routes = []


class CNIManager:
    """Advanced CNI management for enterprise Kubernetes networking"""
    
    def __init__(self, k8s_connection: KubernetesConnection):
        self.k8s = k8s_connection
        self.detected_cnis = self._detect_cni_plugins()
        self.capabilities = self._analyze_capabilities()
    
    def _detect_cni_plugins(self) -> Dict[str, bool]:
        """Detect and analyze available CNI plugins"""
        plugins = {
            "calico": False,
            "cilium": False,
            "flannel": False,
            "weave": False,
            "multus": False,
            "antrea": False,
            "contiv": False,
            "canal": False,
            "kube-router": False,
            "sriov": False
        }
        
        try:
            # Check for Calico
            calico_check = self._check_cni_presence("calico", [
                {"label": "k8s-app=calico-node"},
                {"label": "projectcalico.org/ds-ready=true"}
            ])
            plugins["calico"] = calico_check
            
            # Check for Cilium
            cilium_check = self._check_cni_presence("cilium", [
                {"label": "k8s-app=cilium"},
                {"label": "app.kubernetes.io/name=cilium-agent"}
            ])
            plugins["cilium"] = cilium_check
            
            # Check for Flannel
            flannel_check = self._check_cni_presence("flannel", [
                {"label": "app=flannel"},
                {"label": "k8s-app=flannel"}
            ])
            plugins["flannel"] = flannel_check
            
            # Check for Weave
            weave_check = self._check_cni_presence("weave", [
                {"label": "name=weave-net"},
                {"label": "app=weave-net"}
            ])
            plugins["weave"] = weave_check
            
            # Check for Multus
            multus_check = self._check_cni_presence("multus", [
                {"label": "app=multus"},
                {"label": "name=multus"}
            ])
            plugins["multus"] = multus_check
            
            # Check for Antrea
            antrea_check = self._check_cni_presence("antrea", [
                {"label": "app=antrea"},
                {"label": "component=antrea-agent"}
            ])
            plugins["antrea"] = antrea_check
            
            # Check for SR-IOV
            sriov_check = self._check_cni_presence("sriov", [
                {"label": "app=sriov-device-plugin"},
                {"label": "app=sriov-cni"}
            ])
            plugins["sriov"] = sriov_check
            
        except Exception:
            pass
        
        return plugins
    
    def _check_cni_presence(self, cni_name: str, selectors: List[Dict[str, str]]) -> bool:
        """Check if specific CNI is present using multiple selector strategies"""
        for selector in selectors:
            try:
                if "label" in selector:
                    pods = self.k8s.v1.list_pod_for_all_namespaces(
                        label_selector=selector["label"],
                        limit=1
                    )
                    if pods.items:
                        return True
            except Exception:
                continue
        return False
    
    def _analyze_capabilities(self) -> Dict[str, Any]:
        """Analyze network capabilities based on detected CNI plugins"""
        capabilities = {
            "network_policies": False,
            "encryption": False,
            "load_balancing": False,
            "service_mesh": False,
            "multi_cluster": False,
            "bgp_routing": False,
            "ebpf": False,
            "vlan_support": False,
            "sr_iov": False,
            "bandwidth_management": False,
            "observability": []
        }
        
        # Calico capabilities
        if self.detected_cnis["calico"]:
            capabilities.update({
                "network_policies": True,
                "bgp_routing": True,
                "vlan_support": True,
                "encryption": True,  # WireGuard support
                "multi_cluster": True
            })
            capabilities["observability"].append("calico-monitoring")
        
        # Cilium capabilities
        if self.detected_cnis["cilium"]:
            capabilities.update({
                "network_policies": True,
                "ebpf": True,
                "encryption": True,
                "load_balancing": True,
                "service_mesh": True,
                "bandwidth_management": True,
                "multi_cluster": True
            })
            capabilities["observability"].extend(["hubble", "cilium-metrics"])
        
        # Multus capabilities
        if self.detected_cnis["multus"]:
            capabilities.update({
                "vlan_support": True,
                "sr_iov": True
            })
        
        # SR-IOV capabilities
        if self.detected_cnis["sriov"]:
            capabilities.update({
                "sr_iov": True,
                "bandwidth_management": True
            })
        
        return capabilities
    
    def create_network_attachment_definition(self, config: CNIConfig) -> Dict[str, Any]:
        """Create Multus NetworkAttachmentDefinition for advanced networking"""
        
        if config.type == "macvlan":
            cni_config = self._create_macvlan_config(config)
        elif config.type == "sriov":
            cni_config = self._create_sriov_config(config)
        elif config.type == "bridge":
            cni_config = self._create_bridge_config(config)
        elif config.type == "ipvlan":
            cni_config = self._create_ipvlan_config(config)
        else:
            raise ValueError(f"Unsupported CNI type: {config.type}")
        
        network_attachment = {
            "apiVersion": "k8s.cni.cncf.io/v1",
            "kind": "NetworkAttachmentDefinition",
            "metadata": {
                "name": config.name,
                "namespace": self.k8s.namespace,
                "annotations": {
                    "pod.network.example.com/description": f"Advanced {config.type} network",
                    "pod.network.example.com/vlan": str(config.vlan_id) if config.vlan_id else "none"
                }
            },
            "spec": {
                "config": json.dumps(cni_config)
            }
        }
        
        return network_attachment
    
    def _create_macvlan_config(self, config: CNIConfig) -> Dict[str, Any]:
        """Create MACVLAN CNI configuration"""
        cni_config = {
            "cniVersion": "0.3.1",
            "name": config.name,
            "type": "macvlan",
            "master": config.master_interface or "eth0",
            "mode": "bridge",
            "mtu": config.mtu,
            "ipam": {
                "type": "static" if config.subnet else "dhcp"
            }
        }
        
        if config.vlan_id:
            cni_config["vlan"] = config.vlan_id
        
        if config.subnet:
            cni_config["ipam"] = {
                "type": "static",
                "addresses": [
                    {
                        "address": config.subnet,
                        "gateway": config.gateway
                    }
                ],
                "dns": {
                    "nameservers": config.dns_servers
                },
                "routes": config.routes
            }
        
        return cni_config
    
    def _create_sriov_config(self, config: CNIConfig) -> Dict[str, Any]:
        """Create SR-IOV CNI configuration"""
        cni_config = {
            "cniVersion": "0.3.1",
            "name": config.name,
            "type": "sriov",
            "deviceID": config.master_interface or "0000:00:00.0",
            "mtu": config.mtu,
            "ipam": {
                "type": "static" if config.subnet else "dhcp"
            }
        }
        
        if config.vlan_id:
            cni_config["vlan"] = config.vlan_id
        
        if config.subnet:
            cni_config["ipam"] = {
                "type": "static",
                "addresses": [
                    {
                        "address": config.subnet,
                        "gateway": config.gateway
                    }
                ],
                "dns": {
                    "nameservers": config.dns_servers
                }
            }
        
        return cni_config
    
    def _create_bridge_config(self, config: CNIConfig) -> Dict[str, Any]:
        """Create bridge CNI configuration"""
        cni_config = {
            "cniVersion": "0.3.1",
            "name": config.name,
            "type": "bridge",
            "bridge": config.bridge or f"br-{config.name}",
            "isGateway": True,
            "isDefaultGateway": False,
            "forceAddress": False,
            "ipMasq": True,
            "mtu": config.mtu,
            "hairpinMode": True,
            "ipam": {
                "type": "host-local",
                "subnet": config.subnet or "10.244.0.0/16"
            }
        }
        
        if config.vlan_id:
            cni_config["vlan"] = config.vlan_id
        
        return cni_config
    
    def _create_ipvlan_config(self, config: CNIConfig) -> Dict[str, Any]:
        """Create IPVLAN CNI configuration"""
        cni_config = {
            "cniVersion": "0.3.1",
            "name": config.name,
            "type": "ipvlan",
            "master": config.master_interface or "eth0",
            "mode": "l2",
            "mtu": config.mtu,
            "ipam": {
                "type": "static" if config.subnet else "dhcp"
            }
        }
        
        if config.subnet:
            cni_config["ipam"] = {
                "type": "static",
                "addresses": [
                    {
                        "address": config.subnet,
                        "gateway": config.gateway
                    }
                ],
                "dns": {
                    "nameservers": config.dns_servers
                }
            }
        
        return cni_config
    
    def create_calico_ip_pool(self, name: str, cidr: str, vlan_id: Optional[int] = None) -> Dict[str, Any]:
        """Create Calico IP Pool for VLAN isolation"""
        ip_pool = {
            "apiVersion": "projectcalico.org/v3",
            "kind": "IPPool",
            "metadata": {
                "name": name
            },
            "spec": {
                "cidr": cidr,
                "vxlanMode": "Never",
                "ipipMode": "Never",
                "natOutgoing": True,
                "blockSize": 26,
                "allowedUses": ["Workload", "Tunnel"]
            }
        }
        
        if vlan_id:
            ip_pool["spec"]["nodeSelector"] = f"vlan-{vlan_id} == 'true'"
        
        return ip_pool
    
    def create_calico_bgp_configuration(self, as_number: int, router_id: str) -> Dict[str, Any]:
        """Create Calico BGP configuration for enterprise routing"""
        bgp_config = {
            "apiVersion": "projectcalico.org/v3",
            "kind": "BGPConfiguration",
            "metadata": {
                "name": "default"
            },
            "spec": {
                "logSeverityScreen": "Info",
                "nodeToNodeMeshEnabled": True,
                "asNumber": as_number,
                "routerId": router_id,
                "serviceClusterIPs": [
                    {"cidr": "10.96.0.0/12"}
                ],
                "serviceExternalIPs": [
                    {"cidr": "192.168.1.0/24"}
                ]
            }
        }
        
        return bgp_config
    
    def create_cilium_network_policy(self, name: str, namespace: str, 
                                   endpoint_selector: Dict[str, str],
                                   ingress_rules: List[Dict[str, Any]] = None,
                                   egress_rules: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create advanced Cilium NetworkPolicy with eBPF capabilities"""
        
        policy = {
            "apiVersion": "cilium.io/v2",
            "kind": "CiliumNetworkPolicy",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": {
                "endpointSelector": {
                    "matchLabels": endpoint_selector
                }
            }
        }
        
        if ingress_rules:
            policy["spec"]["ingress"] = ingress_rules
        
        if egress_rules:
            policy["spec"]["egress"] = egress_rules
        
        return policy
    
    def create_cilium_cluster_wide_policy(self, name: str,
                                        node_selector: Dict[str, str],
                                        ingress_rules: List[Dict[str, Any]] = None,
                                        egress_rules: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create Cilium ClusterWide NetworkPolicy for global rules"""
        
        policy = {
            "apiVersion": "cilium.io/v2",
            "kind": "CiliumClusterwideNetworkPolicy",
            "metadata": {
                "name": name
            },
            "spec": {
                "nodeSelector": {
                    "matchLabels": node_selector
                }
            }
        }
        
        if ingress_rules:
            policy["spec"]["ingress"] = ingress_rules
        
        if egress_rules:
            policy["spec"]["egress"] = egress_rules
        
        return policy
    
    def apply_network_configuration(self, config_dict: Dict[str, Any]) -> bool:
        """Apply network configuration to the cluster"""
        try:
            api_version = config_dict.get("apiVersion", "")
            kind = config_dict.get("kind", "")
            
            if "k8s.cni.cncf.io" in api_version and kind == "NetworkAttachmentDefinition":
                self.k8s.custom_objects_v1.create_namespaced_custom_object(
                    group="k8s.cni.cncf.io",
                    version="v1",
                    namespace=config_dict["metadata"]["namespace"],
                    plural="network-attachment-definitions",
                    body=config_dict
                )
            elif "projectcalico.org" in api_version:
                if kind == "IPPool":
                    self.k8s.custom_objects_v1.create_cluster_custom_object(
                        group="projectcalico.org",
                        version="v3",
                        plural="ippools",
                        body=config_dict
                    )
                elif kind == "BGPConfiguration":
                    self.k8s.custom_objects_v1.create_cluster_custom_object(
                        group="projectcalico.org",
                        version="v3",
                        plural="bgpconfigurations",
                        body=config_dict
                    )
            elif "cilium.io" in api_version:
                if kind == "CiliumNetworkPolicy":
                    self.k8s.custom_objects_v1.create_namespaced_custom_object(
                        group="cilium.io",
                        version="v2",
                        namespace=config_dict["metadata"]["namespace"],
                        plural="ciliumnetworkpolicies",
                        body=config_dict
                    )
                elif kind == "CiliumClusterwideNetworkPolicy":
                    self.k8s.custom_objects_v1.create_cluster_custom_object(
                        group="cilium.io",
                        version="v2",
                        plural="ciliumclusterwidenetworkpolicies",
                        body=config_dict
                    )
            elif "networking.k8s.io" in api_version and kind == "NetworkPolicy":
                self.k8s.networking_v1.create_namespaced_network_policy(
                    namespace=config_dict["metadata"]["namespace"],
                    body=config_dict
                )
            else:
                return False
            
            return True
            
        except ApiException as e:
            if e.status == 409:  # Already exists
                return True
            return False
        except Exception:
            return False
    
    def get_network_observability_config(self) -> Dict[str, Any]:
        """Get observability configuration for network monitoring"""
        config = {
            "prometheus_metrics": False,
            "flow_logs": False,
            "network_topology": False,
            "policy_verdicts": False,
            "endpoints": []
        }
        
        if self.detected_cnis["cilium"]:
            config.update({
                "prometheus_metrics": True,
                "flow_logs": True,
                "network_topology": True,
                "policy_verdicts": True,
                "endpoints": [
                    "http://cilium-agent:9090/metrics",
                    "http://hubble-metrics:9091/metrics"
                ]
            })
        
        if self.detected_cnis["calico"]:
            config.update({
                "prometheus_metrics": True,
                "endpoints": [
                    "http://calico-node:9091/metrics",
                    "http://calico-typha:9093/metrics"
                ]
            })
        
        return config
    
    def create_bandwidth_policy(self, pod_name: str, namespace: str,
                              ingress_rate: str, egress_rate: str) -> Dict[str, Any]:
        """Create bandwidth management policy"""
        
        # This creates annotations for CNI bandwidth plugin
        annotations = {
            "kubernetes.io/ingress-bandwidth": ingress_rate,  # e.g., "100M"
            "kubernetes.io/egress-bandwidth": egress_rate     # e.g., "100M"
        }
        
        # For Cilium, we can create CiliumEndpoint with bandwidth limits
        if self.detected_cnis["cilium"]:
            bandwidth_policy = {
                "apiVersion": "cilium.io/v2",
                "kind": "CiliumEndpoint",
                "metadata": {
                    "name": pod_name,
                    "namespace": namespace
                },
                "spec": {
                    "networking": {
                        "bandwidthManager": {
                            "enabled": True,
                            "config": {
                                "ingressRate": ingress_rate,
                                "egressRate": egress_rate
                            }
                        }
                    }
                }
            }
            return bandwidth_policy
        
        # Return annotation-based approach for other CNIs
        return {"annotations": annotations}