from __future__ import absolute_import
import quantities as pq
import neo.core
from nineline.cells.neuron import NineCellMetaClass, \
                                  simulation_controller as nineline_controller
from .__init__ import Simulation


class NineLineSimulation(Simulation):
    "A simulation class for 9ml descriptions"

    def __init__(self, cell_9ml, build_mode='lazy'):
        """
        `cell_9ml`    -- A 9ml file [str]
        """
        # Generate the NineLine class from the nineml file and initialise a
        # single cell from it
        self.cell_9ml = cell_9ml
        self.celltype = NineCellMetaClass(cell_9ml, build_mode=build_mode)
        self.default_seg = self.celltype().source_section.name

    def set_tune_parameters(self, tune_parameters):
        super(NineLineSimulation, self).set_tune_parameters(tune_parameters)
        self.genome_keys = []
        self.log_scales = []
        for param in tune_parameters:
            if '.' in param.name:
                key = param.name
            else:
                key = self.default_seg + '.' + param.name
            self.genome_keys.append(key)
            self.log_scales.append(param.log_scale)

    def prepare_simulations(self):
        """
        Prepare all simulations (eg. create cells and set recorders if
        possible)
        """
        # Parse all recording sites into a tuple containing the variable name,
        # segment name and component names
        for setup in self._simulation_setups:
            for i, rec in enumerate(setup.record_variables):
                if rec is None:
                    # Records the voltage in the default segment by default
                    var = 'v'
                    segname = self.default_seg
                    component = None
                else:
                    parts = rec.split('.')
                    if len(parts) == 1:
                        var = parts[0]
                        segname = self.default_seg
                        component = None
                    elif len(parts) == 2:
                        segname, var = parts
                        component = None
                    else:
                        segname, component, var = parts
                setup.record_variables[i] = (var, segname, component)
        # Check to see if there are multiple setups, because if there aren't
        # the cell can be initialised (they can't in general if there are
        # multiple as there is only ever one instance of NEURON running)
        if len(self._simulation_setups) == 1:
            self._prepare(self._simulation_setups[0])

    def run(self, candidate, setup):
        """
        Run a simulation given a requested experimental setup required to
        assess the candidate

        `candidate` -- a list of parameters [list(float)]
        `setup`             -- a simulation setup [Setup]

        returns neo.Segment containing the measured analog signals

        """
        # If there aren't multiple simulation setups the same setup can be
        # reused with just the recorders being reset
        if len(self._simulation_setups) != 1:
            self._prepare(setup)
        else:
            nineline_controller.reset()
        self._set_candidate_params(candidate)
        # Convert requested record time to ms
        record_time = float(pq.Quantity(setup.record_time, units='ms'))
        # Run simulation
        nineline_controller.run(record_time)
        # Return neo Segment object with all recordings
        seg = neo.core.Segment()
        recordings = self.cell.get_recording(*zip(*setup.record_variables))
        seg.analogsignals.extend(recordings)
        return seg

    def _prepare(self, simulation_setup):
        """
        Initialises cell and sets recording sites. Record sites are delimited
        by '.'s into segment names, component names and variable names.
        Sitenames without '.'s are interpreted as properties of the default
        segment and site-names with only one '.' are interpreted as (segment
        name - property) pairs. Therefore in order to record from component
        states you must also provide the segment name to disambiguate it from
        the segment name - property case.

        `simulation_setup` -- A set of simulation setup instructions
                              [Simulation.SimulationSetup]
        """
        # Initialise cell
        self.cell = self.celltype()
        for rec in simulation_setup.record_variables:
            self.cell.record(*rec)

    def _set_candidate_params(self, candidate):
        """
        Set the parameters of the candidate

        `candidate` -- a list of parameters [list(float)]
        """
        assert len(candidate) == len(self.genome_keys), \
                                 "length of candidate and genome keys do " \
                                 "not match"
        for key, val, log_scale in zip(self.genome_keys, candidate,
                                       self.log_scales):
            if log_scale:
                val = 10 ** val
            setattr(self.cell, key, val)
