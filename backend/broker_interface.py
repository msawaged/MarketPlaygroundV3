# backend/broker_interface.py

from abc import ABC, abstractmethod

class BrokerInterface(ABC):
    """
    Abstract base class for all broker implementations.
    Every broker must implement the execute_order() method
    with a unified strategy dictionary input.
    """

    @abstractmethod
    def execute_order(self, strategy: dict, user_id: str = "anonymous") -> dict:
        """
        Execute a trade order based on the given strategy.

        Args:
            strategy (dict): Contains parsed belief → strategy output, including:
                - ticker
                - strategy type (e.g., "long call", "put spread")
                - allocation
                - expiry_date
                - direction
                - strike prices, etc.
            user_id (str): ID of the user placing the trade.

        Returns:
            dict: Execution response with:
                - status: "success" or "error"
                - message: summary of the result
                - order_id (if successful)
                - error (if failed)
        """
        pass
