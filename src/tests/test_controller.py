#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2011-2014 The LogikSim Authors. All rights reserved.
# Use of this source code is governed by the GNU GPL license that can
# be found in the LICENSE.txt file.
#
import unittest
from backend.controller import Controller
from backend.interface import Handler
from tests.helpers import CallTrack, drain_queue, try_repeatedly


class ElementMock:
    def __init__(self, metadata=None):
        self._metadata = metadata if metadata else {}

    def id(self):
        return self.get_metadata_field('id')

    def get_metadata_field(self, field, default=None):
        return self._metadata.get(field, default)

    def set_metadata_fields(self, data, propagate=True):
        self._metadata.update(data)

    def get_metadata(self):
        return self._metadata

    def updated(self):
        pass


class CoreMock:
    def set_controller(self, controller):
        pass


class ControllerTest(unittest.TestCase):
    """
    Unit and integration tests for backend controller.
    """

    def test_element_creation(self):
        inst_counter = 0
        ids = []

        def instantiate_mock(guid, el_id, parent, metadata):
            nonlocal inst_counter
            inst_counter += 1
            ids.append(el_id)
            return ElementMock({'GUID': guid,
                                'id': el_id})

        library_emu = CallTrack(tracked_member="instantiate",
                                result_fu=instantiate_mock)

        ctrl = Controller(core=CoreMock(), library=library_emu)
        i = ctrl.get_interface()

        i.create_element("FOO")
        i.create_element("BAR")

        # Work around multiprocessing.Queue insertion delay
        try_repeatedly(lambda: not ctrl.get_channel_in().empty())
        ctrl.process(0)

        self.assertListEqual([("FOO", ids[0], ctrl, {}),
                              ("BAR", ids[1], ctrl, {})], library_emu())

        self.assertEqual(inst_counter, 2)

    def test_element_update(self):
        ids = []
        data = {}

        def instantiate_mock(guid, el_id, parent, metadata):
            nonlocal data
            nonlocal ids

            ids.append(el_id)

            data = {'GUID': guid,
                    'id': el_id,
                    'foo': 'bar',
                    'a': 'b'}

            return ElementMock(data)

        library_emu = CallTrack(tracked_member="instantiate",
                                result_fu=instantiate_mock)

        ctrl = Controller(core=CoreMock(), library=library_emu)
        i = ctrl.get_interface()

        i.create_element("FOO")
        try_repeatedly(lambda: not ctrl.get_channel_in().empty())
        ctrl.process(0)

        i.update_element(ids[0], {'foo': 'buz',
                                  'bernd': 'bread'})

        try_repeatedly(lambda: not ctrl.get_channel_in().empty())
        ctrl.process(0)

        self.assertEqual(1, len(ids))
        self.assertDictEqual({'GUID': 'FOO',
                              'id': ids[0],
                              'foo': 'buz',
                              'bernd': 'bread',
                              'a': 'b'}, data)

    def test_controller_element_root_parent_interface(self):
        class Lib:
            pass

        lib = Lib()

        ctrl = Controller(core=CoreMock(), library=lib)

        # def propagate_change(self, data)
        ctrl.propagate_change({'id': 1,
                               'foo': 'bar'})

        # Work around multiprocessing.Queue insertion delay
        try_repeatedly(lambda: not ctrl.get_channel_out().empty())

        self.assertListEqual([{'action': 'change',
                               'data': {'id': 1,
                                        'foo': 'bar'}}],
                             drain_queue(ctrl.get_channel_out()))

        # def get_library(self):
        self.assertIs(lib, ctrl.get_library())

        # def child_added(self, child):
        class El:
            pass

        e = El()
        ctrl.child_added(e)

        self.assertListEqual([e], ctrl._top_level_elements)

    def test_controller_handler(self):
        updates = []

        class HandlerMock(Handler):
            def handle(self, update):
                updates.append(update)
                return True

        root = None

        def instantiate_mock(guid, el_id, parent, metadata):
            nonlocal root
            root = parent
            return ElementMock({'GUID': guid,
                                'id': el_id})

        handler = HandlerMock()
        library_emu = CallTrack(tracked_member="instantiate",
                                result_fu=instantiate_mock)

        ctrl = Controller(core=CoreMock(), library=library_emu)
        ctrl.connect_handler(handler)

        i = ctrl.get_interface()
        i.create_element("FOO")

        # Work around multiprocessing.Queue insertion delay
        try_repeatedly(lambda: not ctrl.get_channel_in().empty())
        ctrl.process(0)

        root.propagate_change({'foo': 'bar'})
        root.propagate_change({'fiz': 'buz'})

        # Work around multiprocessing.Queue insertion delay
        try_repeatedly(lambda: not ctrl.get_channel_out().empty())
        handler.poll()

        self.assertListEqual([{'action': 'change',
                               'data': {'foo': 'bar'}},
                              {'action': 'change',
                               'data': {'fiz': 'buz'}}], updates)
