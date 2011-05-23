#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on May 22, 2011

@author: Christian


Simulation Model
======================

The simulation model evolved from the following properties:

* Capable to simulate: Computing ICs, Schematic ICs, Interconnects

* Assuming an interconnect delays of zero.

The main idea to design this simulation was to have:

* calculate / apply cycles at discrete times

In the calculate step the output is calculated based on the current
state of the simulation and in the apply step these calculated value are 
applied to the simulation. 

Such an approach evolved from the fact that keeping track of dependencies
is tedious and it was natural first performing the calculation step on all
objects without changing the simulation.

    for obj in list:
        obj.calculate_state(t1)
    for obj in list:
        obj.apply_state(t1)


Necessity of Delays
======================

Breaking up the simulation in multiple Simulation Objects requires
transmission delays between them or two separate calculate / apply cycles

This is easy two see, just assume two separate Simulation Objects connected
with a zero delay signal, where the second object depends on the state
of the first one. This scenario would require the following simulation cycle:

1: object1.calculate_state(t1)
2: object1.apply_state(t1)
3: object2.calculate_state(t1)
4: object2.apply_state(t1)

Remarkably such an simulation cycle is impossible to achieve with circular 
dependencies, where object1 depends on object2 and object2 depends on object1. 
In such a situation a transmission delay for (some) signals between 
object1 and object2 is necessary.

Consequences
======================

* All interconnect parts have to share one SimulationObject -> Signal

* These Signals have to cross module boundaries: Interconnect parts of the
    sub module and of the containing module have to belong to the same Signal.
    -> Transparent Connectors for Schematic ICs

* Due to the possible loop nature of Computing ICs they cannot be integrated
    into the Signal Simulation Objects
    -> Simulation ICs have to have their own Simulation Object
        -> Simulation ICs need propagation delay!

Computing ICs
======================

Cause of the filter nature of delayed signals described above we simulate
the necessary propagation delay of our Computing ICs with delayed input 
signals. (Filtering on inputs might possible reduce compute / apply cycles
of Computing ICs)

To reduce the complexity of our model we assume an output delay of zero
for output connectors. However, this has some consequences for our 
interconnect signals.

Delayed Inputs
======================

Delayed Inputs propagate their input value to their Computing IC after a 
specific time. To limit the bandwidth of a delayed signal all changes that are 
shorter than the transmission delay are filtered out.

In principle we could define two different delays, but we restrict the input 
connector model two one number for brevity. (This simplification doesn't 
introduce any limitation. If a further delay is needed, it wouldn't be very 
hard to set the input connector delay according to your maximum bandwidth of 
the IC and simulate a transmission delay in the IC code)

Interconnects
======================

As already mentioned above all connected interconnect parts belong to one
Signal even across sub module / Schematic IC boundaries, where each Signals
belongs to one interconnect trees.

Due to the zero output delay of Computing ICs Signal at time t1 is dependent on 
the outputs of Computing ICs at t1. This suggests two separate compute / apply 
cycles first for our Computing ICs and then after that one for our Signals 
(see section Necessity of Delays).

    for computing_ic in computing_ics:
        computing_ic.calculate(t1)
    for computing_ic in computing_ics:
        computing_ic.apply(t1)
    
    for signal in signals:
        signal.calculate(t1)
    for signal in signals:
        signal.apply(t1)

Cycle Optimizations
======================

Since signal interconnect trees are only connected trough Computing ICs, 
which as shown above have to have a transmission delay, the state of one Signal 
at time t1 is only dependent on the state of the output states of computing
ICs at time t1. Especially the state of one Signal doesn't depend on any other 
Signal at time t1 or any previous point in time. 

This result can be used to simplify the compute / apply circle for Signals.

    for signal in signals:
        signal.calculate_and_apply(t1)

A similar statement can be derived for Computing ICs: A computing IC at time t1 
only depends on the state of Signals at time t2 < t1.

Thus the final simulation loop can be reduced to:

    for computing_ic in computing_ics:
        computing_ic.calculate_and_apply(t1)
    
    for signal in signals:
        signal.calculate_and_apply(t1)

Input Connectors Integration
======================

