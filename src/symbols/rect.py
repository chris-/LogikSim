#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2011-2015 The LogikSim Authors. All rights reserved.
# Use of this source code is governed by the GNU GPL license that can
# be found in the LICENSE.txt file.
#
'''
Simple rect symbol for test purposes.
'''

from PySide import QtGui, QtCore

from simulation_model import Primitive


class Rect(QtGui.QGraphicsRectItem, Primitive,
           metaclass=type('RectMeta', (type(Primitive),
                                       type(QtGui.QGraphicsRectItem)), {})):
    def __init__(self, *args, **kargs):
        super(Rect, self).__init__(*args, **kargs)
        if kargs.get('json_data', None) is not None:
            pass
        else:
            self.setRect(0, 0, 500, 500)
            self.setPen(QtCore.Qt.Black)
            self.setBrush(QtCore.Qt.White)

    @classmethod
    def validate_data(cls, data):
        super(Primitive, cls).validate_data(data)
