# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class PropertyOffer(models.Model):
    _name = 'property.offer'
    _description = 'Offre sur Propriété'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Référence Offre", required=True, copy=False, readonly=True, index=True, default=lambda self: _('Nouveau'))
    
    property_id = fields.Many2one(
        'property.property', 
        string='Propriété Concernée', 
        required=True,
        domain="[('state', 'in', ['available', 'reserved'])]" # On ne peut faire une offre que sur un bien dispo/réservé
    )
    partner_id = fields.Many2one('res.partner', string='Client Offrant', required=True)
    
    offer_price = fields.Monetary(string="Montant de l'Offre", required=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='property_id.currency_id', string="Devise", readonly=True, store=True) # Devise de la propriété

    offer_date = fields.Date(string="Date de l'Offre", default=fields.Date.today, required=True)
    validity_date = fields.Date(string="Date de Validité de l'Offre")
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('submitted', 'Soumise'),
        ('negotiation', 'En Négociation'),
        ('accepted', 'Acceptée'),
        ('refused', 'Refusée'),
        ('cancelled', 'Annulée (par client/agence)')
    ], string='État', default='draft', tracking=True, copy=False)

    notes = fields.Text(string="Notes / Conditions de l'Offre")

    # --- Champs pour lier à la vente/location si acceptée ---
    # sale_order_id = fields.Many2one('sale.order', string='Commande Client (Commission)', readonly=True, copy=False)

    # === Séquence ===
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('property.offer.sequence') or _('Nouveau')
        return super().create(vals_list)

    # === Actions (Boutons) ===
    def action_submit_offer(self):
        self.write({'state': 'submitted'})

    def action_start_negotiation(self):
        self.write({'state': 'negotiation'})

    def action_accept_offer(self):
        for offer in self:
            # 1. Vérifier si la propriété est dans un état acceptable pour une nouvelle offre
            # On ne devrait accepter une offre que si la propriété est 'available'
            # OU si elle est 'reserved' MAIS par aucune autre offre actuellement acceptée.
            # Ceci est plus complexe. Pour l'instant, soyons stricts :
            if offer.property_id.state != 'available':
                # Vérifier si elle est réservée par une autre offre DEJA acceptée
                # S'il y a une autre offre acceptée pour ce bien, on ne peut pas accepter celle-ci.
                conflicting_accepted_offer = self.search_count([
                    ('property_id', '=', offer.property_id.id),
                    ('state', '=', 'accepted'),
                    ('id', '!=', offer.id) # Exclure l'offre actuelle si elle était déjà acceptée (peu probable ici)
                ])
                if conflicting_accepted_offer:
                    raise UserError(_("Impossible d'accepter cette offre. La propriété '%s' est déjà réservée par une autre offre acceptée.") % offer.property_id.display_name)
                # Si la propriété est 'reserved' mais pas par une autre offre acceptée, c'est peut-être OK (ex: réservation manuelle)
                # Mais pour la simplicité, on peut exiger 'available' ou ajouter une logique plus fine.
                # Pour l'instant, si on veut être strict et simple :
                if offer.property_id.state != 'available':
                     raise UserError(_("Cette offre ne peut être acceptée que si la propriété est à l'état 'Disponible'. État actuel : %s") % offer.property_id.state)


            # 2. Refuser toutes les autres offres "ouvertes" pour cette propriété
            other_open_offers = self.search([
                ('property_id', '=', offer.property_id.id),
                ('id', '!=', offer.id),
                ('state', 'in', ['draft', 'submitted', 'negotiation'])
            ])
            
            if other_open_offers:
                # On utilise une méthode qui change juste l'état sans effets de bord compliqués
                other_open_offers.write({'state': 'refused'}) 
                for other_offer in other_open_offers:
                    other_offer.message_post(body=_("Cette offre a été automatiquement refusée car une autre offre a été acceptée pour la même propriété."))

            # 3. Accepter l'offre actuelle et mettre à jour la propriété
            offer.write({'state': 'accepted'})
            offer.property_id.write({'state': 'reserved'}) # Ou un nouvel état 'under_offer' / 'offer_accepted'
            
            offer.message_post(body=_("L'offre a été acceptée ! La propriété '%s' est maintenant réservée.") % offer.property_id.display_name)

            # Optionnel : Déclencher la création de la commande de commission ici ou sur le mandat
            # offer._create_commission_sale_order()

        return True

    def action_refuse_offer(self):
        self.write({'state': 'refused'})
        # Si la propriété était réservée par CETTE offre, la rendre à nouveau disponible
        # Ceci est une logique simplifiée, il faudrait s'assurer qu'aucune autre offre n'est acceptée.
        if self.property_id.state == 'reserved': # Potentiellement affiner cette condition
             is_another_offer_accepted = self.search_count([
                ('property_id', '=', self.property_id.id),
                ('state', '=', 'accepted'),
                ('id', '!=', self.id)
             ])
             if not is_another_offer_accepted:
                self.property_id.action_make_available() 
        self.message_post(body=_("L'offre a été refusée."))
    
    def action_refuse_silently(self): # Pour refuser en batch sans pop-up
        self.write({'state': 'refused'})

    def action_cancel_offer(self):
        # Avant d'annuler, vérifier si elle était acceptée et si la propriété doit redevenir disponible
        if self.state == 'accepted' and self.property_id.state == 'reserved':
             is_another_offer_accepted = self.search_count([
                ('property_id', '=', self.property_id.id),
                ('state', '=', 'accepted'),
                ('id', '!=', self.id)
             ])
             if not is_another_offer_accepted:
                self.property_id.action_make_available()
        self.write({'state': 'cancelled'})
        self.message_post(body=_("L'offre a été annulée."))

    def action_reset_to_draft(self):
        if self.state == 'accepted' and self.property_id.state == 'reserved':
             is_another_offer_accepted = self.search_count([
                ('property_id', '=', self.property_id.id),
                ('state', '=', 'accepted'),
                ('id', '!=', self.id)
             ])
             if not is_another_offer_accepted:
                self.property_id.action_make_available()
        self.write({'state': 'draft'})