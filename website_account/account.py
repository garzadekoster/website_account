# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from datetime import timedelta,date
from operator import itemgetter
import time
import copy

import openerp
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.osv import fields, osv, expression
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round

import openerp.addons.decimal_precision as dp

_logger = logging.getLogger(__name__)

class account_account(osv.osv):
    _inherit = "account.account"  
    max_level = 0
    max_level_bs = 0
    max_level_tb = 0
    max_level_cfs = 5
    final_results = False
    final_results_bs = False
    final_results_tb = False
    final_results_cfs = False
    title_pl = False
    title_tb = False
    title_bs = False
    chart_account_name_bs = False
    title_cfs = False
    filter_str_tb = False
    company_tb = False
    filter_str_cfs = False
    company_cfs = False
    _columns = {
        'cashflow_act':fields.selection([('operating','Operating'),('financing','Financing'),('investing','Investing')], 'Cashflow Activity'),
    }
    
    def get_childs(self,line,lines):
        childs = [d for d in lines if d['parent_id'] == line['id']]
        return childs
        
    def get_parents(self,cr, uid,lines, enable_filter=False,comparison_context=False, context=None):
        account_obj = self.pool.get('account.account')
        account_ids = []
        parents = []
        signs = {}
        for line in lines:
            prents = [d for d in lines if d['id'] == line['parent_id']]
            if not prents:
                if line['parent_id'] and line['type']!='report':
                    account_ids.append(line['parent_id'])
                    if line.has_key('sign'):
                        signs[line['parent_id']] = line['sign']
                account_ids = list(set(account_ids))
        
        for account in account_obj.browse(cr, uid, account_ids, context):
            #if there are accounts to display, we add them to the lines with a level equals to their level in
            #the COA + 1 (to avoid having them with a too low level that would conflicts with the level of data
            #financial reports for Assets, liabilities...)
            if account.code == '2':
                continue
            flag = False
            vals = {
                        'name': account.code + ' ' + account.name,
                        'balance':  account.balance != 0 and account.balance * (signs.has_key(account.id) and signs[account.id] or 1) or account.balance * (signs.has_key(account.id) and signs[account.id] or 1),
                        'type': 'account',
                        'level': min(account.level + 1,6) or 6, #account.level + 1
                        'account_type': account.type,
                        'parent_id':account.parent_id.id,
                        'id':account.id,
                        'flg':False,
                        'parent_name':account.parent_id.code + ' ' + account.parent_id.name,
                        'childs':[],
                        'user_type':account.user_type.name,
                        'parent_user_type':account.parent_id.user_type.name,
                        'has_childs':False
            }
            if enable_filter:
                vals['balance_cmp'] = account_obj.browse(cr, uid, account.id, context=comparison_context).balance * (signs.has_key(account.id) and signs[account.id] or 1) or 0.0
                vals['cur_change'] = vals['balance'] - vals['balance_cmp']
                if vals['balance'] == 0:
                    if vals['balance_cmp'] == 0:
                        vals['per_change'] = 0
                    else:
                        vals['per_change'] = (vals['balance_cmp']>0 and -1 or 1) * 100
                else:
                    if vals['balance_cmp'] == 0:
                        vals['per_change'] = (vals['balance']>0 and 1 or -1) * 100
                    else:
                        vals['per_change'] = ((vals['balance']-vals['balance_cmp'])/abs(vals['balance_cmp'])) * 100
                
            parents.append(vals)
        return parents
        
    def get_user_company(self, cr, uid, data, context=None):    
        user = self.pool.get('res.users').browse(cr, uid, uid)
        return {'id':user.company_id.id, 'name':user.company_id.name}
        
    def get_company_chart_account(self, cr, uid, context=None):    
        user = self.pool.get('res.users').browse(cr, uid, uid)
        charts = self.pool.get('account.account').search(cr, uid, [('parent_id','=',False), ('company_id','=',user.company_id.id)])
        if not charts:
            return False
        else:
            return charts[0]  
        
    def get_user_chart_accounts(self, cr, uid, data, context=None):    
        comps=[]  
        ret = []
        user = self.pool.get('res.users').browse(cr, uid, uid)
        for company in user.company_ids:
            comps.append(company.id)
        charts = self.pool.get('account.account').search(cr, uid, [('parent_id','=',False), ('company_id','in',comps)])
        if not charts:
            return False
        else:
            for dt in self.pool.get('account.account').browse(cr, uid, charts):
                select = False
                if user.company_id.id == dt.company_id.id:
                    select=True
                ret.append({'id':dt.id, 'name':dt.name, 'select':select, 'code':dt.code}) 
            return ret
    def get_fiscal_year(self, cr, uid, chart_id, from_dt=False, to_dt=False, context=None):
        chart = self.pool.get('account.account').browse(cr, uid, chart_id)
        company_id = chart.company_id.id
        today = time.strftime('%Y-%m-%d') 
        if from_dt and to_dt:            
            fiscals = self.pool.get('account.fiscalyear').search(cr, uid, [('company_id','=',company_id), ('date_start','<=',from_dt), ('date_stop','>=',to_dt)])
        else:
            fiscals = self.pool.get('account.fiscalyear').search(cr, uid, [('company_id','=',company_id), ('date_start','<=',today), ('date_stop','>=',today)])
        if not fiscals:
            return False
        else:    
            return fiscals[0]
        
    def get_start_year(self, cr, uid, chart_id, to_dt=False,context=None):
        chart = self.pool.get('account.account').browse(cr, uid, chart_id)
        company_id = chart.company_id.id
        today = time.strftime('%Y-%m-%d')
        if not to_dt:
            fiscals = self.pool.get('account.fiscalyear').search(cr, uid, [('company_id','=',company_id), ('date_start','<=',today), ('date_stop','>=',today)])
            fiscal_obj  = self.pool.get('account.fiscalyear').browse(cr, uid, fiscals[0])
        else:
            fiscals = self.pool.get('account.fiscalyear').search(cr, uid, [('company_id','=',company_id), ('date_start','<=',to_dt), ('date_stop','>=',to_dt)])
            fiscal_obj  = self.pool.get('account.fiscalyear').browse(cr, uid, fiscals[0])            
        if not fiscals:
            return False
        else:    
            return fiscal_obj.date_start
            
    def print_report_pdf(self, cr, uid, data, context=None):
        data['form']['account_report_id'] = data['form']['account_report_id'][0]
        datas = data['form']
        self.title_pl = datas['title']
        fiscalyear_id = self.get_fiscal_year(cr, uid, data['form']['chart_account_id'], from_dt=data['form']['date_from'], to_dt=data['form']['date_to'])
        data['form']['fiscalyear_id'] = fiscalyear_id
        data['form']['used_context']['fiscalyear'] = fiscalyear_id
        ids = self.pool.get('accounting.report').create(cr, uid, datas, context=data['form']['used_context'])
        ids = [ids]
        res = self.pool.get('accounting.report').check_report(cr, uid, ids)
        return res
        
        
    def get_lines_report(self, cr, uid, data, context=None):
        #print '################################', data['form'].has_key('from_load'), data
        
        if data['form'].has_key('from_load') and data['form']['from_load']:
            self.final_results = False
        elif self.final_results:
            return self.final_results
        #data['form']['chart_account_id'] = self.get_company_chart_account(cr, uid)        
        fiscalyear_id = self.get_fiscal_year(cr, uid, data['form']['chart_account_id'], data['form']['date_from'], data['form']['date_to'])
        if fiscalyear_id:
            data['form']['fiscalyear_id'] = fiscalyear_id
            data['form']['used_context']['fiscalyear'] = fiscalyear_id
        else:
            raise osv.except_osv(_('Error!'),_('Fiscal year for the Selected Date Range is not Defind.'))    
        if data['form']['enable_filter']:  
            date_from_cmp = (datetime.strptime(data['form']['date_from_cmp'], '%Y-%m-%d')).date() + relativedelta(years=-1)
            date_to_cmp = (datetime.strptime(data['form']['date_to_cmp'], '%Y-%m-%d')).date() + relativedelta(years=-1)
            data['form']['date_from_cmp'] = date_from_cmp.strftime('%Y-%m-%d')
            data['form']['date_to_cmp'] = date_to_cmp.strftime('%Y-%m-%d')
            data['form']['comparison_context']['date_from'] = date_from_cmp.strftime('%Y-%m-%d')
            data['form']['comparison_context']['date_to'] = date_to_cmp.strftime('%Y-%m-%d')
            fiscalyear_id_cmp = self.get_fiscal_year(cr, uid, data['form']['chart_account_id'], data['form']['date_from_cmp'], data['form']['date_to_cmp'])
            if fiscalyear_id_cmp:
                data['form']['fiscalyear_id_cmp'] = fiscalyear_id_cmp
                data['form']['comparison_context']['fiscalyear'] = fiscalyear_id_cmp
            else:
                raise osv.except_osv(_('Error!'),_('Fiscal year for the Selected Date Range of Comparison is not Defind.')) 
        lines = []
        account_obj = self.pool.get('account.account')
        currency_obj = self.pool.get('res.currency')
        ids2 = self.pool.get('account.financial.report')._get_children_by_order(cr, uid, [data['form']['account_report_id'][0]], context=data['form']['used_context'])
        ids2 = sorted(ids2)
        #print 'yyyyyy', data['form']['used_context']
        for report in self.pool.get('account.financial.report').browse(cr, uid, ids2, context=data['form']['used_context']):
            vals = {
                'name': report.name,
                'balance': report.balance * report.sign or 0.0,
                'type': 'report',
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'account_type': report.type =='sum' and 'view' or False, #used to underline the financial report balances
                'parent_id':report.parent_id.id,
                'id':report.id,
                'flg':False,
                'parent_name':report.parent_id.name,
                'childs':[],
                'user_type':False,
                'parent_user_type':False,
                'has_childs':False,
                'sign':report.sign,
            }
            if report.name =='Profit and Loss':
                print 'ggggggg', vals
            level = bool(report.style_overwrite) and report.style_overwrite or report.level
            if level and level>self.max_level:
                self.max_level = level
            if data['form']['debit_credit']:
                vals['debit'] = report.debit
                vals['credit'] = report.credit
            if data['form']['enable_filter']:
                vals['balance_cmp'] = self.pool.get('account.financial.report').browse(cr, uid, report.id, context=data['form']['comparison_context']).balance * report.sign or 0.0
                vals['cur_change'] = vals['balance'] - vals['balance_cmp']
                if vals['balance'] == 0:
                    if vals['balance_cmp'] == 0:
                        vals['per_change'] = 0
                    else:
                        vals['per_change'] = (vals['balance_cmp']>0 and -1 or 1) * 100
                else:
                    if vals['balance_cmp'] == 0:
                        vals['per_change'] = (vals['balance']>0 and 1 or -1) * 100
                    else:
                        vals['per_change'] = ((vals['balance']-vals['balance_cmp'])/abs(vals['balance_cmp'])) * 100
            lines.append(vals)
            account_ids = []
            if report.display_detail == 'no_detail':
                #the rest of the loop is used to display the details of the financial report, so it's not needed here.
                continue
            if report.type == 'accounts' and report.account_ids:
                account_ids = account_obj._get_children_and_consol(cr, uid, [x.id for x in report.account_ids])
            elif report.type == 'account_type' and report.account_type_ids:
                account_ids = account_obj.search(cr, uid, [('user_type','in', [x.id for x in report.account_type_ids])])
            if account_ids:
                for account in account_obj.browse(cr, uid, account_ids, context=data['form']['used_context']):
                    #if there are accounts to display, we add them to the lines with a level equals to their level in
                    #the COA + 1 (to avoid having them with a too low level that would conflicts with the level of data
                    #financial reports for Assets, liabilities...)
                    if account.type == '2':
                        continue
                    flag = False
                    vals = {
                        'name': account.code + ' ' + account.name,
                        'balance':  account.balance != 0 and account.balance * report.sign or account.balance,
                        'type': 'account',
                        'level': report.display_detail == 'detail_with_hierarchy' and min(account.level + 1,6) or 6, #account.level + 1
                        'account_type': account.type,
                        'parent_id':account.parent_id.id,
                        'id':account.id,
                        'flg':False,
                        'parent_name':account.parent_id.code + ' ' + account.parent_id.name,
                        'childs':[],
                        'user_type':account.user_type.name,
                        'parent_user_type':account.parent_id.user_type.name,
                        'has_childs':False,
                        'sign':report.sign,
                    }
                    chld_level = report.display_detail == 'detail_with_hierarchy' and min(account.level + 1,6) or 6
                    if chld_level and chld_level>self.max_level:
                        self.max_level = chld_level

                    if data['form']['debit_credit']:
                        vals['debit'] = account.debit
                        vals['credit'] = account.credit
                    if not currency_obj.is_zero(cr, uid, account.company_id.currency_id, vals['balance']):
                        flag = True
                    if data['form']['enable_filter']:                        
                        vals['balance_cmp'] = account_obj.browse(cr, uid, account.id, context=data['form']['comparison_context']).balance * report.sign or 0.0
                        vals['cur_change'] = vals['balance'] - vals['balance_cmp']
                        if vals['balance'] == 0:
                            if vals['balance_cmp'] == 0:
                                vals['per_change'] = 0
                            else:
                                vals['per_change'] = (vals['balance_cmp']>0 and -1 or 1) * 100
                        else:
                            if vals['balance_cmp'] == 0:
                                vals['per_change'] = (vals['balance']>0 and 1 or -1) * 100
                            else:
                                vals['per_change'] = ((vals['balance']-vals['balance_cmp'])/abs(vals['balance_cmp'])) * 100
                                
                        if not currency_obj.is_zero(cr, uid, account.company_id.currency_id, vals['balance_cmp']):
                            flag = True
                    if flag:
                        lines.append(vals)            
        values = []                
        #for line in lines:
        #    #if 'profit and loss' in line['parent_name'].lower():
        #    #if 'income' in line['name'].lower():
        #    line['flg'] = True
        #    #print '111111111111111111111111111111',line
        #    childs = self.get_childs(line,lines)
        #    line['childs'] = childs   
        #values=[d for d in lines if d['level'] <=3]
        '''
        income_index,income_rec =  next((index,d) for (index, d) in enumerate(lines) if d["name"].lower() == "income")
        total_income_rec = copy.deepcopy(income_rec)
        income_rec['has_childs'] = True
        total_income_rec['name'] = 'Total '+total_income_rec['name']
        total_income_rec['id'] = -total_income_rec['id']
        lines.insert(income_index+1,total_income_rec)
        income_id = income_rec['id']      
        expense_index,expense_rec =  next((index,d) for (index, d) in enumerate(lines) if d["name"].lower() == "expense")
        total_expense_rec = copy.deepcopy(expense_rec)
        expense_rec['has_childs'] = True
        total_expense_rec['name'] = 'Total '+total_expense_rec['name']
        total_expense_rec['id'] = -total_expense_rec['id']
        lines.insert(expense_index+1,total_expense_rec)
        expense_id = expense_rec['id']
        '''
        totals_dict = {}
        if data['form']['enable_filter']:
            parents = self.get_parents(cr, uid, lines, data['form']['enable_filter'], data['form']['comparison_context'], context=data['form']['used_context'])
        else:
            parents = self.get_parents(cr, uid, lines, context=data['form']['used_context'])    
        parents = sorted(parents, key=lambda k: k['id']) 
        if parents:
            for parent in parents:
                prec = {}
                try:
                    pind,prec = next((index,d) for (index, d) in enumerate(lines) if d["parent_id"] == parent['id'])
                except StopIteration:
                    pass
                  
                if prec:
                    brec = {}
                    try:
                        bind,brec = next((index,d) for (index, d) in enumerate(lines) if d["id"] == prec['parent_id'])
                    except StopIteration:
                        pass 
                    if not brec:     
                        lines.insert(pind,copy.deepcopy(parent))
         
        for idx,line in enumerate(lines):
            #par = filter(lambda val: val['id'] == line['parent_id'], lines)
            #if not par and line['type']!='report':
            #    if line['user_type'].lower().strip() == 'income':
            #        line['parent_id'] = income_id
            #    elif line['user_type'].lower().strip() == 'expense': 
            #        line['parent_id'] = expense_id
            chld = filter(lambda val: val['parent_id'] == line['id'], lines)
            if chld:                
                totals_dict[idx] = copy.deepcopy(line)
                line['has_childs'] = True
                totals_dict[idx]['name'] = 'Total '+line['name']
                totals_dict[idx]['id'] = totals_dict[idx]['id']+0.5
                
        loop = 1        
        #for key,val in totals_dict.iteritems():
        #    lines.insert(key+loop,val)
        #    loop+=1
            
        finals = []   
        newlines = copy.deepcopy(lines)    
        for idx,line in enumerate(lines):
            flg = False
            rec = {}
            try:
                index,rec = next((index,d) for (index, d) in enumerate(finals) if d["id"] == line['parent_id'])
            except StopIteration:
                pass
            if rec:
                dt = {}
                try:
                    ind,dt =  next((index,d) for (index, d) in enumerate(finals) if d["name"] == 'Total ' + line['parent_name'])
                except StopIteration:
                    pass    
                temp = False
                if dt:
                    finals.insert(ind,copy.deepcopy(line))
                    if line['has_childs']:
                        tot = copy.deepcopy(line)
                        tot['name'] = 'Total '+tot['name']
                        tot['id'] = tot['id']+0.5
                        tot['has_childs'] = False
                        finals.insert(ind+1,tot)
                else:
                    finals.insert(index+1,copy.deepcopy(line))
                    if line['has_childs']:
                        tot = copy.deepcopy(line)
                        tot['name'] = 'Total '+tot['name']
                        tot['id'] = tot['id']+0.5
                        tot['has_childs'] = False
                        finals.insert(index+2,tot)
            else:
                finals.append(copy.deepcopy(line))  
                if line['has_childs']:
                    tot = copy.deepcopy(line)
                    tot['name'] = 'Total '+tot['name']
                    tot['id'] = tot['id']+0.5
                    tot['has_childs'] = False
                    finals.append(tot)
        dt = {}
        chart_account_name = False        
        chart_account = self.pool.get('account.account').browse(cr, uid, data['form']['chart_account_id'])
        chart_account_name = chart_account.code + ' ' + chart_account.name
        equityindex = False
        equityrec = False
        liabindex = False
        liabrec = False
        expindex = False
        exprec = False
        directindex = False
        directrec = False
        try:
            liabindex,liabrec = next((index,d) for (index, d) in enumerate(finals) if d["name"] == 'Total 4 INCOME')
        except StopIteration:
            pass
        total_income = 0.00
        if liabrec:
            total_income = liabrec['balance']   
        try:
            equityindex,equityrec = next((index,d) for (index, d) in enumerate(finals) if d["name"] == "Total 51 COST OF GOODS SOLD")
        except StopIteration:
            pass
        total_sold = 0.00
        if equityrec:
            total_sold = equityrec['balance'] 
        try:
            expindex,exprec = next((index,d) for (index, d) in enumerate(finals) if d["name"] == "Total 6 EXPENSES")
        except StopIteration:
            pass
        total_exp = 0.00
        if exprec:
            total_exp = exprec['balance']     
        try:
            directindex,directrec = next((index,d) for (index, d) in enumerate(finals) if d["name"] == "Total 5 DIRECT COST")
        except StopIteration:
            pass    
            
        chld = filter(lambda val: val['level']==0, lines)       
        
        if directrec:
            net1  = copy.deepcopy(directrec)
            net1['name'] = 'Gross Profit'
            net1['type'] = 'not report'
            net1['has_childs'] = False
            net1['level'] = -1
            net1['balance'] = abs(total_income) - abs(total_sold)
            net1['parent_name'] = False
            net1['parent_user_type'] = False
            net1['id'] = 1
            net1['user_type'] = False
            finals.insert(directindex+1,net1)
         
        #chld = filter(lambda val: val['parent_name']==chart_account_name, lines)         
        if chld:
            net  = copy.deepcopy(chld[0])
            net['name'] = 'Net Income'
            net['type'] = 'not report'
            net['has_childs'] = False
            net['balance'] = (abs(total_income) - abs(total_sold)) - abs(total_exp)
            net['level'] = -1
            finals.append(net)
            
       
        self.final_results = finals
        return finals 
        
        
    def print_report_pdf_bs(self, cr, uid, data, context=None):
        data['form']['account_report_id'] = data['form']['account_report_id'][0]
        datas = data['form']
        self.title_bs = datas['title']
        self.chart_account_name_bs = datas['chart_account_name']
        fiscalyear_id = self.get_fiscal_year(cr, uid, data['form']['chart_account_id'], from_dt=data['form']['date_from'], to_dt=data['form']['date_to'])
        data['form']['fiscalyear_id'] = fiscalyear_id
        data['form']['used_context']['fiscalyear'] = fiscalyear_id
        ids = self.pool.get('accounting.report').create(cr, uid, datas, context=data['form']['used_context'])
        ids = [ids]
        res = self.pool.get('accounting.report').check_report(cr, uid, ids)
        return res
        
        data['form'].update(self.pool.get('accounting.report').read(cr, uid, ids, ['date_from_cmp',  'debit_credit', 'date_to_cmp',  'fiscalyear_id_cmp', 'period_from_cmp', 'period_to_cmp',  'filter_cmp', 'account_report_id', 'enable_filter', 'label_filter','target_move'], context=context)[0])
        
        return self.pool['report'].get_action(cr, uid, [], 'account.report_financial', data=data, context=context)
        
    def get_lines_balance_sheet(self, cr, uid, data, context=None):
        
        if data['form'].has_key('from_load') and data['form']['from_load']:
            self.final_results_bs = False
        elif self.final_results_bs:
            return self.final_results_bs
        #data['form']['chart_account_id'] = self.get_company_chart_account(cr, uid) 
        to_dt = (datetime.strptime(data['form']['date_to'], '%Y-%m-%d')).strftime('%Y-%m-%d')  
        start_year = self.get_start_year(cr, uid, data['form']['chart_account_id'], to_dt)
        data['form']['date_from'] = start_year
        data['form']['used_context']['date_from'] = start_year
        data['form']['date_to'] = to_dt
        data['form']['used_context']['date_to'] = to_dt
        from_dt = start_year #(datetime.strptime(start_year, '%m-%d-%Y')).strftime('%Y-%m-%d')
             
        fiscalyear_id = self.get_fiscal_year(cr, uid, data['form']['chart_account_id'],from_dt, to_dt)
        if fiscalyear_id:
            data['form']['fiscalyear_id'] = fiscalyear_id
            data['form']['used_context']['fiscalyear'] = fiscalyear_id
        else:
            raise osv.except_osv(_('Error!'),_('Fiscal year for the Selected Date Range is not Defind.')) 
        if data['form']['enable_filter']:  
            date_from_cmp = (datetime.strptime(data['form']['date_from_cmp'], '%Y-%m-%d')).date() + relativedelta(years=-1)
            date_to_cmp = (datetime.strptime(data['form']['date_to_cmp'], '%Y-%m-%d')).date() + relativedelta(years=-1)
            data['form']['date_from_cmp'] = date_from_cmp.strftime('%Y-%m-%d')
            data['form']['date_to_cmp'] = date_to_cmp.strftime('%Y-%m-%d')
            data['form']['comparison_context']['date_from'] = date_from_cmp.strftime('%Y-%m-%d')
            data['form']['comparison_context']['date_to'] = date_to_cmp.strftime('%Y-%m-%d')
            date_to_cmp = data['form']['date_to_cmp']
            start_year_cmp = self.get_start_year(cr, uid, data['form']['chart_account_id'], date_to_cmp)
            data['form']['date_from_cmp'] = start_year_cmp
            data['form']['comparison_context']['date_from_cmp'] = start_year_cmp
            date_from_cmp = start_year_cmp #(datetime.strptime(start_year, '%m-%d-%Y')).strftime('%Y-%m-%d')
            fiscalyear_id_cmp = self.get_fiscal_year(cr, uid, data['form']['chart_account_id'], date_from_cmp, date_to_cmp)
            if fiscalyear_id_cmp:
                data['form']['fiscalyear_id_cmp'] = fiscalyear_id_cmp
                data['form']['comparison_context']['fiscalyear'] = fiscalyear_id_cmp
            else:
                raise osv.except_osv(_('Error!'),_('Fiscal year for the Selected Date Range of Comparison is not Defind.')) 
        
        lines = []
        account_obj = self.pool.get('account.account')
        currency_obj = self.pool.get('res.currency')
        ids2 = self.pool.get('account.financial.report')._get_children_by_order(cr, uid, [data['form']['account_report_id'][0]], context=data['form']['used_context'])       
        ids2 = sorted(ids2)
        for report in self.pool.get('account.financial.report').browse(cr, uid, ids2, context=data['form']['used_context']):
            vals = {
                'name': report.name,
                'balance': report.balance * report.sign or 0.0,
                'type': 'report',
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'account_type': report.type =='sum' and 'view' or False, #used to underline the financial report balances
                'parent_id':report.parent_id.id,
                'id':report.id,
                'flg':False,
                'parent_name':report.parent_id.name,
                'childs':[],
                'user_type':False,
                'parent_user_type':False,
                'has_childs':False,
                'sign':report.sign,
            }
            level = bool(report.style_overwrite) and report.style_overwrite or report.level
            if level and level>self.max_level_bs:
                self.max_level_bs = level
            if data['form']['debit_credit']:
                vals['debit'] = report.debit
                vals['credit'] = report.credit
            if data['form']['enable_filter']:
                vals['balance_cmp'] = self.pool.get('account.financial.report').browse(cr, uid, report.id, context=data['form']['comparison_context']).balance * report.sign or 0.0
                vals['cur_change'] = vals['balance'] - vals['balance_cmp']
                if vals['balance'] == 0:
                    if vals['balance_cmp'] == 0:
                        vals['per_change'] = 0
                    else:
                        vals['per_change'] = (vals['balance_cmp']>0 and -1 or 1) * 100
                else:
                    if vals['balance_cmp'] == 0:
                        vals['per_change'] = (vals['balance']>0 and 1 or -1) * 100
                    else:
                        vals['per_change'] = ((vals['balance']-vals['balance_cmp'])/abs(vals['balance_cmp'])) * 100                
            lines.append(vals)
            account_ids = []
            if report.display_detail == 'no_detail':
                #the rest of the loop is used to display the details of the financial report, so it's not needed here.
                continue
            if report.type == 'accounts' and report.account_ids:
                account_ids = account_obj._get_children_and_consol(cr, uid, [x.id for x in report.account_ids])
            elif report.type == 'account_type' and report.account_type_ids:
                account_ids = account_obj.search(cr, uid, [('user_type','in', [x.id for x in report.account_type_ids])])
            if account_ids:
                #account_ids = sorted(account_ids)
                for account in account_obj.browse(cr, uid, account_ids, context=data['form']['used_context']):
                    #if there are accounts to display, we add them to the lines with a level equals to their level in
                    #the COA + 1 (to avoid having them with a too low level that would conflicts with the level of data
                    #financial reports for Assets, liabilities...)
                    if account.type == '2':
                        continue
                    flag = False
                    vals = {
                        'name': account.code + ' ' + account.name,
                        'balance':  account.balance != 0 and account.balance * report.sign or account.balance,
                        'type': 'account',
                        'level': report.display_detail == 'detail_with_hierarchy' and account.level + 1 or 6, #account.level + 1
                        'account_type': account.type,
                        'parent_id':account.parent_id.id,
                        'id':account.id,
                        'flg':False,
                        'parent_name':account.parent_id.code + ' ' + account.parent_id.name,
                        'childs':[],
                        'user_type':account.user_type.name,
                        'parent_user_type':account.parent_id.user_type.name,
                        'has_childs':False,
                        'sign':report.sign,
                    }
                    chld_level = report.display_detail == 'detail_with_hierarchy' and account.level + 1 or 6
                    if chld_level and chld_level>self.max_level_bs:
                        self.max_level_bs = chld_level

                    if data['form']['debit_credit']:
                        vals['debit'] = account.debit
                        vals['credit'] = account.credit
                    if not currency_obj.is_zero(cr, uid, account.company_id.currency_id, vals['balance']):
                        flag = True
                    if data['form']['enable_filter']:                        
                        vals['balance_cmp'] = account_obj.browse(cr, uid, account.id, context=data['form']['comparison_context']).balance * report.sign or 0.0
                        vals['cur_change'] = vals['balance'] - vals['balance_cmp']
                        if vals['balance'] == 0:
                            if vals['balance_cmp'] == 0:
                                vals['per_change'] = 0
                            else:
                                vals['per_change'] = (vals['balance_cmp']>0 and -1 or 1) * 100
                        else:
                            if vals['balance_cmp'] == 0:
                                vals['per_change'] = (vals['balance']>0 and 1 or -1) * 100
                            else:
                                vals['per_change'] = ((vals['balance']-vals['balance_cmp'])/abs(vals['balance_cmp'])) * 100
                        vals['balance_cmp'] = account_obj.browse(cr, uid, account.id, context=data['form']['comparison_context']).balance * report.sign or 0.0
                        if not currency_obj.is_zero(cr, uid, account.company_id.currency_id, vals['balance_cmp']):
                            flag = True
                    if flag:
                        lines.append(vals)            
        values = []                
        #for line in lines:
        #    #if 'profit and loss' in line['parent_name'].lower():
        #    #if 'income' in line['name'].lower():
        #    line['flg'] = True
        #    #print '111111111111111111111111111111',line
        #    childs = self.get_childs(line,lines)
        #    line['childs'] = childs   
        #values=[d for d in lines if d['level'] <=3]
        '''
        income_index,income_rec =  next((index,d) for (index, d) in enumerate(lines) if d["name"].lower() == "income")
        total_income_rec = copy.deepcopy(income_rec)
        income_rec['has_childs'] = True
        total_income_rec['name'] = 'Total '+total_income_rec['name']
        total_income_rec['id'] = -total_income_rec['id']
        lines.insert(income_index+1,total_income_rec)
        income_id = income_rec['id']      
        expense_index,expense_rec =  next((index,d) for (index, d) in enumerate(lines) if d["name"].lower() == "expense")
        total_expense_rec = copy.deepcopy(expense_rec)
        expense_rec['has_childs'] = True
        total_expense_rec['name'] = 'Total '+total_expense_rec['name']
        total_expense_rec['id'] = -total_expense_rec['id']
        lines.insert(expense_index+1,total_expense_rec)
        expense_id = expense_rec['id']
        '''
        totals_dict = {}
        if data['form']['enable_filter']:
            parents = self.get_parents(cr, uid, lines, data['form']['enable_filter'], data['form']['comparison_context'], context=data['form']['used_context'])
        else:
            parents = self.get_parents(cr, uid, lines, context=data['form']['used_context'])            
        parents = sorted(parents, key=lambda k: k['id']) 
        if parents:
            for parent in parents:
                prec = {}
                try:
                    pind,prec = next((index,d) for (index, d) in enumerate(lines) if d["parent_id"] == parent['id'])
                except StopIteration:
                    pass
                  
                if prec:
                    brec = {}
                    try:
                        bind,brec = next((index,d) for (index, d) in enumerate(lines) if d["id"] == prec['parent_id'])
                    except StopIteration:
                        pass 
                    if not brec:     
                        lines.insert(pind,copy.deepcopy(parent))
         
        for idx,line in enumerate(lines):
            #par = filter(lambda val: val['id'] == line['parent_id'], lines)
            #if not par and line['type']!='report':
            #    if line['user_type'].lower().strip() == 'income':
            #        line['parent_id'] = income_id
            #    elif line['user_type'].lower().strip() == 'expense': 
            #        line['parent_id'] = expense_id
            chld = filter(lambda val: val['parent_id'] == line['id'], lines)
            if chld:                
                totals_dict[idx] = copy.deepcopy(line)
                line['has_childs'] = True
                totals_dict[idx]['name'] = 'Total '+line['name']
                totals_dict[idx]['id'] = totals_dict[idx]['id']+0.5
                
        loop = 1        
        #for key,val in totals_dict.iteritems():
        #    lines.insert(key+loop,val)
        #    loop+=1
            
        finals = []   
        newlines = copy.deepcopy(lines)    
        for idx,line in enumerate(lines):
            flg = False
            rec = {}
            try:
                index,rec = next((index,d) for (index, d) in enumerate(finals) if d["id"] == line['parent_id'])
            except StopIteration:
                pass
            if rec:
                dt = {}
                try:
                    ind,dt =  next((index,d) for (index, d) in enumerate(finals) if d["name"] == 'Total ' + line['parent_name'])
                except StopIteration:
                    pass    
                temp = False
                if dt:
                    finals.insert(ind,copy.deepcopy(line))
                    if line['has_childs']:
                        tot = copy.deepcopy(line)
                        tot['name'] = 'Total '+tot['name']
                        tot['id'] = tot['id']+0.5
                        tot['has_childs'] = False
                        finals.insert(ind+1,tot)
                else:
                    finals.insert(index+1,copy.deepcopy(line))
                    if line['has_childs']:
                        tot = copy.deepcopy(line)
                        tot['name'] = 'Total '+tot['name']
                        tot['id'] = tot['id']+0.5
                        tot['has_childs'] = False
                        finals.insert(index+2,tot)
            else:
                finals.append(copy.deepcopy(line))  
                if line['has_childs']:
                    tot = copy.deepcopy(line)
                    tot['name'] = 'Total '+tot['name']
                    tot['id'] = tot['id']+0.5
                    tot['has_childs'] = False
                    finals.append(tot)
        dt = {}
        chart_account_name = False   
        equityrec = False     
        chart_account = self.pool.get('account.account').browse(cr, uid, data['form']['chart_account_id'])
        chart_account_name = chart_account.code + ' ' + chart_account.name
        
        chld = filter(lambda val: val['parent_name']==chart_account_name, lines)   
        pl = self.get_pl_net_income(cr, uid, data)['balance']
        assetindex = False
        assetrec = False
        liabindex = False
        liabrec = False
        try:
            assetindex,assetrec = next((index,d) for (index, d) in enumerate(finals) if d["name"] == 'Total 1 ASSET')
        except StopIteration:
            pass
        total_asset = 0.00
        if assetrec:
            total_asset = assetrec['balance']
        try:
            liabindex,liabrec = next((index,d) for (index, d) in enumerate(finals) if d["name"] == 'Total 2 LIABILITIES')
        except StopIteration:
            pass
        total_liab = 0.00
        if liabrec:
            total_liab = liabrec['balance']   
        try:
            equityindex,equityrec = next((index,d) for (index, d) in enumerate(finals) if d["name"] == "Total 3 OWNERS' EQUITY")
        except StopIteration:
            pass
        total_equity = 0.00
        if equityrec:
            total_equity = equityrec['balance'] 
             
        
        if pl:
            net  = copy.deepcopy(chld[0])
            net['name'] = 'Total Net Profit / Loss'
            net['type'] = 'not report'
            net['has_childs'] = False
            net['level'] = -1
            net['balance'] = pl
            net['parent_name'] = False
            finals.append(net)
            net1  = copy.deepcopy(chld[0])
            net1['name'] = 'Total Net Equity'
            net1['type'] = 'not report'
            net1['has_childs'] = False
            net1['level'] = -1
            net1['balance'] = abs(total_equity)+pl
            net1['parent_name'] = False
            finals.append(net1)
            net2  = copy.deepcopy(chld[0])
            net2['name'] = 'Total Liabilities & Equity'
            net2['type'] = 'not report'
            net2['has_childs'] = False
            net2['level'] = -1
            net2['balance'] = abs(total_liab) + (abs(total_equity)+pl)
            net2['parent_name'] = False
            finals.append(net2)
        
        level_finals = []
        if data['form']['report_type'] and data['form']['report_type'][:5] == 'level':
            for dtrec in finals:               
                if int(dtrec['level']) <= int(data['form']['report_type'][5:]):
                    level_finals.append(copy.deepcopy(dtrec))
            self.final_results_bs = level_finals
            
            return level_finals
            
        #newfinals = sorted(finals, key=lambda k: k['id']) 
        self.final_results_bs = finals
        
        return finals 
        
        
    def print_report_pdf_tb(self, cr, uid, data, context=None):        
        datas = data['form']
        #print 'cccccccccccccc',datas
        self.title_tb = datas['title']
        self.filter_str_tb = datas['filter_str']
        self.company_tb = datas['company']
        fiscalyear_id = self.get_fiscal_year(cr, uid, data['form']['chart_account_id'], from_dt=data['form']['date_from'], to_dt=data['form']['date_to'])
        data['form']['fiscalyear_id'] = fiscalyear_id
        data['form']['used_context']['fiscalyear'] = fiscalyear_id
        ids = self.pool.get('account.balance.report').create(cr, uid, datas, context=data['form']['used_context'])
        ids = [ids]
        res = self.pool.get('account.balance.report').check_report(cr, uid, ids)
        #print 'ooooooooooooooooooooooooooooo'
        return res
        
    def get_lines_trail_balance(self, cr, uid, data, context=None):
        #print '################################11111111111111111', data['form'].has_key('from_load'), data
        
        if data['form'].has_key('from_load') and data['form']['from_load']:
            self.final_results_tb = False
            #print 'ccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
        elif self.final_results_tb:
            #print 'uuuuuuuuuuuuuuuuuuuuuuuuuddddddddddddddddddddddddddddddddddddddddddddd'
            return self.final_results_tb
        #data['form']['chart_account_id'] = self.get_company_chart_account(cr, uid)        
        fiscalyear_id = self.get_fiscal_year(cr, uid, data['form']['chart_account_id'], from_dt=data['form']['date_from'], to_dt=data['form']['date_to'])
        data['form']['fiscalyear_id'] = fiscalyear_id
        data['form']['used_context']['fiscalyear'] = fiscalyear_id
        lines = []
        lines = self.lines(cr, uid, data['form'], [data['form']['chart_account_id']])
        #print '<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<', data
        finals = []   
        newlines = copy.deepcopy(lines)    
        for idx,line in enumerate(lines):
            flg = False
            rec = {}
            try:
                index,rec = next((index,d) for (index, d) in enumerate(finals) if d["id"] == line['parent_id'])
            except StopIteration:
                pass
            if rec:
                dt = {}
                try:
                    ind,dt =  next((index,d) for (index, d) in enumerate(finals) if d["name"] == 'Total ' + line['parent_name'])
                except StopIteration:
                    pass    
                temp = False
                if dt:
                    finals.insert(ind,copy.deepcopy(line))
                    if line['has_childs']:
                        tot = copy.deepcopy(line)
                        tot['name'] = 'Total '+tot['name']
                        tot['id'] = tot['id']+0.5
                        tot['has_childs'] = False
                        finals.insert(ind+1,tot)
                else:
                    finals.insert(index+1,copy.deepcopy(line))
                    if line['has_childs']:
                        tot = copy.deepcopy(line)
                        tot['name'] = 'Total '+tot['name']
                        tot['id'] = tot['id']+0.5
                        tot['has_childs'] = False
                        finals.insert(index+2,tot)
            else:
                finals.append(copy.deepcopy(line))  
                if line['has_childs']:
                    tot = copy.deepcopy(line)
                    tot['name'] = 'Total '+tot['name']
                    tot['id'] = tot['id']+0.5
                    tot['has_childs'] = False
                    finals.append(tot)    
        self.final_results_tb = finals
        ##print 'nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn', finals
        return finals 
        
    def lines(self, cr, uid, form, ids=None, done=None):
        #print '11111111111111111111', cr, uid, form, ids
        self.cr = cr
        self.uid = uid
        self.sum_debit = 0.00
        self.sum_credit = 0.00
        self.date_lst = []
        self.date_lst_string = ''
        self.result_acc = []
        def _process_child(accounts, disp_acc, parent):
                #print '22222222222222222222222222', accounts, disp_acc, parent
                account_rec = [acct for acct in accounts if acct['id']==parent][0]
                currency_obj = self.pool.get('res.currency')
                acc_id = self.pool.get('account.account').browse(self.cr, self.uid, account_rec['id'])
                currency = acc_id.currency_id and acc_id.currency_id or acc_id.company_id.currency_id
                res = {
                    'id': account_rec['id'],
                    'type': account_rec['type'],
                    'code': account_rec['code'],
                    'name': account_rec['code'] + ' ' + account_rec['name'],
                    'level': account_rec['level'],
                    'debit': account_rec['debit'],
                    'credit': account_rec['credit'],
                    'balance': account_rec['balance'],
                    'parent_id': account_rec['parent_id'] and account_rec['parent_id'][0] or False,
                    'bal_type': '',
                    'has_childs': len(account_rec['child_id'])>0 and True or False,
                    'account_type': account_rec['type'],
                    'id':account_rec['id'],
                    'parent_name':account_rec['parent_id'] and account_rec['parent_id'][1] or False,
                    
                }
                if account_rec['level'] and account_rec['level']>self.max_level_tb:
                    self.max_level_tb = account_rec['level']
                self.sum_debit += account_rec['debit']
                self.sum_credit += account_rec['credit']
                if disp_acc == 'movement':
                    if not currency_obj.is_zero(self.cr, self.uid, currency, res['credit']) or not currency_obj.is_zero(self.cr, self.uid, currency, res['debit']) or not currency_obj.is_zero(self.cr, self.uid, currency, res['balance']):
                        self.result_acc.append(res)
                elif disp_acc == 'not_zero':
                    if not currency_obj.is_zero(self.cr, self.uid, currency, res['balance']):
                        self.result_acc.append(res)
                else:
                    self.result_acc.append(res)
                if account_rec['child_id']:
                    for child in account_rec['child_id']:
                        _process_child(accounts,disp_acc,child)

        obj_account = self.pool.get('account.account')
        if not ids:
            ids = self.ids
        if not ids:
            return []
        if not done:
            done={}

        ctx = self.context = {}
        #print '33333333333333333333333333333333333333333'
        ctx['fiscalyear'] = form['fiscalyear_id']
        if form['filter'] == 'filter_period':
            ctx['period_from'] = form['period_from']
            ctx['period_to'] = form['period_to']
        elif form['filter'] == 'filter_date':
            ctx['date_from'] = form['date_from']
            ctx['date_to'] =  form['date_to']
        ctx['state'] = form['target_move']
        parents = ids
        child_ids = obj_account._get_children_and_consol(self.cr, self.uid, ids, ctx)
        if child_ids:
            ids = child_ids
        accounts = obj_account.read(self.cr, self.uid, ids, ['type','code','name','debit','credit','balance','parent_id','level','child_id'], ctx)
        for parent in parents:
                if parent in done:
                    continue
                done[parent] = 1
                _process_child(accounts,form['display_account'],parent)
        return self.result_acc
        
        
    def print_report_pdf_cfs(self, cr, uid, data, context=None):        
        datas = data['form']
        self.title_cfs = datas['title']
        self.filter_str_cfs = datas['filter_str']
        self.company_cfs = datas['company']
        data['form']['display_account'] = 'all'
        #ids = self.pool.get('account.balance.report').create(cr, uid, datas, context=data['form']['used_context'])
        #ids = [ids]
        #res = self.pool.get('account.balance.report').check_report(cr, uid, ids)
        return self.pool['report'].get_action(cr, uid, [], 'website_account.report_cashflow_statement', data, context=data['form']['used_context'])
        #print 'ooooooooooooooooooooooooooooo'
        return res
        
    def get_lines_cashflow_statement(self, cr, uid, data, context=None):
        
        if data['form'].has_key('from_load') and data['form']['from_load']:
            self.final_results_cfs = False
        elif self.final_results_cfs:
            return self.final_results_cfs
        fiscalyear_id = self.get_fiscal_year(cr, uid, data['form']['chart_account_id'], data['form']['date_from'], data['form']['date_to'])
        data['form']['fiscalyear_id'] = fiscalyear_id
        data['form']['used_context']['fiscalyear'] = fiscalyear_id
        lines = []
        lines = self.set_data_template(cr, uid, data['form'])
        finals = []   
        retfinals = []
        invest = []
        total_invest = 0.0
        finance = []
        total_finance = 0.0
        operation = []
        total_operation = 0.0
        pl_debit =0.0
        pl_credit = 0.0
        pl_bal=0.0
        begin_bal = 0.0
        end_bal = 0.0
        pl_id = -2
        
        
        acc_obj = self.pool.get('account.account')
        pl_ids = acc_obj.search(cr, uid, [('name','=', 'Profit and Loss')])
        pl = self.get_pl_net_income(cr, uid, data)
        if pl:
            pl_debit =pl['debit']
            pl_credit = pl['credit']
            pl_bal = pl['balance']
            pl_id = pl['id']
        #To get the Beginning of period Balalnce
        frm = data['form']['date_from']
        data['form']['date_to'] = (datetime.strptime(frm, '%m-%d-%Y') + timedelta(days=-1)).strftime('%m-%d-%Y')
        data['form']['date_from'] = None
        begin_period_lines = self.set_data_template(cr, uid, data['form'])
        for key, val in begin_period_lines.iteritems():
            for detls in val:
                for acc,amnts in detls.iteritems():
                    begin_bal += amnts[2]
        pl_am = self.get_pl_net_income(cr, uid, data)['balance']
        begin_bal += pl_am
        
        
            
        retfinals.append({'name':'Cash Flow','has_childs':True, 'id':9999999996,'debit':0.0, 'credit':0.0, 'balance':0.0, 'parent_id':9999999994, 'parent_name':False, 'level':2})
        for key, val in lines.iteritems():
            if key == 'financing':
                keyid = 9999999997
                key_name = key.upper() + ' ACTIVITIES'
                finance.append({'name':key_name,'has_childs':True, 'id':keyid,'debit':0.0, 'credit':0.0, 'balance':0.0, 'parent_id':9999999996, 'parent_name':'Cash Flow', 'level':3})
                for details in val:
                    for acc,amts in details.iteritems():
                        acnt = acc_obj.browse(cr, uid, acc)
                        finance.append({'name':acnt.code+' ' +acnt.name,'has_childs':False, 'id':acnt.id,'debit':amts[0], 'credit':amts[1], 'balance':amts[2], 'parent_id':keyid, 'parent_name':key_name, 'level':4}) 
                        total_finance += amts[2]           
            elif key == 'investing':
                keyid = 9999999998
                key_name = key.upper() + ' ACTIVITIES'
                invest.append({'name':key_name,'has_childs':True, 'id':keyid,'debit':0.0, 'credit':0.0, 'balance':0.0, 'parent_id':9999999996, 'parent_name':'Cash Flow', 'level':3})
                for details in val:
                    for acc,amts in details.iteritems():
                        acnt = acc_obj.browse(cr, uid, acc)
                        invest.append({'name':acnt.code+' ' +acnt.name,'has_childs':False, 'id':acnt.id,'debit':amts[0], 'credit':amts[1], 'balance':amts[2], 'parent_id':keyid, 'parent_name':key_name, 'level':4})
                        total_invest += amts[2]
            else:  
                keyid = 9999999999  
                key_name = key.upper() + ' ACTIVITIES'
                operation.append({'name':key_name,'has_childs':True, 'id':keyid,'debit':0.0, 'credit':0.0, 'balance':0.0, 'parent_id':9999999996, 'parent_name':'Cash Flow', 'level':3})                 
                for details in val:
                    for acc,amts in details.iteritems():
                        acnt = acc_obj.browse(cr, uid, acc)
                        operation.append({'name':acnt.code+' ' +acnt.name,'has_childs':False, 'id':acnt.id,'debit':amts[0], 'credit':amts[1], 'balance':amts[2], 'parent_id':keyid, 'parent_name':key_name, 'level':5})  
                        total_operation += amts[2] 
                operation.append({'name':'to net cash provided by operations:','has_childs':False, 'id':-666,'debit':0.0, 'credit':0.0, 'balance':0.0, 'parent_id':keyid, 'parent_name':key_name, 'level':4, 'hide_bal':True})         
                operation.append({'name':'Adjustments to reconcile Net Income','has_childs':False, 'id':-666,'debit':0.0, 'credit':0.0, 'balance':0.0, 'parent_id':keyid, 'parent_name':key_name, 'level':4, 'hide_bal':True})         
                operation.append({'name':'Net Income','has_childs':False, 'id':pl_id,'debit':pl_debit, 'credit':pl_credit, 'balance':pl_bal, 'parent_id':keyid, 'parent_name':key_name, 'level':4})
                total_operation += pl_bal
        
        retfinals = retfinals + finance + invest + operation
        total_cashflow = total_operation + total_invest + total_finance  
        end_bal = begin_bal + total_cashflow
        
        newlines = copy.deepcopy(retfinals)    
        for idx,line in enumerate(retfinals):
            flg = False
            rec = {}
            try:
                index,rec = next((index,d) for (index, d) in enumerate(finals) if d["id"] == line['parent_id'])
            except StopIteration:
                pass
            if rec:
                dt = {}
                try:
                    ind,dt =  next((index,d) for (index, d) in enumerate(finals) if d["name"] == 'Total ' + line['parent_name'])
                except StopIteration:
                    pass    
                temp = False
                if dt:
                    finals.insert(ind,copy.deepcopy(line))
                    if line['has_childs']:
                        tot = copy.deepcopy(line)
                        tot_name = tot['name'].lower().replace(' activities','')
                        tot['name'] = tot_name == 'cash flow' and 'Net cash increase for period' or 'Net cash provided by '+tot['name'].title()
                        tot['id'] = tot['id']+0.5
                        tot['has_childs'] = False
                        tot['bold'] = True
                        tot['balance'] = (tot_name == 'financing' and total_finance or (tot_name == 'investing' and total_invest or (tot_name == 'operating' and total_operation or (tot_name == 'cash flow' and total_cashflow or 0.00))))
                        finals.insert(ind+1,tot)
                else:
                    finals.insert(index+1,copy.deepcopy(line))
                    if line['has_childs']:
                        tot = copy.deepcopy(line)
                        tot_name = tot['name'].lower().replace(' activities','')
                        tot['name'] = tot_name == 'cash flow' and 'Net cash increase for period' or 'Net cash provided by '+tot['name'].title()
                        tot['id'] = tot['id']+0.5
                        tot['has_childs'] = False
                        tot['bold'] = True
                        tot['balance'] = (tot_name == 'financing' and total_finance or (tot_name == 'investing' and total_invest or (tot_name == 'operating' and total_operation or (tot_name == 'cash flow' and total_cashflow or 0.00))))
                        finals.insert(index+2,tot)
            else:
                finals.append(copy.deepcopy(line))  
                if line['has_childs']:
                    tot = copy.deepcopy(line)
                    tot_name = tot['name'].lower().replace(' activities','')
                    tot['name'] = tot_name == 'cash flow' and 'Net cash increase for period' or 'Net cash provided by '+tot['name'].title()
                    tot['id'] = tot['id']+0.5
                    tot['has_childs'] = False
                    tot['bold'] = True
                    tot['balance'] = (tot_name == 'financing' and total_finance or (tot_name == 'investing' and total_invest or (tot_name == 'operating' and total_operation or (tot_name == 'cash flow' and total_cashflow or 0.00))))
                    finals.append(tot)   
        finals.append({'name':'Cash at beginning of period','has_childs':False, 'id':9999999995,'debit':0.0, 'credit':0.0, 'balance':begin_bal, 'parent_id':9999999994, 'parent_name':False, 'bold':True, 'level':2, 'total':True})   
        finals.append({'name':'Cash at end of period','has_childs':False, 'id':9999999994,'debit':0.0, 'credit':0.0, 'balance':end_bal, 'parent_id':False, 'parent_name':False, 'bold':True, 'level':1})             
        self.final_results_cfs = finals
        #print 'nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn', finals
        return finals
        
    def set_data_template(self, cr, uid, data,context=None):
        
        cash_flow_amounts, cash_flow_types, total_by_type = self.get_data_cash_flow_st(cr, uid, data,context)
        
        dict_update = {
                       'cash_flow_amounts': cash_flow_amounts,
                       'cash_flow_types':cash_flow_types,
                       'total_by_type':total_by_type                       
                       } 
        return cash_flow_amounts
        
    #1. Report parameters
    def get_report_parameters(self, cr, uid, data, context):
        
        filter_data = [] #contains the start and stop period or dates.
 
        #===================FILTER PARAMETERS =====================#       
        fiscalyear = self.pool.get('account.fiscalyear').browse(cr, uid, data['fiscalyear_id'])
        fiscal_year = fiscalyear
        filter_type = data['filter']
        target_move = 'posted'
        chart_account_id = data['chart_account_id']
        
        #======================FILTER TIME ===============================#       
        #if filter_type == 'filter_period':            
        #    #Build filter_data
        #    filter_data.append(self.get_start_period(data))
        #    filter_data.append(self.get_end_period(data))
            
        if filter_type == 'filter_date':
            #Build filter_data
            filter_data.append(data['date_from'])
            filter_data.append(data['date_to'])

        else:
            filter_type = ''        
        
        return {
                'filter_data' : filter_data,
                'filter_type': filter_type,
                'fiscal_year': fiscal_year,
                'chart_account_id': chart_account_id,
                'target_move': target_move,
                
                }
        
