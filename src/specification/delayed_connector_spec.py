'''
Created on May 23, 2011

@author: Christian
'''

import unittest

from simulation_model import DelayedConnectorModel, LogicValue


LV_0, LV_1, LV_X = map(LogicValue, '01X')

class DelayedConnectorSpec(unittest.TestCase):
    def test_default_values(self):
        dc_0 = DelayedConnectorModel(0, '0')
        dc_1 = DelayedConnectorModel(1, '1')
        self.assertListEqual([dc_0.delay, dc_1.delay], [0, 1])
        self.assertListEqual([dc_0.int_value, dc_1.int_value], [LV_0, LV_1])
        self.assertListEqual([dc_0.ext_value, dc_1.ext_value], [LV_0, LV_1])
    
    def test_propagation_output(self):
        dc = DelayedConnectorModel(0, '0')
        self.assertListEqual([dc.int_value, dc.ext_value], [LV_0, LV_0])
        
        dc.int_value = '1'
        self.assertListEqual([dc.int_value, dc.ext_value], [LV_1, LV_0])
        dc.on_calculate_next_state(0)
        dc.on_apply_next_state(0)
        self.assertListEqual([dc.int_value, dc.ext_value], [LV_1, LV_1])
    
    def test_propagation_input(self):
        dc = DelayedConnectorModel(0, '0')
        self.assertListEqual([dc.int_value, dc.ext_value], [LV_0, LV_0])
        
        dc.ext_value = 'X'
        self.assertListEqual([dc.int_value, dc.ext_value], [LV_1, LV_X])
        dc.on_calculate_next_state(0)
        dc.on_apply_next_state(0)
        self.assertListEqual([dc.int_value, dc.ext_value], [LV_X, LV_X])
    
    def test_on_calculate_next_state_invariance(self):
        dc = DelayedConnectorModel(0, '0')
        dc.int_value = '1'
        self.assertListEqual([dc.int_value, dc.ext_value], [LV_1, LV_0])
        dc.on_calculate_next_state(0)
        self.assertListEqual([dc.int_value, dc.ext_value], [LV_1, LV_0])
        
