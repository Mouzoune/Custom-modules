import logging
from odoo import models, fields, api, exceptions

_logger = logging.getLogger(__name__)


class SaleOrderLineCategoryPrices(models.Model):
    _name = 'order.line.category.price'
    _description = 'Order Line Category Price'

    name = fields.Char(string='Description', required=True, copy=False)
    categ_ids = fields.Many2many('product.category', string='Catégories', required=True)
    qty = fields.Float(string='Quantité', required=True, copy=False)
    amount = fields.Float(string='Montant', required=True, copy=False)