#2. Get all accounts that moves_cash
    def get_accounts_moves_cash(self, cr, uid, context):
        return self.pool.get('account.account').search(cr, uid, [('cashflow_act','!=',False)])
    
    #3. Get move_lines that match with filters.
    def get_move_lines(self, cr, uid, data, context):
        
        account_report_lib = self.pool.get('account.webkit.report.library')
        account_dict = {}
        
        #======================================================
        #Accounts
        account_ids = self.get_accounts_moves_cash(cr, uid, context) 
        #Parameters
        parameter_dict = self.get_report_parameters(cr, uid, data, context)
        
        #Get move_lines for each account.
        for account_id in account_ids:
            if account_id not in account_dict.keys():
                account_dict[account_id] = account_report_lib.get_move_lines(cr, uid,
                                                       account_ids=[account_id],   
                                                       filter_type=parameter_dict['filter_type'], 
                                                       filter_data=parameter_dict['filter_data'], 
                                                       fiscalyear=parameter_dict['fiscal_year'], 
                                                       target_move=parameter_dict['target_move'], 
                                                       unreconcile=False, 
                                                       historic_strict=False, 
                                                       special_period=False, 
                                                       context=context)
        
        #account_dict is a dictionary where key is account_id and it has all move_lines for each account.
        return account_dict
    
    #4. Build data for report
    def get_data_cash_flow_st(self, cr, uid, data,context):

        distribution_obj = self.pool.get('account.cash.flow.distribution')
        cash_flow_amounts = {} # contains amounts for each cash_flow_types
        cash_flow_details = {}
        cash_flow_types = {}   # Groups by type    
        total_by_type = {}     # Return total amount by type
        
        #===========================================================
        
        #Get move_lines
        account_dict = self.get_move_lines(cr, uid, data, context)
        
        #Find if lines have a distribution_line
        for account, move_lines in account_dict.iteritems():
            cash_flow_amounts = {}
            for line in move_lines:
                amount_debit = 0
                amount_credit = 0.0
                
                #Get debit and credit from original line. 
                if line.debit > 0:
                    amount_debit = line.debit
                elif line.credit > 0:
                    amount_credit = line.credit
                    
                #Search all distribution_lines that are asociated to line
                #lines_distribution = distribution_obj.search(cr, uid, [('account_move_line_id', '=', line.id)])
                #lines_distribution_list = distribution_obj.browse(cr, uid, lines_distribution)
                
                #Only if accounts have cash_flow_type
                #for line_distribution in lines_distribution_list:
                if line.account_id.cashflow_act:                        
                        cash_flow_type = line.account_id.cashflow_act
                        account_name = line.account_id.code + ' ' + line.account_id.name
