import numpy as np
from enum import Enum
from collections import defaultdict, OrderedDict
import gym.spaces as spaces
from gym import Env, ObservationWrapper, RewardWrapper
from gym.utils import seeding
import os
import string

class Action(Enum):
    LEFT = 0
    DOWN = 1
    RIGHT = 2
    UP = 3
    STAY = 4

class Dropzone():
    def __init__(self, index):
        self.index = index
        
    def __repr__(self):
        return 'Z{}'.format(self.index)

class Packet():
    def __init__(self, index):
        self.index = index
        
    def __repr__(self):
        return 'P{}'.format(self.index)

class Drone():
    def __init__(self, index):
        self.index = index
        self.packet = None
        
    def __repr__(self):
        return 'D{}'.format(self.index)
        
class Grid():
    def __init__(self, shape):
        self.shape = shape
        self.grid = np.full(shape, fill_value=None, dtype=np.object)
    
    def __getitem__(self, key):
        return self.grid[key]
    
    def __setitem__(self, key, value):
        self.grid[key] = value
    
    def get_objects_positions(self, objs):
        results = []
        for y in range(self.shape[0]):
            for x in range(self.shape[1]):
                for obj in objs:
                    if self.grid[y, x] == obj:
                        results.append((obj, (y, x)))
        return results
    
    def get_objects(self, object_type, positions=None, zip_results=False):
        """Filter objects matching criteria"""
        objects_mask = np.vectorize(lambda tile: isinstance(tile, object_type))(self.grid)

        if positions is not None:
            position_mask = np.full(shape=self.shape, fill_value=False)
            for x, y in filter(self.is_inside, positions):
                position_mask[x, y] = True
            objects_mask = np.logical_and(objects_mask, position_mask)
        
        if zip_results:
            # Make things much easier in for loops ".. for obj, pos in get_objects(..)"
            return zip(self[objects_mask], zip(*np.nonzero(objects_mask)))
        else:
            # Numpy like format: objects, (pos_x, pos_y)
            return self[objects_mask], np.nonzero(objects_mask)
    
    def spawn(self, objects):
        """Spawn objects on empty tiles. Return positions."""
        flat_idxs = np.random.choice(np.flatnonzero(self.grid == None), size=len(objects), replace=False)
        idxs = np.unravel_index(flat_idxs, self.shape)
        self.grid[idxs] = objects
        return idxs
    
    def is_inside(self, position):
        try:
            np.ravel_multi_index(multi_index=position, dims=self.shape, mode='raise')
            return True
        except ValueError:
            return False
        
