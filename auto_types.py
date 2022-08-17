from dataclasses import dataclass
from solana.publickey import PublicKey
from borsh_construct.enum import _rust_enum
from sumtypes import constructor

@_rust_enum
class SwapDirection:
    ADD = constructor()
    REMOVE = constructor()
 
@_rust_enum
class PositionDirection:
    LONG = constructor()
    SHORT = constructor()
 
@_rust_enum
class LiquidationMultiplierType:
    DISCOUNT = constructor()
    PREMIUM = constructor()
 
@_rust_enum
class MarginRequirementType:
    INITIAL = constructor()
    MAINTENANCE = constructor()
 
@_rust_enum
class BankBalanceType:
    DEPOSIT = constructor()
    BORROW = constructor()
 
@_rust_enum
class DepositDirection:
    DEPOSIT = constructor()
    WITHDRAW = constructor()
 
@_rust_enum
class OrderAction:
    PLACE = constructor()
    CANCEL = constructor()
    FILL = constructor()
    TRIGGER = constructor()
    EXPIRE = constructor()
 
@_rust_enum
class OrderActionExplanation:
    NONE = constructor()
    BREACHEDMARGINREQUIREMENT = constructor()
    ORACLEPRICEBREACHEDLIMITPRICE = constructor()
    MARKETORDERFILLEDTOLIMITPRICE = constructor()
    MARKETORDERAUCTIONEXPIRED = constructor()
    CANCELEDFORLIQUIDATION = constructor()
 
@_rust_enum
class LiquidationType:
    LIQUIDATEPERP = constructor()
    LIQUIDATEBORROW = constructor()
    LIQUIDATEBORROWFORPERPPNL = constructor()
    LIQUIDATEPERPPNLFORDEPOSIT = constructor()
 
@_rust_enum
class FulfillmentMethod:
    AMM = constructor()
    MATCH = constructor()
 
@_rust_enum
class OracleSource:
    PYTH = constructor()
    SWITCHBOARD = constructor()
    QUOTEASSET = constructor()
 
@_rust_enum
class OrderStatus:
    INIT = constructor()
    OPEN = constructor()
    FILLED = constructor()
    CANCELED = constructor()
 
@_rust_enum
class OrderType:
    MARKET = constructor()
    LIMIT = constructor()
    TRIGGERMARKET = constructor()
    TRIGGERLIMIT = constructor()
 
@_rust_enum
class OrderDiscountTier:
    NONE = constructor()
    FIRST = constructor()
    SECOND = constructor()
    THIRD = constructor()
    FOURTH = constructor()
 
@_rust_enum
class OrderTriggerCondition:
    ABOVE = constructor()
    BELOW = constructor()
 
@dataclass
class OrderParamsOptionalAccounts:
    discountToken: bool
    referrer: bool
 
@dataclass
class OrderParams:
    orderType: OrderType
    direction: PositionDirection
    userOrderId: int
    baseAssetAmount: int
    price: int
    marketIndex: int
    reduceOnly: bool
    postOnly: bool
    immediateOrCancel: bool
    triggerPrice: int
    triggerCondition: OrderTriggerCondition
    optionalAccounts: OrderParamsOptionalAccounts
    positionLimit: int
    oraclePriceOffset: int
    auctionDuration: int
    padding0: bool
    padding1: bool
 
@dataclass
class PoolBalance:
    balance: int
 
