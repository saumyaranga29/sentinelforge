# Calculator System Specification

## Overview
The calculator module provides clean arithmetic helper operations for educational and calculation purposes.

## Core Functions
1. `add(a, b)`: Returns arithmetic sum of two floats.
2. `subtract(a, b)`: Returns difference `a - b`.
3. `multiply(a, b)`: Computes product `a * b`.
4. `divide(a, b)`: Computes division `a / b`.

## Error Handling Specifications
- In `divide(a, b)`, when divisor `b` equals 0, the function must raise a `ValueError("Cannot divide by zero")`.
- Under no circumstances should division by zero return `None` or cause an unhandled `ZeroDivisionError`.

## Testing Policy
Unit test fixtures in `test_calculator.py` must run inside the sandboxed environment before any code modification is presented for human review.

