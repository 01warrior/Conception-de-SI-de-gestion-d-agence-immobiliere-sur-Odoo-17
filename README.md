# Système de Gestion d'Agence Immobilière - Odoo 17

## 📋 Description
Module Odoo 17 pour la gestion complète d'une agence immobilière avec gestion des biens, clients, mandats, visites et offres.

## ✨ Fonctionnalités

- **Gestion des Biens** : Propriétés en vente/location avec caractéristiques détaillées
- **Gestion des Clients** : Propriétaires, acheteurs et locataires
- **Mandats** : Suivi des contrats de vente et de location
- **Visites** : Planification et suivi des rendez-vous
- **Offres** : Gestion des propositions d'achat/location
- **Notifications** : Templates d'emails automatiques

## 🚀 Installation

### Prérequis
- Docker & Docker Compose
- Git

### Démarrage rapide

1. **Cloner le projet**
```bash
git clone https://github.com/01warrior/Conception-de-SI-de-gestion-d-agence-immobiliere-sur-Odoo-17.git
cd Conception-de-SI-de-gestion-d-agence-immobiliere-sur-Odoo-17
```

2. **Lancer les conteneurs**
```bash
docker-compose up -d
```

3. **Accéder à Odoo**
- URL : `http://localhost:8069`
- Base de données : `postgres`
- Email : admin
- Mot de passe : admin

4. **Installer le module**
- Aller dans Apps
- Rechercher "gestion_agence_immobiliere"
- Cliquer sur Installer

## 🏗️ Structure du Projet

```
extra-addons/gestion_agence_immobiliere/
├── models/          # Modèles de données (Bien, Client, Mandat, Visite, Offre)
├── views/           # Interfaces utilisateur
├── data/            # Données initiales et templates
├── security/        # Droits d'accès et règles de sécurité
└── controllers/     # Contrôleurs web
```

## 👥 Auteur
Soumaila Savadogo

## 📄 Licence
Module développé dans le cadre d'un projet académique