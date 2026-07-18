# TDD Patterns for JavaScript and TypeScript

## Basic RED-GREEN Cycle

Two RED states: `Cannot find module` is environment RED — stub the module until the failure becomes an assertion failure (`Expected: 90, Received: 0`), the correct RED to implement against. See the Failure Analysis table below for the full mapping.

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

```typescript
// WRONG: describe used to batch unrelated behaviors (still horizontal slicing)
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

**Important:** Async tests that never await silently pass. Always verify the test reaches the assertion:

```typescript
// WRONG — the promise is never awaited; the test returns synchronously with zero
// assertions run, so the framework reports a pass
test('fetches user', () => {
  fetchUser('u-123').then((user) => expect(user.name).toBe('Alice'));
});
```

```typescript
// RIGHT — explicitly check the assertion reached
test('fetches user', async () => {
  expect.assertions(1); // Jest: fails if no assertion runs
  const user = await fetchUser('u-123');
  expect(user.name).toBe('Alice');
});
```

> **Vitest/Mocha:** `expect.assertions` is Jest-only. In Vitest, await the promise directly (`await expect(fetchUser('u-123')).resolves.toEqual(...)`) so an un-awaited rejection fails the run.

## TypeScript: Type Errors as a Form of RED

A type error is a valid RED state — treat it like an AssertionError: missing property → environment fix; wrong return type → implementation fix. Never add `// @ts-ignore` to bypass a type failure; fix the type as you would a failing assertion.

## Mocking at System Boundaries Only

Apply SKILL.md's mocking rule in Jest terms: `jest.mock('./httpClient')` (external HTTP boundary) is RIGHT; `jest.mock('./userRepository')` (internal collaborator) is WRONG — test the real thing.

## Failure Analysis in JavaScript

| Failure message                               | Type        | Action                                                 |
| --------------------------------------------- | ----------- | ------------------------------------------------------ |
| `Cannot find module './foo'`                  | Environment | Create the module with a stub export                   |
| `foo is not a function`                       | Environment | Add the missing export                                 |
| `Expected X, received undefined`              | Logic       | Function returned wrong value — fix impl               |
| `Expected: true, Received: false`             | Logic       | Wrong boolean logic — fix condition                    |
| `TypeError: Cannot read property 'x' of null` | Unexpected  | Debug — may be flawed test setup or missing null guard |
