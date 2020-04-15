"""
This file is part of nucypher.

nucypher is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

nucypher is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with nucypher.  If not, see <https://www.gnu.org/licenses/>.
"""


from decimal import Decimal, localcontext
from math import log
from typing import Tuple

from nucypher.blockchain.eth.agents import ContractAgency, NucypherTokenAgent, StakingEscrowAgent, AdjudicatorAgent, \
    WorkLockAgent
from nucypher.blockchain.eth.registry import BaseContractRegistry
from nucypher.blockchain.eth.token import NU

LOG2 = Decimal(log(2))


class BaseEconomics:
    """
    A representation of a contract deployment set's constructor parameters, and the calculations
    used to generate those values from high-level human-understandable parameters.

    --------------------------

    Formula for staking in one period:
    (totalSupply - currentSupply) * (lockedValue / totalLockedValue) * (k1 + allLockedPeriods) / k2

    K2 - Staking coefficient
    K1 - Locked periods coefficient

    if allLockedPeriods > maximum_rewarded_periods then allLockedPeriods = maximum_rewarded_periods
    kappa * log(2) / halving_delay === (k1 + allLockedPeriods) / k2

    """

    # Token Denomination
    __token_decimals = 18
    nunits_per_token = 10 ** __token_decimals  # Smallest unit designation

    # Period Definition
    _default_hours_per_period = 24

    # Time Constraints
    _default_minimum_worker_periods = 2
    _default_minimum_locked_periods = 30  # 720 Hours minimum

    # Value Constraints
    _default_minimum_allowed_locked = NU(15_000, 'NU').to_nunits()
    _default_maximum_allowed_locked = NU(4_000_000, 'NU').to_nunits()

    # Slashing parameters
    HASH_ALGORITHM_KECCAK256 = 0
    HASH_ALGORITHM_SHA256 = 1
    HASH_ALGORITHM_RIPEMD160 = 2

    # Adjudicator
    _default_hash_algorithm = HASH_ALGORITHM_SHA256
    _default_base_penalty = 100
    _default_penalty_history_coefficient = 10
    _default_percentage_penalty_coefficient = 8
    _default_reward_coefficient = 2

    # Worklock
    _default_worklock_supply: int = NotImplemented
    _default_bidding_start_date: int = NotImplemented
    _default_bidding_end_date: int = NotImplemented
    _default_cancellation_end_date: int = NotImplemented
    _default_worklock_boosting_refund_rate: int = NotImplemented
    _default_worklock_commitment_duration: int = NotImplemented
    _default_worklock_min_allowed_bid: int = NotImplemented

    def __init__(self,

                 # StakingEscrow
                 initial_supply: int,
                 first_phase_supply: int,
                 total_supply: int,
                 first_phase_stable_issuance: int,
                 second_phase_coefficient: int,
                 locking_duration_coefficient_1: int,
                 locking_duration_coefficient_2: int,
                 maximum_rewarded_periods: int,
                 hours_per_period: int = _default_hours_per_period,
                 minimum_locked_periods: int = _default_minimum_locked_periods,
                 minimum_allowed_locked: int = _default_minimum_allowed_locked,
                 maximum_allowed_locked: int = _default_maximum_allowed_locked,
                 minimum_worker_periods: int = _default_minimum_worker_periods,

                 # Adjudicator
                 hash_algorithm: int = _default_hash_algorithm,
                 base_penalty: int = _default_base_penalty,
                 penalty_history_coefficient: int = _default_penalty_history_coefficient,
                 percentage_penalty_coefficient: int = _default_percentage_penalty_coefficient,
                 reward_coefficient: int = _default_reward_coefficient,

                 # WorkLock
                 worklock_supply: int = _default_worklock_supply,
                 bidding_start_date: int = _default_bidding_start_date,
                 bidding_end_date: int = _default_bidding_end_date,
                 cancellation_end_date: int = _default_cancellation_end_date,
                 worklock_boosting_refund_rate: int = _default_worklock_boosting_refund_rate,
                 worklock_commitment_duration: int = _default_worklock_commitment_duration,
                 worklock_min_allowed_bid: int = _default_worklock_min_allowed_bid):

        """
        :param initial_supply: Number of tokens in circulating supply at t=0
        :param first_phase_supply: Number of tokens in circulating supply at phase switch (variable t)
        :param total_supply: Tokens at t=8
        :param first_phase_stable_issuance: Maximum number of tokens issued per period in first phase
        :param second_phase_coefficient: K2
        :param locking_duration_coefficient_1: K1
        :param locking_duration_coefficient_2: K3
        :param maximum_rewarded_periods: Max periods that will be additionally rewarded
        :param hours_per_period: Hours in single period
        :param minimum_locked_periods: Min amount of periods during which tokens can be locked
        :param minimum_allowed_locked: Min amount of tokens that can be locked
        :param maximum_allowed_locked: Max amount of tokens that can be locked
        :param minimum_worker_periods: Min amount of periods while a worker can't be changed

        :param hash_algorithm: Hashing algorithm
        :param base_penalty: Base for the penalty calculation
        :param penalty_history_coefficient: Coefficient for calculating the penalty depending on the history
        :param percentage_penalty_coefficient: Coefficient for calculating the percentage penalty
        :param reward_coefficient: Coefficient for calculating the reward
        """

        #
        # WorkLock
        #

        self.bidding_start_date = bidding_start_date
        self.bidding_end_date = bidding_end_date
        self.cancellation_end_date = cancellation_end_date
        self.worklock_supply = worklock_supply
        self.worklock_boosting_refund_rate = worklock_boosting_refund_rate
        self.worklock_commitment_duration = worklock_commitment_duration
        self.worklock_min_allowed_bid = worklock_min_allowed_bid

        #
        # NucypherToken & Staking Escrow
        #

        self.initial_supply = initial_supply
        # Remaining / Reward Supply - Escrow Parameter
        self.reward_supply = total_supply - initial_supply
        self.total_supply = total_supply
        self.first_phase_supply = first_phase_supply
        self.first_phase_stable_issuance = first_phase_stable_issuance
        self.second_phase_coefficient = second_phase_coefficient
        self.locking_duration_coefficient_1 = locking_duration_coefficient_1
        self.locking_duration_coefficient_2 = locking_duration_coefficient_2
        self.maximum_rewarded_periods = maximum_rewarded_periods
        self.hours_per_period = hours_per_period
        self.minimum_locked_periods = minimum_locked_periods
        self.minimum_allowed_locked = minimum_allowed_locked
        self.maximum_allowed_locked = maximum_allowed_locked
        self.minimum_worker_periods = minimum_worker_periods
        self.seconds_per_period = hours_per_period * 60 * 60  # Seconds in single period

        #
        # Adjudicator
        #

        self.hash_algorithm = hash_algorithm
        self.base_penalty = base_penalty
        self.penalty_history_coefficient = penalty_history_coefficient
        self.percentage_penalty_coefficient = percentage_penalty_coefficient
        self.reward_coefficient = reward_coefficient

    @property
    def erc20_initial_supply(self) -> int:
        return int(self.initial_supply)

    @property
    def erc20_reward_supply(self) -> int:
        return int(self.reward_supply)

    @property
    def erc20_total_supply(self) -> int:
        return int(self.total_supply)

    @property
    def staking_deployment_parameters(self) -> Tuple[int, ...]:
        """Cast coefficient attributes to uint256 compatible type for solidity+EVM"""
        deploy_parameters = (

            # Period
            self.hours_per_period,                  # Hours in single period

            # Coefficients
            self.second_phase_coefficient,          # Second phase coefficient (k2)
            self.locking_duration_coefficient_1,    # Numerator of he locking duration coefficient (k1)
            self.locking_duration_coefficient_2,    # Denominator of the locking duration coefficient (k3)
            self.maximum_rewarded_periods,          # Max periods that will be additionally rewarded (awarded_periods)
            self.first_phase_supply,                # Total supply for the first phase
            self.first_phase_stable_issuance,       # Max possible reward for one period for all stakers in the first phase

            # Constraints
            self.minimum_locked_periods,            # Min amount of periods during which tokens can be locked
            self.minimum_allowed_locked,            # Min amount of tokens that can be locked
            self.maximum_allowed_locked,            # Max amount of tokens that can be locked
            self.minimum_worker_periods             # Min amount of periods while a worker can't be changed
        )
        return tuple(map(int, deploy_parameters))

    @property
    def slashing_deployment_parameters(self) -> Tuple[int, ...]:
        """Cast coefficient attributes to uint256 compatible type for solidity+EVM"""
        deployment_parameters = [
            self.hash_algorithm,
            self.base_penalty,
            self.penalty_history_coefficient,
            self.percentage_penalty_coefficient,
            self.reward_coefficient
        ]
        return tuple(map(int, deployment_parameters))

    @property
    def worklock_deployment_parameters(self):
        """
        0 token - Token contract
        1 escrow -  Staking Escrow contract
        ...
        2 startBidDate - Timestamp when bidding starts
        3 endBidDate - Timestamp when bidding will end
        4 endCancellationDate - Timestamp when cancellation window will end
        5 boostingRefund - Coefficient to boost refund ETH
        6 stakingPeriods - Duration of tokens locking
        7 minAllowedBid - Minimum allowed ETH amount for bidding
        """
        deployment_parameters = [self.bidding_start_date,
                                 self.bidding_end_date,
                                 self.cancellation_end_date,
                                 self.worklock_boosting_refund_rate,
                                 self.worklock_commitment_duration,
                                 self.worklock_min_allowed_bid]
        return tuple(map(int, deployment_parameters))

    @property
    def bidding_duration(self) -> int:
        """Returns the total bidding window duration in seconds."""
        return self.bidding_end_date - self.bidding_start_date

    @property
    def cancellation_window_duration(self) -> int:
        """Returns the total cancellation window duration in seconds."""
        return self.cancellation_end_date - self.bidding_end_date


