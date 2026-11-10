# XUnit Test Specifications (TypeScript / Jest & Integration Spec)

## 1. Gateway Proxy Tests
- **Test 1.1**: Verify `POST /api/banksmart/facilities` forwards payload with PascalCase `SignOnRq` and Basic Auth headers.
- **Test 1.2**: Verify `POST /api/banksmart/payout` uses lowercase `signOnRq` envelope casing.
- **Test 1.3**: Verify commodity booking injects `2031-08-01T00:00:00+08:00` into `invoiceDate`.

## 2. SLA Engine Tests
- **Test 2.1**: TAT >= 6 hours computes `ON_TRACK`.
- **Test 2.2**: TAT < 6 hours computes `WARNING`.
- **Test 2.3**: TAT > 24 hours computes `BREACHED`.

## 3. Grounded Test Cases Validation
- **Test 3.1 (Case 1)**: Verify Sample Customer A (CIF 50000248) displays 141 DPD overdue, PKR 27,000 outstanding, and PKR 1,420.50 overdue profit in Stage 2/3 Watchlist.
- **Test 3.2 (Case 2)**: Verify Sample Customer B (CIF 50000231) displays 65 DPD default and PKR 327,563.37 principal due in Stage 3 Default.
- **Test 3.3 (Case 3)**: Verify multi-loan facility rendering for Customer A with sub-loan 1 and sub-loan 2 running concurrently.
- **Test 3.4 (Case 4)**: Execute full 5-gate Murabaha Origination wizard flow for Customer B with limit check, inventory booking, loan execution, payout, and completion certificate.