#                        ====================================================================
#                        Create a dictionary, where key is cash_flow_type id. Create a list, with type, amount and name of
#                        cash_flow. Then, iterate this dictionary and group for type and print in report.
#                        List order = [type, debit, credit, amount, name]
#                        ====================================================================
                        if account not in cash_flow_amounts.keys():
                            target_amount = line.debit - line.credit
                            list = [amount_debit, amount_credit, target_amount]
                            cash_flow_amounts[account] = list                            
                        else:
                            temp_list = cash_flow_amounts[account]
                            #======= Update amounts                                
                            target_new_amount = line.debit - line.credit
                            temp_list[0] += amount_debit
                            temp_list[1] += amount_credit
                            temp_list[2] += target_new_amount
                            cash_flow_amounts[account] = temp_list      
            acc = self.pool.get('account.account').browse(cr, uid, account)
            cf_type = acc.cashflow_act
            if cash_flow_amounts:
                if cf_type not in cash_flow_details.keys():
                    cash_flow_details[cf_type] = [cash_flow_amounts]
                else:
                    cash_flow_details[cf_type].append(cash_flow_amounts)
        #========================================================================
        
        #Group in types (operational, investment, financing). Create list of each type (with id)
        #This connect dictionary with amounts (cash_flow_amounts) and dictionary with types.
        #example = {'operational': 1, 3, 4} -> cash_flow_id
        for type_name, items in cash_flow_details.iteritems():
            acc_name = items[0]
            if type_name not in cash_flow_types.keys():
                cash_flow_types[type_name] = [type_name] #position 2 is id of cash_flow_type. Create a list with id of cash_flow_type.
            
            else:
                list = cash_flow_types[type_name] 
                list.append(acc_name) #Add new id
                cash_flow_types[type_name] = list
                list = []
        
        
        #========================================================================
        amount = 0.0
        #Group totals by type, return a dictionary with totals.
        #Iterate in each id and sum, in cash_flow_amounts
        '''for type, list_ids in cash_flow_types.iteritems():
            for item in list_ids:
                if item in cash_flow_details.keys():
                    list_values = cash_flow_details[item] #extract info from cash_flow_details
                    amount += list_values[3] #amount for type.
            
            #for example
            #total_by_type['operational'] = ₡40 000
            total_by_type[type] = amount'''
       
        #=========================================================================
       
        #====RETURN THREE DICTIONARIES
        # 1. CASH_FLOW_AMOUNTS = Contains total amount, debit and credit for each cash_flow type
        # 2. CASH_FLOW_TYPES =  Return type_cash_flow as key (operational, investment and financing) and a list of ids of cash_flow_types that 
        # are associated of one of those types.
        # 3. TOTAL_BY_TYPE = Return a dictionary, where key is one type and it has total amount for each type.
        
        
        #If there not exist data, return empty dictionaries
        #if not cash_flow_amounts:
        '''cash_flow_types = {
                               'operation': [],
                               'investment': [],
                               'financing': [],
                               }'''
        total_by_type = {
                               'operation':0.0,
                               'investment': 0.0,
                               'financing':0.0,
                               }

        return cash_flow_details, cash_flow_types, total_by_type               
        
    def get_pl_net_income(self, cr, uid, data, context=None):    
        ret = []
        #print ',,,,,,,,,,,,,,,,', data
        account_obj = self.pool.get('account.account')
        currency_obj = self.pool.get('res.currency')
        rpt_id = self.pool.get('account.financial.report').search(cr, uid, [('parent_id','=',False), ('name','=','Profit and Loss')])
        data['form']['state'] = 'posted'
        if data['form']['date_from'] == None:
            data['form']['date_from'] = '01-01-1900'
        ids2 = self.pool.get('account.financial.report')._get_children_by_order(cr, uid, rpt_id, context=data['form'])
        ids2 = sorted(ids2)
        #print 'vvvv', data['form']['used_context']
        for report in self.pool.get('account.financial.report').browse(cr, uid, ids2, context=data['form']['used_context']):
            vals = {
                'name': report.name,
                'balance': report.balance * report.sign or 0.0,
                'type': 'report',
                'level': bool(report.style_overwrite) and report.style_overwrite or report.level,
                'account_type': report.type =='sum' and 'view' or False, #used to underline the financial report balances
                'parent_id':report.parent_id.id,
                'id':report.id,
                'flg':False,
                'parent_name':report.parent_id.name,
                'childs':[],
                'user_type':False,
                'parent_user_type':False,
                'has_childs':False,
                'debit':report.debit,
                'credit':report.credit,
            }
            #print 'mmmmmm', vals
            if report.name == 'Profit and Loss':
                return vals
        return {'balance':0.0}
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
