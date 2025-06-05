from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta 

class PropertyVisit(models.Model):
    _name = 'property.visit'
    _description = 'Visite de Propriété Immobilière'
    _order = 'visit_date desc' # Ordre par date de visite, la plus récente en premier
    _rec_name = 'reference' 
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- Référence et Informations de Base ---
    reference = fields.Char(
        string='Référence Visite', 
        required=True, 
        copy=False, 
        readonly=True, 
        index=True, 
        default=lambda self: _('Nouveau')
    )

    name = fields.Char(string="Objet de la Visite", compute="_compute_visit_name", store=True, help="Ex: Visite APPART001 par M. Dupont")

    property_id = fields.Many2one(
        'property.property', 
        string='Propriété à Visiter', 
        required=True,
        domain="[('state', 'in', ['available', 'reserved'])]", # On ne visite que des biens disponibles ou réservés
        tracking=True
    )
    client_id = fields.Many2one(
        'res.partner', 
        string='Client Visiteur', 
        required=True, 
        domain="[('is_potential_buyer', '=', True), ('is_potential_renter', '=', True)]", # Filtrer pour clients potentiels
        tracking=True
        # Note: le domaine ci-dessus est un OU logique implicite. Pour un ET, il faudrait plusieurs tuples.
        # Pour un OU plus explicite : domain="['|', ('is_potential_buyer', '=', True), ('is_potential_renter', '=', True)]"
    )
    agent_id = fields.Many2one(
        'res.users', 
        string='Agent Accompagnateur', 
        required=True, 
        default=lambda self: self.env.user, # Agent qui crée la visite par défaut
        tracking=True
    )
    
    # --- Planification ---
    visit_date = fields.Datetime(string='Date et Heure de Visite Prévues', required=True, default=fields.Datetime.now, tracking=True)
    duration = fields.Float(string='Durée Estimée (heures)', default=0.5, tracking=True) # Ex: 0.5 pour 30 mins
    
    visit_type = fields.Selection([
        ('first', 'Première Visite'),
        ('second', 'Seconde Visite'),
        ('revisit', 'Revisite (après intérêt)'),
        ('final_check', 'Visite de Contrôle Final')
    ], string='Type de Visite', default='first', tracking=True)
    
    # --- État de la Visite ---
    state = fields.Selection([
        ('draft', 'Brouillon'), # En préparation par l'agent
        ('scheduled', 'Planifiée'), # Date et heure fixées, en attente de confirmation client/agent
        ('confirmed', 'Confirmée'), # Confirmée par toutes les parties
        ('in_progress', 'En Cours'), # La visite a lieu actuellement
        ('completed', 'Terminée'), # Visite effectuée
        ('no_show_client', 'Client Absent'), # Le client ne s'est pas présenté
        ('no_show_agent', 'Agent Absent'), # L'agent ne s'est pas présenté (rare)
        ('cancelled_client', 'Annulée par Client'),
        ('cancelled_agency', 'Annulée par Agence')
    ], string='État', default='draft', tracking=True, copy=False)
    
    # --- Feedback (après la visite) ---
    client_rating = fields.Selection([
        ('1', '⭐ (Très Négatif)'),
        ('2', '⭐⭐ (Négatif)'),
        ('3', '⭐⭐⭐ (Neutre)'),
        ('4', '⭐⭐⭐⭐ (Positif)'),
        ('5', '⭐⭐⭐⭐⭐ (Très Positif)')
    ], string='Évaluation du Client')
    client_feedback = fields.Text(string='Commentaires du Client')
    agent_notes = fields.Text(string='Notes Internes de l\'Agent')
    client_interested = fields.Boolean(string='Client Intéressé par la Propriété ?')
    
    # --- Suivi (si intéressé) ---
    follow_up_needed = fields.Boolean(string='Suivi Actif Nécessaire', compute="_compute_follow_up_needed", store=True)
    follow_up_date = fields.Date(string='Date de Prochain Suivi')
    follow_up_notes = fields.Text(string='Notes pour le Suivi')

    # --- Liaison Calendrier Odoo ---
    calendar_event_id = fields.Many2one('calendar.event', string='Événement Calendrier', readonly=True, copy=False)

    # === Méthodes Calculées (Compute) ===
    @api.depends('property_id.title', 'client_id.name', 'reference')
    def _compute_visit_name(self):
        for visit in self:
            name = visit.reference or _("Nouvelle Visite")
            if visit.property_id and visit.client_id:
                name = f"Visite {visit.property_id.title or ''} par {visit.client_id.name or ''} ({name})"
            elif visit.property_id:
                name = f"Visite {visit.property_id.title or ''} ({name})"
            visit.name = name
    
    @api.depends('client_interested', 'state')
    def _compute_follow_up_needed(self):
        for visit in self:
            if visit.state == 'completed' and visit.client_interested:
                visit.follow_up_needed = True
            else:
                visit.follow_up_needed = False # Réinitialiser si l'état change ou si plus intéressé

    # === Surcharge de Create et Write ===
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('Nouveau')) == _('Nouveau'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('property.visit.sequence') or _('Nouveau')
        visits = super().create(vals_list)
        for visit in visits: # Créer l'événement calendrier après la création de la visite
            if visit.state in ['scheduled', 'confirmed']: # Ou juste 'confirmed' si on préfère
                visit._create_calendar_event()
        return visits

    def write(self, vals):
        res = super().write(vals)
        if 'visit_date' in vals or 'duration' in vals or 'agent_id' in vals or 'client_id' in vals or 'state' in vals:
            for visit in self:
                if visit.calendar_event_id and visit.state not in ['cancelled_client', 'cancelled_agency', 'completed', 'no_show_client', 'no_show_agent']:
                    visit._update_calendar_event()
                elif not visit.calendar_event_id and visit.state in ['scheduled', 'confirmed']:
                    visit._create_calendar_event()
                elif visit.calendar_event_id and visit.state in ['cancelled_client', 'cancelled_agency']:
                    visit.calendar_event_id.action_archive() 
        return res
    
    # === Actions (Boutons) ===
    def action_schedule(self):
        self.write({'state': 'scheduled'})
        for visit in self:
            if not visit.calendar_event_id:
                visit._create_calendar_event()
            else:
                visit._update_calendar_event()

    def action_confirm(self):
        self.write({'state': 'confirmed'})
        for visit in self:
            visit._send_confirmation_email() # Placeholder pour l'email
            if not visit.calendar_event_id: # S'assurer que l'événement existe
                visit._create_calendar_event()
            else:
                visit._update_calendar_event() # Mettre à jour l'événement si besoin
            visit.calendar_event_id.active = True # S'assurer qu'il est actif

    def action_start_visit(self):
        self.write({'state': 'in_progress'})
        for visit in self:
            if visit.calendar_event_id:
                 visit.calendar_event_id.active = True # Juste pour s'assurer

    def action_complete(self):
        self.write({'state': 'completed'})
        for visit in self:
            if visit.client_interested and not visit.follow_up_date: # Suggérer une date de suivi
                visit.follow_up_date = fields.Date.today() + timedelta(days=3)
            if visit.calendar_event_id: # Peut-être marquer comme terminé dans le calendrier aussi
                visit.calendar_event_id.action_archive() # Archiver l'événement passé

    def action_no_show_client(self):
        self.write({'state': 'no_show_client'})
        if self.calendar_event_id: self.calendar_event_id.action_archive()

    def action_cancel_client(self):
        self.write({'state': 'cancelled_client'})
        if self.calendar_event_id: self.calendar_event_id.action_archive()

    def action_cancel_agency(self):
        self.write({'state': 'cancelled_agency'})
        if self.calendar_event_id: self.calendar_event_id.action_archive() 

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

        if self.calendar_event_id: self.calendar_event_id.unlink() # Supprimer l'événement si on revient au brouillon

    # === Méthodes Privées pour Logique Spécifique ===
    def _prepare_calendar_event_values(self):
        self.ensure_one()
        attendees = []
        if self.client_id:
            attendees.append(self.client_id.id)
        #ajouter l'agent comme participant s'il n'est pas l'organisateur
        if self.agent_id.partner_id and self.agent_id.partner_id != self.env.user.partner_id:
            attendees.append(self.agent_id.partner_id.id)

        return {
            'name': self.name or f"Visite {self.property_id.name}",
            'start': self.visit_date,
            'stop': self.visit_date + timedelta(hours=self.duration) if self.visit_date and self.duration else self.visit_date,
            'duration': self.duration,
            'description': f"Visite de la propriété : {self.property_id.title}\nClient : {self.client_id.name}\nAgent : {self.agent_id.name}\nRéférence Visite : {self.reference}",
            'partner_ids': [(6, 0, attendees)], # (6,0,IDs) remplace les participants existants
            'user_id': self.agent_id.id, # L'agent est l'organisateur
            'res_id': self.id, # Lier l'événement à cet enregistrement de visite
            'res_model': self._name, # Lier à ce modèle
        }

    def _create_calendar_event(self):
        for visit in self:
            if not visit.calendar_event_id and visit.visit_date: # Créer seulement s'il n'existe pas et qu'une date est définie
                vals = visit._prepare_calendar_event_values()
                event = self.env['calendar.event'].create(vals)
                visit.calendar_event_id = event.id

    def _update_calendar_event(self):
        for visit in self:
            if visit.calendar_event_id and visit.visit_date:
                vals = visit._prepare_calendar_event_values()
                visit.calendar_event_id.write(vals)
    
    def _send_confirmation_email(self):
        self.ensure_one()
        # Placeholder - La vraie logique d'envoi d'email sera implémentée plus tard
        # avec des mail.template si nécessaire.
        # Pour l'instant, on peut juste poster un message dans le chatter.
        if self.property_id and self.client_id:
            self.message_post(body=_(f"Email de confirmation (simulé) envoyé à {self.client_id.name} pour la visite de {self.property_id.title} le {self.visit_date}."))
        return True

    def action_view_calendar_event(self):
        self.ensure_one()
        if not self.calendar_event_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'view_mode': 'form',
            'res_id': self.calendar_event_id.id,
            'target': 'current', # ou 'new' pour une nouvelle fenêtre/onglet
        }