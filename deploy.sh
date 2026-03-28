#!/bin/bash
# =====================================================
# Script de déploiement Production LLM Load Balancer
# =====================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Vérification des dépendances
check_dependencies() {
    log_info "Vérification des dépendances..."
    
    command -v python3 >/dev/null 2>&1 || {
        log_error "Python3 est requis mais non installé."
        exit 1
    }
    
    python3 -c "import fastapi" 2>/dev/null || {
        log_error "FastAPI n'est pas installé. Exécutez: pip install -r requirements.txt"
        exit 1
    }
    
    log_info "Dépendances vérifiées."
}

# Démarrage des workers
start_workers() {
    log_info "Démarrage des workers..."
    
    python3 worker/main_llm.py --id M1 --port 8001 --backend simulated &
    PID_M1=$!
    
    python3 worker/main_llm.py --id M2 --port 8002 --backend simulated &
    PID_M2=$!
    
    python3 worker/main_llm.py --id M3 --port 8003 --backend simulated &
    PID_M3=$!
    
    log_info "Workers démarrés (PIDs: $PID_M1, $PID_M2, $PID_M3)"
}

# Démarrage de l'orchestrateur
start_orchestrator() {
    log_info "Démarrage de l'orchestrateur..."
    
    export CONFIG_PATH="config/workers.yaml"
    export PORT=8000
    
    python3 -m uvicorn orchestrator.main_production_final:app --host 0.0.0.0 --port 8000
    
    log_info "Orchestrateur démarré sur le port 8000"
}

# Affichage du statut
show_status() {
    echo ""
    echo "========================================"
    echo "         STATUT DU SYSTÈME"
    echo "========================================"
    echo ""
    echo "Orchestrateur: http://localhost:8000"
    echo "Dashboard:     http://localhost:8000/"
    echo "Stats:         http://localhost:8000/stats"
    echo "Metrics:       http://localhost:8000/metrics"
    echo "Health:        http://localhost:8000/health"
    echo ""
    echo "Workers:"
    echo "  M1: http://localhost:8001"
    echo "  M2: http://localhost:8002"
    echo "  M3: http://localhost:8003"
    echo ""
    echo "API Endpoints:"
    echo "  POST /infer         - Inference"
    echo "  GET  /queue/{id}    - Queue status"
    echo "  GET  /dead-letter  - Failed requests"
    echo "  WS   /ws            - WebSocket"
    echo ""
}

# Arrêt propre
stop_services() {
    log_info "Arrêt des services..."
    pkill -f "worker/main_llm.py" || true
    pkill -f "uvicorn" || true
    log_info "Services arrêtés."
}

# Menu principal
case "${1:-start}" in
    start)
        check_dependencies
        start_workers
        sleep 2
        start_orchestrator
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 2
        start
        ;;
    status)
        show_status
        ;;
    workers)
        check_dependencies
        start_workers
        wait
        ;;
    orchestrator)
        check_dependencies
        start_orchestrator
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|workers|orchestrator}"
        exit 1
        ;;
esac
