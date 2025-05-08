import logging
from random import randint
from odoo import models, fields, api, exceptions

_logger = logging.getLogger(__name__)


class ProductCategory(models.Model):
    _inherit = 'product.category'


    def _get_default_color(self):
        return randint(1, 11)

    color = fields.Integer(string='Color', default=_get_default_color)
