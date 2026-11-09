/**
 * Savyant Systems - Interactive Order Form Management (Part 7)
 * - Product selection fetching price and stock via REST API
 * - Dynamic rows addition and removal without page reload
 * - Live real-time calculations (item amount, subtotal, discount, grand total)
 * - Strict client-side input validation
 * - Duplicate submission prevention
 */

document.addEventListener('DOMContentLoaded', () => {
    const tableBody = document.getElementById('orderItemsTableBody');
    const addRowBtn = document.getElementById('addRowBtn');
    const discountInput = document.getElementById('discountInput');
    const orderForm = document.getElementById('orderForm');
    const submitBtn = document.getElementById('submitOrderBtn');
    const validationAlert = document.getElementById('validationAlert');

    // Display elements for live calculation
    const subtotalDisplay = document.getElementById('subtotalDisplay');
    const discountAmountDisplay = document.getElementById('discountAmountDisplay');
    const grandTotalDisplay = document.getElementById('grandTotalDisplay');

    // Cache of fetched product details: { productId: { price, stock, code, name } }
    const productCache = {};

    function showValidationError(message) {
        if (!validationAlert) return;
        validationAlert.textContent = message;
        validationAlert.style.display = 'block';
        validationAlert.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function clearValidationError() {
        if (!validationAlert) return;
        validationAlert.textContent = '';
        validationAlert.style.display = 'none';
    }

    /**
     * Fetch product details (price and available stock) from the REST API
     */
    async function fetchProductDetails(productId) {
        if (!productId) return null;
        if (productCache[productId]) {
            return productCache[productId];
        }

        try {
            const response = await fetch(`/api/products/${productId}/`, {
                headers: { 'Accept': 'application/json' }
            });
            if (!response.ok) {
                throw new Error('Failed to fetch product details.');
            }
            const data = await response.json();
            productCache[productId] = {
                price: parseFloat(data.price),
                stock: parseInt(data.stock_quantity, 10),
                code: data.product_code,
                name: data.name
            };
            return productCache[productId];
        } catch (err) {
            console.error(err);
            return null;
        }
    }

    /**
     * Add a new dynamic item row to the table
     */
    function addRow() {
        const rowCount = tableBody.querySelectorAll('tr').length;
        const row = document.createElement('tr');
        row.className = 'item-row';
        row.innerHTML = `
            <td>
                <select name="product_id[]" class="form-select product-select" required>
                    <option value="">-- Select Product --</option>
                    ${window.AVAILABLE_PRODUCTS.map(p => `
                        <option value="${p.id}" data-price="${p.price}" data-stock="${p.stock}">
                            ${p.code} - ${p.name}
                        </option>
                    `).join('')}
                </select>
            </td>
            <td>
                <span class="stock-badge badge badge-inactive">Select product</span>
            </td>
            <td>
                <input type="number" name="quantity[]" class="form-control item-qty" min="1" step="1" value="1" required style="max-width: 110px;">
            </td>
            <td>
                <input type="text" class="form-control item-rate" readonly value="0.00" style="max-width: 130px; background: #f8fafc;">
            </td>
            <td>
                <span class="item-amount" style="font-weight: 600;">0.00</span>
            </td>
            <td style="text-align: center;">
                <button type="button" class="btn btn-danger btn-sm remove-row-btn" title="Remove Item">
                    ✕
                </button>
            </td>
        `;

        tableBody.appendChild(row);
        attachRowEvents(row);
        calculateOrderTotals();
    }

    /**
     * Attach change, input, and removal events to a row
     */
    function attachRowEvents(row) {
        const select = row.querySelector('.product-select');
        const qtyInput = row.querySelector('.item-qty');
        const rateInput = row.querySelector('.item-rate');
        const stockBadge = row.querySelector('.stock-badge');
        const removeBtn = row.querySelector('.remove-row-btn');

        // Product selection changed
        select.addEventListener('change', async () => {
            clearValidationError();
            const productId = select.value;

            if (!productId) {
                rateInput.value = '0.00';
                stockBadge.textContent = 'Select product';
                stockBadge.className = 'stock-badge badge badge-inactive';
                calculateOrderTotals();
                return;
            }

            // Check if duplicate product already selected in another row
            const allSelected = Array.from(tableBody.querySelectorAll('.product-select'))
                .map(s => s.value)
                .filter(v => v !== '');

            const duplicateCount = allSelected.filter(v => v === productId).length;
            if (duplicateCount > 1) {
                showValidationError(`Duplicate product selected. You cannot add the same product multiple times to one order.`);
                select.value = '';
                rateInput.value = '0.00';
                stockBadge.textContent = 'Duplicate';
                stockBadge.className = 'stock-badge badge badge-cancelled';
                calculateOrderTotals();
                return;
            }

            // Fetch live price & stock via API
            const details = await fetchProductDetails(productId);
            if (details) {
                rateInput.value = details.price.toFixed(2);
                stockBadge.textContent = `${details.stock} in stock`;
                stockBadge.className = details.stock > 0 ? 'stock-badge badge badge-confirmed' : 'stock-badge badge badge-cancelled';
            } else {
                // Fallback to data attributes
                const selectedOpt = select.options[select.selectedIndex];
                const price = parseFloat(selectedOpt.getAttribute('data-price') || '0');
                const stock = parseInt(selectedOpt.getAttribute('data-stock') || '0', 10);
                rateInput.value = price.toFixed(2);
                stockBadge.textContent = `${stock} in stock`;
                stockBadge.className = stock > 0 ? 'stock-badge badge badge-confirmed' : 'stock-badge badge badge-cancelled';
            }

            calculateOrderTotals();
        });

        // Quantity input changed
        qtyInput.addEventListener('input', () => {
            clearValidationError();
            calculateOrderTotals();
        });

        // Remove row
        removeBtn.addEventListener('click', () => {
            const totalRows = tableBody.querySelectorAll('.item-row').length;
            if (totalRows <= 1) {
                showValidationError("An order must contain at least one product item row.");
                return;
            }
            row.remove();
            clearValidationError();
            calculateOrderTotals();
        });
    }

    /**
     * Live Calculations (Part 5 & Part 7):
     * Item Amount = Quantity * Rate
     * Subtotal = Sum of Item Amounts
     * Discount Amount = Subtotal * Discount Percentage / 100
     * Grand Total = Subtotal - Discount Amount
     */
    function calculateOrderTotals() {
        let subtotal = 0;
        const rows = tableBody.querySelectorAll('.item-row');

        rows.forEach(row => {
            const qtyInput = row.querySelector('.item-qty');
            const rateInput = row.querySelector('.item-rate');
            const amountSpan = row.querySelector('.item-amount');

            const qty = parseInt(qtyInput.value, 10) || 0;
            const rate = parseFloat(rateInput.value) || 0;
            const itemAmount = qty * rate;

            amountSpan.textContent = itemAmount.toFixed(2);
            subtotal += itemAmount;
        });

        let discountPct = parseFloat(discountInput.value) || 0;
        if (discountPct < 0) discountPct = 0;
        if (discountPct > 20) discountPct = 20;

        const discountAmount = (subtotal * discountPct) / 100;
        const grandTotal = subtotal - discountAmount;

        if (subtotalDisplay) subtotalDisplay.textContent = subtotal.toFixed(2);
        if (discountAmountDisplay) discountAmountDisplay.textContent = discountAmount.toFixed(2);
        if (grandTotalDisplay) grandTotalDisplay.textContent = grandTotal.toFixed(2);
    }

    // Attach listeners
    if (addRowBtn) {
        addRowBtn.addEventListener('click', addRow);
    }

    if (discountInput) {
        discountInput.addEventListener('input', () => {
            clearValidationError();
            const val = parseFloat(discountInput.value);
            if (val < 0 || val > 20) {
                showValidationError("Discount percentage must be strictly between 0 and 20%.");
            }
            calculateOrderTotals();
        });
    }

    // Initial setup: attach to existing rows or add one default row
    const existingRows = tableBody.querySelectorAll('.item-row');
    if (existingRows.length > 0) {
        existingRows.forEach(row => attachRowEvents(row));
        calculateOrderTotals();
    } else {
        addRow();
    }

    // Form submit validation & duplicate submission prevention
    if (orderForm) {
        orderForm.addEventListener('submit', (e) => {
            clearValidationError();

            const customerSelect = document.getElementById('customerSelect');
            if (!customerSelect || !customerSelect.value) {
                e.preventDefault();
                showValidationError("Please select a customer for this order.");
                return false;
            }

            const rows = tableBody.querySelectorAll('.item-row');
            if (rows.length === 0) {
                e.preventDefault();
                showValidationError("An order must contain at least one item.");
                return false;
            }

            const selectedProductIds = [];
            for (let i = 0; i < rows.length; i++) {
                const row = rows[i];
                const select = row.querySelector('.product-select');
                const qtyInput = row.querySelector('.item-qty');

                if (!select.value) {
                    e.preventDefault();
                    showValidationError(`Row ${i + 1}: Please select a product.`);
                    select.focus();
                    return false;
                }

                const qty = parseInt(qtyInput.value, 10);
                if (isNaN(qty) || qty <= 0) {
                    e.preventDefault();
                    showValidationError(`Row ${i + 1}: Product quantity must be a whole number greater than 0.`);
                    qtyInput.focus();
                    return false;
                }

                if (selectedProductIds.includes(select.value)) {
                    e.preventDefault();
                    showValidationError(`Duplicate products detected. Remove duplicate rows before submitting.`);
                    return false;
                }
                selectedProductIds.push(select.value);
            }

            const discount = parseFloat(discountInput.value || '0');
            if (isNaN(discount) || discount < 0 || discount > 20) {
                e.preventDefault();
                showValidationError("Discount percentage must be between 0 and 20.");
                discountInput.focus();
                return false;
            }

            // Disable submit button while request is processing to prevent duplicate submissions
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = 'Submitting Order...';
            }
        });
    }
});
