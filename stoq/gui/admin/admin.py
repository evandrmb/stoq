# -*- Mode: Python; coding: iso-8859-1 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2005 Async Open Source <http://www.async.com.br>
## All rights reserved
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307,
## USA.
##
## Author(s):   Evandro Vale Miquelito      <evandro@async.com.br>
##              Bruno Rafael Garcia         <brg@async.com.br>
##
"""
stoq/gui/admin/admin.py:

    Main gui definition for admin application.
"""

import gettext

from kiwi.ui.widgets.list import Column
from sqlobject.sqlbuilder import AND
from stoqlib.gui.search import SearchBar
from stoqlib.gui.columns import ForeignKeyColumn
from stoqlib.database import rollback_and_begin, finish_transaction

from stoq.gui.search.person import EmployeeRoleSearch, EmployeeSearch
from stoq.gui.application import AppWindow
from stoq.gui.editors.profile import UserProfileEditor
from stoq.gui.editors.person import UserEditor
from stoq.gui.slaves.filter import FilterSlave
from stoq.gui.wizards.person import run_person_role_dialog
from stoq.lib.runtime import new_transaction
from stoq.lib.defaults import ALL_ITEMS_INDEX
from stoq.domain.person import Person
from stoq.domain.profile import UserProfile
from stoq.domain.interfaces import IUser

_ = gettext.gettext


class AdminApp(AppWindow):
   
    app_name = _('Administrative')
    gladefile = "admin"
    
    widgets = ('add_button',
               'users_list', 
               'edit_button',
               'change_password_button')
    
    def __init__(self, app):
        self.conn = new_transaction()
        AppWindow.__init__(self, app)
        self.table = Person.getAdapterClass(IUser)
        self.users_list.set_columns(self._get_columns())
        self._setup_slaves()
        self._update_view()
        
    def _select_first_item(self, list):
        if len(list):
            # XXX this part will be removed after bug 2178
            list.select(list[0])

    def _setup_slaves(self):
        table = Person.getAdapterClass(IUser)
        items = [(value, key) for key, value in table.statuses.items()]
        items.append((_('Any'), ALL_ITEMS_INDEX))
        self.filter_slave = FilterSlave(items, selected=ALL_ITEMS_INDEX)
        self.filter_slave.set_filter_label(_('Show:'))
        self.search_bar = SearchBar(self, self.table,
                                    self._get_columns(), 
                                    filter_slave=self.filter_slave)
        self.search_bar.set_result_strings('user', 'users')
        self.search_bar.set_searchbar_labels(_('users Matching:'))
        self.filter_slave.connect('status-changed',
                                  self.search_bar.search_items)
        self.attach_slave("search_bar_holder", self.search_bar)

    def _update_view(self):
        has_selected = self.users_list.get_selected() is not None
        self.edit_button.set_sensitive(has_selected)
        self.change_password_button.set_sensitive(has_selected)

    def _get_columns(self):
        return [Column('username', title=_('Login Name'), sorted=True,
                       data_type=str, width=150, searchable=True),
                ForeignKeyColumn(UserProfile, 'name', title=_('Profile'),
                                 obj_field='profile', data_type=str,
                                 width=150),
                ForeignKeyColumn(Person, 'name', title=_('Name'), 
                                 data_type=str, obj_field='_original',
                                 width=300),
                Column('status_str', title=_('Status'), data_type=str)]

    def _edit_user(self): 
        user = self.users_list.get_selected()
        model =  run_person_role_dialog(UserEditor, self, self.conn, 
                                        user)
        if finish_transaction(self.conn, model, keep_transaction=True):
            self.users_list.update(model)

    #
    # Hooks
    #

    def get_extra_query(self):
        """Hook called by SearchBar"""
        q1 = self.table.q._originalID == Person.q.id
        q2 = UserProfile.q.id == self.table.q.profileID
        return AND(q1, q2)
        
    def update_klist(self, users=None):
        """Hook called by SearchBar"""
        rollback_and_begin(self.conn)
        self.users_list.clear()
        for user in users:
            # Since search bar change the connection internally we must get
            # the objects back in our main connection
            obj = self.table.get(user.id, connection=self.conn)
            self.users_list.append(obj)
        if len(self.users_list) > 0:
            self._select_first_item(self.users_list)
        self._update_view()

    def filter_results(self, users):
        """Hook called by SearchBar"""
        status = self.filter_slave.get_selected_status()
        if status == ALL_ITEMS_INDEX:
            return users
        elif status == self.table.STATUS_ACTIVE:
            return [user for user in users if user.is_active]
        elif status == self.table.STATUS_INACTIVE:
            return [user for user in users if not user.is_active]
        else:
            raise ValueError('Invalid status for User table. got %s'
                             % status)

    #
    # Callbacks
    #
    
    def on_users_list__double_click(self, *args):
        self._edit_user()
        
    def on_users_list__selection_changed(self, *args):
        self._update_view()

    def _on_employees_action_clicked(self, *args):
        self.run_dialog(EmployeeSearch, hide_footer=True)

    def _on_user_profiles_action_clicked(self, *args):
        model = self.run_dialog(UserProfileEditor, self.conn)
        finish_transaction(self.conn, model, keep_transaction=True)
    
    def _on_employee_role__action_clicked(self, *args):
        self.run_dialog(EmployeeRoleSearch)

    def on_add_button__clicked(self, *args):
        conn = new_transaction()
        model = run_person_role_dialog(UserEditor, self, conn)
        if finish_transaction(conn, model):
            self.search_bar.search_items()
            model = self.table.get(model.id, connection=self.conn)
            self.users_list.select(model)
        
    def on_edit_button__clicked(self, *args):
        self._edit_user()
            
    def on_change_password_button__clicked(self, *args):
        from stoq.gui.editors.person import PasswordEditor
        # This avoid circular import
        user = self.users_list.get_selected()
        model = self.run_dialog(PasswordEditor, self.conn, user)
        finish_transaction(self.conn, model, keep_transaction=True)
