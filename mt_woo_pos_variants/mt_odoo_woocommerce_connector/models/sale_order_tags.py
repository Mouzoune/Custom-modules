from random import randint
from odoo import api, models, fields


class SaleOrderTags(models.Model):
    _name = 'sale.order.tags.woocommerce'
    _description = 'Tags for sale order woocommerce state'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char('Nom')
    color = fields.Integer('Color', default = _get_default_color)
