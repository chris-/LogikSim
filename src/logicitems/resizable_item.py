#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2011-2014 The LogikSim Authors. All rights reserved.
# Use of this source code is governed by the GNU GPL license that can
# be found in the LICENSE.txt file.
#
'''
Resizable logic item with variable number of inputs.
'''

from PySide import QtGui, QtCore

import logicitems
from actions.resize_action import ResizeAction


class ResizableItem(logicitems.LogicItem):
    # item overlap above first and below last input connector in
    # in grid gap fraction
    _overlap = 0.37

    def __init__(self, parent=None, metadata={}):
        super().__init__(parent=parent, metadata=metadata)

        self._input_count = metadata.get('#inputs', 2)

        # internal state
        self._show_handles = False
        self._body_rect = QtCore.QRectF(0, 0, 0, 0)
        self._connectors = []
        self._handles = {}

    def update(self, metadata):
        super().update(metadata)

        input_count = metadata.get('#inputs')
        if input_count is not None:
            self.set_input_count_and_pos(input_count)

    def get_input_count(self):
        return self._input_count

    def set_input_count_and_pos(self, new_input_count, new_position=None):
        # create undo redo event
        if not self.is_temporary():
            action = ResizeAction(self.scene().getUndoRedoGroupId(), self,
                                  self.get_input_count(), self.pos(),
                                  new_input_count, new_position)
            self.scene().actions.push(action)
        # update input count
        self._input_count = new_input_count
        self._update_state()
        # update position
        if new_position is not None:
            temp = self.is_temporary()
            self.set_temporary(True)
            self.setPos(new_position)
            self.set_temporary(temp)

    def _set_show_handles(self, value):
        if value != self._show_handles:
            self._show_handles = value
            self._update_resize_tool_handles()

    def _update_state(self):
        assert self.scene() is not None
        self._invalidate_bounding_rect()
        scale = self.scene().get_grid_spacing()
        # update body
        self._body_rect = self._to_col_rect(QtCore.QRectF(
            0, -scale * self._overlap, scale * 2,
            scale * (self._input_count - 1 + 2 * self._overlap)))
        # update connectors
        for con in self._connectors:
            con.setParentItem(None)
        self._connectors = []
        for i in range(self._input_count):
            # inputs
            con = logicitems.ConnectorItem(
                self, QtCore.QPointF(0, scale * (i)),
                QtCore.QPointF(-scale, scale * (i)))
            self._connectors.append(con)
        # output
        mid_point = int((self._input_count - 1) / 2)
        con = logicitems.ConnectorItem(
            self, QtCore.QPointF(2 * scale, scale * (mid_point)),
            QtCore.QPointF(3 * scale, scale * (mid_point)))
        self._connectors.append(con)

    def _update_resize_tool_handles(self):
        for handle in self._handles.values():
            handle.setParentItem(None)
        self._handles = {}
        if self.isSelected() and self._show_handles:
            scale = self.scene().get_grid_spacing()
            ht = logicitems.ResizeHandle(self, horizontal=False,
                                         resize_callback=self.on_handle_resize)
            ht.setPos(scale, -scale * self._overlap)
            hb = logicitems.ResizeHandle(self, horizontal=False,
                                         resize_callback=self.on_handle_resize)
            hb.setPos(scale, (self._input_count - 1 + self._overlap) * scale)
            self._handles = {'top': ht, 'bottom': hb}

    def on_handle_resize(self, handle, delta):
        sign = (-1 if handle is self._handles['top'] else 1)
        round_delta = self.scene().roundToGrid(delta)
        input_delta = sign * self.scene().to_grid(round_delta)[1]  # y delta
        new_input_count = max(2, self._input_count + input_delta)
        if new_input_count != self._input_count:
            eff_pos_delta = self.scene().to_scene_point(
                (0, (new_input_count - self._input_count)))
            # calc new position
            if handle is self._handles['top']:
                new_pos = self.pos() - eff_pos_delta
            else:
                new_pos = None
            # update item
            self.set_input_count_and_pos(new_input_count, new_pos)
            # update handle position
            self._handles['bottom'].setPos(self._handles['bottom'].pos() +
                                           eff_pos_delta)
            # notify scene of change
            self.scene().selectedItemPosChanged.emit()

    def itemChange(self, change, value):
        if change is QtGui.QGraphicsItem.ItemSceneHasChanged:
            if value is not None:
                self._update_state()
        elif change is QtGui.QGraphicsItem.ItemSelectedHasChanged:
            self._update_resize_tool_handles()
        elif change == logicitems.ItemBase.ItemSingleSelectionHasChanged:
            self._set_show_handles(value)
        return super().itemChange(change, value)

    def ownBoundingRect(self):
        return self._body_rect

    def selectionRect(self):
        rect = self.ownBoundingRect()
        for con in self._connectors:
            rect = rect.united(con.boundingRect())
        return rect

    def paint(self, painter, options, widget):
        painter.setBrush(QtGui.QColor(255, 255, 128))
        painter.setPen(QtCore.Qt.black)
        painter.drawRect(self._body_rect)