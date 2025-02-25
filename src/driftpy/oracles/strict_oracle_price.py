from typing import Optional


class StrictOraclePrice:
    def __init__(self, current: int, twap: Optional[int] = None):
        self.current = current
        self.twap = twap

    def max(self) -> int:
        if self.twap:
            return max(self.twap, self.current)
        else:
            return self.current

    def min(self):
        if self.twap:
            return min(self.twap, self.current)
        else:
            return self.current
