import pytest
import jax
import jax.numpy as jnp

from env.env import DroneEnvState, DroneEnvParams, DeliveryDrones


ACTION_LEFT = 0
ACTION_DOWN = 1
ACTION_RIGHT = 2
ACTION_UP = 3
ACTION_STAY = 4
OBJ_SKYSCRAPER = 2
OBJ_STATION = 3
OBJ_DROPZONE = 4
OBJ_PACKET = 5


##########
# FIXTURES
##########

@pytest.fixture
def single_drone_env():
    grid_size = (8, 8)
    n_drones = 1
    params = DroneEnvParams(n_drones=n_drones)
    air = jnp.zeros(grid_size, dtype=jnp.int32)
    air = air.at[3, 3].set(1)
    ground = jnp.zeros(grid_size, dtype=jnp.int8)
    carrying_package = jnp.zeros((n_drones,), dtype=jnp.bool)
    charge = jnp.array(n_drones * [100], dtype=jnp.int32)
    state = DroneEnvState(air=air, ground=ground, carrying_package=carrying_package, charge=charge)
    return state, params


@pytest.fixture
def dual_drone_env():
    grid_size = (8, 8)
    n_drones = 2
    params = DroneEnvParams(n_drones=n_drones)
    air = jnp.zeros(grid_size, dtype=jnp.int32)
    air = air.at[3, 1].set(1)
    air = air.at[3, 3].set(2)
    ground = jnp.zeros(grid_size, dtype=jnp.int8)
    carrying_package = jnp.zeros((n_drones,), dtype=jnp.bool)
    charge = jnp.array(n_drones * [100], dtype=jnp.int32)
    state = DroneEnvState(air=air, ground=ground, carrying_package=carrying_package, charge=charge)
    return state, params


@pytest.fixture
def drone_env_packages():
    grid_size = (8, 8)
    n_drones = 1
    params = DroneEnvParams(n_drones=n_drones)
    air = jnp.zeros(grid_size, dtype=jnp.int32)
    air = air.at[3, 3].set(1)
    ground = jnp.zeros(grid_size, dtype=jnp.int8)
    ground = ground.at[3, 4].set(OBJ_PACKET)   # package to the right
    ground = ground.at[3, 5].set(OBJ_DROPZONE)   # dropzone to the right
    carrying_package = jnp.zeros((n_drones,), dtype=jnp.bool)
    charge = jnp.array(n_drones * [100], dtype=jnp.int32)
    state = DroneEnvState(air=air, ground=ground, carrying_package=carrying_package, charge=charge)
    return state, params


@pytest.fixture
def drone_env_skyscrapers():
    grid_size = (8, 8)
    n_drones = 2
    params = DroneEnvParams(n_drones=n_drones)
    air = jnp.zeros(grid_size, dtype=jnp.int32)
    air = air.at[3, 0].set(1)
    air = air.at[3, 3].set(2)
    ground = jnp.zeros(grid_size, dtype=jnp.int8)
    ground = ground.at[3, 4].set(OBJ_SKYSCRAPER)   # skyscraper to the right
    carrying_package = jnp.zeros((n_drones,), dtype=jnp.bool)
    charge = jnp.array(n_drones * [100], dtype=jnp.int32)
    state = DroneEnvState(air=air, ground=ground, carrying_package=carrying_package, charge=charge)
    return state, params

@pytest.fixture
def drone_env_charge():
    grid_size = (8, 8)
    n_drones = 3
    params = DroneEnvParams(n_drones=n_drones)
    air = jnp.zeros(grid_size, dtype=jnp.int32)
    air = air.at[3, 0].set(1)
    air = air.at[3, 3].set(2)
    air = air.at[0, 0].set(3)
    ground = jnp.zeros(grid_size, dtype=jnp.int8)
    ground = ground.at[3, 4].set(OBJ_STATION)   # charging station to the right
    carrying_package = jnp.zeros((n_drones,), dtype=jnp.bool)
    charge = jnp.array([50, 50, 10], dtype=jnp.int32)
    state = DroneEnvState(air=air, ground=ground, carrying_package=carrying_package, charge=charge)
    return state, params


