#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2011-2015 The LogikSim Authors. All rights reserved.
# Use of this source code is governed by the GNU GPL license that can
# be found in the LICENSE.txt file.
#
'''
Defines scene that contain all the parts of the schematics.
'''

from logging import getLogger

from threading import Thread

from PySide import QtGui, QtCore


from backend.core import Core
from backend.controller import Controller
from backend.component_library import get_library
from logicitems.item_registry import ItemRegistry
from logicitems.insertable_item import InsertableRegistry
from actions.action_stack_model import ActionStackModel
import logicitems


class GridScene(QtGui.QGraphicsScene):
    # Emitted when the position or shape of any selected item has changed.
    selectedItemPosChanged = QtCore.Signal()

    # Emitted when the scene has become active or inactive.
    activated = QtCore.Signal(bool)

    # Emitted when items are selected or deselected.
    copyAvailable = QtCore.Signal(bool)

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)

        self.log = getLogger("scene")

        self._is_grid_enabled = True
        # can items be selected in this scene?
        self._allow_item_selection = False
        # can items be placed in this scene?
        self._allow_item_insertion = True

        # setup undo stack
        self.actions = ActionStackModel(self.tr("New circuit"), parent=self)
        self.actions.aboutToUndo.connect(self.onAboutToUndoRedo)
        self.actions.aboutToRedo.connect(self.onAboutToUndoRedo)

        # Simulation backend for this scene
        self._core = None
        self._controller = None
        self._interface = None
        self._registry = None
        self._core_thread = None

        self._setup_backend()

        # default values for new scene
        height = 100 * 1000  # golden ratio
        self.setSceneRect(0, 0, height * (1 + 5 ** 0.5) / 2, height)

        # setup selection item
        self._selection_item = logicitems.SelectionItem()
        self.addItem(self._selection_item)
        self.selectionChanged.connect(self._selection_item.onSelectionChanged)
        self.selectedItemPosChanged.connect(
            self._selection_item.onSelectedItemPosChanged)

        # setup signal for single selection notification
        self._single_selected_item = None
        self.selectionChanged.connect(self.onSelectionChanged)

        # incativity
        self._is_active = True
        self._registered_during_inactivity = set()  # set of BaseItems

        # group undo events
        self._is_undo_grouping = False
        self._undo_group_id = 0

    def _setup_backend(self):
        """Setup simulation backend for this scene."""
        self._core = Core()
        self._controller = Controller(self._core, get_library())
        self._interface = self._controller.get_interface()

        self._registry = ItemRegistry(self._controller, self)
        for cls in InsertableRegistry.get_insertable_types():
            self._registry.register_type(cls)
        self._registry.start_handling()

        self._core_thread = Thread(target=self._core.run)
        self._core_thread.start()

        # fetch all components and properties
        self._interface.enumerate_components()
        self._interface.query_simulation_properties()

        # Configure it how we want it to
        # self._interface.set_simulation_properties({'rate': 10})

        # Join threads on destruct (mustn't be a slot on this object)
        self.destroyed.connect(lambda: [self._core.quit(),
                                        self._core_thread.join()])

    def interface(self):
        return self._interface

    def registry(self):
        return self._registry

    def set_grid_enabled(self, value):
        assert isinstance(value, bool)
        self._is_grid_enabled = value

    def get_grid_spacing(self):
        return 100

    def get_grid_spacing_from_scale(self, scale):
        return 100 if scale > 0.033 else 500

    def get_lod_from_painter(self, painter):
        return QtGui.QStyleOptionGraphicsItem.levelOfDetailFromTransform(
            painter.worldTransform())

    def get_grid_spacing_from_painter(self, painter):
        lod = self.get_lod_from_painter(painter)
        return self.get_grid_spacing_from_scale(lod)

    def to_scene_point(self, grid_point):
        """
        Converts grid tuple to QPointF in scene coordinates.

        :param grid_point: Point in grid coordinates as tuple (int, int)
        :return: Point in scene coordinates as QtCore.QPointF
        """
        spacing = self.get_grid_spacing()
        x, y = grid_point
        return QtCore.QPointF(x * spacing, y * spacing)

    def to_grid(self, scene_point):
        """ Converts points in self.scene to grid points used here.

        The functions always rounds down

        :param scene_point: Point in scene coordinates as QtCore.QPointF
        :return: Point in grid coordinates as tuple (int, int)
        """
        spacing = self.get_grid_spacing()
        return int(scene_point.x() / spacing), int(scene_point.y() / spacing)

    def drawBackground(self, painter, rect):
        if self._is_grid_enabled:
            self._draw_grid(painter, rect)
        else:
            painter.setPen(QtCore.Qt.white)
            painter.setBrush(QtCore.Qt.white)
            painter.drawRect(rect)

    def _draw_grid(self, painter, rect):
        # calculate step
        lod = self.get_lod_from_painter(painter)
        step = self.get_grid_spacing_from_painter(painter)
        # estimate area to redraw (limit background to sceneRect)

        def step_round(x, n=0):
            return int(x / step + n) * step

        crect = rect.intersected(self.sceneRect())
        x0, y0 = map(step_round, (crect.x(), crect.y()))

        def get_extend(dir):
            return min(step_round(getattr(crect, dir)(), 2),
                       int(getattr(self.sceneRect(), dir)()))

        w, h = map(get_extend, ('width', 'height'))

        # pen_minor = QtGui.QPen((QtGui.QColor(23, 23, 23))) # dark mode
        # pen_major = QtGui.QPen((QtGui.QColor(30, 30, 30))) # dark mode
        pen_minor = QtGui.QPen((QtGui.QColor(0, 0, 0, 20)))  # light mode
        pen_major = QtGui.QPen((QtGui.QColor(0, 0, 0, 40)))  # light mode
        # draw border (everything outside of sceneRect)
        painter.setBrush(QtGui.QColor(210, 210, 210))
        painter.setPen(QtCore.Qt.NoPen)
        # border = QtGui.QPolygonF(rect).subtracted(QtGui.QPolygonF(
        #        self.sceneRect()))
        # painter.drawPolygon(border)
        painter.drawRect(rect)
        # translate to scene origin
        painter.save()
        painter.translate(x0, y0)
        # draw shadow and white background
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(100, 100, 100)))
        srect = QtCore.QRectF(0, 0, w, h)
        # painter.drawRect(srect.translated(5/lod, 5/lod))
        painter.setBrush(QtCore.Qt.white)
        painter.drawRect(srect)
        # draw grid

        def set_pen(z):
            painter.setPen(pen_major if z % 500 == 0 else pen_minor)

        for x in range(0, w, step):
            set_pen(x0 + x)
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            set_pen(y0 + y)
            painter.drawLine(0, y, w, y)
        # draw border
        painter.restore()
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtCore.Qt.black)
        # painter.drawRect(self.sceneRect().adjusted(-1/lod, -1/lod, 0, 0))
        # ### above does not work in PySide 1.2.2
        # ## see http://stackoverflow.com/questions/18862234
        # ## starting workaround
        rect = self.sceneRect().adjusted(-1 / lod, -1 / lod, 0, 0)
        painter.drawLine(rect.topLeft(), rect.topRight())
        painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.drawLine(rect.bottomRight(), rect.bottomLeft())
        painter.drawLine(rect.bottomLeft(), rect.topLeft())
        # ### end workaround

    def roundToGrid(self, pos, y=None):
        """
        round scene coordinate to next grid point

        pos - QPointF or x coordinate
        """
        if y is not None:
            pos = QtCore.QPointF(pos, y)
        spacing = self.get_grid_spacing()
        return (pos / spacing).toPoint() * spacing

    def selectionAllowed(self):
        return self._allow_item_selection

    def setSelectionAllowed(self, value):
        self._allow_item_selection = value
        if not value:
            self.clearSelection()

    def insertItemAllowed(self):
        return self._allow_item_insertion

    def setInsertItemAllowed(self, value):
        self._allow_item_insertion = value

    def is_active(self):
        """
        Returns True, if the scene is active.

        See set_active
        """
        return self._is_active

    def is_inactive(self):
        """
        Returns True, if the scene is inactive.

        See set_active
        """
        return not self._is_active

    def set_active(self, value):
        """
        If value is True, set the scene active.

        The scene is active by default.

        In an inactive scene item changes are not propagated
        to the backend. All changes made during this time
        are cached and send when the scene becomes active again.

        Items that change during inactivity may register
        their changes by calling register_change_during_inactivity.
        """
        if value != self._is_active:
            for item in self._registered_during_inactivity.copy():
                item.itemChange(
                    logicitems.ItemBase.ItemSceneActivatedChange, value)
            if value:
                self._update_connections(self._registered_during_inactivity)
            self._is_active = value
            for item in self._registered_during_inactivity:
                item.itemChange(
                    logicitems.ItemBase.ItemSceneActivatedHasChanged, value)
            self._registered_during_inactivity = set()
            self.update()
            self.activated.emit(value)

    def _update_connections(self, changed_items):
        """
        Update input and output connections.

        This function is called automatically before the scene becomes active.

        :param changed_items: list of changed items
        """
        # Include all objects connected to inputs of any changed item.
        # This is because items only manager their outputs.
        changed_items_set = set(item for item in changed_items
                                if item.scene() is self)
        for item in changed_items:
            changed_items_set.update(item.connected_input_items())
        # Also include all items located at connection positions.
        # This is mainly because items only manager their outputs.
        # We also include outputs here, because changes in LineTree
        # inputs also effects their outputs.
        for item in changed_items_set.copy():
            changed_items_set.update(item.items_at_connections())
        # First disconnect all outputs to prevent trying to make
        # connections to outputs that are not yet disconnected.
        for item in changed_items_set:
            item.disconnect_all_outputs()
        # Finally connect outputs on all items.
        for item in changed_items_set:
            item.connect_all_outputs()

    def register_change_during_inactivity(self, item):
        """
        Notify the scene that the item has changed during inactivity.

        This makes sure that the item is notified with
            item.itemChange(logicitems.ItemBase.ItemSceneActivatedChange)
        and
            item.itemChange(logicitems.ItemBase.ItemSceneActivatedHasChanged)
        once the scene becomes active.
        """
        # TODO: better assert self.is_inactive() here to prevent sync problems
        if self.is_inactive():
            self._registered_during_inactivity.add(item)

    def mousePressEvent(self, mouseEvent):
        # Hack: prevent clearing the selection, e.g. while dragging or pressing
        # the right mouse button
        #
        # original implementation has something like:
        # if qobject_cast<QGraphicsView*>(mouseEvent->widget()->parentWidget())
        #    view = mouseEvent->widget()
        #    dontClearSelection = view && view->dragMode() ==
        #         QGraphicsView::ScrollHandDrag
        view = mouseEvent.widget().parentWidget()
        if isinstance(view, QtGui.QGraphicsView):
            origDragMode = view.dragMode()
            try:
                view.setDragMode(QtGui.QGraphicsView.ScrollHandDrag)
                QtGui.QGraphicsScene.mousePressEvent(self, mouseEvent)
            finally:
                view.setDragMode(origDragMode)
        else:
            QtGui.QGraphicsScene.mousePressEvent(self, mouseEvent)

    def wheelEvent(self, event):
        QtGui.QGraphicsScene.wheelEvent(self, event)
        # mark event as handled (prevent view from scrolling)
        event.accept()

    def onSelectionChanged(self):
        def set_single_selection_state(item, state):
            if item is not None and item.scene() is self:
                assert isinstance(item, logicitems.ItemBase)
                item.itemChange(
                    logicitems.ItemBase.ItemSingleSelectionHasChanged, state)

        # disable last
        set_single_selection_state(self._single_selected_item, False)
        # enable new
        sel_items = self.selectedItems()
        if len(sel_items) == 1:
            self._single_selected_item = sel_items[0]
            set_single_selection_state(self._single_selected_item, True)
        else:
            self._single_selected_item = None
        # notify copyAvailable
        self.copyAvailable.emit(len(sel_items) > 0)

    @QtCore.Slot()
    def onAboutToUndoRedo(self):
        self.clearSelection()

    def getUndoGroupId(self):
        """
        Get undo redo group id.

        All undo/redo actions with the same group should be merged.
        """
        if self._is_undo_grouping:
            return self._undo_group_id
        else:
            return -1

    def beginUndoGroup(self):
        """Group all coming item changes into one undo entry."""
        self._undo_group_id += 1
        assert not self._is_undo_grouping
        self._is_undo_grouping = True

    def endUndoGroup(self):
        """End grouping of undo entries."""
        assert self._is_undo_grouping
        self._is_undo_grouping = False
