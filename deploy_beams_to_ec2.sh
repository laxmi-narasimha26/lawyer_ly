#!/bin/bash
# Deploy Beams Background to EC2
# Instance: i-0e9c5df4c9271d19d
# IP: 13.233.134.236

set -e

echo "🚀 Deploying Beams Background to EC2..."
echo "Instance: i-0e9c5df4c9271d19d"
echo "IP: 13.233.134.236"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Pull latest code
echo -e "${BLUE}Step 1: Pulling latest code from GitHub...${NC}"
cd /home/ubuntu/lawyer_ly
git pull origin master

# 2. Install dependencies
echo -e "${BLUE}Step 2: Installing Three.js dependencies...${NC}"
cd frontend
npm install --legacy-peer-deps

# 3. Build frontend
echo -e "${BLUE}Step 3: Building production bundle...${NC}"
npm run build

# 4. Restart service (adjust based on your setup)
echo -e "${BLUE}Step 4: Restarting frontend service...${NC}"

# Try different service managers
if systemctl is-active --quiet lawyer-ly-frontend; then
    echo "Using systemd..."
    sudo systemctl restart lawyer-ly-frontend
elif command -v pm2 &> /dev/null; then
    echo "Using PM2..."
    pm2 restart lawyer-ly-frontend
elif [ -f docker-compose.yml ]; then
    echo "Using Docker Compose..."
    docker-compose restart frontend
else
    echo "⚠️  Please manually restart your frontend service"
fi

# 5. Verify
echo -e "${BLUE}Step 5: Verifying deployment...${NC}"
sleep 3
curl -I http://localhost:3000 || curl -I http://localhost:3001 || curl -I http://localhost:3002

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Check your site at: http://13.233.134.236"
echo ""
echo "Verify these features:"
echo "  ✓ Beams background displays"
echo "  ✓ 3D animation is smooth"
echo "  ✓ Black & white theme maintained"
echo "  ✓ No console errors"
