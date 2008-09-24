# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2005-2008 Async Open Source <http://www.async.com.br>
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
## Author(s):   Johan Dahlin               <jdahlin@async.com.br>
##
"""Payment groups, a set of payments

The two use cases for payment groups are:

  - Sale
  - Purchase

Both of them contains a list of payments and they behaves slightly
differently
"""

import datetime

from kiwi.argcheck import argcheck
from kiwi.datatypes import currency
from sqlobject.col import IntCol, DateTimeCol
from sqlobject.sqlbuilder import AND, IN, const
from zope.interface import implements

from stoqlib.domain.base import InheritableModelAdapter
from stoqlib.exceptions import DatabaseInconsistency
from stoqlib.domain.interfaces import (IContainer, IPaymentGroup,
                                       IInPayment)
from stoqlib.domain.payment.payment import Payment
from stoqlib.domain.till import Till
from stoqlib.lib.parameters import sysparam
from stoqlib.lib.translation import stoqlib_gettext

_ = stoqlib_gettext

class AbstractPaymentGroup(InheritableModelAdapter):
    """A base class for payment group adapters. """

    (STATUS_PREVIEW,
     STATUS_OPEN,
     STATUS_CLOSED,
     STATUS_CANCELLED) = range(4)

    statuses = {STATUS_PREVIEW: _(u"Preview"),
                STATUS_OPEN: _(u"Open"),
                STATUS_CLOSED: _(u"Closed"),
                STATUS_CANCELLED: _(u"Cancelled")}

    implements(IPaymentGroup, IContainer)

    status = IntCol(default=STATUS_OPEN)
    open_date = DateTimeCol(default=datetime.datetime.now)
    close_date = DateTimeCol(default=None)
    cancel_date = DateTimeCol(default=None)
    installments_number = IntCol(default=1)
    interval_type = IntCol(default=None)
    intervals = IntCol(default=None)

    #
    # IPaymentGroup implementation
    #

    #
    # FIXME: We should to remove all these methods without implementation, so
    # we can ensure that interface are properly implemented in subclasses.
    #
    def get_thirdparty(self):
        raise NotImplementedError

    def get_group_description(self):
        """Returns a small description for the payment group which will be
        used in payment descriptions
        """
        raise NotImplementedError

    def confirm(self):
        """This can be implemented in a subclass, but it's not required"""

    def pay(self, payment):
        pass

    #
    # IContainer implementation
    #

    @argcheck(Payment)
    def add_item(self, payment):
        payment.group = self

    @argcheck(Payment)
    def remove_item(self, payment):
        assert payment.group == self, payment.group
        payment.group = None

    def get_items(self):
        return Payment.selectBy(group=self,
                                connection=self.get_connection())

    #
    # Fiscal methods
    #

    def _get_paid_payments(self):
        return Payment.select(AND(Payment.q.groupID == self.id,
                                  IN(Payment.q.status,
                                     [Payment.STATUS_PAID,
                                      Payment.STATUS_REVIEWING,
                                      Payment.STATUS_CONFIRMED])),
                              connection=self.get_connection())

    #
    # Public API
    #

    def can_cancel(self):
        """ Returns True if it's possible to cancel the payment,
        otherwise False.
        """
        return self.status != AbstractPaymentGroup.STATUS_CANCELLED

    def cancel(self, renegotiation):
        """Cancels the payment group.
        This method does very little, it just changes the status and
        marks the payment group as cancelled. It's up to the subclasses
        to decide how to treat cancellation of all the contained payments
        @param renegotiation: renegotiation information
        @type renegotiation: L{RenegotiationData}
        """
        assert self.can_cancel()
        self.status = AbstractPaymentGroup.STATUS_CANCELLED
        self.cancel_date = const.NOW()

    def get_total_paid(self):
        return currency(self._get_paid_payments().sum('value') or 0)

    def add_inpayments(self):
        conn = self.get_connection()
        till = Till.get_current(conn)

        payment_count = self.get_items().count()
        if not payment_count:
            raise ValueError(
                'You must have at least one payment for each payment group')
        self.installments_number = payment_count

        for payment in self.get_items():
            assert payment.is_preview()
            payment.set_pending()
            assert IInPayment(payment, None)
            till.add_entry(payment)

            if payment.method.method_name == 'money':
                payment.pay()

    def clear_unused(self):
        """Delete payments of preview status associated to the current
        payment_group. It can happen if user open and cancel this wizard.
        """
        payments = Payment.selectBy(
            connection=self.get_connection(),
            status=Payment.STATUS_PREVIEW,
            group=self)
        for payment in payments:
            self.remove_item(payment)
            Payment.delete(payment.id)

    #
    # Accessors
    #

    def get_status_string(self):
        if not self.status in AbstractPaymentGroup.statuses.keys():
            raise DatabaseInconsistency("Invalid status, got %d"
                                        % self.status)
        return self.statuses[self.status]
