///** @odoo-module */
//
////import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
//import { patch } from "@web/core/utils/patch";
//
//import { OrderWidget } from "@point_of_sale/app/generic_components/order_widget/order_widget";
//
////patch(ProductScreen.prototype, {
////    //@Override
////    async _barcodeProductAction(code) {
////        await super._barcodeProductAction(...arguments);
////
////    },
////});
//patch(OrderWidget.prototype, {
//   get TotalQuantity(){
//       var totalQuantity = 0;
//       this.props.lines.forEach(line => totalQuantity += line.quantity);
//       return totalQuantity
//   }
//});