class StandardTokenEconomics(BaseEconomics):
    """
    --------------------------

    Formula for staking in one period:
    (totalSupply - currentSupply) * (lockedValue / totalLockedValue) * (k1 + allLockedPeriods) / k2

    K2 - Staking coefficient
    K1 - Locked periods coefficient

    if allLockedPeriods > maximum_rewarded_periods then allLockedPeriods = maximum_rewarded_periods
    kappa * log(2) / halving_delay === (k1 + allLockedPeriods) / k2

    ...but also...

    kappa = small_stake_multiplier + (1 - small_stake_multiplier) * min(T, T1) / T1
    where allLockedPeriods == min(T, T1)

    --------------------------

    Academic Reference:

    NuCypher: Mining & Staking Economics - Michael Egorov, MacLane Wilkison, NuCypher
    <https://github.com/nucypher/mining-paper/blob/master/mining-paper.pdf>

    """

    # Decimal
    _precision = 28

    # Supply
    __default_initial_supply = NU(int(1_000_000_000), 'NU').to_nunits()
    __default_first_phase_supply = NU(int(1_829_579_800), 'NU').to_nunits()
    __default_issuance = NU(int(365_915_960), 'NU').to_nunits()

    __default_token_halving = 2      # years
    __default_reward_saturation = 1  # years
    __default_small_stake_multiplier = Decimal(0.5)

    def __init__(self,
                 initial_supply: int = __default_initial_supply,
                 first_phase_supply: int = __default_first_phase_supply,
                 stable_issuance: int = __default_issuance,
                 halving_delay: int = __default_token_halving,
                 reward_saturation: int = __default_reward_saturation,
                 small_stake_multiplier: Decimal = __default_small_stake_multiplier,
                 **kwargs):
        """
        :param initial_supply: Tokens at t=0
        :param initial_supply: Number of tokens in circulating supply at t=0
        ;param first_phase_supply: Number of tokens in circulating supply at phase switch (variable t)
        :param halving_delay: Time for issuance to halve in years (in second phase only)
        :param reward_saturation: "saturation" time - if staking is longer than T_sat, the reward doesn't get any higher
        :param small_stake_multiplier: Fraction of maximum reward paid to those who are about to unlock tokens
        """

        #
        # Calculated
        #

        with localcontext() as ctx:
            ctx.prec = self._precision

            initial_supply = Decimal(initial_supply)

            first_phase_supply = Decimal(first_phase_supply)

            # TODO finish this
            # ERC20 Token parameter (See Equation 4 in Mining paper)
            total_supply = initial_supply + first_phase_supply + stable_issuance * halving_delay / LOG2

            # Awarded periods- Escrow parameter
            maximum_rewarded_periods = reward_saturation * 365

            # k3 - Escrow parameter
            locking_duration_coefficient_2 = maximum_rewarded_periods / (1 - small_stake_multiplier)

            # k1 - Escrow parameter
            locking_duration_coefficient_1 = locking_duration_coefficient_2 * small_stake_multiplier

            # k2 - Escrow parameter
            second_phase_coefficient = 365 * halving_delay / LOG2

            first_phase_stable_issuance = stable_issuance // 365

        #
        # Injected
        #

        self.token_halving = halving_delay
        self.token_saturation = reward_saturation
        self.small_stake_multiplier = small_stake_multiplier

        super().__init__(initial_supply=initial_supply,
                         first_phase_supply=first_phase_supply,
                         total_supply=total_supply,
                         first_phase_stable_issuance=first_phase_stable_issuance,
                         second_phase_coefficient=second_phase_coefficient,
                         locking_duration_coefficient_1=locking_duration_coefficient_1,
                         locking_duration_coefficient_2=locking_duration_coefficient_2,
                         maximum_rewarded_periods=maximum_rewarded_periods,
                         **kwargs)

    # TODO change this
    def token_supply_at_period(self, period: int) -> int:
        if period < 0:
            raise ValueError("Period must be a positive integer")

        with localcontext() as ctx:
            ctx.prec = self._precision

            #
            # Eq. 3 of the mining paper
            # https://github.com/nucypher/mining-paper/blob/master/mining-paper.pdf
            #

            t = Decimal(period)
            S_0 = self.erc20_initial_supply
            S_p1 = self.first_phase_supply
            phase_switch = 5  # TODO: Make this a variable
            phase_switch_in_periods = phase_switch * 365
            I_s_per_period = self.first_phase_stable_issuance  # per period
            T_half = self.token_halving  # in years
            T_half_in_periods = T_half * 365

            if t <= phase_switch_in_periods:
                S_t = S_0 + (t * I_s_per_period)
            else:
                S_t = S_0 + S_p1 + I_s_per_period * (1 - 2 ** (-t / T_half_in_periods)) / LOG2
            return int(S_t)

    def cumulative_rewards_at_period(self, period: int) -> int:
        return self.token_supply_at_period(period) - self.erc20_initial_supply

    def rewards_during_period(self, period: int) -> int:
        return self.cumulative_rewards_at_period(period) - self.cumulative_rewards_at_period(period-1)


