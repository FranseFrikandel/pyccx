import abc
from enum import auto, Enum, Flag
from typing import Any, List, Tuple, Union

import numpy as np

from ..core import Amplitude, ElementSet, ModelObject, NodeSet, SurfaceSet, DOF


class BoundaryConditionType(Flag):
    """
    Boundary condition type specifies which type of analyses the boundary condition may be applied to. Flags may be mixed
    when coupled analyses are performed (e.g.  thermo-mechanical analysis: STRUCTURAL | THERMAL)
    """

    ANY = auto()
    """ Boundary condition can be used in any analysis"""

    STRUCTURAL = auto()
    """ Boundary condition can be used in a structural analysis"""

    THERMAL = auto()
    """ Boundary condition can be used in a thermal analysis"""

    FLUID = auto()
    """ Boundary condition can be used in a fluid  analysis"""


class BoundaryCondition(ModelObject):
    """
    Base class for all boundary conditions
    """

    def __init__(self, name, target, amplitude = None, timeDelay = None):

        self.init = True
        self._target = target

        if not name:
            name = ''

        self._amplitude = amplitude
        self._timeDelay = timeDelay

        super().__init__(name)

    @property
    def name(self):
        """
        The name of the boundary condition
        """
        return self._name

    @name.setter
    def name(self, name: str):
        self._name = name

    @property
    def amplitude(self) -> Union[None, Amplitude]:
        """
        Apply a single Amplitude (time based profile) for the boundary condition
        """
        return self._amplitude

    @amplitude.setter
    def amplitude(self, amplitude: Amplitude):
        if not isinstance(amplitude, Amplitude):
            raise TypeError('Boundary condition\'s amplitude must be an Amplitude object')

        self._amplitude = amplitude

    @property
    def timeDelay(self) -> Union[None, float]:
        """
        A time delay can be added before initiating an Amplitude profile on the boundary condition
        """
        return self._timeDelay

    @timeDelay.setter
    def timeDelay(self, time):
        if time < 1e-8:
            self._timeDelay = None
        else:
            self._timeDelay = time
    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, target):
        self._target = target

    def getTargetName(self) -> str:
        return self._target.name

    def getBoundaryElements(self):

        if isinstance(self._target, ElementSet):
            return self._target.els

        return None

    def getBoundaryFaces(self):

        if isinstance(self._target, SurfaceSet):
            return self._target.surfacePairs

        return None

    def getBoundaryNodes(self):

        if isinstance(self._target, NodeSet):
            return self._target.nodes

        return None

    @abc.abstractmethod
    def type(self) -> BoundaryConditionType:
        """
        Returns the BC type so that they are only applied to suitable load cases
        """
        raise NotImplemented()

    @abc.abstractmethod
    def writeInput(self) -> str:
        raise NotImplemented()


class Film(BoundaryCondition):
    """
    The film or convective heat transfer boundary condition applies the Newton's law of cooling
    - :math:`q = h_{c}\\left(T-T_{amb}\\right)` to specified faces of
    boundaries elements (correctly ordered according to Calculix's requirements). This BC may be used in thermal and
    coupled thermo-mechanical analyses.
    """

    def __init__(self, target, h: float = 0.0, TAmbient: float = 0.0,
                 name: str = None, amplitude: Amplitude = None, timeDelay: float = None):

        self.h = h
        self.T_amb = TAmbient

        if not isinstance(target, SurfaceSet):
            raise ValueError('A SurfaceSet must be used for a Film Boundary Condition')

        super().__init__(name, target, amplitude, timeDelay)

    def type(self) -> BoundaryConditionType:
        return BoundaryConditionType.THERMAL

    @property
    def heatTransferCoefficient(self) -> float:
        """
        The heat transfer coefficient :math:`h_{c}` used for the Film Boundary Condition
        """
        return self.h

    @heatTransferCoefficient.setter
    def heatTransferCoefficient(self, h: float) -> None:
        self.h = h

    @property
    def ambientTemperature(self) -> float:
        """
        The ambient temperature :math:`T_{amb}`. used for the Film Boundary Condition
        """
        return self.T_amb

    @ambientTemperature.setter
    def ambientTemperature(self, Tamb: float) -> None:
        self.T_amb = Tamb

    def writeInput(self) -> str:
        bCondStr = '*FILM'

        if self._amplitude:
            bCondStr += ', AMPLITUDE = {:s}'.format(self._amplitude.name)

        if self._timeDelay:
            bCondStr += ', TIMEDELAY = {:e}'.format(self._timeDelay)

        bCondStr += '\n'

        bfaces = self.getBoundaryFaces()

        for i in len(bfaces):
            bCondStr += '{:d},F{:d}, {:e}, {:e}\n'.format(bfaces[i, 0], bfaces[i, 1], self.T_amb, self.h)

        return bCondStr


