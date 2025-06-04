from odoo import models, fields, api, _ #_ pour la traduction si besoin

class ResPartnerPropertyExtension(models.Model): # Nom de classe descriptif
    _inherit = 'res.partner' # IMPORTANT: Indique que l'on étend un modèle existant

    # --- Champs pour identifier le rôle du contact dans l'immobilier ---
    is_property_owner = fields.Boolean(string='Est un Propriétaire')
    is_potential_buyer = fields.Boolean(string='Est un Acheteur Potentiel')
    is_potential_renter = fields.Boolean(string='Est un Locataire Potentiel')
    
    client_type = fields.Selection([ 
        ('buyer', 'Acheteur'),
        ('renter', 'Locataire'),
        ('owner_seller', 'Propriétaire Vendeur'), # Plus spécifique
        ('owner_lessor', 'Propriétaire Bailleur'), # Plus spécifique
        ('investor', 'Investisseur'),
        ('other', 'Autre')
    ], string='Type de Client Immobilier')

    # --- Champs pour les préférences de recherche (principalement pour acheteurs/locataires) ---
    budget_min = fields.Monetary(string='Budget Minimum', currency_field='currency_id_partner_pref')
    budget_max = fields.Monetary(string='Budget Maximum', currency_field='currency_id_partner_pref')
    # On utilise une devise spécifique pour les préférences, qui peut être différente de la devise principale du partenaire
    # Surtout si le partenaire est une compagnie avec une devise, mais cherche dans une autre devise.
    # Par défaut, on peut prendre la devise de la compagnie de l'utilisateur actuel.
    currency_id_partner_pref = fields.Many2one(
        'res.currency', 
        string="Devise du Budget (Préférences)", 
        default=lambda self: self.env.company.currency_id
    )

    preferred_location_city = fields.Char(string='Ville Préférée')
    preferred_location_notes = fields.Text(string='Notes sur Localisation Préférée')
    
    preferred_property_type_id = fields.Many2one('property.type', string='Type de Propriété Préféré')
    mandate_ids_as_owner = fields.One2many('property.mandate', 'owner_id', string='Mandats en tant que Propriétaire')
    
    min_surface_desired = fields.Float(string='Surface Minimum Désirée (m²)')
    min_rooms_desired = fields.Integer(string='Nombre de Pièces Minimum Désiré')
    min_bedrooms_desired = fields.Integer(string='Nombre de Chambres Minimum Désiré')

    # --- Champs relationnels (on les décommentera et implémentera plus tard, Phase avancée) ---
    # owned_property_ids = fields.One2many('property.property', 'owner_id', string='Propriétés Possédées')
    # Ceci nécessitera que le champ 'owner_id' sur 'property.property' soit bien défini.

    # visit_ids_as_client = fields.One2many('property.visit', 'client_id', string='Visites Effectuées en tant que Client')
    # Ceci nécessitera la création du modèle 'property.visit' et du champ 'client_id'.

    # mandate_ids_as_owner = fields.One2many('property.mandate', 'owner_id', string='Mandats en tant que Propriétaire')
    # Ceci nécessitera la création du modèle 'property.mandate'.