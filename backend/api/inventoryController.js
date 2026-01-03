const Inventory = require('../models/Inventory');
const crypto = require('crypto');

class InventoryController {
  /**
   * Get current inventory levels
   */
  async getInventory(req, res) {
    try {
      const { goldType, vaultId, status } = req.query;

      const filter = {};
      if (goldType) filter.goldType = goldType;
      if (vaultId) filter['location.vaultId'] = vaultId;
      if (status) filter.status = status;

      const inventory = await Inventory.find(filter)
        .sort({ goldType: 1, 'location.vaultId': 1 })
        .lean();

      // Calculate totals
      const summary = this.calculateInventorySummary(inventory);

      res.status(200).json({
        success: true,
        data: inventory,
        summary
      });

    } catch (error) {
      console.error('Get inventory error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to retrieve inventory',
        error: error.message
      });
    }
  }

  /**
   * Add new inventory
   */
  async addInventory(req, res) {
    try {
      const {
        goldType,
        quantity,
        location,
        certification,
        supplier,
        pricing
      } = req.body;

      const inventory = new Inventory({
        inventoryId: `INV-${Date.now()}-${crypto.randomBytes(4).toString('hex').toUpperCase()}`,
        goldType,
        quantity: {
          available: quantity,
          reserved: 0,
          total: quantity,
          unit: 'GRAM'
        },
        location,
        certification,
        supplier,
        pricing: {
          ...pricing,
          lastUpdated: new Date()
        },
        movements: [{
          type: 'RECEIVED',
          quantity,
          date: new Date(),
          notes: 'Initial inventory addition'
        }],
        status: 'AVAILABLE'
      });

      await inventory.save();

      res.status(201).json({
        success: true,
        message: 'Inventory added successfully',
        data: inventory
      });

    } catch (error) {
      console.error('Add inventory error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to add inventory',
        error: error.message
      });
    }
  }

  /**
   * Update inventory pricing
   */
  async updatePricing(req, res) {
    try {
      const { inventoryId } = req.params;
      const { basePrice, premiumPercentage, currentMarketPrice } = req.body;

      const inventory = await Inventory.findOne({ inventoryId });

      if (!inventory) {
        return res.status(404).json({
          success: false,
          message: 'Inventory not found'
        });
      }

      inventory.pricing = {
        basePrice: basePrice || inventory.pricing.basePrice,
        premiumPercentage: premiumPercentage || inventory.pricing.premiumPercentage,
        currentMarketPrice: currentMarketPrice || inventory.pricing.currentMarketPrice,
        lastUpdated: new Date()
      };

      await inventory.save();

      res.status(200).json({
        success: true,
        message: 'Pricing updated successfully',
        data: inventory.pricing
      });

    } catch (error) {
      console.error('Update pricing error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to update pricing',
        error: error.message
      });
    }
  }

  /**
   * Transfer inventory between vaults
   */
  async transferInventory(req, res) {
    try {
      const { inventoryId } = req.params;
      const { toVaultId, quantity, notes } = req.body;

      const inventory = await Inventory.findOne({ inventoryId });

      if (!inventory) {
        return res.status(404).json({
          success: false,
          message: 'Inventory not found'
        });
      }

      if (inventory.quantity.available < quantity) {
        return res.status(400).json({
          success: false,
          message: 'Insufficient available inventory'
        });
      }

      // Update quantities
      inventory.quantity.available -= quantity;

      // Record movement
      inventory.movements.push({
        type: 'TRANSFERRED',
        quantity,
        date: new Date(),
        reference: toVaultId,
        notes: notes || `Transferred to vault ${toVaultId}`
      });

      inventory.status = 'IN_TRANSIT';

      await inventory.save();

      res.status(200).json({
        success: true,
        message: 'Transfer initiated successfully',
        data: inventory
      });

    } catch (error) {
      console.error('Transfer inventory error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to transfer inventory',
        error: error.message
      });
    }
  }

  /**
   * Schedule inventory audit
   */
  async scheduleAudit(req, res) {
    try {
      const { inventoryId } = req.params;
      const { auditDate, auditedBy } = req.body;

      const inventory = await Inventory.findOne({ inventoryId });

      if (!inventory) {
        return res.status(404).json({
          success: false,
          message: 'Inventory not found'
        });
      }

      inventory.audit.nextAuditDate = new Date(auditDate);
      inventory.audit.auditedBy = auditedBy;

      await inventory.save();

      res.status(200).json({
        success: true,
        message: 'Audit scheduled successfully',
        data: inventory.audit
      });

    } catch (error) {
      console.error('Schedule audit error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to schedule audit',
        error: error.message
      });
    }
  }

  /**
   * Get real-time inventory availability
   */
  async checkAvailability(req, res) {
    try {
      const { goldType, quantity } = req.query;

      const inventory = await Inventory.findOne({
        goldType,
        status: 'AVAILABLE',
        'quantity.available': { $gte: parseFloat(quantity) }
      }).lean();

      if (!inventory) {
        return res.status(200).json({
          success: true,
          available: false,
          message: 'Insufficient inventory'
        });
      }

      res.status(200).json({
        success: true,
        available: true,
        inventory: {
          inventoryId: inventory.inventoryId,
          availableQuantity: inventory.quantity.available,
          location: inventory.location,
          pricing: inventory.pricing
        }
      });

    } catch (error) {
      console.error('Check availability error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to check availability',
        error: error.message
      });
    }
  }

  /**
   * Get inventory movements history
   */
  async getMovements(req, res) {
    try {
      const { inventoryId } = req.params;

      const inventory = await Inventory.findOne({ inventoryId })
        .select('inventoryId goldType movements')
        .lean();

      if (!inventory) {
        return res.status(404).json({
          success: false,
          message: 'Inventory not found'
        });
      }

      res.status(200).json({
        success: true,
        data: {
          inventoryId: inventory.inventoryId,
          goldType: inventory.goldType,
          movements: inventory.movements
        }
      });

    } catch (error) {
      console.error('Get movements error:', error);
      res.status(500).json({
        success: false,
        message: 'Failed to retrieve movements',
        error: error.message
      });
    }
  }

  /**
   * Calculate inventory summary
   */
  calculateInventorySummary(inventory) {
    const summary = {
      totalValue: 0,
      byGoldType: {},
      byVault: {},
      totalAvailable: 0,
      totalReserved: 0
    };

    inventory.forEach(item => {
      const value = item.quantity.total * item.pricing.currentMarketPrice;
      summary.totalValue += value;
      summary.totalAvailable += item.quantity.available;
      summary.totalReserved += item.quantity.reserved;

      // By gold type
      if (!summary.byGoldType[item.goldType]) {
        summary.byGoldType[item.goldType] = {
          quantity: 0,
          value: 0
        };
      }
      summary.byGoldType[item.goldType].quantity += item.quantity.total;
      summary.byGoldType[item.goldType].value += value;

      // By vault
      const vaultId = item.location.vaultId;
      if (!summary.byVault[vaultId]) {
        summary.byVault[vaultId] = {
          quantity: 0,
          value: 0
        };
      }
      summary.byVault[vaultId].quantity += item.quantity.total;
      summary.byVault[vaultId].value += value;
    });

    return summary;
  }
}

module.exports = new InventoryController();
