PARTIE 2 : Load Balancing d’instances LLM (Inference)
1. Objectif
L'objectif est de concevoir et mettre en œuvre un mécanisme de répartition de charge pour l'inférence de modèles de langage (LLM) afin de :
Distribuer les requêtes vers plusieurs instances d'inférence de manière optimale.
Garantir la haute disponibilité du service.
Assurer la centralisation des réponses vers le point d'entrée initial.
Gérer efficacement les surcharges et les défaillances critiques.
2. Contexte et Problématique
Le système s'appuie sur un pool de machines (M1, M2, M3), chacune hébergeant une instance d'inférence ou une API simulée. Chaque unité de calcul est sujette à des variations de performance : indisponibilité réseau, surcharge CPU/GPU, latence accrue ou erreurs applicatives.
Le flux doit impérativement respecter le schéma suivant : Requête du client → Machine principale (Orchestrateur) → Instance d'inférence ou Worker (M1/M2/M3) → Machine principale (Orchestrateur) → Réponse attendue pour le client
 
3. Contraintes Techniques
A. Résilience et Détection d'erreurs
Le système doit être capable de réagir aux incidents suivants (ou autres cas possibles) :
Timeouts : Absence de réponse dans un délai imparti.
Erreurs HTTP/Application : Codes d'erreurs 5xx ou réponses malformées.
Saturation : Instance incapable d'accepter de nouvelles connexions.
 
B. Critères de Sélection (Orchestration)
La stratégie de distribution ne doit pas être purement aléatoire. Elle doit s'appuyer sur des indicateurs de santé (Healthchecks) et de performance :
Disponibilité : État binaire de l'instance.
Charge active : Utilisation des ressources (CPU/GPU) et nombre de requêtes concurrentes.
Latence historique : Temps de réponse moyen des dernières requêtes.
Autres à trouver et à compléter
 
C. Gestion de la File d'Attente (Queueing)
En cas d'indisponibilité totale du cluster :
La requête doit être persistée dans une file d'attente.
Un mécanisme de Retry doit être configuré.
Le traitement doit reprendre automatiquement dès qu'une ressource se libère.
 
4. Spécificités liées aux LLM
Bien que les modèles puissent être simulés, l'architecture doit anticiper les caractéristiques propres à l'IA générative :
Hétérogénéité des requêtes : La durée de génération varie selon le nombre de tokens demandés.
Coût de calcul : Optimisation du routage pour éviter le gaspillage de ressources.
Instabilité de la latence : Gestion spécifique des flux de streaming ou des temps de pré-traitement longs.
 
5. Livrables Attendus
1. Architecture du Système
Schéma de communication entre les nœuds.
Positionnement du Load Balancer (Reverse Proxy ou Orchestrateur maison).
Logique de centralisation des flux de données.
2. Stratégie de Distribution
Description de la stratégie optée
Configuration des seuils de timeout et politiques de santé.
3. Gestion des Échecs
Protocole de basculement (Fallback).
Logique de mise en attente et priorisation des requêtes.
4. Code tout prêt à être intégré sur une vraie machine, et sur une vraie instance de model LLM