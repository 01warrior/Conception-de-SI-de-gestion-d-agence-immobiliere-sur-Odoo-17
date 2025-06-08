from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class PropertyType(models.Model):
    _name = 'property.type'
    _description = 'Type de Propriété'
    
    name = fields.Char('Type', required=True)
    description = fields.Text('Description')

class Property(models.Model):
    _name = 'property.property'
    _description = 'Propriété Immobilière'
    _order = 'create_date desc'
    _rec_name = 'title'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Informations générales
    title = fields.Char('Titre', required=True)
    reference = fields.Char('Référence', required=True, copy=False, default='New')
    description = fields.Html('Description')
    
    # Type et caractéristiques
    property_type_id = fields.Many2one('property.type', string='Type', required=True)
    transaction_type = fields.Selection([
        ('sale', 'Vente'),
        ('rent', 'Location'),
        ('both', 'Vente et Location')
    ], string='Type de Transaction', required=True, default='sale')
    
    # Prix
    sale_price = fields.Monetary('Prix de Vente', currency_field='currency_id')
    rent_price = fields.Monetary('Prix de Location/mois', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency',string="Devise", default=lambda self: self.env.company.currency_id)
    
    # Caractéristiques
    surface = fields.Float('Surface (m²)')
    rooms = fields.Integer('Nombre de pièces')
    bedrooms = fields.Integer('Chambres')
    bathrooms = fields.Integer('Salles de bain')
    floor = fields.Integer('Étage')
    
    # Adresse
    street = fields.Char('Rue')
    city = fields.Char('Ville')
    zip_code = fields.Char('Code Postal')
    country_id = fields.Many2one('res.country', string='Pays')
    
    # Relations
    owner_id = fields.Many2one('res.partner', string='Propriétaire', required=True, domain=[('is_property_owner', '=', True)]) 
    agent_id = fields.Many2one('res.users', string='Agent Responsable', default=lambda self: self.env.user)
    mandate_ids = fields.One2many('property.mandate', 'property_id', string="Mandats Associés")
    
    # État
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('available', 'Disponible'),
        ('reserved', 'Réservé'),
        ('sold', 'Vendu'),
        ('rented', 'Loué'),
        ('cancelled', 'Annulé')
    ], string='État', default='draft', tracking=True)
    
    # Dates
    available_date = fields.Date('Disponible à partir du')
    
    # Visites
    visit_ids = fields.One2many('property.visit', 'property_id', string='Visites Programmées')
    visit_count = fields.Integer('Nombre de Visites', compute='_compute_visit_count',store=True) #store pour stocker le résultat dans la base de données
    
    # Offres
    offer_ids = fields.One2many('property.offer', 'property_id', string="Offres Reçues")
    offer_count = fields.Integer(string="Nb. Offres", compute="_compute_offer_count", store=True)

    # Images
    image_main = fields.Image('Image Principale', help="Image principale affichée dans les listes et kanbans.")
    image_ids = fields.One2many('property.image', 'property_id', string='Images')
    
    @api.depends('offer_ids')
    def _compute_offer_count(self):
        for record in self:
            record.offer_count = len(record.offer_ids)

    @api.model
    def create(self, vals):
        if vals.get('reference', 'New') == 'New' or vals.get('reference', _('Nouveau')) == _('Nouveau'): # Gère "New" ou sa traduction
            vals['reference'] = self.env['ir.sequence'].next_by_code('property.property.sequence') or _('Nouveau')
        return super(Property, self).create(vals)
    
    @api.depends('visit_ids')
    def _compute_visit_count(self):
        for record in self:
            record.visit_count = len(record.visit_ids)
    
    def action_make_available(self):
        self.state = 'available'
    
    def action_reserve(self):
        self.state = 'reserved'
    
    def action_sold(self):
        for prop in self:
            prop.state = 'sold'
            prop.message_post(body=_("Propriété marquée comme VENDUE."))
            
            # Rechercher un mandat actif ou en brouillon pour cette propriété
            active_mandate = self.env['property.mandate'].search([
                ('property_id', '=', prop.id),
                ('state', 'in', ['draft', 'active'])
            ], limit=1)

            if active_mandate:
                if active_mandate.transaction_type in ['sale', 'both']:
                    # Le mandat correspond à une vente, on peut le marquer comme complété pour la vente
                    active_mandate.action_mark_sold_rented() # Cette méthode mettra l'état et appellera la génération de commission
                    prop.message_post(body=_(f"Le mandat associé {active_mandate.reference} a été mis à jour pour refléter la vente."))
                else: # Le mandat était uniquement pour location, mais le bien est vendu
                    active_mandate.write({'state': 'completed_other_way'}) # Ou un autre état pour indiquer une clôture non standard
                    prop.message_post(body=_(f"Le mandat de location {active_mandate.reference} a été clôturé car la propriété a été vendue."))
            else:
                prop.message_post(body=_("Aucun mandat actif trouvé à mettre à jour pour cette vente."))
    
    def action_rented(self):
        for prop in self:
            prop.state = 'rented'
            prop.message_post(body=_("Propriété marquée comme LOUÉE."))

            active_mandate = self.env['property.mandate'].search([
                ('property_id', '=', prop.id),
                ('state', 'in', ['draft', 'active'])
            ], limit=1)

            if active_mandate:
                if active_mandate.transaction_type in ['rent', 'both']:
                    active_mandate.action_mark_sold_rented()
                    prop.message_post(body=_(f"Le mandat associé {active_mandate.reference} a été mis à jour pour refléter la location."))
                else: # Le mandat était uniquement pour vente, mais le bien est loué
                    active_mandate.write({'state': 'completed_other_way'})
                    prop.message_post(body=_(f"Le mandat de vente {active_mandate.reference} a été clôturé car la propriété a été louée."))
            else:
                prop.message_post(body=_("Aucun mandat actif trouvé à mettre à jour pour cette location."))


    #ici ma fonction pour créer un mandat à partir d'une propriété réservée
    def action_create_mandate_for_reserved_property(self):
        self.ensure_one() # S'assurer qu'on travaille sur une seule propriété

        if self.state != 'reserved':
            raise UserError(_("Un mandat ne peut être créé pour cette action que si la propriété est à l'état 'Réservé'."))

        # Vérifier si un mandat actif ou en brouillon n'existe pas déjà pour éviter les doublons
        # (Ceci est une vérification optionnelle mais une bonne pratique)
        existing_mandate = self.env['property.mandate'].search([
            ('property_id', '=', self.id),
            ('state', 'in', ['draft', 'active']) # Ou les états qui indiquent un mandat en cours
        ], limit=1)

        if existing_mandate:
            # Option 1: Ouvrir le mandat existant
            # return {
            #     'type': 'ir.actions.act_window',
            #     'res_model': 'property.mandate',
            #     'view_mode': 'form',
            #     'res_id': existing_mandate.id,
            #     'target': 'current',
            # }
            # Option 2: Lever une erreur
            raise UserError(_("Un mandat (Réf: %s) existe déjà pour cette propriété à l'état '%s'.") % (existing_mandate.reference, existing_mandate.state))


        # Pré-remplir les valeurs pour le nouveau mandat
        # Trouver l'offre acceptée pour pré-remplir le prix du mandat, si possible
        accepted_offer = self.env['property.offer'].search([
            ('property_id', '=', self.id),
            ('state', '=', 'accepted')
        ], order='offer_date desc', limit=1) # Prendre la plus récente offre acceptée

        mandate_price_to_use = self.sale_price if self.transaction_type in ['sale', 'both'] else self.rent_price
        if accepted_offer:
            mandate_price_to_use = accepted_offer.offer_price

        mandate_vals = {
            'property_id': self.id,
            # 'owner_id': self.owner_id.id, # owner_id sur le mandat est related=property_id.owner_id, donc pas besoin ici
            'agent_id': self.agent_id.id or self.env.user.id,
            # 'transaction_type': self.transaction_type, # transaction_type sur mandat est related, pas besoin ici
            'mandate_price': mandate_price_to_use,
            'start_date': fields.Date.today(),
            # 'state': 'draft', # L'état par défaut du mandat est 'draft'
            # Vous pouvez ajouter d'autres valeurs par défaut si pertinent
        }
        
        mandate = self.env['property.mandate'].create(mandate_vals)
        
        self.message_post(body=_(f"Mandat <a href='#' data-oe-model='property.mandate' data-oe-id='{mandate.id}'>{mandate.reference}</a> créé à partir de la propriété réservée."))

        # Ouvrir le formulaire du mandat nouvellement créé
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'property.mandate',
            'view_mode': 'form',
            'res_id': mandate.id,
            'target': 'current', # Ouvrir dans la même fenêtre
            'context': self.env.context, # Passer le contexte actuel
        }
        
    # ici on ajoute une action ppour visualiser les visites associées à cette propriété
    def action_view_visits(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Visites pour %s') % self.title,
            'res_model': 'property.visit',
            'view_mode': 'tree,form,calendar',
            'domain': [('property_id', '=', self.id)],
            'context': {'default_property_id': self.id,'default_agent_id': self.agent_id.id if self.agent_id else self.env.user.id}
        }

class PropertyImage(models.Model):
    _name = 'property.image' 
    _description = 'Images Propriété'
    _order = 'sequence, id' # Pour trier par séquence et ID

    name = fields.Char('Titre/Description Image')
    sequence = fields.Integer('Séquence', default=10) # champ pour definir l'ordre d'affichage des images
    
    property_id = fields.Many2one('property.property', string='Propriété',required=True, ondelete='cascade')
    image = fields.Image('Image', required=True)
    name = fields.Char('Nom')
    is_main_image = fields.Boolean(
        string="Est l'image principale de la galerie ?", 
        default=False,
        help="Cochez cette case si cette image doit être considérée comme l'image principale pour la galerie de cette propriété. "
             "Cela pourrait mettre à jour l'image principale affichée sur la propriété elle-même."
    )