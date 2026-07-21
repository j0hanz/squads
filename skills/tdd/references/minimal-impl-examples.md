---
description: >-
  Worked examples of the smallest GREEN implementation per domain (math,
  validation, parsing, classes) — how minimal is minimal in Step 2 of the
  TDD cycle. Examples are Python; the shape applies to any language.
metadata:
  tags: [tdd, green, minimal-implementation, examples]
---

# Minimal Implementation: Domain-Specific Patterns

Rule: do only what test want, no more. Python shown, make fit own stack.

## Math Functions: Direct Formula

```python
# Test: assert calculate_discount(100, 10) == 90

def calculate_discount(price, discount_percent):
    return price * (1 - discount_percent / 100)
```

```python
# NOT minimal (adds validation not yet tested)
def calculate_discount(price, discount_percent):
    if price < 0:
        raise ValueError("Price must be >= 0")
    return price * (1 - discount_percent / 100)
```

Add check when test for check come.

## Validation Functions: Simple Boolean Check

```python
# Test: assert validator.validate_email("x@y.com") == True

def validate_email(self, email):
    return '@' in email
```

```python
# NOT minimal (adds regex not yet tested)
def validate_email(self, email):
    import re
    return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', email))
```

Add regex when RFC test come.

## Parsing / String Processing: Iterate As Needed

```python
# Test: assert parse("a,b,c") == ["a", "b", "c"]

# Minimal (correct) — iteration is necessary to pass this test
def parse(self, line):
    return line.split(',')
```

```python
# Later test: assert parse("a,b\nc,d") handles newlines
# Minimal (correct) at this point
def parse(self, data):
    return [line.split(',') for line in data.split('\n')]
```

Each feature get own test and small code.

## Classes: Extract Helpers Only On Duplication

```python
# Test 1: assert validator.validate_email() == True
class UserValidator:
    def validate_email(self, email):
        return '@' in email
```

```python
# Test 2: assert validator.validate_password() == True
# Minimal (correct) — no helper extracted yet (no duplicated logic)
class UserValidator:
    def validate_email(self, email):
        return '@' in email
    def validate_password(self, pwd):
        return '#' in pwd  # requires a symbol — same "contains required char" shape
```

```python
# Test 3: assert combined validation — both methods now check "contains a required char"
# NOW extract (correct): _contains_required_character(email, '@') and _contains_required_character(pwd, '#')
def _contains_required_character(self, text, char):
    return char in text
```

Make helper only when code copy-paste happen � not "just in case".
