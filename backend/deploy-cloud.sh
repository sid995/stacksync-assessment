#!/bin/bash

# Complete deployment script for Google Cloud Run
set -e

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION=${REGION:-us-central1}
SERVICE_NAME="python-executor"
IMAGE_NAME="python-executor"

if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: No Google Cloud project configured"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "🚀 Deploying Python Code Execution API to Google Cloud Run"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Service: $SERVICE_NAME"
echo "   Image: $IMAGE_NAME"
echo ""

# Build with specific Dockerfile and BUILD argument
echo "🔨 Building Docker image with Dockerfile.cloud..."
docker build -f Dockerfile.cloud --build-arg BUILD=cloud -t gcr.io/$PROJECT_ID/$IMAGE_NAME .

# Push to registry
echo "📤 Pushing image to Google Container Registry..."
docker push gcr.io/$PROJECT_ID/$IMAGE_NAME

# Deploy to Cloud Run
echo " Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8080 \
    --memory 1Gi \
    --cpu 1 \
    --timeout 30 \
    --max-instances 10 \
    --min-instances 0 \
    --concurrency 10 \
    --set-env-vars BUILD=cloud,SCRIPT_TIMEOUT=10,MAX_SCRIPT_SIZE=10000,FLASK_DEBUG=false

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

echo ""
echo "✅ Deployment complete!"
echo "🌍 Service URL: $SERVICE_URL"
echo ""
echo "🔍 Test the deployment:"
echo "   curl $SERVICE_URL/health"
echo ""
echo "📝 Example API call:"
echo "   curl -X POST $SERVICE_URL/execute \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{\"script\": \"def main(): return {\\\"message\\\": \\\"Hello from Cloud Run!\\\"}\"}'"
echo ""
echo "📊 Monitor logs:"
echo "   gcloud logs tail --follow --service=$SERVICE_NAME --region=$REGION"