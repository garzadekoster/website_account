# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#
#    Copyright (c) 2013 Noviat nv/sa (www.noviat.com). All rights reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import orm
import xlwt
from openerp.addons.website_account.report_xls import report_xls
from openerp.addons.website_account.utils import rowcol_to_cell
from openerp.tools.translate import _
# import logging
# _logger = logging.getLogger(__name__)

class trail_balance_xls(orm.TransientModel):
    _name = 'trail.balance.xls'

    def xls_export(self, cr, uid, data, context=None):
        #return self.check_report(cr, uid, ids, context=context)
        fiscalyear_id = self.pool.get('account.account').get_fiscal_year(cr, uid, data['form']['chart_account_id'])
        data['form']['fiscalyear_id'] = fiscalyear_id
        data['form']['used_context']['fiscalyear'] = fiscalyear_id
        ret = {'type': 'ir.actions.report.xml', 'datas': {'model': 'ir.ui.menu', 'ids': [], 'form': {'chart_account_id': data['form']['chart_account_id'], 'period_to': False, 'fiscalyear_id': data['form']['fiscalyear_id'], 'periods': [], 'date_from': data['form']['date_from'], 'used_context': {'lang': 'en_US', 'state': data['form']['target_move'], 'chart_account_id': data['form']['chart_account_id'], 'fiscalyear': data['form']['fiscalyear_id']}, 'period_from': False, 'date_to': data['form']['date_to'], 'filter': data['form']['filter'], 'target_move': data['form']['target_move'], 'display_account':data['form']['display_account'], 'target_move': data['form']['target_move']}, 'title':data['form']['title'], 'company': data['form']['company'], 'filter_str':data['form']['filter_str']}, 'report_name': 'account.account_report_trail_balance_xls'}
        
        return ret
        