class DeliveryDrones(Env):
    # OpenAI Gym environment fields
    metadata = {'render.modes': ['ainsi'], 'drone_density': 0.05}
    
    def __init__(self, n):
        # Define size of the environment
        self.n_drones = n
        self.side_size = int(np.ceil(np.sqrt(self.n_drones/self.metadata['drone_density'])))
        self.shape = (self.side_size, self.side_size)
        
        # Define spaces
        self.action_space = spaces.Discrete(len(Action))
        
    def step(self, actions):
        # By default, drones get a reward of zero
        rewards = {index: 0 for index in actions.keys()}
        
        # Do some air navigation for drones based on actions
        new_positions = defaultdict(list)
        air_respawns = []
        ground_respawns = []

        for drone, position in self.air.get_objects(Drone, zip_results=True):
            # Drones actually teleports, temporarily remove them from the air
            self.air[position] = None
            
            # Get action and drone position
            action = Action.STAY if drone.index not in actions else Action(actions[drone.index])
            if action is Action.LEFT:
                new_position = position[0], position[1]-1
            elif action is Action.DOWN:
                new_position = position[0]+1, position[1]
            elif action is Action.RIGHT:
                new_position = position[0], position[1]+1
            elif action is Action.UP:
                new_position = position[0]-1, position[1]
            else:
                new_position = position
            
            # Drone plans to move to a valid place, save it
            if(self.air.is_inside(new_position)):
                new_positions[new_position].append(drone)
                  
            # Drone plans to move outside the grid -> crash
            else:
                # Drone gets a negative reward and respawns
                rewards[drone.index] = -1
                air_respawns.append(drone)
                
                # Delivery content is lost with drone crash (!)
                if drone.packet is not None:
                    ground_respawns.append(drone.packet)
                    drone.packet = None
                    
        # Further air navigation for drones that didn't went outside the grid
        for position, drones in new_positions.items():
            # Is there a collision?
            if len(drones) > 1:
                # Drones get a negative reward and have to respawn
                rewards.update({drone.index: -1 for drone in drones})
                air_respawns.extend(drones)
                
                # Delivery content is lost with drones crash (!)
                ground_respawns.extend([drone.packet for drone in drones if drone.packet is not None])
                for drone in drones:
                    drone.packet = None
                continue
                
            # If not, move the drone and check what's on the ground
            drone = drones[0]
            self.air[position] = drone

            # Is there a packet?
            if isinstance(self.ground[position], Packet):
                # Does the drone already have a packet?
                if drone.packet is not None:
                    # Then switch the packets
                    drone.packet, self.ground[position] = (self.ground[position], drone.packet)
                    
                # Otherwise, just take the packet
                else:
                    drone.packet = self.ground[position]
                    self.ground[position] = None
                    
            # A drop zone?
            elif isinstance(self.ground[position], Dropzone):
                dropzone = self.ground[position]
                
                # Did we just delivered a packet?
                if drone.packet is not None:
                    if drone.packet.index == dropzone.index:
                        # Pay the drone for the delivery
                        rewards[drone.index] = 1
                        
                        # Create new delivery
                        ground_respawns.extend([drone.packet, dropzone])
                        self.ground[position] = None
                        drone.packet = None
                        
        # Respawn objects
        self.ground.spawn(ground_respawns)
        self._pick_packets_after_respawn(self.air.spawn(air_respawns))
        
        # Episode ends when drone respawns
        dones = {index: False for index in actions.keys()}
        for drone in air_respawns:
            dones[drone.index] = True
        
        # Return new states, rewards, done and other infos
        info = {'air_respawns': air_respawns, 'ground_respawns': ground_respawns}
        return self._get_grids(), rewards, dones, info
        
    def reset(self):
        # Create grids
        self.air = Grid(shape=self.shape)
        self.ground = Grid(shape=self.shape)
        
        # Create
        # Note: use 1-indexing to simplify state encoding where 0 denotes "absence"
        self.packets = [Packet(index) for index in range(1, self.n_drones+1)]
        self.dropzones = [Dropzone(index) for index in range(1, self.n_drones+1)]
        self.drones = [Drone(index) for index in range(1, self.n_drones+1)]
        
        # Spawn objects
        self.ground.spawn(self.packets)
        self.ground.spawn(self.dropzones)
        self._pick_packets_after_respawn(self.air.spawn(self.drones))
        
        return self._get_grids()
        
    def render(self, mode='ainsi'):
        if mode == 'ainsi':
            return self.__str__()
        else:
            super().render(mode=mode)
    
    def _get_grids(self):
        return {'ground': self.ground, 'air': self.air}
        
    def _pick_packets_after_respawn(self, positions):
        for y, x in zip(*positions):
            if isinstance(self.ground[y, x], Packet):
                self.air[y, x].packet = self.ground[y, x]
                self.ground[y, x] = None
    
    def __str__(self):
        # Generate aribitrary names for deliveries
        pacname = lambda index: string.ascii_lowercase[(index-1)%len(string.ascii_lowercase)]
        dropname = lambda index: string.ascii_uppercase[(index-1)%len(string.ascii_uppercase)]

        # Convert air/ground tiles to text
        def tiles_to_char(ground_tile, air_tile):
            # Air is empty
            if air_tile is None:
                if ground_tile is None:
                    return ''
                elif isinstance(ground_tile, Packet):
                    return '{}'.format(pacname(ground_tile.index))
                elif isinstance(ground_tile, Dropzone):
                    return '({})'.format(dropname(ground_tile.index))
                
            # Air has a drone
            elif isinstance(air_tile, Drone):
                if air_tile.packet is None:
                    return '{}'.format(air_tile.index)
                else:
                    return '{}<{}'.format(
                        air_tile.index,
                        pacname(air_tile.packet.index))
            return '?'
                
        grid_char = np.vectorize(tiles_to_char)(self.ground.grid, self.air.grid)
        
        # Assemble tiles into a grid
        tile_size = max(3, max([len(c) for c in grid_char.flatten()]))
        row_sep = ('+' + '-' * tile_size) * self.shape[1] + '+'
        lines = [row_sep]
        for i, row in enumerate(grid_char):
            line_str = '|'
            for j, tile_str in enumerate(row):
                tile_str = ' ' * ((tile_size-len(tile_str)) // 2) + tile_str
                tile_str = tile_str.ljust(tile_size, ' ')
                line_str += tile_str + '|'
            lines.append(line_str)
            lines.append(row_sep)
            
        return '\n'.join(lines)
    
    def format_action(self, i):
        return Action(i).name
        
class CompassQTable(ObservationWrapper):
    """
    Observation wrapper for Q-table based algorithms
    The state gives campass direction (W/SW/S/SE/E/NE/N/NW)
    to nearest packet or dropzone to deliver.
    """
    def __init__(self, env):
        # Initialize wrapper with observation space
        super().__init__(env)
        self.observation_space = spaces.Discrete(8)
        self.cardinals = ['W', 'SW', 'S', 'SE', 'E', 'NE', 'N', 'NW']
        
    def observation(self, _):
        # Return state for each drone
        return {
            drone.index: self.get_drone_state(drone, *position)
            for drone, position in self.env.air.get_objects(Drone, zip_results=True)}
        
    def get_drone_state(self, drone, drone_y, drone_x):        
        # Target direction: nearest packet or associated dropzone
        targets, positions = self.env.ground.get_objects(Packet if drone.packet is None else Dropzone)
        if drone.packet is None:
            l1_distances = np.abs(positions[0] - drone_y) + np.abs(positions[1] - drone_x)
            target_idx = l1_distances.argmin() # Index of the nearest packet
        else:
            target_idx = [d.index for d in targets].index(drone.packet.index)
            
         # Direction to go to reduce distance to the packet
        target_y, target_x = positions[0][target_idx], positions[1][target_idx]
        west, south = (drone_x - target_x), (target_y - drone_y)
        return np.argmax([
            (west >  0) and (south == 0),
            (west >  0) and (south >  0),
            (west == 0) and (south >  0),
            (west <  0) and (south >  0),
            (west <  0) and (south == 0),
            (west <  0) and (south <  0),
            (west == 0) and (south <  0),
            (west >  0) and (south <  0)
        ])
    
    def format_state(self, s):
        return self.cardinals[s]
    
class LidarCompassQTable(CompassQTable):
    """
    Observation wrapper for Q-table based algorithms 
    The states indicate campass direction and lidar information
    """
    def __init__(self, env):
        # Initialize wrapper with observation space
        super().__init__(env)
        self.observation_space = spaces.Dict([
            ('target', self.observation_space),
            ('lidar', spaces.MultiBinary(8))
        ])
        target_cardinality = self.observation_space['target'].n
        lidar_cardinality = 2**self.observation_space['lidar'].n
        self.observation_space.n = target_cardinality*lidar_cardinality
        self.lidar_positions = {
            'W' : [(0, -1), (0, -2)],
            'SW': [(1, -1)],
            'S' : [(1, 0), (2, 0)],
            'SE': [(1, 1)],
            'E' : [(0, 1), (0, 2)],
            'NE': [(-1, 1)],
            'N' : [(-1, 0), (-2, 0)],
            'NW': [(-1, -1)]
        }
        
    def get_drone_state(self, drone, drone_y, drone_x):
        # Get target and  direction
        target = super().get_drone_state(drone, drone_y, drone_x)
        lidar = [self.sense_obstacles(
            self.lidar_positions[c], drone_y, drone_x) for c in self.cardinals]
        
        # Use the same ordering as obs. space to avoid any issues
        return OrderedDict([('target', target), ('lidar', lidar)])
    
    # Lidar information
    def sense_obstacles(self, positions, drone_y=0, drone_x=0):
        for y, x in positions:
            y, x = (y + drone_y), (x + drone_x)
            if not self.env.air.is_inside([y, x]):
                return 1
            if isinstance(self.env.air[y, x], Drone):
                return 1
        return 0
    
    def format_state(self, state):
        # Find directions with positive lidar signal
        positive_lidar_signals = np.nonzero(state['lidar'])[0]
        lidar_cardinals = np.take(self.cardinals, positive_lidar_signals)
        
        return 'target: {}, lidar: {}'.format(
            self.cardinals[state['target']], ', '.join(lidar_cardinals))

class GridView(ObservationWrapper):
    """
    Observation wrapper: (N, N, 3) numerical arrays with location of
    (1) drones      marked with    drone index 1..i / 0 otherwise
    (2) packets     marked with delivery index 1..i / 0 otherwise
    (3) dropzones   marked with delivery index 1..i / 0 otherwise
    Where N is the size of the environment grid, i the number of drones
    """
    def __init__(self, env):
        # Initialize wrapper with observation space
        super().__init__(env)
        self.observation_space = spaces.Box(
            low=1, high=self.n_drones, shape=self.env.shape+(3,), dtype=np.int)
        
    def observation(self, _):
        # Create grid and get objects
        grid = np.zeros(shape=self.env.shape + (3,))

        # Drones (and their packets)
        for drone, (y, x) in self.env.air.get_objects(Drone, zip_results=True):
            grid[y, x, 0] = drone.index
            if drone.packet is not None:
                grid[y, x, 1] = drone.packet.index

        # Packets
        for packet, (y, x) in self.env.ground.get_objects(Packet, zip_results=True):
            grid[y, x, 1] = packet.index

        # Dropzones
        for dropzone, (y, x) in self.env.ground.get_objects(Dropzone, zip_results=True):
            grid[y, x, 2] = dropzone.index
            
        return {index: grid for index in range(1, self.env.n_drones+1)}
    
class BinaryGridView(GridView):
    """
    Observation wrapper
    """
    def __init__(self, env):
        # TODO
        pass
        
    def observation(self, _):
        # TODO
        pass
