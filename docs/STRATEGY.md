# Stratégie de Distribution

## Algorithme de Routing : Weighted Least Connections

### Principe
Le worker avec le moins de connexions actives et le meilleur score de santé est sélectionné.

### Critères de Sélection

| Critère | Pondération | Description |
|---------|-------------|-------------|
| Disponibilité | 100% | Worker must be healthy (binary) |
| Charge active | 40% | Nombre de requêtes en cours |
| Latence moyenne | 30% | Temps de réponse moyen (dernières 10 requêtes) |
| Score santé | 30% | Composite des healthchecks |

### Calcul du Score

```
score_worker = (1 / (connexions_actives + 1)) * (1 / latence_moyenne) * score_santé
```

### Healthchecks

| Paramètre | Valeur |
|-----------|--------|
| Intervalle | 5 secondes |
| Timeout | 2 secondes |
| Seuil d'échec | 3 échecs consécutifs |
| Seuil de recovery | 2 succès consécutifs |

### Configuration des Timeouts

| Paramètre | Valeur |
|-----------|--------|
| Request Timeout | 30 secondes |
| Connect Timeout | 5 secondes |
| Idle Timeout | 60 secondes |

### Politiques

1. **Circuit Breaker** : Ouverture après 5 erreurs consécutives
2. **Retry** : 3 tentatives avec backoff exponentiel (1s, 2s, 4s)
3. **Queue** : Requête mise en attente si tous les workers saturés

## Stratégies Alternatives Implémentées

- `round_robin` : Distribution séquentielle
- `least_connections` : Moins de connexions actives
- `weighted` : Pondération manuelle
- `adaptive` : Basé sur les métriques (notre choix)
