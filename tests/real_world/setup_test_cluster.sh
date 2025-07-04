#!/bin/bash

# Setup script for local Kubernetes test cluster
# Supports multiple cluster types: kind, minikube, k3s

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CLUSTER_TYPE=${1:-kind}
CLUSTER_NAME="pod-test-cluster"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}"
}

print_status() {
    case $1 in
        "success") echo -e "${GREEN}✓${NC} $2" ;;
        "error") echo -e "${RED}✗${NC} $2" ;;
        "warning") echo -e "${YELLOW}⚠${NC} $2" ;;
        "info") echo -e "${BLUE}ℹ${NC} $2" ;;
    esac
}

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check Docker
    if command -v docker &> /dev/null; then
        print_status "success" "Docker is installed"
    else
        print_status "error" "Docker is not installed"
        exit 1
    fi
    
    # Check kubectl
    if command -v kubectl &> /dev/null; then
        print_status "success" "kubectl is installed"
    else
        print_status "warning" "kubectl not found, installing..."
        install_kubectl
    fi
}

install_kubectl() {
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    chmod +x kubectl
    sudo mv kubectl /usr/local/bin/
    print_status "success" "kubectl installed"
}

setup_kind_cluster() {
    print_header "Setting up Kind cluster"
    
    # Install Kind if not present
    if ! command -v kind &> /dev/null; then
        print_status "info" "Installing Kind..."
        curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
        chmod +x ./kind
        sudo mv ./kind /usr/local/bin/kind
    fi
    
    # Delete existing cluster
    if kind get clusters | grep -q "$CLUSTER_NAME"; then
        print_status "info" "Deleting existing cluster..."
        kind delete cluster --name "$CLUSTER_NAME"
    fi
    
    # Create cluster
    print_status "info" "Creating Kind cluster..."
    kind create cluster --name "$CLUSTER_NAME" --config "$SCRIPT_DIR/kind-config.yaml" --wait 5m
    
    # Set kubeconfig
    kind get kubeconfig --name "$CLUSTER_NAME" > ~/.kube/config-kind
    export KUBECONFIG=~/.kube/config-kind
    
    print_status "success" "Kind cluster created"
}

setup_minikube_cluster() {
    print_header "Setting up Minikube cluster"
    
    # Install Minikube if not present
    if ! command -v minikube &> /dev/null; then
        print_status "info" "Installing Minikube..."
        curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
        sudo install minikube-linux-amd64 /usr/local/bin/minikube
        rm minikube-linux-amd64
    fi
    
    # Delete existing cluster
    if minikube status -p "$CLUSTER_NAME" &> /dev/null; then
        print_status "info" "Deleting existing cluster..."
        minikube delete -p "$CLUSTER_NAME"
    fi
    
    # Create cluster
    print_status "info" "Creating Minikube cluster..."
    minikube start \
        -p "$CLUSTER_NAME" \
        --nodes=3 \
        --cpus=2 \
        --memory=2048 \
        --kubernetes-version=v1.28.0 \
        --container-runtime=docker \
        --driver=docker
    
    # Enable addons
    minikube addons enable metrics-server -p "$CLUSTER_NAME"
    minikube addons enable ingress -p "$CLUSTER_NAME"
    
    print_status "success" "Minikube cluster created"
}

setup_k3s_cluster() {
    print_header "Setting up K3s cluster"
    
    # Install K3s
    print_status "info" "Installing K3s..."
    curl -sfL https://get.k3s.io | sh -s - \
        --docker \
        --disable traefik \
        --write-kubeconfig-mode 644
    
    # Wait for K3s to be ready
    print_status "info" "Waiting for K3s to be ready..."
    sudo k3s kubectl wait --for=condition=ready nodes --all --timeout=300s
    
    # Copy kubeconfig
    mkdir -p ~/.kube
    sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
    sudo chown $USER:$USER ~/.kube/config
    
    print_status "success" "K3s cluster created"
}