There are still some options on how to model the input connectors. 

* integrate the logic into the computing_ic.calculate_and_apply method

* having own Simulation Objects whose calculate_and_apply method is
    called in the calculate_and_apply of the owning computing_ic

* as separate Simulation Objects with their own calculate_and_apply
    apply loop preceding the calculate_and_apply of the computing_ics

Before deciding which solution might be the best it is advisable to first 
have a look at the time discretisation.

Time Discretisation
======================

Our simulation contains only logical signals which are discrete in time
and value. Looking at a specific input the value can only change at specific
times and we only have to invoke the logic behind it at these times. The same
applies for the output. Thus it is sufficient to limit computations to two 
events:

* When the input changes state -> Invoke Computation IC

* When a delay has expired, defined by the component itself on the last call
    (e.g. necessary for clocks)

We will then increase the simulation time to the point in time when the next
delay expires and invoke only those Simulation Object which have pending
events at that time.

Final simulation cycle
======================

At the beginning of the simulation all Input Connectors are flagged as
having changed, at a later point in time the list changed_inputs will
only contain those, who want to change their value at that time.

    sim_time = 0
    
    changed_inputs = get_input_changes(sim_time)

These inputs will now add change their internal value and then add their
parent Computation IC to the changed_ics list.

    changed_ics = set()
    
    for input in changed_inputs:
        input.apply_state(sim_time)
        changed_ics.add(input.parent)

Now the ics with expired delays are added

    changed_ics.update( get_ics_with_expired_delays(sim_time) )
    changed_signals.clear()

    for ic in changed_ics:
        delta = ic.calculate_and_apply(sim_time)
        if delta is not None:
            set_future_ic_event(sim_time + delta, ic)

Whenever an ic is setting an output in the calculate_and_apply method the 
output checks if he is connected to a signal and in such a case adds the 
Signal to the changed_signals set. The ic can decide if he wants to be
called in the future by returning a delta value.

Then the signal states are updated

    for signal in changed_signals:
        signal.update_state()
        
        for input in signal.connected_inputs():
            delta = input.set_value(signal.value, sim_time)
            set_future_input_event(sim_time + delta, input)

After a signal has been updated all connected inputs are invoked
and the return value is used to generate future input events. This returned
delta indicates when the Input wants to pass a new internal value to its
owning Computing IC.

Additional Notes
======================

Component defined future events are deleted when the IC is called at
an earlier time by different e.g. input event. It is also impossible
to have multiple pending component event.

The logic behind the set_future_input_event / get_input_changes and
set_future_ic_event / get_ics_with_expired_delays will be on two
priority queues and a separate dictionary to prevent multiple entries
for the same input / ic.

