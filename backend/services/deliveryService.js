const crypto = require('crypto');
const QRCode = require('qrcode');

class DeliveryService {
  /**
   * Create delivery tracking for order
   * Generates QR code, tracking number, and security seal
   */
  async createDelivery(order) {
    try {
      const trackingNumber = this.generateTrackingNumber();
      const securitySeal = this.generateSecuritySeal();

      // Generate QR code with encrypted order data
      const qrData = {
        orderId: order.orderId,
        trackingNumber,
        securitySeal,
        goldType: order.goldType,
        quantity: order.quantity.value,
        timestamp: new Date().toISOString()
      };

      const qrCodeData = await this.generateQRCode(qrData);

      // Estimate delivery time based on location
      const estimatedDelivery = this.calculateDeliveryTime(order.deliveryAddress);

      return {
        trackingNumber,
        qrCode: qrCodeData,
        securitySeal,
        estimatedDelivery,
        courier: this.assignCourier(order.deliveryAddress),
        status: 'PENDING_PICKUP'
      };

    } catch (error) {
      console.error('Create delivery error:', error);
      throw new Error('Failed to create delivery tracking');
    }
  }

  /**
   * Generate QR code for delivery verification
   */
  async generateQRCode(data) {
    try {
      // Encrypt sensitive data
      const encryptedData = this.encryptData(JSON.stringify(data));

      // Generate QR code
      const qrCode = await QRCode.toDataURL(encryptedData, {
        errorCorrectionLevel: 'H',
        type: 'image/png',
        quality: 1,
        margin: 1,
        width: 300
      });

      return qrCode;

    } catch (error) {
      console.error('QR code generation error:', error);
      throw error;
    }
  }

  /**
   * Verify QR code at delivery
   */
  async verifyQRCode(scannedData, expectedData) {
    try {
      const decrypted = this.decryptData(scannedData);
      const qrData = JSON.parse(decrypted);

      return {
        valid: qrData.orderId === expectedData.orderId &&
               qrData.securitySeal === expectedData.securitySeal,
        data: qrData
      };

    } catch (error) {
      return { valid: false, error: error.message };
    }
  }

