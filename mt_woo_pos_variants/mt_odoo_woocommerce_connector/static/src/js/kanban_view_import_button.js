/** @odoo-module */

import { registry } from "@web/core/registry";
import { kanbanView } from '@web/views/kanban/kanban_view';
import { KanbanController } from "@web/views/kanban/kanban_controller";
export class WooCommKanbanImportController extends KanbanController {
    setup() {
        super.setup();
    }

    /*
        open the wizard for importing products
    */
    async onClickWooCommProductImport() {
        return this.actionService.doAction("mt_odoo_woocommerce_connector.action_wizard_woocomm_import_product_instance", {});
    }

    /*
        open the wizard for importing customers
    */
    async onClickWooCommCustomerImport() {
        return this.actionService.doAction("mt_odoo_woocommerce_connector.action_woocomm_wizard_import_customer", {});
    }

}


export const WooCommImportKanbanView = {
    ...kanbanView,
    Controller: WooCommKanbanImportController,
    buttonTemplate: 'WooCommImportKanban.Buttons',
};

registry.category("views").add('woocomm_import_product_k_button', WooCommImportKanbanView);
registry.category("views").add('woocomm_import_customer_k_button', WooCommImportKanbanView);