install_cni_plugins() {
    print_header "Installing CNI Plugins"
    
    # Install Multus
    print_status "info" "Installing Multus CNI..."
    kubectl apply -f https://raw.githubusercontent.com/k8snetworkplumbingwg/multus-cni/master/deployments/multus-daemonset-thick.yml
    
    # Install Calico
    print_status "info" "Installing Calico CNI..."
    kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.0/manifests/tigera-operator.yaml
    
    # For Kind, we need a custom Calico configuration
    if [[ "$CLUSTER_TYPE" == "kind" ]]; then
        cat <<EOF | kubectl apply -f -
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    containerIPForwarding: Enabled
    ipPools:
    - blockSize: 26
      cidr: 10.244.0.0/16
      encapsulation: VXLANCrossSubnet
      natOutgoing: Enabled
      nodeSelector: all()
EOF
    else
        kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.0/manifests/custom-resources.yaml
    fi
    
    # Wait for CNI to be ready
    print_status "info" "Waiting for CNI plugins to be ready..."
    kubectl wait --for=condition=ready pods -l k8s-app=calico-node -n kube-system --timeout=300s || true
    kubectl wait --for=condition=ready pods -l app=multus -n kube-system --timeout=300s || true
    
    print_status "success" "CNI plugins installed"
}

create_test_resources() {
    print_header "Creating Test Resources"
    
    # Create test namespace
    kubectl create namespace pod-test || true
    
    # Create NetworkAttachmentDefinitions for testing
    cat <<EOF | kubectl apply -f -
apiVersion: k8s.cni.cncf.io/v1
kind: NetworkAttachmentDefinition
metadata:
  name: macvlan-vlan100
  namespace: pod-test
spec:
  config: '{
    "cniVersion": "0.3.1",
    "type": "macvlan",
    "master": "eth0",
    "vlan": 100,
    "ipam": {
      "type": "host-local",
      "subnet": "10.100.0.0/24",
      "rangeStart": "10.100.0.10",
      "rangeEnd": "10.100.0.50",
      "gateway": "10.100.0.1"
    }
  }'
---
apiVersion: k8s.cni.cncf.io/v1
kind: NetworkAttachmentDefinition
metadata:
  name: macvlan-vlan200
  namespace: pod-test
spec:
  config: '{
    "cniVersion": "0.3.1",
    "type": "macvlan",
    "master": "eth0",
    "vlan": 200,
    "ipam": {
      "type": "host-local",
      "subnet": "10.200.0.0/24",
      "rangeStart": "10.200.0.10",
      "rangeEnd": "10.200.0.50",
      "gateway": "10.200.0.1"
    }
  }'
EOF
    
    print_status "success" "Test resources created"
}

verify_cluster() {
    print_header "Verifying Cluster"
    
    # Check nodes
    print_status "info" "Cluster nodes:"
    kubectl get nodes
    
    # Check system pods
    print_status "info" "System pods:"
    kubectl get pods -n kube-system
    
    # Check CNI
    print_status "info" "CNI status:"
    kubectl get pods -n kube-system | grep -E '(calico|multus|cilium|flannel)' || print_status "warning" "No CNI pods found"
    
    # Run validation script
    print_status "info" "Running validation..."
    python "$SCRIPT_DIR/validate_environment.py"
}

cleanup_cluster() {
    print_header "Cleaning up cluster"
    
    case $CLUSTER_TYPE in
        kind)
            kind delete cluster --name "$CLUSTER_NAME"
            ;;
        minikube)
            minikube delete -p "$CLUSTER_NAME"
            ;;
        k3s)
            /usr/local/bin/k3s-uninstall.sh
            ;;
    esac
    
    print_status "success" "Cluster deleted"
}

# Main execution
main() {
    case $1 in
        cleanup)
            cleanup_cluster
            exit 0
            ;;
        verify)
            verify_cluster
            exit 0
            ;;
    esac
    
    print_header "POD Library - Kubernetes Test Cluster Setup"
    print_status "info" "Cluster type: $CLUSTER_TYPE"
    
    # Check prerequisites
    check_prerequisites
    
    # Setup cluster based on type
    case $CLUSTER_TYPE in
        kind)
            setup_kind_cluster
            ;;
        minikube)
            setup_minikube_cluster
            ;;
        k3s)
            setup_k3s_cluster
            ;;
        *)
            print_status "error" "Unknown cluster type: $CLUSTER_TYPE"
            echo "Usage: $0 [kind|minikube|k3s|cleanup|verify]"
            exit 1
            ;;
    esac
    
    # Install CNI plugins
    install_cni_plugins
    
    # Create test resources
    create_test_resources
    
    # Verify cluster
    verify_cluster
    
    print_header "Setup Complete!"
    print_status "success" "Kubernetes test cluster is ready"
    echo ""
    echo "Next steps:"
    echo "  1. Export kubeconfig: export KUBECONFIG=~/.kube/config"
    echo "  2. Run tests: ./run_k8s_tests.sh"
    echo "  3. Cleanup: $0 cleanup"
    echo ""
}

# Run main function
main "$@"