class HeatFlux(BoundaryCondition):
    """
    The flux boundary condition applies a uniform external heat flux :math:`q` to faces of surface
    boundaries elements (correctly ordered according to Calculix's requirements). This BC may be used in thermal and
    coupled thermo-mechanical analyses.
    """

    def __init__(self, target, flux: float = 0.0,
                 name: str = None, amplitude: Amplitude = None, timeDelay: float = None):

        self._flux = flux

        if not isinstance(target, SurfaceSet):
            raise ValueError('A SurfaceSet must be used for a Heat Flux Boundary Condition')

        super().__init__(name, target, amplitude, timeDelay)

    def type(self) -> BoundaryConditionType:
        return BoundaryConditionType.THERMAL

    @property
    def flux(self) -> float:
        """
        The flux value :math:`q` used for the Heat Flux Boundary Condition
        """
        return self._flux

    @flux.setter
    def flux(self, fluxVal: float) -> None:
        self._flux = fluxVal

    def writeInput(self) -> str:

        bCondStr = '*DFLUX'

        if self._amplitude:
            bCondStr += ', AMPLITUDE = {:s}'.format(self._amplitude.name)

        if self._timeDelay:
            bCondStr += ', TIMEDELAY = {:e}'.format(self._timeDelay)

        bCondStr += '\n'

        bfaces = self.getBoundaryFaces()

        for i in range(len(bfaces)):
            bCondStr += '{:d}, S{:d},{:e}\n'.format(bfaces[i, 0], bfaces[i, 1], self._flux)

        return bCondStr


class Radiation(BoundaryCondition):
    """
    The radiation boundary condition applies Black-body radiation using the Stefan-Boltzmann Law,
    :math:`q_{rad} = \\epsilon \\sigma_b\\left(T-T_{amb}\\right)^4`, which is imposed on the faces of
    boundaries elements (correctly ordered according to Calculix's requirements). Ensure that the Stefan-Boltzmann constant :math:
    `\\sigma_b`, has consistent units, which is set in the :attr:`~pyccx.analysis.Simulation.SIGMAB`.
    This BC may be used in thermal and coupled thermo-mechanical analyses.
    """

    def __init__(self, target, epsilon: float = 1.0, TAmbient: float = 0.0,
                 name: str = None, amplitude: Amplitude = None, timeDelay: float = None):

        self.T_amb = TAmbient
        self._epsilon = epsilon

        if not isinstance(target, SurfaceSet):
            raise ValueError('A SurfaceSet must be used for a Radiation Boundary Condition')

        super().__init__(name, target, amplitude, timeDelay)

    def type(self) -> BoundaryConditionType:
        return BoundaryConditionType.THERMAL

    @property
    def emmisivity(self) -> float:
        """
        The emmisivity value :math:`\\epsilon` used for the Radiation Boundary Condition
        """
        return self._epsilon

    @emmisivity.setter
    def emmisivity(self, val: float):
        self._epsilon = val

    @property
    def ambientTemperature(self) -> float:
        """
        The ambient temperature :math:`T_{amb}`. used for the Radiation Boundary Condition
        """
        return self.T_amb

    @ambientTemperature.setter
    def ambientTemperature(self, Tamb: float) -> None:
        self.T_amb = Tamb

    def writeInput(self) -> str:

        bCondStr = '*RADIATE'

        if self._amplitude:
            bCondStr += ', AMPLITUDE = {:s}'.format(self._amplitude.name)

        if self._timeDelay:
            bCondStr += ', TIMEDELAY = {:e}'.format(self._timeDelay)

        bCondStr += '\n'

        bfaces = self.getBoundaryFaces()

        for i in range(len(bfaces)):
            bCondStr += '{:d}, F{:d}, {:e}, {:e}\n'.format(bfaces[i, 0], bfaces[i, 1], self.T_amb, self._epsilon)

        return bCondStr


