#!/bin/bash
# LLM Orchestrator Visualization - Quick Commands

# 🚀 START EVERYTHING (One Command)
echo "🚀 Starting Full Stack..."
docker-compose -f docker-compose.v2.yml up -d

# ⏳ Wait for services to start
echo "⏳ Waiting for services to start (10s)..."
sleep 10

# 📊 Show running containers
echo "✅ Running containers:"
docker-compose -f docker-compose.v2.yml ps

# 🌐 Show access URLs
echo ""
echo "🌐 Access Dashboards:"
echo "   🎨 WebUI (Real-time):     http://localhost:8000"
echo "   📊 Grafana:               http://localhost:3000 (admin/admin)"
echo "   📈 Prometheus:            http://localhost:9090"
echo ""

# 📝 Show next steps
echo "📝 Next steps:"
echo "   1. Open http://localhost:8000 in browser"
echo "   2. In new terminal, run: python demo_load.py"
echo "   3. Watch the dashboard update in real-time!"
echo ""

# Optional: Start load demo in background
read -p "Run demo load test now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 Starting load test..."
    python demo_load.py
fi
