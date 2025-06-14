{
    'name': "gestion_agence_immobiliere",

    'summary': "Système de gestion complète pour agence immobilière",

    'description': """
        Module de gestion d'agence immobilière incluant :
        - Gestion des biens immobiliers
        - Planification et suivi des visites
        - Gestion des clients (propriétaires, acheteurs, locataires)
        - Gestion des mandats et contrats
        - Reporting et statistiques
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    'category': 'Real Estate',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': [
        'base', 
        'mail',
        'sale_management',
        'calendar',
        'contacts'
    ],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/product_data.xml',
        'data/mail_templates.xml',
        'views/client_views.xml',
        'views/property_views.xml',
        'views/mandate_views.xml',
        'views/visit_views.xml',
        'views/offer_views.xml',
        'views/menu_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}

