const mongoose = require('mongoose');

const InventorySchema = new mongoose.Schema({
  inventoryId: {
    type: String,
    required: true,
    unique: true
  },
  goldType: {
    type: String,
    enum: ['24K', '22K', '18K', 'BARS', 'COINS'],
    required: true
  },
  quantity: {
    available: { type: Number, required: true, min: 0 },
    reserved: { type: Number, default: 0, min: 0 },
    total: { type: Number, required: true, min: 0 },
    unit: { type: String, enum: ['GRAM', 'OUNCE', 'KG'], default: 'GRAM' }
  },
  location: {
    vaultId: { type: String, required: true },
    vaultName: String,
    address: {
      street: String,
      city: String,
      country: String
    },
    section: String,
    shelf: String,
    bin: String
  },
  certification: {
    assayOffice: String,
    certificateNumber: String,
    purity: Number,
    weight: Number,
    serialNumber: String,
    hallmark: String,
    certificationDate: Date
  },
  supplier: {
    name: String,
    supplierId: String,
    country: String,
    certification: String
  },
  pricing: {
    basePrice: Number,
    premiumPercentage: Number,
    currentMarketPrice: Number,
    lastUpdated: Date
  },
  security: {
    insuranceProvider: String,
    insurancePolicyNumber: String,
    insuredValue: Number,
    securityLevel: {
      type: String,
      enum: ['STANDARD', 'HIGH', 'MAXIMUM'],
      default: 'HIGH'
    }
  },
  audit: {
    lastAuditDate: Date,
    nextAuditDate: Date,
    auditedBy: String,
    discrepancies: [{
      date: Date,
      description: String,
      resolved: Boolean
    }]
  },
  movements: [{
    type: {
      type: String,
      enum: ['RECEIVED', 'SOLD', 'TRANSFERRED', 'AUDITED', 'RESERVED', 'RELEASED']
    },
    quantity: Number,
    date: { type: Date, default: Date.now },
    reference: String,
    notes: String,
    performedBy: String
  }],
  status: {
    type: String,
    enum: ['AVAILABLE', 'RESERVED', 'IN_TRANSIT', 'SOLD', 'AUDIT_REQUIRED'],
    default: 'AVAILABLE'
  }
}, {
  timestamps: true
});

// Indexes
InventorySchema.index({ inventoryId: 1 });
InventorySchema.index({ goldType: 1, status: 1 });
InventorySchema.index({ 'location.vaultId': 1 });

// Method to reserve inventory
InventorySchema.methods.reserve = function(amount) {
  if (this.quantity.available < amount) {
    throw new Error('Insufficient inventory available');
  }
  this.quantity.available -= amount;
  this.quantity.reserved += amount;
  this.movements.push({
    type: 'RESERVED',
    quantity: amount,
    date: new Date()
  });
  return this.save();
};

// Method to release reserved inventory
InventorySchema.methods.release = function(amount) {
  if (this.quantity.reserved < amount) {
    throw new Error('Insufficient reserved inventory');
  }
  this.quantity.reserved -= amount;
  this.quantity.available += amount;
  this.movements.push({
    type: 'RELEASED',
    quantity: amount,
    date: new Date()
  });
  return this.save();
};

module.exports = mongoose.model('Inventory', InventorySchema);
