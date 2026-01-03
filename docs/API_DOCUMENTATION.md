# Gold Trading Platform - API Documentation

## Base URL
```
Production: https://api.goldtrading.com/v1
Staging: https://api-staging.goldtrading.com/v1
Development: http://localhost:3000/api/v1
```

## Authentication

All authenticated endpoints require a JWT token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Authentication Endpoints

#### Register New User
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "profile": {
    "firstName": "John",
    "lastName": "Doe",
    "phoneNumber": "+60123456789",
    "dateOfBirth": "1990-01-01"
  }
}

Response 201:
{
  "success": true,
  "message": "Registration successful",
  "data": {
    "userId": "USER-1234567890-ABC",
    "email": "user@example.com",
    "accessToken": "eyJhbGciOiJIUzI1NiIs...",
    "refreshToken": "eyJhbGciOiJIUzI1NiIs..."
  }
}
```

#### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}

Response 200:
{
  "success": true,
  "data": {
    "userId": "USER-1234567890-ABC",
    "accessToken": "eyJhbGciOiJIUzI1NiIs...",
    "refreshToken": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "email": "user@example.com",
      "profile": {...},
      "kyc": {...}
    }
  }
}
```

## Order Management

### Create Order

```http
POST /orders
Authorization: Bearer <token>
Content-Type: application/json

{
  "orderType": "BUY",
  "goldType": "24K",
  "quantity": {
    "value": 100,
    "unit": "GRAM"
  },
  "deliveryMethod": "HOME_DELIVERY",
  "deliveryAddress": {
    "street": "123 Main Street",
    "city": "Kuala Lumpur",
    "state": "Federal Territory",
    "country": "Malaysia",
    "postalCode": "50000",
    "coordinates": {
      "latitude": 3.1390,
      "longitude": 101.6869
    }
  }
}

Response 201:
{
  "success": true,
  "message": "Order created successfully",
  "data": {
    "order": {
      "orderId": "ORD-1704278400000-A1B2C3D4",
      "userId": "USER-1234567890-ABC",
      "orderType": "BUY",
      "goldType": "24K",
      "quantity": {
        "value": 100,
        "unit": "GRAM"
      },
      "pricePerUnit": 250.50,
      "totalAmount": 25050.00,
      "status": "PENDING",
      "blockchain": {
        "transactionHash": "0x123abc...",
        "blockNumber": 12345678,
        "verified": true
      },
      "delivery": {
        "trackingNumber": "GOLD-1M2N3O4P-A1B2C3D4",
        "qrCode": "data:image/png;base64,...",
        "securitySeal": "SEAL-ABC123-4D5E"
      },
      "createdAt": "2024-01-03T12:00:00.000Z"
    },
    "paymentLink": "https://pay.goldtrading.com/checkout/PAY-123456",
    "blockchainVerification": {
      "hash": "0x123abc...",
      "network": "ethereum-sepolia"
    }
  }
}
```

### Get Order Details

```http
GET /orders/:orderId
Authorization: Bearer <token>

Response 200:
{
  "success": true,
  "data": {
    "orderId": "ORD-1704278400000-A1B2C3D4",
    "status": "IN_TRANSIT",
    "timeline": [
      {
        "status": "PENDING",
        "timestamp": "2024-01-03T12:00:00.000Z",
        "description": "Order created"
      },
      {
        "status": "PAYMENT_CONFIRMED",
        "timestamp": "2024-01-03T12:15:00.000Z",
        "description": "Payment confirmed"
      },
      {
        "status": "IN_TRANSIT",
        "timestamp": "2024-01-03T14:00:00.000Z",
        "description": "Order dispatched from vault"
      }
    ],
    ...
  }
}
```

### Get User Orders

```http
GET /orders/user/:userId?status=DELIVERED&page=1&limit=20
Authorization: Bearer <token>

Response 200:
{
  "success": true,
  "data": [
    {
      "orderId": "ORD-...",
      "goldType": "24K",
      "quantity": 100,
      "totalAmount": 25050,
      "status": "DELIVERED",
      "createdAt": "2024-01-01T10:00:00.000Z"
    },
    ...
  ],
  "pagination": {
    "total": 45,
    "page": 1,
    "pages": 3
  }
}
```

### Track Delivery

