#!/bin/bash

set -e

echo "🚀 Deploying Cyber Threat Hunter..."

# Build and push images
echo "📦 Building Docker images..."
docker build -t your-registry/threat-hunter-backend:latest ./backend
docker build -t your-registry/threat-hunter-frontend:latest ./frontend

echo "🔄 Pushing to registry..."
docker push your-registry/threat-hunter-backend:latest
docker push your-registry/threat-hunter-frontend:latest

# Deploy based on environment
if [ "$1" = "kubernetes" ]; then
    echo "☸️ Deploying to Kubernetes..."
    kubectl apply -f deploy/kubernetes/
elif [ "$1" = "swarm" ]; then
    echo "🐳 Deploying to Docker Swarm..."
    docker stack deploy -c deploy/docker-stack.yml threat-hunter
else
    echo "🐙 Deploying with Docker Compose..."
    docker-compose -f docker-compose.prod.yml up -d
fi

echo "✅ Deployment complete!"
