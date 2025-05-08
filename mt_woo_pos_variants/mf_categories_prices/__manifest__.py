{
    'name': "MF. Categories Prices",
    'summary': """
        MF. Categories Prices,
        """,
    'description': """
        This module allows users to synchronize their Google Contacts with Odoo. It supports both importing and exporting contacts, ensuring that contact information is consistent between Google Contacts and Odoo.
    """,
    'author': "MF TECH",
    'license': 'AGPL-3',
    'website': "",
    'category': 'Base',
    'version': '0.1',
    'depends': ['base', 'contacts', 'stock', 'sale', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/order_line_category_price.xml',
    ],
}
