#!/bin/bash
# Lance la batterie de scénarios MatchConsult
# Usage :
#   bash tests/run.sh                          # depuis la racine du projet
#   bash tests/run.sh http://51.83.44.48:8000  # URL personnalisée

URL=${1:-http://localhost:8000}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  Démarrage des scénarios de test..."
echo "  (logs backend disponibles via : docker compose logs -f backend)"
echo ""

python3 "$SCRIPT_DIR/run_scenarios.py" "$URL"
EXIT=$?

if [ $EXIT -eq 0 ]; then
    echo "  Tous les scénarios ont passé."
elif [ $EXIT -eq 2 ]; then
    echo "  Application non disponible — vérifier docker compose ps"
else
    echo "  Des scénarios ont échoué — consulter le rapport ci-dessus."
fi

exit $EXIT