@dataclass
class AMM:
    oracle: PublicKey
    oracleSource: OracleSource
    lastOraclePrice: int
    lastOracleConfPct: int
    lastOracleDelay: int
    lastOracleNormalisedPrice: int
    lastOraclePriceTwap: int
    lastOraclePriceTwapTs: int
    lastOracleMarkSpreadPct: int
    baseAssetReserve: int
    quoteAssetReserve: int
    sqrtK: int
    pegMultiplier: int
    terminalQuoteAssetReserve: int
    netBaseAssetAmount: int
    quoteAssetAmountLong: int
    quoteAssetAmountShort: int
    lastFundingRate: int
    lastFundingRateTs: int
    fundingPeriod: int
    cumulativeFundingRateLong: int
    cumulativeFundingRateShort: int
    cumulativeFundingRateLp: int
    cumulativeRepegRebateLong: int
    cumulativeRepegRebateShort: int
    markStd: int
    lastMarkPriceTwap: int
    lastMarkPriceTwapTs: int
    minimumQuoteAssetTradeSize: int
    maxBaseAssetAmountRatio: int
    maxSlippageRatio: int
    baseAssetAmountStepSize: int
    baseSpread: int
    longSpread: int
    shortSpread: int
    maxSpread: int
    askBaseAssetReserve: int
    askQuoteAssetReserve: int
    bidBaseAssetReserve: int
    bidQuoteAssetReserve: int
    lastBidPriceTwap: int
    lastAskPriceTwap: int
    longIntensityCount: int
    longIntensityVolume: int
    shortIntensityCount: int
    shortIntensityVolume: int
    curveUpdateIntensity: int
    totalFee: int
    totalMmFee: int
    totalExchangeFee: int
    totalFeeMinusDistributions: int
    totalFeeWithdrawn: int
    netRevenueSinceLastFunding: int
    feePool: PoolBalance
    lastUpdateSlot: int
    padding0: int
    padding1: int
    padding2: int
    padding3: int
 
@dataclass
class PriceDivergenceGuardRails:
    markOracleDivergenceNumerator: int
    markOracleDivergenceDenominator: int
 
@dataclass
class ValidityGuardRails:
    slotsBeforeStale: int
    confidenceIntervalMaxSize: int
    tooVolatileRatio: int
 
@dataclass
class OracleGuardRails:
    priceDivergence: PriceDivergenceGuardRails
    validity: ValidityGuardRails
    useForLiquidations: bool
 
@dataclass
class DiscountTokenTier:
    minimumBalance: int
    discountNumerator: int
    discountDenominator: int
 
@dataclass
class DiscountTokenTiers:
    firstTier: DiscountTokenTier
    secondTier: DiscountTokenTier
    thirdTier: DiscountTokenTier
    fourthTier: DiscountTokenTier
 
@dataclass
class DiscountTokenTiers:
    firstTier: DiscountTokenTier
    secondTier: DiscountTokenTier
    thirdTier: DiscountTokenTier
    fourthTier: DiscountTokenTier
 
@dataclass
class ReferralDiscount:
    referrerRewardNumerator: int
    referrerRewardDenominator: int
    refereeDiscountNumerator: int
    refereeDiscountDenominator: int
 
@dataclass
class OrderFillerRewardStructure:
    rewardNumerator: int
    rewardDenominator: int
    timeBasedRewardLowerBound: int
 
@dataclass
class FeeStructure:
    feeNumerator: int
    feeDenominator: int
    discountTokenTiers: DiscountTokenTiers
    referralDiscount: ReferralDiscount
    makerRebateNumerator: int
    makerRebateDenominator: int
    fillerRewardStructure: OrderFillerRewardStructure
    cancelOrderFee: int
 
@dataclass
class DiscountTokenTiers:
    firstTier: DiscountTokenTier
    secondTier: DiscountTokenTier
    thirdTier: DiscountTokenTier
    fourthTier: DiscountTokenTier
 
@dataclass
class UserBankBalance:
    bankIndex: int
    balanceType: BankBalanceType
    balance: int
 
@dataclass
class Order:
    status: OrderStatus
    orderType: OrderType
    ts: int
    slot: int
    orderId: int
    userOrderId: int
    marketIndex: int
    price: int
    existingPositionDirection: PositionDirection
    baseAssetAmount: int
    baseAssetAmountFilled: int
    quoteAssetAmountFilled: int
    fee: int
    direction: PositionDirection
    reduceOnly: bool
    postOnly: bool
    immediateOrCancel: bool
    discountTier: OrderDiscountTier
    triggerPrice: int
    triggerCondition: OrderTriggerCondition
    triggered: bool
    referrer: PublicKey
    oraclePriceOffset: int
    auctionStartPrice: int
    auctionEndPrice: int
    auctionDuration: int
    padding: list[int]
 
