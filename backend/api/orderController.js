const Order = require('../models/Order');
const Inventory = require('../models/Inventory');
const { createBlockchainRecord } = require('../services/blockchainService');
const { initiatePayment } = require('../services/paymentService');
const { generateQRCode, createDelivery } = require('../services/deliveryService');
const { verifyKYC, checkAML } = require('../services/complianceService');

class OrderController {
  // Create new order
  async createOrder(req, res) {
    try {
      const { userId, orderType, goldType, quantity, deliveryMethod, deliveryAddress } = req.body;

      // Step 1: Verify user compliance
      const kycStatus = await verifyKYC(userId);
      const amlStatus = await checkAML(userId);

      if (!kycStatus.verified || !amlStatus.cleared) {
        return res.status(403).json({
          success: false,
          message: 'User verification required. Please complete KYC/AML process.'
        });
      }

      // Step 2: Check inventory availability
      const inventory = await Inventory.findOne({
        goldType,
        status: 'AVAILABLE',
        'quantity.available': { $gte: quantity.value }
      });

      if (!inventory) {
        return res.status(400).json({
          success: false,
          message: 'Insufficient inventory for this gold type'
        });
      }

      // Step 3: Calculate pricing
      const pricePerUnit = inventory.pricing.currentMarketPrice * (1 + inventory.pricing.premiumPercentage / 100);
      const totalAmount = pricePerUnit * quantity.value;

      // Step 4: Create order
      const order = new Order({
        userId,
        orderType,
        goldType,
        quantity,
        pricePerUnit,
        totalAmount,
        deliveryMethod,
        deliveryAddress,
        verification: {
          kycVerified: true,
          amlCleared: true
        }
      });

      // Step 5: Reserve inventory
      await inventory.reserve(quantity.value);

      // Step 6: Record on blockchain
      const blockchainRecord = await createBlockchainRecord({
        orderId: order.orderId,
        userId,
        goldType,
        quantity: quantity.value,
        totalAmount,
        timestamp: new Date()
      });

      order.blockchain = {
        transactionHash: blockchainRecord.hash,
        blockNumber: blockchainRecord.blockNumber,
        verified: true,
        timestamp: blockchainRecord.timestamp
      };

      // Step 7: Generate delivery tracking
      if (deliveryMethod !== 'VAULT_STORAGE') {
        const deliveryTracking = await createDelivery(order);
        order.delivery.qrCode = deliveryTracking.qrCode;
        order.delivery.trackingNumber = deliveryTracking.trackingNumber;
        order.delivery.securitySeal = deliveryTracking.securitySeal;
      }

      await order.save();

      // Step 8: Initiate payment
      const paymentLink = await initiatePayment(order);

      res.status(201).json({
        success: true,
        message: 'Order created successfully',
        data: {
          order,
          paymentLink,
          blockchainVerification: blockchainRecord
        }
      });

    } catch (error) {
      console.error('Create order error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to create order',
        error: error.message
      });
    }
  }

  // Get order details
  async getOrder(req, res) {
    try {
      const { orderId } = req.params;

      const order = await Order.findOne({ orderId })
        .populate('userId', 'profile email')
        .lean();

      if (!order) {
        return res.status(404).json({
          success: false,
          message: 'Order not found'
        });
      }

      res.status(200).json({
        success: true,
        data: order
      });

    } catch (error) {
      console.error('Get order error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to retrieve order',
        error: error.message
      });
    }
  }

  // Update order status
  async updateOrderStatus(req, res) {
    try {
      const { orderId } = req.params;
      const { status, notes, updatedBy } = req.body;

      const order = await Order.findOne({ orderId });

      if (!order) {
        return res.status(404).json({
          success: false,
          message: 'Order not found'
        });
      }

      order.status = status;
      order.timeline.push({
        status,
        timestamp: new Date(),
        description: notes || `Order status updated to ${status}`,
        updatedBy
      });

      await order.save();

      res.status(200).json({
        success: true,
        message: 'Order status updated',
        data: order
      });

    } catch (error) {
      console.error('Update order status error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to update order status',
        error: error.message
      });
    }
  }

  // Confirm delivery
  async confirmDelivery(req, res) {
    try {
      const { orderId } = req.params;
      const { signature, photo, gpsLocation, qrCodeScanned } = req.body;

      const order = await Order.findOne({ orderId });

      if (!order) {
        return res.status(404).json({
          success: false,
          message: 'Order not found'
        });
      }

      // Verify QR code
      if (order.delivery.qrCode !== qrCodeScanned) {
        return res.status(400).json({
          success: false,
          message: 'Invalid QR code. Delivery verification failed.'
        });
      }

      order.delivery.deliveryProof = {
        signature,
        photo,
        gpsLocation,
        timestamp: new Date()
      };
      order.delivery.actualDelivery = new Date();
      order.status = 'DELIVERED';

      await order.save();

      res.status(200).json({
        success: true,
        message: 'Delivery confirmed successfully',
        data: order
      });

    } catch (error) {
      console.error('Confirm delivery error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to confirm delivery',
        error: error.message
      });
    }
  }

  // Get user orders
  async getUserOrders(req, res) {
    try {
      const { userId } = req.params;
      const { status, page = 1, limit = 20 } = req.query;

      const query = { userId };
      if (status) query.status = status;

      const orders = await Order.find(query)
        .sort({ createdAt: -1 })
        .limit(limit * 1)
        .skip((page - 1) * limit)
        .lean();

      const count = await Order.countDocuments(query);

      res.status(200).json({
        success: true,
        data: orders,
        pagination: {
          total: count,
          page: parseInt(page),
          pages: Math.ceil(count / limit)
        }
      });

    } catch (error) {
      console.error('Get user orders error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to retrieve orders',
        error: error.message
      });
    }
  }

  // Track delivery in real-time
  async trackDelivery(req, res) {
    try {
      const { trackingNumber } = req.params;

      const order = await Order.findOne({ 'delivery.trackingNumber': trackingNumber })
        .select('orderId status delivery timeline')
        .lean();

      if (!order) {
        return res.status(404).json({
          success: false,
          message: 'Tracking number not found'
        });
      }

      res.status(200).json({
        success: true,
        data: {
          orderId: order.orderId,
          status: order.status,
          delivery: order.delivery,
          timeline: order.timeline
        }
      });

    } catch (error) {
      console.error('Track delivery error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to track delivery',
        error: error.message
      });
    }
  }
}

module.exports = new OrderController();