@pytest.fixture
def drone_respawn_beahviour():
    grid_size = (8, 8)
    n_drones = 2
    params = DroneEnvParams(n_drones=n_drones)
    air = jnp.zeros(grid_size, dtype=jnp.int32)
    air = air.at[3, 1].set(1)
    air = air.at[3, 3].set(2)
    ground = jnp.zeros(grid_size, dtype=jnp.int8)
    ground = ground.at[4, 4].set(OBJ_PACKET)  # drone 1 will respawn here after collision
    carrying_package = jnp.zeros((n_drones,), dtype=jnp.bool)
    charge = jnp.array(n_drones * [100], dtype=jnp.int32)
    state = DroneEnvState(air=air, ground=ground, carrying_package=carrying_package, charge=charge)
    return state, params


@pytest.fixture
def simple_params():
    return DroneEnvParams(n_drones=3, packets_factor=3, dropzones_factor=2, stations_factor=2, skyscrapers_factor=3)


#######
# TESTS
#######

@pytest.mark.focus
def test_reset(simple_params):
    env = DeliveryDrones()
    rng = jax.random.PRNGKey(0)
    state = env.reset(rng, simple_params, grid_size=8)
    assert jnp.sum(state.air) == 6  # 1 + 2 + 3 (player IDs)
    assert jnp.sum(state.air > 0) == 3  # 3 players
    num_packets = simple_params.packets_factor * simple_params.n_drones
    num_dropzones = simple_params.dropzones_factor * simple_params.n_drones
    num_stations = simple_params.stations_factor * simple_params.n_drones
    num_skyscrapers = simple_params.skyscrapers_factor * simple_params.n_drones
    assert jnp.sum(state.ground == OBJ_PACKET) == num_packets - 2  # 2 packages have been picked up
    assert jnp.sum(state.ground == OBJ_STATION) == num_stations
    assert jnp.sum(state.ground == OBJ_SKYSCRAPER) == num_skyscrapers
    assert jnp.sum(state.ground == OBJ_DROPZONE) == num_dropzones
    assert jnp.sum(state.charge) == 100 * simple_params.n_drones
    assert state.carrying_package[0]
    assert state.carrying_package[1]
    assert not state.carrying_package[2]


def test_respawn(drone_respawn_beahviour):
    state, params = drone_respawn_beahviour
    env = DeliveryDrones()
    rng = jax.random.PRNGKey(0)
    actions = jnp.array([ACTION_RIGHT, ACTION_LEFT], dtype=jnp.int32)  # make them crash!
    assert jnp.sum(state.ground == OBJ_PACKET) == 1  # we have one package
    assert jnp.sum(state.carrying_package) == 0  # no one is carrying a package
    state_out, rewards, dones = env.step(rng, state, actions, params)
    assert jnp.sum(dones) == 2  # drones crashed
    assert jnp.sum(state_out.ground == OBJ_PACKET) == 0  # package was picked up
    assert jnp.sum(state_out.carrying_package) == 1  # no one is carrying a package
    assert jnp.sum(rewards) == -2  # we don't give a reward for this


