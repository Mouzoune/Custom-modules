/** @odoo-module */

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

export class WooCommListImportController extends ListController {
    setup() {
        super.setup();
    }

    async onClickGetProductsMostSold() {
    console.log('/////////////////////////////////', this)
    console.log('/////////////////////////////////', this.model)
        this.actionService.doAction({
            res_model: 'product.template',
            name: ("Produits plus vendu"),
            type: "ir.actions.act_window",
            target: "current",
            views: [[false, "tree"]],
            context: {
                getProductSortedBySalesCount: true,
            },
        })
    }


    /*
        open the wizard for importing products
    */
    async onClickWooCommProductImport() {
        return this.actionService.doAction("mt_odoo_woocommerce_connector.action_wizard_woocomm_import_product_instance", {});
    }

    /*
        open the wizard for importing sale order
    */
    async onClickWooCommSaleOrderImport() {
        return this.actionService.doAction("mt_odoo_woocommerce_connector.action_wizard_import_woocomm_sale_order", {});
    }

    /*
        open the wizard for importing customers
    */
    async onClickWooCommCustomerImport() {
        return this.actionService.doAction("mt_odoo_woocommerce_connector.action_woocomm_wizard_import_customer", {});
    }

    /*
        open the wizard for importing Category
    */
        async onClickWooCommCategoryImport() {
            return this.actionService.doAction("mt_odoo_woocommerce_connector.action_wizard_import_woocomm_product_category", {});
        }    

            /*
        open the wizard for importing Attribute
    */
        async onClickWooCommAttributeImport() {
            return this.actionService.doAction("mt_odoo_woocommerce_connector.action_wizard_import_woocomm_product_attribute", {});
        } 

    /*
        open the wizard for importing Taxes
    */
        async onClickWooCommTaxImport() {
            return this.actionService.doAction("mt_odoo_woocommerce_connector.action_wizard_import_woocomm_tax", {});
        }         
}


export const WooCommImportListView = {
    ...listView,
    Controller: WooCommListImportController,
    buttonTemplate: 'WooCommImportList.Buttons',
};

registry.category("views").add('woocomm_import_product_button', WooCommImportListView);
registry.category("views").add('woocomm_import_sale_order_button', WooCommImportListView);
registry.category("views").add('woocomm_import_customer_button', WooCommImportListView);
registry.category("views").add('woocomm_import_product_category_button', WooCommImportListView);
registry.category("views").add('woocomm_import_product_attribute_button', WooCommImportListView);
registry.category("views").add('woocomm_import_tax_button', WooCommImportListView);