"""

import weakref


class LogicValue(object):
    """ inspired by four-valued logic common to most HDLs """
    _representation = frozenset('01X')
    __slots__ = ['_value', '__weakref__']
    
    def __init__(self, value):
        """ one of '0', '1' or 'X' """
        if value not in self._representation:
            raise ValueError('Invalid logic value')
        self._value = value
    
    def __repr__(self):
        return 'LogicValue(%r)' % str(self)
    
    def __str__(self):
        return self._value
    
    def __eq__(self, other):
        """ == """
        if isinstance(other, LogicValue):
            return self._value == other._value
        else:
            return False
    
    def __ne__(self, other):
        """ != """
        return not self == other
    
    def __hash__(self):
        return hash(LogicValue) ^ hash(self._value)
    
    def __and__(self, other):
        """ & logical and """
        if not isinstance(other, LogicValue):
            return NotImplemented
        values = (self._value, other._value)
        if '0' in values:
            return LogicValue('0')
        elif 'X' in values:
            return LogicValue('X')
        else:
            return LogicValue('1')
    
    def __or__(self, other):
        """ | logical or """
        if not isinstance(other, LogicValue):
            return NotImplemented
        values = (self._value, other._value)
        if '1' in values:
            return LogicValue('1')
        elif 'X' in values:
            return LogicValue('X')
        else:
            return LogicValue('0')
    
    def __xor__(self, other):
        """ ^ logical xor """
        if not isinstance(other, LogicValue):
            return NotImplemented
        if 'X' in (self._value, other._value):
            return LogicValue('X')
        elif self._value == other._value:
            return LogicValue('0')
        else:
            return LogicValue('1')
    
    _inv_table = {'0': '1', '1': '0', 'X': 'X'}
    def __invert__(self):
        """ ~ logical invert """
        return LogicValue(self._inv_table[self._value])
    
    def __add__(self, other):
        """
        + merges two signals, if compatible, returns 'X' otherwise
        (0 + 0 -> 0; 1 + 1 -> 1; 1 + 0 = X) 
        """
        if not isinstance(other, LogicValue):
            return NotImplemented
        if 'X' in (self._value, other._value):
            return LogicValue('X')
        elif self._value == other._value:
            return LogicValue(self._value)
        else:
            return LogicValue('X')
    
    def __nonzero__(self):
        """ bool, if, not """
        raise ValueError("Casting a LogicValue to bool is not supported")
    
    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            # we assume that instance attributes are accessed many times
            # more than created, since the exception path is 10 times slower
            try:
                return instance.__dict__[id(self)]
            except KeyError:
                val = LogicValue(self._value)
                instance.__dict__[id(self)] = val
                return val
    
    def __set__(self, instance, value):
        lv = self.__get__(instance, None)
        
        if isinstance(value, str):
            lv.__init__(value)
        elif isinstance(value, LogicValue):
            lv._value = value._value
        else:
            raise TypeError('Unsupported type, try "0" or '
                    'LogicValue("0") instead')
    
    def __delete__(self, instance):
        if id(self) in instance.__dict__:
            del instance.__dict__
    
    def copy_from(self, value):
        """
        copies value to internal state
        
        useful if you want to change the value of a logic_value with multipla
        references
        """
        self.__set__(None, value)


class SimulationObject(object):
    """
    defines an abstract method interface for all simulation parts
    """
    def on_calculate_next_state(self, sim_time):
        """
        calculate the next state based on all current inputs
        
        This function is called whenever an input has changed state or
        after a user defined delta_time
        
        sim_time (float) - current point in time in seconds of the simulation
        @return (float or None) - you can optionally return a delta_time, 
                which will guaranty that on_calculate_next_state is called
                again after delta_time (in seconds).
        """
        raise NotImplementedError
    
    def on_apply_next_state(self, sim_time):
        """
        Apply the calculated state to the outputs
        
        sim_time (float) - current point in time in seconds of the simulation
        
        is called after calculate_next_state was invoked for every item
        in the simulation.
        """
        raise NotImplementedError


class InputConnectorModel(SimulationObject):
    int_value = LogicValue('0')
    ext_value = LogicValue('0')
    
    _int_value_last = LogicValue('0')
    _ext_value_last = LogicValue('0')
    
    def __init__(self, delay, value):
        SimulationObject.__init__()
        
        self.delay = delay
        self.int_value = value
        self.ext_value = value
        #self._int_value_last = value
        #self._ext_value_last = value
    
    def on_calculate_next_state(self, sim_time):
        self
    
    def on_apply_next_state(self, sim_time):
        pass


class OutputConnectorModel(SimulationObject):
    pass
    


class UnidirectionalSignal(SimulationObject, LogicValue):
    """
    unidirectional signal to connect an input and an output with a
    user defined delay
    
    Used e.g. in connectors
    """
    _int_state = LogicValue('0')
    
    def __init__(self, delay, default='0'):
        SimulationObject.__init__(self)
        LogicValue.__init__(self, default)
        
        self.delay = delay
        self._int_state = default
        self._slots = weakref.WeakSet()
        self._last_change = 0
    
    def connect(self, logic_value):
        assert isinstance(logic_value, LogicValue)
        self._slots.add(logic_value)
    
    def disconnect(self, logic_value):
        self._slots.remove(logic_value)
    
    def on_calculate_next_state(self, sim_time):
        self._int_state = self
        self._last_change = sim_time
    
    def on_apply_next_state(self, sim_time):
        if sim_time - self._last_change >= self.delay:
            for lv in self._slots:
                lv.copy_from(self)

