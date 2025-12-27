#!/bin/bash

# AI Cloud Drive - Deployment Script
set -e

echo "🚀 AI Cloud Drive Deployment Script"
echo "===================================="

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi

# Check for Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed"
    exit 1
fi

# Environment
ENV=${1:-development}
echo "📦 Deploying in $ENV mode"

# Create .env if not exists
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example"
    cp .env.example .env
    echo "⚠️  Please update .env with production values!"
fi

# Create certs directory
mkdir -p certs

case $ENV in
    development)
        echo "🔧 Starting development environment..."
        docker-compose up --build -d
        ;;
    production)
        echo "🏭 Starting production environment..."
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
        ;;
    *)
        echo "❌ Unknown environment: $ENV"
        echo "Usage: ./deploy.sh [development|production]"
        exit 1
        ;;
esac

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo ""
echo "🔍 Service Health:"
docker-compose ps

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📍 Access Points:"
echo "   - App:      http://localhost"
echo "   - API:      http://localhost:8000"
echo "   - Docs:     http://localhost:8000/docs"
echo "   - MinIO:    http://localhost:9001"
echo ""
echo "📝 Logs: docker-compose logs -f [service]"
echo "🛑 Stop: docker-compose down"
