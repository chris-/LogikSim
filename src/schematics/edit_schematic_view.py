#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2011-2014 The LogikSim Authors. All rights reserved.
# Use of this source code is governed by the GNU GPL license that can 
# be found in the LICENSE.txt file.
#
'''
Defines the schematic view used to create and visualize logic circuits.
'''

from . import mouse_modes
from . import grid_scene

from PySide import QtCore


class EditSchematicView(
            mouse_modes.SelectItemsMode, 
            mouse_modes.InsertItemMode,
            mouse_modes.InsertLineMode,
            mouse_modes.InsertConnectorMode):
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.setScene(grid_scene.GridScene(self))
        self.setMouseMode(mouse_modes.SelectItemsMode)
    
#    @timeit
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
    
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_F1:
            print('selection mode')
            self.setMouseMode(mouse_modes.SelectItemsMode)
        elif event.key() == QtCore.Qt.Key_F2:
            print('insert logic element')
            self.setMouseMode(mouse_modes.InsertItemMode)
        elif event.key() == QtCore.Qt.Key_F3:
            print('insert connector')
            self.setMouseMode(mouse_modes.InsertConnectorMode)
        elif event.key() == QtCore.Qt.Key_F4:
            print('insert lines')
            self.setMouseMode(mouse_modes.InsertLineMode)
        elif event.key() == QtCore.Qt.Key_F5:
            actions = self.scene().actions

            if actions.canUndo():
                print('undo')
                self.scene().actions.undo()
            else:
                print("can't undo")

        elif event.key() == QtCore.Qt.Key_F6:
            actions = self.scene().actions

            if actions.canRedo():
                print('redo')
                self.scene().actions.redo()
            else:
                print("can't redo")
        elif event.key() == QtCore.Qt.Key_Escape:
            self.abort_line_inserting()
        else:
            super().keyPressEvent(event)
