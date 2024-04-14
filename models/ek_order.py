from odoo import models, fields, api, _, exceptions
import logging
import json
import requests
from datetime import datetime
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import ValidationError, UserError
from odoo.http import request
_logger = logging.getLogger(__name__)
from .config import *


class EkOrder(models.Model):
    _inherit = 'sale.order'


    create_by = fields.Char('Crée a partir de', default='Odoo')
    ek_file = fields.Char("Dossier ekiclik")
    ek_state = fields.Char("Statut ekiclik")
    cancel_reason = fields.Char("Motif d'annulation de dossier")

    headers = {"Content-Type": "application/json","Accept": "application/json", "Catch-Control": "no-cache"}

    @api.model
    def create(self, vals):

        # SET THE ENVIRONMENT
        utils = self.env['odoo_utils']
        domain = "https://apiadmin-alsalam-stg.wissal-group.com"

        # RECEIVE ORDER/QUOTATION FROM EK
        if 'create_by' in vals and vals['create_by'] != 'odoo':

            # SEARCH FOR THE CLIENT
            if "client" in vals:
                if vals["client"]:
                    client = vals.get('client', {})
                vals.pop('client')
                try:
                    client_id = self.env['res.partner'].search([('name', '=', client["name"])])
                    if client_id:
                        vals['partner_id'] = client_id.id
                    else:
                        # CHECK TYPE OF CLIENT IF PERSON
                        if client["is_company"] == False:
                            _logger.info(
                                '\n\n\n company\n\n\n\n--->>  %s\n\n\n\n', client['is_company'])
                            if 'type' in client and client['type'] == 'delivery':

                                # PUT THE PARENT ID BY SEARCHING WITH SOURCE
                                if 'source' in client and client['source']:
                                    # Get the bank record
                                    bank = self.env['res.partner'].search([('name', '=', client['source'])])
                                    if bank:
                                        client['parent_id'] = bank.id
                                    else:
                                        bank = self.env['res.partner'].create([{
                                            'name': client['source'],
                                            'company_type': 'company',
                                            'customer_rank': 1
                                        }])
                                        client['parent_id'] = bank.id

                                    client.pop('source')

                                # PUT THE country_id [res.country] (Many2one Relation)
                                if 'country_id' in client.keys():
                                    country = self.env['res.country'].search([('code', '=', client['country_id'])])

                                    client['country_id'] = country.id
                                # PUT THE state_id [res.country.state] (Many2one Relation)
                                if 'state_id' in client.keys():
                                    state_id = utils.affect_many_to_one(
                                        client['state_id'], 'res.country.state', 'name')
                                    if state_id:
                                        client['state_id'] = state_id
                                    else:
                                        client['state_id'] = None

                        _logger.info(
                            '\n\n\ncreating partner\n\n\n\n--->>  %s\n\n\n\n', client)
                        partner = self.env['res.partner'].create({
                            'name': client['name'],
                            'email': client['email'],
                            'type': client['type'],
                            'source': client['parent_id'],
                            'state_id': client['state_id'],
                            'country_id': client['country_id'],
                            'phone': client['phone'],
                            'is_company': client['is_company'],
                            'parent_id': client['parent_id']
                        })

                        _logger.info(
                            '\n\n\npartner created \n\n\n\n--->>  %s\n\n\n\n', client)
                        vals['partner_id'] = partner.id

                except Exception as e:
                    _logger.error("An error occurred: %s", e)
                    raise

            vals['create_by'] = "ekiclik"

            logging.warning("DATA TO CREATE======")
            logging.warning(vals)
            if 'order_line' in vals:
                order_line_values = vals.get('order_line', {})
                vals.pop('order_line')

            rec = super(EkOrder, self).create(vals)
            product = None

            if order_line_values:
                for line in order_line_values:
                    # Get the product record based on default_code
                    # Get the product record based on ref_odoo
                    if 'ref_odoo' in line:
                        product = self.env['product.product'].search([('ref_odoo', '=', line['ref_odoo'])],
                                                                     order='create_date DESC', limit=1)

                    # Ensure a single product is found
                    if product:
                        order_values = {
                            'product_id': product.id,
                            'product_uom_qty': line['qty'],
                            'name': product.name,
                            'product_uom': product.uom_id.id,
                            'state': 'sale',
                            'price_unit': product.lst_price,
                            'order_id': rec.id
                        }
                        self.env['sale.order.line'].create(order_values)

                    else:
                        new_product = self.env['product.product'].create({
                            'name': line['product_name'],
                            'ref_odoo': line['ref_odoo']
                        })

                        if new_product:
                            order_values = {
                                'product_id': new_product.id,
                                'product_uom_qty': line['qty'],
                                'name': rec.name,
                                'product_uom': new_product.uom_id.id,
                                'state': 'sale',
                                'price_unit': product.lst_price,
                                'order_id': rec.id

                            }
                            self.env['sale.order.line'].create(order_values)
            rec.action_confirm()
            return rec
        else:
            return super(EkOrder, self).create(vals)

    def write(self, vals):
        _logger.info("Writing records with values: %s", vals)

        # Receive order/quotation from EK
        if 'create_by' in vals and vals['create_by'] != 'odoo':
            try:
                # Map EK states to Odoo states
                state_mapping = {
                    "EK_ORDER_IN_PREPARATION": "Commande en préparation",
                    "EK_ORDER_IN_DELIVERY": "Livraison en cours",
                    "EK_ORDER_DELIVERED": "Client livré",
                    "EK_CLIENT_ORDER_CANCELED": "Commande annulée",
                }
                # Update ek_state if present in vals
                if 'ek_state' in vals:
                    old_state = vals['ek_state']
                    vals['ek_state'] = state_mapping.get(old_state, old_state)
                    _logger.debug("Mapped EK state '%s' to Odoo state '%s'", old_state, vals['ek_state'])

                vals['create_by'] = "ekiclik"
                self._compute_onchange_state(vals)
                return super(EkOrder, self).write(vals)

            except Exception as e:
                _logger.error("An error occurred during EkOrder write operation: %s", e)
                raise
        else:
            self._compute_onchange_state(vals)
            return super(EkOrder, self).write(vals)

    def _compute_onchange_state(self, vals):
        for record in self:
            _logger.warning("O R D E R      N A M E '%s'", record.name)

            if vals.get('ek_state') == "Client livré":
                _logger.info("Detected EK state 'Client livré'")

                picking = self.env['stock.picking'].search([('origin', '=', record.name)])
                if picking:
                    _logger.info("Found associated stock picking '%s'", picking.name)
                    picking.button_validate()
                    _logger.info("Validated associated stock picking '%s'", picking.name)
                else:
                    _logger.warning("No stock picking found for order '%s'", record.name)

                invoice_vals = {
                    'partner_id': record.partner_id.id,
                    'invoice_origin': record.name,  # Set invoice_origin value
                    'move_type': 'out_invoice',  # for customer invoice
                    'currency_id': record.currency_id.id,
                    'invoice_line_ids': [(0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.name,
                        'quantity': line.product_uom_qty,
                        'price_unit': line.price_unit,
                        'account_id': line.product_id.categ_id.property_account_income_categ_id.id,
                    }) for line in record.order_line],
                }
                if invoice_vals['invoice_line_ids']:  # Check if there are order lines before creating an invoice
                    invoice = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(
                        invoice_vals)

                    _logger.info("Invoice created with invoice_origin '%s' for order '%s'", record.name,
                                 record.name)  # Log creation with invoice_origin

                    # Write invoice_origin on the invoice
                    invoice.invoice_origin = record.name

                    invoice.action_post()
                    _logger.info("Invoice posted successfully for order '%s'", record.name)
                    for move in invoice:
                        move.message_post_with_view('mail.message_origin_link',
                                                    values={'self': move,
                                                            'origin': record.name},
                                                    subtype_id=self.env.ref('mail.mt_note').id
                                                    )
                    # Add the invoice to the Many2many field
                    try:
                        record.write({'invoice_ids': [(4, invoice.id)]})  # Update invoice_ids with new invoice
                        _logger.debug("Invoice linked to sale order '%s'", record.name)
                    except Exception as e:
                        _logger.error("Error linking invoice to sale order '%s': %s", record.name, e)
                else:
                    _logger.warning("No order lines found for order '%s'", record.name)
