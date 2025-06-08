# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError # Pour les messages d'erreur plus tard
from dateutil.relativedelta import relativedelta # Pour calculer la date de fin

class PropertyMandate(models.Model):
    _name = 'property.mandate'
    _description = 'Mandat de Vente ou Location de Propriété'
    _order = 'create_date desc'
    _rec_name = 'reference' # Ou une combinaison de référence et nom de propriété
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- Référence et Informations Principales ---
    reference = fields.Char(
        string='Référence Mandat', 
        required=True, 
        copy=False, 
        readonly=True, 
        index=True, 
        default=lambda self: _('Nouveau')
    )
    name = fields.Char(string="Nom du Mandat", compute="_compute_mandate_name", store=True, help="Nom descriptif du mandat, ex: Mandat Vente - [Nom Propriété]")

    property_id = fields.Many2one(
        'property.property', 
        string='Propriété Concernée', 
        required=True, 
        domain="[('state', 'in', ['draft', 'available'])]", # On ne peut mandater que des biens dispo ou en brouillon
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company', 
        string='Compagnie', 
        default=lambda self: self.env.company, # Compagnie de l'utilisateur par défaut
        required=True, # Souvent requis pour la cohérence des données
        readonly=True, # Souvent en lecture seule après création ou lié à d'autres logiques
        states={'draft': [('readonly', False)]} # Exemple pour le rendre modifiable en brouillon
    )

    owner_id = fields.Many2one(
        related='property_id.owner_id', # Se remplit automatiquement depuis la propriété
        string='Propriétaire du Bien', 
        store=True, # la valeur récupérée est aussi stockée dans la base de données Important pour la recherche et le regroupement
        readonly=True # On ne peut pas modifier le propriétaire depuis le mandat
    )

    sale_order_id = fields.Many2one(
        'sale.order', 
        string='Commande de Commission', 
        readonly=True, 
        copy=False,
        tracking=True # C'est bien de suivre quand il est lié
    )

    agent_id = fields.Many2one(
        'res.users', 
        string='Agent Responsable du Mandat', 
        required=True, 
        default=lambda self: self.env.user, # Agent qui crée le mandat par défaut
        tracking=True
    )

    # --- Type de Mandat et Transaction ---
    mandate_type = fields.Selection([
        ('exclusive', 'Exclusif'),
        ('simple', 'Simple'),
        ('semi_exclusive', 'Semi-Exclusif')
    ], string='Type de Mandat', required=True, default='simple', tracking=True)
    
    transaction_type = fields.Selection(
        related='property_id.transaction_type', # Se remplit depuis la propriété
        string='Type de Transaction du Mandat', # Devrait correspondre au type de transaction de la propriété
        store=True,
        readonly=True
    )

    # --- Dates et Durée ---
    start_date = fields.Date(string='Date de Début', required=True, default=fields.Date.today, tracking=True)
    duration_months = fields.Integer(string='Durée Prévue (mois)', default=3, tracking=True) # Ex: 3 mois
    end_date = fields.Date(string='Date de Fin Calculée', compute='_compute_end_date', store=True, readonly=True, tracking=True)

    # --- Prix et Commission ---
    # Le prix demandé est celui de la propriété au moment de la création du mandat
    mandate_price = fields.Monetary(
        string='Prix de Vente/Location Demandé (lors du mandat)', 
        currency_field='currency_id',
        tracking=True
    ) 
    # On pourrait aussi utiliser un compute pour prendre le prix actuel de la propriété, 
    # mais le stocker ici fige le prix au moment du mandat.

    commission_rate = fields.Float(string='Taux de Commission (%)', default=5.0, tracking=True)
    commission_amount = fields.Monetary(
        string='Montant Commission Estimé', 
        compute='_compute_commission_amount', 
        store=True, 
        currency_field='currency_id',
        tracking=True
    )
    currency_id = fields.Many2one(
        related='property_id.currency_id', # Devise de la propriété
        string="Devise",
        store=True,
        readonly=True
    )
    
    # --- État du Mandat ---
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('sold_rented_under_mandate', 'Vendu/Loué (sous ce mandat)'),
        ('expired', 'Expiré'),
        ('terminated', 'Résilié (avant terme)'),
        ('completed_other_way', 'Terminé (bien vendu/loué autrement)')
    ], string='État du Mandat', default='draft', tracking=True, copy=False)
    
    # --- Conditions et Notes ---
    conditions = fields.Html(string='Conditions Particulières du Mandat')
    notes = fields.Text(string='Notes Internes')

    # === Méthodes Calculées (Compute) ===
    @api.depends('property_id.title', 'reference')
    def _compute_mandate_name(self):
        for mandate in self:
            name = mandate.reference or _("Nouveau Mandat")
            if mandate.property_id:
                name = f"Mandat {mandate.transaction_type or ''} - {mandate.property_id.title or ''} ({name})"
            mandate.name = name

    @api.depends('start_date', 'duration_months')
    def _compute_end_date(self):
        for record in self:
            if record.start_date and record.duration_months > 0:
                record.end_date = record.start_date + relativedelta(months=+record.duration_months)
            else:
                record.end_date = False # Ou record.start_date si durée = 0

    @api.depends('mandate_price', 'commission_rate')
    def _compute_commission_amount(self):
        for record in self:
            if record.mandate_price > 0 and record.commission_rate > 0:
                record.commission_amount = (record.mandate_price * record.commission_rate) / 100.0
            else:
                record.commission_amount = 0.0

    # === Surcharge de Create et Write ===
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('Nouveau')) == _('Nouveau'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('property.mandate.sequence') or _('Nouveau')
            # Au moment de la création, on fige le prix de la propriété
            if 'property_id' in vals and not 'mandate_price' in vals:
                prop = self.env['property.property'].browse(vals['property_id'])
                if prop.transaction_type == 'sale' or prop.transaction_type == 'both':
                    vals['mandate_price'] = prop.sale_price
                elif prop.transaction_type == 'rent':
                    vals['mandate_price'] = prop.rent_price
        return super().create(vals_list)

    # === Actions (Boutons) ===
    def action_activate(self):
        for mandate in self:
            if not mandate.property_id:
                raise UserError(_("Veuillez d'abord lier une propriété à ce mandat."))
            mandate.write({'state': 'active'})
            # Optionnel: Mettre à jour l'état de la propriété si elle était en brouillon
            if mandate.property_id.state == 'draft':
                mandate.property_id.action_make_available() 

    # Déclenche la création de la commande de commission
    def action_mark_sold_rented(self):
        self.ensure_one() # S'assurer qu'on travaille sur un seul mandat à la fois pour cette action     
        if self.state == 'sold_rented_under_mandate' and self.sale_order_id:raise UserError(_("La commission a déjà été générée pour ce mandat."))    

        self.write({'state': 'sold_rented_under_mandate'})
        self.message_post(body=_(f"Le mandat est maintenant marqué comme '{self.state}'. Préparation de la génération de la commission."))

        # Déclencher la création de la commande de commission.ici on vas retourner pour que l'utilisateur soit redirigé vers la commande
        return self.action_generate_commission_sale_order() 


    def action_generate_commission_sale_order(self): # Cette méthode est celle de la Phase 8
        self.ensure_one()
        if self.sale_order_id:
            # Rediriger vers la commande existante au lieu de lever une erreur ou permettre la création multiple
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'view_mode': 'form',
                'res_id': self.sale_order_id.id,
                'target': 'current',
                'flags': {'form': {'action_buttons': True, 'options': {'mode': 'edit'}}}
            }
       

        # On s'assure que l'état est bien celui qui permet la facturation
        if self.state != 'sold_rented_under_mandate':
            raise UserError(_("La commission ne peut être générée que pour un mandat à l'état 'Vendu/Loué (sous ce mandat)'."))
            
        if not self.owner_id:
            raise UserError(_("Le propriétaire n'est pas défini sur ce mandat."))
            
        # Utiliser la commission déjà calculée et stockée
        if self.commission_amount <= 0:
            raise UserError(_("Le montant de la commission calculé est de zéro ou négatif. Vérifiez les prix et taux sur le mandat."))
        
        product_to_invoice = False
        # Assurez-vous que property_id.transaction_type est fiable ou utilisez transaction_type sur le mandat
        transaction_type_to_use = self.transaction_type

        if transaction_type_to_use == 'sale':
            product_to_invoice = self.env.ref('gestion_agence_immobiliere.product_commission_sale', raise_if_not_found=False)
        elif transaction_type_to_use == 'rent':
            product_to_invoice = self.env.ref('gestion_agence_immobiliere.product_commission_rent', raise_if_not_found=False)
        elif transaction_type_to_use == 'both':
            # Si c'est 'both' sur le mandat, cela signifie que la propriété pouvait être vendue OU louée.
            # Maintenant, nous devons savoir si la transaction finale (celle qui a mis la propriété à 'sold' ou 'rented')
            # était une vente ou une location.
            
            # On se base sur l'état ACTUEL de la propriété liée au mandat
            if self.property_id.state == 'sold':
                 product_to_invoice = self.env.ref('gestion_agence_immobiliere.product_commission_sale', raise_if_not_found=False)
                 self.message_post(body=_("Mandat 'both' : Commission de VENTE générée car la propriété est marquée comme 'Vendu'."))
            elif self.property_id.state == 'rented':
                 product_to_invoice = self.env.ref('gestion_agence_immobiliere.product_commission_rent', raise_if_not_found=False)
                 self.message_post(body=_("Mandat 'both' : Commission de LOCATION générée car la propriété est marquée comme 'Loué'."))
            else:
                raise UserError(_("Pour un mandat de type 'Vente et Location', impossible de déterminer la commission car l'état final de la propriété ('%s') n'est ni 'Vendu' ni 'Loué'.") % self.property_id.state)

        if not product_to_invoice:
            # Cette erreur sera maintenant plus spécifique si le cas 'both' n'a pas pu être résolu
            raise UserError(_("Produit de commission non trouvé pour le type de transaction du mandat ('%s') ou l'état final de la propriété. Vérifiez data/product_data.xml et l'état de la propriété.") % transaction_type_to_use)
        

        order_line_vals = [(0, 0, {
            'product_id': product_to_invoice.id,
            'name': f"{product_to_invoice.name} - Propriété: {self.property_id.display_name or 'N/A'} (Mandat: {self.reference or 'N/A'})",
            'product_uom_qty': 1,
            'price_unit': self.commission_amount,
        })]

        sale_order_vals = {
            'partner_id': self.owner_id.id,
            'order_line': order_line_vals,
            'origin': self.reference, 
            'company_id': self.company_id.id if self.company_id else self.env.company.id,
            'note': f"Commission relative au mandat {self.reference} pour la propriété {self.property_id.display_name}."
        }
            
        so = self.env['sale.order'].create(sale_order_vals)
        self.sale_order_id = so.id
        self.message_post(body=_(f"Commande de commission <a href='#' data-oe-model='sale.order' data-oe-id='{so.id}'>{so.name}</a> créée."))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': so.id,
            'target': 'current',
        }

    def action_terminate(self):
        self.write({'state': 'terminated'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