class account_trail_balance_xls(report_xls):
    column_sizes = []

    def generate_xls_report(self, _p, _xs, data, objects, wb):
        formula_dict_debit = {}
        formula_dict_credit = {}
        formula_dict = {}
        formula_dict_sum_debit = {}
        formula_dict_sum_credit = {}
        ws = wb.add_sheet('Trail Balance')
        ws.panes_frozen = True
        ws.remove_splits = True
        ws.portrait = 0  # Landscape
        ws.fit_width_to_pages = 1
        row_pos = 0
        self.column_sizes = []
	records = self.pool.get('account.account').get_lines_trail_balance(self.cr, self.uid, data)
	max_level = self.pool.get('account.account').max_level_tb + 4  # Index starts with 0 but levels starts with 1, -3 to avoid 3 empty Rows
        # set print header/footer
        ws.header_str = data['title']
        ws.footer_str = self.xls_footers['standard']

        # cf. account_report_trial_balance.mako
        initial_balance_text = {'initial_balance': _('Computed'),
                                'opening_balance': _('Opening Entries'),
                                False: _('No')}

        # Title
        cell_style = xlwt.easyxf(_xs['xls_title'])
        
        cell_format = _xs['bold'] + _xs['borders_all']
        cell_style = xlwt.easyxf(cell_format)
        cell_style_center = xlwt.easyxf(cell_format + _xs['center'])
        c_specs = [
            ('company', max_level+1, 0, 'text', data['company'], None, cell_style_center),
        ]
        row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
        row_pos = self.xls_write_row(
            ws, row_pos, row_data, row_style=cell_style)
        c_specs = [
            ('title', max_level+1, 0, 'text', data['title'], None, cell_style_center),
        ]
        row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
        row_pos = self.xls_write_row(
            ws, row_pos, row_data, row_style=cell_style)
        c_specs = [
            ('filter_str', max_level+1, 0, 'text', data['filter_str'], None, cell_style_center),
        ]
        row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
        row_pos = self.xls_write_row(
            ws, row_pos, row_data, row_style=cell_style)

        # write empty row to define column sizes
	
        self.column_sizes.extend([5] * (max_level-4))
        self.column_sizes.append(45)
        self.column_sizes.append(20)
        self.column_sizes.append(20)
        self.column_sizes.append(20)
        self.column_sizes.append(20)
        c_sizes = self.column_sizes
        c_specs = [('empty%s' % i, 1, c_sizes[i], 'text', None)
                   for i in range(0, len(c_sizes))]
        row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
        row_pos = self.xls_write_row(
            ws, row_pos, row_data, set_column_size=True,set_row_height=False)


        # Column Header Row
        cell_format = _xs['bold'] + _xs['fill_blue'] + \
            _xs['borders_all'] + _xs['wrap'] + _xs['top']
        cell_style = xlwt.easyxf(cell_format)
        cell_style_right = xlwt.easyxf(cell_format + _xs['right'])
        cell_style_center = xlwt.easyxf(cell_format + _xs['center'])
        c_specs = [
            ('account', max_level-3, 0, 'text', _('Account'), None, cell_style_center),
        ]        
        c_specs += [('debit', 1, 0, 'text',
                         _('Debit'), None, cell_style_right),
                         ('credit', 1, 0, 'text',
                         _('Credit'), None, cell_style_right),
                         ('balance', 2, 0, 'text',
                         _('Balance'), None, cell_style_center)]        
        row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
        row_pos = self.xls_write_row(
            ws, row_pos, row_data, row_style=cell_style)
        ws.set_horz_split_pos(row_pos)
        c_specs = [
            ('account', max_level-3, 0, 'text', _(''), None, cell_style_center),
        ]        
        c_specs += [('debit', 1, 0, 'text',
                         _(''), None, cell_style_right),
                         ('credit', 1, 0, 'text',
                         _(''), None, cell_style_right),
                         ('sum_debit', 1, 0, 'text',
                         _('Debit'), None, cell_style_right),
                         ('sum_credit', 1, 0, 'text',
                         _('Credit'), None, cell_style_right)]        
        row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
        row_pos = self.xls_write_row(
            ws, row_pos, row_data, row_style=cell_style)
        ws.set_horz_split_pos(row_pos)

        last_child_consol_ids = []

        # cell styles for account data
        view_cell_format = _xs['bold'] + _xs['borders_all']
        view_cell_style = xlwt.easyxf(view_cell_format)
        view_cell_style_center = xlwt.easyxf(view_cell_format + _xs['center'])
        view_cell_style_decimal = xlwt.easyxf(
            view_cell_format + _xs['right'],
            num_format_str=report_xls.decimal_format)
        view_cell_style_pct = xlwt.easyxf(
            view_cell_format + _xs['center'], num_format_str='0')
        regular_cell_format = _xs['borders_all']
        regular_cell_style = xlwt.easyxf(regular_cell_format)
        regular_cell_style_center = xlwt.easyxf(
            regular_cell_format + _xs['center'])
        regular_cell_style_decimal = xlwt.easyxf(
            regular_cell_format + _xs['right'],
            num_format_str=report_xls.decimal_format)
        regular_cell_style_pct = xlwt.easyxf(
            regular_cell_format + _xs['center'], num_format_str='0')
        tall_style = xlwt.easyxf('font:height 720;' + view_cell_format)    	
	
        view_cell_style.font.colour_index = xlwt.Style.colour_map['dark_blue_ega']           
        view_cell_style_center.font.colour_index = xlwt.Style.colour_map['dark_blue_ega']           
        view_cell_style_decimal.font.colour_index = xlwt.Style.colour_map['dark_blue_ega']   
              
        for current_account in records:

            if current_account['type'] == 'view':
                cell_style = view_cell_style
                cell_style_center = view_cell_style_center
                cell_style_decimal = view_cell_style_decimal
                cell_style_pct = view_cell_style_pct
            else:
                cell_style = regular_cell_style
                cell_style_center = regular_cell_style_center
                cell_style_decimal = regular_cell_style_decimal
                cell_style_pct = regular_cell_style_pct
		
	    debit = current_account['debit']
	    credit = current_account['credit']
	    balance = current_account['balance']
	    
	    """-3 to avoid 3 empty Rows"""
            c_specs = [
                ('account', 1, 0, 'text', current_account['name'], None, None, None, current_account['level'], max_level-3),
            ]              
            if current_account['has_childs']:
                c_specs +=[
                ('debit', 1, 0, 'text', None, None, None),
                ('credit', 1, 0, 'text', None, None, None),
                ('sum_debit', 1, 0, 'text', None, None, None),
                ('sum_credit', 1, 0, 'text', None, None, None),
                ]
            else:
                if current_account['name'][:5] != 'Total': # or current_account['name'][:5] == 'Total' """ Give this condition also if any issue in Formulas or to avoid Formulas"""
                    c_specs +=[
                        ('debit', 1, 0, 'number', debit, None, cell_style_decimal),
                        ('credit', 1, 0, 'number', credit, None, cell_style_decimal),
                        ('sum_debit', 1, 0, 'number', balance>=0 and balance or 0.00, None, cell_style_decimal),
                        ('sum_credit', 1, 0, 'number', balance<=0 and abs(balance) or 0.00, None, cell_style_decimal),
                    ]
                elif current_account['name'][:5] == 'Total':
                    formula_dict_debit[current_account['id']-0.5] += ',5)'
                    formula_dict_credit[current_account['id']-0.5] += ',5)'
                    formula_dict_sum_debit[current_account['id']-0.5] += ',5)'
                    formula_dict_sum_credit[current_account['id']-0.5] += ',5)'
                    c_specs +=[
                        ('debit', 1, 0, 'number', None, formula_dict_debit[current_account['id']-0.5], cell_style_decimal),
                        ('credit', 1, 0, 'number', None, formula_dict_credit[current_account['id']-0.5], cell_style_decimal),
                        ('sum_debit', 1, 0, 'number', None, formula_dict_sum_debit[current_account['id']-0.5], cell_style_decimal),
                        ('sum_credit', 1, 0, 'number', None, formula_dict_sum_credit[current_account['id']-0.5], cell_style_decimal),
                    ]
                    
                    
            t_cell_debit = rowcol_to_cell(row_pos, max_level-3)
            t_cell_credit = rowcol_to_cell(row_pos, max_level-2)        
            t_cell_sum_debit = rowcol_to_cell(row_pos, max_level-1)
            t_cell_sum_credit = rowcol_to_cell(row_pos, max_level)
            if formula_dict_debit.has_key(current_account['parent_id']):
                formula_dict_debit[current_account['parent_id']] += ' + ' + t_cell_debit
            else:
                formula_dict_debit[current_account['parent_id']] = 'Round(' + t_cell_debit
                
            if formula_dict_credit.has_key(current_account['parent_id']):
                formula_dict_credit[current_account['parent_id']] += ' + ' + t_cell_credit
            else:
                formula_dict_credit[current_account['parent_id']] = 'Round(' + t_cell_credit
                
            if formula_dict_sum_debit.has_key(current_account['parent_id']):
                formula_dict_sum_debit[current_account['parent_id']] += ' + ' + t_cell_sum_debit
            else:
                formula_dict_sum_debit[current_account['parent_id']] = 'Round(' + t_cell_sum_debit
                
            if formula_dict_sum_credit.has_key(current_account['parent_id']):
                formula_dict_sum_credit[current_account['parent_id']] += ' + ' + t_cell_sum_credit
            else:
                formula_dict_sum_credit[current_account['parent_id']] = 'Round(' + t_cell_sum_credit
                
            
            row_data = self.xls_row_template(c_specs, [x[0] for x in c_specs])
            if row_data[0][2][4][:5]=='Total':
                row_pos = self.xls_write_row(
                ws, row_pos, row_data, row_style=cell_style, set_row_height=True)
            else:    
                row_pos = self.xls_write_row(
                ws, row_pos, row_data, row_style=cell_style)

account_trail_balance_xls('report.account.account_report_trail_balance_xls',
                  'account.account')
