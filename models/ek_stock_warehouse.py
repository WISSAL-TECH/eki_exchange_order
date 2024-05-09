import json
import re

import requests
from odoo import models, fields, api, exceptions
from odoo.http import request
import logging
from _datetime import datetime
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import UserError
from odoo import SUPERUSER_ID, _, api, fields, models


_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    create_by = fields.Char(string="Créé à partir de", readonly=True)
    ek_file = fields.Char("Dossier ekiclik", compute="_compute_ek_file")
    can_validate = fields.Selection([
        ('validating', 'Dossier en cours de validation'),
        ('validated', 'Dossier validé')],
        'Status de validation',
        default=lambda self: 'validated' if self.env.company.id == 3 else 'validating')

    order_or_purchase = fields.Boolean(string="order", default = False, compute= '_compute_order_or_purchase')



    # set the url and headers
    headers = {"Content-Type": "application/json", "Accept": "application/json", "Catch-Control": "no-cache"}
    url_stock = '/api/odoo/stocks'
    url_commande = '/api/odoo/order'


    def _compute_ek_file(self):
        """function to compute the ek_file value"""

        order = self.env['sale.order'].search([('name', '=', self.origin)])
        self.ek_file = order.ek_file

    def _compute_order_or_purchase(self):
        """function to compute the oder_or_purchase value"""

        purchase = self.env['purchase.order'].search([('name', '=', self.origin)])
        if purchase:
            self.order_or_purchase = False
        else:
            self.order_or_purchase = True

    def button_validate(self):
        # Clean-up the context key at validation to avoid forcing the creation of immediate
        # transfers.
        _logger.info('\n\n\nbutton validate stock.picking\n\n\n\n--->>  \n\n\n\n' )

        ctx = dict(self.env.context)
        ctx.pop('default_immediate_transfer', None)
        self = self.with_context(ctx)

        # Sanity checks.
        pickings_without_moves = self.browse()
        pickings_without_quantities = self.browse()
        pickings_without_lots = self.browse()
        products_without_lots = self.env['product.product']
        for picking in self:
            if not picking.move_lines and not picking.move_line_ids:
                pickings_without_moves |= picking

            picking.message_subscribe([self.env.user.partner_id.id])
            picking_type = picking.picking_type_id
            precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            no_quantities_done = all(float_is_zero(move_line.qty_done, precision_digits=precision_digits) for move_line in picking.move_line_ids.filtered(lambda m: m.state not in ('done', 'cancel')))
            no_reserved_quantities = all(float_is_zero(move_line.product_qty, precision_rounding=move_line.product_uom_id.rounding) for move_line in picking.move_line_ids)
            if no_reserved_quantities and no_quantities_done:
                pickings_without_quantities |= picking

            if picking_type.use_create_lots or picking_type.use_existing_lots:
                lines_to_check = picking.move_line_ids
                if not no_quantities_done:
                    lines_to_check = lines_to_check.filtered(lambda line: float_compare(line.qty_done, 0, precision_rounding=line.product_uom_id.rounding))
                for line in lines_to_check:
                    product = line.product_id
                    if product and product.tracking != 'none':
                        if not line.lot_name and not line.lot_id:
                            pickings_without_lots |= picking
                            products_without_lots |= product

        if not self._should_show_transfers():
            if pickings_without_moves:
                raise UserError(_('Please add some items to move.'))
            if pickings_without_quantities:
                raise UserError(self._get_without_quantities_error_message())
            if pickings_without_lots:
                raise UserError(_('You need to supply a Lot/Serial number for products %s.') % ', '.join(products_without_lots.mapped('display_name')))
        else:
            message = ""
            if pickings_without_moves:
                message += _('Transfers %s: Please add some items to move.') % ', '.join(pickings_without_moves.mapped('name'))
            if pickings_without_quantities:
                message += _('\n\nTransfers %s: You cannot validate these transfers if no quantities are reserved nor done. To force these transfers, switch in edit more and encode the done quantities.') % ', '.join(pickings_without_quantities.mapped('name'))
            if pickings_without_lots:
                message += _('\n\nTransfers %s: You need to supply a Lot/Serial number for products %s.') % (', '.join(pickings_without_lots.mapped('name')), ', '.join(products_without_lots.mapped('display_name')))
            if message:
                raise UserError(message.lstrip())

        # Run the pre-validation wizards. Processing a pre-validation wizard should work on the
        # moves and/or the context and never call `_action_done`.
        if not self.env.context.get('button_validate_picking_ids'):
            self = self.with_context(button_validate_picking_ids=self.ids)
        res = self._pre_action_done_hook()
        if res is not True:
            return res

        # Call `_action_done`.
        if self.env.context.get('picking_ids_not_to_backorder'):
            pickings_not_to_backorder = self.browse(self.env.context['picking_ids_not_to_backorder'])
            pickings_to_backorder = self - pickings_not_to_backorder
        else:
            pickings_not_to_backorder = self.env['stock.picking']
            pickings_to_backorder = self
        pickings_not_to_backorder.with_context(cancel_backorder=True)._action_done()
        pickings_to_backorder.with_context(cancel_backorder=False)._action_done()

        if self.user_has_groups('stock.group_reception_report') \
                and self.user_has_groups('stock.group_auto_reception_report') \
                and self.filtered(lambda p: p.picking_type_id.code != 'outgoing'):
            lines = self.move_lines.filtered(lambda m: m.product_id.type == 'product' and m.state != 'cancel' and m.quantity_done and not m.move_dest_ids)
            if lines:
                # don't show reception report if all already assigned/nothing to assign
                wh_location_ids = self.env['stock.location']._search([('id', 'child_of', self.picking_type_id.warehouse_id.view_location_id.ids), ('usage', '!=', 'supplier')])
                if self.env['stock.move'].search([
                        ('state', 'in', ['confirmed', 'partially_available', 'waiting', 'assigned']),
                        ('product_qty', '>', 0),
                        ('location_id', 'in', wh_location_ids),
                        ('move_orig_ids', '=', False),
                        ('picking_id', 'not in', self.ids),
                        ('product_id', 'in', lines.product_id.ids)], limit=1):
                    action = self.action_view_reception_report()
                    action['context'] = {'default_picking_ids': self.ids}
                    return action
        domain = ""
        domain_cpa = ""
        config_settings = self.env['res.config.settings'].search([], order='id desc', limit=1)
        if config_settings:
            domain = config_settings.domain
            domain_cpa = config_settings.domain_cpa
        _logger.info('\n\n\nDOMAIN\n\n\n\n--->>  %s\n\n\n\n', domain)
        _logger.info('\n\n\nDOMAIN\n\n\n\n--->>  %s\n\n\n\n', domain_cpa)

        num_dossier = self.env['sale.order'].search([('name', '=', self.origin)]).ek_file

        commande = {
            "requestNumber": num_dossier,
            "state": "EK_ORDER_DELIVERED"
        }
        data =[]
        for line in self.move_line_ids_without_package:
            numeric_value = ""
            _logger.info(
                '\n\n\n liiiiiiiiiiiiine \n\n\n\n--->> \n\n\n\n')
            if self.location_dest_id.company_id.name == "Centrale des Achats" or self.location_id.company_id.name == "Centrale des Achats":
                if line.product_id.tax_string:
                    pattern = r'(\d[\d\s,.]+)'

                    # Use the findall function to extract all matches
                    matches = re.findall(pattern, line.product_id.tax_string)


                    # Join the matches into a single string (if there are multiple matches)
                    numeric_value = ''.join(matches)

                    # Replace commas with dots (if necessary)
                    numeric_value = numeric_value.replace(',', '.')

                    # Remove non-breaking space characters
                    numeric_value = numeric_value.replace('\xa0', '')

                else:
                    numeric_value = line.product_id.list_price
                if self.picking_type_id == "outgoing":
                    product_stock = self.env['stock.quant'].search([
                        ('location_id', '=', self.location_id.id),
                        ('product_id', '=', line.product_id.id)])
                else:
                    product_stock = self.env['stock.quant'].search([
                        ('location_id', '=', self.location_dest_id.id),
                        ('product_id', '=', line.product_id.id)])

                dataa = {
                    "pos": "EKIWH",
                    "configuration_ref_odoo": line.product_id.ref_odoo,
                    "realQuantity": product_stock.quantity if product_stock else line.qty_done,
                    "price": line.product_id.list_price}
                data.append(dataa)


                _logger.info(
                        '\n\n\n sending stock.picking to ek \n\n\n\n--->>  %s\n\n\n\n', data)
                response1 = requests.put(domain + self.url_stock, data=json.dumps(data),
                                                 headers=self.headers)
                _logger.info(
                            '\n\n\n response \n\n\n\n--->>  %s\n\n\n\n', response1)
                _logger.info(
                        '\n\n\n sending state to ek \n\n\n\n--->>  %s\n\n\n\n', commande)
                logging.warning(str(domain) + str(self.url_commande) + '/' + str(self.ek_file))
                response = requests.put(str(domain) + str(self.url_commande) +'/'+ str(self.ek_file), headers=self.headers)
                _logger.info(
                            '\n\n\n response \n\n\n\n--->>  %s\n\n\n\n', response)
                _logger.info(
                    '\n\n\n sending stock.picking to ek cpa \n\n\n\n--->>  %s\n\n\n\n', data)
                response1_cpa = requests.put(domain_cpa + self.url_stock, data=json.dumps(data),
                                             headers=self.headers)
                _logger.info(
                    '\n\n\n response \n\n\n\n--->>  %s\n\n\n\n', response1)
                _logger.info(
                    '\n\n\n sending state to ek \n\n\n\n--->>  %s\n\n\n\n', commande)
                logging.warning(str(domain_cpa) + str(self.url_commande) + '/' + str(self.ek_file))
                response_cpa = requests.put(str(domain_cpa) + str(self.url_commande) + '/' + str(self.ek_file),
                                            headers=self.headers)
                _logger.info(
                    '\n\n\n response \n\n\n\n--->>  %s\n\n\n\n', response)
                return response1, response, response1_cpa, response_cpa

            else:
                if line.product_id.tax_string:
                    pattern = r'(\d[\d\s,.]+)'

                    # Use the findall function to extract all matches
                    matches = re.findall(pattern, line.product_id.tax_string)


                    # Join the matches into a single string (if there are multiple matches)
                    numeric_value = ''.join(matches)

                    # Replace commas with dots (if necessary)
                    numeric_value = numeric_value.replace(',', '.')

                    # Remove non-breaking space characters
                    numeric_value = numeric_value.replace('\xa0', '')

                else:
                    numeric_value = line.product_id.list_price

                if self.picking_type_id == "outgoing":
                    product_stock = self.env['stock.quant'].search([
                        ('location_id', '=', self.location_id.id),
                        ('product_id', '=', line.product_id.id)])
                    company = self.location_id

                else:
                    product_stock = self.env['stock.quant'].search([
                        ('location_id', '=', self.location_dest_id.id),
                        ('product_id', '=', line.product_id.id)])
                    company = self.location_dest_id
                dataa = {
                    "pos": company.company_id.codification,
                    "configuration_ref_odoo": line.product_id.ref_odoo,
                    "realQuantity": product_stock.quantity if product_stock else line.qty_done,
                    "price": line.product_id.list_price}
                data.append(dataa)


                _logger.info(
                        '\n\n\n sending stock.picking to pdv \n\n\n\n--->>  %s\n\n\n\n', data)
                response1 = requests.put(domain + self.url_stock, data=json.dumps(data),
                                                 headers=self.headers)
                _logger.info(
                            '\n\n\n response \n\n\n\n--->>  %s\n\n\n\n', response1)
                _logger.info(
                        '\n\n\n sending state to ek \n\n\n\n--->>  %s\n\n\n\n', commande)
                logging.warning(str(domain) + str(self.url_commande) + '/' + str(self.ek_file))
                response = requests.put(str(domain) + str(self.url_commande) +'/'+ str(self.ek_file), headers=self.headers)
                _logger.info(
                            '\n\n\n response \n\n\n\n--->>  %s\n\n\n\n', response)
                _logger.info(
                        '\n\n\n sending stock.picking to pdv cpa \n\n\n\n--->>  %s\n\n\n\n', data)
                response1_cpa = requests.put(domain_cpa + self.url_stock, data=json.dumps(data),
                                                 headers=self.headers)
                _logger.info(
                            '\n\n\n response \n\n\n\n--->>  %s\n\n\n\n', response1)
                _logger.info(
                        '\n\n\n sending state to ek \n\n\n\n--->>  %s\n\n\n\n', commande)
                logging.warning(str(domain_cpa) + str(self.url_commande) + '/' + str(self.ek_file))
                response_cpa = requests.put(str(domain_cpa) + str(self.url_commande) +'/'+ str(self.ek_file), headers=self.headers)
                _logger.info(
                            '\n\n\n response \n\n\n\n--->>  %s\n\n\n\n', response)
                return response1_cpa, response_cpa


    def write(self, vals):

        # SET THE ENVIREMENT
        utils = self.env['odoo_utils']

        # CHECK IF UPDATE MADE BY ekiclik--------------------------------------------------------------------------------------
        if 'create_by' in vals and vals['create_by'] != "odoo":
            if 'can_validate' in vals and vals['can_validate'] == 'ok':
                vals['can_validate'] = 'validated'

            vals['create_by'] = 'ekiclik'

            response = super(StockPicking, self).write(vals)


            _logger.info(
                '\n\n\nresponse value is :  \n\n\n\n\n--->  %s\n\n\n\n\n\n\n', response)

            if response:
                _logger.info(
                    '\n\n\nstock picking updated from ekiclik \n\n\n\n\n--->  %s\n\n\n\n\n\n\n', vals)
            return response