```http
GET /orders/track/:trackingNumber

Response 200:
{
  "success": true,
  "data": {
    "orderId": "ORD-...",
    "status": "IN_TRANSIT",
    "delivery": {
      "trackingNumber": "GOLD-...",
      "currentLocation": {
        "latitude": 3.1390,
        "longitude": 101.6869,
        "city": "Kuala Lumpur",
        "timestamp": "2024-01-03T14:30:00.000Z"
      },
      "estimatedDelivery": "2024-01-03T18:00:00.000Z",
      "checkpoints": [
        {
          "location": "Vault Facility",
          "timestamp": "2024-01-03T14:00:00.000Z",
          "status": "PICKED_UP"
        },
        {
          "location": "Distribution Center",
          "timestamp": "2024-01-03T14:30:00.000Z",
          "status": "IN_TRANSIT"
        }
      ]
    },
    "timeline": [...]
  }
}
```

### Confirm Delivery

```http
POST /orders/:orderId/confirm-delivery
Authorization: Bearer <token>
Content-Type: application/json

{
  "signature": "data:image/png;base64,...",
  "photo": "data:image/jpeg;base64,...",
  "gpsLocation": {
    "latitude": 3.1390,
    "longitude": 101.6869
  },
  "qrCodeScanned": "encrypted-qr-data"
}

Response 200:
{
  "success": true,
  "message": "Delivery confirmed successfully",
  "data": {
    "orderId": "ORD-...",
    "status": "DELIVERED",
    "delivery": {
      "actualDelivery": "2024-01-03T17:45:00.000Z",
      "deliveryProof": {
        "signature": "...",
        "photo": "...",
        "gpsLocation": {...},
        "timestamp": "2024-01-03T17:45:00.000Z"
      }
    }
  }
}
```

## Inventory Management

### Get Inventory

```http
GET /inventory?goldType=24K&status=AVAILABLE
Authorization: Bearer <token>

Response 200:
{
  "success": true,
  "data": [
    {
      "inventoryId": "INV-...",
      "goldType": "24K",
      "quantity": {
        "available": 5000,
        "reserved": 500,
        "total": 5500,
        "unit": "GRAM"
      },
      "location": {
        "vaultId": "VAULT-KL-01",
        "vaultName": "Kuala Lumpur Main Vault",
        "address": {...}
      },
      "pricing": {
        "basePrice": 240.00,
        "premiumPercentage": 4.0,
        "currentMarketPrice": 249.60,
        "lastUpdated": "2024-01-03T12:00:00.000Z"
      }
    }
  ],
  "summary": {
    "totalValue": 1374000,
    "totalAvailable": 5000,
    "totalReserved": 500,
    "byGoldType": {...},
    "byVault": {...}
  }
}
```

### Check Availability

```http
GET /inventory/availability?goldType=24K&quantity=100
Authorization: Bearer <token>

Response 200:
{
  "success": true,
  "available": true,
  "inventory": {
    "inventoryId": "INV-...",
    "availableQuantity": 5000,
    "location": {...},
    "pricing": {...}
  }
}
```

## Payment Processing

### Initiate Payment

```http
POST /payments/initiate
Authorization: Bearer <token>
Content-Type: application/json

{
  "orderId": "ORD-..."
}

Response 200:
{
  "success": true,
  "data": {
    "sessionId": "PAY-...",
    "orderId": "ORD-...",
    "amount": 25050.00,
    "currency": "USD",
    "paymentLink": "https://pay.goldtrading.com/checkout/PAY-...",
    "qrCode": "data:image/png;base64,...",
    "methods": [
      {
        "type": "BANK_TRANSFER",
        "name": "Bank Wire Transfer",
        "processingTime": "1-2 business days",
        "fees": 0
      },
      {
        "type": "CRYPTO",
        "name": "Cryptocurrency",
        "supportedCoins": ["BTC", "ETH", "USDT", "USDC"],
        "processingTime": "15-60 minutes",
        "fees": "0.5%"
      },
      {
        "type": "CREDIT_CARD",
        "name": "Credit/Debit Card",
        "processingTime": "Instant",
        "fees": "2.9%"
      },
      {
        "type": "ESCROW",
        "name": "Escrow Service",
        "processingTime": "Released upon delivery confirmation",
        "fees": "1%"
      }
    ],
    "expiresAt": "2024-01-03T12:30:00.000Z"
  }
}
```

### Process Payment

```http
POST /payments/process
Authorization: Bearer <token>
Content-Type: application/json

{
  "method": "CRYPTO",
  "orderId": "ORD-...",
  "amount": 25050.00,
  "details": {
    "cryptocurrency": "ETH",
    "walletAddress": "0x...",
    "transactionHash": "0x..."
  }
}

Response 200:
{
  "success": true,
  "data": {
    "transactionId": "0x...",
    "method": "CRYPTO",
    "amount": 25050.00,
    "status": "CONFIRMED",
    "confirmations": 3,
    "timestamp": "2024-01-03T12:20:00.000Z"
  }
}
```