def test_charge(drone_env_charge):
    state, params = drone_env_charge
    env = DeliveryDrones()
    rng = jax.random.PRNGKey(0)
    actions = jnp.array([ACTION_RIGHT, ACTION_RIGHT, ACTION_RIGHT], dtype=jnp.int32)
    state_out, rewards, dones = env.step(rng, state, actions, params)
    assert state_out.charge[0] == max(50 - params.discharge, 0)
    assert state_out.charge[1] == min(50 + params.charge, 100)
    assert state_out.charge[2] == 100
    assert dones[2]
    assert rewards[0] == 0
    assert rewards[1] == params.charge_reward
    assert rewards[2] == params.crash_reward
    actions = jnp.array([ACTION_RIGHT, ACTION_STAY, ACTION_RIGHT], dtype=jnp.int32)
    state_out, rewards, dones = env.step(rng, state_out, actions, params)
    assert state_out.charge[0] == max(50 - 2 * params.discharge, 0)
    assert state_out.charge[1] == min(50 + 2 * params.charge, 100)
    assert state_out.charge[2] == max(100 - params.discharge, 0)
    actions = jnp.array([ACTION_RIGHT, ACTION_STAY, ACTION_RIGHT], dtype=jnp.int32)
    state_out, rewards, dones = env.step(rng, state_out, actions, params)
    assert state_out.charge[0] == max(50 - 3 * params.discharge, 0)
    assert state_out.charge[1] == min(50 + 3 * params.charge, 100)
    assert state_out.charge[2] == max(100 - 2 * params.discharge, 0)
    actions = jnp.array([ACTION_RIGHT, ACTION_DOWN, ACTION_RIGHT], dtype=jnp.int32)
    state_out, rewards, dones = env.step(rng, state_out, actions, params)
    assert state_out.charge[0] == max(50 - 3 * params.discharge + params.charge, 0)
    assert state_out.charge[1] == min(50 + 3 * params.charge, 100) - params.discharge
    assert state_out.charge[2] == max(100 - 3 * params.discharge, 0)


def test_skyscrapers(drone_env_skyscrapers):
    state, params = drone_env_skyscrapers
    env = DeliveryDrones()
    rng = jax.random.PRNGKey(0)
    actions = jnp.array([ACTION_LEFT, ACTION_RIGHT], dtype=jnp.int32)
    state_out, rewards, dones = env.step(rng, state, actions, params)
    assert jnp.sum(dones) == 2  # both died
    assert jnp.sum(state_out.air > 0) == 2  # both drones respawned
    assert jnp.sum(rewards) == params.crash_reward * 2
    assert state_out.ground[3, 4] == OBJ_SKYSCRAPER  # skyscraper hasn't moved


def test_packages(drone_env_packages):
    state, params = drone_env_packages
    env = DeliveryDrones()
    rng = jax.random.PRNGKey(0)
    actions = jnp.array([ACTION_RIGHT], dtype=jnp.int32)
    state_out, rewards, dones = env.step(rng, state, actions, params)
    # check that package has been picked up
    assert state_out.carrying_package[0]
    assert state_out.air[3, 4] == 1
    assert state_out.ground[3, 4] == 0
    assert rewards[0] == params.pickup_reward
    state_out2, rewards, dones = env.step(rng, state_out, actions, params)
    assert not state_out2.carrying_package[0]
    assert state_out2.air[3, 5] == 1
    assert rewards[0] == params.pickup_reward + params.delivery_reward
    assert state_out.ground[3, 5] == OBJ_DROPZONE
    assert jnp.sum(state_out.ground > 0) == 1


def test_collisions(dual_drone_env):
    state, params = dual_drone_env
    env = DeliveryDrones()
    rng = jax.random.PRNGKey(0)
    actions = jnp.array([ACTION_RIGHT, ACTION_LEFT], dtype=jnp.int32)
    state_out, rewards, dones = env.step(rng, state, actions, params)
    assert jnp.sum(dones) == 2 # both should be done
    assert jnp.sum(state_out.air > 0) == 2 # both should be done
    assert jnp.sum(state_out.charge) == 200 # both should again have full charge after respawn


def test_single_movements(single_drone_env):
    state, params = single_drone_env
    env = DeliveryDrones()
    rng = jax.random.PRNGKey(0)
    for action, (y, x) in zip([0, 1, 2, 3, 4], [(3, 2), (4, 3), (3, 4), (2, 3), (3, 3)]):
        actions = jnp.array([action], dtype=jnp.int32)
        state_out, rewards, dones = env.step(rng, state, actions, params)
        assert jnp.sum(state_out.air) == 1
        assert state_out.air[y, x] == 1
