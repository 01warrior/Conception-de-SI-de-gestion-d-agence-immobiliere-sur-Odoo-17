from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

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
    
    # Images
    image_main = fields.Image('Image Principale', help="Image principale affichée dans les listes et kanbans.")
    image_ids = fields.One2many('property.image', 'property_id', string='Images')
    
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
        self.state = 'sold'
    
    def action_rented(self):
        self.state = 'rented'
    
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