class Fixed(BoundaryCondition):
    """
    The fixed boundary condition removes or sets the DOF (e.g. displacement components, temperature) specifically on
    a Node Set. This BC may be used in thermal and coupled thermo-mechanical analyses provided the DOF is applicable to
    the analysis type.
    """

    def __init__(self, target: Any, dof: List[DOF] = [], values=None,
                 name: str = None, amplitude: Amplitude = None, timeDelay: float = None):

        if not isinstance(target, NodeSet):
            raise ValueError('The target for a Fixed Boundary Condition must be a NodeSet')

        # for d in dof:
        #     if not d in DOF:
        #         raise ValueError('Degree of freedom must be specified')

        self._dof = dof
        self._values = values

        super().__init__(name, target, amplitude, timeDelay)

    def type(self) -> BoundaryConditionType:
        return BoundaryConditionType.ANY

    @property
    def dof(self):
        """
        Degree of Freedoms to be fixed
        """
        return self._dof

    @dof.setter
    def dof(self, vals):
        self._dof = vals

    @property
    def values(self) -> Any:
        """
        Values to assign to the selected DOF to be fixed
        """
        return self._dof

    @values.setter
    def values(self, vals):
        self._values = vals

    def writeInput(self) -> str:

        bCondStr = '*BOUNDARY'

        if self._amplitude:
            bCondStr += ', AMPLITUDE = {:s}'.format(self._amplitude.name)

        if self._timeDelay:
            bCondStr += ', TIMEDELAY = {:e}'.format(self._timeDelay)

        bCondStr += '\n'

        nodesetName = self.getTargetName()

        if self._values and (len(self.dof) != len(self._values)):
            raise ValueError('DOF and Prescribed DOF must have a matching size')

        # 1-3 U, 4-6, rotational DOF, 11 = Temp
        for i in range(len(self._dof)):
            if self._values:
                # Inhomogeneous boundary conditions
                bCondStr += '{:s},{:d},, {:e}\n'.format(nodesetName, self._dof[i], self._values[i])
            else:
                # Fixed boundary condition
                bCondStr += '{:s},{:d}\n'.format(nodesetName, self._dof[i])

        return bCondStr


class Acceleration(BoundaryCondition):
    """
    The Acceleration Boundary Condition applies an acceleration term across a Volume (i.e. Element Set) during a structural
    analysis. This is provided as magnitude, direction of the acceleration on the body.
    """

    def __init__(self, target, dir = None, mag = 1.0,
                 name: str = None, amplitude: Amplitude = None, timeDelay: float = None):

        self._mag = 1.0

        if not isinstance(target, NodeSet) or not isinstance(target, ElementSet):
            raise ValueError('The target for an Acceleration BC should be a node or element set.')

        if dir:
            self.dir = np.asanyarray(dir)
        else:
            self.dir = np.array([0.0, 0.0, 1.0])

        super().__init__(name, target, amplitude, timeDelay)

    def type(self) -> BoundaryConditionType:
        return BoundaryConditionType.STRUCTURAL

    def setVector(self, v) -> None:
        """
        The acceleration of the body set by an Acceleration Vector

        :param v: The vector of the acceleration
        """
        from numpy import linalg
        mag = linalg.norm(v)
        self.dir = v / linalg.norm(v)
        self.magnitude = mag

    @property
    def magnitude(self) -> float:
        """
        The acceleration magnitude applied onto the body
        """
        return self._mag

    @magnitude.setter
    def magnitude(self, magVal: float) -> None:
        from numpy import linalg
        self._mag = magVal

    @property
    def direction(self) -> np.ndarray:
        """
        The acceleration direction (normalised vector)
        """
        return self.dir

    @direction.setter
    def direction(self, v: float) -> None:
        from numpy import linalg
        self.dir = v / linalg.norm(v)

    def writeInput(self) -> str:
        bCondStr = '*DLOAD'

        if self._amplitude:
            bCondStr += ', AMPLITUDE = {:s}'.format(self._amplitude.name)

        if self._timeDelay:
            bCondStr += ', TIMEDELAY = {:e}'.format(self._timeDelay)

        bCondStr += '\n'

        bCondStr += '{:s},GRAV,{:.5f}, {:e},{:e},{:e}\n'.format(self.target.name, self._mag, *self.dir)
        return bCondStr