## KYC/AML Compliance

### Submit KYC Documents

```http
POST /kyc/submit
Authorization: Bearer <token>
Content-Type: multipart/form-data

idDocument: <file>
selfieDocument: <file>
addressProof: <file>
idType: PASSPORT
idNumber: A12345678

Response 200:
{
  "success": true,
  "message": "KYC documents submitted successfully",
  "data": {
    "status": "PENDING",
    "submittedAt": "2024-01-03T12:00:00.000Z",
    "estimatedReview": "2024-01-04T12:00:00.000Z"
  }
}
```

### Get KYC Status

```http
GET /kyc/status
Authorization: Bearer <token>

Response 200:
{
  "success": true,
  "data": {
    "status": "APPROVED",
    "verifiedAt": "2024-01-04T10:30:00.000Z",
    "requirements": {
      "identityDocument": true,
      "selfieVerification": true,
      "addressProof": true
    }
  }
}
```

## Blockchain Verification

### Verify Transaction

```http
GET /blockchain/verify/:transactionHash
Authorization: Bearer <token>

Response 200:
{
  "success": true,
  "data": {
    "verified": true,
    "transactionHash": "0x...",
    "blockNumber": 12345678,
    "confirmations": 25,
    "timestamp": "2024-01-03T12:15:00.000Z",
    "network": "ethereum-sepolia"
  }
}
```

### Get Ownership Certificate

```http
GET /blockchain/certificate/:orderId
Authorization: Bearer <token>

Response 200:
{
  "success": true,
  "data": {
    "certificateId": "CERT-...",
    "orderId": "ORD-...",
    "tokenId": 123,
    "owner": "0x...",
    "goldType": "24K",
    "quantity": 100,
    "serialNumber": "GOLD-...",
    "issueDate": "2024-01-03T17:45:00.000Z",
    "blockchainReference": "0x...",
    "valid": true
  }
}
```

## Error Responses

All error responses follow this format:

```json
{
  "success": false,
  "message": "Error description",
  "error": "Detailed error message"
}
```

### Common Error Codes

- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (e.g., duplicate order)
- `422 Unprocessable Entity` - Validation error
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

## Rate Limiting

API requests are rate-limited to prevent abuse:

- **Authenticated users**: 100 requests per 15 minutes
- **Unauthenticated requests**: 20 requests per 15 minutes
- **Payment endpoints**: 10 requests per 15 minutes

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704279000
```

## Webhooks

### Payment Webhook

```http
POST <your-webhook-url>
Content-Type: application/json
X-Signature: <hmac-sha256-signature>

{
  "event": "payment.completed",
  "orderId": "ORD-...",
  "transactionId": "TXN-...",
  "amount": 25050.00,
  "method": "CRYPTO",
  "timestamp": "2024-01-03T12:20:00.000Z"
}
```

### Delivery Webhook

```http
POST <your-webhook-url>
Content-Type: application/json
X-Signature: <hmac-sha256-signature>

{
  "event": "delivery.completed",
  "orderId": "ORD-...",
  "trackingNumber": "GOLD-...",
  "deliveredAt": "2024-01-03T17:45:00.000Z",
  "proof": {
    "signature": "...",
    "photo": "...",
    "gpsLocation": {...}
  }
}
```

## SDK Examples

### JavaScript/Node.js

```javascript
const GoldTradingAPI = require('gold-trading-sdk');

const client = new GoldTradingAPI({
  apiKey: 'your-api-key',
  environment: 'production'
});

// Create order
const order = await client.orders.create({
  orderType: 'BUY',
  goldType: '24K',
  quantity: { value: 100, unit: 'GRAM' },
  deliveryMethod: 'HOME_DELIVERY',
  deliveryAddress: {...}
});

// Track delivery
const tracking = await client.orders.track(order.delivery.trackingNumber);
console.log(tracking.currentLocation);
```

### Python

```python
from gold_trading import GoldTradingClient

client = GoldTradingClient(
    api_key='your-api-key',
    environment='production'
)

# Create order
order = client.orders.create(
    order_type='BUY',
    gold_type='24K',
    quantity={'value': 100, 'unit': 'GRAM'},
    delivery_method='HOME_DELIVERY',
    delivery_address={...}
)

# Track delivery
tracking = client.orders.track(order['delivery']['trackingNumber'])
print(tracking['currentLocation'])
```

## Support

For API support and questions:
- Email: api-support@goldtrading.com
- Documentation: https://docs.goldtrading.com
- Status Page: https://status.goldtrading.com
