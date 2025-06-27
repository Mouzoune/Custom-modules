import json
import logging
from email.policy import default

from odoo import http, _, fields
from odoo.http import request
from odoo.addons.website.controllers.form import WebsiteForm
from odoo.addons.survey.controllers.main import Survey
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment
_logger = logging.getLogger(__name__)
from odoo.addons.portal.controllers.portal import CustomerPortal
from datetime import date, datetime, timedelta
from odoo.addons.website.controllers.form import WebsiteForm
from werkzeug.exceptions import BadRequest
from odoo.exceptions import AccessDenied, ValidationError, UserError
from odoo.tools.image import image_guess_size_from_field_name
from woocommerce import API


class Main(http.Controller):


    @http.route('/webhook/wp/<string:wc_action>/<int:wc_id>', type='http', auth='public', methods=['POST', 'GET'], csrf=False)
    def webhook_order(self, wc_action, wc_id, **kwargs):
        request.env['product.template'].with_context(dont_send_data_to_wooc_from_write_method=True).sudo().create_product(2, 1)
        return {'status': 'success', 'message': 'Webhook received'}

    def import_product(self, wooc_instance, is_force_update=False):
        for p_item in self.get_all_products(wooc_instance, limit=20):
            # Check if the product already exists
            product = request.env['product.template'].sudo().search(
                [('wooc_id', '=', p_item['id']), ('woocomm_instance_id', '=', wooc_instance.id)], limit=1)

            if product and not is_force_update:
                _logger.info(f"Product {p_item['id']} already exists. Skipping update.")
                continue

            # Create or update the product
            if product:
                _logger.info(f"Updating Product {p_item['id']}")
                product.sudo().write(self._prepare_product_vals(p_item, wooc_instance))
            else:
                _logger.info(f"Creating Product {p_item['id']}")
                product = request.env['product.template'].sudo().create(self._prepare_product_vals(p_item, wooc_instance))

            # Handle variations
            if p_item.get('variations'):
                self._create_or_update_variations(product, p_item['variations'], wooc_instance)

    def _prepare_product_vals(self, p_item, wooc_instance):
        _logger.error(f'p_item =  {p_item}')
        data =  {
            'wooc_id': p_item['id'],
            'name': p_item.get('name', ''),
            'woocomm_instance_id': wooc_instance.id,
            'type': 'product',
            'woocomm_product_status': p_item.get('status', 'draft'),
            'woocomm_regular_price': float(p_item.get('regular_price', 0.0)) if p_item.get('regular_price', 0.0) else 0.0,
            'woocomm_sale_price': float(p_item.get('sale_price', 0.0)) if p_item.get('sale_price', 0.0) else 0.0,
            'description': p_item.get('description', ''),
            'is_exported': True,
            'is_product_active': p_item.get('status') == 'publish',
        }
        _logger.error(f'data =  {data}')

        return data

    def _create_or_update_variations(self, product, variations, wooc_instance):
        for variation in variations:
            variant = request.env['product.product'].sudo().search(
                [('woocomm_variant_id', '=', variation), ('product_tmpl_id', '=', product.id), ('woocomm_instance_id', '=', wooc_instance.id)], limit=1)

            variation_data = self.get_all_products_variants(product.wooc_id, wooc_instance, limit=20)
            for var_data in variation_data:
                variant_vals = {
                    'woocomm_variant_id': var_data['id'],
                    'woocomm_regular_price': float(p_item.get('regular_price', 0.0)) if p_item.get('regular_price', 0.0) else 0.0,
                    'woocomm_sale_price': float(p_item.get('sale_price', 0.0)) if p_item.get('sale_price', 0.0) else 0.0,
                    'woocomm_stock_quantity': var_data.get('stock_quantity', 0),
                    'woocomm_stock_status': var_data.get('stock_status', 'instock'),
                    'is_exported': True,
                }

                if variant:
                    _logger.info(f"Updating Variant {var_data['id']}")
                    variant.sudo().write(variant_vals)
                else:
                    _logger.info(f"Creating Variant {var_data['id']}")
                    variant_vals.update({'product_tmpl_id': product.id})
                    request.env['product.product'].sudo().create(variant_vals)

    def init_wc_api(self, wooc_instance):
        wooc_instance = request.env['woocommerce.instance'].sudo().search([], limit=1, order='id asc')

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


    @http.route('/wp-json/wc/v3/webhooks', type='json', auth='public', methods=['POST'], csrf=False)
    def webhook_product_updated(self, **kwargs):
        # try:
        # Parse the JSON payload
        product_data = json.loads(request.httprequest.data)
        source_path = request.httprequest.headers.get('X-Wc-Webhook-Source').replace('https://', '').replace('/', '')
        # if product_data.get('variations', False) or (not product_data.get('variations', False) and product_data.get('parent_id', 0) == 0):
        if product_data.get('variations', False):
            wooc_instance = request.env['woocommerce.instance'].sudo().search([]).filtered(lambda x: source_path == x.shop_url.replace('https://', ''))
            _logger.error(f"Create/Update product   Instance: {wooc_instance.display_name}   ID = {product_data.get('id', False)}")
            if not wooc_instance:
                wooc_instance = request.env['woocommerce.instance'].sudo().search([], limit=1, order='id asc')
            product_id = product_data['id']
            params, url = {}, f"products" + f'?include={f"{product_id}"}'
            woo_api = API(
                url=wooc_instance.shop_url,
                consumer_key=wooc_instance.wooc_consumer_key,
                consumer_secret=wooc_instance.wooc_consumer_secret,
                wp_api=True,
                version=wooc_instance.wooc_api_version
            )
            product = woo_api.get(url, params=params)
            product_data_item = product.json()

            # admin_env = request.env(user=1)
            _logger.error('///////////////////. webhooks start ')
            request.env['product.template'].with_user(request.env.ref("base.user_admin")).sudo().with_context(dont_send_data_to_wooc_from_write_method=True).create_product(product_data_item[0], wooc_instance)
            _logger.error('///////////////////. webhooks end ')
        return {'status': 'success', 'message': 'Product processed successfully'}


    @http.route('/wp-json/wc/v3/webhooks/orders', type='json', auth='public', methods=['POST'], csrf=False)
    def webhook_order_created_updated(self, **kwargs):
        order_data = json.loads(request.httprequest.data)
        source_path = request.httprequest.headers.get('X-Wc-Webhook-Source').replace('https://', '').replace('/', '')
        _logger.error(f'source_path = {source_path}')
        wooc_instance = request.env['woocommerce.instance'].sudo().search([]).filtered(lambda x: source_path == x.shop_url.replace('https://', ''))
        _logger.error(f"Create/Update order  Instance: {wooc_instance.display_name}   ID = {order_data.get('id', False)}")
        if not wooc_instance:
            wooc_instance = request.env['woocommerce.instance'].sudo().search([], limit=1, order='id asc')
        order_id = order_data['id']
        params, url = {}, f"orders" + f'?include={f"{order_id}"}'
        woo_api = API(
            url=wooc_instance.shop_url,
            consumer_key=wooc_instance.wooc_consumer_key,
            consumer_secret=wooc_instance.wooc_consumer_secret,
            wp_api=True,
            version=wooc_instance.wooc_api_version
        )
        order = woo_api.get(url, params=params)
        order_data_item = order.json()
        request.env['sale.order'].sudo().with_context(dont_send_data_to_wooc_from_write_method=True).create_sale_order(order_data_item[0], wooc_instance)
        return {'status': 'success', 'message': 'Order processed successfully'}

    # @http.route('/wp-json/wc/v3/webhooks', type='json', auth='public', methods=['POST', 'GET'], csrf=False)
    # def webhook_product_updated(self, **kwargs):
    #     _logger.error(f'kwargs == {kwargs}')
    #     payload = json.loads(request.httprequest.data)
    #     _logger.error(payload)

    #     return {'status': 'success', 'message': 'Webhook received'}


    @http.route('/webhook/wp/product/<string:wc_action>/<int:wc_id>', type='json', auth='public', methods=['POST'], csrf=False)
    def webhook_product(self, wc_action, wc_id, **kwargs):
        payload = json.loads(request.httprequest.data)
        _logger.error(payload)
        _logger.error(f'////////////// Products:  wc action ({wc_action}) & wc id ({wc_id}) ////////////////')
        existed_must_create_update_products = request.env.company.sudo().must_create_update_products
        must_create_update_products_added = {**existed_must_create_update_products} if existed_must_create_update_products else {}
        must_create_update_products_added[f"{wc_action}_{wc_id}"] = int(wc_id)
        _logger.error(f'Products ==>  {list(request.env.company.sudo().must_create_update_products.values())}')
        return {'status': 'success', 'message': 'Webhook received'}


    @http.route(['/web/image',
        '/web/image/<string:xmlid>',
        '/web/image/<string:xmlid>/<string:filename>',
        '/web/image/<string:xmlid>/<int:width>x<int:height>',
        '/web/image/<string:xmlid>/<int:width>x<int:height>/<string:filename>',
        '/web/image/<string:model>/<int:id>/<string:field>',
        '/web/image/<string:model>/<int:id>/<string:field>/<string:filename>',
        '/web/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>',
        '/web/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>/<string:filename>',
        '/web/image/<int:id>',
        '/web/image/<int:id>/<string:filename>',
        '/web/image/<int:id>/<int:width>x<int:height>',
        '/web/image/<int:id>/<int:width>x<int:height>/<string:filename>',
        '/web/image/<int:id>-<string:unique>',
        '/web/image/<int:id>-<string:unique>/<string:filename>',
        '/web/image/<int:id>-<string:unique>/<int:width>x<int:height>',
        '/web/image/<int:id>-<string:unique>/<int:width>x<int:height>/<string:filename>'], type='http', auth="public")
    # pylint: disable=redefined-builtin,invalid-name
    def content_image(self, xmlid=None, model='ir.attachment', id=None, field='raw',
                      filename_field='name', filename=None, mimetype=None, unique=False,
                      download=False, width=0, height=0, crop=False, access_token=None,
                      nocache=False):
        try:
            record = request.env['ir.binary'].sudo()._find_record(xmlid, model, id and int(id), access_token)
            stream = request.env['ir.binary'].sudo()._get_image_stream_from(
                record, field, filename=filename, filename_field=filename_field,
                mimetype=mimetype, width=int(width), height=int(height), crop=crop,
            )

        except UserError as exc:
            if download:
                raise request.not_found() from exc
            # Use the ratio of the requested field_name instead of "raw"
            if (int(width), int(height)) == (0, 0):
                width, height = image_guess_size_from_field_name(field)
            record = request.env.ref('web.image_placeholder').sudo()
            stream = request.env['ir.binary']._get_image_stream_from(
                record, 'raw', width=int(width), height=int(height), crop=crop,
            )

        send_file_kwargs = {'as_attachment': download}
        if unique:
            send_file_kwargs['immutable'] = True
            send_file_kwargs['max_age'] = http.STATIC_CACHE_LONG
        if nocache:
            send_file_kwargs['max_age'] = None

        res = stream.get_response(**send_file_kwargs)
        res.headers['Content-Security-Policy'] = "default-src 'none'"
        return res
