# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2012 Async Open Source <http://www.async.com.br>
## All rights reserved
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Lesser General Public License for more details.
##
## You should have received a copy of the GNU Lesser General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., or visit: http://www.gnu.org/.
##
## Author(s): Stoq Team <stoq-devel@async.com.br>
##

from stoqlib.gui.dialogs.stockcostdialog import StockCostDialog
from stoqlib.gui.uitestutils import GUITest


class TestStockCostDialog(GUITest):
    def test_confirm(self):
        dialog = StockCostDialog(self.trans)

        treeview = dialog.slave.listcontainer.list.get_treeview()
        treeview.set_cursor(0)
        rows, column = treeview.get_cursor()
        item = dialog.slave.listcontainer.list[0]
        dialog.slave.listcontainer.list.emit('cell-edited', item, 'initial_stock')
        self.assertNotEquals((rows, column), treeview.get_cursor())

        self.click(dialog.main_dialog.ok_button)
        self.check_dialog(dialog, 'dialog-stock-cost-confirm', dialog.retval)