class Pressure(BoundaryCondition):
    """
    The Pressure Boundary Condition applies a uniform pressure to faces across an element boundary.
    """

    def __init__(self, target, magnitude: float = 0.0,
                 name: str = None, amplitude: Amplitude = None, timeDelay: float = None):

        self._mag = magnitude

        if not isinstance(target, SurfaceSet):
            raise ValueError('A surface set must be assigned to a Pressure boundary condition.')

        super().__init__(name, target, amplitude, timeDelay)

    def type(self) -> BoundaryConditionType:
        return BoundaryConditionType.STRUCTURAL

    @property
    def magnitude(self) -> float:
        """
        The magnitude of pressure applied onto the surface
        """
        return self._mag

    @magnitude.setter
    def magnitude(self, magVal: float) -> None:
        self._mag = magVal

    def writeInput(self) -> str:

        bCondStr = '*DLOAD'

        if self._amplitude:
            bCondStr += ', AMPLITUDE = {:s}'.format(self._amplitude.name)

        if self._timeDelay:
            bCondStr += ', TIMEDELAY = {:e}'.format(self._timeDelay)

        bCondStr += '\n'

        bfaces = self.getBoundaryFaces()

        for i in range(len(bfaces)):
            bCondStr += '{:6d}, P{:d}, {:e}\n'.format(bfaces[i, 0], bfaces[i, 1], self._mag)

        return bCondStr


class SurfaceTraction(BoundaryCondition):
    """
    The SurfaceTraction Boundary Condition applies a force to faces across an element boundary.
    """

    def __init__(self, target):
        self.mag = 0.0
        self.dir = np.array([0.0, 0.0, 1.0])

        super().__init__(target)

    def type(self) -> BoundaryConditionType:
        return BoundaryConditionType.STRUCTURAL

    def setVector(self, v) -> None:
        """
        The applied force set by the vector

        :param v: The Force vector
        """
        from numpy import linalg
        mag = linalg.norm(v)
        self.dir = v / linalg.norm(v)
        self.mag = mag

    @property
    def magnitude(self) -> float:
        """
        The magnitude of force applied onto the surface
        """
        return self.mag

    @magnitude.setter
    def magnitude(self, magVal: float) -> None:
        self.mag = magVal

    @property
    def direction(self) -> np.ndarray:
        """
        The normalised vector of the force direction
        """
        return self.dir

    @direction.setter
    def direction(self, v: float) -> None:
        from numpy import linalg
        self.dir = v / linalg.norm(v)

    def writeInput(self) -> str:
        bCondStr = '*CLOAD\n'
        nodesetName = self.getTargetName()
        numNodes = len(self.target.nodes)

        for i in range(3):
            compMag = self.mag * self.dir[i] / numNodes
            bCondStr += '{:s},{:d},{:f}\n'.format(nodesetName, i + 1, compMag)

        return bCondStr


class Force(BoundaryCondition):
    """
    The Force Boundary applies a uniform force directly to nodes. This BC may be used in thermal and
    coupled thermo-mechanical analyses provided the DOF is applicable to the analysis type.
    """

    def __init__(self, target,
                 name: str = None, amplitude: Amplitude = None, timeDelay: float = None):
        self.mag = 0.0
        self.dir = np.array([0.0, 0.0, 1.0])

        super().__init__(name, target, amplitude, timeDelay)

    def type(self) -> BoundaryConditionType:
        return BoundaryConditionType.STRUCTURAL

    def setVector(self, v: np.ndarray) -> None:
        """
        The applied force set by the vector

        :param v: The Force vector
        """
        from numpy import linalg
        mag = linalg.norm(v)
        self.dir = v / linalg.norm(v)
        self.magnitude = mag

    @property
    def magnitude(self) -> float:
        """
        The magnitude of the force applied
        """
        return self.mag

    @magnitude.setter
    def magnitude(self, magVal: float) -> None:
        self.mag = magVal

    @property
    def direction(self) -> np.ndarray:
        """
        The normalised vector of the force direction
        """
        return self.dir

    @direction.setter
    def direction(self, v: float) -> None:
        from numpy import linalg
        self.dir = v / linalg.norm(v)

    def writeInput(self) -> str:
        bCondStr = '*CLOAD'

        if self._amplitude:
            bCondStr += ', AMPLITUDE = {:s}'.format(self._amplitude.name)

        if self._timeDelay:
            bCondStr += ', TIMEDELAY = {:e}'.format(self._timeDelay)

        bCondStr += '\n'

        nodesetName = self.getTargetName()

        for i in range(3):
            compMag = self.mag * self.dir[i]
            bCondStr += '{:s},{:d},{:f}\n'.format(nodesetName, i + 1, compMag)

        return bCondStr
