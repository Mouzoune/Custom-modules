import logging
from email.policy import default

from woocommerce import API
from odoo import models, api, fields, _

_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'


    commercial_partner_id = fields.Many2one(
        'res.partner', string='Commercial Entity',
        compute='_compute_commercial_partner', store=True,
        recursive=True, index=True)

    @api.depends('is_company', 'parent_id.commercial_partner_id')
    def _compute_commercial_partner(self):
        pass
        #for partner in self:
        #    if partner.is_company or not partner.parent_id:
        #        partner.commercial_partner_id = partner
        #    else:
        #        partner.commercial_partner_id = partner.parent_id.commercial_partner_id


class ResCompany(models.Model):
    _inherit = 'res.company'

    must_create_orders = fields.Char(string='Orders to create')
    must_create_orders_json = fields.Json(string='Orders to create', default={})
    must_create_products = fields.Char(string='Products to create')
    must_create_update_products = fields.Json(string='Products to create', default={})
    woocomm_instance_id = fields.Many2one('woocommerce.instance', string='WooCommerce Instance')

    def init_wc_api(self, wooc_instance):
        # wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
#        wooc_instance = self.woocomm_instance_id
        if wooc_instance.is_authenticated:
            try:
                woo_api = API(
                    url=wooc_instance.shop_url,
                    consumer_key=wooc_instance.wooc_consumer_key,
                    consumer_secret=wooc_instance.wooc_consumer_secret,
                    wp_api=True,
                    version=wooc_instance.wooc_api_version
                )
                req_data = woo_api.get("")

                return woo_api
            except Exception as error:
                raise UserError(_("Please check your connection and try again"))
        else:
            raise UserError(
                _("Connection Instance needs to authenticate first. \n Please try after authenticating connection!!!"))
