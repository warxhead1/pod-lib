#!/bin/bash
# Script to run POD container integration tests with Docker-in-Docker

set -e

echo "POD Container Integration Test Runner"
echo "===================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: docker-compose is not installed. Please install docker-compose first."
    exit 1
fi

# Function to cleanup
cleanup() {
    echo -e "\nCleaning up..."
    docker-compose down -v
    docker network prune -f
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Build and start services
echo -e "\n1. Building test environment..."
docker-compose build

echo -e "\n2. Starting Docker-in-Docker environment..."
docker-compose up -d dind-host vlan-bridge-setup

# Wait for DinD to be ready
echo -e "\n3. Waiting for Docker-in-Docker to be ready..."
sleep 10

# Check if DinD is running
if docker-compose exec -T dind-host docker version &> /dev/null; then
    echo "   ✓ Docker-in-Docker is ready"
else
    echo "   ✗ Docker-in-Docker failed to start"
    exit 1
fi

# Run integration tests
echo -e "\n4. Running integration tests..."
docker-compose run --rm pod-controller

# Show logs if requested
if [ "$1" == "--logs" ]; then
    echo -e "\n5. Container logs:"
    docker-compose logs
fi

echo -e "\n✓ Integration tests completed!"