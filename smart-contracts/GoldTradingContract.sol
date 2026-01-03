// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title GoldTradingContract
 * @dev Smart contract for transparent gold trading with ownership certificates
 * Each gold transaction is recorded as an NFT for proof of ownership
 */
contract GoldTradingContract is ERC721, Ownable, ReentrancyGuard {

    struct GoldTransaction {
        string orderId;
        address buyer;
        address seller;
        string goldType;
        uint256 quantity; // in grams (scaled by 1000 for decimals)
        uint256 totalAmount; // in wei
        uint256 timestamp;
        string deliveryStatus;
        bool verified;
        string certificationNumber;
    }

    struct GoldCertificate {
        uint256 tokenId;
        string serialNumber;
        uint256 purity; // in basis points (e.g., 9999 = 99.99%)
        uint256 weight; // in grams (scaled by 1000)
        string assayOffice;
        string vaultLocation;
        bool isPhysical;
        uint256 issueDate;
    }

    // Mappings
    mapping(uint256 => GoldTransaction) public transactions;
    mapping(uint256 => GoldCertificate) public certificates;
    mapping(string => uint256) public orderIdToTokenId;
    mapping(address => uint256[]) public userTransactions;

    // Counters
    uint256 private _tokenIdCounter;

    // Events
    event TransactionRecorded(
        uint256 indexed tokenId,
        string orderId,
        address indexed buyer,
        uint256 quantity,
        uint256 totalAmount
    );

    event DeliveryStatusUpdated(
        uint256 indexed tokenId,
        string newStatus,
        uint256 timestamp
    );

    event CertificateIssued(
        uint256 indexed tokenId,
        string serialNumber,
        address indexed owner
    );

    event TransactionVerified(
        uint256 indexed tokenId,
        address indexed verifier,
        uint256 timestamp
    );

    constructor() ERC721("GoldTradingCertificate", "GOLD") {
        _tokenIdCounter = 1;
    }

    /**
     * @dev Record a new gold transaction on blockchain
     * @param orderId Unique order identifier
     * @param buyer Address of the buyer
     * @param goldType Type of gold (24K, 22K, etc.)
     * @param quantity Amount in grams (scaled by 1000)
     * @param totalAmount Total transaction amount
     */
    function recordTransaction(
        string memory orderId,
        address buyer,
        string memory goldType,
        uint256 quantity,
        uint256 totalAmount
    ) external onlyOwner returns (uint256) {
        require(buyer != address(0), "Invalid buyer address");
        require(quantity > 0, "Quantity must be greater than 0");

        uint256 tokenId = _tokenIdCounter;
        _tokenIdCounter++;

        // Mint NFT certificate to buyer
        _safeMint(buyer, tokenId);

        // Record transaction details
        transactions[tokenId] = GoldTransaction({
            orderId: orderId,
            buyer: buyer,
            seller: msg.sender,
            goldType: goldType,
            quantity: quantity,
            totalAmount: totalAmount,
            timestamp: block.timestamp,
            deliveryStatus: "PENDING",
            verified: false,
            certificationNumber: ""
        });

        orderIdToTokenId[orderId] = tokenId;
        userTransactions[buyer].push(tokenId);

        emit TransactionRecorded(tokenId, orderId, buyer, quantity, totalAmount);

        return tokenId;
    }

    /**
     * @dev Issue physical gold certificate
     * @param tokenId Token ID of the transaction
     * @param serialNumber Unique serial number of the gold
     * @param purity Purity in basis points
     * @param weight Weight in grams (scaled by 1000)
     * @param assayOffice Name of assay office
     * @param vaultLocation Location where gold is stored
     * @param isPhysical Whether gold is physically delivered or stored
     */
    function issueCertificate(
        uint256 tokenId,
        string memory serialNumber,
        uint256 purity,
        uint256 weight,
        string memory assayOffice,
        string memory vaultLocation,
        bool isPhysical
    ) external onlyOwner {
        require(_exists(tokenId), "Token does not exist");

        certificates[tokenId] = GoldCertificate({
            tokenId: tokenId,
            serialNumber: serialNumber,
            purity: purity,
            weight: weight,
            assayOffice: assayOffice,
            vaultLocation: vaultLocation,
            isPhysical: isPhysical,
            issueDate: block.timestamp
        });

        transactions[tokenId].certificationNumber = serialNumber;

        emit CertificateIssued(tokenId, serialNumber, ownerOf(tokenId));
    }

    /**
     * @dev Update delivery status
     * @param tokenId Token ID of the transaction
     * @param status New delivery status
     */
    function updateDeliveryStatus(
        uint256 tokenId,
        string memory status
    ) external onlyOwner {
        require(_exists(tokenId), "Token does not exist");

        transactions[tokenId].deliveryStatus = status;

        emit DeliveryStatusUpdated(tokenId, status, block.timestamp);
    }

    /**
     * @dev Verify transaction (called after delivery confirmation)
     * @param tokenId Token ID to verify
     */
    function verifyTransaction(uint256 tokenId) external onlyOwner {
        require(_exists(tokenId), "Token does not exist");
        require(!transactions[tokenId].verified, "Already verified");

        transactions[tokenId].verified = true;

        emit TransactionVerified(tokenId, msg.sender, block.timestamp);
    }

    /**
     * @dev Get transaction details
     * @param tokenId Token ID
     */
    function getTransaction(uint256 tokenId)
        external
        view
        returns (GoldTransaction memory)
    {
        require(_exists(tokenId), "Token does not exist");
        return transactions[tokenId];
    }

    /**
     * @dev Get certificate details
     * @param tokenId Token ID
     */
    function getCertificate(uint256 tokenId)
        external
        view
        returns (GoldCertificate memory)
    {
        require(_exists(tokenId), "Token does not exist");
        return certificates[tokenId];
    }

    /**
     * @dev Get all transactions for a user
     * @param user Address of the user
     */
    function getUserTransactions(address user)
        external
        view
        returns (uint256[] memory)
    {
        return userTransactions[user];
    }

    /**
     * @dev Get token ID from order ID
     * @param orderId Order identifier
     */
    function getTokenIdByOrderId(string memory orderId)
        external
        view
        returns (uint256)
    {
        return orderIdToTokenId[orderId];
    }

    /**
     * @dev Check if token exists
     * @param tokenId Token ID to check
     */
    function _exists(uint256 tokenId) internal view returns (bool) {
        return _ownerOf(tokenId) != address(0);
    }

    /**
     * @dev Get total number of transactions recorded
     */
    function getTotalTransactions() external view returns (uint256) {
        return _tokenIdCounter - 1;
    }
}
