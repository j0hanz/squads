# TDD Patterns for JavaScript and TypeScript

## Test Runner Equivalents

| Python (pytest)             | JavaScript (Jest/Vitest)       |
| --------------------------- | ------------------------------ |
| `def test_foo():`           | `test('foo', () => { ... })`   |
| `assert x == y`             | `expect(x).toBe(y)`            |
| `pytest.raises(ValueError)` | `expect(() => fn()).toThrow()` |
| `pytest test_foo.py`        | `npx jest foo.test.ts`         |
| `ModuleNotFoundError`       | `Cannot find module './foo'`   |
| `AssertionError`            | `Expected X to equal Y`        |

## Basic RED-GREEN Cycle

**Step 1 — Write the failing test first:**

```typescript
// discount.test.ts (written before discount.ts exists)
import { calculateDiscount } from './discount';

test('applies 10% discount to base price', () => {
  expect(calculateDiscount(100, 10)).toBe(90);
});
```

**Run: RED — environment failure**

`Cannot find module './discount' from 'discount.test.ts'`

**Step 2 — Create stub:**

```typescript
// discount.ts
export function calculateDiscount(price: number, discountPercent: number): number {
  return 0; // stub
}
```

**Run: RED — assertion failure (correct RED state)**

```
Expected: 90
Received: 0
```

**Step 3 — Minimal implementation:**

```typescript
export function calculateDiscount(price: number, discountPercent: number): number {
  return price * (1 - discountPercent / 100);
}
```

**Run: GREEN**

## Describe/It Nesting (when to use)

Use `describe` only to group tests for the **same unit** — not to batch tests for different behaviors:

```typescript
// RIGHT: describe groups tests for one function
describe('calculateDiscount', () => {
  test('applies percentage discount', () => { ... });
  test('returns original price when discount is 0', () => { ... });
  test('throws when price is negative', () => { ... });
});
```

// WRONG: describe used to batch unrelated behaviors (still horizontal slicing)

```typescript
describe('discount module', () => {
  test('calculateDiscount works', () => { ... });
  test('applyPromoCode works', () => { ... });  // different function — own cycle
});
```

## Async Functions

For async code, the TDD loop is the same — just use `async/await` in tests:

```typescript
// RED first
test('fetches user by id', async () => {
  const user = await fetchUser('u-123');
  expect(user.name).toBe('Alice');
});
```

**Important**: Async tests that never await will silently pass. Always verify the test actually reaches the assertion:

```typescript
// WRONG — the promise is never awaited; the test returns synchronously with zero
// assertions run, so the framework reports a pass
test('fetches user', () => {
  fetchUser('u-123').then(user => expect(user.name).toBe('Alice'));
});
```

// RIGHT — explicitly check assertion reached

```typescript
test('fetches user', async () => {
  expect.assertions(1); // Jest: fails if no assertion runs
  const user = await fetchUser('u-123');
  expect(user.name).toBe('Alice');
});
```

## TypeScript: Type Errors as a Form of RED

In TypeScript, a type error is a valid RED state — the type system is failing on your assertion. Treat it the same as an AssertionError:

- Type error on missing property → add the property (environment fix)
- Type error on wrong return type → fix the impl (logic fix)

Do NOT add `// @ts-ignore` to bypass type failures. Fix the type, just like you'd fix a failing assertion.

```typescript
// RED — type error IS a failing test
const result: number = calculateDiscount('100', 10); // TS: Argument of type 'string' is not assignable to 'number'

// GREEN — fix the implementation or the test input
const result: number = calculateDiscount(100, 10);
```

## Mocking at System Boundaries Only

Examples for the Strict Rules mocking rule (mock only true externals):

```typescript
// RIGHT — mocking an external HTTP call (system boundary)
jest.mock('./httpClient');
const mockGet = jest.fn().mockResolvedValue({ id: '123', name: 'Alice' });
(httpClient.get as jest.Mock) = mockGet;

// WRONG — mocking an internal collaborator
jest.mock('./userRepository'); // internal class — test the real thing
```

## Failure Analysis in JavaScript

| Failure message                               | Type        | Action                                                 |
| --------------------------------------------- | ----------- | ------------------------------------------------------ |
| `Cannot find module './foo'`                  | Environment | Create the module with a stub export                   |
| `foo is not a function`                       | Environment | Add the missing export                                 |
| `Expected X, received undefined`              | Logic       | Function returned wrong value — fix impl               |
| `Expected: true, Received: false`             | Logic       | Wrong boolean logic — fix condition                    |
| `TypeError: Cannot read property 'x' of null` | Unexpected  | Debug — may be flawed test setup or missing null guard |
