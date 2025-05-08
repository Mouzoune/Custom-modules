import logging
from odoo.exceptions import UserError

from odoo import api, fields, models
_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    show_cost_price = fields.Boolean(string='Show Cost Price', default=False)

    @api.onchange('show_cost_price')
    def onchange_show_cost_price(self):
        if self.show_cost_price:
            self.env.ref('hide_cost_price.groups_view_cost_price').users = [(4, self.id)]
        else:
            self.env.ref('hide_cost_price.groups_view_cost_price').users = [(3, self.id)]
