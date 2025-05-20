{
    'name': 'MF Dynamic Product Price',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': """View and manage price securely with customizable access controls.""",
    'description': """Provides a tree-view for price with advanced access controls.""",
    'author': 'Farid MOUZOUNE',
    'company': 'Farid MOUZOUNE',
    'maintainer': 'Farid MOUZOUNE',
    'website': "https://www.mtech.com",
    'depends': ['sale', 'sales_team', 'sale_management', 'purchase'],
    'data': [
        'views/product_pricelist_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
