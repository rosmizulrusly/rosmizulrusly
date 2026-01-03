const mongoose = require('mongoose');
const crypto = require('crypto');

const OrderSchema = new mongoose.Schema({
  orderId: {
    type: String,
    required: true,
    unique: true,
    default: () => `ORD-${Date.now()}-${crypto.randomBytes(4).toString('hex').toUpperCase()}`
  },
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  orderType: {
    type: String,
    enum: ['BUY', 'SELL'],
    required: true
  },
  goldType: {
    type: String,
    enum: ['24K', '22K', '18K', 'BARS', 'COINS'],
    required: true
  },
  quantity: {
    value: { type: Number, required: true, min: 0.01 },
    unit: { type: String, enum: ['GRAM', 'OUNCE', 'KG'], default: 'GRAM' }
  },
  pricePerUnit: {
    type: Number,
    required: true
  },
  totalAmount: {
    type: Number,
    required: true
  },
  deliveryMethod: {
    type: String,
    enum: ['VAULT_STORAGE', 'HOME_DELIVERY', 'PICKUP', 'DIGITAL_CERTIFICATE'],
    required: true
  },
  deliveryAddress: {
    street: String,
    city: String,
    state: String,
    country: String,
    postalCode: String,
    coordinates: {
      latitude: Number,
      longitude: Number
    }
  },
  status: {
    type: String,
    enum: ['PENDING', 'VERIFIED', 'PAYMENT_CONFIRMED', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED', 'DISPUTED'],
    default: 'PENDING'
  },
  blockchain: {
    transactionHash: String,
    blockNumber: Number,
    verified: { type: Boolean, default: false },
    timestamp: Date
  },
  payment: {
    method: {
      type: String,
      enum: ['BANK_TRANSFER', 'CRYPTO', 'CREDIT_CARD', 'ESCROW']
    },
    status: {
      type: String,
      enum: ['PENDING', 'CONFIRMED', 'FAILED', 'REFUNDED'],
      default: 'PENDING'
    },
    transactionId: String,
    paidAt: Date
  },
  delivery: {
    courier: String,
    trackingNumber: String,
    qrCode: String,
    securitySeal: String,
    estimatedDelivery: Date,
    actualDelivery: Date,
    deliveryProof: {
      signature: String,
      photo: String,
      gpsLocation: {
        latitude: Number,
        longitude: Number
      },
      timestamp: Date
    }
  },
  verification: {
    kycVerified: { type: Boolean, default: false },
    amlCleared: { type: Boolean, default: false },
    goldAuthenticated: { type: Boolean, default: false },
    certificationNumber: String,
    assayReport: String
  },
  insurance: {
    provider: String,
    policyNumber: String,
    coverage: Number,
    premium: Number
  },
  timeline: [{
    status: String,
    timestamp: { type: Date, default: Date.now },
    description: String,
    updatedBy: String
  }]
}, {
  timestamps: true
});

// Indexes for fast queries
OrderSchema.index({ orderId: 1 });
OrderSchema.index({ userId: 1, status: 1 });
OrderSchema.index({ 'blockchain.transactionHash': 1 });
OrderSchema.index({ createdAt: -1 });

// Pre-save middleware to add timeline entry
OrderSchema.pre('save', function(next) {
  if (this.isModified('status')) {
    this.timeline.push({
      status: this.status,
      timestamp: new Date(),
      description: `Order status changed to ${this.status}`
    });
  }
  next();
});

module.exports = mongoose.model('Order', OrderSchema);
