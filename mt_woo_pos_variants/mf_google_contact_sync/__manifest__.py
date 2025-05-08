{
    'name': "MF Google Contacts Sync",
    'summary': """
        Synchronize Google Contacts with Odoo.
        """,
    'description': """
        This module allows users to synchronize their Google Contacts with Odoo. It supports both importing and exporting contacts, ensuring that contact information is consistent between Google Contacts and Odoo.
    """,
    'author': "MF TECH",
    'license': 'AGPL-3',
    'website': "",
    'category': 'Base',
    'version': '0.1',
    'depends': ['base', 'contacts'],
    'external_dependencies': {
        'python': ['google-api-python-client-stubs', 'google_auth_oauthlib', 'google-auth']
    },
    'images': ['static/description/gco.png'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/google_contacts.xml',
        'wizard/google_contacts_export.xml',
        'views/res_config_settings_view_form_inherit.xml',
    ],
}