@dataclass
class Bank:
    bankIndex: int
    pubkey: PublicKey
    oracle: PublicKey
    oracleSource: OracleSource
    mint: PublicKey
    vault: PublicKey
    vaultAuthority: PublicKey
    vaultAuthorityNonce: int
    decimals: int
    optimalUtilization: int
    optimalBorrowRate: int
    maxBorrowRate: int
    depositBalance: int
    borrowBalance: int
    cumulativeDepositInterest: int
    cumulativeBorrowInterest: int
    lastUpdated: int
    initialAssetWeight: int
    maintenanceAssetWeight: int
    initialLiabilityWeight: int
    maintenanceLiabilityWeight: int
    imfFactor: int
    liquidationFee: int
 
@dataclass
class Market:
    marketIndex: int
    pubkey: PublicKey
    initialized: bool
    amm: AMM
    baseAssetAmountLong: int
    baseAssetAmountShort: int
    openInterest: int
    marginRatioInitial: int
    marginRatioMaintenance: int
    nextFillRecordId: int
    nextFundingRateRecordId: int
    nextCurveRecordId: int
    pnlPool: PoolBalance
    unsettledProfit: int
    unsettledLoss: int
    imfFactor: int
    unsettledInitialAssetWeight: int
    unsettledMaintenanceAssetWeight: int
    unsettledImfFactor: int
    liquidationFee: int
    padding0: int
    padding1: int
    padding2: int
    padding3: int
    padding4: int
 
@dataclass
class State:
    admin: PublicKey
    exchangePaused: bool
    fundingPaused: bool
    adminControlsPrices: bool
    insuranceVault: PublicKey
    insuranceVaultAuthority: PublicKey
    insuranceVaultNonce: int
    marginRatioInitial: int
    marginRatioMaintenance: int
    marginRatioPartial: int
    partialLiquidationClosePercentageNumerator: int
    partialLiquidationClosePercentageDenominator: int
    partialLiquidationPenaltyPercentageNumerator: int
    partialLiquidationPenaltyPercentageDenominator: int
    fullLiquidationPenaltyPercentageNumerator: int
    fullLiquidationPenaltyPercentageDenominator: int
    partialLiquidationLiquidatorShareDenominator: int
    fullLiquidationLiquidatorShareDenominator: int
    feeStructure: FeeStructure
    whitelistMint: PublicKey
    discountMint: PublicKey
    oracleGuardRails: OracleGuardRails
    numberOfMarkets: int
    numberOfBanks: int
    minOrderQuoteAssetAmount: int
    minAuctionDuration: int
    maxAuctionDuration: int
    liquidationMarginBufferRatio: int
    padding0: int
    padding1: int
 
@dataclass
class UserFees:
    totalFeePaid: int
    totalFeeRebate: int
    totalTokenDiscount: int
    totalReferralReward: int
    totalRefereeDiscount: int
 
@dataclass
class MarketPosition:
    marketIndex: int
    baseAssetAmount: int
    quoteAssetAmount: int
    quoteEntryAmount: int
    lastCumulativeFundingRate: int
    lastCumulativeRepegRebate: int
    lastFundingRateTs: int
    openOrders: int
    unsettledPnl: int
    openBids: int
    openAsks: int
    padding0: int
    padding1: int
    padding2: int
    padding3: int
    padding4: int
 
@dataclass
class User:
    authority: PublicKey
    userId: int
    name: list[int]
    bankBalances: list[UserBankBalance]
    fees: UserFees
    nextOrderId: int
    positions: list[MarketPosition]
    orders: list[Order]
    beingLiquidated: bool
 
