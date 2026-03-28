# Gestion des Échecs et Résilience

## Scénarios d'Échec

### 1. Timeout
- **Détection** : Pas de réponse dans `request_timeout`
- **Action** : Retry sur autre worker
- **Fallback** : File d'attente si tous indisponibles

### 2. Erreur HTTP 5xx
- **Détection** : Code erreur 500, 502, 503, 504
- **Action** : Retry immédiat sur worker alternatif
- **Logging** : Erreur enregistrée avec détails

### 3. Saturation (Worker)
- **Détection** : File d'attente pleine ou connexions max
- **Action** : Routing vers autre worker
- **Alerte** : Notification si tous saturés

### 4. Indisponibilité Totale
- **Détection** : Aucun worker healthy
- **Action** : Mise en attente (queue) + retry périodique

## Circuit Breaker

```
États: CLOSED → OPEN → HALF_OPEN

CLOSED   : Fonctionnement normal
OPEN     : Bloque les requêtes (après 5 erreurs)
HALF_OPEN: Test de récupération (après 30s)
```

## File d'Attente

| Paramètre | Valeur |
|-----------|--------|
| Max size | 100 requêtes |
| TTL | 5 minutes |
| Retry interval | 10 secondes |

## Priorisation

1. **Haute** : Requêtes critiques (timeout imminent)
2. **Normale** : Requêtes standard
3. **Basse** : Requêtes de background

## Métriques de Résilience

- Taux d'erreur par worker
- Nombre de retries
- Temps moyen de recovery
- Disponibilité par worker (SLA)
