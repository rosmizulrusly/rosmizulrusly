const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');
const crypto = require('crypto');

const UserSchema = new mongoose.Schema({
  userId: {
    type: String,
    required: true,
    unique: true,
    default: () => `USER-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`
  },
  email: {
    type: String,
    required: true,
    unique: true,
    lowercase: true,
    trim: true
  },
  password: {
    type: String,
    required: true,
    select: false
  },
  profile: {
    firstName: { type: String, required: true },
    lastName: { type: String, required: true },
    phoneNumber: { type: String, required: true },
    dateOfBirth: Date,
    nationality: String
  },
  kyc: {
    status: {
      type: String,
      enum: ['NOT_SUBMITTED', 'PENDING', 'APPROVED', 'REJECTED'],
      default: 'NOT_SUBMITTED'
    },
    idType: {
      type: String,
      enum: ['PASSPORT', 'DRIVERS_LICENSE', 'NATIONAL_ID']
    },
    idNumber: String,
    idDocument: String,
    selfieDocument: String,
    addressProof: String,
    submittedAt: Date,
    verifiedAt: Date,
    verifiedBy: String,
    rejectionReason: String
  },
  aml: {
    riskLevel: {
      type: String,
      enum: ['LOW', 'MEDIUM', 'HIGH', 'PROHIBITED'],
      default: 'MEDIUM'
    },
    lastChecked: Date,
    sources: [String],
    flags: [{
      type: String,
      description: String,
      severity: String,
      date: Date
    }]
  },
  wallets: [{
    type: {
      type: String,
      enum: ['FIAT', 'CRYPTO', 'GOLD_VAULT']
    },
    currency: String,
    balance: { type: Number, default: 0 },
    address: String,
    isActive: { type: Boolean, default: true }
  }],
  preferences: {
    defaultDeliveryMethod: String,
    notifications: {
      email: { type: Boolean, default: true },
      sms: { type: Boolean, default: true },
      push: { type: Boolean, default: true }
    },
    twoFactorEnabled: { type: Boolean, default: false },
    twoFactorSecret: String
  },
  security: {
    lastLogin: Date,
    lastPasswordChange: Date,
    failedLoginAttempts: { type: Number, default: 0 },
    accountLocked: { type: Boolean, default: false },
    lockedUntil: Date,
    passwordResetToken: String,
    passwordResetExpires: Date,
    trustedDevices: [{
      deviceId: String,
      deviceName: String,
      lastUsed: Date,
      ipAddress: String
    }]
  },
  tradingLimits: {
    daily: { type: Number, default: 100000 },
    monthly: { type: Number, default: 1000000 },
    perTransaction: { type: Number, default: 50000 }
  },
  verification: {
    emailVerified: { type: Boolean, default: false },
    phoneVerified: { type: Boolean, default: false },
    emailVerificationToken: String,
    phoneVerificationCode: String
  },
  role: {
    type: String,
    enum: ['USER', 'TRADER', 'ADMIN', 'VAULT_MANAGER', 'COMPLIANCE_OFFICER'],
    default: 'USER'
  },
  status: {
    type: String,
    enum: ['ACTIVE', 'SUSPENDED', 'CLOSED'],
    default: 'ACTIVE'
  }
}, {
  timestamps: true
});

// Hash password before saving
UserSchema.pre('save', async function(next) {
  if (!this.isModified('password')) return next();
  this.password = await bcrypt.hash(this.password, 12);
  next();
});

// Compare password method
UserSchema.methods.comparePassword = async function(candidatePassword) {
  return await bcrypt.compare(candidatePassword, this.password);
};

// Generate password reset token
UserSchema.methods.createPasswordResetToken = function() {
  const resetToken = crypto.randomBytes(32).toString('hex');
  this.security.passwordResetToken = crypto
    .createHash('sha256')
    .update(resetToken)
    .digest('hex');
  this.security.passwordResetExpires = Date.now() + 10 * 60 * 1000; // 10 minutes
  return resetToken;
};

module.exports = mongoose.model('User', UserSchema);
