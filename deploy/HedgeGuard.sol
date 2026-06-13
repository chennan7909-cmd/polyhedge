// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface AggregatorV3Interface {
    function decimals() external view returns (uint8);
    function latestRoundData()
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        );
}

contract HedgeGuard {
    address public owner;
    AggregatorV3Interface public priceFeed;
    uint256 public maxStaleness = 3 hours;

    struct Hedge {
        address account;
        string market;
        uint256 shares;
        int256 guardPrice;
        uint256 timestamp;
    }

    Hedge[] public hedges;

    event HedgeRecorded(
        uint256 indexed id,
        address indexed account,
        string market,
        uint256 shares,
        int256 guardPrice
    );

    constructor(address _priceFeed) {
        owner = msg.sender;
        priceFeed = AggregatorV3Interface(_priceFeed);
    }

    function getValidatedPrice() public view returns (int256) {
        (
            uint80 roundId,
            int256 answer,
            ,
            uint256 updatedAt,
            uint80 answeredInRound
        ) = priceFeed.latestRoundData();

        require(answer > 0, "Chainlink: invalid price");
        require(updatedAt != 0, "Chainlink: round not complete");
        require(answeredInRound >= roundId, "Chainlink: stale round");
        require(block.timestamp - updatedAt <= maxStaleness, "Chainlink: price too old");
        return answer;
    }

    function recordHedge(string calldata market, uint256 shares) external returns (uint256) {
        int256 guardPrice = getValidatedPrice();

        hedges.push(Hedge({
            account: msg.sender,
            market: market,
            shares: shares,
            guardPrice: guardPrice,
            timestamp: block.timestamp
        }));

        uint256 id = hedges.length - 1;
        emit HedgeRecorded(id, msg.sender, market, shares, guardPrice);
        return id;
    }

    function hedgeCount() external view returns (uint256) {
        return hedges.length;
    }

    function setPriceFeed(address _priceFeed) external {
        require(msg.sender == owner, "only owner");
        priceFeed = AggregatorV3Interface(_priceFeed);
    }
}