  /**
   * Track delivery in real-time using GPS
   */
  async trackDeliveryLocation(trackingNumber) {
    try {
      // In production, integrate with courier API
      // For now, return simulated tracking data
      return {
        trackingNumber,
        currentLocation: {
          latitude: 3.1390,
          longitude: 101.6869,
          city: 'Kuala Lumpur',
          country: 'Malaysia',
          timestamp: new Date()
        },
        status: 'IN_TRANSIT',
        checkpoints: [
          {
            location: 'Vault Facility',
            timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
            status: 'PICKED_UP'
          },
          {
            location: 'Distribution Center',
            timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000),
            status: 'IN_TRANSIT'
          }
        ],
        estimatedDelivery: new Date(Date.now() + 3 * 60 * 60 * 1000)
      };

    } catch (error) {
      console.error('Track delivery error:', error);
      throw error;
    }
  }

  /**
   * Generate unique tracking number
   */
  generateTrackingNumber() {
    const prefix = 'GOLD';
    const timestamp = Date.now().toString(36).toUpperCase();
    const random = crypto.randomBytes(4).toString('hex').toUpperCase();
    return `${prefix}-${timestamp}-${random}`;
  }

  /**
   * Generate tamper-proof security seal number
   */
  generateSecuritySeal() {
    const random = crypto.randomBytes(6).toString('hex').toUpperCase();
    const checksum = this.calculateChecksum(random);
    return `SEAL-${random}-${checksum}`;
  }

  /**
   * Calculate checksum for security seal
   */
  calculateChecksum(data) {
    return crypto
      .createHash('sha256')
      .update(data)
      .digest('hex')
      .substring(0, 4)
      .toUpperCase();
  }

  /**
   * Verify security seal integrity
   */
  verifySecuritySeal(seal) {
    const parts = seal.split('-');
    if (parts.length !== 3 || parts[0] !== 'SEAL') {
      return false;
    }

    const [, data, checksum] = parts;
    const calculatedChecksum = this.calculateChecksum(data);

    return checksum === calculatedChecksum;
  }

  /**
   * Assign courier based on delivery location
   */
  assignCourier(address) {
    // In production, use sophisticated courier selection algorithm
    // based on location, service level, availability, etc.
    const couriers = [
      { name: 'SecureGold Express', specialty: 'HIGH_VALUE' },
      { name: 'Brinks Logistics', specialty: 'SECURE_TRANSPORT' },
      { name: 'G4S Cash Solutions', specialty: 'PRECIOUS_METALS' }
    ];

    // Select based on address (simplified)
    return couriers[0].name;
  }

  /**
   * Calculate estimated delivery time
   */
  calculateDeliveryTime(address) {
    // In production, integrate with mapping/routing API
    // For now, use simplified calculation

    let hoursToAdd = 24; // Default 1 day

    // Adjust based on country/city (simplified)
    if (address.country === 'Malaysia') {
      hoursToAdd = address.city === 'Kuala Lumpur' ? 4 : 24;
    } else {
      hoursToAdd = 72; // 3 days for international
    }

    return new Date(Date.now() + hoursToAdd * 60 * 60 * 1000);
  }

  /**
   * Encrypt sensitive delivery data
   */
  encryptData(data) {
    const algorithm = 'aes-256-cbc';
    const key = crypto.scryptSync(process.env.ENCRYPTION_KEY || 'default-key', 'salt', 32);
    const iv = crypto.randomBytes(16);

    const cipher = crypto.createCipheriv(algorithm, key, iv);
    let encrypted = cipher.update(data, 'utf8', 'hex');
    encrypted += cipher.final('hex');

    return `${iv.toString('hex')}:${encrypted}`;
  }

  /**
   * Decrypt delivery data
   */
  decryptData(encryptedData) {
    const algorithm = 'aes-256-cbc';
    const key = crypto.scryptSync(process.env.ENCRYPTION_KEY || 'default-key', 'salt', 32);

    const [ivHex, encrypted] = encryptedData.split(':');
    const iv = Buffer.from(ivHex, 'hex');

    const decipher = crypto.createDecipheriv(algorithm, key, iv);
    let decrypted = decipher.update(encrypted, 'hex', 'utf8');
    decrypted += decipher.final('utf8');

    return decrypted;
  }

  /**
   * Initiate secure vault pickup
   */
  async scheduleVaultPickup(order) {
    return {
      pickupId: `PICKUP-${Date.now()}`,
      vaultLocation: 'Main Vault, KL',
      scheduledTime: new Date(Date.now() + 2 * 60 * 60 * 1000),
      securityTeam: 'Team Alpha',
      vehicle: 'Armored Transport AX-901',
      route: 'Optimized for security',
      estimatedDuration: '4 hours'
    };
  }

  /**
   * Verify delivery completion with multi-factor authentication
   */
  async verifyDeliveryCompletion(deliveryData) {
    const {
      qrCodeScanned,
      securitySealIntact,
      recipientSignature,
      gpsLocation,
      photoEvidence,
      timestamp
    } = deliveryData;

    // Verify all security checks
    const verificationResults = {
      qrCodeValid: await this.verifyQRCode(qrCodeScanned),
      sealIntact: this.verifySecuritySeal(securitySealIntact),
      signaturePresent: !!recipientSignature,
      locationVerified: this.verifyDeliveryLocation(gpsLocation),
      photoVerified: !!photoEvidence,
      timestamp: new Date(timestamp),
      overallValid: false
    };

    verificationResults.overallValid =
      verificationResults.qrCodeValid.valid &&
      verificationResults.sealIntact &&
      verificationResults.signaturePresent &&
      verificationResults.locationVerified &&
      verificationResults.photoVerified;

    return verificationResults;
  }

  /**
   * Verify delivery location matches order address
   */
  verifyDeliveryLocation(gpsLocation, orderAddress) {
    // In production, use geolocation API to verify proximity
    // For now, simplified check
    return gpsLocation && gpsLocation.latitude && gpsLocation.longitude;
  }
}

module.exports = new DeliveryService();
module.exports.DeliveryService = DeliveryService;