class EconomicsFactory:
    # TODO: Enforce singleton

    __economics = dict()

    @classmethod
    def get_economics(cls, registry: BaseContractRegistry) -> BaseEconomics:
        registry_id = registry.id
        try:
            return cls.__economics[registry_id]
        except KeyError:
            economics = EconomicsFactory.retrieve_from_blockchain(registry=registry)
            cls.__economics[registry_id] = economics
            return economics

    @staticmethod
    def retrieve_from_blockchain(registry: BaseContractRegistry) -> BaseEconomics:

        # Agents
        token_agent = ContractAgency.get_agent(NucypherTokenAgent, registry=registry)
        staking_agent = ContractAgency.get_agent(StakingEscrowAgent, registry=registry)
        adjudicator_agent = ContractAgency.get_agent(AdjudicatorAgent, registry=registry)

        worklock_deployed = True
        try:
            worklock_agent = ContractAgency.get_agent(WorkLockAgent, registry=registry)
        except registry.UnknownContract:
            worklock_deployed = False

        # Token
        total_supply = token_agent.contract.functions.totalSupply().call()
        reward_supply = staking_agent.contract.functions.getReservedReward().call()
        # Not the "real" initial_supply value because used current reward instead of initial reward
        initial_supply = total_supply - reward_supply

        # Staking Escrow
        staking_parameters = list(staking_agent.staking_parameters())
        seconds_per_period = staking_parameters.pop(0)
        staking_parameters.insert(3, seconds_per_period // 60 // 60)  # hours_per_period

        # Adjudicator
        slashing_parameters = adjudicator_agent.slashing_parameters()

        # Worklock
        if worklock_deployed:
            worklock_parameters = worklock_agent.worklock_parameters()
        else:
            worklock_parameters = list()

        # Aggregate (order-sensitive)
        economics_parameters = (initial_supply,
                                total_supply,
                                *staking_parameters,
                                *slashing_parameters,
                                *worklock_parameters)

        economics = BaseEconomics(*economics_parameters)
        return economics
